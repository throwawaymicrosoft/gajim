# -*- coding: utf-8 -*-
## src/common/location_listener.py
##
## Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
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

from datetime import datetime
import logging

from gajim.common import app

import gi
gi.require_version('Geoclue', '2.0')
from gi.repository import Geoclue
from gi.repository import GLib

log = logging.getLogger('gajim.c.location_listener')


class LocationListener:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._data = {}

    # Note: do not remove third parameter `paramSpec`
    #       because notify signal expects three parameters
    def _on_location_update(self, simple, paramSpec=None):
        location = simple.get_location()
        timestamp = location.get_property("timestamp")[0]
        lat = location.get_property("latitude")
        lon = location.get_property("longitude")
        alt = location.get_property("altitude")
        # in XEP-0080 it's horizontal accuracy
        acc = location.get_property("accuracy")

        # update data with info we just received
        self._data = {'lat': lat, 'lon': lon, 'alt': alt, 'accuracy': acc}
        self._data['timestamp'] = self._timestamp_to_utc(timestamp)
        self._send_location()

    def _on_simple_ready(self, obj, result):
        try:
            self.simple = Geoclue.Simple.new_finish(result)
        except GLib.Error as e:
            if e.domain == 'g-dbus-error-quark':
                log.warning("Could not enable geolocation: %s", e.message)
            else:
                raise
        else:
            self.simple.connect('notify::location', self._on_location_update)
            self._on_location_update(self.simple)

    def get_data(self):
        Geoclue.Simple.new("org.gajim.Gajim",
                           Geoclue.AccuracyLevel.EXACT,
                           None,
                           self._on_simple_ready)

    def start(self):
        self.location_info = {}
        self.get_data()

    def _send_location(self):
        accounts = app.connections.keys()
        for acct in accounts:
            if not app.account_is_connected(acct):
                continue
            if not app.config.get_per('accounts', acct, 'publish_location'):
                continue
            if self.location_info == self._data:
                continue
            if 'timestamp' in self.location_info and 'timestamp' in self._data:
                last_data = self.location_info.copy()
                del last_data['timestamp']
                new_data = self._data.copy()
                del new_data['timestamp']
                if last_data == new_data:
                    continue
            app.connections[acct].get_module('UserLocation').send(self._data)
            self.location_info = self._data.copy()

    def _timestamp_to_utc(self, timestamp):
        time = datetime.utcfromtimestamp(timestamp)
        return time.strftime('%Y-%m-%dT%H:%MZ')


def enable():
    listener = LocationListener.get()
    listener.start()
