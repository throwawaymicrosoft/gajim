# Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

# XEP-0060: Publish-Subscribe

import logging

import nbxmpp

from gajim.common import app
from gajim.common.modules import dataforms
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.pubsub')


class PubSub:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

        self.publish_options = False

    def pass_disco(self, from_, identities, features, data, node):
        if nbxmpp.NS_PUBSUB_PUBLISH_OPTIONS not in features:
            # Remove stored bookmarks accessible to everyone.
            self._con.get_module('Bookmarks').purge_pubsub_bookmarks()
            return
        log.info('Discovered Pubsub publish options: %s', from_)
        self.publish_options = True

    def send_pb_subscription_query(self, jid, cb, **kwargs):
        if not app.account_is_connected(self._account):
            return

        query = nbxmpp.Iq('get', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('subscriptions')

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_subscribe(self, jid, node, cb, **kwargs):
        if not app.account_is_connected(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('subscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_unsubscribe(self, jid, node, cb, **kwargs):
        if not app.account_is_connected(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_publish(self, jid, node, item,
                        id_=None, options=None, cb=None, **kwargs):
        if not app.account_is_connected(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        e = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        p = e.addChild('publish', {'node': node})
        attrs = {}
        if id_:
            attrs = {'id': id_}
        p.addChild('item', attrs, [item])
        if options:
            p = e.addChild('publish-options')
            p.addChild(node=options)

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    @staticmethod
    def get_pb_retrieve_iq(jid, node, item_id=None):
        """
        Get IQ to query items from a node
        """
        query = nbxmpp.Iq('get', to=jid)
        r = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        r = r.addChild('items', {'node': node})
        if item_id is not None:
            r.addChild('item', {'id': item_id})
        return query

    def send_pb_retrieve(self, jid, node, item_id=None, cb=None, **kwargs):
        """
        Get items from a node
        """
        if not app.account_is_connected(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = self.get_pb_retrieve_iq(jid, node, item_id)

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_retract(self, jid, node, id_, cb=None, **kwargs):
        """
        Delete item from a node
        """
        if not app.account_is_connected(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        r = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        r = r.addChild('retract', {'node': node, 'notify': '1'})
        r = r.addChild('item', {'id': id_})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_purge(self, jid, node, cb=None, **kwargs):
        """
        Purge node: Remove all items
        """
        if not app.account_is_connected(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        d = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        d = d.addChild('purge', {'node': node})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_delete(self, jid, node, on_ok=None, on_fail=None):
        """
        Delete node
        """
        if not app.account_is_connected(self._account):
            return
        query = nbxmpp.Iq('set', to=jid)
        d = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        d = d.addChild('delete', {'node': node})

        def response(con, resp, jid, node):
            if resp.getType() == 'result' and on_ok:
                on_ok(jid, node)
            elif on_fail:
                msg = resp.getErrorMsg()
                on_fail(jid, node, msg)

        self._con.connection.SendAndCallForResponse(
            query, response, {'jid': jid, 'node': node})

    def send_pb_create(self, jid, node, cb,
                       configure=False, configure_form=None):
        """
        Create a new node
        """
        if not app.account_is_connected(self._account):
            return
        query = nbxmpp.Iq('set', to=jid)
        c = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        c = c.addChild('create', {'node': node})
        if configure:
            conf = c.addChild('configure')
            if configure_form is not None:
                conf.addChild(node=configure_form)

        self._con.connection.SendAndCallForResponse(query, cb)

    def send_pb_configure(self, jid, node, form, cb=None, **kwargs):
        if not app.account_is_connected(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        c = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        c = c.addChild('configure', {'node': node})
        c.addChild(node=form)

        log.info('Send node config for %s', node)
        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def request_pb_configuration(self, jid, node):
        if not app.account_is_connected(self._account):
            return

        query = nbxmpp.Iq('get', to=jid)
        e = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        e = e.addChild('configure', {'node': node})

        log.info('Request node config for %s', node)
        self._con.connection.SendAndCallForResponse(
            query, self._received_pb_configuration, {'node': node})

    def _received_pb_configuration(self, conn, stanza, node):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Error: %s', stanza.getError())
            return

        pubsub = stanza.getTag('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        if pubsub is None:
            log.warning('Malformed PubSub configure '
                        'stanza (no pubsub node): %s', stanza)
            return

        configure = pubsub.getTag('configure')
        if configure is None:
            log.warning('Malformed PubSub configure '
                        'stanza (no configure node): %s', stanza)
            return

        if configure.getAttr('node') != node:
            log.warning('Malformed PubSub configure '
                        'stanza (wrong node): %s', stanza)
            return

        form = configure.getTag('x', namespace=nbxmpp.NS_DATA)
        if form is None:
            log.warning('Malformed PubSub configure '
                        'stanza (no form): %s', stanza)
            return

        app.nec.push_incoming_event(PubSubConfigReceivedEvent(
            None, conn=self._con, node=node,
            form=dataforms.ExtendForm(node=form)))

    def _default_callback(self, conn, stanza, *args, **kwargs):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Error: %s', stanza.getError())


class PubSubConfigReceivedEvent(NetworkIncomingEvent):
    name = 'pubsub-config-received'
    base_network_events = []


def get_instance(*args, **kwargs):
    return PubSub(*args, **kwargs), 'PubSub'
