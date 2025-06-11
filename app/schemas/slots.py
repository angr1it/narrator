from typing import Any

from pydantic import BaseModel


class SlotFill(BaseModel):
    template_id: str
    slots: dict[str, Any]
    details: str
