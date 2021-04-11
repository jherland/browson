from collections.abc import MutableSequence
from contextlib import contextmanager
from functools import wraps
import logging
import signal
from time import monotonic as now

logger = logging.getLogger(__name__)


def clamp(val, minimum, maximum):
    assert maximum >= minimum
    return minimum if val < minimum else maximum if val > maximum else val


def debug_time(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            t = now()
            return f(*args, **kwargs)
        finally:
            logger.debug(f"{f.__name__} took {now() - t}s")

    return wrapper


@contextmanager
def signal_handler(signalnum, handler):
    """Install the given signal handler for the duration of this context."""

    def wrapped_handler(signum, frame):
        logger.debug(f"signal handler invoked with {signum}, {frame}")
        handler()

    prev = signal.signal(signalnum, wrapped_handler)
    try:
        yield
    finally:
        signal.signal(signalnum, prev)
