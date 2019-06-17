import os
from boto.s3.connection import OrdinaryCallingFormat
from os import environ as env

# IndexClient
INDEX_CLIENT = {
   'host': env.get('INDEX_CLIENT_HOST', 'http://localhost:8888'),
   'version': 'v0',
   'auth': None}

# Auth
AUTH = 'https://gdc-portal.nci.nih.gov/auth/keystone/v3/'
INTERNAL_AUTH = env.get('INTERNAL_AUTH', 'https://gdc-portal.nci.nih.gov/auth/')

AUTH_ADMIN_CREDS = {
    'domain_name': env.get('KEYSTONE_DOMAIN'),
    'username': env.get('KEYSTONE_USER'),
    'password': env.get('KEYSTONE_PASSWORD'),
    'auth_url': env.get('KEYSTONE_AUTH_URL'),
    'user_domain_name': env.get('KEYSTONE_DOMAIN')}

# Storage
CLEVERSAFE_HOST = env.get('CLEVERSAFE_HOST', 'cleversafe.service.consul')

STORAGE = {"s3": {
    "keys": {
        "cleversafe.service.consul": {
            "access_key": os.environ.get('CLEVERSAFE_ACCESS_KEY'),
            'secret_key': os.environ.get('CLEVERSAFE_SECRET_KEY')},
        "localhost": {
            "access_key": os.environ.get('CLEVERSAFE_ACCESS_KEY'),
            'secret_key': os.environ.get('CLEVERSAFE_SECRET_KEY')},
    }, "kwargs": {
        'cleversafe.service.consul': {
            'host': 'cleversafe.service.consul',
            "is_secure": False,
            "calling_format": OrdinaryCallingFormat()},
        'localhost': {
            'host': 'localhost',
            "is_secure": False,
            "calling_format": OrdinaryCallingFormat()},
    }}}
SUBMISSION = {
    "bucket": 'test_submission',
    "host": CLEVERSAFE_HOST,
}
# Postgres
PSQLGRAPH = {
    'host': os.getenv("GDC_PG_HOST", "localhost"),
    'user': os.getenv("GDC_PG_USER", "test"),
    'password': os.getenv("GDC_PG_PASSWORD", "test"),
    'database': os.getenv("GDC_PG_DBNAME", "automated_test")
}

# API server
PEREGRINE_HOST = os.getenv("PEREGRINE_HOST", "localhost")
PEREGRINE_PORT = int(os.getenv("PEREGRINE_PORT", "5000"))

# FLASK_SECRET_KEY should be set to a secure random string with an appropriate
# length; 50 is reasonable. For the random generation to be secure, use
# ``random.SystemRandom()``
FLASK_SECRET_KEY = 'eCKJOOw3uQBR5pVDz3WIvYk3RsjORYoPRdzSUNJIeUEkm1Uvtq'

DICTIONARY_URL = os.environ.get('DICTIONARY_URL','https://s3.amazonaws.com/dictionary-artifacts/datadictionary/develop/schema.json')

HMAC_ENCRYPTION_KEY = os.environ.get('CDIS_HMAC_ENCRYPTION_KEY', '')
OAUTH2 = {
    "client_id": os.environ.get('CDIS_PEREGRINE_CLIENT_ID'),
    "client_secret": os.environ.get("CDIS_PEREGRINE_CLIENT_SECRET"),
    "oauth_provider": os.environ.get("CDIS_USER_API_OAUTH", 'http://localhost:8000/oauth2/'),
    "redirect_uri": os.environ.get("CDIS_PEREGRINE_OAUTH_REDIRECT", 'localhost:5000/v0/oauth2/authorize'),
}

USER_API = "http://localhost:8000/"
SESSION_COOKIE_NAME = 'PEREGRINE_session'
# verify project existence in dbgap or not
VERIFY_PROJECT = False
AUTH_SUBMISSION_LIST = False
USE_LAZY_TRAVERSE = True
