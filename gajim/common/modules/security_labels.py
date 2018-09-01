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

# XEP-0258: Security Labels in XMPP

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.security_labels')


class SecLabels:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

        self._catalogs = {}
        self.supported = False

    def pass_disco(self, from_, identities, features, data, node):
        if nbxmpp.NS_SECLABEL not in features:
            return

        self.supported = True
        log.info('Discovered security labels: %s', from_)

    def request_catalog(self, jid):
        server = app.get_jid_from_account(self._account).split("@")[1]
        iq = nbxmpp.Iq(typ='get', to=server)
        iq.addChild(name='catalog',
                    namespace=nbxmpp.NS_SECLABEL_CATALOG,
                    attrs={'to': jid})
        log.info('Request catalog: server: %s, to: %s', server, jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._catalog_received)

    def _catalog_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return

        query = stanza.getTag('catalog', namespace=nbxmpp.NS_SECLABEL_CATALOG)
        to = query.getAttr('to')
        items = query.getTags('item')

        labels = {}
        label_list = []
        default = None
        for item in items:
            label = item.getAttr('selector')
            labels[label] = item.getTag('securitylabel')
            label_list.append(label)
            if item.getAttr('default') == 'true':
                default = label

        catalog = (labels, label_list, default)
        self._catalogs[to] = catalog

        app.nec.push_incoming_event(SecLabelCatalog(
            None, account=self._account, jid=to, catalog=catalog))

    def get_catalog(self, jid):
        return self._catalogs.get(jid)


def parse_securitylabel(stanza):
    seclabel = stanza.getTag('securitylabel', namespace=nbxmpp.NS_SECLABEL)
    if seclabel is None:
        return None
    return seclabel.getTag('displaymarking')


class SecLabelCatalog(NetworkIncomingEvent):
    name = 'sec-catalog-received'


def get_instance(*args, **kwargs):
    return SecLabels(*args, **kwargs), 'SecLabels'
