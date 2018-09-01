# -*- coding:utf-8 -*-
## src/advanced.py
##
## Copyright (C) 2005 Travis Shirk <travis AT pobox.com>
##                    Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
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

from enum import IntEnum, unique

from gi.repository import Gtk
from gajim import gtkgui_helpers
from gi.repository import GLib
from gi.repository import Pango

from gajim.common import app

@unique
class Column(IntEnum):
    PREFERENCE_NAME = 0
    VALUE = 1
    TYPE = 2

def rate_limit(rate):
    """
    Call func at most *rate* times per second
    """
    def decorator(func):
        timeout = [None]
        def f(*args, **kwargs):
            if timeout[0] is not None:
                GLib.source_remove(timeout[0])
                timeout[0] = None
            def timeout_func():
                func(*args, **kwargs)
                timeout[0] = None
            timeout[0] = GLib.timeout_add(int(1000.0 / rate), timeout_func)
        return f
    return decorator

def tree_model_iter_children(model, treeiter):
    it = model.iter_children(treeiter)
    while it:
        yield it
        it = model.iter_next(it)

def tree_model_pre_order(model, treeiter):
    yield treeiter
    for childiter in tree_model_iter_children(model, treeiter):
        for it in tree_model_pre_order(model, childiter):
            yield it


class AdvancedConfigurationWindow(object):
    def __init__(self, transient):
        self.xml = gtkgui_helpers.get_gtk_builder('advanced_configuration_window.ui')
        self.window = self.xml.get_object('advanced_configuration_window')
        self.window.set_transient_for(transient)
        self.entry = self.xml.get_object('advanced_entry')
        self.desc_label = self.xml.get_object('advanced_desc_label')
        self.restart_box = self.xml.get_object('restart_box')
        self.reset_button = self.xml.get_object('reset_button')

        # Format:
        # key = option name (root/subopt/opt separated by \n then)
        # value = array(oldval, newval)
        self.changed_opts = {}

        # For i18n
        self.right_true_dict = {True: _('Activated'), False: _('Deactivated')}
        self.types = {
                'boolean': _('Boolean'),
                'integer': _('Integer'),
                'string': _('Text'),
                'color': _('Color')}

        treeview = self.xml.get_object('advanced_treeview')
        self.treeview = treeview
        self.model = Gtk.TreeStore(str, str, str)
        self.fill_model()
        self.model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(self.visible_func)

        renderer_text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Preference Name'), renderer_text, text = 0)
        treeview.insert_column(col, -1)
        col.set_resizable(True)

        renderer_text = Gtk.CellRendererText()
        renderer_text.connect('edited', self.on_config_edited)
        renderer_text.set_property('ellipsize', Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_('Value'),renderer_text, text = 1)
        treeview.insert_column(col, -1)
        col.set_cell_data_func(renderer_text, self.cb_value_column_data)

        col.props.resizable = True
        col.props.expand = True
        col.props.sizing = Gtk.TreeViewColumnSizing.FIXED

        renderer_text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Type'), renderer_text, text = 2)
        treeview.insert_column(col, -1)
        col.props.sizing = Gtk.TreeViewColumnSizing.FIXED

        treeview.set_model(self.modelfilter)

        # connect signal for selection change
        treeview.get_selection().connect('changed',
                self.on_advanced_treeview_selection_changed)

        self.xml.connect_signals(self)
        self.restart_box.set_no_show_all(True)
        self.window.show_all()
        app.interface.instances['advanced_config'] = self

    def cb_value_column_data(self, col, cell, model, iter_, data):
        """
        Check if it's boolean or holds password stuff and if yes  make the
        cellrenderertext not editable, else - it's editable
        """
        optname = model[iter_][Column.PREFERENCE_NAME]
        opttype = model[iter_][Column.TYPE]
        if opttype == self.types['boolean'] or optname == 'password':
            cell.set_property('editable', False)
        else:
            cell.set_property('editable', True)

    @staticmethod
    def get_option_path(model, iter_):
        # It looks like path made from reversed array
        # path[0] is the true one optname
        # path[1] is the key name
        # path[2] is the root of tree
        # last two is optional
        path = [model[iter_][0]]
        parent = model.iter_parent(iter_)
        while parent:
            path.append(model[parent][0])
            parent = model.iter_parent(parent)
        return path

    def on_advanced_treeview_selection_changed(self, treeselection):
        model, iter_ = treeselection.get_selected()
        # Check for GtkTreeIter
        if iter_:
            opt_path = self.get_option_path(model, iter_)
            # Get text from first column in this row
            desc = None
            if len(opt_path) == 3:
                desc = app.config.get_desc_per(opt_path[2], opt_path[0])
            elif len(opt_path) == 1:
                desc = app.config.get_desc(opt_path[0])
            if desc:
                self.desc_label.set_text(desc)
            else:
                #we talk about option description in advanced configuration editor
                self.desc_label.set_text(_('(None)'))
            if len(opt_path) == 3 or (len(opt_path) == 1 and not \
            model.iter_has_child(iter_)):
                self.reset_button.set_sensitive(True)
            else:
                self.reset_button.set_sensitive(False)
        else:
            self.reset_button.set_sensitive(False)

    def remember_option(self, option, oldval, newval):
        if option in self.changed_opts:
            self.changed_opts[option] = (self.changed_opts[option][0], newval)
        else:
            self.changed_opts[option] = (oldval, newval)

    def on_advanced_treeview_row_activated(self, treeview, path, column):
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        option = modelrow[0]
        if modelrow[2] == self.types['boolean']:
            for key in self.right_true_dict.keys():
                if self.right_true_dict[key] == modelrow[1]:
                    modelrow[1] = str(key)
            newval = {'False': True, 'True': False}[modelrow[1]]
            if len(modelpath.get_indices()) > 1:
                optnamerow = self.model[modelpath.get_indices()[0]]
                optname = optnamerow[0]
                modelpath.up()
                keyrow = self.model[modelpath]
                key = keyrow[0]
                self.remember_option(option + '\n' + key + '\n' + optname,
                        modelrow[1], newval)
                app.config.set_per(optname, key, option, newval)
            else:
                self.remember_option(option, modelrow[1], newval)
                app.config.set(option, newval)
            modelrow[1] = self.right_true_dict[newval]
            self.check_for_restart()

    def check_for_restart(self):
        self.restart_box.hide()
        for opt in self.changed_opts:
            opt_path = opt.split('\n')
            if len(opt_path)==3:
                restart = app.config.get_restart_per(opt_path[2], opt_path[1],
                        opt_path[0])
            else:
                restart = app.config.get_restart(opt_path[0])
            if restart:
                if self.changed_opts[opt][0] != self.changed_opts[opt][1]:
                    self.restart_box.set_no_show_all(False)
                    self.restart_box.show_all()
                    break

    def on_config_edited(self, cell, path, text):
        # convert modelfilter path to model path
        path=Gtk.TreePath.new_from_string(path)
        modelpath = self.modelfilter.convert_path_to_child_path(path)
        modelrow = self.model[modelpath]
        option = modelrow[0]
        if modelpath.get_depth() > 2:
            modelpath.up() # Get parent
            keyrow = self.model[modelpath]
            key = keyrow[0]
            modelpath.up() # Get parent
            optnamerow = self.model[modelpath]
            optname = optnamerow[0]
            self.remember_option(option + '\n' + key + '\n' + optname, modelrow[1],
                    text)
            app.config.set_per(optname, key, option, text)
        else:
            self.remember_option(option, modelrow[1], text)
            app.config.set(option, text)
        modelrow[1] = text
        self.check_for_restart()

    @staticmethod
    def on_advanced_configuration_window_destroy(widget):
        del app.interface.instances['advanced_config']

    def on_reset_button_clicked(self, widget):
        model, iter_ = self.treeview.get_selection().get_selected()
        # Check for GtkTreeIter
        if iter_:
            path = model.get_path(iter_)
            opt_path =  self.get_option_path(model, iter_)
            if len(opt_path) == 1:
                default = app.config.get_default(opt_path[0])
            elif len(opt_path) == 3:
                default = app.config.get_default_per(opt_path[2], opt_path[0])

            if model[iter_][Column.TYPE] == self.types['boolean']:
                if self.right_true_dict[default] == model[iter_][Column.VALUE]:
                    return
                modelpath = self.modelfilter.convert_path_to_child_path(path)
                modelrow = self.model[modelpath]
                option = modelrow[0]
                if len(modelpath) > 1:
                    optnamerow = self.model[modelpath[0]]
                    optname = optnamerow[0]
                    keyrow = self.model[modelpath[:2]]
                    key = keyrow[0]
                    self.remember_option(option + '\n' + key + '\n' + optname,
                        modelrow[Column.VALUE], default)
                    app.config.set_per(optname, key, option, default)
                else:
                    self.remember_option(option, modelrow[Column.VALUE], default)
                    app.config.set(option, default)
                modelrow[Column.VALUE] = self.right_true_dict[default]
                self.check_for_restart()
            else:
                if str(default) == model[iter_][Column.VALUE]:
                    return
                self.on_config_edited(None, path.to_string(), str(default))

    def on_advanced_close_button_clicked(self, widget):
        self.window.destroy()

    def fill_model(self, node=None, parent=None):
        for item, option in app.config.get_children(node):
            name = item[-1]
            if option is None: # Node
                newparent = self.model.append(parent, [name, '', ''])
                self.fill_model(item, newparent)
            else: # Leaf
                if len(item) == 1:
                    type_ = self.types[app.config.get_type(name)]
                elif len(item) == 3:
                    type_ = self.types[app.config.get_type_per(item[0],
                        item[2])]
                if name == 'password':
                    value = _('Hidden')
                else:
                    if type_ == self.types['boolean']:
                        value = self.right_true_dict[option]
                    else:
                        try:
                            value = str(option)
                        except:
                            value = option
                self.model.append(parent, [name, value, type_])

    def visible_func(self, model, treeiter, data):
        search_string  = self.entry.get_text().lower()
        for it in tree_model_pre_order(model, treeiter):
            if model[it][Column.TYPE] != '':
                opt_path = self.get_option_path(model, it)
                if len(opt_path) == 3:
                    desc = app.config.get_desc_per(opt_path[2], opt_path[0])
                elif len(opt_path) == 1:
                    desc = app.config.get_desc(opt_path[0])
                if search_string in model[it][Column.PREFERENCE_NAME] or (desc and \
                search_string in desc.lower()):
                    return True
        return False

    @rate_limit(3)
    def on_advanced_entry_changed(self, widget):
        self.modelfilter.refilter()
        if not widget.get_text():
            # Maybe the expanded rows should be remembered here ...
            self.treeview.collapse_all()
        else:
            # ... and be restored correctly here
            self.treeview.expand_all()
