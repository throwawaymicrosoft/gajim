# -*- coding:utf-8 -*-
## gajim/common/logger.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
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

"""
This module allows to access the on-disk database of logs
"""

import os
import sys
import time
import datetime
import calendar
import json
import logging
import sqlite3 as sqlite
from collections import namedtuple
from gzip import GzipFile
from io import BytesIO
from gi.repository import GLib

from gajim.common import exceptions
from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import (
    JIDConstant, KindConstant, ShowConstant, TypeConstant,
    SubscriptionConstant)


LOGS_SQL_STATEMENT = '''
    CREATE TABLE jids(
            jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            jid TEXT UNIQUE,
            type INTEGER
    );
    CREATE TABLE unread_messages(
            message_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            jid_id INTEGER,
            shown BOOLEAN default 0
    );
    CREATE INDEX idx_unread_messages_jid_id ON unread_messages (jid_id);
    CREATE TABLE logs(
            log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            account_id INTEGER,
            jid_id INTEGER,
            contact_name TEXT,
            time INTEGER,
            kind INTEGER,
            show INTEGER,
            message TEXT,
            subject TEXT,
            additional_data TEXT,
            stanza_id TEXT,
            encryption TEXT,
            encryption_state TEXT,
            marker INTEGER
    );
    CREATE TABLE last_archive_message(
            jid_id INTEGER PRIMARY KEY UNIQUE,
            last_mam_id TEXT,
            oldest_mam_timestamp TEXT,
            last_muc_timestamp TEXT
    );
    CREATE INDEX idx_logs_jid_id_time ON logs (jid_id, time DESC);
    CREATE INDEX idx_logs_stanza_id ON logs (stanza_id);
    PRAGMA user_version=1;
    '''

CACHE_SQL_STATEMENT = '''
    CREATE TABLE transports_cache (
            transport TEXT UNIQUE,
            type INTEGER
    );
    CREATE TABLE caps_cache (
            hash_method TEXT,
            hash TEXT,
            data BLOB,
            last_seen INTEGER);
    CREATE TABLE rooms_last_message_time(
            jid_id INTEGER PRIMARY KEY UNIQUE,
            time INTEGER
    );
    CREATE TABLE roster_entry(
            account_jid_id INTEGER,
            jid_id INTEGER,
            name TEXT,
            subscription INTEGER,
            ask BOOLEAN,
            avatar_sha TEXT,
            PRIMARY KEY (account_jid_id, jid_id)
    );
    CREATE TABLE roster_group(
            account_jid_id INTEGER,
            jid_id INTEGER,
            group_name TEXT,
            PRIMARY KEY (account_jid_id, jid_id, group_name)
    );
    PRAGMA user_version=1;
    '''

log = logging.getLogger('gajim.c.logger')


class Logger:
    def __init__(self):
        self._jid_ids = {}
        self._jid_ids_reversed = {}
        self._con = None
        self._commit_timout_id = None
        self._log_db_path = configpaths.get('LOG_DB')
        self._cache_db_path = configpaths.get('CACHE_DB')

        self._create_databases()
        self._migrate_databases()
        self._connect_databases()
        self._get_jid_ids_from_db()

    def _create_databases(self):
        if os.path.isdir(self._log_db_path):
            log.error(_('%s is a directory but should be a file'),
                      self._log_db_path)
            sys.exit()

        if os.path.isdir(self._cache_db_path):
            log.error(_('%s is a directory but should be a file'),
                      self._cache_db_path)
            sys.exit()

        if not os.path.exists(self._log_db_path):
            if os.path.exists(self._cache_db_path):
                os.remove(self._cache_db_path)
            self._create(LOGS_SQL_STATEMENT, self._log_db_path)

        if not os.path.exists(self._cache_db_path):
            self._create(CACHE_SQL_STATEMENT, self._cache_db_path)

    @staticmethod
    def _connect(*args, **kwargs):
        con = sqlite.connect(*args, **kwargs)
        con.execute("PRAGMA secure_delete=1")
        return con

    @classmethod
    def _create(cls, statement, path):
        log.info(_('Creating %s'), path)
        con = cls._connect(path)
        os.chmod(path, 0o600)

        try:
            con.executescript(statement)
        except Exception as error:
            log.exception('Error')
            con.close()
            os.remove(path)
            sys.exit()

        con.commit()
        con.close()

    @staticmethod
    def _get_user_version(con) -> int:
        """ Return the value of PRAGMA user_version. """
        return con.execute('PRAGMA user_version').fetchone()[0]

    def _migrate_databases(self):
        try:
            con = self._connect(self._log_db_path)
            self._migrate_logs(con)
            con.close()

            con = self._connect(self._cache_db_path)
            self._migrate_cache(con)
            con.close()
        except Exception:
            log.exception('Error')
            sys.exit()

    def _migrate_logs(self, con):
        if self._get_user_version(con) == 0:
            # All migrations from 0.16.9 until 1.0.0
            statements = [
                'ALTER TABLE logs ADD COLUMN "account_id" INTEGER',
                'ALTER TABLE logs ADD COLUMN "stanza_id" TEXT',
                'ALTER TABLE logs ADD COLUMN "encryption" TEXT',
                'ALTER TABLE logs ADD COLUMN "encryption_state" TEXT',
                'ALTER TABLE logs ADD COLUMN "marker" INTEGER',
                'ALTER TABLE logs ADD COLUMN "additional_data" TEXT',
                '''CREATE TABLE IF NOT EXISTS last_archive_message(
                    jid_id INTEGER PRIMARY KEY UNIQUE,
                    last_mam_id TEXT,
                    oldest_mam_timestamp TEXT,
                    last_muc_timestamp TEXT
                    )''',

                '''CREATE INDEX IF NOT EXISTS idx_logs_stanza_id
                    ON logs(stanza_id)''',
                'PRAGMA user_version=1'
                ]

            self._execute_multiple(con, statements)

        if self._get_user_version(con) < 2:
            pass

    def _migrate_cache(self, con):
        if self._get_user_version(con) == 0:
            # All migrations from 0.16.9 until 1.0.0
            statements = [
                'ALTER TABLE roster_entry ADD COLUMN "avatar_sha" TEXT',
                'PRAGMA user_version=1'
                ]
            self._execute_multiple(con, statements)

        if self._get_user_version(con) < 2:
            pass

    @staticmethod
    def _execute_multiple(con, statements):
        """
        Execute mutliple statements with the option to fail on duplicates
        but still continue
        """
        for sql in statements:
            try:
                con.execute(sql)
                con.commit()
            except sqlite.OperationalError as error:
                if str(error).startswith('duplicate column name:'):
                    log.info(error)
                else:
                    log.exception('Error')
                    sys.exit()

    def namedtuple_factory(self, cursor, row):
        """
        Usage:
        con.row_factory = namedtuple_factory
        """
        fields = [col[0] for col in cursor.description]
        Row = namedtuple("Row", fields)
        named_row = Row(*row)
        if 'additional_data' in fields:
            named_row = named_row._replace(
                additional_data=json.loads(named_row.additional_data or '{}'))

        # if an alias `account` for the field `account_id` is used for the
        # query, the account_id is converted to the account jid
        if 'account' in fields:
            if named_row.account:
                jid = self._jid_ids_reversed[named_row.account].jid
                named_row = named_row._replace(account=jid)
        return named_row

    def dispatch(self, event, error):
        app.ged.raise_event(event, None, str(error))

    def _connect_databases(self):
        self._con = self._connect(
            self._log_db_path, timeout=20.0, isolation_level='IMMEDIATE')

        self._con.row_factory = self.namedtuple_factory

        # DB functions
        self._con.create_function("like", 1, self._like)
        self._con.create_function("get_timeout", 0, self._get_timeout)

        self._set_synchronous(False)
        try:
            self._con.execute("ATTACH DATABASE '%s' AS cache" %
                              self._cache_db_path.replace("'", "''"))
        except Exception as error:
            log.exception('Error')
            self._con.close()
            sys.exit()

    def _set_synchronous(self, sync):
        try:
            if sync:
                self._con.execute("PRAGMA synchronous = NORMAL")
            else:
                self._con.execute("PRAGMA synchronous = OFF")
        except sqlite.Error as e:
            log.exception('Error')

    @staticmethod
    def _get_timeout():
        """
        returns the timeout in epoch
        """
        timeout = app.config.get('restore_timeout')

        now = int(time.time())
        if timeout > 0:
            timeout = now - (timeout * 60)
        return timeout

    @staticmethod
    def _like(search_str):
        return '%{}%'.format(search_str)

    def commit(self):
        try:
            self._con.commit()
        except sqlite.OperationalError as e:
            print(str(e), file=sys.stderr)
        self._commit_timout_id = None
        return False

    def _timeout_commit(self):
        if self._commit_timout_id:
            return
        self._commit_timout_id = GLib.timeout_add(500, self.commit)

    def simple_commit(self, sql_to_commit):
        """
        Helper to commit
        """
        self._con.execute(sql_to_commit)
        self._timeout_commit()

    def _get_jid_ids_from_db(self):
        """
        Load all jid/jid_id tuples into a dict for faster access
        """
        rows = self._con.execute(
            'SELECT jid_id, jid, type FROM jids').fetchall()
        for row in rows:
            self._jid_ids[row.jid] = row
            self._jid_ids_reversed[row.jid_id] = row

    def get_jids_in_db(self):
        return self._jid_ids.keys()

    def jid_is_from_pm(self, jid):
        """
        If jid is gajim@conf/nkour it's likely a pm one, how we know gajim@conf
        is not a normal guy and nkour is not his resource?  we ask if gajim@conf
        is already in jids (with type room jid) this fails if user disables
        logging for room and only enables for pm (so higly unlikely) and if we
        fail we do not go chaos (user will see the first pm as if it was message
        in room's public chat) and after that all okay
        """
        if jid.find('/') > -1:
            possible_room_jid = jid.split('/', 1)[0]
            return self.jid_is_room_jid(possible_room_jid)
        else:
            # it's not a full jid, so it's not a pm one
            return False

    def jid_is_room_jid(self, jid):
        """
        Return True if it's a room jid, False if it's not, None if we don't know
        """
        jid_ = self._jid_ids.get(jid)
        if jid_ is None:
            return
        return jid_.type == JIDConstant.ROOM_TYPE

    @staticmethod
    def _get_family_jids(account, jid):
        """
        Get all jids of the metacontacts family

        :param account: The account

        :param jid:     The JID

        returns a list of JIDs'
        """
        family = app.contacts.get_metacontacts_family(account, jid)
        if family:
            return [user['jid'] for user in family]
        return [jid]

    def get_account_id(self, account):
        jid = app.get_jid_from_account(account)
        return self.get_jid_id(jid, type_=JIDConstant.NORMAL_TYPE)

    def get_jid_id(self, jid, kind=None, type_=None):
        """
        Get the jid id from a jid.
        In case the jid id is not found create a new one.

        :param jid:     The JID

        :param kind:    The KindConstant

        :param type_:   The JIDConstant

        return the jid id
        """

        if kind in (KindConstant.GC_MSG, KindConstant.GCSTATUS):
            type_ = JIDConstant.ROOM_TYPE
        elif kind is not None:
            type_ = JIDConstant.NORMAL_TYPE

        result = self._jid_ids.get(jid, None)
        if result is not None:
            return result.jid_id

        sql = 'SELECT jid_id, jid, type FROM jids WHERE jid = ?'
        row = self._con.execute(sql, [jid]).fetchone()
        if row is not None:
            self._jid_ids[jid] = row
            return row.jid_id

        if type_ is None:
            raise ValueError(
                'Unable to insert new JID because type is missing')

        sql = 'INSERT INTO jids (jid, type) VALUES (?, ?)'
        lastrowid = self._con.execute(sql, (jid, type_)).lastrowid
        Row = namedtuple('Row', 'jid_id jid type')
        self._jid_ids[jid] = Row(lastrowid, jid, type_)
        self._timeout_commit()
        return lastrowid

    def convert_kind_values_to_db_api_values(self, kind):
        """
        Convert from string style to constant ints for db
        """
        if kind == 'status':
            kind_col = KindConstant.STATUS
        elif kind == 'gcstatus':
            kind_col = KindConstant.GCSTATUS
        elif kind == 'gc_msg':
            kind_col = KindConstant.GC_MSG
        elif kind == 'single_msg_recv':
            kind_col = KindConstant.SINGLE_MSG_RECV
        elif kind == 'single_msg_sent':
            kind_col = KindConstant.SINGLE_MSG_SENT
        elif kind == 'chat_msg_recv':
            kind_col = KindConstant.CHAT_MSG_RECV
        elif kind == 'chat_msg_sent':
            kind_col = KindConstant.CHAT_MSG_SENT
        elif kind == 'error':
            kind_col = KindConstant.ERROR

        return kind_col

    def convert_show_values_to_db_api_values(self, show):
        """
        Convert from string style to constant ints for db
        """

        if show == 'online':
            return ShowConstant.ONLINE
        elif show == 'chat':
            return ShowConstant.CHAT
        elif show == 'away':
            return ShowConstant.AWAY
        elif show == 'xa':
            return ShowConstant.XA
        elif show == 'dnd':
            return ShowConstant.DND
        elif show == 'offline':
            return ShowConstant.OFFLINE
        elif show is None:
            return ShowConstant.ONLINE
        else: # invisible in GC when someone goes invisible
            # it's a RFC violation .... but we should not crash
            return None

    def convert_human_transport_type_to_db_api_values(self, type_):
        """
        Convert from string style to constant ints for db
        """
        if type_ == 'aim':
            return TypeConstant.AIM
        if type_ == 'gadu-gadu':
            return TypeConstant.GG
        if type_ == 'http-ws':
            return TypeConstant.HTTP_WS
        if type_ == 'icq':
            return TypeConstant.ICQ
        if type_ == 'msn':
            return TypeConstant.MSN
        if type_ == 'qq':
            return TypeConstant.QQ
        if type_ == 'sms':
            return TypeConstant.SMS
        if type_ == 'smtp':
            return TypeConstant.SMTP
        if type_ in ('tlen', 'x-tlen'):
            return TypeConstant.TLEN
        if type_ == 'newmail':
            return TypeConstant.NEWMAIL
        if type_ == 'rss':
            return TypeConstant.RSS
        if type_ == 'weather':
            return TypeConstant.WEATHER
        if type_ == 'mrim':
            return TypeConstant.MRIM
        if type_ == 'jabber':
            return TypeConstant.NO_TRANSPORT
        return None

    def convert_api_values_to_human_transport_type(self, type_id):
        """
        Convert from constant ints for db to string style
        """
        if type_id == TypeConstant.AIM:
            return 'aim'
        if type_id == TypeConstant.GG:
            return 'gadu-gadu'
        if type_id == TypeConstant.HTTP_WS:
            return 'http-ws'
        if type_id == TypeConstant.ICQ:
            return 'icq'
        if type_id == TypeConstant.MSN:
            return 'msn'
        if type_id == TypeConstant.QQ:
            return 'qq'
        if type_id == TypeConstant.SMS:
            return 'sms'
        if type_id == TypeConstant.SMTP:
            return 'smtp'
        if type_id == TypeConstant.TLEN:
            return 'tlen'
        if type_id == TypeConstant.NEWMAIL:
            return 'newmail'
        if type_id == TypeConstant.RSS:
            return 'rss'
        if type_id == TypeConstant.WEATHER:
            return 'weather'
        if type_id == TypeConstant.MRIM:
            return 'mrim'
        if type_id == TypeConstant.NO_TRANSPORT:
            return 'jabber'

    def convert_human_subscription_values_to_db_api_values(self, sub):
        """
        Convert from string style to constant ints for db
        """
        if sub == 'none':
            return SubscriptionConstant.NONE
        if sub == 'to':
            return SubscriptionConstant.TO
        if sub == 'from':
            return SubscriptionConstant.FROM
        if sub == 'both':
            return SubscriptionConstant.BOTH

    def convert_db_api_values_to_human_subscription_values(self, sub):
        """
        Convert from constant ints for db to string style
        """
        if sub == SubscriptionConstant.NONE:
            return 'none'
        if sub == SubscriptionConstant.TO:
            return 'to'
        if sub == SubscriptionConstant.FROM:
            return 'from'
        if sub == SubscriptionConstant.BOTH:
            return 'both'

    def insert_unread_events(self, message_id, jid_id):
        """
        Add unread message with id: message_id
        """
        sql = 'INSERT INTO unread_messages VALUES (%d, %d, 0)' % (message_id,
                jid_id)
        self.simple_commit(sql)

    def set_read_messages(self, message_ids):
        """
        Mark all messages with ids in message_ids as read
        """
        ids = ','.join([str(i) for i in message_ids])
        sql = 'DELETE FROM unread_messages WHERE message_id IN (%s)' % ids
        self.simple_commit(sql)

    def set_shown_unread_msgs(self, msg_log_id):
        """
        Mark unread message as shown un GUI
        """
        sql = 'UPDATE unread_messages SET shown = 1 where message_id = %s' % \
                msg_log_id
        self.simple_commit(sql)

    def reset_shown_unread_messages(self):
        """
        Set shown field to False in unread_messages table
        """
        sql = 'UPDATE unread_messages SET shown = 0'
        self.simple_commit(sql)

    def get_unread_msgs(self):
        """
        Get all unread messages
        """
        all_messages = []
        try:
            unread_results = self._con.execute(
                'SELECT message_id, shown from unread_messages').fetchall()
        except Exception:
            unread_results = []
        for message in unread_results:
            msg_log_id = message.message_id
            shown = message.shown
            # here we get infos for that message, and related jid from jids table
            # do NOT change order of SELECTed things, unless you change function(s)
            # that called this function
            result = self._con.execute('''
                    SELECT logs.log_line_id, logs.message, logs.time, logs.subject,
                    jids.jid, logs.additional_data
                    FROM logs, jids
                    WHERE logs.log_line_id = %d AND logs.jid_id = jids.jid_id
                    ''' % msg_log_id
                    ).fetchone()
            if result is None:
                # Log line is no more in logs table. remove it from unread_messages
                self.set_read_messages([msg_log_id])
                continue

            all_messages.append((result, shown))
        return all_messages

    def get_last_conversation_lines(self, account, jid, pending):
        """
        Get recent messages

        Pending messages are already in queue to be printed when the
        ChatControl is opened, so we dont want to request those messages.
        How many messages are requested depends on the 'restore_lines'
        config value. How far back in time messages are requested depends on
        _get_timeout().

        :param account: The account

        :param jid:     The jid from which we request the conversation lines

        :param pending: How many messages are currently pending so we dont
                        request those messages

        returns a list of namedtuples
        """

        restore = app.config.get('restore_lines')
        if restore <= 0:
            return []

        kinds = map(str, [KindConstant.SINGLE_MSG_RECV,
                          KindConstant.SINGLE_MSG_SENT,
                          KindConstant.CHAT_MSG_RECV,
                          KindConstant.CHAT_MSG_SENT,
                          KindConstant.ERROR])

        jids = self._get_family_jids(account, jid)

        sql = '''
            SELECT time, kind, message, subject, additional_data
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids}) AND
            kind IN ({kinds}) AND time > get_timeout()
            ORDER BY time DESC, log_line_id DESC LIMIT ? OFFSET ?
            '''.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        try:
            messages = self._con.execute(
                sql, tuple(jids) + (restore, pending)).fetchall()
        except sqlite.DatabaseError:
            self.dispatch('DB_ERROR',
                          exceptions.DatabaseMalformed(self._log_db_path))
            return []

        messages.reverse()
        return messages

    def get_unix_time_from_date(self, year, month, day):
        # year (fe 2005), month (fe 11), day (fe 25)
        # returns time in seconds for the second that starts that date since epoch
        # gimme unixtime from year month day:
        d = datetime.date(year, month, day)
        local_time = d.timetuple() # time tuple (compat with time.localtime())
        # we have time since epoch baby :)
        start_of_day = int(time.mktime(local_time))
        return start_of_day

    def get_conversation_for_date(self, account, jid, date):
        """
        Load the complete conversation with a given jid on a specific date

        :param account: The account

        :param jid:     The jid for which we request the conversation

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a list of namedtuples
        """

        jids = self._get_family_jids(account, jid)

        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)

        sql = '''
            SELECT contact_name, time, kind, show, message, subject,
                   additional_data, log_line_id
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND time BETWEEN ? AND ?
            ORDER BY time, log_line_id
            '''.format(jids=', '.join('?' * len(jids)))

        return self._con.execute(sql, tuple(jids) +
                                      (date.timestamp(),
                                      (date + delta).timestamp())).fetchall()

    def search_log(self, account, jid, query, date=None):
        """
        Search the conversation log for messages containing the `query` string.

        The search can either span the complete log for the given
        `account` and `jid` or be restriced to a single day by
        specifying `date`.

        :param account: The account

        :param jid:     The jid for which we request the conversation

        :param query:   A search string

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)

        if date:
            delta = datetime.timedelta(
                hours=23, minutes=59, seconds=59, microseconds=999999)

            between = '''
                AND time BETWEEN {start} AND {end}
                '''.format(start=date.timestamp(),
                           end=(date + delta).timestamp())

        sql = '''
        SELECT contact_name, time, kind, show, message, subject,
               additional_data, log_line_id
        FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
        AND message LIKE like(?) {date_search}
        ORDER BY time, log_line_id
        '''.format(jids=', '.join('?' * len(jids)),
                   date_search=between if date else '')

        return self._con.execute(sql, tuple(jids) + (query,)).fetchall()

    def get_days_with_logs(self, account, jid, year, month):
        """
        Request the days in a month where we received messages
        for a given `jid`.

        :param account: The account

        :param jid:     The jid for which we request the days

        :param year:    The year

        :param month:   The month

        returns a list of namedtuples
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        # Calculate the start and end datetime of the month
        date = datetime.datetime(year, month, 1)
        days = calendar.monthrange(year, month)[1] - 1
        delta = datetime.timedelta(
            days=days, hours=23, minutes=59, seconds=59, microseconds=999999)

        sql = """
            SELECT DISTINCT 
            CAST(strftime('%d', time, 'unixepoch', 'localtime') AS INTEGER)
            AS day FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND time BETWEEN ? AND ?
            AND kind NOT IN ({kinds})
            ORDER BY time
            """.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        return self._con.execute(sql, tuple(jids) +
                                      (date.timestamp(),
                                      (date + delta).timestamp())).fetchall()

    def get_last_date_that_has_logs(self, account, jid):
        """
        Get the timestamp of the last message we received for the jid.

        :param account: The account

        :param jid:     The jid for which we request the last timestamp

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MAX(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND kind NOT IN ({kinds})
            '''.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MAX() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    def get_first_date_that_has_logs(self, account, jid):
        """
        Get the timestamp of the first message we received for the jid.

        :param account: The account

        :param jid:     The jid for which we request the first timestamp

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        sql = '''
            SELECT MIN(time) as time FROM logs
            NATURAL JOIN jids WHERE jid IN ({jids})
            AND kind NOT IN ({kinds})
            '''.format(jids=', '.join('?' * len(jids)),
                       kinds=', '.join(kinds))

        # fetchone() returns always at least one Row with all
        # attributes set to None because of the MIN() function
        return self._con.execute(sql, tuple(jids)).fetchone().time

    def get_date_has_logs(self, account, jid, date):
        """
        Get single timestamp of a message we received for the jid
        in the time range of one day.

        :param account: The account

        :param jid:     The jid for which we request the first timestamp

        :param date:    datetime.datetime instance
                        example: datetime.datetime(year, month, day)

        returns a timestamp or None
        """
        jids = self._get_family_jids(account, jid)

        kinds = map(str, [KindConstant.STATUS,
                          KindConstant.GCSTATUS])

        delta = datetime.timedelta(
            hours=23, minutes=59, seconds=59, microseconds=999999)

        sql = '''
            SELECT time
            FROM logs NATURAL JOIN jids WHERE jid IN ({jids})
            AND time BETWEEN ? AND ?
            '''.format(jids=', '.join('?' * len(jids)))

        return self._con.execute(sql, tuple(jids) +
                                      (date.timestamp(),
                                      (date + delta).timestamp())).fetchone()

    def get_room_last_message_time(self, account, jid):
        """
        Get the timestamp of the last message we received in a room.

        :param account: The account

        :param jid:     The jid for which we request the last timestamp

        returns a timestamp or None
        """
        sql = '''
            SELECT time FROM rooms_last_message_time
            NATURAL JOIN jids WHERE jid = ?
            '''

        row = self._con.execute(sql, (jid,)).fetchone()
        if not row:
            return self.get_last_date_that_has_logs(account, jid)
        return row.time

    def set_room_last_message_time(self, jid, timestamp):
        """
        Set the timestamp of the last message we received in a room.

        :param jid:         The jid

        :param timestamp:   The timestamp in epoch

        """

        jid_id = self.get_jid_id(jid, type_=JIDConstant.ROOM_TYPE)
        sql = '''REPLACE INTO rooms_last_message_time
                 VALUES (:jid_id, COALESCE(
                 (SELECT time FROM rooms_last_message_time
                  WHERE jid_id = :jid_id AND time >= :time), :time))'''

        self._con.execute(sql, {"jid_id": jid_id, "time": timestamp})
        self._timeout_commit()

    def save_transport_type(self, jid, type_):
        """
        Save the type of the transport in DB
        """
        type_id = self.convert_human_transport_type_to_db_api_values(type_)
        if not type_id:
            # unknown type
            return
        result = self._con.execute(
            'SELECT type from transports_cache WHERE transport = "%s"' % jid).fetchone()
        if result:
            if result.type == type_id:
                return
            sql = 'UPDATE transports_cache SET type = %d WHERE transport = "%s"' %\
                    (type_id, jid)
            self.simple_commit(sql)
            return
        sql = 'INSERT INTO transports_cache VALUES ("%s", %d)' % (jid, type_id)
        self.simple_commit(sql)

    def get_transports_type(self):
        """
        Return all the type of the transports in DB
        """
        results = self._con.execute('SELECT * from transports_cache').fetchall()
        if not results:
            return {}
        answer = {}
        for result in results:
            answer[result.transport] = self.convert_api_values_to_human_transport_type(
                    result.type)
        return answer

    # A longer note here:
    # The database contains a blob field. Pysqlite seems to need special care for
    # such fields.
    # When storing, we need to convert string into buffer object (1).
    # When retrieving, we need to convert it back to a string to decompress it.
    # (2)
    # GzipFile needs a file-like object, StringIO emulates file for plain strings
    def iter_caps_data(self):
        """
        Iterate over caps cache data stored in the database

        The iterator values are pairs of (node, ver, ext, identities, features):
        identities == {'category':'foo', 'type':'bar', 'name':'boo'},
        features being a list of feature namespaces.
        """
        # get data from table
        # the data field contains binary object (gzipped data), this is a hack
        # to get that data without trying to convert it to unicode
        try:
            rows = self._con.execute('SELECT hash_method, hash, data FROM caps_cache;')
        except sqlite.OperationalError:
            # might happen when there's no caps_cache table yet
            # -- there's no data to read anyway then
            return

        # list of corrupted entries that will be removed
        to_be_removed = []
        for row in rows:
            # for each row: unpack the data field
            # (format: (category, type, name, category, type, name, ...
            #   ..., 'FEAT', feature1, feature2, ...).join(' '))
            # NOTE: if there's a need to do more gzip, put that to a function
            try:
                data = GzipFile(fileobj=BytesIO(row.data)).read().decode('utf-8').split('\0')
            except IOError:
                # This data is corrupted. It probably contains non-ascii chars
                to_be_removed.append((row.hash_method, row.hash))
                continue
            i = 0
            identities = list()
            features = list()
            while i < (len(data) - 3) and data[i] != 'FEAT':
                category = data[i]
                type_ = data[i + 1]
                lang = data[i + 2]
                name = data[i + 3]
                identities.append({'category': category, 'type': type_,
                        'xml:lang': lang, 'name': name})
                i += 4
            i+=1
            while i < len(data):
                features.append(data[i])
                i += 1

            # yield the row
            yield row.hash_method, row.hash, identities, features
        for hash_method, hash_ in to_be_removed:
            sql = '''DELETE FROM caps_cache WHERE hash_method = "%s" AND
                    hash = "%s"''' % (hash_method, hash_)
            self.simple_commit(sql)

    def add_caps_entry(self, hash_method, hash_, identities, features):
        data = []
        for identity in identities:
            # there is no FEAT category
            if identity['category'] == 'FEAT':
                return
            data.extend((identity.get('category'), identity.get('type', ''),
                    identity.get('xml:lang', ''), identity.get('name', '')))
        data.append('FEAT')
        data.extend(features)
        data = '\0'.join(data)
        # if there's a need to do more gzip, put that to a function
        string = BytesIO()
        gzip = GzipFile(fileobj=string, mode='w')
        gzip.write(data.encode('utf-8'))
        gzip.close()
        data = string.getvalue()
        self._con.execute('''
                INSERT INTO caps_cache ( hash_method, hash, data, last_seen )
                VALUES (?, ?, ?, ?);
                ''', (hash_method, hash_, memoryview(data), int(time.time())))
        # (1) -- note above
        self._timeout_commit()

    def update_caps_time(self, method, hash_):
        sql = '''UPDATE caps_cache SET last_seen = %d
                WHERE hash_method = "%s" and hash = "%s"''' % \
                (int(time.time()), method, hash_)
        self.simple_commit(sql)

    def clean_caps_table(self):
        """
        Remove caps which was not seen for 3 months
        """
        sql = '''DELETE FROM caps_cache WHERE last_seen < %d''' % \
                int(time.time() - 3*30*24*3600)
        self.simple_commit(sql)

    def replace_roster(self, account_name, roster_version, roster):
        """
        Replace current roster in DB by a new one

        accout_name is the name of the account to change.
        roster_version is the version of the new roster.
        roster is the new version.
        """
        # First we must reset roster_version value to ensure that the server
        # sends back all the roster at the next connexion if the replacement
        # didn't work properly.
        app.config.set_per('accounts', account_name, 'roster_version', '')

        account_jid = app.get_jid_from_account(account_name)
        # Execute get_jid_id() because this ensures on new accounts that the
        # jid_id will be created
        self.get_jid_id(account_jid, type_=JIDConstant.NORMAL_TYPE)

        # Delete old roster
        self.remove_roster(account_jid)

        # Fill roster tables with the new roster
        for jid in roster:
            self.add_or_update_contact(account_jid, jid, roster[jid]['name'],
                roster[jid]['subscription'], roster[jid]['ask'],
                roster[jid]['groups'], commit=False)
        self._timeout_commit()

        # At this point, we are sure the replacement works properly so we can
        # set the new roster_version value.
        app.config.set_per('accounts', account_name, 'roster_version',
            roster_version)

    def del_contact(self, account_jid, jid):
        """
        Remove jid from account_jid roster
        """
        try:
            account_jid_id = self.get_jid_id(account_jid)
            jid_id = self.get_jid_id(jid)
        except exceptions.PysqliteOperationalError as e:
            raise exceptions.PysqliteOperationalError(str(e))
        self._con.execute(
                'DELETE FROM roster_group WHERE account_jid_id=? AND jid_id=?',
                (account_jid_id, jid_id))
        self._con.execute(
                'DELETE FROM roster_entry WHERE account_jid_id=? AND jid_id=?',
                (account_jid_id, jid_id))
        self._timeout_commit()

    def add_or_update_contact(self, account_jid, jid, name, sub, ask, groups,
    commit=True):
        """
        Add or update a contact from account_jid roster
        """
        if sub == 'remove':
            self.del_contact(account_jid, jid)
            return

        try:
            account_jid_id = self.get_jid_id(account_jid)
            jid_id = self.get_jid_id(jid, type_=JIDConstant.NORMAL_TYPE)
        except exceptions.PysqliteOperationalError as e:
            raise exceptions.PysqliteOperationalError(str(e))

        # Update groups information
        # First we delete all previous groups information
        self._con.execute(
                'DELETE FROM roster_group WHERE account_jid_id=? AND jid_id=?',
                (account_jid_id, jid_id))
        # Then we add all new groups information
        for group in groups:
            self._con.execute('INSERT INTO roster_group VALUES(?, ?, ?)',
                    (account_jid_id, jid_id, group))

        if name is None:
            name = ''

        self._con.execute('''
            REPLACE INTO roster_entry
            (account_jid_id, jid_id, name, subscription, ask)
            VALUES(?, ?, ?, ?, ?)''', (
                account_jid_id, jid_id, name,
                self.convert_human_subscription_values_to_db_api_values(sub),
                bool(ask)))
        if commit:
            self._timeout_commit()

    def get_roster(self, account_jid):
        """
        Return the accound_jid roster in NonBlockingRoster format
        """
        data = {}
        account_jid_id = self.get_jid_id(account_jid, type_=JIDConstant.NORMAL_TYPE)

        # First we fill data with roster_entry informations
        rows = self._con.execute('''
                SELECT j.jid, re.jid_id, re.name, re.subscription, re.ask, re.avatar_sha
                FROM roster_entry re, jids j
                WHERE re.account_jid_id=? AND j.jid_id=re.jid_id''', (account_jid_id,))
        for row in rows:
            #jid, jid_id, name, subscription, ask
            jid = row.jid
            name = row.name
            data[jid] = {}
            data[jid]['avatar_sha'] = row.avatar_sha
            if name:
                data[jid]['name'] = name
            else:
                data[jid]['name'] = None
            data[jid]['subscription'] = \
                    self.convert_db_api_values_to_human_subscription_values(
                    row.subscription)
            data[jid]['groups'] = []
            data[jid]['resources'] = {}
            if row.ask:
                data[jid]['ask'] = 'subscribe'
            else:
                data[jid]['ask'] = None
            data[jid]['id'] = row.jid_id

        # Then we add group for roster entries
        for jid in data:
            rows = self._con.execute('''
                    SELECT group_name FROM roster_group
                    WHERE account_jid_id=? AND jid_id=?''',
                    (account_jid_id, data[jid]['id']))
            for row in rows:
                group_name = row.group_name
                data[jid]['groups'].append(group_name)
            del data[jid]['id']

        return data

    def remove_roster(self, account_jid):
        """
        Remove the roster of an account

        :param account_jid:     The jid of the account
        """
        try:
            jid_id = self.get_jid_id(account_jid)
        except ValueError:
            # This happens if the JID never made it to the Database
            # because the account was never connected
            return

        sql = '''
            DELETE FROM roster_entry WHERE account_jid_id = {jid_id};
            DELETE FROM roster_group WHERE account_jid_id = {jid_id};
            '''.format(jid_id=jid_id)

        self._con.executescript(sql)
        self._timeout_commit()

    def search_for_duplicate(self, account, jid, timestamp, msg):
        """
        Check if a message is already in the `logs` table

        :param account:     The account

        :param jid:         The jid as string

        :param timestamp:   The timestamp in UTC epoch

        :param msg:         The message text
        """

        # Add 10 seconds around the timestamp
        start_time = timestamp - 30
        end_time = timestamp + 30

        account_id = self.get_account_id(account)
        log.debug('start: %s, end: %s, jid: %s, message: %s',
                  start_time, end_time, jid, msg)

        sql = '''
            SELECT * FROM logs
            NATURAL JOIN jids WHERE jid = ? AND message = ? AND account_id = ?
            AND time BETWEEN ? AND ?
            '''

        result = self._con.execute(
            sql, (jid, msg, account_id, start_time, end_time)).fetchone()

        if result is not None:
            log.debug('Message already in DB')
            return True
        return False

    def find_stanza_id(self, account, archive_jid, stanza_id, origin_id=None,
                       groupchat=False):
        """
        Checks if a stanza-id is already in the `logs` table

        :param account:     The account

        :param archive_jid: The jid of the archive the stanza-id belongs to
                            only used if groupchat=True

        :param stanza_id:   The stanza-id

        :param origin_id:   The origin-id

        :param groupchat:   stanza-id is from a groupchat

        return True if the stanza-id was found
        """
        ids = []
        if stanza_id is not None:
            ids.append(stanza_id)
        if origin_id is not None:
            ids.append(origin_id)

        if not ids:
            return False

        type_ = JIDConstant.NORMAL_TYPE
        if groupchat:
            type_ = JIDConstant.ROOM_TYPE

        archive_id = self.get_jid_id(archive_jid, type_=type_)
        account_id = self.get_account_id(account)

        if groupchat:
            # Stanza ID is only unique within a specific archive.
            # So a Stanza ID could be repeated in different MUCs, so we
            # filter also for the archive JID which is the bare MUC jid.
            sql = '''
                SELECT stanza_id FROM logs
                WHERE stanza_id IN ({values})
                AND jid_id = ? AND account_id = ? LIMIT 1
                '''.format(values=', '.join('?' * len(ids)))
            result = self._con.execute(
                sql, tuple(ids) + (archive_id, account_id)).fetchone()
        else:
            sql = '''
                SELECT stanza_id FROM logs
                WHERE stanza_id IN ({values}) AND account_id = ? AND kind != ? LIMIT 1
                '''.format(values=', '.join('?' * len(ids)))
            result = self._con.execute(
                sql, tuple(ids) + (account_id, KindConstant.GC_MSG)).fetchone()

        if result is not None:
            log.info('Found duplicated message, stanza-id: %s, origin-id: %s, '
                     'archive-jid: %s, account: %s', stanza_id, origin_id, archive_jid, account_id)
            return True
        return False

    def insert_jid(self, jid, kind=None, type_=JIDConstant.NORMAL_TYPE):
        """
        Insert a new jid into the `jids` table.
        This is an alias of get_jid_id() for better readablility.

        :param jid:     The jid as string

        :param kind:    A KindConstant

        :param type_:   A JIDConstant
        """
        return self.get_jid_id(jid, kind, type_)

    def insert_into_logs(self, account, jid, time_, kind,
                         unread=True, **kwargs):
        """
        Insert a new message into the `logs` table

        :param jid:     The jid as string

        :param time_:   The timestamp in UTC epoch

        :param kind:    A KindConstant

        :param unread:  If True the message is added to the`unread_messages`
                        table. Only if kind == CHAT_MSG_RECV

        :param kwargs:  Every additional named argument must correspond to
                        a field in the `logs` table
        """
        jid_id = self.get_jid_id(jid, kind=kind)
        account_id = self.get_account_id(account)

        if 'additional_data' in kwargs:
            if not kwargs['additional_data']:
                del kwargs['additional_data']
            else:
                kwargs['additional_data'] = json.dumps(kwargs["additional_data"])

        sql = '''
              INSERT INTO logs (account_id, jid_id, time, kind, {columns})
              VALUES (?, ?, ?, ?, {values})
              '''.format(columns=', '.join(kwargs.keys()),
                         values=', '.join('?' * len(kwargs)))

        lastrowid = self._con.execute(
            sql, (account_id, jid_id, time_, kind) + tuple(kwargs.values())).lastrowid

        log.info('Insert into DB: jid: %s, time: %s, kind: %s, stanza_id: %s',
                 jid, time_, kind, kwargs.get('stanza_id', None))

        if unread and kind == KindConstant.CHAT_MSG_RECV:
            sql = '''INSERT INTO unread_messages (message_id, jid_id)
                     VALUES (?, (SELECT jid_id FROM jids WHERE jid = ?))'''
            self._con.execute(sql, (lastrowid, jid))

        self._timeout_commit()

        return lastrowid

    def set_avatar_sha(self, account_jid, jid, sha=None):
        """
        Set the avatar sha of a jid on an account

        :param account_jid: The jid of the account

        :param jid:         The jid that belongs to the avatar

        :param sha:         The sha of the avatar

        """

        account_jid_id = self.get_jid_id(account_jid)
        jid_id = self.get_jid_id(jid, type_=JIDConstant.NORMAL_TYPE)

        sql = '''
            UPDATE roster_entry SET avatar_sha = ?
            WHERE account_jid_id = ? AND jid_id = ?
            '''
        self._con.execute(sql, (sha, account_jid_id, jid_id))
        self._timeout_commit()

    def get_archive_timestamp(self, jid, type_=None):
        """
        Get the last archive id/timestamp for a jid

        :param jid:     The jid that belongs to the avatar

        """
        jid_id = self.get_jid_id(jid, type_=type_)
        sql = '''SELECT * FROM last_archive_message WHERE jid_id = ?'''
        return self._con.execute(sql, (jid_id,)).fetchone()

    def set_archive_timestamp(self, jid, **kwargs):
        """
        Set the last archive id/timestamp

        :param jid:                     The jid that belongs to the avatar

        :param last_mam_id:             The last MAM result id

        :param oldest_mam_timestamp:    The oldest date we requested MAM
                                        history for

        :param last_muc_timestamp:      The timestamp of the last message we
                                        received in a MUC

        """
        jid_id = self.get_jid_id(jid)
        exists = self.get_archive_timestamp(jid)
        if not exists:
            sql = '''INSERT INTO last_archive_message VALUES (?, ?, ?, ?)'''
            self._con.execute(sql, (
                jid_id,
                kwargs.get('last_mam_id', None),
                kwargs.get('oldest_mam_timestamp', None),
                kwargs.get('last_muc_timestamp', None)))
        else:
            args = ' = ?, '.join(kwargs.keys()) + ' = ?'
            sql = '''UPDATE last_archive_message SET {}
                     WHERE jid_id = ?'''.format(args)
            self._con.execute(sql, tuple(kwargs.values()) + (jid_id,))
        log.info('Save archive timestamps: %s', kwargs)
        self._timeout_commit()
