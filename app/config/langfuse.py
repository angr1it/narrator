from __future__ import annotations

from langfuse.callback.langchain import LangchainCallbackHandler
from langfuse.utils.langfuse_singleton import LangfuseSingleton
from langfuse.client import Langfuse

from config import app_settings


def get_client() -> Langfuse:
    """Return a singleton Langfuse client."""
    return LangfuseSingleton().get(
        public_key=app_settings.LANGFUSE_PUBLIC_KEY,
        secret_key=app_settings.LANGFUSE_SECRET_KEY,
        host=app_settings.LANGFUSE_HOST,
    )


def provide_callback_handler_with_tags(
    tags: list[str] = None,
) -> LangchainCallbackHandler:
    if tags is None:
        tags = []
    lf = get_client()
    trace = lf.trace(tags=tags)
    handler = trace.get_langchain_handler()
    return handler
