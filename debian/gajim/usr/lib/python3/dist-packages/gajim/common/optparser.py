# -*- coding:utf-8 -*-
## gajim/common/optparser.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Brendan Taylor <whateley AT gmail.com>
##                    Tomasz Melcer <liori AT exroot.org>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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
import re
import logging

from gajim.common import app
from gajim.common import caps_cache


log = logging.getLogger('gajim.c.optparser')


class OptionsParser:
    def __init__(self, filename):
        self.__filename = os.path.realpath(filename)
        self.old_values = {}    # values that are saved in the file and maybe
                                                        # no longer valid

    def read(self):
        try:
            fd = open(self.__filename, encoding='utf-8')
        except Exception:
            if os.path.exists(self.__filename):
                #we talk about a file
                print(_('Error: cannot open %s for reading') % self.__filename,
                    file=sys.stderr)
            return False

        new_version = app.config.get('version')
        new_version = new_version.split('+', 1)[0]
        seen = set()
        regex = re.compile(r"(?P<optname>[^.=]+)(?:(?:\.(?P<key>.+))?\.(?P<subname>[^.=]+))?\s=\s(?P<value>.*)")

        for line in fd:
            match = regex.match(line)
            if match is None:
                log.warn('Invalid configuration line, ignoring it: %s', line)
                continue
            optname, key, subname, value = match.groups()
            if key is None:
                self.old_values[optname] = value
                app.config.set(optname, value)
            else:
                if (optname, key) not in seen:
                    if optname in self.old_values:
                        self.old_values[optname][key] = {}
                    else:
                        self.old_values[optname] = {key: {}}
                    app.config.add_per(optname, key)
                    seen.add((optname, key))
                self.old_values[optname][key][subname] = value
                app.config.set_per(optname, key, subname, value)

        old_version = app.config.get('version')
        if '+' in old_version:
            old_version = old_version.split('+', 1)[0]
        elif '-' in old_version:
            old_version = old_version.split('-', 1)[0]

        self.update_config(old_version, new_version)
        self.old_values = {} # clean mem

        fd.close()
        return True

    def write_line(self, fd, opt, parents, value):
        if value is None:
            return
        # convert to utf8 before writing to file if needed
        value = str(value)
        s = ''
        if parents:
            if len(parents) == 1:
                return
            for p in parents:
                s += p + '.'
        s += opt
        fd.write(s + ' = ' + value + '\n')

    def write(self):
        (base_dir, filename) = os.path.split(self.__filename)
        self.__tempfile = os.path.join(base_dir, '.' + filename)
        try:
            with open(self.__tempfile, 'w', encoding='utf-8') as f:
                app.config.foreach(self.write_line, f)
        except IOError as e:
            return str(e)

        if os.path.exists(self.__filename):
            if os.name == 'nt':
                # win32 needs this
                try:
                    os.remove(self.__filename)
                except Exception as e:
                    return str(e)
        try:
            os.rename(self.__tempfile, self.__filename)
        except IOError as e:
            return str(e)

    def update_config(self, old_version, new_version):
        old_version_list = old_version.split('.') # convert '0.x.y' to (0, x, y)
        old = []
        while len(old_version_list):
            old.append(int(old_version_list.pop(0)))
        new_version_list = new_version.split('.')
        new = []
        while len(new_version_list):
            new.append(int(new_version_list.pop(0)))

        if old < [0, 14, 0, 1] and new >= [0, 14, 0, 1]:
            self.update_config_to_01401()
        if old < [0, 14, 90, 0] and new >= [0, 14, 90, 0]:
            self.update_config_to_014900()
        if old < [0, 16, 0, 1] and new >= [0, 16, 0, 1]:
            self.update_config_to_01601()
        if old < [0, 16, 4, 1] and new >= [0, 16, 4, 1]:
            self.update_config_to_01641()
        if old < [0, 16, 10, 1] and new >= [0, 16, 10, 1]:
            self.update_config_to_016101()
        if old < [0, 16, 10, 2] and new >= [0, 16, 10, 2]:
            self.update_config_to_016102()
        if old < [0, 16, 10, 4] and new >= [0, 16, 10, 4]:
            self.update_config_to_016104()
        if old < [0, 16, 10, 5] and new >= [0, 16, 10, 5]:
            self.update_config_to_016105()
        if old < [0, 98, 3] and new >= [0, 98, 3]:
            self.update_config_to_0983()

        app.config.set('version', new_version)

        caps_cache.capscache.initialize_from_db()

    @staticmethod
    def update_ft_proxies(to_remove=None, to_add=None):
        if to_remove is None:
            to_remove = []
        if to_add is None:
            to_add = []
        for account in app.config.get_per('accounts'):
            proxies_str = app.config.get_per('accounts', account,
                    'file_transfer_proxies')
            proxies = [p.strip() for p in proxies_str.split(',')]
            for wrong_proxy in to_remove:
                if wrong_proxy in proxies:
                    proxies.remove(wrong_proxy)
            for new_proxy in to_add:
                if new_proxy not in proxies:
                    proxies.append(new_proxy)
            proxies_str = ', '.join(proxies)
            app.config.set_per('accounts', account, 'file_transfer_proxies',
                    proxies_str)

    def update_config_to_01401(self):
        if 'autodetect_browser_mailer' not in self.old_values or 'openwith' \
        not in self.old_values or \
        (self.old_values['autodetect_browser_mailer'] == False and \
        self.old_values['openwith'] != 'custom'):
            app.config.set('autodetect_browser_mailer', True)
            app.config.set('openwith', app.config.DEFAULT_OPENWITH)
        app.config.set('version', '0.14.0.1')

    def update_config_to_014900(self):
        if 'use_stun_server' in self.old_values and self.old_values[
        'use_stun_server'] and not self.old_values['stun_server']:
            app.config.set('use_stun_server', False)
        if os.name == 'nt':
            app.config.set('autodetect_browser_mailer', True)

    def update_config_to_01601(self):
        if 'last_mam_id' in self.old_values:
            last_mam_id = self.old_values['last_mam_id']
            for account in app.config.get_per('accounts'):
                app.config.set_per('accounts', account, 'last_mam_id',
                    last_mam_id)
        app.config.set('version', '0.16.0.1')

    def update_config_to_01641(self):
        for account in self.old_values['accounts'].keys():
            connection_types = self.old_values['accounts'][account][
            'connection_types'].split()
            if 'plain' in connection_types and len(connection_types) > 1:
                connection_types.remove('plain')
            app.config.set_per('accounts', account, 'connection_types',
                ' '.join(connection_types))
        app.config.set('version', '0.16.4.1')

    def update_config_to_016101(self):
        if 'video_input_device' in self.old_values:
            if self.old_values['video_input_device'] == 'autovideosrc ! videoscale ! ffmpegcolorspace':
                app.config.set('video_input_device', 'autovideosrc')
            if self.old_values['video_input_device'] == 'videotestsrc is-live=true ! video/x-raw-yuv,framerate=10/1':
                app.config.set('video_input_device', 'videotestsrc is-live=true ! video/x-raw,framerate=10/1')
        app.config.set('version', '0.16.10.1')

    def update_config_to_016102(self):
        for account in self.old_values['accounts'].keys():
            app.config.del_per('accounts', account, 'minimized_gc')

        app.config.set('version', '0.16.10.2')

    def update_config_to_016104(self):
        app.config.set('emoticons_theme', 'noto-emoticons')
        app.config.set('version', '0.16.10.4')

    def update_config_to_016105(self):
        app.config.set('muc_restore_timeout', -1)
        app.config.set('restore_timeout', -1)
        app.config.set('version', '0.16.10.5')

    def update_config_to_0983(self):
        for account in self.old_values['accounts'].keys():
            password = self.old_values['accounts'][account]['password']
            if password == "winvault:":
                app.config.set_per('accounts', account, 'password', 'keyring:')
            elif password == "libsecret:":
                app.config.set_per('accounts', account, 'password', '')
        app.config.set('version', '0.98.3')
