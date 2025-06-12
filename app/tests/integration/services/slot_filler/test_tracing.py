import time
import uuid
import pytest

pytestmark = pytest.mark.integration

from langchain_openai import ChatOpenAI
from services.slot_filler import SlotFiller
from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from config.langfuse import get_client

try:
    from config import app_settings
except Exception:
    pytest.skip("Settings not configured", allow_module_level=True)


@pytest.fixture(scope="module")
def openai_key() -> str:
    key = app_settings.OPENAI_API_KEY
    assert key, "Set OPENAI_API_KEY in environment to run integration tests"
    return key


def test_fill_slots_tracing(openai_key: str):
    client = get_client()
    trace = client.trace()
    handler = trace.get_langchain_handler(update_parent=True)
    trace_id = trace.id

    llm = ChatOpenAI(api_key=openai_key, temperature=0.0)
    filler = SlotFiller(llm=llm, callback_handler=handler)

    template = CypherTemplate(
        id=uuid.uuid4(),
        name="member_of",
        title="Test",
        description="",
        slots={
            "character": SlotDefinition(name="character", type="STRING"),
            "faction": SlotDefinition(name="faction", type="STRING"),
        },
        graph_relation=GraphRelationDescriptor(
            predicate="MEMBER_OF", subject="$character", object="$faction"
        ),
        cypher="member_of.j2",
        return_map={"c": "Character", "f": "Faction"},
    )
    fills = filler.fill_slots(template, "Арам вступил в Братство Стали.")
    assert fills, "Slots not filled"

    time.sleep(5)
    fetched = client.fetch_trace(trace_id)
    assert fetched is not None
    assert fetched.name == "slotfiller.extract"
    assert any(obs["type"] == "generation" for obs in fetched.observations)
