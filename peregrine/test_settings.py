import os
from collections import OrderedDict


SIGNPOST = {
    "host": "http://localhost:8000/", 'version': 'v0',
    "auth": None}
AUTH = 'https://fake_auth_url'
INTERNAL_AUTH = 'https://fake_auth_url'
AUTH_ADMIN_CREDS = {
    'domain_name': 'some_domain',
    'username': 'iama_username',
    'password': 'iama_password',
    'auth_url': 'https://fake_auth_url',
    'user_domain_name': 'some_domain',
}
SUBMISSION = {
    "bucket": 'test_submission',
    "host": 'host',
}
STORAGE = {"s3": {"keys": {}, "kwargs": {}}}
STORAGE["s3"]["keys"]["host"] = {"access_key": "fake",
                                 "secret_key": "sooper_sekrit"}
STORAGE["s3"]["kwargs"]["host"] = {}

PSQLGRAPH = {
    'host': "localhost",
    'user': "test",
    'password': "test",
    'database': "automated_test",
}

GDC_PORTAL_ENDPOINT = 'http://fake_portal_endpoint_for_tests'

PEREGRINE_HOST = "localhost"
PEREGRINE_PORT = "443"

# Slicing settings
SLICING = {
    'host': 'localhost',
    'gencode': 'REPLACEME',
}

FLASK_SECRET_KEY = 'flask_test_key'

from cryptography.fernet import Fernet

HMAC_ENCRYPTION_KEY = Fernet.generate_key()
OAUTH2 = {
    "client_id": "",
    "client_secret": "",
    "oauth_provider": "",
    "redirect_uri": "",
}

DICTIONARY_URL = os.environ.get('DICTIONARY_URL','https://s3.amazonaws.com/dictionary-artifacts/datadictionary/develop/schema.json')

USER_API = "http://localhost"
# used by fence.jwt.token.generate_signed_access_token for iss
BASE_URL = "http://localhost"

VERIFY_PROJECT = False
AUTH_SUBMISSION_LIST = False

JWT_KEYPAIR_FILES = OrderedDict([
    (
        'key-test',
        ('resources/keys/test_public_key.pem', 'resources/keys/test_private_key.pem'),
    )
])
