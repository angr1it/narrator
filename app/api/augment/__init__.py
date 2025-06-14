from fastapi import APIRouter
from schemas import AugmentCtxIn, AugmentCtxOut
from services.pipeline import get_augment_pipeline


route = APIRouter()


@route.post("/augment-context", response_model=AugmentCtxOut)
async def augment_ctx(req: AugmentCtxIn):
    """Augment the text fragment with additional context."""
    pipeline = get_augment_pipeline()
    return await pipeline.augment_context(req.text, req.chapter)
