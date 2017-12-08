from contextlib import contextmanager
from boto import connect_s3
import time
from flask import current_app


@contextmanager
def log_duration(name="Unnamed action"):
    """Context manager for executing code and logging the duration.

    """
    start_t = time.time()
    yield
    end_t = time.time()
    msg = "Executed [{}] in {:.2f} ms".format(name, (end_t-start_t)*1000)
    current_app.logger.info(msg)


def get_s3_conn(host):
    """Get a connection to a given storage host based on configuration in the
    current app context.
    """
    config = current_app.config["STORAGE"]["s3"]
    return connect_s3(config["keys"][host]["access_key"],
                      config["keys"][host]["secret_key"],
                      **config["kwargs"][host])
