from fastapi import FastAPI

from api import api_router
from config import app_settings
from services.pipeline import get_extraction_pipeline


def create_app() -> FastAPI:
    """Configure and return the FastAPI application."""
    app = FastAPI(title="StoryGraph Service", debug=app_settings.DEBUG)
    app.include_router(api_router, prefix="/v1", tags=["v1"])

    @app.on_event("startup")
    async def _startup() -> None:
        get_extraction_pipeline()

    @app.get("/v1/sys/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
