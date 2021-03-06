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
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from indx.crypto import load_key

class IndxKeystore:
    """ Stores keys (public/private/public-hash triple) in a database table and permits access. """

    def __init__(self, db):
        self.db = db

    def put(self, key, username, boxid):
        """ Store a key in the keystore. """
        return_d = Deferred()

        query = "INSERT INTO tbl_keystore (public_hash, public_key, private_key, username, box) VALUES (%s, %s, %s, %s, %s)"
        params = [key['public-hash'], key['public'], key['private'], username, boxid]

        self.db.runOperation(query, params).addCallbacks(return_d.callback, return_d.errback)
        return return_d

    def get(self, public_hash):
        """ Get a key from the store, by the hash of the public key. """
        return_d = Deferred()

        query = "SELECT public_hash, public_key, private_key, username, box FROM tbl_keystore WHERE public_hash = %s"
        params = [public_hash]

        def queried_cb(rows):
            if len(rows) != 1:
                return_d.callback(None) # no key, return nothing
                return

            public_hash, public_key, private_key, username, boxid = rows[0]

            if private_key is None or private_key == '':
                key = {"public-hash": public_hash, "public": load_key(public_key), "private": ""}
            else:
                key = {"public-hash": public_hash, "public": load_key(public_key), "private": load_key(private_key)}

            return_d.callback({"username": username, "box": boxid, "key": key})
        
        self.db.runQuery(query, params).addCallbacks(queried_cb, return_d.errback)
        return return_d

