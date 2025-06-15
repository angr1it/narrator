from __future__ import annotations

import json
import re
import asyncio
from typing import Any, List, Type

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, RootModel

from utils.logger import get_logger


logger = get_logger(__name__)


def _extract_json_array(text: str) -> str:
    """Return the first JSON array found in *text* or the original string."""
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


async def call_llm_with_json_list(
    item_model: Type[BaseModel],
    llm: Any,
    prompt: PromptTemplate,
    *,
    callback_handler: Any | None = None,
    run_name: str | None = None,
    tags: List[str] | None = None,
    max_attempts: int = 2,
) -> List[BaseModel]:
    """Invoke *llm* with *prompt* and parse JSON list of ``item_model`` objects."""

    class ResponseList(RootModel[List[item_model]]):  # type: ignore[misc, valid-type]
        pass


    parser = PydanticOutputParser(pydantic_object=ResponseList)
    fix_parser = OutputFixingParser.from_llm(llm, parser)
    chain = prompt | llm

    attempts = 0
    config: RunnableConfig | None = None
    if callback_handler or tags or run_name is not None:
        config = {"callbacks": [callback_handler] if callback_handler else []}
        if tags:
            config["tags"] = tags
        if run_name is not None:
            config["run_name"] = run_name

    while True:
        try:
            raw = await chain.ainvoke({}, config=config)
            if hasattr(raw, "content"):
                raw = raw.content
            raw = _extract_json_array(str(raw))
            try:
                result = await parser.ainvoke(raw)
            except OutputParserException:
                try:
                    result = await fix_parser.ainvoke(raw, config=config)
                except OutputParserException:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        data = [data]
                    result = ResponseList.model_validate(data)
            return list(result.root)
        except Exception as e:
            attempts += 1
            logger.error("LLM call failed: %s", e)
            if attempts >= max_attempts:
                raise


def call_llm_with_json_list_sync(*args, **kwargs):
    """Synchronous wrapper around :func:`call_llm_with_json_list`."""
    return asyncio.run(call_llm_with_json_list(*args, **kwargs))


async def call_llm_with_model(
    model: Type[BaseModel],
    llm: Any,
    prompt: PromptTemplate,
    *,
    callback_handler: Any | None = None,
    run_name: str | None = None,
    tags: List[str] | None = None,
    max_attempts: int = 2,
) -> BaseModel:
    """Invoke *llm* with *prompt* and parse JSON object of ``model`` type."""

    parser = PydanticOutputParser(pydantic_object=model)
    fix_parser = OutputFixingParser.from_llm(llm, parser)
    chain = prompt | llm

    attempts = 0
    config: RunnableConfig | None = None
    if callback_handler or tags or run_name is not None:
        config = {"callbacks": [callback_handler] if callback_handler else []}
        if tags:
            config["tags"] = tags
        if run_name is not None:
            config["run_name"] = run_name

    while True:
        try:
            raw = await chain.ainvoke({}, config=config)
            if hasattr(raw, "content"):
                raw = raw.content
            try:
                result = await parser.ainvoke(str(raw))
            except OutputParserException:
                try:
                    result = await fix_parser.ainvoke(str(raw), config=config)
                except OutputParserException:
                    data = json.loads(str(raw))
                    result = model.model_validate(data)
            return result
        except Exception as e:  # pragma: no cover - network / llm errors
            attempts += 1
            logger.error("LLM call failed: %s", e)
            if attempts >= max_attempts:
                raise


def call_llm_with_model_sync(*args, **kwargs):
    """Synchronous wrapper around :func:`call_llm_with_model`."""
    return asyncio.run(call_llm_with_model(*args, **kwargs))
