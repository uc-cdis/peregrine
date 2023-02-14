from contextlib import contextmanager
import time
from flask import current_app


@contextmanager
def log_duration(name="Unnamed action"):
    """Context manager for executing code and logging the duration."""
    start_t = time.time()
    yield
    end_t = time.time()
    msg = "Executed [{}] in {:.2f} ms".format(name, (end_t - start_t) * 1000)
    current_app.logger.info(msg)
