import pytest
from fastapi.testclient import TestClient

from main import create_app
from config import app_settings
import api.extract as extract_module


class DummyPipeline:
    def __init__(self):
        self.calls = []

    async def extract_and_save(self, text, chapter, stage, tags):
        self.calls.append((text, chapter, stage, tags))
        return {
            "chunk_id": "c1",
            "raptor_node_id": "r1",
            "relationships": [],
            "aliases": [],
        }


@pytest.fixture()
def client(monkeypatch):
    pipeline = DummyPipeline()
    monkeypatch.setattr(extract_module, "get_extraction_pipeline", lambda: pipeline)
    app = create_app()
    return TestClient(app), pipeline


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {app_settings.AUTH_TOKEN}"}


def test_auth_required(client):
    c, _ = client
    resp = c.post("/v1/extract-save", json={"text": "a. b.", "chapter": 1})
    assert resp.status_code == 401


def test_invalid_text_long(client):
    c, _ = client
    long_text = "x" * 1001
    resp = c.post(
        "/v1/extract-save",
        json={"text": long_text, "chapter": 1},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_invalid_chapter(client):
    c, _ = client
    resp = c.post(
        "/v1/extract-save",
        json={"text": "a. b.", "chapter": 0},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_invalid_stage(client):
    c, _ = client
    resp = c.post(
        "/v1/extract-save",
        json={"text": "a. b.", "chapter": 1, "stage": "unknown"},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_success(client):
    c, pipeline = client
    resp = c.post(
        "/v1/extract-save",
        json={"text": "a. b.", "chapter": 1, "tags": ["x"]},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["chunkId"] == "c1"
    assert pipeline.calls
