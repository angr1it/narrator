"""Unit tests for SlotFiller slot extraction.

These tests use dummy LLM chains to verify fallback behaviour and slot
validation without hitting external services.
"""

from uuid import uuid4
import pytest
from services.slot_filler import SlotFiller
from schemas.cypher import CypherTemplate, SlotDefinition


class DummyChain:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __or__(self, other):
        return self

    def invoke(self, _):
        phase = self.calls.pop(0)
        return type(
            "R",
            (),
            {"model_dump": lambda self: [self.responses[phase]]},
        )()


class DummyLLM:
    def __init__(self, responses):
        self.chain = DummyChain(responses)

    def __or__(self, other):
        self.chain.calls.append(other)
        return self.chain


def make_template(required=True, with_summary=False):
    slots = {
        "character": SlotDefinition(
            name="character",
            type="STRING",
            required=required,
        )
    }
    if with_summary:
        slots["summary"] = SlotDefinition(
            name="summary",
            type="STRING",
            required=False,
        )
    return CypherTemplate(
        id=str(uuid4()),
        name="t",
        title="t",
        description="d",
        slots=slots,
        extract_cypher="simple.j2",
        return_map={"a": "b"},
    )


@pytest.mark.asyncio
async def test_fill_slots_simple(monkeypatch):
    """Basic extraction should populate mandatory slots."""
    tpl = make_template()
    llm = DummyLLM(
        {
            "extract": {"character": "A"},
            "generate": {"character": "A"},
        }
    )
    filler = SlotFiller(llm)

    async def _mock(*_a, **_k):
        return [{"character": "A"}]

    monkeypatch.setattr(filler, "_run_phase", _mock)
    result = await filler.fill_slots(tpl, "txt")
    assert result[0].slots["character"] == "A"


@pytest.mark.asyncio
async def test_fallback_triggered(monkeypatch):
    """Fallback phase should run when extract returns empty."""
    tpl = make_template()
    calls = {
        "extract": [{}],
        "fallback": [{"character": "B"}],
        "generate": [{"character": "B"}],
    }
    llm = DummyLLM(calls)
    filler = SlotFiller(llm)

    async def _mock(phase, *_args, **_kw):
        return [calls[phase].pop(0)]

    monkeypatch.setattr(filler, "_run_phase", _mock)
    result = await filler.fill_slots(tpl, "txt")
    assert result[0].slots["character"] == "B"


@pytest.mark.asyncio
async def test_generate_additional_field(monkeypatch):
    """Generation phase may return optional fields such as summary."""
    tpl = make_template(with_summary=True)
    responses = {
        "extract": [{"character": "A"}],
        "generate": [{"character": "A", "summary": "S"}],
    }
    filler = SlotFiller(DummyLLM(responses))

    async def _mock(phase, *_a, **_k):
        return [responses[phase].pop(0)]

    monkeypatch.setattr(filler, "_run_phase", _mock)
    result = await filler.fill_slots(tpl, "txt")
    assert result[0].slots.get("summary") == "S"


def test_validate_and_cast():
    """Validation should keep strings unchanged for STRING type."""
    tpl = make_template()
    filler = SlotFiller(DummyLLM({}))
    obj = {"character": "c"}
    casted = filler._validate_and_cast(obj, tpl)
    assert casted["character"] == "c"
