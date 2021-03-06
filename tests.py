import json
from urllib import urlencode
import redis
from tornado.testing import *
import statuspy
import settings
from settings import API_VERSION

settings.DEBUG = True

# We go on fresh tests
r = redis.Redis(host=settings.REDIS_HOST, db=settings.REDIS_DB_DEBUG)
r.flushdb()


class APIUsersTest(AsyncHTTPTestCase):
    
    def get_app(self):
        return statuspy.APPLICATION
    
    
    def test_api_version(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, '{"version": "%s", "statuspy": "Welcome"}' % API_VERSION)
    
    def test_post_with_user_name(self):
        self.http_client.fetch(self.get_url('/%s/foo' % API_VERSION),\
                               self.stop, method="POST", body='')
        response = self.wait()
        self.assertEqual(response.code, 405)
    
    def test_post_missing_arg(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),\
                               self.stop, method="POST",\
                               body='user_name=bob')
        response = self.wait()
        self.assertEqual(response.code, 400)
    
    def test_post_full_args(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=bob&password=alice&email=aaa@example.com')
        response = self.wait()
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data.get('uid'))
    
    def test_post_already_exists(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=guy&password=yeah&email=bbb@example.com')
        response = self.wait()
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=guy&password=yeah&email=bbb@example.com')
        response = self.wait()
        self.assertEqual(response.code, 409)
    
    def test_get_info_user(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=albert&password=yeah&email=bbb@example.com')
        response = self.wait()

        self.http_client.fetch(self.get_url('/%s/%s' % (API_VERSION, 'albert')),
                               self.stop, method='GET')
        response = self.wait()
        data = json.loads(response.body)
        self.assertEquals(response.code, 200)
        self.assertEquals(data['user_name'], 'albert')
        self.assertEquals(data['email'], 'bbb@example.com')
        self.assertTrue(int(data['uid']).__class__ == int)
    
    def test_get_followers(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=aaa&password=yeah&email=bbb@example.com')
        response = self.wait()

        # Let's create another user
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION),
                               self.stop, method='POST',\
                               body='user_name=bbb&password=yeah&email=bbb@example.com')
        response = self.wait()
        self.assertEqual(response.code, 200)

        # The second user will now follow da first one
        self.http_client.fetch(self.get_url('/%s/bbb/following/' % API_VERSION),
                           self.stop, method='POST', body='user_name=aaa&password=yeah')
        response = self.wait()
        self.assertEqual(response.code, 200)
        # So bbb now follows aaa.
        
        self.http_client.fetch(self.get_url('/%s/aaa/followers/' % API_VERSION),
                               self.stop, method='GET'),
        response = self.wait()
        data = json.loads(response.body)
        self.assertEqual(response.code, 200)
        self.assertEqual(data['followers'], ['bbb'])
        
        self.http_client.fetch(self.get_url('/%s/bbb/following/' % API_VERSION),
                               self.stop, method='GET'),
        response = self.wait()
        data = json.loads(response.body)
        self.assertEqual(response.code, 200)
        self.assertEqual(data['following'], ['aaa'])
        
        # Now we want bbb to stop following aaa
        body = urlencode({'password': 'yeah'})
        self.http_client.fetch(self.get_url('/%s/bbb/following/aaa/delete?%s' % (API_VERSION, body)),
                               self.stop, method='GET')
        response = self.wait()
        data = json.loads(response.body)
        self.assertEqual(response.code, 200)
        self.assertEqual(data["done"], True)
