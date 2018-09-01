# -*- coding:utf-8 -*-
## gajim/common/app.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
## Copyright (C) 2018 Philipp Hörist <philipp @ hoerist.com>
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

import os
import sys
import logging
import uuid
from distutils.version import LooseVersion as V
from collections import namedtuple

import nbxmpp

import gajim
from gajim.common import config as c_config
from gajim.common import configpaths
from gajim.common import ged as ged_module
from gajim.common.contacts import LegacyContactsAPI
from gajim.common.events import Events
from gajim.common.css_config import CSSConfig

interface = None # The actual interface (the gtk one for the moment)
thread_interface = lambda *args: None # Interface to run a thread and then a callback
config = c_config.Config()
version = gajim.__version__
connections = {} # 'account name': 'account (connection.Connection) instance'
avatar_cache = {}
ipython_window = None
app = None  # Gtk.Application

ged = ged_module.GlobalEventsDispatcher() # Global Events Dispatcher
nec = None # Network Events Controller
plugin_manager = None # Plugins Manager

logger = None

# For backwards compatibility needed
# some plugins use that
gajimpaths = configpaths.gajimpaths


RecentGroupchat = namedtuple('RecentGroupchat', ['room', 'server', 'nickname'])

css_config = None

os_info = None # used to cache os information

transport_type = {} # list the type of transport

last_message_time = {} # list of time of the latest incoming message
                       # {acct1: {jid1: time1, jid2: time2}, }
encrypted_chats = {}   # list of encrypted chats {acct1: [jid1, jid2], ..}

contacts = LegacyContactsAPI()
gc_connected = {}    # tell if we are connected to the room or not
                     # {acct: {room_jid: True}}
gc_passwords = {}    # list of the pass required to enter a room
                     # {room_jid: password}
automatic_rooms = {} # list of rooms that must be automaticaly configured
                     # and for which we have a list of invities
                     #{account: {room_jid: {'invities': []}}}
new_room_nick = None # if it's != None, use this nick instead of asking for
                     # a new nickname when there is a conflict.

groups = {} # list of groups
newly_added = {} # list of contacts that has just signed in
to_be_removed = {} # list of contacts that has just signed out

events = Events()

notification = None

nicks = {} # list of our nick names in each account
# should we block 'contact signed in' notifications for this account?
# this is only for the first 30 seconds after we change our show
# to something else than offline
# can also contain account/transport_jid to block notifications for contacts
# from this transport
block_signed_in_notifications = {}
con_types = {} # type of each connection (ssl, tls, tcp, ...)

sleeper_state = {} # whether we pass auto away / xa or not
#'off': don't use sleeper for this account
#'online': online and use sleeper
#'autoaway': autoaway and use sleeper
#'autoxa': autoxa and use sleeper
status_before_autoaway = {}

# jid of transport contacts for which we need to ask avatar when transport will
# be online
transport_avatar = {} # {transport_jid: [jid_list]}

# Is Gnome configured to activate on single click ?
single_click = False
SHOW_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
        'invisible', 'error']

# zeroconf account name
ZEROCONF_ACC_NAME = 'Local'

# These will be set in app.gui_interface.
idlequeue = None
socks5queue = None

gajim_identity = {'type': 'pc', 'category': 'client', 'name': 'Gajim'}
gajim_common_features = [nbxmpp.NS_BYTESTREAM, nbxmpp.NS_SI, nbxmpp.NS_FILE,
    nbxmpp.NS_MUC, nbxmpp.NS_MUC_USER, nbxmpp.NS_MUC_ADMIN, nbxmpp.NS_MUC_OWNER,
    nbxmpp.NS_MUC_CONFIG, nbxmpp.NS_COMMANDS, nbxmpp.NS_DISCO_INFO, 'ipv6',
    'jabber:iq:gateway', nbxmpp.NS_LAST, nbxmpp.NS_PRIVACY, nbxmpp.NS_PRIVATE,
    nbxmpp.NS_REGISTER, nbxmpp.NS_VERSION, nbxmpp.NS_DATA, nbxmpp.NS_ENCRYPTED,
    'msglog', 'sslc2s', 'stringprep', nbxmpp.NS_PING, nbxmpp.NS_TIME_REVISED,
    nbxmpp.NS_SSN, nbxmpp.NS_MOOD, nbxmpp.NS_ACTIVITY, nbxmpp.NS_NICK,
    nbxmpp.NS_ROSTERX, nbxmpp.NS_SECLABEL, nbxmpp.NS_HASHES_2,
    nbxmpp.NS_HASHES_MD5, nbxmpp.NS_HASHES_SHA1, nbxmpp.NS_HASHES_SHA256,
    nbxmpp.NS_HASHES_SHA512, nbxmpp.NS_CONFERENCE, nbxmpp.NS_CORRECT,
    nbxmpp.NS_EME, 'urn:xmpp:avatar:metadata+notify']

# Optional features gajim supports per account
gajim_optional_features = {}

# Capabilities hash per account
caps_hash = {}

_dependencies = {
    'PYTHON-DBUS': False,
    'PYBONJOUR': False,
    'PYGPG': False,
    'GPG_BINARY': False,
    'FARSTREAM': False,
    'GEOCLUE': False,
    'UPNP': False,
    'PYCURL': False,
    'GSPELL': False,
    'IDLE': False,
}


def is_installed(dependency):
    if dependency == 'GPG':
        # Alias for checking python-gnupg and the GPG binary
        return _dependencies['PYGPG'] and _dependencies['GPG_BINARY']
    if dependency == 'ZEROCONF':
        # Alias for checking zeroconf libs
        return _dependencies['PYTHON-DBUS'] or _dependencies['PYBONJOUR']
    return _dependencies[dependency]

def is_flatpak():
    return gajim.IS_FLATPAK

def disable_dependency(dependency):
    _dependencies[dependency] = False

def detect_dependencies():
    import gi

    # ZEROCONF
    try:
        if os.name == 'nt':
            import pybonjour
            _dependencies['PYBONJOUR'] = True
        else:
            import dbus
            _dependencies['PYTHON-DBUS'] = True
    except Exception:
        pass

    # python-gnupg
    try:
        import gnupg
        '''
        We need https://pypi.python.org/pypi/python-gnupg
        but https://pypi.python.org/pypi/gnupg shares the same package name.
        It cannot be used as a drop-in replacement.
        We test with a version check if python-gnupg is installed as it is
        on a much lower version number than gnupg
        Also we need at least python-gnupg 0.3.8
        '''
        v_gnupg = gnupg.__version__
        if V(v_gnupg) < V('0.3.8') or V(v_gnupg) > V('1.0.0'):
            log('gajim').info('Gajim needs python-gnupg >= 0.3.8')
            raise ImportError
        _dependencies['PYGPG'] = True
    except ImportError:
        pass

    # GPG BINARY
    import subprocess

    def test_gpg(binary='gpg'):
        if os.name == 'nt':
            gpg_cmd = binary + ' -h >nul 2>&1'
        else:
            gpg_cmd = binary + ' -h >/dev/null 2>&1'
        if subprocess.call(gpg_cmd, shell=True):
            return False
        return True

    if test_gpg(binary='gpg2'):
        _dependencies['GPG_BINARY'] = 'gpg2'
    elif test_gpg(binary='gpg'):
        _dependencies['GPG_BINARY'] = 'gpg'

    # FARSTREAM
    try:
        if os.name == 'nt':
            os.environ['FS_PLUGIN_PATH'] = 'gtk\\lib\\farstream-0.1'
            os.environ['GST_PLUGIN_PATH'] = 'gtk\\lib\\gstreamer-0.10'
        gi.require_version('Farstream', '0.2')
        from gi.repository import Farstream
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        try:
            Gst.init(None)
            conference = Gst.ElementFactory.make('fsrtpconference', None)
            session = conference.new_session(Farstream.MediaType.AUDIO)
        except Exception as error:
            log('gajim').info(error)
        _dependencies['FARSTREAM'] = True
    except (ImportError, ValueError):
        pass

    # GEOCLUE
    try:
        gi.require_version('Geoclue', '2.0')
        from gi.repository import Geoclue
        _dependencies['GEOCLUE'] = True
    except (ImportError, ValueError):
        pass

    # UPNP
    try:
        gi.require_version('GUPnPIgd', '1.0')
        from gi.repository import GUPnPIgd
        gupnp_igd = GUPnPIgd.SimpleIgd()
        _dependencies['UPNP'] = True
    except ValueError:
        pass

    # PYCURL
    try:
        import pycurl
        _dependencies['PYCURL'] = True
    except ImportError:
        pass

    # IDLE
    try:
        from gajim.common import idle
        if idle.Monitor.is_available():
            _dependencies['IDLE'] = True
    except Exception:
        pass

    # GSPELL
    try:
        gi.require_version('Gspell', '1')
        from gi.repository import Gspell
        langs = Gspell.language_get_available()
        for lang in langs:
            log('gajim').info('%s (%s) dict available',
                              lang.get_name(), lang.get_code())
        if langs:
            _dependencies['GSPELL'] = True
    except (ImportError, ValueError):
        pass

    # Print results
    for dep, val in _dependencies.items():
        log('gajim').info('%-13s %s', dep, val)

def get_gpg_binary():
    return _dependencies['GPG_BINARY']

def get_an_id():
    return str(uuid.uuid4())

def get_nick_from_jid(jid):
    pos = jid.find('@')
    return jid[:pos]

def get_server_from_jid(jid):
    pos = jid.find('@') + 1 # after @
    return jid[pos:]

def get_name_and_server_from_jid(jid):
    name = get_nick_from_jid(jid)
    server = get_server_from_jid(jid)
    return name, server

def get_room_and_nick_from_fjid(jid):
    # fake jid is the jid for a contact in a room
    # gaim@conference.jabber.no/nick/nick-continued
    # return ('gaim@conference.jabber.no', 'nick/nick-continued')
    l = jid.split('/', 1)
    if len(l) == 1: # No nick
        l.append('')
    return l

def get_real_jid_from_fjid(account, fjid):
    """
    Return real jid or returns None, if we don't know the real jid
    """
    room_jid, nick = get_room_and_nick_from_fjid(fjid)
    if not nick: # It's not a fake_jid, it is a real jid
        return fjid # we return the real jid
    real_jid = fjid
    if interface.msg_win_mgr.get_gc_control(room_jid, account):
        # It's a pm, so if we have real jid it's in contact.jid
        gc_contact = contacts.get_gc_contact(account, room_jid, nick)
        if not gc_contact:
            return
        # gc_contact.jid is None when it's not a real jid (we don't know real jid)
        real_jid = gc_contact.jid
    return real_jid

def get_room_from_fjid(jid):
    return get_room_and_nick_from_fjid(jid)[0]

def get_contact_name_from_jid(account, jid):
    c = contacts.get_first_contact_from_jid(account, jid)
    return c.name

def get_jid_without_resource(jid):
    return jid.split('/')[0]

def construct_fjid(room_jid, nick):
    # fake jid is the jid for a contact in a room
    # gaim@conference.jabber.org/nick
    return room_jid + '/' + nick

def get_resource_from_jid(jid):
    jids = jid.split('/', 1)
    if len(jids) > 1:
        return jids[1] # abc@doremi.org/res/res-continued
    else:
        return ''

def get_number_of_accounts():
    """
    Return the number of ALL accounts
    """
    return len(connections.keys())

def get_number_of_connected_accounts(accounts_list = None):
    """
    Returns the number of CONNECTED accounts. Uou can optionally pass an
    accounts_list and if you do those will be checked, else all will be checked
    """
    connected_accounts = 0
    if accounts_list is None:
        accounts = connections.keys()
    else:
        accounts = accounts_list
    for account in accounts:
        if account_is_connected(account):
            connected_accounts = connected_accounts + 1
    return connected_accounts

def get_connected_accounts():
    """
    Returns a list of CONNECTED accounts
    """
    account_list = []
    for account in connections:
        if account_is_connected(account):
            account_list.append(account)
    return account_list

def get_enabled_accounts_with_labels(exclude_local=True, connected_only=False,
                                     private_storage_only=False):
    """
    Returns a list with [account, account_label] entries.
    Order by account_label
    """
    accounts = []
    for acc in connections:
        if exclude_local and account_is_zeroconf(acc):
            continue
        if connected_only and not account_is_connected(acc):
            continue
        if private_storage_only and not account_supports_private_storage(acc):
            continue

        acc_label = config.get_per(
            'accounts', acc, 'account_label') or acc
        accounts.append([acc, acc_label])

    accounts.sort(key=lambda xs: str.lower(xs[1]))
    return accounts

def account_is_zeroconf(account):
    return connections[account].is_zeroconf

def account_supports_private_storage(account):
    # If Delimiter module is not available we can assume
    # Private Storage is not available
    return connections[account].get_module('Delimiter').available

def account_is_connected(account):
    if account not in connections:
        return False
    if connections[account].connected > 1: # 0 is offline, 1 is connecting
        return True
    else:
        return False

def is_invisible(account):
    return SHOW_LIST[connections[account].connected] == 'invisible'

def account_is_disconnected(account):
    return not account_is_connected(account)

def zeroconf_is_connected():
    return account_is_connected(ZEROCONF_ACC_NAME) and \
            config.get_per('accounts', ZEROCONF_ACC_NAME, 'is_zeroconf')

def in_groupchat(account, room_jid):
    if room_jid not in gc_connected[account]:
        return False
    return gc_connected[account][room_jid]

def get_number_of_securely_connected_accounts():
    """
    Return the number of the accounts that are SSL/TLS connected
    """
    num_of_secured = 0
    for account in connections.keys():
        if account_is_securely_connected(account):
            num_of_secured += 1
    return num_of_secured

def account_is_securely_connected(account):
    if account_is_connected(account) and \
    account in con_types and con_types[account] in ('tls', 'ssl'):
        return True
    else:
        return False

def get_transport_name_from_jid(jid, use_config_setting = True):
    """
    Returns 'gg', 'irc' etc

    If JID is not from transport returns None.
    """
    #FIXME: jid can be None! one TB I saw had this problem:
    # in the code block # it is a groupchat presence in handle_event_notify
    # jid was None. Yann why?
    if not jid or (use_config_setting and not config.get('use_transports_iconsets')):
        return

    host = get_server_from_jid(jid)
    if host in transport_type:
        return transport_type[host]

    # host is now f.e. icq.foo.org or just icq (sometimes on hacky transports)
    host_splitted = host.split('.')
    if len(host_splitted) != 0:
        # now we support both 'icq.' and 'icq' but not icqsucks.org
        host = host_splitted[0]

    if host in ('irc', 'icq', 'sms', 'weather', 'mrim', 'facebook'):
        return host
    elif host == 'gg':
        return 'gadu-gadu'
    elif host == 'jit':
        return 'icq'
    elif host == 'facebook':
        return 'facebook'
    else:
        return None

def jid_is_transport(jid):
    # if not '@' or '@' starts the jid then it is transport
    if jid.find('@') <= 0:
        return True
    return False

def get_jid_from_account(account_name):
    """
    Return the jid we use in the given account
    """
    name = config.get_per('accounts', account_name, 'name')
    hostname = config.get_per('accounts', account_name, 'hostname')
    jid = name + '@' + hostname
    return jid

def get_account_from_jid(jid):
    for account in config.get_per('accounts'):
        if jid == get_jid_from_account(account):
            return account

def get_our_jids():
    """
    Returns a list of the jids we use in our accounts
    """
    our_jids = list()
    for account in contacts.get_accounts():
        our_jids.append(get_jid_from_account(account))
    return our_jids

def get_hostname_from_account(account_name, use_srv = False):
    """
    Returns hostname (if custom hostname is used, that is returned)
    """
    if use_srv and connections[account_name].connected_hostname:
        return connections[account_name].connected_hostname
    if config.get_per('accounts', account_name, 'use_custom_host'):
        return config.get_per('accounts', account_name, 'custom_host')
    return config.get_per('accounts', account_name, 'hostname')

def get_notification_image_prefix(jid):
    """
    Returns the prefix for the notification images
    """
    transport_name = get_transport_name_from_jid(jid)
    if transport_name in ('icq', 'facebook'):
        prefix = transport_name
    else:
        prefix = 'jabber'
    return prefix

def get_name_from_jid(account, jid):
    """
    Return from JID's shown name and if no contact returns jids
    """
    contact = contacts.get_first_contact_from_jid(account, jid)
    if contact:
        actor = contact.get_shown_name()
    else:
        actor = jid
    return actor

def get_muc_domain(account):
    return connections[account].muc_jid.get('jabber', None)

def get_recent_groupchats(account):
    recent_groupchats = config.get_per(
        'accounts', account, 'recent_groupchats').split()

    recent_list = []
    for groupchat in recent_groupchats:
        jid = nbxmpp.JID(groupchat)
        recent = RecentGroupchat(
            jid.getNode(), jid.getDomain(), jid.getResource())
        recent_list.append(recent)
    return recent_list

def add_recent_groupchat(account, room_jid, nickname):
    recent = config.get_per(
        'accounts', account, 'recent_groupchats').split()
    full_jid = room_jid + '/' + nickname
    if full_jid in recent:
        recent.remove(full_jid)
    recent.insert(0, full_jid)
    if len(recent) > 10:
        recent = recent[0:9]
    config_value = ' '.join(recent)
    config.set_per(
        'accounts', account, 'recent_groupchats', config_value)

def get_priority(account, show):
    """
    Return the priority an account must have
    """
    if not show:
        show = 'online'

    if show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible') and \
    config.get_per('accounts', account, 'adjust_priority_with_status'):
        prio = config.get_per('accounts', account, 'autopriority_' + show)
    else:
        prio = config.get_per('accounts', account, 'priority')
    if prio < -128:
        prio = -128
    elif prio > 127:
        prio = 127
    return prio

def log(domain):
    if domain != 'gajim':
        domain = 'gajim.%s' % domain
    return logging.getLogger(domain)

def prefers_app_menu():
    if sys.platform == 'darwin':
        return True
    if sys.platform == 'win32':
        return False
    return app.prefers_app_menu()

def get_app_window(cls, account=None):
    for win in app.get_windows():
        if isinstance(cls, str):
            if type(win).__name__ == cls:
                if account is not None:
                    if account != win.account:
                        continue
                return win
        elif isinstance(win, cls):
            if account is not None:
                if account != win.account:
                    continue
            return win
    return None

def load_css_config():
    global css_config
    css_config = CSSConfig()
