#    Copyright (C) 2011-2013 University of Southampton
#    Copyright (C) 2011-2013 Daniel Alexander Smith
#    Copyright (C) 2011-2013 Max Van Kleek
#    Copyright (C) 2011-2013 Nigel R. Shadbolt
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

from zope.interface import Interface, Attribute, implements

class ISession(Interface):
    is_authenticated = Attribute("A bool which registers if a user has successfully authenticated.")
    username = Attribute("Username of the authenticated user.")
    password = Attribute("Password of the authenticated user.")    
    openid_session = Attribute("OpenID Session")
    openid_redirect = Attribute("OpenID Redirect URL")
    limit_boxes = Attribute("Limit Auth to Boxes")

class INDXSession(object):
    """ Stored per user session to record if the user is authenticated etc. """
    implements(ISession)

    def __init__(self, session, webserver):
        self.reset()

    def reset(self):
        self.is_authenticated = False
        self.username = None
        self.password = None
        self.usertype = None
        self.openid_session = {}
        self.openid_redirect = None
        self.limit_boxes = None

    def setAuthenticated(self, val):
        self.is_authenticated = val
   
    def setUser(self, username):
        self.username = username

    def setPassword(self, password):
        self.password = password

    def setUserType(self, usertype):
        self.usertype = usertype

    def get_openid_session(self):
        return self.openid_session

    # redirects for openid authentication
    def set_openid_redirect(self, redirect):
        self.openid_redirect = redirect
    def get_openid_redirect(self):
        return self.openid_redirect

