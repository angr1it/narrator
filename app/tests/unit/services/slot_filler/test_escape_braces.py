"""Ensure _run_phase works with unsafe Jinja delimiters in user text."""

import pytest
from jinja2 import Template
import uuid

from services.slot_filler import SlotFiller, PROMPTS_ENV
from schemas.cypher import CypherTemplate, SlotDefinition
from langchain_core.language_models.fake import FakeListLLM


class DummyTemplate(CypherTemplate):
    pass


@pytest.mark.asyncio
async def test_run_phase_escapes_user_text(monkeypatch):
    """Text containing "{{" or "{%" should not raise TemplateSyntaxError."""
    llm = FakeListLLM(responses=["[]"])
    filler = SlotFiller(llm)
    monkeypatch.setattr(PROMPTS_ENV, "get_template", lambda pf: Template("text"))

    tpl = DummyTemplate(
        id=str(uuid.uuid4()),
        name="t",
        title="t",
        description="d",
        slots={"s": SlotDefinition(name="s", type="STRING")},
        extract_cypher="simple.j2",
        return_map={"a": "b"},
    )

    unsafe_text = 'He said: {{oops}} and {% bad %}'
    res = await filler._run_phase("extract", "extract_slots.j2", tpl, unsafe_text)
    assert res == []
