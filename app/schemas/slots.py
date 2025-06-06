from pydantic import BaseModel


class SlotFill(BaseModel):
    template_id: str
    slots: dict[str, any]
    details: str
