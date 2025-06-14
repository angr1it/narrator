# 📚 Примеры работы пайплайна `extract-save`

## 🧩 Пример 1: Изменение альянса персонажа

**Входной текст:**

> «В главе 15 Арен разрывает клятву с Домом Зари, заявляя, что их учения были ложью. Он теперь открыто симпатизирует Северному фронту.»

**Метаданные:** `chapter=15`, `tags=["разрыв", "альянс", "раскрытие"]`

### Этапы нового пайплайна

1. **Создание `ChunkNode`.**
   ```cypher
   CREATE (c:Chunk {
     id: $chunk_id,
     text: $text,
     chapter: 15,
     draft_stage: "brainstorm",
     tags: ["разрыв", "альянс", "раскрытие"],
     raptor_node_id: NULL
   })
   ```
2. **Поиск шаблонов.** `TemplateService` находит `membership_change.j2` по вектору текста.
3. **Заполнение слотов.** `SlotFiller` извлекает:
   ```json
   {"character": "Арен", "faction": "Северный фронт"}
   ```
   и
   ```json
   {"character": "Арен", "faction": "Дом Зари"}
   ```
4. **IdentityService.** Все имена сопоставляются с `entity_id`, создаются записи `AliasRecord` с `chunk_id`.
5. **Raptor слой.** `flat_raptor.insert_chunk(text_vec, fact_vec)` возвращает `raptor_node_id`, который записывается в поле `ChunkNode.raptor_node_id`.
6. **Рендер и выполнение Cypher.** Шаблон генерирует связи `MEMBER_OF` и `MENTIONS` через `chunk_mentions.j2`:
   ```cypher
   MERGE (a:Character {id: "UUID-123"})
   MERGE (b:Faction {id: "UUID-456"})
   MERGE (a)-[:MEMBER_OF {chapter: 15, chunk_id: $chunk_id}]->(b)
   MATCH (chunk:Chunk {id: $chunk_id})
   MERGE (chunk)-[:MENTIONS]->(a)
   MERGE (chunk)-[:MENTIONS]->(b)
   ```
7. **GraphProxy.** Выполняет весь Cypher в одной транзакции.

Итогом является `chunk_id` с привязанными сущностями и `raptor_node_id` для дальнейшего версионирования.

---

## 📤 Пример 2: Аугментация на основе существующих связей

**Входной текст:**

> «Эрик колеблется. Он больше не уверен, действительно ли его решения — его собственные. Что бы сказала Миранда?»

**Метаданные:** `chapter=19`, `tags=["конфликт", "решение"]`

1. `TemplateService` подбирает SELECT-шаблоны (`has_trait_select`, `influence_select`).
2. `SlotFiller` заполняет слоты:
   ```json
   {"subject": "Миранда", "chapter": 19}
   {"subject": "Миранда", "target": "Эрик", "chapter": 19}
   ```
3. Шаблоны формируют Cypher-запросы без участия `Fact`-нод. Данные выбираются из прямых связей:
   ```cypher
   MATCH (p:Character {id: "UUID_M"})-[:HAS_TRAIT]->(t:Trait)
   WHERE t.chapter <= 19
   RETURN t.name
   ```
4. Полученные сведения используются для генеративной подсказки в сцене.
