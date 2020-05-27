import os
import sys
import time
import logging
import pkg_resources
import importlib

from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy_session import flask_scoped_session
from psqlgraph import PsqlGraphDriver

from authutils import AuthError
import datamodelutils
from dictionaryutils import DataDictionary, dictionary as dict_init
from cdispyutils.log import get_handler
from cdispyutils.uwsgi import setup_user_harakiri
from gen3authz.client.arborist.client import ArboristClient

import peregrine
from peregrine import dictionary
from peregrine.blueprints import datasets
from .errors import APIError, setup_default_handlers, UnhealthyCheck
from .resources import submission
from .version_data import VERSION, COMMIT


# recursion depth is increased for complex graph traversals
sys.setrecursionlimit(10000)
DEFAULT_ASYNC_WORKERS = 8


def app_register_blueprints(app):
    # TODO: (jsm) deprecate the index endpoints on the root path,
    # these are currently duplicated under /index (the ultimate
    # path) for migration
    v0 = "/v0"
    app.url_map.strict_slashes = False

    app.register_blueprint(
        peregrine.blueprints.blueprint, url_prefix=v0 + "/submission"
    )
    app.register_blueprint(datasets.blueprint, url_prefix=v0 + "/datasets")


def app_register_duplicate_blueprints(app):
    # TODO: (jsm) deprecate this v0 version under root endpoint.  This
    # root endpoint duplicates /v0 to allow gradual client migration
    app.register_blueprint(peregrine.blueprints.blueprint, url_prefix="/submission")
    app.register_blueprint(datasets.blueprint, url_prefix="/datasets")


def async_pool_init(app):
    """Create and start an pool of workers for async tasks."""
    n_async_workers = app.config.get("ASYNC", {}).get(
        "N_WORKERS", DEFAULT_ASYNC_WORKERS
    )
    app.async_pool = peregrine.utils.scheduling.AsyncPool()
    app.async_pool.start(n_async_workers)


def db_init(app):
    app.logger.info("Initializing PsqlGraph driver")
    app.db = PsqlGraphDriver(
        host=app.config["PSQLGRAPH"]["host"],
        user=app.config["PSQLGRAPH"]["user"],
        password=app.config["PSQLGRAPH"]["password"],
        database=app.config["PSQLGRAPH"]["database"],
        set_flush_timestamps=True,
    )


# Set CORS options on app configuration
def cors_init(app):
    accepted_headers = [
        "Content-Type",
        "X-Requested-With",
        "X-CSRFToken",
    ]
    CORS(
        app,
        resources={r"/*": {"origins": "*"},},
        headers=accepted_headers,
        expose_headers=["Content-Disposition"],
    )


def dictionary_init(app):
    start = time.time()
    if "DICTIONARY_URL" in app.config:
        app.logger.info("Initializing dictionary from url")
        url = app.config["DICTIONARY_URL"]
        d = DataDictionary(url=url)
        dict_init.init(d)
    elif "PATH_TO_SCHEMA_DIR" in app.config:
        app.logger.info("Initializing dictionary from schema dir")
        d = DataDictionary(root_dir=app.config["PATH_TO_SCHEMA_DIR"])
        dict_init.init(d)
    else:
        app.logger.info("Initializing dictionary from gdcdictionary")
        import gdcdictionary

        d = gdcdictionary.gdcdictionary
    dictionary.init(d)
    from gdcdatamodel import models as md
    from gdcdatamodel import validators as vd

    datamodelutils.validators.init(vd)
    datamodelutils.models.init(md)

    end = int(round(time.time() - start))
    app.logger.info("Initialized dictionary in {} sec".format(end))


def app_init(app):
    app.logger.setLevel(logging.INFO)

    # Register duplicates only at runtime
    app.logger.info("Initializing app")
    dictionary_init(app)

    if app.config.get("USE_USER_HARAKIRI", True):
        setup_user_harakiri(app)

    app_register_blueprints(app)
    app_register_duplicate_blueprints(app)

    db_init(app)
    # exclude es init as it's not used yet
    # es_init(app)
    cors_init(app)
    submission.graphql.make_graph_traversal_dict(app)
    app.graphql_schema = submission.graphql.get_schema()
    app.schema_file = submission.generate_schema_file(app.graphql_schema, app.logger)
    try:
        app.secret_key = app.config["FLASK_SECRET_KEY"]
    except KeyError:
        app.logger.error("Secret key not set in config! Authentication will not work")
    async_pool_init(app)

    # ARBORIST deprecated, replaced by ARBORIST_URL
    arborist_url = os.environ.get("ARBORIST_URL", os.environ.get("ARBORIST"))
    if arborist_url:
        app.auth = ArboristClient(arborist_base_url=arborist_url)
    else:
        app.logger.info("Using default Arborist base URL")
        app.auth = ArboristClient()

    app.node_authz_entity_name = os.environ.get("AUTHZ_ENTITY_NAME", None)
    if app.node_authz_entity_name:
        full_module_name = "datamodelutils.models"
        mymodule = importlib.import_module(full_module_name)
        for i in dir(mymodule):
            if i.lower() == app.node_authz_entity_name.lower():
                attribute = getattr(mymodule, i)
                app.node_authz_entity = attribute
    

    app.logger.info("Initialization complete.")


app = Flask(__name__)

# Setup logger
app.logger.addHandler(get_handler())

setup_default_handlers(app)


@app.route("/_status", methods=["GET"])
def health_check():
    with app.db.session_scope() as session:
        try:
            session.execute("SELECT 1")
        except Exception:
            raise UnhealthyCheck("Unhealthy")

    return "Healthy", 200


@app.route("/_version", methods=["GET"])
def version():
    # dictver['commit'] deprecated; see peregrine#130
    dictver = {
        "version": pkg_resources.get_distribution("gen3dictionary").version,
        "commit": "",
    }
    base = {
        "version": VERSION,
        "commit": COMMIT,
        "dictionary": dictver,
    }

    return jsonify(base), 200


@app.errorhandler(404)
def page_not_found(e):
    return jsonify(message=e.description), e.code


@app.errorhandler(500)
def server_error(e):
    app.logger.exception(e)
    return jsonify(message="internal server error"), 500


def _log_and_jsonify_exception(e):
    """
    Log an exception and return the jsonified version along with the code.

    This is the error handling mechanism for ``APIErrors`` and
    ``OAuth2Errors``.
    """
    app.logger.exception(e)
    if hasattr(e, "json") and e.json:
        return jsonify(**e.json), e.code
    else:
        return jsonify(message=e.message), e.code


app.register_error_handler(APIError, _log_and_jsonify_exception)

app.register_error_handler(peregrine.errors.APIError, _log_and_jsonify_exception)
app.register_error_handler(AuthError, _log_and_jsonify_exception)


def run_for_development(**kwargs):
    app.logger.setLevel(logging.INFO)

    for key in ["http_proxy", "https_proxy"]:
        if os.environ.get(key):
            del os.environ[key]
    app.config.from_object("peregrine.dev_settings")

    kwargs["port"] = app.config["PEREGRINE_PORT"]
    kwargs["host"] = app.config["PEREGRINE_HOST"]

    try:
        app_init(app)
    except:
        app.logger.exception("Couldn't initialize application, continuing anyway")
    app.run(**kwargs)
