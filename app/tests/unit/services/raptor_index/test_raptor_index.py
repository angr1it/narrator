"""Unit tests for the simplified vector index implementation.

They validate centroid computation, schema setup and merge behaviour of
:class:`FlatRaptorIndex` without hitting Weaviate.
"""

import numpy as np
from services.raptor_index import FlatRaptorIndex


class DummyData:
    def __init__(self, parent):
        self.parent = parent

    def insert(self, uuid, properties, vector):
        self.parent.calls.append((uuid, properties, vector))


class DummyCollection:
    def __init__(self):
        self.data = DummyData(self)
        self.calls = []

        class Q:
            def near_vector(self, **kwargs):
                return type("Res", (), {"objects": []})

        self.query = Q()


class DummyClient:
    def __init__(self):
        self.coll = DummyCollection()

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


def fake_embedder(text):
    if text == "text":
        return [1.0, 1.0]
    return [3.0, 3.0]


class TestIndex(FlatRaptorIndex):
    def _ensure_schema(self):
        pass


def test_insert_chunk():
    client = DummyClient()
    idx = TestIndex(client, embedder=fake_embedder, alpha=0.5)
    rid = idx.insert_chunk("text", "fact")
    uuid, props, vec = client.coll.calls[0]
    assert props["centroid"] == [2.0, 2.0]
    assert rid


from weaviate.classes.config import Property


class SchemaClient(DummyClient):
    def __init__(self, exists: bool = False):
        super().__init__()
        self.created = None
        self.exists_flag = exists

        class C:
            def __init__(self, outer):
                self.outer = outer

            def exists(self, name):
                return self.outer.exists_flag

            def create(self, **kwargs):
                self.outer.created = kwargs

            def get(self, name):
                return self.outer.coll

        self.collections = C(self)


def test_ensure_schema_creates_collection():
    client = SchemaClient()
    FlatRaptorIndex(client, embedder=fake_embedder)
    props = client.created["properties"]
    assert any(isinstance(p, Property) and p.name == "text_vec" for p in props)


def test_ensure_schema_skips_if_exists():
    client = SchemaClient(exists=True)
    FlatRaptorIndex(client, embedder=fake_embedder)
    assert client.created is None


class MergeQuery:
    def __init__(self, dist):
        self.dist = dist

    def near_vector(self, **kwargs):
        if self.dist is None:
            return type("Res", (), {"objects": []})
        meta = type("M", (), {"distance": self.dist})()
        obj = type("O", (), {"uuid": "existing", "metadata": meta, "properties": {}})
        return type("Res", (), {"objects": [obj]})


class MergeCollection(DummyCollection):
    def __init__(self, dist):
        super().__init__()
        self.query = MergeQuery(dist)


class MergeClient(DummyClient):
    def __init__(self, dist):
        super().__init__()
        self.coll = MergeCollection(dist)

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


def test_insert_chunk_merges_if_similar():
    client = MergeClient(0.05)
    idx = TestIndex(client, embedder=fake_embedder)
    node_id = idx.insert_chunk("text", "fact")
    assert node_id == "existing"
    assert not client.coll.calls


def test_insert_chunk_creates_if_distant():
    client = MergeClient(0.5)
    idx = TestIndex(client, embedder=fake_embedder)
    node_id = idx.insert_chunk("text", "fact")
    assert client.coll.calls
    assert node_id != "existing"
