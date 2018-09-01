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

import nbxmpp

from gi.repository import Gtk
from gi.repository import GObject

from gajim.common import app
from gajim.common.const import DEVS_CURRENT
from gajim.common.const import DEVS_PAST
from gajim.common.const import ARTISTS
from gajim.common.const import THANKS


class AboutDialog(Gtk.AboutDialog):
    def __init__(self):
        Gtk.AboutDialog.__init__(self)
        self.set_transient_for(app.interface.roster.window)
        self.set_name('Gajim')
        self.set_version(app.version)
        self.set_copyright('Copyright © 2003-2018 Gajim Team')
        self.set_license_type(Gtk.License.GPL_3_0_ONLY)
        self.set_website('https://gajim.org/')

        gtk_ver = '%i.%i.%i' % (
            Gtk.get_major_version(),
            Gtk.get_minor_version(),
            Gtk.get_micro_version())
        gobject_ver = '.'.join(map(str, GObject.pygobject_version))

        comments = []
        comments.append(_('A GTK+ XMPP client'))
        comments.append(_('GTK+ Version: %s' % gtk_ver))
        comments.append(_('PyGObject Version: %s') % gobject_ver)
        comments.append(_('python-nbxmpp Version: %s') % nbxmpp.__version__)
        self.set_comments("\n".join(comments))

        self.add_credit_section(_('Current Developers'), DEVS_CURRENT)
        self.add_credit_section(_('Past Developers'), DEVS_PAST)
        self.add_credit_section(_('Artists'), ARTISTS)

        thanks = list(THANKS)
        thanks.append('')
        thanks.append(_('Last but not least'))
        thanks.append(_('we would like to thank all the package maintainers.'))
        self.add_credit_section(_('Thanks'), thanks)

        self.set_translator_credits(_('translator-credits'))
        self.set_logo_icon_name('org.gajim.Gajim')

        self.connect(
            'response', lambda dialog, *args: Gtk.AboutDialog.do_close(dialog))

        self.show()
