from os import path

API_VERSION = '1.0'
REDIS_HOST = '127.0.0.1'
REDIS_DB = 0
REDIS_DB_DEBUG = 1
DEBUG = True

ROOT_PATH = path.dirname(path.abspath(__file__))
STATIC_PATH = path.join(ROOT_PATH, "static")
TEMPLATES_PATH = path.join(ROOT_PATH, "templates")
COOKIE_SECRET = "edv6&87*6=n!h5j$0x!(-@@bpc=wbs(zm$wo2sv$a65#jwc&8c"
