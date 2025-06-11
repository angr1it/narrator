from typing import Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas.stage import StageEnum


class ChunkBase(BaseModel):
    """Chunk -- кусок текста """
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    chapter: int
    stage: StageEnum = StageEnum.brainstorm
    revision_hash: str = ""
    raptor_node_id: Optional[str] = None
    slots: Dict[str, Union[str, int, float, bool]]
    alias_refs: List[str]
    embedding: Optional[List[float]] = None