from jinja2 import Template
from contextlib import contextmanager
import services.slot_filler as services
from services.slot_filler import SlotFiller, PROMPTS_ENV
from schemas.cypher import CypherTemplate, SlotDefinition
from langchain.prompts import PromptTemplate
import uuid


class DummyChain:
    def __init__(self):
        self.calls = 0

    def __or__(self, other):
        return self

    def invoke(self, _):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("bad json")

        class R:
            def model_dump(self):
                return [{"character": "A"}]

        return R()


dummy_chain = DummyChain()


class DummyLLM:
    def __or__(self, other):
        return dummy_chain


class DummyTemplate(CypherTemplate):
    pass


def test_run_phase_retries(monkeypatch):
    filler = SlotFiller(DummyLLM())
    monkeypatch.setattr(PROMPTS_ENV, "get_template", lambda pf: Template("text"))
    orig_or = PromptTemplate.__or__

    def patched_or(self, other):
        if other is filler.llm:
            return dummy_chain
        return orig_or(self, other)

    monkeypatch.setattr(PromptTemplate, "__or__", patched_or, raising=False)

    called = {"n": 0}

    @contextmanager
    def dummy_span(name: str):
        called["n"] += 1

        class S:
            def update(self, **_):
                pass

        yield S()

    monkeypatch.setattr(
        services,
        "start_as_current_span",
        dummy_span,
    )

    tpl = DummyTemplate(
        id=uuid.uuid4(),
        name="t",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        cypher="simple.j2",
        return_map={"a": "b"},
    )
    res = filler._run_phase("extract", "extract_slots.j2", tpl, "txt")
    assert dummy_chain.calls == 2
    assert res == [{"character": "A"}]
    assert called["n"] == 1
