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

# XEP-0209: Metacontacts

import logging

import nbxmpp

from gajim.common import app
from gajim.common import helpers
from gajim.common.nec import NetworkEvent

log = logging.getLogger('gajim.c.m.metacontacts')


class MetaContacts:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self.available = False

        self.handlers = []

    def get_metacontacts(self):
        log.info('Request')
        node = nbxmpp.Node('storage', attrs={'xmlns': 'storage:metacontacts'})
        iq = nbxmpp.Iq('get', nbxmpp.NS_PRIVATE, payload=node)

        self._con.connection.SendAndCallForResponse(
            iq, self._metacontacts_received)

    def _metacontacts_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Request error: %s', stanza.getError())
        else:
            self.available = True
            meta_list = self._parse_metacontacts(stanza)

            log.info('Received: %s', meta_list)

            app.nec.push_incoming_event(NetworkEvent(
                'metacontacts-received', conn=self._con, meta_list=meta_list))

        self._con.connect_machine()

    @staticmethod
    def _parse_metacontacts(stanza):
        meta_list = {}
        query = stanza.getQuery()
        storage = query.getTag('storage')
        metas = storage.getTags('meta')
        for meta in metas:
            try:
                jid = helpers.parse_jid(meta.getAttr('jid'))
            except helpers.InvalidFormat:
                continue
            tag = meta.getAttr('tag')
            data = {'jid': jid}
            order = meta.getAttr('order')
            try:
                order = int(order)
            except Exception:
                order = 0
            if order is not None:
                data['order'] = order
            if tag in meta_list:
                meta_list[tag].append(data)
            else:
                meta_list[tag] = [data]
        return meta_list

    def store_metacontacts(self, tags_list):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVATE)
        meta = iq.getQuery().addChild('storage',
                                      namespace='storage:metacontacts')
        for tag in tags_list:
            for data in tags_list[tag]:
                jid = data['jid']
                dict_ = {'jid': jid, 'tag': tag}
                if 'order' in data:
                    dict_['order'] = data['order']
                meta.addChild(name='meta', attrs=dict_)
        log.info('Store: %s', tags_list)
        self._con.connection.SendAndCallForResponse(
            iq, self._store_response_received)

    def _store_response_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Store error: %s', stanza.getError())


def get_instance(*args, **kwargs):
    return MetaContacts(*args, **kwargs), 'MetaContacts'
