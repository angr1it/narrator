from typing import Tuple, List, Dict, Any

from services.fact_builder import FactBuilder
from services.graph_proxy import GraphProxy
from services.slot_filler import SlotFiller
from services.template_renderer import TemplateRenderer
from services.templates import TemplateService
from services.identity_service import IdentityService
from schemas.cypher import CypherTemplate


class ExtractionPipeline:
    """
    ExtractionPipeline связывает TemplateService → SlotFiller → GraphProxy → IdentityService.

    Основной сценарий:
    1️⃣ Получает текст и метаданные (chapter, tags).
    2️⃣ Ищет top-K CypherTemplate-ов (по векторному поиску).
    3️⃣ Для каждого шаблона извлекает слоты.
    4️⃣ Собирает Cypher-батч:
        - сначала alias-запросы (add_alias / create_entity_with_alias),
        - затем основной факт-запрос.
    5️⃣ Выполняет Cypher в Neo4j через GraphProxy.
    6️⃣ Обрабатывает alias-task-и из результата → пишет алиасы в Weaviate.
    7️⃣ Возвращает список фактов + вставленные id-ы.
    """

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        graph_proxy: GraphProxy,
        identity_service: IdentityService,
        template_renderer: TemplateRenderer,
        fact_builder: FactBuilder,
        top_k: int = 3,
    ):
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.graph_proxy = graph_proxy
        self.identity_service = identity_service
        self.template_renderer = template_renderer
        self.fact_builder = fact_builder
        self.top_k = top_k

    def extract_and_save(
        self, text: str, chapter: int, tags: List[str] | None = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Выполняет полный цикл:
        - ищет шаблоны,
        - заполняет слоты,
        - подготавливает alias-запросы,
        - отправляет всё в Neo4j,
        - обрабатывает alias-таски.
        """
        templates = self.template_service.top_k(text, k=self.top_k)
        all_facts = []
        inserted_ids = []

        for tpl in templates:
            slot_fills = self.slot_filler.fill_slots(tpl, text)
            for slot_fill in slot_fills:
                # 1️⃣ рендерим content-cypher
                render_plan = self.template_renderer.render(
                    tpl, slot_fill, {"chapter": chapter, "tags": tags or []}
                )
                content_cypher = render_plan.content_cypher

                # 2️⃣ выполняем content-cypher и получаем UIDs
                result = self.graph_proxy.run_query(content_cypher)
                uids = {
                    k: result[0][render_plan.return_keys[k]]
                    for k in render_plan.return_keys
                }

                # 3️⃣ рендерим fact-cypher (всегда; Cypher сам решает, создавать или нет)
                fact_plan = self.fact_builder.make(
                    tpl, slot_fill.slots, uids, {"chapter": chapter, "tags": tags}
                )

                # 4️⃣ выполняем fact-cypher
                self.graph_proxy.run_query(fact_plan.cypher)

                # 5️⃣ собираем результат
                all_facts.append(
                    {
                        "template": tpl.id,
                        "slots": slot_fill.slots,
                        "details": slot_fill.details,
                    }
                )
                inserted_ids.append(
                    result[0].get("id")
                )  # зависит от того, что возвращает

        return all_facts, inserted_ids

    def _collect_alias_cypher(self, slots: Dict, chapter: int) -> List[str]:
        """
        Собирает список Cypher-запросов для alias-операций:
        - add_alias
        - create_entity_with_alias

        Использует только те поля, которые относятся к сущностям.
        """
        cypher_list: List[str] = []

        for field, value in slots.items():
            entity_type = _map_field_to_entity_type(field)
            if not entity_type:
                continue

            tasks = self.identity_service.resolve(
                raw_name=value,
                etype=entity_type,
                chapter=chapter,
                fragment_id=slots.get("fragment_id", ""),  # можно передать пустое
                snippet=slots.get("source_text", ""),
            )

            for tpl_id, params in tasks:
                tpl = self.identity_service.get_alias_template(tpl_id)
                cypher = _render_cypher(tpl, params, chapter, None)
                cypher_list.append(cypher)

        return cypher_list


def _map_field_to_entity_type(field: str) -> str | None:
    """
    Маппинг полей-слотов → entity_type.
    Возвращает None, если поле не относится к сущностям.
    """
    mapping = {
        "character": "CHARACTER",
        "faction": "FACTION",
        "location": "LOCATION",
    }
    return mapping.get(field)


def _render_cypher(
    template: CypherTemplate,
    slots: Dict,
    chapter: int,
    tags: List[str] | None,
) -> str:
    """
    Рендерит финальный Cypher Jinja2-шаблон с контекстом:
    - chapter, tags,
    - слоты,
    - (опционально) fact_descriptor.
    """
    context = dict(slots)
    context.update(
        {
            "chapter": chapter,
            "tags": tags or [],
        }
    )

    if template.fact_descriptor:
        fd = template.fact_descriptor

        def resolve(expr: str | None) -> str | None:
            if expr and expr.startswith("$"):
                return slots.get(expr[1:])
            return expr

        context["fact"] = {
            "predicate": fd.predicate,
            "subject": resolve(fd.subject),
            "object": resolve(fd.object),
            "value": resolve(fd.value),
        }

    return template.render(slots=context)
