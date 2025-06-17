# Character relation augment issue

This note documents why `/augment-context` sometimes produced queries with raw character names and how the fix changes the pipeline.

## Observed log

When augmenting a text fragment the pipeline emitted a query with string names instead of IDs:

```
MATCH (a:Character {id: "Lyra"})-[r:`ALLY_OF`]->(b:Character {id: "Luthar"})
```

Neo4j warned that the relationship type `ALLY_OF` was unknown, but the real issue is that `Lyra` and `Luthar` are aliases, not stored graph IDs.

## Current implementation

The augmentation pipeline resolves entity references before rendering each Cypher template. The relevant portion:

```python
resolve = await self.identity_service.resolve_bulk(
    fill.slots,
    slot_defs=tpl.slots,
    chapter=chapter,
    chunk_id="aug",
    snippet=text,
)
alias_map.update(resolve.alias_map)
slot_fill = SlotFill(template_id=str(tpl.id), slots=resolve.mapped_slots, details=fill.details)
```
【F:app/services/pipeline.py†L292-L307】

`resolve_bulk` maps slot values to graph IDs. It uses the slot definition or a fallback table to pick the entity type and records an alias map so IDs can be translated back later:

```python
for field, raw_val in slots.items():
    if slot_defs is not None:
        slot_def = slot_defs.get(field)
        if not slot_def or not slot_def.is_entity_ref:
            continue
        etype = slot_def.entity_type or _FIELD_TO_ENTITY.get(field)
    else:
        etype = _FIELD_TO_ENTITY.get(field)
    if not etype:
        continue
    decision = self._resolve_single_sync(
        raw_name=str(raw_val),
        entity_type=etype,
        chapter=chapter,
        chunk_id=chunk_id,
        snippet=snippet,
    )
    mapped_slots[field] = decision["entity_id"]
    alias_map[decision["entity_id"]] = decision["alias_text"]
```
【F:app/services/identity_service.py†L164-L185】

The fallback mapping defines which slot names correspond to graph entities:

```python
_FIELD_TO_ENTITY = {
    "character": "CHARACTER",
    "source": "CHARACTER",
    "target": "CHARACTER",
}
```
【F:app/services/identity_service.py†L398-L406】

After executing a query the pipeline replaces any IDs found in the result rows with the original alias text:

```python
for row in result:
    for key, val in list(row.items()):
        if isinstance(val, str) and val in alias_map:
            row[key] = alias_map[val]
```
【F:app/services/pipeline.py†L329-L333】

## Applied fix

- Built-in templates now specify `entity_type` for every entity-ref slot.
- `IdentityService` exposes `alias_map` via `BulkResolveResult`, allowing `AugmentPipeline` to rewrite query results with readable names.
- The fallback `_FIELD_TO_ENTITY` table was trimmed to only common names.
- Unit tests cover the new slot definitions.

## Implementation summary

The fix touches three areas of the codebase:

1. **`IdentityService`** – `_resolve_bulk_sync` now records an `alias_map` for each resolved ID. The fallback table was simplified because templates specify `entity_type` directly.
2. **`AugmentPipeline`** – collects `alias_map` from every call to `resolve_bulk` and replaces IDs in returned rows with their original names.
3. **Tests** – extended to cover the new slot definitions and ID mapping behaviour.

## Template compatibility

The built‑in templates use various slot names. Those highlighted below already work with the current mapping, while others would require explicit `entity_type` in the slot definition:

| template | entity slots | compatible? |
|----------|--------------|-------------|
| `trait_attribution_v1` | `character` | ✅
| `membership_change_v1` | `character`, `faction` | ✅
| `character_relation_v1` | `character_a`, `character_b` | ✅
| `ownership_v1` | `character`, `item` | ✅
| `relocation_v1` | `character`, `place` | ✅
| `emotion_state_v1` | `character`, `target` | ✅
| `vow_promise_v1` | `character`, `goal` | ✅
| `death_event_v1` | `character` | ✅
| `belief_ideology_v1` | `character`, `ideology` | ✅
| `title_acquisition_v1` | `character`, `title_name` | ✅

Templates marked ❌ still work for extraction but will leave names in augment queries unless `entity_type` is specified.

### Analysis by template

* **trait_attribution_v1** – uses the `character` slot mapped to `CHARACTER`.
* **membership_change_v1** – slots `character` and `faction` reference `CHARACTER` and `FACTION`.
* **character_relation_v1** – slots `character_a` and `character_b` reference `CHARACTER`.
* **ownership_v1** – slots `character` and `item` reference `CHARACTER` and `ITEM`.
* **relocation_v1** – slots `character` and `place` reference `CHARACTER` and `LOCATION`.
* **emotion_state_v1** – slots `character` and `target` reference `CHARACTER`.
* **vow_promise_v1** – slots `character` and `goal` reference `CHARACTER` and `GOAL`.
* **death_event_v1** – slot `character` references `CHARACTER`.
* **belief_ideology_v1** – slots `character` and `ideology` reference `CHARACTER` and `IDEOLOGY`.
* **title_acquisition_v1** – slots `character` and `title_name` reference `CHARACTER` and `TITLE`.

## Requirements for new templates

1. Every slot that references a graph entity must set `is_entity_ref=True`.
2. Use an existing slot name from `_FIELD_TO_ENTITY` **or** provide `entity_type` in the `SlotDefinition` so `IdentityService` can resolve the alias.
3. Templates should expect IDs in Cypher and rely on the pipeline to map IDs back to names when returning rows.

## Planned improvement

1. Ensure all templates continue to declare `entity_type` for any new slots.
2. Gradually deprecate `_FIELD_TO_ENTITY` once external callers supply slot definitions with explicit types.
3. Keep tests up to date with any new template slots.

## Test cases

- Resolving any entity-ref slot returns a new ID and updates the alias map.
- Slots with explicit `entity_type` (e.g. `place` → `LOCATION`) resolve even if the name is absent from `_FIELD_TO_ENTITY`.
- Query results are rewritten using the alias map so callers see the original names.
- Backward compatibility: if a slot definition is missing `entity_type` but its name exists in `_FIELD_TO_ENTITY`, resolution still works.
