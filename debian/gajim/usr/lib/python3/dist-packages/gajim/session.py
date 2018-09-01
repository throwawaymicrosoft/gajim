# -*- coding:utf-8 -*-
## src/session.py
##
## Copyright (C) 2008-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import string
import random
import itertools

from gajim.common import helpers
from gajim.common import events
from gajim.common import app
from gajim.common import contacts
from gajim.common import ged
from gajim.common.connection_handlers_events import ChatstateReceivedEvent, \
    InformationEvent
from gajim.common.const import KindConstant
from gajim import message_control
from gajim import notify
from gajim.gtk import SingleMessageWindow


class ChatControlSession(object):
    def __init__(self, conn, jid, thread_id, type_='chat'):
        self.conn = conn
        self.jid = jid
        self.type_ = type_
        self.resource = jid.getResource()
        self.control = None

        if thread_id:
            self.received_thread_id = True
            self.thread_id = thread_id
        else:
            self.received_thread_id = False
            if type_ == 'normal':
                self.thread_id = None
            else:
                self.thread_id = self.generate_thread_id()

        self.loggable = True

        self.last_send = 0
        self.last_receive = 0

        app.ged.register_event_handler('decrypted-message-received',
                                       ged.PREGUI,
                                       self._nec_decrypted_message_received)

    def generate_thread_id(self):
        return ''.join(
            [f(string.ascii_letters) for f in itertools.repeat(
                random.choice, 32)]
        )

    def is_loggable(self):
        return app.config.should_log(self.conn.name,
                                     self.jid.getStripped())

    def get_to(self):
        to = str(self.jid)
        return app.get_jid_without_resource(to) + '/' + self.resource

    def _nec_decrypted_message_received(self, obj):
        """
        Dispatch a received <message> stanza
        """
        if obj.session != self:
            return
        contact = app.contacts.get_contact(self.conn.name, obj.jid,
            obj.resource)
        if not contact:
            contact = app.contacts.get_gc_contact(self.conn.name, obj.jid,
                obj.resource)
        if self.resource != obj.resource:
            self.resource = obj.resource
            if self.control:
                if isinstance(contact, contacts.GC_Contact):
                    self.control.gc_contact = contact
                    self.control.contact = contact.as_contact()
                else:
                    self.control.contact = contact
                if self.control.resource:
                    self.control.change_resource(self.resource)

        if obj.mtype == 'chat':
            if not obj.msgtxt and obj.chatstate is None:
                return

            log_type = KindConstant.CHAT_MSG_RECV
            if obj.forwarded and obj.sent:
                log_type = KindConstant.CHAT_MSG_SENT
        else:
            log_type = KindConstant.SINGLE_MSG_RECV
            if obj.forwarded and obj.sent:
                log_type = KindConstant.SINGLE_MSG_SENT

        treat_as = app.config.get('treat_incoming_messages')
        if treat_as:
            obj.mtype = treat_as
        pm = False
        if obj.muc_pm or (obj.gc_control and obj.resource):
            # It's a Private message
            pm = True
            obj.mtype = 'pm'

        if self.is_loggable() and obj.msgtxt:
            if obj.xhtml and app.config.get('log_xhtml_messages'):
                msg_to_log = obj.xhtml
            else:
                msg_to_log = obj.msgtxt

            jid = obj.fjid
            if not pm:
                jid = obj.jid

            obj.msg_log_id = app.logger.insert_into_logs(
                self.conn.name, jid, obj.timestamp, log_type,
                message=msg_to_log,
                subject=obj.subject,
                additional_data=obj.additional_data,
                stanza_id=obj.unique_id)

        self.conn.get_module('MAM').save_archive_id(
            None, obj.stanza_id, obj.timestamp)

        if obj.muc_pm and not obj.gc_control:
            # This is a carbon of a PM from a MUC we are not currently
            # joined. We log it silently without notification.
            return True

        # Handle chat states
        if contact and (not obj.forwarded or not obj.sent):
            if self.control and self.control.type_id == \
            message_control.TYPE_CHAT:
                if obj.chatstate is not None:
                    # other peer sent us reply, so he supports jep85 or jep22
                    contact.chatstate = obj.chatstate
                    if contact.our_chatstate == 'ask': # we were jep85 disco?
                        contact.our_chatstate = 'active' # no more
                    app.nec.push_incoming_event(ChatstateReceivedEvent(None,
                        conn=obj.conn, msg_obj=obj))
                elif contact.chatstate != 'active':
                    # got no valid jep85 answer, peer does not support it
                    contact.chatstate = False
            elif obj.chatstate == 'active':
                # Brand new message, incoming.
                contact.our_chatstate = obj.chatstate
                contact.chatstate = obj.chatstate

        # THIS MUST BE AFTER chatstates handling
        # AND BEFORE playsound (else we hear sounding on chatstates!)
        if not obj.msgtxt: # empty message text
            return True

        if app.config.get_per('accounts', self.conn.name,
        'ignore_unknown_contacts') and not app.contacts.get_contacts(
        self.conn.name, obj.jid) and not pm:
            return True

        highest_contact = app.contacts.get_contact_with_highest_priority(
            self.conn.name, obj.jid)

        # does this resource have the highest priority of any available?
        is_highest = not highest_contact or not highest_contact.resource or \
            obj.resource == highest_contact.resource or highest_contact.show ==\
            'offline'

        if not self.control:
            ctrl = app.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
                if isinstance(contact, contacts.GC_Contact):
                    self.control.gc_contact = contact
                    self.control.contact = contact.as_contact()
                else:
                    self.control.contact = contact

        if not pm:
            self.roster_message2(obj)

        if app.interface.remote_ctrl:
            app.interface.remote_ctrl.raise_signal('NewMessage', (
                self.conn.name, [obj.fjid, obj.msgtxt, obj.timestamp,
                obj.encrypted, obj.mtype, obj.subject, obj.chatstate,
                obj.msg_log_id, obj.user_nick, obj.xhtml, obj.form_node]))

    def roster_message2(self, obj):
        """
        Display the message or show notification in the roster
        """
        contact = None
        jid = obj.jid
        resource = obj.resource

        fjid = jid

        # Try to catch the contact with correct resource
        if resource:
            fjid = jid + '/' + resource
            contact = app.contacts.get_contact(obj.conn.name, jid, resource)

        highest_contact = app.contacts.get_contact_with_highest_priority(
            obj.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an
            # invisible resource
            lcontact = app.contacts.get_contacts(obj.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = app.contacts.copy_contact(highest_contact)
                contact.resource = resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                app.contacts.add_contact(obj.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = app.interface.roster.add_to_not_in_the_roster(
                obj.conn.name, jid, obj.user_nick)

        if not self.control:
            ctrl = app.interface.msg_win_mgr.search_control(obj.jid,
                obj.conn.name, obj.resource)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        obj.popup = helpers.allow_popup_window(self.conn.name)

        event_t = events.ChatEvent
        event_type = 'message_received'

        if obj.mtype == 'normal':
            event_t = events.NormalEvent
            event_type = 'single_message_received'

        if self.control and obj.mtype != 'normal':
            # We have a ChatControl open
            obj.show_in_roster = False
            obj.show_in_systray = False
            do_event = False
        elif obj.forwarded and obj.sent:
            # Its a Carbon Copied Message we sent
            obj.show_in_roster = False
            obj.show_in_systray = False
            unread_events = app.events.get_events(
                self.conn.name, fjid, types=['chat'])
            read_ids = []
            for msg in unread_events:
                read_ids.append(msg.msg_log_id)
            app.logger.set_read_messages(read_ids)
            app.events.remove_events(self.conn.name, fjid, types=['chat'])
            do_event = False
        else:
            # Everything else
            obj.show_in_roster = notify.get_show_in_roster(event_type,
                self.conn.name, contact.jid, self)
            obj.show_in_systray = notify.get_show_in_systray(event_type,
                self.conn.name, contact.jid)
            if obj.mtype == 'normal' and obj.popup:
                do_event = False
            else:
                do_event = True
        if do_event:
            event = event_t(obj.msgtxt, obj.subject, obj.mtype, obj.timestamp,
                obj.encrypted, obj.resource, obj.msg_log_id,
                correct_id=(obj.id_, obj.correct_id), xhtml=obj.xhtml,
                session=self, form_node=obj.form_node,
                displaymarking=obj.displaymarking,
                sent_forwarded=obj.forwarded and obj.sent,
                show_in_roster=obj.show_in_roster,
                show_in_systray=obj.show_in_systray,
                additional_data=obj.additional_data)

            app.events.add_event(self.conn.name, fjid, event)

    def roster_message(self, jid, msg, tim, encrypted=False, msg_type='',
    subject=None, resource='', msg_log_id=None, user_nick='', xhtml=None,
    form_node=None, displaymarking=None, additional_data=None):
        """
        Display the message or show notification in the roster
        """
        contact = None
        fjid = jid

        if additional_data is None:
            additional_data = {}

        # Try to catch the contact with correct resource
        if resource:
            fjid = jid + '/' + resource
            contact = app.contacts.get_contact(self.conn.name, jid, resource)

        highest_contact = app.contacts.get_contact_with_highest_priority(
                self.conn.name, jid)
        if not contact:
            # If there is another resource, it may be a message from an invisible
            # resource
            lcontact = app.contacts.get_contacts(self.conn.name, jid)
            if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
            lcontact[0].show != 'offline')) and jid.find('@') > 0:
                contact = app.contacts.copy_contact(highest_contact)
                contact.resource = resource
                if resource:
                    fjid = jid + '/' + resource
                contact.priority = 0
                contact.show = 'offline'
                contact.status = ''
                app.contacts.add_contact(self.conn.name, contact)

            else:
                # Default to highest prio
                fjid = jid
                contact = highest_contact

        if not contact:
            # contact is not in roster
            contact = app.interface.roster.add_to_not_in_the_roster(
                    self.conn.name, jid, user_nick)

        if not self.control:
            ctrl = app.interface.msg_win_mgr.get_control(fjid, self.conn.name)
            if ctrl:
                self.control = ctrl
                self.control.set_session(self)
            else:
                fjid = jid

        # Do we have a queue?
        no_queue = len(app.events.get_events(self.conn.name, fjid)) == 0

        popup = helpers.allow_popup_window(self.conn.name)

        if msg_type == 'normal' and popup: # it's single message to be autopopuped
            SingleMessageWindow(self.conn.name, contact.jid,
                    action='receive', from_whom=jid, subject=subject, message=msg,
                    resource=resource, session=self, form_node=form_node)
            return

        # We print if window is opened and it's not a single message
        if self.control and msg_type != 'normal':
            typ = ''

            if msg_type == 'error':
                typ = 'error'

            self.control.print_conversation(msg, typ, tim=tim, encrypted=encrypted,
                    subject=subject, xhtml=xhtml, displaymarking=displaymarking,
                    additional_data=additional_data)

            if msg_log_id:
                app.logger.set_read_messages([msg_log_id])

            return

        # We save it in a queue
        event_t = events.ChatEvent
        event_type = 'message_received'

        if msg_type == 'normal':
            event_t = events.NormalEvent
            event_type = 'single_message_received'

        show_in_roster = notify.get_show_in_roster(event_type, self.conn.name,
                contact.jid, self)
        show_in_systray = notify.get_show_in_systray(event_type, self.conn.name,
                contact.jid)

        event = event_t(msg, subject, msg_type, tim, encrypted, resource,
            msg_log_id, xhtml=xhtml, session=self, form_node=form_node,
            displaymarking=displaymarking, sent_forwarded=False,
            show_in_roster=show_in_roster, show_in_systray=show_in_systray,
            additional_data=additional_data)

        app.events.add_event(self.conn.name, fjid, event)

        if popup:
            if not self.control:
                self.control = app.interface.new_chat(contact,
                    self.conn.name, session=self)

                if len(app.events.get_events(self.conn.name, fjid)):
                    self.control.read_queue()
        else:
            if no_queue: # We didn't have a queue: we change icons
                app.interface.roster.draw_contact(jid, self.conn.name)

            app.interface.roster.show_title() # we show the * or [n]
        # Select the big brother contact in roster, it's visible because it has
        # events.
        family = app.contacts.get_metacontacts_family(self.conn.name, jid)
        if family:
            nearby_family, bb_jid, bb_account = \
                    app.contacts.get_nearby_family_and_big_brother(family,
                    self.conn.name)
        else:
            bb_jid, bb_account = jid, self.conn.name
        app.interface.roster.select_contact(bb_jid, bb_account)
