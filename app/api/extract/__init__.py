from fastapi import APIRouter, Depends

from core.auth import token_auth
from schemas import ExtractSaveIn, ExtractSaveOut


route = APIRouter()


@route.post("/extract-save", response_model=ExtractSaveOut)
def extract_save(req: ExtractSaveIn, token=Depends(token_auth)):
    return extract_pipeline.run(req.text, {"chapter": req.chapter})
