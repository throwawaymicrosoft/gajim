# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# Presence handler

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.user_nickname import parse_nickname

log = logging.getLogger('gajim.c.m.presence')


class Presence:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('presence', self._presence_received),
            ('presence', self._subscribe_received, 'subscribe'),
            ('presence', self._subscribed_received, 'subscribed'),
            ('presence', self._unsubscribe_received, 'unsubscribe'),
            ('presence', self._unsubscribed_received, 'unsubscribed'),
        ]

        # keep the jids we auto added (transports contacts) to not send the
        # SUBSCRIBED event to GUI
        self.automatically_added = []

        # list of jid to auto-authorize
        self.jids_for_auto_auth = []

    def _presence_received(self, con, stanza):
        if stanza.getType() in ('subscribe', 'subscribed',
                                'unsubscribe', 'unsubscribed'):
            # Dont handle that here
            return

        log.info('Received from %s', stanza.getFrom())
        app.nec.push_incoming_event(
            NetworkEvent('raw-pres-received',
                         conn=self._con,
                         stanza=stanza))

    def _subscribe_received(self, con, stanza):
        from_ = stanza.getFrom()
        jid = from_.getStripped()
        fjid = str(from_)
        status = stanza.getStatus()
        is_transport = app.jid_is_transport(fjid)
        auto_auth = app.config.get_per('accounts', self._account, 'autoauth')
        user_nick = parse_nickname(stanza)

        log.info('Received Subscribe: %s, transport: %s, auto_auth: %s, '
                 'user_nick: %s', from_, is_transport, auto_auth, user_nick)
        if is_transport and fjid in self._con.agent_registrations:
            self._con.agent_registrations[fjid]['sub_received'] = True
            if not self.agent_registrations[fjid]['roster_push']:
                # We'll reply after roster push result
                raise nbxmpp.NodeProcessed

        if auto_auth or is_transport or jid in self.jids_for_auto_auth:
            presence = nbxmpp.Presence(fjid, 'subscribed')
            presence = self._add_sha(presence)
            self._con.connection.send(presence)

        if not status:
            status = _('I would like to add you to my roster.')

        app.nec.push_incoming_event(NetworkEvent(
            'subscribe-presence-received',
            conn=self._con,
            jid=jid,
            fjid=fjid,
            status=status,
            user_nick=user_nick,
            is_transport=is_transport))

        raise nbxmpp.NodeProcessed

    def _subscribed_received(self, con, stanza):
        from_ = stanza.getFrom()
        jid = from_.getStripped()
        resource = from_.getResource()
        log.info('Received Subscribed: %s', from_)
        if jid in self.automatically_added:
            self.automatically_added.remove(jid)
            raise nbxmpp.NodeProcessed

        app.nec.push_incoming_event(NetworkEvent(
            'subscribed-presence-received',
            conn=self._con, jid=jid, resource=resource))
        raise nbxmpp.NodeProcessed

    def _unsubscribe_received(self, con, stanza):
        log.info('Received Unsubscribe: %s', stanza.getFrom())
        raise nbxmpp.NodeProcessed

    def _unsubscribed_received(self, con, stanza):
        from_ = stanza.getFrom()
        jid = from_.getStripped()
        log.info('Received Unsubscribed: %s', from_)
        app.nec.push_incoming_event(NetworkEvent(
            'unsubscribed-presence-received',
            conn=self._con, jid=jid))
        raise nbxmpp.NodeProcessed

    def subscribed(self, jid):
        if not app.account_is_connected(self._account):
            return
        log.info('Subscribed: %s', jid)
        presence = nbxmpp.Presence(jid, 'subscribed')
        presence = self._add_sha(presence)
        self._con.connection.send(presence)

    def unsubscribed(self, jid):
        if not app.account_is_connected(self._account):
            return
        log.info('Unsubscribed: %s', jid)
        presence = nbxmpp.Presence(jid, 'unsubscribed')
        presence = self._add_sha(presence)
        self._con.connection.send(presence)

    def unsubscribe(self, jid, remove_auth=True):
        if not app.account_is_connected(self._account):
            return
        if remove_auth:
            self._con.getRoster().delItem(jid)
            jid_list = app.config.get_per('contacts')
            for j in jid_list:
                if j.startswith(jid):
                    app.config.del_per('contacts', j)
        else:
            log.info('Unsubscribe from %s', jid)
            self._con.getRoster().Unsubscribe(jid)
            self._con.getRoster().setItem(jid)

    def subscribe(self, jid, msg='', name='', groups=None,
                  auto_auth=False, user_nick=''):
        if not app.account_is_connected(self._account):
            return
        if groups is None:
            groups = []

        log.info('Request Subscription to %s', jid)

        if auto_auth:
            self.jids_for_auto_auth.append(jid)

        infos = {'jid': jid}
        if name:
            infos['name'] = name
        iq = nbxmpp.Iq('set', nbxmpp.NS_ROSTER)
        query = iq.setQuery()
        item = query.addChild('item', attrs=infos)
        for group in groups:
            item.addChild('group').setData(group)
        self._con.connection.send(iq)

        presence = nbxmpp.Presence(jid, 'subscribe')
        if user_nick:
            nick = presence.setTag('nick', namespace=nbxmpp.NS_NICK)
            nick.setData(user_nick)
        presence = self._add_sha(presence)
        if msg:
            presence.setStatus(msg)
        self._con.connection.send(presence)

    def _add_sha(self, presence, send_caps=True):
        vcard = self._con.get_module('VCardAvatars')
        presence = vcard.add_update_node(presence)
        if send_caps:
            return self._add_caps(presence)
        return presence

    def _add_caps(self, presence):
        c = presence.setTag('c', namespace=nbxmpp.NS_CAPS)
        c.setAttr('hash', 'sha-1')
        c.setAttr('node', 'http://gajim.org')
        c.setAttr('ver', app.caps_hash[self._account])
        return presence


def parse_show(stanza):
    show = stanza.getShow()
    type_ = parse_type(stanza)
    if show is None and type_ is None:
        return 'online'

    if type_ == 'unavailable':
        return 'offline'

    if show not in (None, 'chat', 'away', 'xa', 'dnd'):
        log.warning('Invalid show element: %s', stanza)
        if type_ is None:
            return 'online'
        return 'offline'

    if show is None:
        return 'online'
    return show


def parse_type(stanza):
    type_ = stanza.getType()
    if type_ not in (None, 'unavailable', 'error', 'subscribe',
                     'subscribed', 'unsubscribe', 'unsubscribed'):
        log.warning('Invalid type: %s', stanza)
        return None
    return type_


def get_instance(*args, **kwargs):
    return Presence(*args, **kwargs), 'Presence'
