from fastapi import APIRouter

from app.api.augment import route as augment_router
from app.api.extract import route as extract_router

api_router = APIRouter()

api_router.include_router(augment_router, tags=["augment"])
api_router.include_router(extract_router, tags=["extract"])
