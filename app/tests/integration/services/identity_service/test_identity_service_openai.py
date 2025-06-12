import os
from pathlib import Path
from uuid import uuid4
import hashlib
import subprocess

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration
import weaviate
from weaviate.collections.classes.data import DataObject
from weaviate.embedded import EmbeddedOptions

from services.identity_service import get_identity_service_async


def openai_embedder(text: str) -> list[float]:
    """Deterministic pseudo-embedding for offline tests."""
    h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    return [float(h % 1000)]


# ─────────────────── Prepare test data ────────────────────────────────────────
eid_a = str(uuid4())  # фиксированные ID для alias "Zorian"
eid_b = str(uuid4())  # фиксированные ID для alias "Miranda"


from _pytest.monkeypatch import MonkeyPatch


@pytest_asyncio.fixture(scope="session")
async def wclient(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("weaviate-data")
    binary_dir = Path(__file__).parent / "weaviate_bin"

    mp = MonkeyPatch()
    orig_popen = subprocess.Popen

    def silent_popen(*args, **kwargs):
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stderr", subprocess.DEVNULL)
        return orig_popen(*args, **kwargs)

    mp.setattr(subprocess, "Popen", silent_popen)

    client = weaviate.WeaviateAsyncClient(
        embedded_options=EmbeddedOptions(
            binary_path=str(binary_dir),
            persistence_data_path=str(data_dir),
            hostname="127.0.0.1",
            port=8079,
            grpc_port=50060,
        )
    )
    try:
        await client.connect()
    except Exception:
        await client._connection.wait_for_weaviate(30)
        await client.connect()
    yield client

    await client.close()
    mp.undo()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_alias_data(wclient: weaviate.WeaviateAsyncClient):
    """Создаём коллекцию и добавляем тестовые alias-данные."""

    service = get_identity_service_async(wclient=wclient, embedder=openai_embedder)

    await service.startup()

    alias_col = service.w.collections.get("Alias")
    await alias_col.data.insert_many(
        [
            DataObject(
                properties={
                    "alias_text": "Zorian",
                    "entity_id": eid_a,
                    "entity_type": "CHARACTER",
                    "canonical": True,
                },
                vector=openai_embedder("Zorian"),
            ),
            DataObject(
                properties={
                    "alias_text": "Miranda",
                    "entity_id": eid_b,
                    "entity_type": "CHARACTER",
                    "canonical": True,
                },
                vector=openai_embedder("Miranda"),
            ),
        ]
    )


# ─────────────────── Dummy LLM factory (Callable) ─────────────────────────────
import json


def make_dummy_llm(forced_response: dict):
    json_response = json.dumps(forced_response)

    def llm_callable(_):
        return json_response

    return llm_callable


# ─────────────────── IdentityService factory ──────────────────────────────────
@pytest.fixture
def identity_service_factory(wclient: weaviate.WeaviateAsyncClient):
    async def _factory(llm=None):
        service = get_identity_service_async(
            llm_disambiguator=llm,
            wclient=wclient,
            embedder=openai_embedder,
        )
        await service.startup()
        return service

    return _factory


# ─────────────────── Tests ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exact_canonical_match(identity_service_factory):
    service = await identity_service_factory()
    result = await service.resolve_bulk(
        {"character": "Zorian"},
        chapter=1,
        chunk_id="frag-1",
        snippet="Zorian walked into the room.",
    )
    assert result.alias_tasks == []
    assert result.mapped_slots["character"] == eid_a


@pytest.mark.asyncio
async def test_exact_almost_canonical_match(identity_service_factory):
    service = await identity_service_factory()
    result = await service.resolve_bulk(
        {"character": "Zorian's"},
        chapter=1,
        chunk_id="frag-1",
        snippet="Zorian's sword gleamed in the light.",
    )
    assert len(result.alias_tasks) == 1
    task = result.alias_tasks[0]
    assert task.cypher_template_id == "add_alias"
    assert task.entity_id == eid_a
    assert task.alias_text == "Zorian's"
    assert task.chapter == 1
    assert task.chunk_id == "frag-1"


@pytest.mark.asyncio
async def test_llm_add_alias(identity_service_factory):
    service = await identity_service_factory(
        make_dummy_llm(
            {
                "action": "use",
                "entity_id": eid_a,
                "alias_text": "Zориан",
                "canonical": False,
            }
        )
    )
    result = await service.resolve_bulk(
        {"character": "Zориан"},
        chapter=2,
        chunk_id="frag-2",
        snippet="Все звали его Zорианом.",
    )
    assert result.alias_tasks
    task = result.alias_tasks[0]
    assert task.cypher_template_id == "add_alias"
    assert task.entity_id == eid_a
    assert task.alias_text == "Zориан"


@pytest.mark.asyncio
async def test_llm_creates_new_entity(identity_service_factory):
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
    result = await service.resolve_bulk(
        {"character": "Valerius"},
        chapter=3,
        chunk_id="frag-3",
        snippet="Valerius впервые появился на горизонте.",
    )
    assert result.alias_tasks
    assert result.alias_tasks[0].cypher_template_id == "create_entity_with_alias"


@pytest.mark.asyncio
async def test_exact_create_new_entity(identity_service_factory):
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
    result = await service.resolve_bulk(
        {"character": "Commodus"},
        chapter=4,
        chunk_id="frag-4",
        snippet="Император Commodus пришёл.",
    )
    assert result.alias_tasks
    assert result.alias_tasks[0].cypher_template_id == "create_entity_with_alias"


@pytest.mark.asyncio
async def test_llm_selects_existing_alias_different(identity_service_factory):
    service = await identity_service_factory(
        make_dummy_llm(
            {
                "action": "use",
                "entity_id": eid_b,
                "alias_text": "Миранда",
                "canonical": False,
            }
        )
    )
    result = await service.resolve_bulk(
        {"character": "Миранда"},
        chapter=5,
        chunk_id="frag-5",
        snippet="Она представилась как Миранда.",
    )
    task = result.alias_tasks[0]
    assert task.cypher_template_id == "add_alias"
    assert task.entity_id == eid_b
    assert task.alias_text == "Миранда"
