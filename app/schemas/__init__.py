from fastapi_camelcase import CamelModel


class ExtractSaveIn(CamelModel):
    chapter: int
    tags: list[str] = []
    text: str


class ExtractSaveOut(CamelModel):
    status: str
    cypher_batch: list[str]
    trace_id: str


class AugmentCtxIn(ExtractSaveIn): ...


class AugmentCtxOut(CamelModel):
    context: list[str, any]
    trace_id: str
