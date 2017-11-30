import json
import pytest

import flask
from mock import patch

from .graphql.test_graphql import put_cgci


class MockResponse(object):

    def __init__(self, r):
        self.r = r
        self._data = r.data
        self._json = json.loads(r.data)

    def json(self):
        return self._json

    @property
    def text(self):
        return self._data


def mock_request(userapi_client):
    class Requests(object):
        def post(self, url, data=None, headers={}):
            r = userapi_client.post(url, data=data, headers=headers)
            return MockResponse(r)

        def get(self, url, headers={}):
            r = userapi_client.get(url, headers=headers)
            return MockResponse(r)
    return Requests()


def test_oauth_flow(monkeypatch, app, client, pg_driver, userapi_client):
    assert client.get("/v0/submission/")
    redirect_url = client.get("/v0/oauth2/authorization_url").data
    r = userapi_client.get('/user/')
    print r.data
    r = userapi_client.get(redirect_url.replace('http://localhost', ''))
    assert r.status_code == 302
    code = r.headers['Location'].split("=")[-1]

    mocked_requests = mock_request(userapi_client)
    monkeypatch.setattr('cdis_oauth2client.client.requests', mocked_requests)
    monkeypatch.setattr('cdis_oauth2client.oauth2.requests', mocked_requests)
    r = client.get("/v0/oauth2/authorize?code={}".format(code))
    # Secret key must have been set for the session to work.
    assert isinstance(app.secret_key, str)
    assert 'access_token' in flask.session

    r = put_cgci(client)
    assert r.status_code != 403
    print r.status_code
