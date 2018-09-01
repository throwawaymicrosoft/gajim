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

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.gtk import ErrorDialog
from gajim.gtk.util import get_builder


class AddNewContactWindow(Gtk.ApplicationWindow):

    uid_labels = {'jabber': _('Jabber ID'),
                  'gadu-gadu': _('GG Number'),
                  'icq': _('ICQ Number')}

    def __init__(self, account=None, jid=None, user_nick=None, group=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_resizable(False)
        self.set_title(_('Add Contact'))

        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)

        self.account = account
        self.adding_jid = False

        # fill accounts with active accounts
        accounts = app.get_enabled_accounts_with_labels()

        if not accounts:
            return

        if not account:
            self.account = accounts[0][0]

        self.xml = get_builder('add_new_contact_window.ui')
        self.add(self.xml.get_object('add_contact_box'))
        self.xml.connect_signals(self)

        for w in ('account_combobox', 'account_label', 'prompt_label',
                  'uid_label', 'uid_entry', 'protocol_combobox',
                  'protocol_jid_combobox', 'protocol_label', 'nickname_entry',
                  'message_scrolledwindow', 'save_message_checkbutton',
                  'register_hbox', 'add_button', 'message_textview',
                  'connected_label', 'group_comboboxentry',
                  'auto_authorize_checkbutton', 'save_message_revealer',
                  'nickname_label', 'group_label'):
            self.__dict__[w] = self.xml.get_object(w)

        self.subscription_table = [self.uid_label, self.uid_entry,
                                   self.nickname_label, self.nickname_entry,
                                   self.group_label, self.group_comboboxentry]

        self.add_button.grab_default()

        self.agents = {'jabber': []}
        self.gateway_prompt = {}
        # types to which we are not subscribed but account has an agent for it
        self.available_types = []
        for acct in accounts:
            for j in app.contacts.get_jid_list(acct[0]):
                if app.jid_is_transport(j):
                    type_ = app.get_transport_name_from_jid(j, False)
                    if not type_:
                        continue
                    if type_ in self.agents:
                        self.agents[type_].append(j)
                    else:
                        self.agents[type_] = [j]
                    self.gateway_prompt[j] = {'desc': None, 'prompt': None}
        # Now add the one to which we can register
        for acct in accounts:
            for type_ in app.connections[acct[0]].available_transports:
                if type_ in self.agents:
                    continue
                self.agents[type_] = []
                for jid_ in app.connections[acct[0]].available_transports[type_]:
                    if jid_ not in self.agents[type_]:
                        self.agents[type_].append(jid_)
                        self.gateway_prompt[jid_] = {'desc': None,
                                                     'prompt': None}
                self.available_types.append(type_)

        uf_type = {'jabber': 'XMPP', 'gadu-gadu': 'Gadu Gadu', 'icq': 'ICQ'}
        # Jabber as first
        liststore = self.protocol_combobox.get_model()
        liststore.append(['XMPP', 'xmpp', 'jabber'])
        for type_ in self.agents:
            if type_ == 'jabber':
                continue
            if type_ in uf_type:
                liststore.append([uf_type[type_], type_ + '-online', type_])
            else:
                liststore.append([type_, type_ + '-online', type_])

            if account:
                for service in self.agents[type_]:
                    app.connections[account].request_gateway_prompt(service)
        self.protocol_combobox.set_active(0)
        self.auto_authorize_checkbutton.show()

        if jid:
            self.jid_escaped = True
            type_ = app.get_transport_name_from_jid(jid)
            if not type_:
                type_ = 'jabber'
            if type_ == 'jabber':
                self.uid_entry.set_text(jid)
            else:
                uid, transport = app.get_name_and_server_from_jid(jid)
                self.uid_entry.set_text(uid.replace('%', '@', 1))
            # set protocol_combobox
            model = self.protocol_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][2] == type_:
                    self.protocol_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1

            # set protocol_jid_combobox
            self.protocol_jid_combobox.set_active(0)
            model = self.protocol_jid_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][0] == transport:
                    self.protocol_jid_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1
            if user_nick:
                self.nickname_entry.set_text(user_nick)
            self.nickname_entry.grab_focus()
        else:
            self.jid_escaped = False
            self.uid_entry.grab_focus()
        group_names = []
        for acct in accounts:
            for g in app.groups[acct[0]].keys():
                if g not in helpers.special_groups and g not in group_names:
                    group_names.append(g)
        group_names.sort()
        i = 0
        for g in group_names:
            self.group_comboboxentry.append_text(g)
            if group == g:
                self.group_comboboxentry.set_active(i)
            i += 1

        if len(accounts) > 1:
            liststore = self.account_combobox.get_model()
            for acc in accounts:
                liststore.append(acc)

            self.account_combobox.set_active_id(self.account)
            self.account_label.show()
            self.account_combobox.show()

        if len(self.agents) > 1:
            self.protocol_label.show()
            self.protocol_combobox.show()

        if self.account:
            message_buffer = self.message_textview.get_buffer()
            msg = helpers.from_one_line(helpers.get_subscription_request_msg(
                self.account))
            message_buffer.set_text(msg)

        self.show_all()

        app.ged.register_event_handler('gateway-prompt-received', ged.GUI1,
                                       self._nec_gateway_prompt_received)
        app.ged.register_event_handler('presence-received', ged.GUI1,
                                       self._nec_presence_received)

    def _on_destroy(self, widget):
        app.ged.remove_event_handler('presence-received', ged.GUI1,
                                     self._nec_presence_received)
        app.ged.remove_event_handler('gateway-prompt-received', ged.GUI1,
                                     self._nec_gateway_prompt_received)

    def on_register_button_clicked(self, widget):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        jid = model[row][0]
        from gajim.gtk import ServiceRegistration
        ServiceRegistration(self.account, jid)

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def on_cancel_button_clicked(self, widget):
        """
        When Cancel button is clicked
        """
        self.destroy()

    def on_message_textbuffer_changed(self, widget):
        self.save_message_revealer.show()
        self.save_message_revealer.set_reveal_child(True)

    def on_add_button_clicked(self, widget):
        """
        When Subscribe button is clicked
        """
        jid = self.uid_entry.get_text().strip()
        if not jid:
            ErrorDialog(
                _('%s Missing') % self.uid_label.get_text(),
                _('You must supply the %s of the new contact.' %
                    self.uid_label.get_text())
            )
            return

        model = self.protocol_combobox.get_model()
        row = self.protocol_combobox.get_active_iter()
        type_ = model[row][2]
        if type_ != 'jabber':
            model = self.protocol_jid_combobox.get_model()
            row = self.protocol_jid_combobox.get_active()
            transport = model[row][0]
            if self.account and not self.jid_escaped:
                self.adding_jid = (jid, transport, type_)
                app.connections[self.account].request_gateway_prompt(
                    transport, jid)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        else:
            self._add_jid(jid, type_)

    def _add_jid(self, jid, type_):
        # check if jid is conform to RFC and stringprep it
        try:
            jid = helpers.parse_jid(jid)
        except helpers.InvalidFormat as s:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, str(s))
            return

        # No resource in jid
        if jid.find('/') >= 0:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('The user ID must not contain a resource.'))
            return

        if jid == app.get_jid_from_account(self.account):
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('You cannot add yourself to your roster.'))
            return

        if not app.account_is_connected(self.account):
            ErrorDialog(
                _('Account Offline'),
                _('Your account must be online to add new contacts.')
            )
            return

        nickname = self.nickname_entry.get_text() or ''
        # get value of account combobox, if account was not specified
        if not self.account:
            model = self.account_combobox.get_model()
            index = self.account_combobox.get_active()
            self.account = model[index][1]

        # Check if jid is already in roster
        if jid in app.contacts.get_jid_list(self.account):
            c = app.contacts.get_first_contact_from_jid(self.account, jid)
            if _('Not in Roster') not in c.groups and c.sub in ('both', 'to'):
                ErrorDialog(
                    _('Contact already in roster'),
                    _('This contact is already listed in your roster.'))
                return

        if type_ == 'jabber':
            message_buffer = self.message_textview.get_buffer()
            start_iter = message_buffer.get_start_iter()
            end_iter = message_buffer.get_end_iter()
            message = message_buffer.get_text(start_iter, end_iter, True)
            if self.save_message_checkbutton.get_active():
                msg = helpers.to_one_line(message)
                app.config.set_per('accounts', self.account,
                                   'subscription_request_msg', msg)
        else:
            message = ''
        group = self.group_comboboxentry.get_child().get_text()
        groups = []
        if group:
            groups = [group]
        auto_auth = self.auto_authorize_checkbutton.get_active()
        app.interface.roster.req_sub(
            self, jid, message, self.account,
            groups=groups, nickname=nickname, auto_auth=auto_auth)
        self.destroy()

    def on_account_combobox_changed(self, widget):
        account = widget.get_active_id()
        message_buffer = self.message_textview.get_buffer()
        message_buffer.set_text(helpers.get_subscription_request_msg(account))
        self.account = account

    def on_protocol_jid_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        if not iter_:
            return
        jid_ = model[iter_][0]
        model = self.protocol_combobox.get_model()
        iter_ = self.protocol_combobox.get_active_iter()
        type_ = model[iter_][2]

        desc = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            desc = self.gateway_prompt[jid_]['desc']

        if desc:
            self.prompt_label.set_markup(desc)
            self.prompt_label.show()
        else:
            self.prompt_label.hide()

        prompt = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self.uid_label.set_text(prompt)

    def on_protocol_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        type_ = model[iter_][2]
        model = self.protocol_jid_combobox.get_model()
        model.clear()
        if len(self.agents[type_]):
            for jid_ in self.agents[type_]:
                model.append([jid_])
            self.protocol_jid_combobox.set_active(0)
        desc = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                desc = self.gateway_prompt[jid_]['desc']

        if desc:
            self.prompt_label.set_markup(desc)
            self.prompt_label.show()
        else:
            self.prompt_label.hide()

        if len(self.agents[type_]) > 1:
            self.protocol_jid_combobox.show()
        else:
            self.protocol_jid_combobox.hide()
        prompt = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self.uid_label.set_text(prompt)

        if type_ == 'jabber':
            self.message_scrolledwindow.show()
            self.save_message_checkbutton.show()
        else:
            self.message_scrolledwindow.hide()
            self.save_message_checkbutton.hide()
        if type_ in self.available_types:
            self.register_hbox.show()
            self.auto_authorize_checkbutton.hide()
            self.connected_label.hide()
            self._subscription_table_hide()
            self.add_button.set_sensitive(False)
        else:
            self.register_hbox.hide()
            if type_ != 'jabber':
                model = self.protocol_jid_combobox.get_model()
                row = self.protocol_jid_combobox.get_active()
                jid = model[row][0]
                contact = app.contacts.get_first_contact_from_jid(
                    self.account, jid)
                if contact is None or contact.show in ('offline', 'error'):
                    self._subscription_table_hide()
                    self.connected_label.show()
                    self.add_button.set_sensitive(False)
                    self.auto_authorize_checkbutton.hide()
                    return
            self._subscription_table_show()
            self.auto_authorize_checkbutton.show()
            self.connected_label.hide()
            self.add_button.set_sensitive(True)

    def transport_signed_in(self, jid):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self.register_hbox.hide()
            self.connected_label.hide()
            self._subscription_table_show()
            self.auto_authorize_checkbutton.show()
            self.add_button.set_sensitive(True)

    def transport_signed_out(self, jid):
        model = self.protocol_jid_combobox.get_model()
        row = self.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self._subscription_table_hide()
            self.auto_authorize_checkbutton.hide()
            self.connected_label.show()
            self.add_button.set_sensitive(False)

    def _nec_presence_received(self, obj):
        if app.jid_is_transport(obj.jid):
            if obj.old_show == 0 and obj.new_show > 1:
                self.transport_signed_in(obj.jid)
            elif obj.old_show > 1 and obj.new_show == 0:
                self.transport_signed_out(obj.jid)

    def _nec_gateway_prompt_received(self, obj):
        if self.adding_jid:
            jid, transport, type_ = self.adding_jid
            if obj.stanza.getError():
                ErrorDialog(
                    _('Error while adding transport contact'),
                    _('This error occured while adding a contact for transport '
                      '%(transport)s:\n\n%(error)s') % {
                        'transport': transport,
                        'error': obj.stanza.getErrorMsg()})
                return
            if obj.prompt_jid:
                self._add_jid(obj.prompt_jid, type_)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        elif obj.jid in self.gateway_prompt:
            if obj.desc:
                self.gateway_prompt[obj.jid]['desc'] = obj.desc
            if obj.prompt:
                self.gateway_prompt[obj.jid]['prompt'] = obj.prompt

    def _subscription_table_hide(self):
        for widget in self.subscription_table:
            widget.hide()

    def _subscription_table_show(self):
        for widget in self.subscription_table:
            widget.show()
