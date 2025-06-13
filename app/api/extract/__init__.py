from fastapi import APIRouter
from schemas import ExtractSaveIn, ExtractSaveOut
from services.pipeline import get_extraction_pipeline


route = APIRouter()


@route.post("/extract-save", response_model=ExtractSaveOut)
async def extract_save(req: ExtractSaveIn) -> ExtractSaveOut:
    """Run the extraction pipeline for the given fragment."""
    pipeline = get_extraction_pipeline()
    return await pipeline.extract_and_save(
        text=req.text,
        chapter=req.chapter,
        stage=req.stage,
        tags=req.tags,
    )
