"""Unit tests for the ``call_llm_with_json_list`` helper."""

import json
import pytest
from pydantic import BaseModel
from langchain_core.language_models.fake import FakeListLLM
from langchain.prompts import PromptTemplate

from utils.helpers.llm import call_llm_with_json_list


class ItemModel(BaseModel):
    name: str


PROMPT = PromptTemplate.from_template("ignore")


def make_llm(response: str) -> FakeListLLM:
    """Return a fake LLM yielding ``response``."""
    return FakeListLLM(responses=[response])


def test_parse_json_object():
    """A single JSON object should be wrapped into a list."""
    llm = make_llm('{"name": "A"}')
    result = call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="A")]


def test_parse_json_array():
    """A JSON array should be returned as a list."""
    llm = make_llm('[{"name": "B"}, {"name": "C"}]')
    result = call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="B"), ItemModel(name="C")]


def test_parse_empty_response():
    """An empty response should raise after retries."""
    llm = make_llm("")
    with pytest.raises(json.JSONDecodeError):
        call_llm_with_json_list(ItemModel, llm, PROMPT)


def test_parse_plain_text_response():
    """Plain text without JSON should raise."""
    llm = make_llm("hello")
    with pytest.raises(json.JSONDecodeError):
        call_llm_with_json_list(ItemModel, llm, PROMPT)


def test_parse_json_with_text_response():
    """A JSON object mixed with text should raise."""
    llm = make_llm('prefix {"name": "D"} suffix')
    with pytest.raises(json.JSONDecodeError):
        call_llm_with_json_list(ItemModel, llm, PROMPT)


def test_parse_list_with_text_response():
    """A JSON array surrounded by text should still be parsed."""
    llm = make_llm('start [{"name": "E"}] end')
    result = call_llm_with_json_list(ItemModel, llm, PROMPT)
    assert result == [ItemModel(name="E")]
