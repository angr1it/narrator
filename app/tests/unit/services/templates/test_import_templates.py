"""Unit tests for :func:`templates.imports.import_templates`.

These tests verify that the helper imports every template from
``base_templates`` by calling :meth:`TemplateService.upsert` once per entry.
"""

import uuid

from templates.imports import import_templates
from templates.base import base_templates
from services.templates import TemplateService, CypherTemplateBase, CypherTemplate


class DummyService(TemplateService):
    """Service stub that records templates passed to ``upsert``."""

    def __init__(self):
        self.saved = []
        super().__init__(weaviate_client=object(), embedder=None)

    def _ensure_schema(self) -> None:  # type: ignore[override]
        pass

    def ensure_base_templates(self) -> None:  # type: ignore[override]
        pass

    def upsert(self, tpl: CypherTemplateBase) -> CypherTemplate:  # type: ignore[override]
        self.saved.append(tpl)
        return CypherTemplate(id=str(uuid.uuid4()), **tpl.model_dump())


def test_imports_all_base_templates():
    """All templates from ``base_templates`` should be upserted."""
    svc = DummyService()
    import_templates(svc, base_templates)
    names = [t.name for t in svc.saved]
    assert names == [d["name"] for d in base_templates]
