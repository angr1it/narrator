from typing import List, Optional

from pydantic import BaseModel
import numpy as np

from schemas.stage import StageEnum


class RaptorNode(BaseModel):
    node_id: str
    level: int = 0
    parent_id: Optional[str] = None
    children: Optional[List[str]] = []

    text_vec: np.ndarray[float]  # 1536-d
    alias_vec: np.ndarray[float]  # 1536-d
    triple_vec: np.ndarray[float]  # 1536-d
    centroid: np.ndarray[float]  # α·text + β·triple

    chapter_span: tuple[int, int]
    insertions_cnt: int = 1
    stage: StageEnum = StageEnum.brainstorm

    summary_text: Optional[str] = None
