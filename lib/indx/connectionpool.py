#    Copyright (C) 2013 University of Southampton
#    Copyright (C) 2013 Daniel Alexander Smith
#    Copyright (C) 2013 Max Van Kleek
#    Copyright (C) 2013 Nigel R. Shadbolt
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License, version 3,
#    as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import copy
from txpostgres import txpostgres
from twisted.internet.defer import Deferred
from twisted.internet import threads

class IndxConnectionPool:
    """ A wrapper for txpostgres connection pools, which auto-reconnects. """

    def __init__(self, _ignored, *connargs, **connkw):
        logging.debug("IndxConnectionPool starting. ")
        self._ignored = _ignored
        self.connargs = connargs
        self.connkw = connkw
        self.subscribers = []
        self.pool = self._connectPool()

    def _connectPool(self):
        logging.debug("IndxConnectionPool _connectionPool")
        return txpostgres.ConnectionPool(self._ignored, *self.connargs, **self.connkw)

    # Wrap existing functions
    def start(self, *args, **kwargs):
        logging.debug("IndxConnectionPool start")
        return self.pool.start(*args, **kwargs)

    def close(self, *args, **kwargs):
        logging.debug("IndxConnectionPool close")
        return self.pool.close(*args, **kwargs)

    def remove(self, *args, **kwargs):
        logging.debug("IndxConnectionPool remove")
        return self.pool.remove(*args, **kwargs)

    def add(self, *args, **kwargs):
        logging.debug("IndxConnectionPool add")
        return self.pool.add(*args, **kwargs)

#
#    def reconnect_subscribe(self, cb):
#        self.subscribers.append(cb)
#
#    def flush_subscribers(self):
#        subs = copy.copy(self.subscribers)
#        self.subscribers = []
#
#        for cb in subs:
#            threads.deferToThread(cb, None)
#

    # Wrap query functions with auto-reconnection
    def runQuery(self, *args, **kwargs):
        logging.debug("IndxConnectionPool runQuery, args: {0}, kwargs: {1}".format(args, kwargs))
        deferred = Deferred()
        pool_deferred = self.pool.runQuery(*args, **kwargs)
        pool_deferred.addCallbacks(deferred.callback, deferred.errback)
#        pool_deferred.addCallback(deferred.callback)
#
#        def err_cb(failure):
#            logging.debug("IndxConnectionPool runQuery err_cb {0} {1}".format(failure, failure.value))
#            # failure!
#            # reconnect and try the query again
#            # TODO check exception is a psycopg2.InterfaceError and a "connection already closed" error first, otherwise send on to the deferred errback instead
#            def connected2(conn):
#                logging.debug("IndxConnectionPool runQuery err_cb connected2")
#                self.flush_subscribers()
#                conn.runQuery(*args, **kwargs).addCallbacks(deferred.callback, deferred.errback)
#
#            self.pool.close() # clean up existing
#            self.pool = self._connectPool()
#            self.pool.start().addCallbacks(connected2, deferred.errback) # FIXME is this the best errback?
#
#        pool_deferred.addErrback(err_cb)
        return deferred


    def runOperation(self, *args, **kwargs):
        logging.debug("IndxConnectionPool runOperation, args: {0}, kwargs: {1}".format(args, kwargs))
        deferred = Deferred()
        pool_deferred = self.pool.runOperation(*args, **kwargs)
        pool_deferred.addCallbacks(deferred.callback, deferred.errback)
#        pool_deferred.addCallback(deferred.callback)
#
#        def err_cb(failure):
#            logging.debug("IndxConnectionPool runOperation err_cb {0} {1}".format(failure, failure.value))
#            # failure!
#            # reconnect and try the query again
#            # TODO check exception is a psycopg2.InterfaceError and a "connection already closed" error first, otherwise send on to the deferred errback instead
#            def connected2(conn):
#                logging.debug("IndxConnectionPool runOperation err_cb connected2")
#                self.flush_subscribers()
#                conn.runOperation(*args, **kwargs).addCallbacks(deferred.callback, deferred.errback)
#
#            self.pool.close() # clean up existing
#            self.pool = self._connectPool()
#            self.pool.start().addCallbacks(connected2, deferred.errback) # FIXME is this the best errback?
#
#        pool_deferred.addErrback(err_cb)
        return deferred


    def runInteraction(self, *args, **kwargs):
        logging.debug("IndxConnectionPool runInteraction, args: {0}, kwargs: {1}".format(args, kwargs))
        deferred = Deferred()
        pool_deferred = self.pool.runInteraction(*args, **kwargs)
        pool_deferred.addCallbacks(deferred.callback, deferred.errback)
#        pool_deferred.addCallback(deferred.callback)
#
#        def err_cb(failure):
#            logging.debug("IndxConnectionPool runInteration err_cb {0} {1}".format(failure, failure.value))
#            # failure!
#            # reconnect and try the query again
#            # TODO check exception is a psycopg2.InterfaceError and a "connection already closed" error first, otherwise send on to the deferred errback instead
#            def connected2(conn):
#                logging.debug("IndxConnectionPool runInteraction err_cb connected2")
#                self.flush_subscribers()
#                conn.runInteraction(*args, **kwargs).addCallbacks(deferred.callback, deferred.errback)
#
#            self.pool.close() # clean up existing
#            self.pool = self._connectPool()
#            self.pool.start().addCallbacks(connected2, deferred.errback) # FIXME is this the best errback?
#
#        pool_deferred.addErrback(err_cb)
        return deferred

