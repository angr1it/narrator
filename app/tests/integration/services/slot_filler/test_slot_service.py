import os
import pytest
from uuid import uuid4

pytestmark = pytest.mark.integration

from langchain_openai import ChatOpenAI
from services.slot_filler import SlotFiller
from schemas.cypher import CypherTemplate, SlotDefinition

try:
    from config import app_settings
except Exception:
    pytest.skip("Settings not configured", allow_module_level=True)

# --- FIXTURES ---------------------------------------------------------------

FIXED_UUID = uuid4()


@pytest.fixture(scope="module")
def openai_key() -> str:
    key = app_settings.OPENAI_API_KEY
    assert key, "Set OPENAI_API_KEY in environment to run integration tests"
    return key


@pytest.fixture
def base_template() -> CypherTemplate:
    return CypherTemplate(
        id=FIXED_UUID,
        name="membership_change",
        title="Membership change",
        description="Когда персонаж покидает одну фракцию и вступает в другую",
        slots={
            "character": SlotDefinition(
                name="character", type="STRING", description="Имя героя", required=True
            ),
            "faction": SlotDefinition(
                name="faction",
                type="STRING",
                description="Название фракции",
                required=True,
            ),
            "summary": SlotDefinition(
                name="summary",
                type="STRING",
                description="Краткое описание",
                required=False,
            ),
        },
        cypher="mock.cypher",
        return_map={},
    )


@pytest.fixture
def filler(openai_key) -> SlotFiller:
    llm = ChatOpenAI(api_key=openai_key, temperature=0.0)
    return SlotFiller(llm)


# --- TEST CASES -------------------------------------------------------------


def test_extract_multiple_results(filler: SlotFiller, base_template: CypherTemplate):
    text = "Арен покинул Дом Зари и примкнул к Северному фронту."
    results = filler.fill_slots(base_template, text)

    assert isinstance(results, list)
    assert len(results) >= 2

    for r in results:
        assert r.template_id == str(FIXED_UUID)
        assert "character" in r.slots
        assert "faction" in r.slots
        assert isinstance(r.details, str)


def test_extract_missing_then_generate(filler: SlotFiller):
    template = CypherTemplate(
        id=FIXED_UUID,
        name="emotion_event",
        title="Emotion expression",
        description="Персонаж выражает эмоцию к другому персонажу",
        slots={
            "subject": SlotDefinition(
                name="subject",
                type="STRING",
                description="Кто испытывает эмоцию",
                required=True,
            ),
            "target": SlotDefinition(
                name="target",
                type="STRING",
                description="На кого направлена эмоция",
                required=True,
            ),
            "emotion": SlotDefinition(
                name="emotion", type="STRING", description="Тип эмоции", required=True
            ),
            "summary": SlotDefinition(
                name="summary",
                type="STRING",
                description="Описание сцены",
                required=False,
            ),
        },
        cypher="mock.cypher",
        return_map={},
    )
    text = "Мира посмотрела на Эрика с презрением."
    results = filler.fill_slots(template, text)

    assert results
    for r in results:
        slots = r.slots
        assert slots["subject"] == "Мира"
        assert slots["target"] == "Эрик"
        assert "emotion" in slots
        assert isinstance(r.details, str)
        if "summary" in slots and slots["summary"] is not None:
            assert isinstance(slots["summary"], str)


def test_extract_single_object(filler: SlotFiller):
    template = CypherTemplate(
        id=FIXED_UUID,
        name="trait_reveal",
        title="Trait reveal",
        description="Когда персонаж раскрывает черту другого",
        slots={
            "actor": SlotDefinition(
                name="actor", type="STRING", description="Кто раскрыл", required=True
            ),
            "trait": SlotDefinition(
                name="trait", type="STRING", description="Какая черта", required=True
            ),
        },
        cypher="mock.cypher",
        return_map={},
    )
    text = "Мира раскрыла, что Арен с рождения был одноруким."
    results = filler.fill_slots(template, text)

    assert len(results) == 1
    r = results[0]
    assert r.slots["actor"] == "Мира"
    assert "trait" in r.slots
    assert isinstance(r.details, str)
