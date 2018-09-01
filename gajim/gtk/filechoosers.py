# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
from pathlib import Path
from collections import namedtuple

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GObject

from gajim.common import app

Filter = namedtuple('Filter', 'name pattern default')


def _require_native():
    if app.is_flatpak():
        return True
    if sys.platform in ('win32', 'darwin'):
        return True
    return False


# Notes: Adding mime types to Gtk.FileFilter forces non-native dialogs

class BaseFileChooser:
    def _on_response(self, dialog, response, accept_cb, cancel_cb):
        if response == Gtk.ResponseType.ACCEPT:
            if self.get_select_multiple():
                accept_cb(dialog.get_filenames())
            else:
                accept_cb(dialog.get_filename())

        if response in (Gtk.ResponseType.CANCEL,
                        Gtk.ResponseType.DELETE_EVENT):
            if cancel_cb is not None:
                cancel_cb()

    def _add_filters(self, filters):
        for filterinfo in filters:
            filter_ = Gtk.FileFilter()
            filter_.set_name(filterinfo.name)
            if isinstance(filterinfo.pattern, list):
                for mime_type in filterinfo.pattern:
                    filter_.add_mime_type(mime_type)
            else:
                filter_.add_pattern(filterinfo.pattern)
            self.add_filter(filter_)
            if filterinfo.default:
                self.set_filter(filter_)

    def _update_preview(self, filechooser):
        path_to_file = filechooser.get_preview_filename()
        preview = filechooser.get_preview_widget()
        if path_to_file is None or os.path.isdir(path_to_file):
            # nothing to preview
            preview.clear()
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                path_to_file, *self._preivew_size)
        except GObject.GError:
            preview.clear()
            return
        filechooser.get_preview_widget().set_from_pixbuf(pixbuf)


class BaseFileOpenDialog:

    _title = _('Choose File to Send…')
    _filters = [Filter(_('All files'), '*', True)]


class BaseAvatarChooserDialog:

    _title = _('Choose Avatar…')
    _preivew_size = (100, 100)

    if _require_native():
        _filters = [Filter(_('PNG files'), '*.png', True),
                    Filter(_('JPEG files'), '*.jp*g', False),
                    Filter(_('SVG files'), '*.svg', False)]
    else:
        _filters = [Filter(_('Images'), ['image/png',
                                         'image/jpeg',
                                         'image/svg+xml'], True)]


class NativeFileChooserDialog(Gtk.FileChooserNative, BaseFileChooser):

    _title = ''
    _filters = []
    _action = Gtk.FileChooserAction.OPEN

    def __init__(self, accept_cb, cancel_cb=None, transient_for=None,
                 path=None, file_name=None, select_multiple=False,
                 modal=False):

        Gtk.FileChooserNative.__init__(self,
                                       title=self._title,
                                       action=self._action,
                                       transient_for=transient_for)

        self.set_current_folder(path or str(Path.home()))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_do_overwrite_confirmation(True)
        self.set_modal(modal)
        self._add_filters(self._filters)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()


class ArchiveChooserDialog(NativeFileChooserDialog):

    _title = _('Choose Archive')
    _filters = [Filter(_('All files'), '*', False),
                Filter(_('ZIP files'), '*.zip', True)]


class FileSaveDialog(NativeFileChooserDialog):

    _title = _('Save File as…')
    _filters = [Filter(_('All files'), '*', True)]
    _action = Gtk.FileChooserAction.SAVE


class AvatarSaveDialog(FileSaveDialog):

    if sys.platform == 'win32':
        _filters = [Filter(_('Images'), '*.png;*.jpg;*.jpeg;*.svg', True)]


class NativeFileOpenDialog(BaseFileOpenDialog, NativeFileChooserDialog):
    pass


class NativeAvatarChooserDialog(BaseAvatarChooserDialog, NativeFileChooserDialog):
    pass


class GtkFileChooserDialog(Gtk.FileChooserDialog, BaseFileChooser):

    _title = ''
    _filters = []
    _action = Gtk.FileChooserAction.OPEN
    _preivew_size = (200, 200)

    def __init__(self, accept_cb, cancel_cb=None, transient_for=None,
                 path=None, file_name=None, select_multiple=False,
                 preview=True, modal=False):

        Gtk.FileChooserDialog.__init__(
            self,
            title=self._title,
            action=self._action,
            buttons=[Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                     Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT],
            transient_for=transient_for)

        self.set_current_folder(path or str(Path.home()))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_do_overwrite_confirmation(True)
        self.set_modal(modal)
        self._add_filters(self._filters)

        if preview:
            self.set_use_preview_label(False)
            self.set_preview_widget(Gtk.Image())
            self.connect('selection-changed', self._update_preview)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()

    def _on_response(self, *args):
        super()._on_response(*args)
        self.destroy()


class GtkFileOpenDialog(BaseFileOpenDialog, GtkFileChooserDialog):
    pass


class GtkAvatarChooserDialog(BaseAvatarChooserDialog, GtkFileChooserDialog):
    pass


def FileChooserDialog(*args, **kwargs):
    if _require_native():
        return NativeFileOpenDialog(*args, **kwargs)
    else:
        return GtkFileOpenDialog(*args, **kwargs)


def AvatarChooserDialog(*args, **kwargs):
    if _require_native():
        return NativeAvatarChooserDialog(*args, **kwargs)
    else:
        return GtkAvatarChooserDialog(*args, **kwargs)
