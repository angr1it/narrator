from enum import Enum
from typing import List, Optional
from uuid import uuid4
from dataclasses import dataclass

from pydantic import BaseModel, Field

from schemas.stage import StageEnum


class EntityTypeEnum(str, Enum):
    character = "character"
    faction = "faction"
    item = "item"


class EntityAlias(BaseModel):
    alias_id: str = Field(default_factory=lambda: str(uuid4()))
    alias_text: str
    entity_id: str
    entity_type: EntityTypeEnum
    canonical: bool = False
    chapter: int
    stage: StageEnum = StageEnum.brainstorm
    confidence: float = 0.5
    snippet: Optional[str] = None
    vector: Optional[List[float]] = None


@dataclass
class EntityResolveResult:
    entity_id: str
    alias_cypher: str | None = None  # Cypher, если создаём новую ноду
