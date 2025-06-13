"""End‑to‑end SlotFiller integration tests.

Using a real OpenAI model, these tests check that :class:`SlotFiller` correctly
extracts information from narrative text via the default base templates.
"""

import pytest

pytestmark = pytest.mark.integration

from uuid import uuid4
from langchain_openai import ChatOpenAI
from schemas.cypher import (
    CypherTemplate,
    GraphRelationDescriptor,
    SlotDefinition,
)
from services.slot_filler import SlotFiller
from templates.base import base_templates


@pytest.fixture
def trait_template() -> CypherTemplate:
    template_dict = base_templates[0]
    slots = {
        name: SlotDefinition(**data) for name, data in template_dict["slots"].items()
    }
    relation = GraphRelationDescriptor(**template_dict["graph_relation"])

    return CypherTemplate(
        id=uuid4(),
        name=template_dict["name"],
        version=template_dict["version"],
        title=template_dict["title"],
        description=template_dict["description"],
        category=template_dict["category"],
        slots=slots,
        graph_relation=relation,
        cypher=template_dict["cypher"],
        return_map=template_dict.get("return_map", {}),
    )


@pytest.fixture
def filler(openai_key: str) -> SlotFiller:
    # Температуру ставим 0 для большей детерминированности на тестах
    llm = ChatOpenAI(api_key=openai_key, temperature=0.0)
    return SlotFiller(llm)


def test_trait_attribution_end_to_end(
    filler: SlotFiller, trait_template: CypherTemplate
):
    """
    Проверяем, что SlotFiller извлекает все обязательные слоты:
    character, trait, chapter + генерирует summary (необязательный).
    """
    text = (
        "В 10-й главе Арен проявил невероятную храбрость, "
        "бросившись спасать товарища из горящего здания."
    )

    results = filler.fill_slots(trait_template, text)

    # Ожидаем хотя бы один результат
    assert results, "LLM не вернул ни одного заполнения"

    item = results[0]
    slots = item.slots

    # Обязательные поля
    assert slots["character"].lower().startswith("арен")
    assert "храбр" in slots["trait"].lower()  # модификатор на русский корень
    assert int(slots["chapter"]) == 10

    # "summary" генерируется (может отсутствовать, если модель не сгенерирует)
    if "summary" in slots:
        assert isinstance(slots["summary"], str) and len(slots["summary"]) > 0

    # details присутствуют
    assert isinstance(item.details, str)
