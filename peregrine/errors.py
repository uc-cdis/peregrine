from flask import jsonify
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, message, code, json):
        super(APIError, self).__init__(message)
        self.code = code
        self.json = json


class APINotImplemented(APIError):
    def __init__(self, message):
        self.message = message
        self.code = 501


class NotFoundError(APIError):
    def __init__(self, message, code=404, json=None):
        super(NotFoundError, self).__init__(message, code, json)


class UserError(APIError):
    def __init__(self, message, code=400, json={}):
        self.json = json
        self.message = message
        self.code = code


class AuthError(APIError):
    def __init__(self, message=None, code=403):
        self.message = "You don't have access to the data"
        if message:
            self.message += ': {}'.format(message)
        self.code = code


class InvalidTokenError(AuthError):
    def __init__(self):
        self.message = "Your token is invalid or expired, please get a new token from GDC Data Portal"
        self.code = 403


class InternalError(APIError):
    def __init__(self, message=None, code=500):
        self.message = "Internal server error"
        if message:
            self.message += ': {}'.format(message)
        self.code = code


class ServiceUnavailableError(APIError):
    def __init__(self, message, code=503):
        self.message = message
        self.code = code


class UnhealthyCheck(APIError):
    def __init__(self, message):
        self.message = str(message)
        self.code = 500


def make_json_error(ex):
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.code if isinstance(ex, HTTPException) else 500)
    return response


def setup_default_handlers(app):
    for code in default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = make_json_error
