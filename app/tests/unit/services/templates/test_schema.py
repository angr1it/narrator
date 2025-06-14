"""Tests for schema creation logic in :class:`TemplateService`.

The dummy client emulates Weaviate to verify that the service creates the
collection only when needed and with the expected properties.
"""

import pytest
from services.templates import TemplateService
from weaviate.classes.config import Property


class DummyClient:
    def __init__(self, exists: bool = False):
        self.created = None
        self.exists = exists

        class CollMgr:
            def __init__(self, outer):
                self.outer = outer

            def exists(self, name):
                return self.outer.exists

            def create(self, **kwargs):
                self.outer.created = kwargs

            def get(self, name):
                return None

        self.collections = CollMgr(self)


def test_ensure_schema_creates_collection():
    """Collection should be created with required properties."""
    client = DummyClient()
    TemplateService(weaviate_client=client, embedder=lambda x: [])
    props = client.created["properties"]
    assert any(isinstance(p, Property) and p.name == "name" for p in props)
    assert any(isinstance(p, Property) and p.name == "supports_augment" for p in props)
    assert any(isinstance(p, Property) and p.name == "supports_extract" for p in props)


def test_ensure_schema_skips_if_exists():
    """Service should not attempt creation if collection exists."""
    client = DummyClient(exists=True)
    TemplateService(weaviate_client=client, embedder=lambda x: [])
    assert client.created is None
