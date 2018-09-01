#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

'''
Testing PluginManager class.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 05/30/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys
import os
import unittest

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(gajim_root + '/gajim')

# a temporary version of ~/.gajim for testing
configdir = gajim_root + '/test/tmp'

import time

# define _ for i18n
import builtins
builtins._ = lambda x: x

# wipe config directory
import os
if os.path.isdir(configdir):
    import shutil
    shutil.rmtree(configdir)

os.mkdir(configdir)

from gajim.common import configpaths
configpaths.set_config_root(configdir)
configpaths.init()

# for some reason common.app needs to be imported before xmpppy?

configpaths.override_path('DATA', gajim_root + '/gajim/data')

# name to use for the test account
account_name = 'test'

from plugins import PluginManager

class PluginManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.pluginmanager = PluginManager()

    def tearDown(self):
        pass

    def test_01_Singleton(self):
        """ 1. Checking whether PluginManger class is singleton. """
        self.pluginmanager.test_arg = 1
        secondPluginManager = PluginManager()

        self.assertEqual(id(secondPluginManager), id(self.pluginmanager),
                         'Different IDs in references to PluginManager objects (not a singleton)')
        self.assertEqual(secondPluginManager.test_arg, 1,
                         'References point to different PluginManager objects (not a singleton')

def suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(PluginManagerTestCase)
    return suite

if __name__=='__main__':
    runner = unittest.TextTestRunner()
    test_suite = suite()
    runner.run(test_suite)
