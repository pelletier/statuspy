import json
import redis
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings

API_VERSION = settings.API_VERSION # Fort shortcut (see app)


# Create a pooled connection right now, so we don't waste time connecting 
# sockets on the run.
redis_connection = redis.Redis(host=settings.REDIS_HOST)


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
