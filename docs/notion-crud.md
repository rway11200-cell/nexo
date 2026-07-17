# Notion CRUD

The generic Notion API lets an AI discover and administer any database shared with the Notion integration.

## Setup

1. Open the database in Notion.
2. Select `...` → `Connections` and add the integration associated with `NOTION_API_TOKEN`.
3. Set a separate secret in `NOTION_ADMIN_API_KEY`.
4. Send that secret in the `X-API-Key` header on every `/notion` request.

In Swagger (`/docs`), select **Authorize** and enter `NOTION_ADMIN_API_KEY` once to use all CRUD operations interactively.

Never send `NOTION_API_TOKEN` to an API client. It must remain only on the server.

## Discovery Flow

Search databases available to the integration:

```bash
curl "http://localhost:8000/notion/databases?query=Planeación%202026" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"
```

Inspect a database's properties and types:

```bash
curl "http://localhost:8000/notion/databases/<database_id>/schema" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"
```

The schema response is intentionally simple:

```json
{
  "id": "database-id",
  "title": "Planeación 2026",
  "properties": [
    {"name": "Nombre", "id": "title", "type": "title", "configuration": {}},
    {"name": "Estado", "id": "status", "type": "status", "configuration": {}}
  ]
}
```

## CRUD

Query pages:

```bash
curl -X POST "http://localhost:8000/notion/databases/<database_id>/query" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"page_size": 20}'
```

Create a page:

```bash
curl -X POST "http://localhost:8000/notion/databases/<database_id>/pages" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"properties":{"Nombre":{"title":[{"text":{"content":"Nueva tarea"}}]}}}'
```

Read, update, and archive a page:

```bash
curl "http://localhost:8000/notion/pages/<page_id>" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"

curl -X PATCH "http://localhost:8000/notion/pages/<page_id>" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"properties":{"Estado":{"status":{"name":"Listo"}}}}'

curl -X DELETE "http://localhost:8000/notion/pages/<page_id>" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"
```

Notion does not permanently delete pages through this API. `DELETE` archives the page, which remains recoverable in Notion.
