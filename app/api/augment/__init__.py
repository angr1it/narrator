from fastapi import APIRouter
from schemas import AugmentCtxIn, AugmentCtxOut
from typing import Any


class _DummyPipeline:
    def run(self, text: str, meta: dict[str, Any]):
        raise NotImplementedError


augment_pipeline = _DummyPipeline()


route = APIRouter()


@route.post("/augment-context", response_model=AugmentCtxOut)
async def augment_ctx(req: AugmentCtxIn):
    """Augment the text fragment with additional context."""
    return augment_pipeline.run(req.text, {"chapter": req.chapter})
