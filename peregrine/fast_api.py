import os
import sys
import time
import logging
from importlib.metadata import version as importlib_version

from fastapi import FastAPI, HTTPException, APIRouter, Request
from fastapi.concurrency import asynccontextmanager
from psqlgraph import PsqlGraphDriver

from authutils import AuthError
import datamodelutils
from dictionaryutils import DataDictionary, dictionary as dict_init
from cdispyutils.log import get_handler
from cdispyutils.uwsgi import setup_user_harakiri
from gen3authz.client.arborist.client import ArboristClient

import peregrine
from peregrine import dictionary
from peregrine.routes import router as submission_router
from peregrine.routes.datasets import router as datasets_router
from peregrine.routes.coremetadata import router as coremetadata_router
from peregrine.routes import datasets, coremetadata
from .errors import APIError, setup_default_handlers, UnhealthyCheck
from .resources import submission
from .version_data import VERSION, COMMIT

# recursion depth is increased for complex graph traversals
sys.setrecursionlimit(10000)
DEFAULT_ASYNC_WORKERS = 8


def build_v0_router() -> APIRouter:
    v0 = APIRouter(prefix="/v0")

    v0.include_router(submission_router, prefix="/submission", tags=["submission"])
    v0.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
    v0.include_router(
        coremetadata_router, prefix="/coremetadata", tags=["coremetadata"]
    )

    return v0


def build_legacy_router() -> APIRouter:
    legacy_route_aggregator = APIRouter(deprecated=True)

    # Re-mount the same routers at root-level paths
    legacy_route_aggregator.include_router(
        submission_router, prefix="/submission", tags=["submission"], deprecated=True
    )
    legacy_route_aggregator.include_router(
        datasets_router, prefix="/datasets", tags=["datasets"], deprecated=True
    )
    legacy_route_aggregator.include_router(
        coremetadata_router,
        prefix="/coremetadata",
        tags=["coremetadata"],
        deprecated=True,
    )

    return legacy_route_aggregator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Parse the configuration, setup and instantiate necessary classes.

    This is FastAPI's way of dealing with startup logic before the app
    starts receiving requests.

    https://fastapi.tiangolo.com/advanced/events/#lifespan

    Args:
        app (fastapi.FastAPI): The FastAPI app object
    """
    # startup

    # Dictionary init
    # Db
    # Asyncpool
    # Cors init

    yield

    # teardown


def get_app():
    app = FastAPI(lifespan=lifespan)

    app.include_router(build_v0_router())
    app.include_router(
        build_legacy_router()
    )  # Deprecated: Must be removed in future releases around March/April 2026

    submission.graphql.make_graph_traversal_dict(app)
    app.state.graphql_schema = submission.graphql.get_schema()
    app.state.schema_file = submission.generate_schema_file(
        app.state.graphql_schema, app.logger
    )
    return app


app = get_app()


def get_app_context(request: Request):
    return request.app.state


def get_request_state(request: Request):
    return request.state
