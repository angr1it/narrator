from pydantic import BaseModel
from typing import Optional, List

from schemas.stage import StageEnum


class Fact(BaseModel):
    # ── required ─────────────────────────────────────────────────────────
    id: str  # generated in Cypher (uuid)
    predicate: str  # e.g. HAS_TRAIT, MEMBER_OF …
    subject_id: str  # node-id or name of the subject

    # ── optional but COMMON ──────────────────────────────────────────────
    object_id: Optional[str] = None  # node-id of the object (if relation)
    value: Optional[str] = None  # literal value (if attribute)

    # ── temporal versioning (all optional) ───────────────────────────────
    from_chapter: Optional[int] = None
    to_chapter: Optional[int] = None
    iso_date: Optional[str] = None

    # ── narrative metadata ───────────────────────────────────────────────
    summary: Optional[str] = None
    tags: Optional[List[str]] = None

    stage: StageEnum = StageEnum.brainstorm
    confidence: float = 0.2

    active: bool = True
    source_raptor_node: Optional[str] = None
    supersedes_fact_id: Optional[str] = None

    # ── vector space  ────────────────────────────────────────────────────
    vector: Optional[List[float]] = None
