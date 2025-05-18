
from typing import Tuple, List, Dict, Any

from services.graph_proxy import GraphProxy
from services.slot_filler import SlotFiller
from services.template_service import TemplateService
from schemas.cypher import CypherTemplate


class ExtractionPipeline:
    """Связывает TemplateService → SlotFiller → GraphProxy."""

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        graph_proxy: GraphProxy,
    ):
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.graph_proxy = graph_proxy

    # --- публичный метод -------------------------------------------------------
    def extract_and_save(
        self, text: str, chapter: int, tags: List[str] | None = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Главный метод энд‑пойнта `/v1/extract-save`.

        Возвращает:
        • facts — список dict‑ов (лог, пригодно для отладки или UI)
        • inserted_ids — ID созданных узлов/фактов
        """
        templates = self.template_service.find_templates(text)
        all_facts: List[Dict] = []
        inserted: List[str] = []

        for tpl in templates:
            # 1. Заполняем слоты
            slots = self.slot_filler.fill_slots(tpl, text)
            # 2. Рендерим Cypher (пока — псевдо)
            cypher = self._render_cypher(tpl, slots, chapter, tags)
            # 3. Сохраняем в граф
            result = self.graph_proxy.run_query(cypher)
            # 4. Агрегируем результаты
            all_facts.append({"template": tpl["id"], "slots": slots})
            inserted.extend([r.get("id") for r in result if "id" in r])

        return all_facts, inserted

    # --- приватные утилиты ------------------------------------------------------
    def _render_cypher(
        self,
        template: CypherTemplate,
        slots: Dict,
        chapter: int,
        tags: List[str] | None,
    ) -> str:
        """Подставляет слоты в Cypher Jinja2‑шаблон.

        🎯 В проде используем Jinja2 – см. utils/jinja.py.
        """
        return f"// Cypher for template={template['id']} slots={slots}"


extract_pipeline = ExtractionPipeline()
