from __future__ import annotations

from typing import Any, List

from fastapi_camelcase import CamelModel
from pydantic import Field, field_validator
import re

from schemas.stage import StageEnum


class Relationship(CamelModel):
    subject: str = Field(..., description="ID субъекта")
    predicate: str = Field(..., description="Тип связи")
    object: str | None = Field(None, description="ID объекта")


class AliasOut(CamelModel):
    alias_text: str = Field(..., description="Текст упоминания")
    entity_id: str = Field(..., description="Идентификатор сущности")


class ExtractSaveIn(CamelModel):
    text: str = Field(
        ..., description="Фрагмент до 1000 символов (примерно 2–8 предложений)"
    )
    chapter: int = Field(..., ge=1, description="Номер главы (>= 1)")
    stage: StageEnum = Field(StageEnum.brainstorm, description="Этап черновика")
    tags: List[str] = Field(default_factory=list, description="Ключевые слова")

    @field_validator("stage", mode="before")
    @classmethod
    def _parse_stage(cls, v: Any) -> StageEnum:
        """Allow stage to be specified as enum name or numeric value."""
        if isinstance(v, StageEnum):
            return v
        if isinstance(v, str):
            if v.lstrip("-+").isdigit():
                v = int(v)
            else:
                try:
                    return StageEnum[v]
                except KeyError as exc:  # pragma: no cover - validated in tests
                    raise ValueError(f"invalid stage: {v}") from exc
        try:
            return StageEnum(int(v))
        except (ValueError, TypeError) as exc:  # pragma: no cover - validated
            raise ValueError(f"invalid stage: {v}") from exc

    @field_validator("text")
    @classmethod
    def _check_length(cls, v: str) -> str:
        """Ensure text is not longer than 1000 characters."""
        if len(v) > 1000:
            raise ValueError("text must be 1000 characters or less")
        return v


class ExtractSaveOut(CamelModel):
    chunk_id: str = Field(..., description="Созданный ChunkNode")
    raptor_node_id: str = Field(..., description="ID RaptorNode")
    relationships: List[Relationship] = Field(
        default_factory=list, description="Вставленные связи"
    )
    aliases: List[AliasOut] = Field(
        default_factory=list, description="Записанные алиасы"
    )
