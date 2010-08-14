import json
import hashlib
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
md5 = hashlib.md5()


# Handle the web UI ----------------------------------------------------------
class HomeHandler(tornado.web.RequestHandler):

    def get(self):
        self.write("Hello world")


# API Handling ---------------------------------------------------------------

# --> Base for uniform output (JSON)
class APIBaseHandler(tornado.web.RequestHandler):
    
    def write(self, data):
        mimetype = 'application/json'
        if not data.__class__ == str:
            data = json.dumps(data)
        self.__super__.write(data)
        self.set_header("Content-Type", mimetype)

# --> User managmenent
class APIUsersHandler(tornado.web.RequestHandler):
    
    def get(self, user_name):
        if not user_name:
            self.write({'statuspy':'Welcome', 'version':API_VERSION})
            return None
    
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
        
        print password
        
        # Check if user name does not already exists
        if r.get('username:%s:uid' % user_name):
            raise tornado.web.HTTPError(409)
        
        # Hash the password
        md5.update(password)
        hashed_password = md5.hexdigest()
        
        # Let's inscrement the global user id to get a new one
        uid = r.incr('global:nextUserId')
        
        r.set('username:%s:uid' % user_name, uid)
        r.set('uid:%s:username' % uid, user_name)
        r.set('uid:%s:password' % uid, hashed_password)
        r.set('uid:%s:email' % uid, email)
        
        self.write({'uid': uid})


# Tornado application
application = tornado.web.Application([
        (r"/", HomeHandler),
        (r"/%s/([\w\d_-]*)" % API_VERSION, APIUsersHandler),
    ],
    autoreload=True)


# Run instruction (easy start from command line)
def run():
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    run()
