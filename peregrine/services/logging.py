import datetime

from flask import jsonify

from gdcapi import utils
from gdcapi.esutils import search as repo
from gdcapi.esutils.request import sanitize


def log_entity(entity, req, pid=None):
    base = {"entity": entity, "date": datetime.datetime.now()}
    if "User-Agent" in req.headers:
        base["user_agent"] = req.headers["User-Agent"]
    if pid:
        base['id'] = pid
    repo.log_entity(utils.merge(base, req.args.to_dict()))


def log_error(request):
    allowed = ("event_id", "url", "exception", "cause", "user", "date")
    e = {k: request.json[k] for k in allowed if k in request.json}
    e['headers'] = {k: v for (k, v) in request.headers}
    repo.log_error(e)
