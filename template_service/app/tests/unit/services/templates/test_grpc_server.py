"""Tests for the gRPC server wrapper around :class:`TemplateService`."""

from server import TemplateServiceServicer
from services.templates import TemplateService, CypherTemplate
from schemas.cypher import CypherTemplateBase
from proto import template_service_pb2


class DummyService(TemplateService):
    def __init__(self):
        self.called = {}

    def _ensure_schema(self) -> None:  # pragma: no cover - not needed
        pass

    def upsert(self, tpl: CypherTemplateBase) -> CypherTemplate:  # type: ignore[override]
        self.called["upsert"] = tpl
        return CypherTemplate(id="1", **tpl.model_dump())

    def get(self, id: str) -> CypherTemplate:  # type: ignore[override]
        self.called["get"] = id
        return CypherTemplate(
            id=id,
            name="n",
            title="t",
            description="d",
            slots={},
            extract_cypher="c.j2",
            return_map={},
        )

    def top_k(self, query: str, category: str | None = None, k: int = 10, **_):  # type: ignore[override]
        self.called["top_k"] = query
        tpl = CypherTemplate(
            id="2",
            name="n",
            title="t",
            description="d",
            slots={},
            extract_cypher="c.j2",
            return_map={},
        )
        return [tpl]


def test_find_templates():
    """``FindTemplates`` should return serialized templates."""
    servicer = TemplateServiceServicer(DummyService())
    resp = servicer.FindTemplates(
        template_service_pb2.FindTemplatesRequest(query="q", top_k=1), None
    )
    assert len(resp.templates) == 1
    assert resp.templates[0].id == "2"
