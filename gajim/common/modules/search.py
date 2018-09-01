# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0055: Jabber Search

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.search')


class Search:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

    def request_search_fields(self, jid):
        log.info('Request search fields from %s', jid)
        iq = nbxmpp.Iq(typ='get', to=jid, queryNS=nbxmpp.NS_SEARCH)
        self._con.connection.SendAndCallForResponse(iq, self._fields_received)

    def _fields_received(self, stanza):
        data = None
        is_dataform = False

        if nbxmpp.isResultNode(stanza):
            log.info('Received search fields from %s', stanza.getFrom())
            tag = stanza.getTag('query', namespace=nbxmpp.NS_SEARCH)
            if tag is None:
                log.info('Invalid stanza: %s', stanza)
                return

            data = tag.getTag('x', namespace=nbxmpp.NS_DATA)
            if data is not None:
                is_dataform = True
            else:
                data = {}
                for i in stanza.getQueryPayload():
                    data[i.getName()] = i.getData()
        else:
            log.info('Error: %s', stanza.getError())

        app.nec.push_incoming_event(
            SearchFormReceivedEvent(None, conn=self._con,
                                    is_dataform=is_dataform,
                                    data=data))

    def send_search_form(self, jid, form, is_form):
        iq = nbxmpp.Iq(typ='set', to=jid, queryNS=nbxmpp.NS_SEARCH)
        item = iq.setQuery()
        if is_form:
            item.addChild(node=form)
        else:
            for i in form.keys():
                item.setTagData(i, form[i])

        self._con.connection.SendAndCallForResponse(iq, self._received_result)

    def _received_result(self, stanza):
        data = None
        is_dataform = False

        if nbxmpp.isResultNode(stanza):
            log.info('Received result from %s', stanza.getFrom())
            tag = stanza.getTag('query', namespace=nbxmpp.NS_SEARCH)
            if tag is None:
                log.info('Invalid stanza: %s', stanza)
                return

            data = tag.getTag('x', namespace=nbxmpp.NS_DATA)
            if data is not None:
                is_dataform = True
            else:
                data = []
                for item in tag.getTags('item'):
                    # We also show attributes. jid is there
                    f = item.attrs
                    for i in item.getPayload():
                        f[i.getName()] = i.getData()
                    data.append(f)
        else:
            log.info('Error: %s', stanza.getError())

        app.nec.push_incoming_event(
            SearchResultReceivedEvent(None, conn=self._con,
                                      is_dataform=is_dataform,
                                      data=data))


class SearchFormReceivedEvent(NetworkIncomingEvent):
    name = 'search-form-received'
    base_network_events = []


class SearchResultReceivedEvent(NetworkIncomingEvent):
    name = 'search-result-received'
    base_network_events = []


def get_instance(*args, **kwargs):
    return Search(*args, **kwargs), 'Search'
