from __future__ import annotations
from typing import Dict, Any
from jinja2 import Environment
from pydantic import BaseModel

from schemas.cypher import CypherTemplate
from schemas.slots import SlotFill


class RenderPlan(BaseModel):
    template_id: str
    content_cypher: str
    return_keys: Dict[
        str, str
    ]  # e.g., {"subject_uid": "subject_uid", "rel_uid": "rel_uid"}


class TemplateRenderer:
    """
    TemplateRenderer рендерит Jinja2-шаблон на основе слотов и мета-данных.
    Он возвращает RenderPlan, включающий:
      • готовый Cypher-запрос (строку),
      • карту, какие значения нужно вернуть из GraphProxy.
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
        cypher_query = template.render(**slot_fill.slots, **meta)

        # template.return_map должно быть заранее определено (например, в YAML-описании)
        if not template.return_map:
            raise ValueError(f"Template {template.id} is missing return_map")

        return RenderPlan(
            template_id=template.id,
            content_cypher=cypher_query,
            return_keys=template.return_map,
        )
