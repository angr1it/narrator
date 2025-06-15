"""Unit tests for format instructions injection."""

from uuid import uuid4

import pytest
from langchain_core.language_models.fake import FakeListLLM

from services.slot_filler import SlotFiller, PROMPTS_ENV
from schemas.cypher import CypherTemplate, SlotDefinition


class DummyTemplate(CypherTemplate):
    pass


@pytest.mark.asyncio
async def test_run_phase_includes_format_instructions(monkeypatch):
    """_run_phase should render templates requiring ``format_instructions``."""
    llm = FakeListLLM(responses=["[]"])
    filler = SlotFiller(llm)

    template = DummyTemplate(
        id=uuid4(),
        name="t",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        extract_cypher="simple.j2",
        return_map={"a": "b"},
    )

    orig_get_template = PROMPTS_ENV.get_template

    def fake_get_template(name, *a, **k):
        if name == "extract_slots.j2":
            return PROMPTS_ENV.from_string("{% include 'shared_instructions.j2' %}")
        return orig_get_template(name, *a, **k)

    monkeypatch.setattr(PROMPTS_ENV, "get_template", fake_get_template)

    captured = {}

    async def _fake_call(*args, **kwargs):
        prompt = args[2]
        captured["prompt"] = prompt.template
        return []

    monkeypatch.setattr("services.slot_filler.call_llm_with_json_list", _fake_call)

    await filler._run_phase("extract", "extract_slots.j2", template, "txt")
    assert "{{ format_instructions }}" not in captured["prompt"]
