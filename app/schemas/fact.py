from pydantic import BaseModel
from typing import Optional, List


class Fact(BaseModel):
    # ── required ─────────────────────────────────────────────────────────
    id: str                                # generated in Cypher (uuid)
    predicate: str                         # e.g. HAS_TRAIT, MEMBER_OF …
    subject: str                           # node-id or name of the subject
    # ── optional but COMMON ──────────────────────────────────────────────
    object: Optional[str] = None           # node-id of the object (if relation)
    value:      Optional[str] = None       # literal value (if attribute)
    # ── temporal versioning (all optional) ───────────────────────────────
    from_chapter: Optional[int] = None
    to_chapter:   Optional[int] = None
    iso_date:    Optional[str] = None
    # ── narrative metadata ───────────────────────────────────────────────
    summary: Optional[str] = None
    tags:    Optional[List[str]] = None
    # ── vector space  ────────────────────────────────────────────────────
    vector:  Optional[List[float]] = None
