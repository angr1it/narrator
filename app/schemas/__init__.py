from typing import Any

from fastapi_camelcase import CamelModel


class ExtractSaveIn(CamelModel):
    chapter: int
    tags: list[str] = []
    text: str


class ExtractSaveOut(CamelModel):
    status: str
    cypher_batch: list[str]
    trace_id: str


class AugmentCtxIn(ExtractSaveIn): ...


class AugmentCtxOut(CamelModel):
    context: dict[str, Any]
    trace_id: str
