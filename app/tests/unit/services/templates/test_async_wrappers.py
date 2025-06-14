"""Unit tests for the async wrappers in :mod:`services.templates`.

The dummy service avoids any external dependencies so we can verify that each
async method delegates correctly to its synchronous counterpart.
"""

import pytest
from uuid import uuid4
from services.templates import TemplateService, CypherTemplate
from schemas.cypher import CypherTemplateBase, TemplateRenderMode


class DummyService(TemplateService):
    def __init__(self):
        # Do not call parent __init__ to avoid schema setup
        self.client = None
        self.embedder = None
        self.called = {}

    def upsert(self, tpl: CypherTemplateBase) -> CypherTemplate:  # type: ignore[override]
        self.called["upsert"] = tpl
        return CypherTemplate(id=str(uuid4()), **tpl.model_dump())

    def get(self, id: str) -> CypherTemplate:  # type: ignore[override]
        self.called["get"] = id
        return CypherTemplate(
            id=str(uuid4()),
            name="n",
            title="t",
            description="d",
            slots={},
            extract_cypher="c.j2",
            return_map={},
        )

    def get_by_name(self, name: str) -> CypherTemplate:  # type: ignore[override]
        self.called["get_by_name"] = name
        return CypherTemplate(
            id=str(uuid4()),
            name=name,
            title="t",
            description="d",
            slots={},
            extract_cypher="c.j2",
            return_map={},
        )

    def top_k(
        self,
        query: str,
        category=None,
        k: int = 3,
        distance_threshold: float = 0.5,
        *,
        mode: TemplateRenderMode = TemplateRenderMode.EXTRACT,
    ):  # type: ignore[override]
        self.called["top_k"] = (query, k)
        if k <= 0:
            return []
        return [
            CypherTemplate(
                id=str(uuid4()),
                name="n",
                title="t",
                description="d",
                slots={},
                extract_cypher="c.j2",
                return_map={},
            )
        ]


@pytest.mark.asyncio
async def test_async_wrappers_call_sync_methods():
    """Ensure async helpers delegate to the synchronous methods."""
    svc = DummyService()
    tpl = CypherTemplateBase(
        name="n",
        title="t",
        description="d",
        slots={},
        extract_cypher="c.j2",
        return_map={},
    )

    await svc.upsert_async(tpl)
    assert "upsert" in svc.called

    await svc.get_async("id1")
    assert svc.called["get"] == "id1"

    await svc.get_by_name_async("name")
    assert svc.called["get_by_name"] == "name"

    await svc.top_k_async("q", k=1)
    assert svc.called["top_k"] == ("q", 1)


def test_top_k_handles_nonpositive_k():
    """An empty list is returned when ``k`` is non-positive."""
    svc = DummyService()
    results = svc.top_k("q", k=0)
    assert results == []
