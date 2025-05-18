import pytest

from schemas.cypher import CypherTemplate, FactDescriptor, SlotDefinition
from services.slot_filler import SlotFiller
from tempates.base import base_templates
from config import app_settings


@pytest.fixture(scope="module")
def openai_key() -> str:
    key = app_settings.OPENAI_API_KEY
    assert key, "Установите переменную окружения OPENAI_API_KEY для теста"
    return key


@pytest.fixture
def trait_template() -> CypherTemplate:
    template_dict = base_templates[0]

    slots = [SlotDefinition(**s) for s in template_dict["slots"]]
    fact_desc = FactDescriptor(**template_dict["fact_descriptor"])

    return CypherTemplate(
        id=template_dict["id"],
        version=template_dict["version"],
        title=template_dict["title"],
        description=template_dict["description"],
        category=template_dict["category"],
        slots=slots,
        fact_descriptor=fact_desc,
        cypher=template_dict["cypher"],
    )


@pytest.fixture
def filler(openai_key: str) -> SlotFiller:
    # Температуру ставим 0 для большей детерминированности на тестах
    return SlotFiller(api_key=openai_key, temperature=0.0)


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
    slots = item["slots"]

    # Обязательные поля
    assert slots["character"].lower().startswith("арен")
    assert "храбр" in slots["trait"].lower()  # модификатор на русский корень
    assert int(slots["chapter"]) == 10

    # "summary" генерируется (может отсутствовать, если модель не сгенерирует)
    if "summary" in slots:
        assert isinstance(slots["summary"], str) and len(slots["summary"]) > 0

    # details присутствуют
    assert "details" in item and isinstance(item["details"], str)
