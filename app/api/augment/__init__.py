from fastapi import APIRouter, Depends

from core.auth import token_auth
from schemas import AugmentCtxIn, AugmentCtxOut
from typing import Any


class _DummyPipeline:
    def run(self, text: str, meta: dict[str, Any]):
        raise NotImplementedError


augment_pipeline = _DummyPipeline()


route = APIRouter()


@route.post("/augment-context", response_model=AugmentCtxOut)
def augment_ctx(req: AugmentCtxIn, token=Depends(token_auth)):
    return augment_pipeline.run(req.text, {"chapter": req.chapter})
