from __future__ import annotations

from contextlib import contextmanager

from langfuse.utils.langfuse_singleton import LangfuseSingleton
from langfuse.client import StatefulSpanClient


def get_client():
    """Return a singleton Langfuse client."""
    return LangfuseSingleton().get()


@contextmanager
def start_as_current_span(name: str) -> StatefulSpanClient:
    """Create and automatically close a Langfuse span."""
    span = get_client().span(name=name)
    try:
        yield span
    finally:
        span.end()
