import unittest
import restkit
from tornado.testing import *
import statuspy
from settings import API_VERSION


class APIUsersTest(AsyncHTTPTestCase):

    def get_app(self):
        return statuspy.application

    def test_api_version(self):
        self.http_client.fetch(self.get_url('/%s/' % API_VERSION), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, '{"version": "%s", "statuspy": "Welcome"}' % API_VERSION)

    def test_post_with_user_name(self):
        self.http_client.fetch(self.get_url('/%s/foo' % API_VERSION), self.stop, method="POST", body='')
        response = self.wait()
        self.assertEqual(response.code, 405)
