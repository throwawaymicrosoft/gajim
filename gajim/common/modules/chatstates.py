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

# XEP-0085: Chat State Notifications

import logging

import nbxmpp

from gajim.common.modules.misc import parse_delay

log = logging.getLogger('gajim.c.m.chatstates')


def parse_chatstate(stanza):
    if parse_delay(stanza) is not None:
        return

    children = stanza.getChildren()
    for child in children:
        if child.getNamespace() == nbxmpp.NS_CHATSTATES:
            return child.getName()
