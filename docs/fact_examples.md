# 📚 Примеры использования Fact-ноды с версионированием

## 🧩 Пример 1: Изменение альянса и раскрытие правды

**Входной текст:**

> «В главе 15 Арен разрывает клятву с Домом Зари, заявляя, что их учения были ложью. Он теперь открыто симпатизирует Северному фронту.»

**Метаданные:** `chapter=15`, `tags=["разрыв", "альянс", "раскрытие"]`

### Этапы:

#### 1. Шаблоны:
- `break_faction_allegiance` → старый союз
- `declare_loyalty` → новый союз

#### 2. Извлечённые `slots`:
- `character=Арен`, `faction=Дом Зари`
- `character=Арен`, `faction=Северный фронт`

#### 3. Решение LLM:
> _Сохранить оба как versioned facts? → ✅ Да_

#### 4. Вставка двух фактов:

```json
{
  "subject_id": "Арен",
  "object_id": "Дом Зари",
  "type": "MEMBER_OF",
  "value": "прекращено",
  "chapter": 15,
  "summary": "Арен покинул Дом Зари"
}
```

```json
{
  "subject_id": "Арен",
  "object_id": "Северный фронт",
  "type": "MEMBER_OF",
  "value": "новый союз",
  "chapter": 15,
  "summary": "Арен присоединился к Северному фронту"
}
```

---

## 📤 Пример 2: Аугментация по фактам влияния и черт персонажа

**Входной текст:**

> «Эрик колеблется. Он больше не уверен, действительно ли его решения — его собственные. Что бы сказала Миранда?»

**Метаданные:** `chapter=19`, `tags=["конфликт", "решение"]`

### Этапы:

#### 1. Вопросы от LLM:
- Какие черты есть у Миранды?
- Подчинён ли сейчас Эрик её влиянию?

#### 2. SELECT-шаблоны:
- `select_fact_trait` → `HAS_TRAIT`
- `select_fact_influence` → `INFLUENCE`

#### 3. Заполнение `slots`:

```json
{ "subject": "Миранда", "chapter": 19 }
{ "subject": "Миранда", "target": "Эрик", "chapter": 19 }
```

#### 4. Cypher-запросы:

```cypher
MATCH (f:Fact)
WHERE f.subject_id = 'Миранда'
  AND f.type = 'HAS_TRAIT'
  AND f.from_chapter <= 19
  AND (f.to_chapter IS NULL OR f.to_chapter >= 19)
RETURN f
```

```cypher
MATCH (f:Fact)
WHERE f.subject_id = 'Миранда'
  AND f.object_id = 'Эрик'
  AND f.type = 'INFLUENCE'
  AND f.from_chapter <= 19
  AND (f.to_chapter IS NULL OR f.to_chapter >= 19)
RETURN f
```

#### 5. Результат:

```json
{
  "context": {
    "traits": {
      "Миранда": ["телепатия"]
    },
    "influence": {
      "Миранда → Эрик": "контроль через телепатию (глава 18–...)"
    }
  }
}
```

> Используется в генеративной подстановке для LLM в сцене главы 19.