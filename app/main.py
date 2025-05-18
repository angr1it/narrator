from fastapi import FastAPI

from app.api import api_router


app = FastAPI(title="StoryGraph Prototype – spaCy")

app.include_router(api_router, prefix="/v1", tags=["v1"])


@app.get("/v1/sys/health")
def health():
    return {"status": "ok"}
