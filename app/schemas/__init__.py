from __future__ import annotations

from typing import Any

from fastapi_camelcase import CamelModel

from schemas.extract import (
    AliasOut,
    ExtractSaveIn,
    ExtractSaveOut,
    Relationship,
)


class AugmentCtxIn(ExtractSaveIn):
    pass


class AugmentCtxOut(CamelModel):
    context: dict[str, Any]
    trace_id: str
