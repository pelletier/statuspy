========
Statuspy
========

Web API
=======


Implemented URIs
----------------

You must prepend /api_version/ to all URIs. The version described here is 1.0.
URIs marked with a * must be used by an authenticated user.
The user name used for authentication is `user_name`. The password must be
provided in the `password` request argument.

``/`` - GET
    Returns a JSON-encoded welcome message.   

``/`` - POST
    Create a new user. You must provide:
        - user_name
        - password
        - email

``/user_name/`` - GET
    Returns a JSON-encoded hash containing the keys:    
        - user_name
        - email
        - uid

``/user_name/followers/`` - GET
    Returns a JSON-encoded list of user names, in a hash with containing a
    single key: followers.   

``/user_name/following/`` - GET
    Returns a JSON-encoded list of users who user_name follows.  

``/user_name/following/`` - POST *
    Start to follow a user. You must provide the following payload:
        - user_name

``/user_name/following/other_user/delete`` - GET *
    user_name stops following other_user.


To be implemented
-----------------

None