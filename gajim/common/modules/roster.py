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

# Roster

import logging
from collections import namedtuple

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkEvent

log = logging.getLogger('gajim.c.m.roster')

RosterItem = namedtuple('RosterItem', 'jid data')


class Roster:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('iq', self._roster_push_received, 'set', nbxmpp.NS_ROSTER),
            ('presence', self._presence_received)
        ]

        self._data = {}
        self._set = None

    def load_roster(self):
        log.info('Load from database')
        account_jid = self._con.get_own_jid().getStripped()
        data = app.logger.get_roster(account_jid)
        if data:
            self.setRaw(data)
            for jid, item in self._data.items():
                app.nec.push_incoming_event(NetworkEvent(
                    'roster-info',
                    conn=self._con,
                    jid=jid,
                    nickname=item['name'],
                    sub=item['subscription'],
                    ask=item['ask'],
                    groups=item['groups'],
                    avatar_sha=item['avatar_sha']))
        else:
            log.info('Database empty, reset roster version')
            app.config.set_per(
                'accounts', self._account, 'roster_version', '')

        app.nec.push_incoming_event(NetworkEvent(
            'roster-received',
            conn=self._con,
            roster=self._data.copy(),
            received_from_server=False))

    def request_roster(self):
        version = None
        features = self._con.connection.Dispatcher.Stream.features
        if features and features.getTag('ver', namespace=nbxmpp.NS_ROSTER_VER):
            version = app.config.get_per(
                'accounts', self._account, 'roster_version')

        log.info('Requested from server')
        iq = nbxmpp.Iq('get', nbxmpp.NS_ROSTER)
        if version is not None:
            iq.setTagAttr('query', 'ver', version)
        log.info('Request version: %s', version)
        self._con.connection.SendAndCallForResponse(
            iq, self._roster_received)

    def _roster_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Unable to retrive roster: %s', stanza.getError())
        else:
            log.info('Received Roster')
            received_from_server = False
            if stanza.getTag('query') is not None:
                # clear Roster
                self._data = {}
                version = self._parse_roster(stanza)

                log.info('New version: %s', version)
                app.logger.replace_roster(self._account, version, self._data)

                received_from_server = True

            app.nec.push_incoming_event(NetworkEvent(
                'roster-received',
                conn=self._con,
                roster=self._data.copy(),
                received_from_server=received_from_server))

        self._con.connect_machine()

    def _roster_push_received(self, con, stanza):
        log.info('Push received')

        sender = stanza.getFrom()
        if sender is not None:
            if not self._con.get_own_jid().bareMatch(sender):
                log.warning('Wrong JID %s', stanza.getFrom())
                return

        push_items, version = self._parse_push(stanza)

        self._ack_roster_push(stanza)

        for item in push_items:
            attrs = item.data
            app.nec.push_incoming_event(NetworkEvent(
                'roster-info',
                conn=self._con,
                jid=item.jid,
                nickname=attrs['name'],
                sub=attrs['subscription'],
                ask=attrs['ask'],
                groups=attrs['groups'],
                avatar_sha=None))
            account_jid = self._con.get_own_jid().getStripped()
            app.logger.add_or_update_contact(
                account_jid, item.jid, attrs['name'],
                attrs['subscription'], attrs['ask'], attrs['groups'])

        log.info('New version: %s', version)
        app.config.set_per(
            'accounts', self._account, 'roster_version', version)

        raise nbxmpp.NodeProcessed

    def _parse_roster(self, stanza):
        query = stanza.getTag('query')
        version = query.getAttr('ver')

        for item in query.getTags('item'):
            jid = item.getAttr('jid')
            self._data[jid] = self._get_item_attrs(item, update=False)
            log.info('Item %s: %s', jid, self._data[jid])
        return version

    @staticmethod
    def _get_item_attrs(item, update=True):
        '''
        update: True
            returns only the attrs that are present in the item

        update: False
            returns the attrs of the item but fills missing
            attrs with default values
        '''

        default_attrs = {'name': None,
                         'ask': None,
                         'subscription': None,
                         'groups': [],
                         'avatar_sha': None}

        attrs = item.getAttrs()
        del attrs['jid']
        groups = set([group.getData() for group in item.getTags('group')])
        attrs['groups'] = list(groups)

        if update:
            return attrs
        default_attrs.update(attrs)
        return default_attrs

    def _parse_push(self, stanza):
        query = stanza.getTag('query')
        version = query.getAttr('ver')
        push_items = []

        for item in query.getTags('item'):
            push_items.append(self._update_roster_item(item))
        for item in push_items:
            log.info('Push: %s', item)
        return push_items, version

    def _update_roster_item(self, item):
        jid = item.getAttr('jid')

        if item.getAttr('subscription') == 'remove':
            self._data.pop(jid, None)
            attrs = self._get_item_attrs(item, update=False)
            return RosterItem(jid, attrs)

        else:
            if jid not in self._data:
                self._data[jid] = self._get_item_attrs(item, update=False)
            else:
                self._data[jid].update(self._get_item_attrs(item))

            return RosterItem(jid, self._data[jid])

    def _ack_roster_push(self, stanza):
        iq = nbxmpp.Iq('result',
                       to=stanza.getFrom(),
                       frm=stanza.getTo(),
                       attrs={'id': stanza.getID()})
        self._con.connection.send(iq)

    def _presence_received(self, con, pres):
        '''
        Add contacts that request subscription to our internal
        roster and also to the database. The contact is put into the
        'Not in roster' group and because we save it to the database
        it is also after a restart available.
        '''

        if pres.getType() != 'subscribe':
            return

        jid = pres.getFrom().getStripped()

        if jid in self._data:
            return

        log.info('Add Contact from presence %s', jid)
        self._data[jid] = {'name': None,
                           'ask': None,
                           'subscription':
                           'none',
                           'groups': ['Not in roster']}
        account_jid = self._con.get_own_jid().getStripped()
        app.logger.add_or_update_contact(
            account_jid, jid,
            self._data[jid]['name'],
            self._data[jid]['subscription'],
            self._data[jid]['ask'],
            self._data[jid]['groups'])

    def _getItemData(self, jid, dataname):
        """
        Return specific jid's representation in internal format.
        """
        jid = jid[:(jid + '/').find('/')]
        return self._data[jid][dataname]

    def delItem(self, jid):
        """
        Delete contact 'jid' from roster
        """
        self._con.connection.send(
            nbxmpp.Iq('set', nbxmpp.NS_ROSTER, payload=[
                nbxmpp.Node('item', {'jid': jid, 'subscription': 'remove'})]))

    def getGroups(self, jid):
        """
        Return groups list that contact 'jid' belongs to
        """
        return self._getItemData(jid, 'groups')

    def getName(self, jid):
        """
        Return name of contact 'jid'
        """
        return self._getItemData(jid, 'name')

    def setItem(self, jid, name=None, groups=None):
        """
        Rename contact 'jid' and sets the groups list that it now belongs to
        """
        iq = nbxmpp.Iq('set', nbxmpp.NS_ROSTER)
        query = iq.getTag('query')
        attrs = {'jid': jid}
        if name:
            attrs['name'] = name
        item = query.setTag('item', attrs)
        if groups is not None:
            for group in groups:
                item.addChild(node=nbxmpp.Node('group', payload=[group]))
        self._con.connection.send(iq)

    def setItemMulti(self, items):
        """
        Rename multiple contacts and sets their group lists
        """
        for i in items:
            iq = nbxmpp.Iq('set', nbxmpp.NS_ROSTER)
            query = iq.getTag('query')
            attrs = {'jid': i['jid']}
            if i['name']:
                attrs['name'] = i['name']
            item = query.setTag('item', attrs)
            for group in i['groups']:
                item.addChild(node=nbxmpp.Node('group', payload=[group]))
            self._con.connection.send(iq)

    def getItems(self):
        """
        Return list of all [bare] JIDs that the roster is currently tracks
        """
        return list(self._data.keys())

    def keys(self):
        """
        Same as getItems. Provided for the sake of dictionary interface
        """
        return list(self._data.keys())

    def __getitem__(self, item):
        """
        Get the contact in the internal format.
        Raises KeyError if JID 'item' is not in roster
        """
        return self._data[item]

    def getItem(self, item):
        """
        Get the contact in the internal format (or None if JID 'item' is not in
        roster)
        """
        if item in self._data:
            return self._data[item]

    def Unsubscribe(self, jid):
        """
        Ask for removing our subscription for JID 'jid'
        """
        self._con.connection.send(nbxmpp.Presence(jid, 'unsubscribe'))

    def getRaw(self):
        """
        Return the internal data representation of the roster
        """
        return self._data

    def setRaw(self, data):
        """
        Set the internal data representation of the roster
        """
        own_jid = self._con.get_own_jid().getStripped()
        self._data = data
        self._data[own_jid] = {
            'resources': {},
            'name': None,
            'ask': None,
            'subscription': None,
            'groups': None,
            'avatar_sha': None
        }


def get_instance(*args, **kwargs):
    return Roster(*args, **kwargs), 'Roster'
