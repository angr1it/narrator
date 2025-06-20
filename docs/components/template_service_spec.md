# 📘 Техническое задание: `TemplateService`

`TemplateService` отвечает за хранение и поиск объектов `CypherTemplate`. Сервис вынесен в отдельный репозиторий и взаимодействует с оркестратором через gRPC.

## Контракт
Все сообщения и методы описаны в каталоге [`proto/`](../../proto/). Основные структуры:

- **Template** – описание шаблона (имя, слоты, `graph_relation`, `return_map` и т.д.)
- **SlotDefinition** – схема отдельного слота

### Сервис
```proto
service TemplateService {
    rpc GetTemplate(GetTemplateRequest) returns (Template);
    rpc FindTemplates(FindTemplatesRequest) returns (FindTemplatesResponse);
}
```

`GetTemplate` возвращает шаблон по идентификатору. `FindTemplates` выполняет семантический поиск по тексту и категории.

## Компиляция
Протоколы компилируются командой из корня проекта:

```bash
python -m grpc_tools.protoc -Iproto \
    --python_out=./proto_gen \
    --grpc_python_out=./proto_gen \
    proto/services/template_service.proto
```
