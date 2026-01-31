import flask
from fastapi import APIRouter

blueprint = flask.Blueprint("graphql", "submission_v0")
router = APIRouter()
