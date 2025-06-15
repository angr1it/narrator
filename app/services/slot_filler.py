from __future__ import annotations

from typing import Any, Dict, List, Optional
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, create_model, RootModel, Field


from core.slots.prompts import PROMPTS_ENV
from schemas.cypher import CypherTemplate
from schemas.slots import SlotFill
from utils.logger import get_logger
from utils.helpers.llm import call_llm_with_json_list


logger = get_logger(__name__)

TYPE_MAP = {
    "STRING": str,
    "INT": int,
    "FLOAT": float,
    "BOOL": bool,
}


def build_slot_model(template: CypherTemplate) -> type[BaseModel]:
    fields = {}
    for slot in template.slots.values():
        field_type: Any = TYPE_MAP[slot.type]
        if slot.required:
            default = ...
        else:
            field_type = field_type | type(None)
            default = None
        fields[slot.name] = (
            field_type,
            Field(default=default, description=slot.description or "..."),
        )
    fields["details"] = (str, Field(description="Как извлечены значения"))
    return create_model("ResponseItem", **fields)  # type: ignore[misc, call-overload]


class SlotFiller:
    """Извлекает и валидирует слоты для CypherTemplate."""

    def __init__(self, llm, callback_handler=None):
        self.llm = llm
        self.callback_handler = callback_handler

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

        class ResponseList(RootModel[List[ItemModel]]):  # type: ignore[misc, valid-type]
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

        trace_name = f"{self.__class__.__name__.lower()}.{phase}"
        models = call_llm_with_json_list(
            ItemModel,
            self.llm,
            prompt,
            callback_handler=self.callback_handler,
            run_name=trace_name,
            tags=[self.__class__.__name__],
        )
        return [m.model_dump() for m in models]

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
        fields = {}
        for s in template.slots.values():
            field_type: Any = TYPE_MAP[s.type]
            if s.required:
                default = ...
            else:
                field_type = field_type | type(None)
                default = None
            fields[s.name] = (field_type, default)
        DynamicModel = create_model("DynamicSlotsModel", **fields)  # type: ignore[misc, call-overload]
        filtered = {k: obj.get(k) for k in fields.keys() if k in obj}
        validated: BaseModel = DynamicModel(**filtered)
        return validated.model_dump()
