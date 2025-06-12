import os
import time
from uuid import uuid4

import pytest
import openai

pytestmark = pytest.mark.integration
from weaviate.collections.classes.data import DataObject

from services.identity_service import IdentityService

try:
    from services.templates.service import get_weaviate_client
except Exception:
    pytest.skip("Settings not configured", allow_module_level=True)

MODEL_NAME = "text-embedding-3-small"


def openai_embedder(text: str) -> list[float]:
    response = openai.embeddings.create(
        input=text,
        model=MODEL_NAME,
        user="identity-tests",
    )
    return response.data[0].embedding


# ─────────────────── Weaviate client ──────────────────────────────────────────
@pytest.fixture(scope="session")
def wclient():
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_KEY:
        pytest.skip("OPENAI_API_KEY not set")
    openai.api_key = OPENAI_KEY

    client = get_weaviate_client()
    if not client.is_ready():
        pytest.skip("Weaviate is not available")

    yield client

    # cleanup
    time.sleep(0.5)
    if "Alias" in client.collections.list_all():
        client.collections.delete("Alias")
    client.close()


# ─────────────────── Prepare test data ────────────────────────────────────────
eid_a = str(uuid4())  # фиксированные ID для alias "Zorian"
eid_b = str(uuid4())  # фиксированные ID для alias "Miranda"


@pytest.fixture(scope="session", autouse=True)
async def prepare_alias_data(wclient):
    """Создаём коллекцию и добавляем тестовые alias-данные."""
    service = IdentityService(
        weaviate_async_client=wclient.async_,
        embedder=openai_embedder,
        llm_disambiguator=lambda *_: {"action": "new"},  # dummy
    )
    await service.startup()

    alias_col = wclient.collections.get("Alias")

    alias_col.data.insert_many(
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
def identity_service_factory(wclient):
    async def _factory(llm):
        service = IdentityService(
            weaviate_async_client=wclient.async_,
            embedder=openai_embedder,
            llm_disambiguator=llm,
        )
        await service.startup()
        return service

    return _factory


# ─────────────────── Tests ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exact_canonical_match(identity_service_factory):
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
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
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
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
