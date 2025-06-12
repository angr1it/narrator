import os
import pytest

os.environ.setdefault("OPENAI_API_KEY", "x")
os.environ.setdefault("NEO4J_URI", "bolt://example.com")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "pass")
os.environ.setdefault("NEO4J_DB", "neo4j")
os.environ.setdefault("WEAVIATE_URL", "http://localhost")
os.environ.setdefault("WEAVIATE_API_KEY", "x")
os.environ.setdefault("WEAVIATE_INDEX", "idx")
os.environ.setdefault("WEAVIATE_CLASS_NAME", "cls")
os.environ.setdefault("AUTH_TOKEN", "x")

import config.langfuse as langfuse_module


class DummySpan:
    def __init__(self, events):
        self.events = events

    def end(self):
        self.events.append("end")


class DummyClient:
    def __init__(self, events):
        self.events = events

    def span(self, name: str):
        self.events.append(name)
        return DummySpan(self.events)
