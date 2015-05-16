#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2011       Tim G L Lyons
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Provide the database state class
"""
import sys

from .db import DbReadBase
from .proxy.proxybase import ProxyDbBase
from .utils.callback import Callback
from .config import config

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".dbstate")

class DbState(Callback):
    """
    Provide a class to encapsulate the state of the database.
    """

    __signals__ = {
        'database-changed' : ((DbReadBase, ProxyDbBase), ), 
        'no-database' :  None, 
        }

    def __init__(self):
        """
        Initalize the state with an empty (and useless) DbBsddbRead. This is
        just a place holder until a real DB is assigned.
        """
        Callback.__init__(self)
        self.db      = self.make_database("bsddb")
        self.open    = False
        self.stack = []

    def change_database(self, database):
        """
        Closes the existing db, and opens a new one.
        Retained for backward compatibility.
        """
        self.emit('no-database', ())
        self.db.close()
        self.change_database_noclose(database)

    def change_database_noclose(self, database):
        """
        Change the current database. and resets the configuration prefixes.
        """
        self.db = database
        self.db.set_prefixes(
            config.get('preferences.iprefix'),
            config.get('preferences.oprefix'),
            config.get('preferences.fprefix'),
            config.get('preferences.sprefix'),
            config.get('preferences.cprefix'),
            config.get('preferences.pprefix'),
            config.get('preferences.eprefix'),
            config.get('preferences.rprefix'),
            config.get('preferences.nprefix') )
        self.open = True
        self.signal_change()

    def signal_change(self):
        """
        Emits the database-changed signal with the new database
        """
        self.emit('database-changed', (self.db, ))

    def no_database(self):
        """
        Closes the database without a new database
        """
        self.emit('no-database', ())
        self.db.close()
        self.db = self.make_database("bsddb")
        self.db.db_is_open = False
        self.open = False
        self.emit('database-changed', (self.db, ))
        
    def get_database(self):
        """
        Get a reference to the current database.
        """
        return self.db

    def apply_proxy(self, proxy, *args, **kwargs):
        """
        Add a proxy to the current database. Use pop_proxy() to
        revert to previous db.

        >>> dbstate.apply_proxy(gen.proxy.LivingProxyDb, 1)
        >>> dbstate.apply_proxy(gen.proxy.PrivateProxyDb)
        """
        self.stack.append(self.db)
        self.db = proxy(self.db, *args, **kwargs)
        self.emit('database-changed', (self.db, ))
        
    def pop_proxy(self):
        """
        Remove the previously applied proxy.

        >>> dbstate.apply_proxy(gen.proxy.LivingProxyDb, 1)
        >>> dbstate.pop_proxy()
        >>> dbstate.apply_proxy(gen.proxy.PrivateProxyDb)
        >>> dbstate.pop_proxy()
        """
        self.db = self.stack.pop()
        self.emit('database-changed', (self.db, ))

    def make_database(self, id):
        """
        Make a database, given a plugin id.
        """
        from .plug import BasePluginManager
        from .const import PLUGINS_DIR, USER_PLUGINS

        pmgr = BasePluginManager.get_instance()
        pdata = pmgr.get_plugin(id)
        
        if not pdata:
            # This might happen if using gramps from outside, and
            # we haven't loaded plugins yet
            pmgr.reg_plugins(PLUGINS_DIR, self, None)
            pmgr.reg_plugins(USER_PLUGINS, self, None, load_on_reg=True)
            pdata = pmgr.get_plugin(id)

        if pdata:
            if pdata.reset_system:
                if self.modules_is_set():
                    self.reset_modules()
                else:
                    self.save_modules()
            mod = pmgr.load_plugin(pdata)
            database = getattr(mod, pdata.databaseclass)
            return database()

    ## Work-around for databases that need sys refresh (django):
    def modules_is_set(self):
        LOG.info("modules_is_set?")
        if hasattr(self, "_modules"):
            return self._modules != None
        else:
            self._modules = None
            return False

    def reset_modules(self):
        LOG.info("reset_modules!")
        # First, clear out old modules:
        for key in list(sys.modules.keys()):
            del(sys.modules[key])
        # Next, restore previous:
        for key in self._modules:
            sys.modules[key] = self._modules[key]

    def save_modules(self):
        LOG.info("save_modules!")
        self._modules = sys.modules.copy()

