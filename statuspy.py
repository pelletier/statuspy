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
r = None
if not settings.DEBUG:
    r = redis.Redis(host=settings.REDIS_HOST, db=settings.REDIS_DB)
else:
    r = redis.Redis(host=settings.REDIS_HOST, db=settings.REDIS_DB_DEBUG)

# Create an MD5 hash object, better in case of massive subscription / login
def hash5(string):
    md5 = hashlib.md5()
    md5.update(string)
    return md5.hexdigest()

# Handle the web UI ----------------------------------------------------------
class HomeHandler(tornado.web.RequestHandler):

    def get(self):
        self.write("Hello world")


# API Handling ---------------------------------------------------------------

# --> Base for uniform output (JSON)
def user_exists(f):
    def decorate(self, user_name, *args, **kwargs):
        uid = r.get('username:%s:uid' % user_name)
        if not uid:
            raise tornado.web.HTTPError(404)
        kwargs['uid'] = uid
        return f(self, user_name, *args, **kwargs)
    return decorate

def auth_required(f):
    def decorate(self, user_name, *args, **kwargs):
        uid = r.get('username:%s:uid' % user_name)
        if not uid:
            raise tornado.web.HTTPError(404)
        kwargs['uid'] = uid
        
        passwd = self.request.arguments.get('password', [''])[0]
        if not passwd:
            passwd = urlparse.parse_qs(self.request.body).get('password', '')
        if not passwd:
            raise tornado.web.HTTPError(400)
                
        hashed_password = hash5(passwd)
        real_pass = r.get('uid:%s:password' % uid)
        
        if not real_pass == hashed_password:
            raise tornado.web.HTTPError(401)
                
        return f(self, user_name, *args, **kwargs)
    return decorate
    

class APIBaseHandler(tornado.web.RequestHandler):
    
    def output(self, data):
        mimetype = 'application/json'
        if not data.__class__ == str:
            data = json.dumps(data)
        self.write(data)
        self.set_header("Content-Type", mimetype)


# --> User managmenent
class APIUsersHandler(APIBaseHandler):
    
    # Give informations on either the API (if no user provided) or the
    # user himself.
    def get(self, user_name):
        if not user_name:
            self.output({'statuspy':'Welcome', 'version':API_VERSION})
            return None
        
        uid = r.get('username:%s:uid' % user_name)
        
        if not uid:
            raise tornado.web.HTTPError(404)
        
        data = {}
        data['user_name'] = user_name
        data['uid'] = uid
        data['email'] = r.get('uid:%s:email' % uid)
        
        self.output(data)
    
    # Subscribe a new user
    def post(self, user_name):
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
        if r.get('username:%s:uid' % user_name):
            raise tornado.web.HTTPError(409)
        
        # Hash the password
        hashed_password = hash5(password)
        
        # Let's inscrement the global user id to get a new one
        uid = r.incr('global:nextUserId')
        
        r.set('username:%s:uid' % user_name, uid)
        r.set('uid:%s:username' % uid, user_name)
        r.set('uid:%s:password' % uid, hashed_password)
        r.set('uid:%s:email' % uid, email)
        
        self.output({'uid': uid})


# --> Followers management
class APIFollowersHandler(APIBaseHandler):
    
    # Returns the list of the persons who follow the given user
    @user_exists
    def get(self, user_name, follower_name, action, **kwargs):
        if follower_name:
            raise tornado.web.HTTPError(405)
        uid = kwargs['uid']
        followers = r.smembers('uid:%s:followers' % uid)
        data = []
        for fol_id in followers:
            data.append(r.get('uid:%s:username' % fol_id))
        self.output({'followers': data})
    

# --> Following management
class APIFollowingHandler(APIBaseHandler):
    
    # Dispatch the GET requests
    def get(self, user_name, following_name, action, **kwargs):
        if action == 'delete':
            return self.stop_following(user_name, following_name, action, **kwargs)
        if not action:
            return self.followed_list(user_name, following_name, action, **kwargs)
    
    # Display the list of the followed persons
    @user_exists
    def followed_list(self, user_name, following_name, action, *args, **kwargs):
        if action or following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        
        following = r.smembers('uid:%s:following' % uid)
        data = []
        for fol_id in following:
            data.append(r.get('uid:%s:username' % fol_id))
        
        self.write({'following': data})
    
    # Start following someone
    @auth_required
    def post(self, user_name, following_name, action, **kwargs):
        if action or following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        try:
            follow_name = self.request.arguments['user_name'][0]
        except KeyError:
            raise tornado.web.HTTPError(400)
        
        follow_uid = r.get('username:%s:uid' % follow_name)
        
        if not follow_uid:
            self.output({'error': 'user to follow does not exist'})
            raise tornado.web.HTTPError(400)
        
        r.sadd('uid:%s:followers' % follow_uid, uid)
        r.sadd('uid:%s:following' % uid, follow_uid)
    
    # Stop following someone
    @auth_required
    def stop_following(self, user_name, following_name, *args, **kwargs):
        if not following_name:
            raise tornado.web.HTTPError(405)
        
        uid = kwargs['uid']
        
        following_id = r.get('username:%s:uid' % following_name)
        res = r.srem('uid:%s:following' % uid, following_id)
        
        self.write({'done': bool(res)})
    

# Tornado application
application = tornado.web.Application([
        (r"/", HomeHandler),
        (r"/%s/([\w\d_-]*)" % API_VERSION, APIUsersHandler),
        (r"/%s/([\w\d_-]+)/followers/([\w\d_-]*)/?([\w]*)" % API_VERSION, APIFollowersHandler),
        (r"/%s/([\w\d_-]+)/following/([\w\d_-]*)/?([\w]*)" % API_VERSION, APIFollowingHandler),
    ],
    autoreload=True)


# Run instruction (easy start from command line)
def run():
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    run()
