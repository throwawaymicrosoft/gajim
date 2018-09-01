##      common/zeroconf/zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import logging
log = logging.getLogger('gajim.c.z.zeroconf_avahi')

try:
    import dbus.exceptions
except ImportError:
    pass

from gajim.common.zeroconf.zeroconf import Constant, ConstantRI
from gajim.common.zeroconf.zeroconf_avahi_const import *

class Zeroconf:
    def __init__(self, new_serviceCB, remove_serviceCB, name_conflictCB,
            disconnected_CB, error_CB, name, host, port):
        self.domain = None   # specific domain to browse
        self.stype = '_presence._tcp'
        self.port = port  # listening port that gets announced
        self.username = name
        self.host = host
        self.txt = {}           # service data

        #XXX these CBs should be set to None when we destroy the object
        # (go offline), because they create a circular reference
        self.new_serviceCB = new_serviceCB
        self.remove_serviceCB = remove_serviceCB
        self.name_conflictCB = name_conflictCB
        self.disconnected_CB = disconnected_CB
        self.error_CB = error_CB

        self.service_browser = None
        self.domain_browser = None
        self.bus = None
        self.server = None
        self.contacts = {}    # all current local contacts with data
        self.entrygroup = None
        self.connected = False
        self.announced = False
        self.invalid_self_contact = {}


    ## handlers for dbus callbacks
    def entrygroup_commit_error_CB(self, err):
        # left blank for possible later usage
        pass

    def error_callback1(self, err):
        log.debug('Error while resolving: ' + str(err))

    def error_callback(self, err):
        log.debug(str(err))
        # timeouts are non-critical
        if str(err) != 'Timeout reached':
            self.disconnect()
            self.disconnected_CB()

    def new_service_callback(self, interface, protocol, name, stype, domain,
    flags):
        log.debug('Found service %s in domain %s on %i.%i.' % (name, domain,
                interface, protocol))
        if not self.connected:
            return

        # synchronous resolving
        self.server.ResolveService( int(interface), int(protocol), name, stype,
                domain, Protocol.UNSPEC, dbus.UInt32(0),
                reply_handler=self.service_resolved_callback,
                error_handler=self.error_callback1)

    def remove_service_callback(self, interface, protocol, name, stype, domain,
    flags):
        log.debug('Service %s in domain %s on %i.%i disappeared.' % (name,
                domain, interface, protocol))
        if not self.connected:
            return
        if name != self.name:
            for key in self.contacts.keys():
                val = self.contacts[key]
                if val[Constant.BARE_NAME] == name:
                    # try to reduce instead of delete first
                    resolved_info = val[Constant.RESOLVED_INFO]
                    if len(resolved_info) > 1:
                        for i in range(len(resolved_info)):
                            if resolved_info[i][ConstantRI.INTERFACE] == interface and resolved_info[i][ConstantRI.PROTOCOL] == protocol:
                                del self.contacts[key][Constant.RESOLVED_INFO][i]
                        # if still something left, don't remove
                        if len(self.contacts[key][Constant.RESOLVED_INFO]) > 1: return
                    del self.contacts[key]
                    self.remove_serviceCB(key)
                    return

    def new_service_type(self, interface, protocol, stype, domain, flags):
        # Are we already browsing this domain for this type?
        if self.service_browser:
            return

        object_path = self.server.ServiceBrowserNew(interface, protocol, \
                        stype, domain, dbus.UInt32(0))

        self.service_browser = dbus.Interface(self.bus.get_object(
                DBUS_NAME, object_path),
                DBUS_INTERFACE_SERVICE_BROWSER)
        self.service_browser.connect_to_signal('ItemNew',
                self.new_service_callback)
        self.service_browser.connect_to_signal('ItemRemove',
                self.remove_service_callback)
        self.service_browser.connect_to_signal('Failure', self.error_callback)

    def new_domain_callback(self, interface, protocol, domain, flags):
        if domain != 'local':
            self.browse_domain(interface, protocol, domain)

    def txt_array_to_dict(self, txt_array):
        txt_dict = {}
        for array in txt_array:
            item = bytes(array)
            item = item.decode('utf-8')
            item = item.split('=', 1)

            if item[0] and (item[0] not in txt_dict):
                if len(item) == 1:
                    txt_dict[item[0]] = None
                else:
                    txt_dict[item[0]] = item[1]

        return txt_dict

    @staticmethod
    def string_to_byte_array(s):
        r = []

        for c in s:
            r.append(dbus.Byte(c))

        return r

    def dict_to_txt_array(self, txt_dict):
        array = []

        for k, v in txt_dict.items():
            item = '%s=%s' % (k, v)
            item = item.encode('utf-8')
            array.append(self.string_to_byte_array(item))

        return array

    def service_resolved_callback(self, interface, protocol, name, stype, domain,
    host, aprotocol, address, port, txt, flags):
        log.debug('Service data for service %s in domain %s on %i.%i:'
                % (name, domain, interface, protocol))
        log.debug('Host %s (%s), port %i, TXT data: %s' % (host, address,
                port, self.txt_array_to_dict(txt)))
        if not self.connected:
            return
        bare_name = name
        if name.find('@') == -1:
            name = name + '@' + name

        # we don't want to see ourselves in the list
        if name != self.name:
            resolved_info = [(interface, protocol, host, aprotocol, address, int(port))]
            if name in self.contacts:
                # Decide whether to try to merge with existing resolved info:
                old_name, old_domain, old_resolved_info, old_bare_name, old_txt = self.contacts[name]
                if name == old_name and domain == old_domain and bare_name == old_bare_name:
                    # Seems similar enough, try to merge resolved info:
                    for i in range(len(old_resolved_info)):
                        # for now, keep a single record for each (interface, protocol) pair
                        #
                        # Note that, theoretically, we could both get IPv4 and
                        # IPv6 aprotocol responses via the same protocol,
                        # so this probably needs to be revised again.
                        if old_resolved_info[i][0:2] == (interface, protocol):
                            log.debug('Deleting resolved info for interface %i, protocol %i, host %s, aprotocol %i, address %s, port %i' % old_resolved_info[i])
                            del old_resolved_info[i]
                            break
                    resolved_info = resolved_info + old_resolved_info
                    log.debug('Collected resolved info is now: %s' % (resolved_info,))
            self.contacts[name] = (name, domain, resolved_info, bare_name, txt)
            self.new_serviceCB(name)
        else:
            # remember data
            # In case this is not our own record but of another
            # gajim instance on the same machine,
            # it will be used when we get a new name.
            self.invalid_self_contact[name] = (name, domain,
                    (interface, protocol, host, aprotocol, address, int(port)),
                    bare_name, txt)


    # different handler when resolving all contacts
    def service_resolved_all_callback(self, interface, protocol, name, stype,
    domain, host, aprotocol, address, port, txt, flags):
        if not self.connected:
            return
        bare_name = name
        if name.find('@') == -1:
            name = name + '@' + name
        # update TXT data only, as intended according to resolve_all comment
        old_contact = self.contacts[name]
        self.contacts[name] = old_contact[0:Constant.TXT] + (txt,) + old_contact[Constant.TXT+1:]

    def service_added_callback(self):
        log.debug('Service successfully added')

    def service_committed_callback(self):
        log.debug('Service successfully committed')

    def service_updated_callback(self):
        log.debug('Service successfully updated')

    def service_add_fail_callback(self, err):
        log.debug('Error while adding service. %s' % str(err))
        if 'Local name collision' in str(err):
            alternative_name = self.server.GetAlternativeServiceName(self.username)
            self.name_conflictCB(alternative_name)
            return
        self.error_CB(_('Error while adding service. %s') % str(err))
        self.disconnect()

    def server_state_changed_callback(self, state, error):
        log.debug('server state changed to %s' % state)
        if state == ServerState.RUNNING:
            self.create_service()
        elif state in (ServerState.COLLISION,
                       ServerState.REGISTERING):
            self.disconnect()
            self.entrygroup.Reset()

    def entrygroup_state_changed_callback(self, state, error):
        # the name is already present, so recreate
        if state == EntryGroup.COLLISION:
            log.debug('zeroconf.py: local name collision')
            self.service_add_fail_callback('Local name collision')
        elif state == EntryGroup.FAILURE:
            self.disconnect()
            self.entrygroup.Reset()
            log.debug('zeroconf.py: ENTRY_GROUP_FAILURE reached(that'
                    ' should not happen)')

    # make zeroconf-valid names
    def replace_show(self, show):
        if show in ['chat', 'online', '']:
            return 'avail'
        elif show == 'xa':
            return 'away'
        return show

    def avahi_txt(self):
        return self.dict_to_txt_array(self.txt)

    def create_service(self):
        try:
            if not self.entrygroup:
                # create an EntryGroup for publishing
                self.entrygroup = dbus.Interface(self.bus.get_object(
                        DBUS_NAME, self.server.EntryGroupNew()),
                        DBUS_INTERFACE_ENTRY_GROUP)
                self.entrygroup.connect_to_signal('StateChanged',
                        self.entrygroup_state_changed_callback)

            txt = {}

            # remove empty keys
            for key, val in self.txt.items():
                if val:
                    txt[key] = val

            txt['port.p2pj'] = self.port
            txt['version'] = 1
            txt['txtvers'] = 1

            # replace gajim's show messages with compatible ones
            if 'status' in self.txt:
                txt['status'] = self.replace_show(self.txt['status'])
            else:
                txt['status'] = 'avail'

            self.txt = txt
            log.debug('Publishing service %s of type %s' % (self.name,
                    self.stype))
            self.entrygroup.AddService(Interface.UNSPEC,
                    Protocol.UNSPEC, dbus.UInt32(0), self.name, self.stype, '',
                    '', dbus.UInt16(self.port), self.avahi_txt(),
                    reply_handler=self.service_added_callback,
                    error_handler=self.service_add_fail_callback)

            self.entrygroup.Commit(reply_handler=self.service_committed_callback,
                    error_handler=self.entrygroup_commit_error_CB)

            return True

        except dbus.DBusException as e:
            log.debug(str(e))
            return False

    def announce(self):
        if not self.connected:
            return False

        state = self.server.GetState()
        if state == ServerState.RUNNING:
            if self.create_service():
                self.announced = True
                return True
            return False

    def remove_announce(self):
        if self.announced == False:
            return False
        try:
            if self.entrygroup.GetState() != EntryGroup.FAILURE:
                self.entrygroup.Reset()
                self.entrygroup.Free()
                # .Free() has mem leaks
                self.entrygroup._obj._bus = None
                self.entrygroup._obj = None
                self.entrygroup = None
                self.announced = False

                return True
            else:
                return False
        except dbus.DBusException:
            log.debug("Can't remove service. That should not happen")

    def browse_domain(self, interface, protocol, domain):
        self.new_service_type(interface, protocol, self.stype, domain, '')

    def avahi_dbus_connect_cb(self, a, connect, disconnect):
        if connect != "":
            log.debug('Lost connection to avahi-daemon')
            self.disconnect()
            if self.disconnected_CB:
                self.disconnected_CB()
        else:
            log.debug('We are connected to avahi-daemon')

    # connect to dbus
    def connect_dbus(self):
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            main_loop = DBusGMainLoop(set_as_default=True)
            dbus.set_default_main_loop(main_loop)
        except ImportError:
            log.debug('Error: python-dbus needs to be installed. No '
                    'zeroconf support.')
            return False
        if self.bus:
            return True
        try:
            self.bus = dbus.SystemBus()
            self.bus.add_signal_receiver(self.avahi_dbus_connect_cb,
                    'NameOwnerChanged', 'org.freedesktop.DBus',
                    arg0='org.freedesktop.Avahi')
        except Exception as e:
            # System bus is not present
            self.bus = None
            log.debug(str(e))
            return False
        else:
            return True

    # connect to avahi
    def connect_avahi(self):
        if not self.connect_dbus():
            return False

        if self.server:
            return True
        try:
            self.server = dbus.Interface(self.bus.get_object(DBUS_NAME,
                    DBUS_PATH_SERVER), DBUS_INTERFACE_SERVER)
            self.server.connect_to_signal('StateChanged',
                    self.server_state_changed_callback)
        except Exception as e:
            # Avahi service is not present
            self.server = None
            log.debug(str(e))
            return False
        else:
            return True

    def connect(self):
        self.name = self.username + '@' + self.host # service name
        if not self.connect_avahi():
            return False

        self.connected = True
        # start browsing
        if self.domain is None:
            # Explicitly browse .local
            self.browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, 'local')

            # Browse for other browsable domains
            self.domain_browser = dbus.Interface(self.bus.get_object(
                    DBUS_NAME, self.server.DomainBrowserNew(
                    Interface.UNSPEC, Protocol.UNSPEC, '',
                    DomainBrowser.BROWSE, dbus.UInt32(0))),
                    DBUS_INTERFACE_DOMAIN_BROWSER)
            self.domain_browser.connect_to_signal('ItemNew',
                    self.new_domain_callback)
            self.domain_browser.connect_to_signal('Failure', self.error_callback)
        else:
            self.browse_domain(
                Interface.UNSPEC, Protocol.UNSPEC, self.domain)

        return True

    def disconnect(self):
        if self.connected:
            self.connected = False
            if self.service_browser:
                try:
                    self.service_browser.Free()
                except dbus.DBusException as e:
                    log.debug(str(e))
                self.service_browser._obj._bus = None
                self.service_browser._obj = None
            if self.domain_browser:
                try:
                    self.domain_browser.Free()
                except dbus.DBusException as e:
                    log.debug(str(e))
                self.domain_browser._obj._bus = None
                self.domain_browser._obj = None
            self.remove_announce()
            self.server._obj._bus = None
            self.server._obj = None
        self.server = None
        self.service_browser = None
        self.domain_browser = None

    # refresh txt data of all contacts manually (no callback available)
    def resolve_all(self):
        if not self.connected:
            return False
        for val in self.contacts.values():
            # get txt data from last recorded resolved info
            # TODO: Better try to get it from last IPv6 mDNS, then last IPv4?
            ri = val[Constant.RESOLVED_INFO][0]
            self.server.ResolveService(int(ri[ConstantRI.INTERFACE]), int(ri[ConstantRI.PROTOCOL]),
                    val[Constant.BARE_NAME], self.stype, val[Constant.DOMAIN],
                    Protocol.UNSPEC, dbus.UInt32(0),
                    reply_handler=self.service_resolved_all_callback,
                    error_handler=self.error_callback)

        return True

    def get_contacts(self):
        return self.contacts

    def get_contact(self, jid):
        if not jid in self.contacts:
            return None
        return self.contacts[jid]

    def update_txt(self, show = None):
        if show:
            self.txt['status'] = self.replace_show(show)

        txt = self.avahi_txt()
        if self.connected and self.entrygroup:
            self.entrygroup.UpdateServiceTxt(Interface.UNSPEC,
                    Protocol.UNSPEC, dbus.UInt32(0), self.name, self.stype, '',
                    txt, reply_handler=self.service_updated_callback,
                    error_handler=self.error_callback)
            return True
        else:
            return False


# END Zeroconf