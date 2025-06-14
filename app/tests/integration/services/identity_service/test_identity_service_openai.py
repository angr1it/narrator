"""OpenAI backed IdentityService tests.

These integration tests run against OpenAI embeddings and a local Weaviate
instance.  They verify the entity resolution logic of :class:`IdentityService`
including alias creation and LLM disambiguation.
"""

import pytest
import pytest_asyncio
from uuid import uuid4

pytestmark = pytest.mark.integration

from weaviate.collections.classes.data import DataObject
from services.identity_service import IdentityService, get_identity_service_sync
from schemas.cypher import SlotDefinition

SLOT_DEFS = {
    "character": SlotDefinition(name="character", type="STRING", is_entity_ref=True)
}


# ─────────────────── Prepare test data ────────────────────────────────────────
eid_a = str(uuid4())  # фиксированные ID для alias "Zorian"
eid_b = str(uuid4())  # фиксированные ID для alias "Miranda"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_alias_data(wclient, openai_embedder, clean_alias_collection):
    service = get_identity_service_sync(wclient=wclient, embedder=openai_embedder)
    await service.startup()

    alias_col = service._w.collections.get("Alias")
    await service._run_sync(
        alias_col.data.insert_many,
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
        ],
    )

    # Confirm preparation succeeded
    results = alias_col.query.fetch_objects()
    assert {obj.properties["alias_text"] for obj in results.objects} >= {
        "Zorian",
        "Miranda",
    }


# ─────────────────── Dummy LLM factory (Callable) ─────────────────────────────
def make_dummy_llm(forced_response: dict):
    def llm_callable(raw_name: str, aliases: list, chapter: int, snippet: str) -> dict:
        return forced_response

    return llm_callable


# ─────────────────── IdentityService factory ──────────────────────────────────
@pytest_asyncio.fixture
async def identity_service_factory(prepare_alias_data, wclient, openai_embedder):
    async def _factory(llm=None):
        service = get_identity_service_sync(
            llm=llm,
            wclient=wclient,
            embedder=openai_embedder,
        )
        await service.startup()
        return service

    return _factory


# ─────────────────── Tests ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exact_canonical_match(identity_service_factory):
    """Alias resolution returns existing canonical ID without LLM use."""
    service = await identity_service_factory()
    result = await service.resolve_bulk(
        {"character": "Zorian"},
        slot_defs=SLOT_DEFS,
        chapter=1,
        chunk_id="frag-1",
        snippet="Zorian walked into the room.",
    )
    assert result.alias_tasks == []
    assert result.mapped_slots["character"] == eid_a


@pytest.mark.asyncio
async def test_exact_almost_canonical_match(identity_service_factory):
    """Slightly different alias should trigger add_alias task."""
    service = await identity_service_factory()
    result = await service.resolve_bulk(
        {"character": "Zorian's"},
        slot_defs=SLOT_DEFS,
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
    """LLM suggests adding a new alias to an existing entity."""
    service = await identity_service_factory(
        make_dummy_llm({"action": "use", "entity_id": eid_a, "alias_text": "Zориан"})
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
    """LLM selects creating a brand new entity when no match exists."""
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
    result = await service.resolve_bulk(
        {"character": "Valerius"},
        slot_defs=SLOT_DEFS,
        chapter=3,
        chunk_id="frag-3",
        snippet="Valerius впервые появился на горизонте.",
    )
    assert result.alias_tasks
    assert result.alias_tasks[0].cypher_template_id == "create_entity_with_alias"


@pytest.mark.asyncio
async def test_exact_create_new_entity(identity_service_factory):
    """Exact name with LLM new action creates entity."""
    service = await identity_service_factory(make_dummy_llm({"action": "new"}))
    result = await service.resolve_bulk(
        {"character": "Commodus"},
        slot_defs=SLOT_DEFS,
        chapter=4,
        chunk_id="frag-4",
        snippet="Император Commodus пришёл.",
    )
    assert result.alias_tasks
    assert result.alias_tasks[0].cypher_template_id == "create_entity_with_alias"


@pytest.mark.asyncio
async def test_llm_selects_existing_alias_different(identity_service_factory):
    """LLM chooses an existing alias different from input."""
    service = await identity_service_factory(
        make_dummy_llm({"action": "use", "entity_id": eid_b, "alias_text": "Миранда"})
    )
    result = await service.resolve_bulk(
        {"character": "Миранда"},
        slot_defs=SLOT_DEFS,
        chapter=5,
        chunk_id="frag-5",
        snippet="Она представилась как Миранда.",
    )
    task = result.alias_tasks[0]
    assert task.cypher_template_id == "add_alias"
    assert task.entity_id == eid_b
    assert task.alias_text == "Миранда"
