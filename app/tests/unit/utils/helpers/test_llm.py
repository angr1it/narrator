"""Unit tests for the ``call_llm_with_json_list`` helper."""

import json
import pytest
from pydantic import BaseModel
from langchain_core.language_models.fake import FakeListLLM
from langchain.prompts import PromptTemplate

from utils.helpers.llm import (
    call_llm_with_json_list,
    call_llm_with_model,
)


class ItemModel(BaseModel):
    name: str


class ObjModel(BaseModel):
    action: str
    entity_id: str


PROMPT = PromptTemplate.from_template("ignore")


def make_llm(response: str) -> FakeListLLM:
    """Return a fake LLM yielding ``response``."""
    return FakeListLLM(responses=[response])


@pytest.mark.asyncio
async def test_parse_json_object():
    """A single JSON object should be wrapped into a list."""
    llm = make_llm('{"name": "A"}')
    result = await call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="A")]


@pytest.mark.asyncio
async def test_parse_json_array():
    """A JSON array should be returned as a list."""
    llm = make_llm('[{"name": "B"}, {"name": "C"}]')
    result = await call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="B"), ItemModel(name="C")]


@pytest.mark.asyncio
async def test_parse_empty_response():
    """An empty response should raise after retries."""
    llm = make_llm("")
    with pytest.raises(json.JSONDecodeError):
        await call_llm_with_json_list(ItemModel, llm, PROMPT)


@pytest.mark.asyncio
async def test_parse_plain_text_response():
    """Plain text without JSON should raise."""
    llm = make_llm("hello")
    with pytest.raises(json.JSONDecodeError):
        await call_llm_with_json_list(ItemModel, llm, PROMPT)


@pytest.mark.asyncio
async def test_parse_json_with_text_response():
    """A JSON object mixed with text should raise."""
    llm = make_llm('prefix {"name": "D"} suffix')
    with pytest.raises(json.JSONDecodeError):
        await call_llm_with_json_list(ItemModel, llm, PROMPT)


@pytest.mark.asyncio
async def test_parse_list_with_text_response():
    """A JSON array surrounded by text should still be parsed."""
    llm = make_llm('start [{"name": "E"}] end')
    result = await call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="E")]


@pytest.mark.asyncio
async def test_call_llm_with_model_parses_object():
    """JSON object is parsed into the specified model."""
    llm = make_llm('{"action": "use", "entity_id": "e1"}')
    res = await call_llm_with_model(ObjModel, llm, PROMPT)
    assert res == ObjModel(action="use", entity_id="e1")


@pytest.mark.asyncio
async def test_call_llm_with_model_invalid():
    """Invalid JSON should raise."""
    llm = make_llm("oops")
    with pytest.raises(json.JSONDecodeError):
        await call_llm_with_model(ObjModel, llm, PROMPT)


@pytest.mark.asyncio
async def test_skip_invalid_items():
    """Invalid objects from the LLM should be ignored."""
    response = '[{"name": "A"}, {"name": null}, {"other": "x"}]'
    llm = make_llm(response)
    result = await call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="A")]
