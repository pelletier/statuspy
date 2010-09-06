"""
Statuspy is a simple Twitter clone using Python, Tornado and Redis.
It is an *experiment*!
"""

import json
import hashlib
import urlparse
import redis
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings


API_VERSION = settings.API_VERSION # Fort shortcut (see app)

# Create a pooled connection right now, so we don't waste time connecting 
# sockets on the run.
R = None
if not settings.DEBUG:
    R = redis.Redis(host=settings.REDIS_HOST, db=settings.REDIS_DB)
else:
    R = redis.Redis(host=settings.REDIS_HOST, db=settings.REDIS_DB_DEBUG)

def hash5(string):
    """
    Create an MD5 hash object, better in case of massive subscription / login
    """
    md5 = hashlib.md5()
    md5.update(string)
    return md5.hexdigest()

# Handle the web UI ----------------------------------------------------------
class HomeHandler(tornado.web.RequestHandler):
    """
    Handle the web UI
    """

    def get(self):
        self.write("Hello world")


# API Handling ---------------------------------------------------------------

# --> Base for uniform output (JSON)
def user_exists(func):
    """
    Check if the user exists and add its UID to the kwargs.
    """
    
    def decorate(self, user_name, *args, **kwargs):
        """Decorate"""
        
        uid = R.get('username:%s:uid' % user_name)
        if not uid:
            raise tornado.web.HTTPError(404)
        kwargs['uid'] = uid
        return func(self, user_name, *args, **kwargs)

    return decorate

def auth_required(func):
    """
    Check the user credentials using the plain-text method
    """
    
    def decorate(self, user_name, *args, **kwargs):
        """Decorate"""
        
        uid = R.get('username:%s:uid' % user_name)
        if not uid:
            raise tornado.web.HTTPError(404)
        kwargs['uid'] = uid
        
        passwd = self.request.arguments.get('password', [''])[0]
        if not passwd:
            passwd = urlparse.parse_qs(self.request.body).get('password', '')
        if not passwd:
            raise tornado.web.HTTPError(400)
                
        hashed_password = hash5(passwd)
        real_pass = R.get('uid:%s:password' % uid)
        
        if not real_pass == hashed_password:
            raise tornado.web.HTTPError(401)
                
        return func(self, user_name, *args, **kwargs)
    
    return decorate
    

class APIBaseHandler(tornado.web.RequestHandler):
    """
    Base of all API handlers
    """
    
    def output(self, data):
        """
        Encode the output using JSON, if needed. Also update the content-type.
        """
        mimetype = 'application/json'
        if not data.__class__ == str:
            data = json.dumps(data)
        self.write(data)
        self.set_header("Content-Type", mimetype)


# --> User managmenent
class APIUsersHandler(APIBaseHandler):
    """
    Handle users
    """
    
    def get(self, user_name):
        """
        Give informations on either the API (if no user provided) or the user
        himself.
        """
        
        if not user_name:
            self.output({'statuspy':'Welcome', 'version':API_VERSION})
            return None
        
        uid = R.get('username:%s:uid' % user_name)
        
        if not uid:
            raise tornado.web.HTTPError(404)
        
        data = {}
        data['user_name'] = user_name
        data['uid'] = uid
        data['email'] = R.get('uid:%s:email' % uid)
        
        self.output(data)
    
    def post(self, user_name):
        """
        Subscribe a new user
        """
        
        if user_name:
            raise tornado.web.HTTPError(405)
        
        # Gather needed data
        try:
            user_name = self.request.arguments['user_name'][0]
            password = self.request.arguments['password'][0]
            email = self.request.arguments['email'][0]
        except KeyError:
            raise tornado.web.HTTPError(400)
        
        # Check if user name does not already exists
        if R.get('username:%s:uid' % user_name):
            raise tornado.web.HTTPError(409)
        
        # Hash the password
        hashed_password = hash5(password)
        
        # Let's inscrement the global user id to get a new one
        uid = R.incr('global:nextUserId')
        
        R.set('username:%s:uid' % user_name, uid)
        R.set('uid:%s:username' % uid, user_name)
        R.set('uid:%s:password' % uid, hashed_password)
        R.set('uid:%s:email' % uid, email)
        
        self.output({'uid': uid})


# --> Followers management
class APIFollowersHandler(APIBaseHandler):
    """
    Followers management
    """
    
    @user_exists
    def get(self, user_name, follower_name, action, **kwargs):
        """
        Returns the list of the persons who follow the given user.
        """
        if not user_name:
            raise tornado.web.HTTPError(405)
        
        if follower_name or action:
            raise tornado.web.HTTPError(405)
        uid = kwargs['uid']
        followers = R.smembers('uid:%s:followers' % uid)
        data = []
        for fol_id in followers:
            data.append(R.get('uid:%s:username' % fol_id))
        self.output({'followers': data})
    

# --> Following management
class APIFollowingHandler(APIBaseHandler):
    """
    Following management
    """
    
    def get(self, user_name, following_name, action, **kwargs):
        """
        Dispatch the GET requests
        """
        if action == 'delete':
            return self.stop_following(user_name, following_name, action, \
                                                                     **kwargs)
        if not action:
            return self.followed_list(user_name, following_name, action, \
                                                                     **kwargs)
    
    @user_exists
    def followed_list(self, user_name, following_name, action, *args, **kwargs):
        """
        Display the list of the followed persons.
        """
        
        if action or following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        
        following = R.smembers('uid:%s:following' % uid)
        data = []
        for fol_id in following:
            data.append(R.get('uid:%s:username' % fol_id))
        
        self.write({'following': data})
    
    
    @auth_required
    def post(self, user_name, following_name, action, **kwargs):
        """
        Start following someone
        """
        if action or following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        try:
            follow_name = self.request.arguments['user_name'][0]
        except KeyError:
            raise tornado.web.HTTPError(400)
        
        follow_uid = R.get('username:%s:uid' % follow_name)
        
        if not follow_uid:
            self.output({'error': 'user to follow does not exist'})
            raise tornado.web.HTTPError(400)
        
        R.sadd('uid:%s:followers' % follow_uid, uid)
        R.sadd('uid:%s:following' % uid, follow_uid)
    
    
    @auth_required
    def stop_following(self, user_name, following_name, *args, **kwargs):
        """
        Stop following someone
        """
        if not following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        
        following_id = R.get('username:%s:uid' % following_name)
        res = R.srem('uid:%s:following' % uid, following_id)
        
        self.write({'done': bool(res)})
    

# Tornado application
APPLICATION = tornado.web.Application([
        (r"/", HomeHandler),
        (r"/%s/([\w\d_-]*)" % API_VERSION, APIUsersHandler),
        (r"/%s/([\w\d_-]+)/followers/([\w\d_-]*)/?([\w]*)"\
                % API_VERSION, APIFollowersHandler),
        (r"/%s/([\w\d_-]+)/following/([\w\d_-]*)/?([\w]*)"\
                % API_VERSION, APIFollowingHandler),
    ],
    autoreload=True)


def run():
    """Run instruction (easy start from command line)"""
    http_server = tornado.httpserver.HTTPServer(APPLICATION)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    run()
