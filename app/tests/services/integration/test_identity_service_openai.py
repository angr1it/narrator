import os
import time
from uuid import uuid4

import pytest
import openai
from weaviate.collections.classes.data import DataObject

from services.identity_service import IdentityService
from config.weaviate import connect_to_weaviate

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

    client = connect_to_weaviate()
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
def prepare_alias_data(wclient):
    """Создаём коллекцию и добавляем тестовые alias-данные."""
    service = IdentityService(
        weaviate_client=wclient,
        embedder=openai_embedder,
        llm=lambda _: {"action": "new"},  # dummy
        tracer=None,
    )

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
    def _factory(llm):
        return IdentityService(
            weaviate_client=wclient,
            embedder=openai_embedder,
            llm=llm,
            tracer=None,
        )

    return _factory


# ─────────────────── Tests ────────────────────────────────────────────────────
def test_exact_canonical_match(identity_service_factory):
    service = identity_service_factory(llm=make_dummy_llm({"action": "new"}))
    plans = service.resolve(
        raw_name="Zorian",
        etype="CHARACTER",
        chapter=1,
        fragment_id="frag-1",
        snippet="Zorian walked into the room.",
    )
    assert plans == []


def test_exact_almost_canonical_match(identity_service_factory):
    service = identity_service_factory(llm=make_dummy_llm({"action": "new"}))
    plans = service.resolve(
        raw_name="Zorian's",
        etype="CHARACTER",
        chapter=1,
        fragment_id="frag-1",
        snippet="Zorian's sword gleamed in the light.",
    )
    assert plans == [
        (
            "add_alias",
            {
                "entity_id": eid_a,
                "alias_text": "Zorian's",
                "entity_type": "CHARACTER",
                "chapter": 1,
                "fragment_id": "frag-1",
                "snippet": "Zorian's sword gleamed in the light.",
            },
        )
    ]


def test_llm_add_alias(identity_service_factory):
    service = identity_service_factory(
        llm=make_dummy_llm(
            {
                "action": "use",
                "entity_id": eid_a,
                "alias_text": "Zориан",
                "canonical": False,
            }
        )
    )
    plans = service.resolve(
        raw_name="Zориан",
        etype="CHARACTER",
        chapter=2,
        fragment_id="frag-2",
        snippet="Все звали его Zорианом.",
    )
    assert plans and plans[0][0] == "add_alias"
    assert plans[0][1]["entity_id"] == eid_a
    assert plans[0][1]["alias_text"] == "Zориан"


def test_llm_creates_new_entity(identity_service_factory):
    service = identity_service_factory(llm=make_dummy_llm({"action": "new"}))
    plans = service.resolve(
        raw_name="Valerius",
        etype="CHARACTER",
        chapter=3,
        fragment_id="frag-3",
        snippet="Valerius впервые появился на горизонте.",
    )
    assert plans and plans[0][0] == "create_entity_with_alias"


def test_exact_create_new_entity(identity_service_factory):
    service = identity_service_factory(llm=make_dummy_llm({"action": "new"}))
    plans = service.resolve(
        raw_name="Commodus",
        etype="CHARACTER",
        chapter=4,
        fragment_id="frag-4",
        snippet="Император Commodus пришёл.",
    )
    assert plans and plans[0][0] == "create_entity_with_alias"


def test_llm_selects_existing_alias_different(identity_service_factory):
    service = identity_service_factory(
        llm=make_dummy_llm(
            {
                "action": "use",
                "entity_id": eid_b,
                "alias_text": "Миранда",
                "canonical": False,
            }
        )
    )
    plans = service.resolve(
        raw_name="Миранда",
        etype="CHARACTER",
        chapter=5,
        fragment_id="frag-5",
        snippet="Она представилась как Миранда.",
    )
    assert plans and plans[0][0] == "add_alias"
    assert plans[0][1]["entity_id"] == eid_b
    assert plans[0][1]["alias_text"] == "Миранда"
