from collections.abc import MutableSequence
from contextlib import contextmanager
from functools import wraps
from itertools import islice
import logging
import signal
import sys
from time import monotonic as now
from typing import Iterator, List, Optional, TypeVar

logger = logging.getLogger(__name__)

Item = TypeVar("Item")


def clamp(val, minimum, maximum):
    assert maximum >= minimum
    return minimum if val < minimum else maximum if val > maximum else val


def debug_time(f):
    """Decorator to produce debug log messages with function run times."""

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


class LazyList(MutableSequence):
    """A list interface to an iterator, that extract elements on-demand.

    The behavior of this list is probably not completely well-defined: Some
    operations behave as if this is a "regular" list of the elements that have
    been extracted so far (e.g. len(ll) or negative indexing: ll[-1]), whereas
    others will cause the list to "magically" grow by extracting elements from
    the iterator
    - Accessing elements beyond of the end of .realized (i.e. ll[x] where
      x >= len(ll))
    - TODO: ???
    """

    def __init__(self, iterator: Optional[Iterator[Item]] = None):
        self.iterator: Optional[Iterator[Item]] = iterator
        self.realized: List[Item] = []

    def __repr__(self) -> str:
        return f"{self.realized}/{self.iterator}"

    def __eq__(self, other: "LazyList") -> bool:
        return self.realized == other

    def __len__(self) -> int:
        return len(self.realized)  # this is a lie

    def _extract_until_len(self, n) -> None:
        if n > len(self.realized) and self.iterator is not None:
            self.realized.extend(islice(self.iterator, n - len(self.realized)))

    @debug_time
    def real_length(self):
        self._extract_until_len(sys.maxsize)
        return len(self.realized)

    def __getitem__(self, i):
        if isinstance(i, slice):
            # Extract until end-of-slice
            end = sys.maxsize if i.stop is None else i.stop
        else:
            end = i + 1
        self._extract_until_len(end)
        return self.realized.__getitem__(i)

    def __delitem__(self, i):
        return self.realized.__delitem__(i)

    def __setitem__(self, i, value):
        # We're replacing an item (or a slice of items). We must extract items
        # up to and including the one(s) that are replaced.
        if isinstance(i, slice):
            if i.stop is None:  # Exhaust the entire generator
                # TODO: Is this safe, or must we consider side effects???
                self.iterator = None
            else:
                self._extract_until_len(i.stop)
        else:
            self._extract_until_len(i + 1)
        return self.realized.__setitem__(i, value)

    def insert(self, i, value):
        return self.realized.insert(i, value)
