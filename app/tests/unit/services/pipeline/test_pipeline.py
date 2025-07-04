"""Tests for the ExtractionPipeline orchestration logic.

Only lightweight dummy services are used to validate that the pipeline calls
its dependencies correctly and returns the expected plan.
"""

import pytest
from schemas.stage import StageEnum
from schemas.slots import SlotFill

from services.pipeline import ExtractionPipeline, AugmentPipeline
from services.template_renderer import TemplateRenderer
from schemas.cypher import (
    CypherTemplate,
    SlotDefinition,
    GraphRelationDescriptor,
    TemplateRenderMode,
)
from uuid import uuid4
from pydantic import BaseModel, ValidationError


@pytest.mark.asyncio
async def test_pipeline_simple(
    sample_template,
    template_renderer,
    slot_fill,
    graph_proxy,
    identity_service,
    raptor_index,
    jinja_env,
):
    class FakeTemplateService:
        async def top_k_async(self, text, k=3, *, alpha=0.5):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor_index,
    )

    result = await pipeline.extract_and_save(
        "hello", chapter=1, stage=StageEnum.outline
    )
    assert result["raptor_node_id"] == "rn-test"
    assert raptor_index.inserted[0][0] == "hello"
    merged = []
    for call in graph_proxy.calls:
        if isinstance(call[0], list):
            merged.extend(call[0])
    assert any("MERGE" in c for c in merged)
    update = [
        c for c, _ in graph_proxy.calls if isinstance(c, str) and "raptor_node_id" in c
    ]
    assert update, "raptor id update not executed"


@pytest.mark.asyncio
async def test_pipeline_returns_details(
    sample_template,
    template_renderer,
    graph_proxy,
    identity_service,
    raptor_index,
):
    class FakeTemplateService:
        async def top_k_async(self, text, k=3, *, alpha=0.5):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [
                SlotFill(
                    template_id=str(template.id),
                    slots={"character": "c"},
                    details="why",
                )
            ]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor_index,
    )

    result = await pipeline.extract_and_save("txt", chapter=1)
    assert result["relationships"][0]["details"] == "why"


@pytest.mark.asyncio
async def test_pipeline_deterministic_chunk_id(
    sample_template,
    template_renderer,
    slot_fill,
    graph_proxy,
    identity_service,
    raptor_index,
):
    """Chunk ID should be stable for identical text."""

    class FakeTemplateService:
        async def top_k_async(self, text, k=3, *, alpha=0.5):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor_index,
    )

    res1 = await pipeline.extract_and_save("hello", chapter=1)
    res2 = await pipeline.extract_and_save("hello", chapter=1)
    assert res1["chunk_id"] == res2["chunk_id"]


@pytest.mark.asyncio
async def test_pipeline_converts_raptor_id_to_str(
    sample_template,
    template_renderer,
    graph_proxy,
    identity_service,
    jinja_env,
):
    class NonStrId:
        def __str__(self) -> str:
            return "rn-test"

    class FakeRaptor:
        def insert_chunk(self, text: str, triple_text: str) -> NonStrId:
            return NonStrId()

    class FakeTemplateService:
        async def top_k_async(self, text, k=3, *, alpha=0.5):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [
                SlotFill(
                    template_id=str(template.id), slots={"character": "c"}, details=""
                )
            ]

    raptor = FakeRaptor()
    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor,
    )

    await pipeline.extract_and_save("txt", chapter=1)
    update = [p for c, p in graph_proxy.calls if "raptor_node_id" in c][0]
    assert isinstance(update["rid"], str)


@pytest.mark.asyncio
async def test_pipeline_splits_cypher_at_with_star(
    graph_proxy, identity_service, raptor_index, jinja_env
):
    """Queries containing ``WITH *`` should run as two statements."""
    jinja_env.loader.mapping["chunk_mentions.j2"] = (
        "{% include template_body %}\nWITH *\n"
        "MATCH (chunk:Chunk {id: '{{ chunk_id }}'})\n"
        "  MATCH (x1 {id: '{{ related_node_ids[0] }}'})\n"
        "  MERGE (chunk)-[:MENTIONS]->(x1)"
    )
    jinja_env.loader.mapping["full.j2"] = (
        "MERGE (c:Character {id: '{{ character }}'})\n"
        "MERGE (t:Trait {id: '{{ trait }}'})\n"
        "MERGE (c)-[:HAS_TRAIT]->(t)\n"
        "{% set related_node_ids=[character, trait] %}"
    )
    template = CypherTemplate(
        id=uuid4(),
        name="full",
        title="t",
        description="d",
        slots={
            "character": SlotDefinition(name="character", type="STRING"),
            "trait": SlotDefinition(name="trait", type="STRING"),
        },
        extract_cypher="full.j2",
        use_base_extract=True,
        graph_relation=GraphRelationDescriptor(
            predicate="HAS", subject="$character", object="$trait"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c", "trait": "t"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(self, text, k=3, *, alpha=0.5):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        raptor_index=raptor_index,
    )

    await pipeline.extract_and_save("txt", chapter=1)

    batch = [c for c in graph_proxy.calls if isinstance(c[0], list)][0][0]
    assert len(batch) == 2
    assert batch[0].startswith("MERGE")
    assert batch[1].startswith("MATCH")


@pytest.mark.asyncio
async def test_augment_pipeline_splits_cypher_at_with_star(
    graph_proxy, identity_service, jinja_env
):
    """Augment queries containing ``WITH *`` should run as two statements."""
    jinja_env.loader.mapping["aug.j2"] = (
        "MATCH (c:Character {id: '{{ character }}'}) WITH * MATCH (c) RETURN c"
    )

    template = CypherTemplate(
        id=uuid4(),
        name="aug",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="aug.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(
            self, text, k=3, *, alpha=0.5, mode=TemplateRenderMode.AUGMENT
        ):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=graph_proxy,
    )

    await pipeline.augment_context("txt", chapter=1)

    batch = [c for c in graph_proxy.calls if isinstance(c[0], list)][0][0]
    assert len(batch) == 2
    assert batch[0].startswith("MATCH")
    assert batch[1].startswith("MATCH")


@pytest.mark.asyncio
async def test_augment_pipeline_skips_failed_template(
    graph_proxy, identity_service, jinja_env
):
    """Pipeline should continue if one template fails to fill slots."""
    jinja_env.loader.mapping.update(
        {
            "bad.j2": "MATCH (c:Character {id: '{{ character }}'}) RETURN c",
            "ok.j2": "MATCH (c:Character {id: '{{ character }}'}) RETURN c",
        }
    )
    bad_tpl = CypherTemplate(
        id=uuid4(),
        name="bad",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="bad.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    ok_tpl = CypherTemplate(
        id=uuid4(),
        name="ok",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="ok.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(ok_tpl.id),
        slots={"character": "c"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(
            self, text, k=3, *, alpha=0.5, mode=TemplateRenderMode.AUGMENT
        ):
            return [bad_tpl, ok_tpl]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            if template is bad_tpl:

                class M(BaseModel):
                    a: str

                try:
                    M()
                except ValidationError as e:
                    raise e
            return [slot_fill]

    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=graph_proxy,
    )

    await pipeline.augment_context("txt", chapter=1)

    assert len(graph_proxy.calls) == 1
    assert graph_proxy.calls[0][0].startswith("MATCH")


@pytest.mark.asyncio
async def test_augment_pipeline_rewrites_ids(jinja_env):
    """Returned rows should use alias names and stage strings."""

    class LocalGraphProxy:
        def __init__(self):
            self.calls = []

        async def run_query(self, cypher, params=None, *, write=True):
            self.calls.append((cypher, params))
            return [
                {
                    "relation": "REL",
                    "target": "character-12345678",
                    "meta_draft_stage": 1,
                }
            ]

        async def run_queries(self, cyphers, params_list=None, *, write=True):
            self.calls.append((list(cyphers), params_list))
            return [
                {
                    "relation": "REL",
                    "target": "character-12345678",
                    "meta_draft_stage": 1,
                }
            ]

    jinja_env.loader.mapping.update(
        {
            "name_aug.j2": "RETURN 'REL' AS relation, 1 AS meta_draft_stage, '{{ target }}' AS target"
        }
    )

    template = CypherTemplate(
        id=uuid4(),
        name="aug",  # pragma: no cover - simple template
        title="t",
        description="d",
        slots={
            "character": SlotDefinition(name="character", type="STRING"),
            "target": SlotDefinition(
                name="target",
                type="STRING",
                is_entity_ref=True,
                entity_type="CHARACTER",
            ),
        },
        augment_cypher="name_aug.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="$target"
        ),
        return_map={"target": "Character"},
    )

    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c", "target": "t"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(
            self, text, k=3, *, alpha=0.5, mode=TemplateRenderMode.AUGMENT
        ):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    class AliasService:
        def __init__(self):
            self.lookups = []

        async def resolve_bulk(
            self, slots, *, slot_defs=None, chapter, chunk_id, snippet
        ):
            from services.identity_service import BulkResolveResult

            return BulkResolveResult(
                mapped_slots={"character": "id1", "target": "character-12345678"},
                alias_tasks=[],
                alias_map={"id1": "Lyra"},
            )

        async def get_alias_map(self, entity_ids):
            self.lookups.append(entity_ids)
            return {"character-12345678": "Luthar"}

        async def commit_aliases(self, alias_tasks):
            return []

    svc = AliasService()
    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=svc,
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=LocalGraphProxy(),
    )

    result = await pipeline.augment_context("txt", chapter=1)

    row = result["context"]["rows"][0]
    assert row["source"] == "Lyra"
    assert row["target"] == "Luthar"
    assert row["meta_draft_stage"] == "draft_1"
    assert "triple_text" in row
    assert svc.lookups == [["character-12345678"]]


@pytest.mark.asyncio
async def test_augment_pipeline_fills_missing_value_with_alias(jinja_env):
    """Pipeline should use alias map when cypher returns null value."""

    class LocalGraphProxy:
        async def run_query(self, cypher, params=None, *, write=True):
            return [
                {
                    "relation": "AT_LOCATION",
                    "value": None,
                    "meta_draft_stage": 1,
                }
            ]

        async def run_queries(self, cyphers, params_list=None, *, write=True):
            return [
                {
                    "relation": "AT_LOCATION",
                    "value": None,
                    "meta_draft_stage": 1,
                }
            ]

    jinja_env.loader.mapping.update(
        {
            "null_aug.j2": "RETURN 'AT_LOCATION' AS relation, null AS value, 1 AS meta_draft_stage"
        }
    )

    template = CypherTemplate(
        id=uuid4(),
        name="aug",
        title="t",
        description="d",
        slots={
            "character": SlotDefinition(
                name="character",
                is_entity_ref=True,
                entity_type="CHARACTER",
                type="STRING",
            ),
            "place": SlotDefinition(
                name="place", is_entity_ref=True, entity_type="PLACE", type="STRING"
            ),
        },
        augment_cypher="null_aug.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="AT_LOCATION",
            subject="$character",
            value="$place",
            object="$place",
        ),
        return_map={"p": "Place"},
    )

    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c", "place": "p"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(
            self, text, k=3, *, alpha=0.5, mode=TemplateRenderMode.AUGMENT
        ):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    class AliasService:
        async def resolve_bulk(
            self, slots, *, slot_defs=None, chapter, chunk_id, snippet
        ):
            from services.identity_service import BulkResolveResult

            return BulkResolveResult(
                mapped_slots={"character": "id1", "place": "place-12345678"},
                alias_tasks=[],
                alias_map={"id1": "Lyra", "place-12345678": "Rivia"},
            )

        async def get_alias_map(self, entity_ids):
            return {}

        async def commit_aliases(self, alias_tasks):
            return []

    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=AliasService(),
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=LocalGraphProxy(),
    )

    result = await pipeline.augment_context("txt", chapter=1)

    row = result["context"]["rows"][0]

    assert row["source"] == "Lyra"
    assert row["value"] == "Rivia"
    assert row["target"] == "Rivia"
    assert row["meta_draft_stage"] == "draft_1"
    assert "triple_text" in row
