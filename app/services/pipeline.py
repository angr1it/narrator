from typing import Tuple, List, Dict, Any

import neo4j

from schemas.slots import SlotFill
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
    1. Получает текст и метаданные (chapter, tags).
    2. Ищет top-K CypherTemplate-ов (по векторному поиску).
    3. Для каждого шаблона извлекает слоты.
    4. Собирает Cypher-батч:
        - сначала alias-запросы (add_alias / create_entity_with_alias),
        - затем основной факт-запрос.
    5.Выполняет Cypher в Neo4j через GraphProxy.
    6. Обрабатывает alias-task-и из результата → пишет алиасы в Weaviate.
    7. Возвращает список фактов + вставленные id-ы.
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

    async def extract_and_save(
        self,
        query: str,
        chapter: int,
        tags: List[str] | None = None,
    ):
        templates = self.template_service.top_k(query, k=self.top_k)
        for tpl in templates:
            await self.process_template(template=tpl, query=query, chapter=chapter)

    async def process_template(
        self, template: CypherTemplate, query: str, chapter: int
    ):
        fills: list[SlotFill] = self.slot_filler.fill_slots(template, query)

        fills, alias_tpl_calls = await self.identity_service.resolve_bulk(fills, chapter)
    
        alias_statements = [
            self.template_renderer.render(t, p, {"chapter": chapter})
            for t, p in alias_tpl_calls
        ]

        uid_map = self._collect_uid_map(self.graph_proxy.run_batch(alias_statements))

        domain_cypher = self.template_renderer.render(
            template, fills[0].slots | uid_map, {"chapter": chapter}
        )
        uid_map.update(
            self._collect_uid_map(self.graph_proxy.run_batch([domain_cypher]))
        )

        fact_cypher = self.fact_builder.make(
            template, fills[0].slots, uid_map, chapter
        ).cypher
    
        res_fact = self.graph_proxy.run_batch([fact_cypher])
        uid_map.update(self._collect_uid_map(res_fact))

        self.identity_service.persist_aliases(uid_map)

        return uid_map

    @staticmethod
    def _collect_uid_map(batch_results: List[neo4j.Result]) -> dict[str, Any]:
        """
        Build a consolidated dict:
        {"uid": neo4j_id, "alias_uid": neo4j_id, ...}
        preserving one-to-one mapping even if several statements
        returned the same alias/key.
        """
        uid_map: dict[str, Any] = {}

        for res in batch_results:  # res keeps statement-order inside tx
            record: neo4j.Record = res.single()  # every sub-query returns 1 row
            for key in record.keys():  # uid, alias_uid, entity_id, …
                if key not in uid_map:  # first writer wins
                    uid_map[key] = record[key]

        return uid_map
