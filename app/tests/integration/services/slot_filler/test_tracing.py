"""Integration tests for SlotFiller tracing.

These tests ensure that Langfuse tracing works end‑to‑end when SlotFiller is
used with an OpenAI model.  They poll the API until the trace becomes
available.
"""

import time
import uuid
import pytest

pytestmark = pytest.mark.integration

from langchain_openai import ChatOpenAI
from services.slot_filler import SlotFiller
from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from config.langfuse import get_client
from config import app_settings


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

    # --- wait until the trace has been ingested -----------------------------
    #
    # 404s happen because the SDK sends data asynchronously; the trace may
    # not exist yet when we try to read it :contentReference[oaicite:0]{index=0}.
    # We poll `fetch_trace` with exponential back-off for ≤30 s instead
    # of one hard sleep.

    from tenacity import (
        retry,
        stop_after_delay,
        wait_exponential,
        retry_if_exception_type,
    )
    from langfuse.api.resources.commons.errors import NotFoundError

    @retry(
        retry=retry_if_exception_type(NotFoundError),
        wait=wait_exponential(multiplier=0.5, min=1, max=5),
        stop=stop_after_delay(30),
        reraise=True,
    )
    def _fetch_ready_trace():
        client.flush()
        return client.fetch_trace(trace_id)

    fetched = _fetch_ready_trace()
    assert fetched.data.name == "slotfiller.extract"
