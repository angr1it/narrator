from __future__ import annotations
from functools import lru_cache
from typing import Dict, Any
from jinja2 import Environment
from pydantic import BaseModel

from schemas.cypher import CypherTemplate
from schemas.slots import SlotFill


class RenderPlan(BaseModel):
    template_id: str
    content_cypher: str
    return_keys: Dict[str, str]
    triple_text: str
    related_node_ids: list[str]
    details: str


class TemplateRenderer:
    """
    TemplateRenderer рендерит Jinja2-шаблоны в готовый Cypher.

    Сначала слоты из :class:`SlotFill` объединяются с ``meta`` и передаются в
    ``CypherTemplate.render``.  ``chunk_id`` обязательно должен присутствовать в
    ``meta`` — базовый шаблон ``chunk_mentions.j2`` формирует связи ``MENTIONS``.

    Возвращается :class:`RenderPlan` с самой строкой Cypher, картой ключей и
    текстовым представлением триплета для последующего вычисления векторов.
    """

    def __init__(self, jinja_env: Environment):
        """
        Parameters
        ----------
        jinja_env : Environment
            Jinja2-окружение, настроенное на каталог с Cypher-шаблонами.
        """
        self.jinja_env = jinja_env

    def render(
        self,
        template: CypherTemplate,
        slot_fill: SlotFill,
        meta: Dict[str, Any],
    ) -> RenderPlan:
        """
        Рендерит доменный Cypher, подставляя слоты и мета-данные.

        ``meta`` расширяет слоты и обязательно содержит ``chunk_id``. В результа
        те формируется строка Cypher с уже подключённым ``chunk_mentions.j2``.

        Parameters
        ----------
        template : CypherTemplate
            Описание шаблона (с ID, cypher-файлом и return_map).
        slot_fill : SlotFill
            Объект со слотами и деталями извлечения.
        meta : Dict[str, Any]
            Внешний контекст (например, chapter, fragment_id).

        Returns
        -------
        RenderPlan
            Готовый Cypher-запрос + карта ожидаемых возвращаемых значений.
        """
        context = {**slot_fill.slots, **meta, "details": slot_fill.details}
        chunk_id = meta.get("chunk_id")
        if not chunk_id:
            raise ValueError("chunk_id is required for rendering")
        cypher_query = template.render(context, chunk_id)

        triple_text = ""
        related_node_ids: list[str] = []
        if template.graph_relation:

            def pick(expr: str | None) -> str | None:
                if expr and expr.startswith("$"):
                    return context.get(expr[1:])
                return expr

            subject = pick(template.graph_relation.subject)
            obj = pick(template.graph_relation.object)
            triple_text = (
                f"{subject} {template.graph_relation.predicate} " f"{obj}"
            )  # noqa: E501
            related_node_ids = [v for v in [subject, obj] if v is not None]

        # template.return_map должно быть заранее определено
        # (например, в YAML-описании)
        if not template.return_map:
            raise ValueError(f"Template {template.id} is missing return_map")

        return RenderPlan(
            template_id=str(template.id),
            content_cypher=cypher_query,
            return_keys=template.return_map,
            triple_text=triple_text,
            related_node_ids=related_node_ids,
            details=slot_fill.details,
        )


@lru_cache()
def get_template_renderer(jinja_env: Environment | None = None) -> TemplateRenderer:
    """Return a cached TemplateRenderer instance."""
    from templates import env

    return TemplateRenderer(jinja_env or env)
