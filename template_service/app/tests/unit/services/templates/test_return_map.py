"""Tests for TemplateService._get_return_map behaviour.

These unit tests check that return map extraction works correctly when
retrieving objects from Weaviate query results.
"""

import uuid
from services.templates import TemplateService


class DummyObj:
    def __init__(self, props, uid=None):
        self.properties = props
        self.uuid = uid or str(uuid.uuid4())

        class M:
            distance = 0.0

        self.metadata = M()


class DummyQuery:
    def __init__(self, obj):
        self.obj = obj

    def fetch_object_by_id(self, id):
        return self.obj


class DummyCollection:
    def __init__(self, obj):
        self.query = DummyQuery(obj)


class DummyClient:
    def __init__(self, obj):
        self.coll = DummyCollection(obj)

        class C:
            def __init__(self, outer):
                self.outer = outer

            def exists(self, name):
                return True

            def create(self, **kwargs):
                pass

            def get(self, name):
                return self.outer.coll

        self.collections = C(self)


class TestService(TemplateService):
    def _ensure_schema(self) -> None:
        pass


def test_get_includes_return_map():
    """``TemplateService.get`` should populate the ``return_map`` field."""
    obj = DummyObj(
        {
            "name": "t",
            "title": "T",
            "description": "D",
            "slots": {},
            "extract_cypher": "c.j2",
            "return_map": {"a": "b"},
        }
    )
    svc = TestService(weaviate_client=DummyClient(obj), embedder=lambda x: [])
    tpl = svc.get("id1")
    assert tpl.return_map == {"a": "b"}
