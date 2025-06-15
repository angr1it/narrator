"""Verify that base templates are imported on service creation."""

import uuid
from services.templates import TemplateService, CypherTemplate, CypherTemplateBase
from templates.base import base_templates


class DummyService(TemplateService):
    def __init__(self):
        self.imported = []
        super().__init__(weaviate_client=object(), embedder=None)

    def _ensure_schema(self) -> None:  # override
        pass

    def upsert(self, tpl: CypherTemplateBase) -> CypherTemplate:  # type: ignore[override]
        self.imported.append(tpl)
        return CypherTemplate(id=str(uuid.uuid4()), **tpl.model_dump())

    def get_by_name(self, name: str) -> CypherTemplate:  # type: ignore[override]
        raise ValueError("not found")


def test_init_imports_base_templates():
    """Service initialization should import all ``base_templates``."""
    svc = DummyService()
    names = [t.name for t in svc.imported]
    assert names == [d["name"] for d in base_templates]
