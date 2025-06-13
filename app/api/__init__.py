from fastapi import APIRouter, Depends

from core.auth import get_token_header

from api.augment import route as augment_router
from api.extract import route as extract_router

api_router = APIRouter(dependencies=[Depends(get_token_header)])

api_router.include_router(augment_router, tags=["augment"])
api_router.include_router(extract_router, tags=["extract"])
