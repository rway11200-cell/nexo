from app.main import app
from app.notion import routes as notion_routes
from app.notion import service as notion_service
from app.tasker import service
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "budget-webhook"


def test_status(monkeypatch):
    monkeypatch.setattr(service.repository, "get_active_period", lambda: None)
    monkeypatch.setattr(service.repository, "get_monthly_spent", lambda _: 0)
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("spent", "remaining", "budget", "day", "days_total", "month_pct", "spent_pct", "pace", "advice"):
        assert key in data


def test_status_text(monkeypatch):
    monkeypatch.setattr(service.repository, "get_active_period", lambda: None)
    monkeypatch.setattr(service.repository, "get_monthly_spent", lambda _: 0)
    resp = client.get("/status/text")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


def test_tasker_no_text():
    resp = client.get("/tasker")
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "reason": "no text"}


def test_tasker_cmr(monkeypatch):
    monkeypatch.setattr(service.repository, "get_active_period", lambda: None)
    monkeypatch.setattr(service.repository, "register_notion", lambda *args: True)
    monkeypatch.setattr(service.repository, "get_monthly_spent", lambda _: 1500)
    monkeypatch.setattr(service.repository, "send_telegram", lambda _: None)
    text = "Compraste $1.500 en Starbucks SANTIAGO/CHL Con tu CMR"
    resp = client.get(f"/tasker?text={text}")
    assert resp.status_code == 200
    data = resp.json()
    if "ok" not in data:
        assert "spent" in data
        assert "remaining" in data


def test_tasker_cmr_not_matched():
    resp = client.get("/tasker/cmr?text=noticias%20del%20dia")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "reason": "not a CMR purchase"}


def test_tasker_scotiabank_not_matched():
    resp = client.get("/tasker/scotiabank?text=hola%20mundo")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "reason": "not a Scotia expense"}


def test_test_telegram_no_token():
    resp = client.get("/test-telegram")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_parse_cmr():
    result = service.parse_cmr("Compraste $1.500 en Starbucks SANTIAGO/CHL Con tu CMR")
    assert result is not None
    assert result["amount"] == 1500
    assert result["merchant"] == "Starbucks"


def test_parse_cmr_with_decimal():
    result = service.parse_cmr("Compraste $15.990 en MERCADO LIBRE SANTIAGO/CHL ...")
    assert result is not None
    assert result["amount"] == 15990


def test_parse_scotiabank():
    result = service.parse_scotiabank("App Scotia. Se realizó un pago ... por $25.000 en NETFLIX.")
    assert result is not None
    assert result["amount"] == 25000
    assert result["merchant"] == "NETFLIX"


def test_infer_category():
    assert service.infer_category("Starbucks") == "comida"
    assert service.infer_category("ZARA") == "vestuario"
    assert service.infer_category("COPEC") == "auto"
    assert service.infer_category("Desconocido SA") == "otro"


def test_clean_text():
    assert service.clean_text("hola%20mundo%evtprm1") == "holamundo"
    assert service.clean_text("%NTITLE%NTEXT") == ""


def test_openapi_spec():
    spec = app.openapi()
    assert spec["info"]["title"] == "Budget Webhook API"
    assert "/tasker" in spec["paths"]
    assert "/health" in spec["paths"]


def test_get_budget_summary(monkeypatch):
    monkeypatch.setattr(service.repository, "get_monthly_spent", lambda _: 0)
    summary = service.get_budget_summary(budget=1000000)
    assert summary["budget"] == 1000000
    assert summary["remaining"] == 1000000 - summary["spent"]
    assert "advice" in summary


def test_notion_requires_admin_key(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.get("/notion/databases/db-id/schema")
    assert resp.status_code == 401


def test_notion_database_schema(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(
        notion_service.repository,
        "get_database",
        lambda _: {
            "id": "db-id",
            "title": [{"plain_text": "Planeación 2026"}],
            "url": "https://notion.so/db-id",
            "properties": {
                "Nombre": {"id": "title", "type": "title", "title": {}},
                "Estado": {
                    "id": "status",
                    "type": "status",
                    "status": {"options": [{"name": "Pendiente", "color": "gray"}]},
                },
            },
        },
    )

    resp = client.get(
        "/notion/databases/db-id/schema",
        headers={"X-API-Key": "admin-secret"},
    )

    assert resp.status_code == 200
    assert resp.json()["title"] == "Planeación 2026"
    assert [item["name"] for item in resp.json()["properties"]] == ["Estado", "Nombre"]


def test_notion_search_databases(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(
        notion_service.repository,
        "search_databases",
        lambda query, cursor: {
            "results": [
                {
                    "id": "db-id",
                    "title": [{"plain_text": "Planeación 2026"}],
                    "url": "https://notion.so/db-id",
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
    )

    resp = client.get(
        "/notion/databases?query=Planeación%202026",
        headers={"X-API-Key": "admin-secret"},
    )

    assert resp.status_code == 200
    assert resp.json()["databases"][0]["title"] == "Planeación 2026"


def test_notion_crud_endpoints(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    headers = {"X-API-Key": "admin-secret"}
    page = {"id": "page-id", "properties": {}}

    monkeypatch.setattr(notion_service.repository, "query_database", lambda db, data: {"results": [page]})
    monkeypatch.setattr(notion_service.repository, "create_page", lambda db, data: page)
    monkeypatch.setattr(notion_service.repository, "get_page", lambda page_id: page)
    monkeypatch.setattr(notion_service.repository, "update_page", lambda page_id, data: page)
    monkeypatch.setattr(
        notion_service.repository,
        "archive_page",
        lambda page_id: {"id": page_id, "archived": True},
    )

    query = client.post("/notion/databases/db-id/query", headers=headers, json={})
    created = client.post(
        "/notion/databases/db-id/pages",
        headers=headers,
        json={"properties": {"Nombre": {"title": []}}},
    )
    read = client.get("/notion/pages/page-id", headers=headers)
    updated = client.patch(
        "/notion/pages/page-id",
        headers=headers,
        json={"properties": {"Estado": {"status": {"name": "Listo"}}}},
    )
    deleted = client.delete("/notion/pages/page-id", headers=headers)

    assert query.status_code == 200
    assert created.status_code == 201
    assert read.status_code == 200
    assert updated.status_code == 200
    assert deleted.json() == {"id": "page-id", "archived": True}
