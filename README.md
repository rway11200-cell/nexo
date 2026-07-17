# Budget Webhook

Webhook that receives expense notifications (CMR, bank, etc.) via Tasker and registers them in Notion.

## Stack

- Python 3.11
- FastAPI
- Uvicorn
- Requests
- Notion API
- Telegram Bot API

## Pipeline

1. Tasker on Android captures CMR purchases
2. Sends HTTP GET to the webhook `?text=...`
3. Service parses the notification (CMR or Scotiabank)
4. Repository registers the expense in Notion "Movimientos" DB
5. Deducts from monthly budget
6. Responds remaining balance via Telegram

## Project Structure

```
app/
├── __init__.py
├── config.py            # Environment variables
├── main.py              # FastAPI app, routers, CORS
├── health/
│   ├── __init__.py
│   └── routes.py        # GET /health
├── notion/              # Generic, protected Notion CRUD
│   ├── routes.py
│   ├── schemas.py
│   ├── service.py
│   └── repository.py
└── tasker/
    ├── __init__.py
    ├── routes.py        # HTTP endpoints
    ├── schemas.py       # Pydantic models
    ├── service.py       # Parsing, categories, budget logic
    └── repository.py    # Notion and Telegram integrations

docs/
└── request-flow.md
```

## Request Flow

```
routes.py receives the HTTP request.
schemas.py validates and describes input/output (OpenAPI).
service.py executes the business logic (parse, categorize, budget).
repository.py talks to Notion and Telegram.
config.py centralises environment variables.
```

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the API:

```
http://localhost:8000
```

Open Swagger docs:

```
http://localhost:8000/docs
```

Open ReDoc:

```
http://localhost:8000/redoc
```

## Manual Checks

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/status

curl "http://localhost:8000/tasker?text=Compraste%20%241.500%20en%20Starbucks%20SANTIAGO/CHL%20Con%20tu%20CMR"
```

## Environment Variables

| Variable | Description |
|---|---|
| `NOTION_API_TOKEN` | Notion integration token |
| `NOTION_ADMIN_API_KEY` | Secret required in `X-API-Key` for CRUD endpoints |
| `MOVIMIENTOS_DB` | Notion database ID for expenses |
| `PERIODO_DB` | Notion database ID for periods |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_GROUP_ID` | Telegram group chat ID |
| `DEBUG` | Enable debug logging |

## Generic Notion CRUD

The protected `/notion` endpoints let an AI discover database schemas and administer pages without exposing the Notion integration token.

```bash
curl "http://localhost:8000/notion/databases?query=Planeación%202026" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"

curl "http://localhost:8000/notion/databases/<database_id>/schema" \
  -H "X-API-Key: $NOTION_ADMIN_API_KEY"
```

See [Notion CRUD](docs/notion-crud.md) for query, create, update, and archive examples.
