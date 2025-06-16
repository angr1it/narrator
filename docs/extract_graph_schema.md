# `/extract` Graph Schema

This document describes in detail what nodes and edges the service creates during the `/extract` pipeline. It is focused on how entities become connected in the graph so that we can later reconsider the `MENTIONS` edges.

---

## ✅ Overview of the stage

1. **Chunk creation** – a `:Chunk` node is created with the raw text and metadata.
2. **Template search** – `TemplateService` selects top templates by text similarity.
3. **Slot filling** – `SlotFiller` extracts values according to the template schema.
4. **Alias resolution** – `IdentityService` maps names to stable `entity_id` and stores `AliasRecord` objects in Weaviate.
5. **Cypher rendering** – `TemplateRenderer` renders domain Cypher. The wrapper `chunk_mentions.j2` injects a `MATCH (chunk)` block and `MENTIONS` edges.
6. **Graph execution** – `GraphProxy` runs the Cypher batch creating nodes and edges in Neo4j.
7. **Raptor update** – `FlatRaptorIndex.insert_chunk` calculates embeddings and the returned `raptor_node_id` is stored on the `Chunk` node.

---

## 📦 Nodes written to Neo4j

- **`Chunk`** – central point that stores the fragment text and metadata:
  ```cypher
  CREATE (c:Chunk {
    id: $chunk_id,
    text: $text,
    chapter: $chapter,
    draft_stage: $stage,
    tags: $tags,
    raptor_node_id: NULL
  })
  ```
- **Domain nodes** – created or matched by templates. Examples include `:Character`, `:Faction`, `:Location` and others. Their properties depend on the template.
- **Relationship nodes** – optional. If a domain template models a relation as a node, that node is also linked (see example below).

The `RaptorNode` lives in Weaviate, not in Neo4j. Only its ID is saved on `Chunk.raptor_node_id`.

---

## 🔗 Edges created

1. **Domain edges** – the core relationship expressed by the template, e.g.
   ```cypher
   MERGE (a:Character {id:"UUID-1"})
   MERGE (b:Faction {id:"UUID-2"})
   MERGE (a)-[:MEMBER_OF {
       chapter: $chapter,
       template_id: "membership_change",
       chunk_id: $chunk_id,
       draft_stage: $stage,
       confidence: 0.2
   }]->(b)
   ```
   Properties may vary but always include `chunk_id` so the edge can be traced back to the originating fragment.
2. **`MENTIONS` edges** – automatically added from the `Chunk` to every domain node referenced in the template:
   ```cypher
   MATCH (chunk:Chunk {id:"$chunk_id"})
   MATCH (a {id:"UUID-1"})
   MATCH (b {id:"UUID-2"})
   MERGE (chunk)-[:MENTIONS]->(a)
   MERGE (chunk)-[:MENTIONS]->(b)
   ```
   If the template introduces a relation node (e.g. `(:Event)`), it is also linked via `MENTIONS`. This mechanism is implemented in `chunk_mentions.j2` and ensures that all involved entities can be retrieved through the `Chunk`.
3. **Raptor link** – after embeddings are calculated, the returned ID is stored on the chunk:
   ```cypher
   MATCH (c:Chunk {id:$cid}) SET c.raptor_node_id=$rid
   ```
   No explicit edge is created.

The result is a star-shaped pattern where the `Chunk` node is in the centre and connects to every mentioned entity via `MENTIONS`, while domain edges form the semantic relations between those entities.

---

## 🧩 Why `MENTIONS` accumulate

Every time a character or faction appears in a fragment, the wrapper adds a `MENTIONS` edge from that fragment's `Chunk` to the corresponding node. Main characters therefore accumulate hundreds of such edges across chapters. Reducing or rethinking these edges could help keep the graph sparse while preserving traceability.

---

## 🤔 Что если `MENTIONS` вести только к субъекту

Иногда шаблон описывает связь вида `(:Character)-[:MEMBER_OF]->(:Faction)`.
Сейчас `chunk_mentions.j2` создаёт две связи `MENTIONS` — и к персонажу, и к
фракции. Идея: оставлять прямую связь только к субъекту (`Character`) и
переходить к объекту через доменное ребро.

**Плюсы**

* вдвое меньше рёбер `MENTIONS` для бинарных отношений;
* проще искать все фрагменты, где персонаж был инициатором действия.

**Минусы**

* дополнительные прыжки при поиске упоминаний объекта: понадобится
  `MATCH (chunk)-[:MENTIONS]->(c)-[:MEMBER_OF]->(f)`;
* не все шаблоны имеют явный субъект — для событий или симметричных отношений
  придётся всё равно связывать оба узла или заводить отдельный `:Event`.

Вывод: подход может снизить количество связей, но усложнит запросы и потребует
доработки схемы для случаев без чётко выраженного агента действия.

