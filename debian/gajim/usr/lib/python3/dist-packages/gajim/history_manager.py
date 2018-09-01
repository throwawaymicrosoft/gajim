# -*- coding:utf-8 -*-
## src/history_manager.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

## NOTE: some method names may match those of logger.py but that's it
## someday (TM) should have common class
## that abstracts db connections and helpers on it
## the same can be said for history.py

import os
import sys
import time
import getopt
import sqlite3
from enum import IntEnum, unique

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio

from gajim.common import i18n
from gajim.common import configpaths
from gajim.common.const import StyleAttr

def is_standalone():
    # Determine if we are in standalone mode
    if Gio.Application.get_default() is None:
        return True
    if __name__ == '__main__':
        return True
    return False


if is_standalone():
    try:
        shortargs = 'hvsc:l:p:'
        longargs = 'help verbose separate config-path= loglevel= profile='
        opts = getopt.getopt(sys.argv[1:], shortargs, longargs.split())[0]
    except getopt.error as msg:
        print(str(msg))
        print('for help use --help')
        sys.exit(2)
    for o, a in opts:
        if o in ('-h', '--help'):
            print(_('Usage:') + \
                '\n  gajim-history-manager [options] filename\n\n' + \
                _('Options:') + \
                '\n  -h, --help         ' + \
                    _('Show this help message and exit') + \
                '\n  -c, --config-path  ' + _('Choose folder for logfile') + '\n')
            sys.exit()
        elif o in ('-c', '--config-path'):
            configpaths.set_config_root(a)

    configpaths.init()

from gajim.common import app
from gajim.common.const import JIDConstant, KindConstant
from gajim.common import helpers
from gajim.gtk import YesNoDialog
from gajim.gtk import ErrorDialog
from gajim.gtk import ConfirmationDialog
from gajim.gtk.filechoosers import FileSaveDialog
from gajim import gtkgui_helpers


@unique
class Column(IntEnum):
    UNIXTIME = 2
    MESSAGE = 3
    SUBJECT = 4
    NICKNAME = 5


class HistoryManager:
    def __init__(self):
        pixs = []
        for size in (16, 32, 48, 64, 128):
            pix = gtkgui_helpers.get_icon_pixmap('org.gajim.Gajim', size)
            if pix:
                pixs.append(pix)
        if pixs:
            # set the icon to all windows
            Gtk.Window.set_default_icon_list(pixs)

        log_db_path = configpaths.get('LOG_DB')
        if not os.path.exists(log_db_path):
            ErrorDialog(_('Cannot find history logs database'),
                        '%s does not exist.' % log_db_path)
            sys.exit()

        xml = gtkgui_helpers.get_gtk_builder('history_manager.ui')
        self.window = xml.get_object('history_manager_window')
        self.jids_listview = xml.get_object('jids_listview')
        self.logs_listview = xml.get_object('logs_listview')
        self.search_results_listview = xml.get_object('search_results_listview')
        self.search_entry = xml.get_object('search_entry')
        self.logs_scrolledwindow = xml.get_object('logs_scrolledwindow')
        self.search_results_scrolledwindow = xml.get_object(
                'search_results_scrolledwindow')
        self.welcome_vbox = xml.get_object('welcome_vbox')

        self.jids_already_in = []  # holds jids that we already have in DB
        self.AT_LEAST_ONE_DELETION_DONE = False

        self.con = sqlite3.connect(
            log_db_path, timeout=20.0, isolation_level='IMMEDIATE')
        self.con.execute("PRAGMA secure_delete=1")
        self.cur = self.con.cursor()

        self._init_jids_listview()
        self._init_logs_listview()
        self._init_search_results_listview()

        self._fill_jids_listview()

        self.search_entry.grab_focus()

        self.window.show_all()

        xml.connect_signals(self)

    def _init_jids_listview(self):
        self.jids_liststore = Gtk.ListStore(str, str)  # jid, jid_id
        self.jids_listview.set_model(self.jids_liststore)
        self.jids_listview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        renderer_text = Gtk.CellRendererText()  # holds jid
        col = Gtk.TreeViewColumn(_('JID'), renderer_text, text=0)
        self.jids_listview.append_column(col)

        self.jids_listview.get_selection().connect('changed',
                self.on_jids_listview_selection_changed)

    def _init_logs_listview(self):
        # log_line_id(HIDDEN), jid_id(HIDDEN), time, message, subject, nickname
        self.logs_liststore = Gtk.ListStore(str, str, str, str, str, str)
        self.logs_listview.set_model(self.logs_liststore)
        self.logs_listview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        renderer_text = Gtk.CellRendererText()  # holds time
        col = Gtk.TreeViewColumn(_('Date'), renderer_text, text=Column.UNIXTIME)
        # user can click this header and sort
        col.set_sort_column_id(Column.UNIXTIME)
        col.set_resizable(True)
        self.logs_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds nickname
        col = Gtk.TreeViewColumn(_('Nickname'), renderer_text, text=Column.NICKNAME)
        # user can click this header and sort
        col.set_sort_column_id(Column.NICKNAME)
        col.set_resizable(True)
        col.set_visible(False)
        self.nickname_col_for_logs = col
        self.logs_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds message
        col = Gtk.TreeViewColumn(_('Message'), renderer_text, markup=Column.MESSAGE)
        # user can click this header and sort
        col.set_sort_column_id(Column.MESSAGE)
        col.set_resizable(True)
        self.message_col_for_logs = col
        self.logs_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds subject
        col = Gtk.TreeViewColumn(_('Subject'), renderer_text, text=Column.SUBJECT)
        col.set_sort_column_id(Column.SUBJECT)  # user can click this header and sort
        col.set_resizable(True)
        col.set_visible(False)
        self.subject_col_for_logs = col
        self.logs_listview.append_column(col)

    def _init_search_results_listview(self):
        # log_line_id (HIDDEN), jid, time, message, subject, nickname
        self.search_results_liststore = Gtk.ListStore(int, str, str, str, str,
            str)
        self.search_results_listview.set_model(self.search_results_liststore)

        renderer_text = Gtk.CellRendererText()  # holds JID (who said this)
        col = Gtk.TreeViewColumn(_('JID'), renderer_text, text=1)
        col.set_sort_column_id(1)  # user can click this header and sort
        col.set_resizable(True)
        self.search_results_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds time
        col = Gtk.TreeViewColumn(_('Date'), renderer_text, text=Column.UNIXTIME)
        # user can click this header and sort
        col.set_sort_column_id(Column.UNIXTIME)
        col.set_resizable(True)
        self.search_results_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds message
        col = Gtk.TreeViewColumn(_('Message'), renderer_text, text=Column.MESSAGE)
        col.set_sort_column_id(Column.MESSAGE)  # user can click this header and sort
        col.set_resizable(True)
        self.search_results_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds subject
        col = Gtk.TreeViewColumn(_('Subject'), renderer_text, text=Column.SUBJECT)
        col.set_sort_column_id(Column.SUBJECT)  # user can click this header and sort
        col.set_resizable(True)
        self.search_results_listview.append_column(col)

        renderer_text = Gtk.CellRendererText()  # holds nickname
        col = Gtk.TreeViewColumn(_('Nickname'), renderer_text, text=Column.NICKNAME)
        # user can click this header and sort
        col.set_sort_column_id(Column.NICKNAME)
        col.set_resizable(True)
        self.search_results_listview.append_column(col)

    def on_history_manager_window_delete_event(self, widget, event):
        if not self.AT_LEAST_ONE_DELETION_DONE:
            if is_standalone():
                Gtk.main_quit()
            return

        def on_yes(clicked):
            self.cur.execute('VACUUM')
            self.con.commit()
            if is_standalone():
                Gtk.main_quit()

        def on_no():
            if is_standalone():
                Gtk.main_quit()

        dialog = YesNoDialog(
            _('Do you want to clean up the database? '
            '(STRONGLY NOT RECOMMENDED IF GAJIM IS RUNNING)'),
            _('Normally allocated database size will not be freed, '
                'it will just become reusable. If you really want to reduce '
                'database filesize, click YES, else click NO.'
                '\n\nIn case you click YES, please wait…'),
            on_response_yes=on_yes, on_response_no=on_no)
        dialog.set_title(_('Database Cleanup'))
        button_box = dialog.get_children()[0].get_children()[1]
        button_box.get_children()[0].grab_focus()

    def _fill_jids_listview(self):
        # get those jids that have at least one entry in logs
        self.cur.execute('SELECT jid, jid_id FROM jids WHERE jid_id IN ('
                'SELECT distinct logs.jid_id FROM logs) ORDER BY jid')
        # list of tuples: [('aaa@bbb',), ('cc@dd',)]
        rows = self.cur.fetchall()
        for row in rows:
            self.jids_already_in.append(row[0])  # jid
            self.jids_liststore.append([row[0], str(row[1])])  # jid, jid_id

    def on_jids_listview_selection_changed(self, widget, data=None):
        liststore, list_of_paths = self.jids_listview.get_selection()\
                .get_selected_rows()

        self.logs_liststore.clear()
        if not list_of_paths:
            return

        self.welcome_vbox.hide()
        self.search_results_scrolledwindow.hide()
        self.logs_scrolledwindow.show()

        list_of_rowrefs = []
        for path in list_of_paths:  # make them treerowrefs (it's needed)
            list_of_rowrefs.append(Gtk.TreeRowReference.new(liststore, path))

        for rowref in list_of_rowrefs:  # FILL THE STORE, for all rows selected
            path = rowref.get_path()
            if path is None:
                continue
            jid = liststore[path][0]  # jid
            self._fill_logs_listview(jid)

    def _get_jid_id(self, jid):
        """
        jids table has jid and jid_id
        logs table has log_id, jid_id, contact_name, time, kind, show, message

        So to ask logs we need jid_id that matches our jid in jids table this
        method wants jid and returns the jid_id for later sql-ing on logs
        """
        if jid.find('/') != -1:  # if it has a /
            jid_is_from_pm = self._jid_is_from_pm(jid)
            if not jid_is_from_pm:  # it's normal jid with resource
                jid = jid.split('/', 1)[0]  # remove the resource
        self.cur.execute('SELECT jid_id FROM jids WHERE jid = ?', (jid,))
        jid_id = self.cur.fetchone()[0]
        return str(jid_id)

    def _get_jid_from_jid_id(self, jid_id):
        """
        jids table has jid and jid_id

        This method accepts jid_id and returns the jid for later sql-ing on logs
        """
        self.cur.execute('SELECT jid FROM jids WHERE jid_id = ?', (jid_id,))
        jid = self.cur.fetchone()[0]
        return jid

    def _jid_is_from_pm(self, jid):
        """
        If jid is gajim@conf/nkour it's likely a pm one, how we know gajim@conf
        is not a normal guy and nkour is not his resource? We ask if gajim@conf
        is already in jids (with type room jid). This fails if user disables
        logging for room and only enables for pm (so higly unlikely) and if we
        fail we do not go chaos (user will see the first pm as if it was message
        in room's public chat) and after that everything is ok
        """
        possible_room_jid = jid.split('/', 1)[0]

        self.cur.execute('SELECT jid_id FROM jids WHERE jid = ? AND type = ?',
                (possible_room_jid, JIDConstant.ROOM_TYPE))
        row = self.cur.fetchone()
        if row is None:
            return False
        else:
            return True

    def _jid_is_room_type(self, jid):
        """
        Return True/False if given id is room type or not eg. if it is room
        """
        self.cur.execute('SELECT type FROM jids WHERE jid = ?', (jid,))
        row = self.cur.fetchone()
        if row is None:
            raise
        elif row[0] == JIDConstant.ROOM_TYPE:
            return True
        else:  # normal type
            return False

    def _fill_logs_listview(self, jid):
        """
        Fill the listview with all messages that user sent to or received from
        JID
        """
        # no need to lower jid in this context as jid is already lowered
        # as we use those jids from db
        jid_id = self._get_jid_id(jid)
        self.cur.execute('''
                SELECT log_line_id, jid_id, time, kind, message, subject, contact_name, show
                FROM logs
                WHERE jid_id = ?
                ORDER BY time
                ''', (jid_id,))

        results = self.cur.fetchall()

        if self._jid_is_room_type(jid):  # is it room?
            self.nickname_col_for_logs.set_visible(True)
            self.subject_col_for_logs.set_visible(False)
        else:
            self.nickname_col_for_logs.set_visible(False)
            self.subject_col_for_logs.set_visible(True)

        for row in results:
            # exposed in UI (TreeViewColumns) are only
            # time, message, subject, nickname
            # but store in liststore
            # log_line_id, jid_id, time, message, subject, nickname
            log_line_id, jid_id, time_, kind, message, subject, nickname, \
                show = row
            try:
                time_ = time.strftime('%x', time.localtime(float(time_)))
            except ValueError:
                pass
            else:
                color = None
                if kind in (KindConstant.SINGLE_MSG_RECV,
                KindConstant.CHAT_MSG_RECV, KindConstant.GC_MSG):
                    # it is the other side
                    color = app.css_config.get_value('.gajim-incoming-nickname', StyleAttr.COLOR)  # so incoming color
                elif kind in (KindConstant.SINGLE_MSG_SENT,
                KindConstant.CHAT_MSG_SENT):  # it is us
                    color = app.css_config.get_value('.gajim-outgoing-nickname', StyleAttr.COLOR)  # so outgoing color
                elif kind in (KindConstant.STATUS,
                KindConstant.GCSTATUS):  # is is statuses
                    # so status color
                    color = app.css_config.get_value('.gajim-status-message', StyleAttr.COLOR)
                    # include status into (status) message
                    if message is None:
                        message = ''
                    else:
                        message = ' : ' + message
                    message = helpers.get_uf_show(app.SHOW_LIST[show]) + \
                        message

                message_ = '<span'
                if color:
                    message_ += ' foreground="%s"' % color
                message_ += '>%s</span>' % GLib.markup_escape_text(message)
                self.logs_liststore.append((str(log_line_id), str(jid_id),
                    time_, message_, subject, nickname))

    def _fill_search_results_listview(self, text):
        """
        Ask db and fill listview with results that match text
        """
        self.search_results_liststore.clear()
        like_sql = '%' + text + '%'
        self.cur.execute('''
                SELECT log_line_id, jid_id, time, message, subject, contact_name
                FROM logs
                WHERE message LIKE ? OR subject LIKE ?
                ORDER BY time
                ''', (like_sql, like_sql))

        results = self.cur.fetchall()
        for row in results:
            # exposed in UI (TreeViewColumns) are only
            # JID, time, message, subject, nickname
            # but store in liststore
            # log_line_id, jid (from jid_id), time, message, subject, nickname
            log_line_id, jid_id, time_, message, subject, nickname = row
            try:
                time_ = time.strftime('%x', time.localtime(float(time_)))
            except ValueError:
                pass
            else:
                jid = self._get_jid_from_jid_id(jid_id)

                self.search_results_liststore.append((log_line_id, jid, time_,
                        message, subject, nickname))

    def on_logs_listview_key_press_event(self, widget, event):
        liststore, list_of_paths = self.logs_listview.get_selection()\
                .get_selected_rows()
        if event.keyval == Gdk.KEY_Delete:
            self._delete_logs(liststore, list_of_paths)

    def on_listview_button_press_event(self, widget, event):
        if event.button == 3:  # right click
            xml = gtkgui_helpers.get_gtk_builder('history_manager.ui',
                'context_menu')
            if Gtk.Buildable.get_name(widget) != 'jids_listview':
                xml.get_object('export_menuitem').hide()
            xml.get_object('delete_menuitem').connect('activate',
                    self.on_delete_menuitem_activate, widget)

            xml.connect_signals(self)
            xml.get_object('context_menu').popup(None, None, None, None,
                    event.button, event.time)
            return True

    def on_export_menuitem_activate(self, widget):
        FileSaveDialog(self._on_export,
                       transient_for=self.window,
                       modal=True)

    def _on_export(self, filename):
        liststore, list_of_paths = self.jids_listview.get_selection()\
                .get_selected_rows()
        self._export_jids_logs_to_file(liststore, list_of_paths, filename)

    def on_delete_menuitem_activate(self, widget, listview):
        widget_name = Gtk.Buildable.get_name(listview)
        liststore, list_of_paths = listview.get_selection().get_selected_rows()
        if widget_name == 'jids_listview':
            self._delete_jid_logs(liststore, list_of_paths)
        elif widget_name in ('logs_listview', 'search_results_listview'):
            self._delete_logs(liststore, list_of_paths)
        else:  # Huh ? We don't know this widget
            return

    def on_jids_listview_key_press_event(self, widget, event):
        liststore, list_of_paths = self.jids_listview.get_selection()\
                .get_selected_rows()
        if event.keyval == Gdk.KEY_Delete:
            self._delete_jid_logs(liststore, list_of_paths)

    def _export_jids_logs_to_file(self, liststore, list_of_paths, path_to_file):
        paths_len = len(list_of_paths)
        if paths_len == 0:  # nothing is selected
            return

        list_of_rowrefs = []
        for path in list_of_paths:  # make them treerowrefs (it's needed)
            list_of_rowrefs.append(Gtk.TreeRowReference.new(liststore, path))

        for rowref in list_of_rowrefs:
            path = rowref.get_path()
            if path is None:
                continue
            jid_id = liststore[path][1]
            self.cur.execute('''
                    SELECT time, kind, message, contact_name FROM logs
                    WHERE jid_id = ?
                    ORDER BY time
                    ''', (jid_id,))

        # FIXME: we may have two contacts selected to export. fix that
        # AT THIS TIME FIRST EXECUTE IS LOST! WTH!!!!!
        results = self.cur.fetchall()
        #print results[0]
        file_ = open(path_to_file, 'w', encoding='utf-8')
        for row in results:
            # in store: time, kind, message, contact_name FROM logs
            # in text: JID or You or nickname (if it's gc_msg), time, message
            time_, kind, message, nickname = row
            if kind in (KindConstant.SINGLE_MSG_RECV,
                    KindConstant.CHAT_MSG_RECV):
                who = self._get_jid_from_jid_id(jid_id)
            elif kind in (KindConstant.SINGLE_MSG_SENT,
                    KindConstant.CHAT_MSG_SENT):
                who = _('You')
            elif kind == KindConstant.GC_MSG:
                who = nickname
            else:  # status or gc_status. do not save
                #print kind
                continue

            try:
                time_ = time.strftime('%c', time.localtime(float(time_)))
            except ValueError:
                pass

            file_.write(_('%(who)s on %(time)s said: %(message)s\n') % {
                'who': who, 'time': time_, 'message': message})

    def _delete_jid_logs(self, liststore, list_of_paths):
        paths_len = len(list_of_paths)
        if paths_len == 0:  # nothing is selected
            return

        def on_ok(liststore, list_of_paths):
            # delete all rows from db that match jid_id
            list_of_rowrefs = []
            for path in list_of_paths:  # make them treerowrefs (it's needed)
                list_of_rowrefs.append(Gtk.TreeRowReference.new(liststore, path))

            for rowref in list_of_rowrefs:
                path = rowref.get_path()
                if path is None:
                    continue
                jid_id = liststore[path][1]
                del liststore[path]  # remove from UI
                # remove from db
                self.cur.execute('''
                        DELETE FROM logs
                        WHERE jid_id = ?
                        ''', (jid_id,))

                # now delete "jid, jid_id" row from jids table
                self.cur.execute('''
                                DELETE FROM jids
                                WHERE jid_id = ?
                                ''', (jid_id,))

            self.con.commit()

            self.AT_LEAST_ONE_DELETION_DONE = True

        if paths_len == 1:
            jid_id = '<i>%s</i>' % liststore[list_of_paths[0]][0]
            pri_text = _('Do you wish to delete all correspondence with %(jid)s?') \
                % {'jid': jid_id}
        else:
            pri_text = _(
                'Do you wish to delete all correspondence with the selected contacts?')
        dialog = ConfirmationDialog('',
            _('This can not be undone.'), on_response_ok=(on_ok,
            liststore, list_of_paths))
        dialog.set_title(_('Deletion Confirmation'))
        dialog.set_markup(pri_text)
        ok_button = dialog.get_children()[0].get_children()[1].get_children()[0]
        ok_button.grab_focus()
        dialog.set_transient_for(self.window)

    def _delete_logs(self, liststore, list_of_paths):
        paths_len = len(list_of_paths)
        if paths_len == 0:  # nothing is selected
            return

        def on_ok(liststore, list_of_paths):
            # delete rows from db that match log_line_id
            list_of_rowrefs = []
            for path in list_of_paths:  # make them treerowrefs (it's needed)
                list_of_rowrefs.append(Gtk.TreeRowReference.new(liststore, path))

            for rowref in list_of_rowrefs:
                path = rowref.get_path()
                if path is None:
                    continue
                log_line_id = liststore[path][0]
                del liststore[path]  # remove from UI
                # remove from db
                self.cur.execute('''
                        DELETE FROM logs
                        WHERE log_line_id = ?
                        ''', (log_line_id,))

            self.con.commit()

            self.AT_LEAST_ONE_DELETION_DONE = True

        pri_text = i18n.ngettext(
            'Do you really want to delete the selected message?',
            'Do you really want to delete the selected messages?', paths_len)
        dialog = ConfirmationDialog(pri_text,
            _('This is an irreversible operation.'), on_response_ok=(on_ok,
            liststore, list_of_paths))
        dialog.set_title(_('Deletion Confirmation'))
        ok_button = dialog.get_children()[0].get_children()[1].get_children()[0]
        ok_button.grab_focus()
        dialog.set_transient_for(self.window)

    def on_search_db_button_clicked(self, widget):
        text = self.search_entry.get_text()
        if not text:
            return

        self.welcome_vbox.hide()
        self.logs_scrolledwindow.hide()
        self.search_results_scrolledwindow.show()

        self._fill_search_results_listview(text)

    def on_search_results_listview_row_activated(self, widget, path, column):
        # get log_line_id, jid_id from row we double clicked
        log_line_id = str(self.search_results_liststore[path][0])
        jid = self.search_results_liststore[path][1]
        # make it string as in gtk liststores I have them all as strings
        # as this is what db returns so I don't have to fight with types
        jid_id = self._get_jid_id(jid)

        iter_ = self.jids_liststore.get_iter_first()
        while iter_:
            # self.jids_liststore[iter_][1] holds jid_ids
            if self.jids_liststore[iter_][1] == jid_id:
                break
            iter_ = self.jids_liststore.iter_next(iter_)

        if iter_ is None:
            return

        path = self.jids_liststore.get_path(iter_)
        self.jids_listview.set_cursor(path)

        iter_ = self.logs_liststore.get_iter_first()
        while iter_:
            # self.logs_liststore[iter_][0] holds log_line_ids
            if self.logs_liststore[iter_][0] == log_line_id:
                break
            iter_ = self.logs_liststore.iter_next(iter_)

        path = self.logs_liststore.get_path(iter_)
        self.logs_listview.scroll_to_cell(path)
        self.logs_listview.get_selection().select_path(path)


def main():
    if sys.platform != 'win32':
        if os.geteuid() == 0:
            sys.exit("You must not launch gajim as root, it is insecure.")

    HistoryManager()
    Gtk.main()


if __name__ == '__main__':
    main()
