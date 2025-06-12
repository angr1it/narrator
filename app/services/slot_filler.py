from __future__ import annotations

from typing import Any, Dict, List, Optional
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, create_model, RootModel, Field

from core.slots.prompts import PROMPTS_ENV
from schemas.cypher import CypherTemplate
from schemas.slots import SlotFill
from utils.logger import get_logger
from config.langfuse import get_client, start_as_current_span

logger = get_logger(__name__)

TYPE_MAP = {
    "STRING": str,
    "INT": int,
    "FLOAT": float,
    "BOOL": bool,
}


def build_slot_model(template: CypherTemplate) -> type[BaseModel]:
    fields = {
        slot.name: (TYPE_MAP[slot.type], Field(description=slot.description or "..."))
        for slot in template.slots.values()
    }
    fields["details"] = (str, Field(description="Как извлечены значения"))
    return create_model("ResponseItem", **fields)


class SlotFiller:
    """Извлекает и валидирует слоты для CypherTemplate."""

    def __init__(self, llm, tracer=None):
        self.llm = llm
        self.tracer = tracer

    def fill_slots(self, template: CypherTemplate, text: str) -> List[SlotFill]:
        fillings = self._extract_slots(template, text)

        results: List[SlotFill] = []
        for s in fillings:
            validated = self._validate_and_cast(s, template)
            results.append(
                SlotFill(
                    template_id=str(template.id),
                    slots=validated,
                    details=s.get("details", ""),
                )
            )
        return results

    def _extract_slots(
        self, template: CypherTemplate, text: str
    ) -> List[Dict[str, Any]]:
        fillings = self._run_phase("extract", "extract_slots.j2", template, text)

        if self._needs_fallback(fillings, template):
            fillings = self._run_phase(
                "fallback", "fallback_slots.j2", template, text, previous=fillings
            )

        fillings = self._run_phase(
            "generate", "generate_slots.j2", template, text, previous=fillings
        )

        return fillings

    def _run_phase(
        self,
        phase: str,
        prompt_file: str,
        template: CypherTemplate,
        text: str,
        previous: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if phase != "extract" and not self._needs_fallback(previous, template):
            return previous or []

        slot_names = [s.name for s in template.slots.values()]
        ItemModel = build_slot_model(template)

        class ResponseList(RootModel[List[ItemModel]]):
            pass

        parser = PydanticOutputParser(pydantic_object=ResponseList)
        format_instructions = parser.get_format_instructions()

        tpl = PROMPTS_ENV.get_template(prompt_file)
        rendered = tpl.render(
            template=template,
            text=text,
            slots=template.slots.values(),
            slot_names=slot_names,
            previous=previous,
        )

        prompt = PromptTemplate(
            template=rendered + "\n\n{format_instructions}",
            input_variables=["format_instructions"],
            partial_variables={"format_instructions": format_instructions},
        )

        chain = prompt | self.llm | parser

        attempts = 0
        with start_as_current_span(name=f"slotfiller.{phase}") as span:
            while True:
                try:
                    result = chain.invoke({})
                    break
                except Exception as e:
                    attempts += 1
                    logger.error(f"Error in phase {phase}: {str(e)}")
                    if attempts > 1:
                        raise

            span.update(input={"phase": phase})
        return result.model_dump()

    @staticmethod
    def _needs_fallback(
        fillings: Optional[List[Dict[str, Any]]], template: CypherTemplate
    ) -> bool:
        if not fillings:
            return True
        required = {s.name for s in template.slots.values() if s.required}
        for obj in fillings:
            if not required.issubset(obj.keys()):
                return True
        return False

    def _validate_and_cast(
        self, obj: Dict[str, Any], template: CypherTemplate
    ) -> Dict[str, Any]:
        fields = {
            s.name: (TYPE_MAP[s.type], ... if s.required else None)
            for s in template.slots.values()
        }
        DynamicModel = create_model("DynamicSlotsModel", **fields)
        filtered = {k: obj.get(k) for k in fields.keys() if k in obj}
        validated: BaseModel = DynamicModel(**filtered)
        return validated.model_dump()
