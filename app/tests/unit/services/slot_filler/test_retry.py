"""Tests for SlotFiller retry logic during LLM calls.

These tests simulate failures on the first call and check that a second attempt
is made with the correct tracing configuration.
"""

from jinja2 import Template
from services.slot_filler import SlotFiller, PROMPTS_ENV
from schemas.cypher import CypherTemplate, SlotDefinition
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.callbacks.base import BaseCallbackHandler
import uuid


class MyFakeLLM(FakeListLLM):
    model_config = {"extra": "allow"}

    def __init__(self, responses):
        super().__init__(responses=responses)
        self._last_prompt = None
        self._calls = 0
        self._last_run_manager = None

    def _call(self, prompt, stop=None, run_manager=None, **kwargs):
        self._last_prompt = prompt
        self._last_run_manager = run_manager
        self._calls += 1
        return super()._call(prompt, stop=stop, run_manager=run_manager, **kwargs)

    async def _acall(self, prompt, stop=None, run_manager=None, **kwargs):
        self._last_prompt = prompt
        self._last_run_manager = run_manager
        self._calls += 1
        return await super()._acall(
            prompt, stop=stop, run_manager=run_manager, **kwargs
        )

    def get_prompt(self):
        return self._last_prompt

    def get_run_manager(self):
        return self._last_run_manager

    @property
    def calls(self):
        return self._calls


class DummyHandler(BaseCallbackHandler):
    pass


class DummyTemplate(CypherTemplate):
    pass


def test_run_phase_retries(monkeypatch):
    """The slot filler should retry when the LLM output is invalid JSON."""
    handler = DummyHandler()
    llm = MyFakeLLM(
        [
            "not json",
            '[{"character": "A", "details": "d"}]',
        ]
    )
    filler = SlotFiller(llm, callback_handler=handler)
    monkeypatch.setattr(PROMPTS_ENV, "get_template", lambda pf: Template("text"))

    tpl = DummyTemplate(
        id=uuid.uuid4(),
        name="t",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        extract_cypher="simple.j2",
        return_map={"a": "b"},
    )
    res = filler._run_phase("extract", "extract_slots.j2", tpl, "txt")
    assert llm.calls == 2
    assert res == [{"character": "A", "details": "d"}]
    rm = llm.get_run_manager()
    assert rm.handlers == [handler]
    assert "SlotFiller" in rm.tags
