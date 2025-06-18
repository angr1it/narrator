Вот полное актуальное описание Pydantic-моделей, связанных с `CypherTemplate`, включая все последние изменения, как они представлены в коде и используются в пайплайне:

---

## 🧩 Pydantic-модели шаблонов и связей

### 🔹 `SlotDefinition`

Описывает слот, который должен быть извлечён из текста:

```python
class SlotDefinition(BaseModel):
    name: str
    type: Literal["STRING", "INT", "FLOAT", "BOOL"]
    description: Optional[str] = None
    required: bool = True
    default: Optional[Union[str, int, float, bool]] = None
    # (опц.) признак того, что слот — это ссылка на сущность
    is_entity_ref: Optional[bool] = False
```

---

### 🔹 `GraphRelationDescriptor` (ранее `FactDescriptor`)

Формализует связь шаблона с графом:

```python
class GraphRelationDescriptor(BaseModel):
    predicate: str                   # тип связи: MEMBER_OF, HAS_TRAIT и т.д.
    subject: str                     # "$character" — имя слота
    object: Optional[str] = None     # "$faction"
    value: Optional[str] = None      # строковое значение (если не object)
```

Используется для:

- генерации `triple_text` (для вектора смысла `fact_vec`);
- определения `related_node_ids` для `MENTIONS`-связей с `ChunkNode`.

---

### 🔹 `CypherTemplateBase`

Главная модель, описывающая шаблон доменной связи:

```python
from enum import Enum
from templates import env

class TemplateRenderMode(str, Enum):
    EXTRACT = "extract"
    AUGMENT = "augment"

class CypherTemplateBase(BaseModel):
    name: str                             # slug шаблона
    version: str = "1.0.0"
    title: str
    description: str
    keywords: Optional[list[str]] = None
    category: Optional[str] = None

    slots: dict[str, SlotDefinition]
    graph_relation: Optional[GraphRelationDescriptor] = None
    fact_policy: Literal["none", "always"] = "always"
    attachment_policy: Literal["chunk", "raptor", "both"] = "chunk"

    extract_cypher: Optional[str] = None       # Jinja-файл вставки
    use_base_extract: bool = True              # оборачивать через chunk_mentions.j2

    augment_cypher: Optional[str] = None       # Jinja-файл выборки

    supports_extract: Optional[bool] = None    # вычисляется автоматически
    supports_augment: Optional[bool] = None

    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None
    representation: Optional[str] = None      # текст для векторизации

    default_confidence: float = 0.2

    return_map: dict[str, str]           # имена переменных → ноды/идентификаторы в графе

    def render(
        self,
        slots: dict,
        chunk_id: str,
        *,
        mode: TemplateRenderMode = TemplateRenderMode.EXTRACT,
    ) -> str:
        required = [slot.name for slot in self.slots.values() if slot.required]
        missing = [name for name in required if name not in slots]
        if missing:
            raise ValueError(f"Missing required slots: {missing}")

        context = dict(slots)
        context["chunk_id"] = chunk_id

        # triple-text: semantic string used for fact_vec
        if self.graph_relation:
            def pick(expr: str | None) -> str | None:
                return slots.get(expr[1:]) if expr and expr.startswith("$") else expr

            subject = pick(self.graph_relation.subject)
            object_ = pick(self.graph_relation.object)
            context["triple_text"] = f"{subject} {self.graph_relation.predicate} {object_}"
            context["related_node_ids"] = [
                val for val in [subject, object_] if val is not None
            ]

        # fallback if template_id missing
        context["template_id"] = self.name

        cypher_name = (
            self.extract_cypher if mode is TemplateRenderMode.EXTRACT else self.augment_cypher
        )
        if mode is TemplateRenderMode.AUGMENT:
            self.validate_augment()
        else:
            self.validate_extract()
            if self.use_base_extract and not cypher_name.startswith("chunk_"):
                cypher_name = "chunk_mentions.j2"
                context["template_body"] = self.extract_cypher

        template = env.get_template(cypher_name)
        return template.render(**context)
```

---

### 🔹 `CypherTemplate`

Добавляет UUID:

```python
class CypherTemplate(CypherTemplateBase):
    id: uuid.UUID
```

---

### 🔹 `RenderedCypher`

Результат отрисовки шаблона:

```python
class RenderedCypher(BaseModel):
    template_id: str
    content_cypher: str                   # основная часть с MERGE
    alias_cypher: Optional[str] = None    # если нужен alias
    relation_cypher: Optional[str] = None # ранее: fact_cypher
    triple_text: str                      # строка вида "Aren MEMBER_OF Night Front"
```

---

Если хочешь, могу предложить автоматическую генерацию JSON-схемы (`.schema_json()`), экспорт моделей в Swagger/OpenAPI или сгенерировать docstring-примеры использования каждого класса.
