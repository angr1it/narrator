from services.templates import TemplateService
from schemas.cypher import TemplateRenderMode

"""Unit tests for TemplateService search filtering in augment mode."""

from weaviate.classes.query import Filter


class DummyQuery:
    def __init__(self):
        self.captured = None

    def near_vector(self, *, near_vector, limit, filters=None, return_metadata=None):
        self.captured = filters

        class R:
            objects = []

        return R()


class DummyCollection:
    def __init__(self, q):
        self.query = q


class DummyClient:
    def __init__(self, q):
        self.collections = type(
            "C",
            (),
            {
                "get": lambda self, name: DummyCollection(q),
                "exists": lambda self, name: True,
            },
        )()


class DummyService(TemplateService):
    def ensure_base_templates(self) -> None:  # type: ignore[override]
        pass


def test_top_k_adds_augment_filter():
    """Verify that ``supports_augment`` is added to the Weaviate filter."""
    q = DummyQuery()
    svc = DummyService(weaviate_client=DummyClient(q), embedder=lambda x: [])
    svc.top_k("q", k=1, mode=TemplateRenderMode.AUGMENT)
    assert getattr(q.captured, "target", None) == "supports_augment"
