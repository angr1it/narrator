# Удалённые документы о `Fact`

В июне 2025 года модель хранения истории была изменена: вместо отдельной сущности
`:Fact` версия графа определяется через `ChunkNode` и `RaptorNode`. Ниже приведён
краткий обзор удалённых файлов и причина их исключения из репозитория.

## cypher_template_and_fact.md
Описывал работу `CypherTemplate` и универсального узла `Fact` для версионирования
утверждений. В документе приводилась схема `Fact`, примеры шаблонов с
`fact_descriptor` и алгоритм закрытия старых версий через `PRECEDED_BY`.

**Причина удаления:** информация устарела — версия от июня 2025 больше не
создаёт `:Fact`, а хранит связи напрямую.

## cypher_template_spec_v2.md
Содержал формальное описание модели `CypherTemplate` с полем
`fact_descriptor`. Приводились JSON‑примеры и процедура рендеринга шаблонов.

**Причина удаления:** дублирует сведения из актуального
`pydantic_models_for_cypher_template.md`, но использует старую терминологию.

## fact_examples.md
Пример пошагового сценария, где изменения альянса персонажа сохранялись как
несколько `Fact`‑нод с версионированием. Также описывал использование `Fact` при
аугментации контекста.

**Причина удаления:** противоречит новой схеме без `Fact`‑нод; примеры больше не
соответствуют текущей реализации.

## raptor_pipeline_architecture.md
Документировал ранний вариант пайплайна `RAPTOR`, в котором присутствовал
компонент `FactBuilder` и создание `(:Fact)`. Описывал взаимодействие служб и
идентификацию сущностей через `Alias`.

**Причина удаления:** архитектура переработана, `FactBuilder` устранён, связи
строятся непосредственно от `ChunkNode`.

## specification.md
Старое техническое задание API. Эндпойнт `extract-save` описывал шаг по созданию
`versioned Fact`, а многие примеры ссылались на шаблон `versioned_fact.j2`.

**Причина удаления:** документ устарел и дублирует более свежие файлы в `docs/`;
новая схема не использует отдельный `Fact`.
