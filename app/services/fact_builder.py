from __future__ import annotations
from typing import Any, Dict

from jinja2 import Environment
from pydantic import BaseModel

from schemas.cypher import CypherTemplate
from schemas.stage import StageEnum, stage_to_confidence


class FactPlan(BaseModel):
    cypher: str


class FactBuilder:
    def __init__(self, jinja_env: Environment):
        """
        Parameters
        ----------
        jinja_env : Environment
            Jinja2-окружение для рендера versioned_fact.j2.
        """
        self.jinja_env = jinja_env

    def make(
        self,
        template: CypherTemplate,
        slots: Dict[str, Any],
        uids: Dict[str, str],
        meta: Dict[str, Any],
        stage: StageEnum = StageEnum.brainstorm,
    ) -> FactPlan:
        """
        Рендерит versioned_fact.j2.
        Parameters
        ----------
        template : CypherTemplate
            Шаблон.
        slots : Dict[str, Any]
            Заполненные значения.
        uids : Dict[str, str]
            UIDs (subject, object, rel).
        meta : Dict[str, Any]
            Внешние мета-данные (chapter, iso_date и т.д.).

        Returns
        -------
        FactPlan
            Готовый Cypher-запрос.
        """
        tpl = self.jinja_env.get_template("versioned_fact.j2")
        fact_context = {
            "fact": {
                "predicate": template.fact_descriptor.predicate,
                "subject": uids["subject_uid"],
                "object": uids.get("object_uid"),
                "value": slots.get(template.fact_descriptor.value[1:], None),
            },
            "chapter": meta.get("chapter"),
            "to_chapter": meta.get("to_chapter"),
            "iso_date": meta.get("iso_date"),
            "summary": meta.get("summary"),
            "tags": meta.get("tags"),
            "stage": stage.value,
            "confidence": stage_to_confidence(stage),
            "asserts_node_id": uids.get("subject_uid"),
            "asserts_rel_id": uids.get("rel_uid"),
        }
        cypher_query = tpl.render(**fact_context)
        return FactPlan(cypher=cypher_query)
