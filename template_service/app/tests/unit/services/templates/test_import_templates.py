"""Unit tests for :func:`templates.imports.import_templates`.

These tests verify that the helper imports every template from
``base_templates`` by calling :meth:`TemplateService.upsert` once per entry.
"""

import uuid

from templates.imports import import_templates
from templates.base import base_templates
from services.templates import TemplateService, CypherTemplateBase, CypherTemplate


class DummyService(TemplateService):
    """Service stub that records calls and mimics stored templates."""

    def __init__(self, existing=None):
        self.saved = []
        self.data = {t.name: t for t in (existing or [])}
        super().__init__(weaviate_client=object(), embedder=None)

    def _ensure_schema(self) -> None:  # type: ignore[override]
        pass

    def ensure_base_templates(self) -> None:  # type: ignore[override]
        pass

    def upsert(self, tpl: CypherTemplateBase) -> CypherTemplate:  # type: ignore[override]
        self.saved.append(tpl)
        obj = CypherTemplate(id=str(uuid.uuid4()), **tpl.model_dump())
        self.data[tpl.name] = obj
        return obj

    def get_by_name(self, name: str) -> CypherTemplate:  # type: ignore[override]
        if name not in self.data:
            raise ValueError("not found")
        return self.data[name]


def test_imports_all_base_templates():
    """All templates from ``base_templates`` should be upserted."""
    svc = DummyService()
    import_templates(svc, base_templates)
    names = [t.name for t in svc.saved]
    assert names == [d["name"] for d in base_templates]


def test_skips_when_version_matches():
    """Templates already up-to-date should be skipped."""
    entry = base_templates[0]
    existing = CypherTemplate(id=str(uuid.uuid4()), **entry)
    svc = DummyService(existing=[existing])
    import_templates(svc, [entry])
    assert svc.saved == []


def test_updates_when_version_differs():
    """Existing templates with other versions are overwritten."""
    entry = base_templates[0]
    outdated = entry.copy()
    outdated["version"] = "0.0.1"
    existing = CypherTemplate(id=str(uuid.uuid4()), **outdated)
    svc = DummyService(existing=[existing])
    import_templates(svc, [entry])
    assert [t.name for t in svc.saved] == [entry["name"]]
