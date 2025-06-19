from __future__ import annotations

from typing import Any, List

from pydantic import Field

from fastapi_camelcase import CamelModel

from schemas.extract import (
    AliasOut,
    ExtractSaveIn,
    ExtractSaveOut,
    Relationship,
)


class AugmentCtxIn(ExtractSaveIn):
    pass


class AugmentRow(CamelModel):
    """Single row returned by ``/augment-context``."""

    source: str | None = Field(None, description="Имя субъекта или его идентификатор")
    relation: str = Field(..., description="Тип связи")
    target: str | None = Field(None, description="Имя объекта или его идентификатор")
    value: str | None = Field(None, description="Значение или имя связанной сущности")
    meta_fact_chapter: int | None = Field(
        None, description="Глава, в которой найден факт"
    )
    meta_template_id: str | None = Field(None, description="ID использованного шаблона")
    meta_chunk_id: str | None = Field(None, description="Chunk, породивший запись")
    meta_raptor_id: str | None = Field(None, description="Связанный RaptorNode")
    meta_confidence: float | None = Field(None, description="Уверенность шаблона")
    meta_draft_stage: str | None = Field(None, description="Этап черновика")
    triple_text: str | None = Field(None, description="Строка вида 'A REL B'")


class AugmentContext(CamelModel):
    rows: List[AugmentRow] = Field(default_factory=list, description="Найденные связи")
    summary: str | None = Field(None, description="Краткое резюме")


class AugmentCtxOut(CamelModel):
    context: AugmentContext
    trace_id: str
