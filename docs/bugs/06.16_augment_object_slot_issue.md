# Augment object slot issue

## Overview

When `/augment-context` selects matching templates it fills all slots with `SlotFiller`. If the incoming text lacks information for certain slots (e.g. the `place` slot of `relocation_v1`), the LLM generates a value. The template is then rendered with this fabricated value which results in queries using nonexistent nodes.

Example request:

```json
{
  "text": "As they walk, Lyra fills the silence with cheerful chatter, and for the first time, Luthar finds himself thinking about more than just survival.",
  "chapter": 1,
  "stage": -1,
  "tags": []
}
```

Fragment of the log:

```
⚠️ Warning: top result score below threshold!
Query: As they walk, Lyra fills the silence...
- relocation_v1 (score: 0.7421)
...
MATCH (c:Character {id: "character-a255d71b"})-[r:AT_LOCATION]->(p:Place {id: "Oxford"})
```

Here `Oxford` was invented by the prompt. The graph does not contain this place, so the query either fails or returns no rows.

## Problem statement

Augment templates such as `relocation_aug_v1.j2` specify both subject and object IDs:

```cypher
MATCH (c:Character {id: "{{ character }}"})-[r:AT_LOCATION]->(p:Place {id: "{{ place }}"})
```

If the text lacks the `place` slot, `SlotFiller` attempts to generate one. The pipeline resolves the alias and embeds it into the query. This behaviour affects all templates where the augment Cypher filters on the object ID (`belief_ideology_aug_v1.j2`, `character_relation_aug_v1.j2`, `emotion_state_aug_v1.j2`, `ownership_aug_v1.j2`, `relocation_aug_v1.j2`, `title_acquisition_aug_v1.j2`, `vow_promise_aug_v1.j2`).

## Proposed fix

When retrieving facts from the graph we only need to know that a relation exists. The object should not be pre‑filled. Templates must match any target node.

Example correction for `relocation_aug_v1.j2`:

```cypher
MATCH (c:Character {id: "{{ character }}"})-[r:AT_LOCATION]->(p:Place)
```

The pipeline still keeps the `place` slot for extraction but ignores it in augment mode.

## Affected code

- Augment templates in `app/templates/cypher/*_aug_v1.j2`
- `AugmentPipeline.augment_context` uses these templates via `TemplateRenderer.render`
- `SlotFiller` generates slot values even when not present in text

## Fix plan

1. Update all augment templates to drop `{id: "{{ slot }}"}` from the object pattern.
2. Ensure `base_templates` still define slots for extraction.
3. Add tests verifying that augment queries no longer include object IDs when text lacks those slots.

## Can augment create aliases or entities?

`AugmentPipeline` resolves slot values via `IdentityService.resolve_bulk`. This step may propose creating a new alias or entity if the name is unknown. However these proposals are stored only in `AliasTask` objects. Unlike `/extract-save`, the augmentation flow does **not** call `commit_aliases`, so the tasks are never written to Weaviate or Neo4j. Queries are executed with `write=False` which routes them to a read replica. The earlier `chunk_mentions.j2` bug could produce writes, but that wrapper is now removed for augmentation.

If random slot values are invented by the LLM, the pipeline might still prepare alias tasks for them. Although they are discarded, this wastes time and risks confusion. To avoid such side effects all prompts should instruct the model to leave a slot empty when the text does not contain the required information.

## Template checklist

The following templates filtered by the object ID before the fix. We now drop only the object filter while keeping the subject intact:

- `belief_ideology_aug_v1.j2` – remove `{id: "{{ ideology }}"}` from the Ideology node.
- `character_relation_aug_v1.j2` – remove `{id: "{{ character_b }}"}` from the target character.
- `emotion_state_aug_v1.j2` – remove `{id: "{{ target }}"}` from the target.
- `ownership_aug_v1.j2` – remove `{id: "{{ item }}"}` from the Item node.
- `relocation_aug_v1.j2` – remove `{id: "{{ place }}"}` from the Place node.
- `title_acquisition_aug_v1.j2` – remove `{id: "{{ title_name }}"}` from the Title node.
- `vow_promise_aug_v1.j2` – remove `{id: "{{ goal }}"}` from the Goal node.

Templates already agnostic of the object ID (`membership_change_aug_v1.j2`, `trait_attribution_aug_v1.j2`, `death_event_aug_v1.j2`) need no change.

## Prompt updates

To guarantee read-only behaviour every augmentation prompt must tell the LLM not to invent missing data. A brief instruction like "If the text does not mention a value, output `null`" is sufficient. The service should reject any augmentation plan that would attempt to create aliases or entities.

## Implementation status

The augment templates now omit object IDs. `shared_instructions.j2` contains the new rule about returning `null` when information is missing. Unit tests cover both changes.

### Test cases

1. Rendering `relocation_aug_v1` must not include a place ID in the Cypher query.
2. `shared_instructions.j2` contains the new instruction about `null` fields.
