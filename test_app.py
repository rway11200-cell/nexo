from datetime import date

import pytest

from app.main import app
from app.coding_loop import repository as coding_loop_repository
from app.coding_loop import service as coding_loop_service
from app.notion import routes as notion_routes
from app.notion import service as notion_service
from app.planning import repository as planning_repository
from app.planning import service as planning_service
from app.tasker import repository as tasker_repository
from app.tasker import routes as tasker_routes
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
    for key in ("days_remaining", "daily_available", "daily_average", "projected_total", "status"):
        assert key in summary


def test_short_budget_message_uses_operational_metrics():
    summary = {
        "spent": 211265,
        "remaining": 788735,
        "budget": 1000000,
        "day": 4,
        "days_total": 31,
        "month_pct": 13,
        "spent_pct": 21,
        "pace": 162,
        "advice": "⚠️ Vas más gastado de lo que deberías al día de hoy",
        "days_remaining": 27,
        "daily_available": 29212,
        "daily_average": 52816,
        "projected_total": 1637304,
        "status": "🔴 Ritmo alto",
    }
    message = service.format_budget_summary(summary, "Supermercado", 25000, "comida", "CMR")
    assert "🧾 **$25,000** en *Supermercado*" in message
    assert "💰 Restan **$788,735**" in message
    assert "💵 Disponible promedio: **$29,212/día**" in message
    assert "📈 Proyección: **$1,637,304**" in message
    assert "🔴 Ritmo alto" in message
    assert "Gastado:" not in message


def test_rollover_creates_and_activates_target(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service.repository, "get_active_periods", lambda: [(1000000, "old", "Septiembre 2026")]
    )
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: None)
    monkeypatch.setattr(
        service.repository,
        "create_period",
        lambda name, budget, active=False: {"id": "new", "name": name, "budget": budget},
    )
    monkeypatch.setattr(
        service.repository,
        "update_period_active",
        lambda page_id, active: calls.append((page_id, active)) or True,
    )
    result = service.rollover_period(date(2026, 10, 1))
    assert result["period_name"] == "Octubre 2026"
    assert result["created"] is True
    assert result["budget"] == 1000000
    assert calls == [("old", False), ("new", True)]


def test_rollover_is_idempotent_for_existing_target(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service.repository, "get_active_periods", lambda: [(1000000, "old", "Septiembre 2026")]
    )
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: {"id": "new"})
    monkeypatch.setattr(
        service.repository,
        "update_period_active",
        lambda page_id, active: calls.append((page_id, active)) or True,
    )
    result = service.rollover_period(date(2026, 10, 1))
    assert result["created"] is False
    assert result["period_id"] == "new"
    assert calls == [("old", False), ("new", True)]


def test_rollover_rejects_multiple_active_periods(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_active_periods",
        lambda: [(1000000, "a", "Septiembre 2026"), (1000000, "b", "Octubre 2026")],
    )
    with pytest.raises(service.RolloverIntegrityError) as excinfo:
        service.rollover_period(date(2026, 10, 1))
    assert "más de un periodo activo (2)" in str(excinfo.value)


def test_rollover_rejects_missing_active_and_target(monkeypatch):
    monkeypatch.setattr(service.repository, "get_active_periods", lambda: [])
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: None)
    with pytest.raises(service.RolloverIntegrityError):
        service.rollover_period(date(2026, 10, 1))


def test_rollover_repairs_missing_active_when_target_exists(monkeypatch):
    calls = []
    monkeypatch.setattr(service.repository, "get_active_periods", lambda: [])
    monkeypatch.setattr(
        service.repository,
        "get_period_by_name",
        lambda _: {"id": "target", "properties": {"Presupuesto": {"number": 777000}}},
    )
    monkeypatch.setattr(
        service.repository,
        "update_period_active",
        lambda page_id, active: calls.append((page_id, active)) or True,
    )
    result = service.rollover_period(date(2026, 10, 1))
    assert result["repaired"] is True
    assert result["created"] is False
    assert result["period_id"] == "target"
    assert result["budget"] == 777000
    assert calls == [("target", True)]


def test_rollover_existing_target_reports_its_own_budget(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_active_periods", lambda: [(999000, "old", "Septiembre 2026")]
    )
    monkeypatch.setattr(
        service.repository,
        "get_period_by_name",
        lambda _: {"id": "new", "properties": {"Presupuesto": {"number": 777}}},
    )
    monkeypatch.setattr(service.repository, "update_period_active", lambda *_: True)
    result = service.rollover_period(date(2026, 10, 1))
    assert result["budget"] == 777


def test_rollover_incomplete_when_activation_fails(monkeypatch):
    monkeypatch.setattr(service.repository, "get_active_periods", lambda: [(1000000, "old", "X")])
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: None)
    monkeypatch.setattr(
        service.repository,
        "create_period",
        lambda name, budget, active=False: {"id": "new"},
    )
    monkeypatch.setattr(
        service.repository,
        "update_period_active",
        lambda page_id, active: not (page_id == "new" and active is True),
    )
    with pytest.raises(service.RolloverIncompleteError):
        service.rollover_period(date(2026, 10, 1))


def test_rollover_endpoint_requires_key(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.post("/budget/rollover")
    assert resp.status_code == 401


def test_rollover_endpoint_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.post("/budget/rollover", headers={"X-API-Key": "nope"})
    assert resp.status_code == 401


def test_rollover_endpoint_unconfigured_key(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "")
    resp = client.post("/budget/rollover", headers={"X-API-Key": "admin-secret"})
    assert resp.status_code == 503


def test_rollover_endpoint_rejects_bad_date(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.post(
        "/budget/rollover?target_date=2026-13-99",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 400


def test_rollover_endpoint_success(monkeypatch):
    calls = []
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(
        service.repository, "get_active_periods", lambda: [(1000000, "old", "Septiembre 2026")]
    )
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: None)
    monkeypatch.setattr(
        service.repository,
        "create_period",
        lambda name, budget, active=False: {"id": "new", "name": name, "budget": budget},
    )
    monkeypatch.setattr(
        service.repository,
        "update_period_active",
        lambda page_id, active: calls.append((page_id, active)) or True,
    )
    resp = client.post(
        "/budget/rollover?target_date=2026-10-01",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert data["period_name"] == "Octubre 2026"
    assert calls == [("old", False), ("new", True)]


def test_rollover_endpoint_idempotent(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(
        service.repository, "get_active_periods", lambda: [(1000000, "old", "Septiembre 2026")]
    )
    monkeypatch.setattr(service.repository, "get_period_by_name", lambda _: {"id": "new"})
    monkeypatch.setattr(service.repository, "update_period_active", lambda *_: True)
    resp = client.post(
        "/budget/rollover?target_date=2026-10-01",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is False


def test_rollover_endpoint_conflict_on_double_active(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(
        service.repository,
        "get_active_periods",
        lambda: [(1000000, "a", "Septiembre 2026"), (1000000, "b", "Octubre 2026")],
    )
    resp = client.post(
        "/budget/rollover?target_date=2026-10-01",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 409
    assert "más de un periodo activo" in resp.json()["detail"]


def test_rollover_endpoint_notion_outage_is_502(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")

    def boom():
        raise tasker_repository.NotionUnavailableError("Notion rechazó la consulta (HTTP 503)")

    monkeypatch.setattr(service.repository, "get_active_periods", boom)
    resp = client.post(
        "/budget/rollover?target_date=2026-10-01",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 502
    assert "HTTP 503" in resp.json()["detail"]


def test_rollover_endpoint_repair_returns_200(monkeypatch):
    monkeypatch.setattr(tasker_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    monkeypatch.setattr(service.repository, "get_active_periods", lambda: [])
    monkeypatch.setattr(
        service.repository,
        "get_period_by_name",
        lambda _: {"id": "target", "properties": {"Presupuesto": {"number": 777000}}},
    )
    monkeypatch.setattr(service.repository, "update_period_active", lambda *_: True)
    resp = client.post(
        "/budget/rollover?target_date=2026-10-01",
        headers={"X-API-Key": "admin-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["repaired"] is True


def _periodo_page(pid, name, budget):
    return {
        "id": pid,
        "created_time": f"2026-0{len(pid)}-01T00:00:00.000Z",
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Presupuesto": {"number": budget},
        },
    }


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_get_active_periods_parses_pages(monkeypatch):
    monkeypatch.setattr(tasker_repository, "NOTION_API_TOKEN", "token")
    payload = {"results": [_periodo_page("a", "Octubre 2026", 1000000)], "has_more": False}
    monkeypatch.setattr(tasker_repository.requests, "post", lambda *a, **k: _FakeResp(payload))
    assert tasker_repository.get_active_periods() == [(1000000, "a", "Octubre 2026")]


def test_get_active_periods_includes_zero_budget(monkeypatch):
    monkeypatch.setattr(tasker_repository, "NOTION_API_TOKEN", "token")
    payload = {"results": [_periodo_page("z", "Periodo X", 0)], "has_more": False}
    monkeypatch.setattr(tasker_repository.requests, "post", lambda *a, **k: _FakeResp(payload))
    assert tasker_repository.get_active_periods() == [(0, "z", "Periodo X")]


def test_get_active_periods_skips_pages_without_budget(monkeypatch):
    monkeypatch.setattr(tasker_repository, "NOTION_API_TOKEN", "token")
    page = _periodo_page("a", "Sin presupuesto", 5)
    page["properties"]["Presupuesto"] = {"number": None}
    payload = {"results": [page], "has_more": False}
    monkeypatch.setattr(tasker_repository.requests, "post", lambda *a, **k: _FakeResp(payload))
    assert tasker_repository.get_active_periods() == []


def test_get_active_periods_follows_pagination(monkeypatch):
    monkeypatch.setattr(tasker_repository, "NOTION_API_TOKEN", "token")
    pages = [
        {"results": [_periodo_page("a", "Uno", 100)], "has_more": True, "next_cursor": "c1"},
        {"results": [_periodo_page("bb", "Dos", 200)], "has_more": False},
    ]
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs.get("json", {}))
        return _FakeResp(pages[len(calls) - 1])

    monkeypatch.setattr(tasker_repository.requests, "post", fake_post)
    result = tasker_repository.get_active_periods()
    assert result == [(100, "a", "Uno"), (200, "bb", "Dos")]
    assert calls[1].get("start_cursor") == "c1"


def test_get_active_periods_raises_on_notion_error(monkeypatch):
    monkeypatch.setattr(tasker_repository, "NOTION_API_TOKEN", "token")
    monkeypatch.setattr(
        tasker_repository.requests, "post", lambda *a, **k: _FakeResp({}, status_code=503)
    )
    with pytest.raises(tasker_repository.NotionUnavailableError):
        tasker_repository.get_active_periods()


def test_get_active_period_none_on_duplicates(monkeypatch):
    monkeypatch.setattr(
        tasker_repository, "get_active_periods", lambda: [(1, "a", "X"), (2, "b", "Y")]
    )
    assert tasker_repository.get_active_period() is None


def test_get_active_period_lenient_uses_first_of_duplicates(monkeypatch):
    monkeypatch.setattr(
        tasker_repository, "get_active_periods", lambda: [(1, "a", "X"), (2, "b", "Y")]
    )
    assert tasker_repository.get_active_period_lenient() == (1, "a")


def test_get_active_period_lenient_none_when_notion_down(monkeypatch):
    def boom():
        raise tasker_repository.NotionUnavailableError("down")

    monkeypatch.setattr(tasker_repository, "get_active_periods", boom)
    assert tasker_repository.get_active_period_lenient() is None


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


def planning_page(
    page_id="planning-id",
    name="Comprar escritorio",
    month="Abril",
    tags=None,
    budget=120000,
    completed=False,
):
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Año": {"select": {"name": "2026"}},
            "Mes": {"select": {"name": month} if month else None},
            "Tag": {"multi_select": [{"name": tag} for tag in (tags or [])]},
            "Valor Estimado o Presupuesto": {"number": budget},
            "Completado": {"checkbox": completed},
        },
    }


def test_planning_requires_admin_key(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.get("/planning/items")
    assert resp.status_code == 401


def test_planning_crud(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    headers = {"X-API-Key": "admin-secret"}
    page = planning_page(tags=["Cocina"])

    monkeypatch.setattr(planning_repository, "query_items", lambda payload: {"results": [page]})
    monkeypatch.setattr(planning_repository, "create_item", lambda properties: page)
    monkeypatch.setattr(planning_repository, "get_item", lambda page_id: page)
    monkeypatch.setattr(planning_repository, "update_item", lambda page_id, properties: page)
    monkeypatch.setattr(
        planning_repository,
        "archive_item",
        lambda page_id: {"id": page_id, "archived": True},
    )

    listed = client.get("/planning/items?month=Abril", headers=headers)
    created = client.post(
        "/planning/items",
        headers=headers,
        json={"name": "Comprar escritorio", "month": "Abril", "tags": ["Cocina"]},
    )
    read = client.get("/planning/items/planning-id", headers=headers)
    updated = client.patch(
        "/planning/items/planning-id",
        headers=headers,
        json={"completed": True},
    )
    deleted = client.delete("/planning/items/planning-id", headers=headers)

    assert listed.status_code == 200
    assert listed.json()["items"][0]["month"] == "Abril"
    assert created.status_code == 201
    assert read.json()["name"] == "Comprar escritorio"
    assert updated.status_code == 200
    assert deleted.json() == {"id": "planning-id", "archived": True}


def test_planning_summary(monkeypatch):
    pages = [
        planning_page("one", month="Enero", tags=["Cocina"], budget=100, completed=True),
        planning_page("two", month=None, tags=[], budget=200, completed=False),
    ]
    monkeypatch.setattr(
        planning_repository,
        "query_items",
        lambda payload: {"results": pages, "has_more": False},
    )

    summary = planning_service.get_summary("2026", None, None)

    assert summary["item_count"] == 2
    assert summary["completed_count"] == 1
    assert summary["pending_budget"] == 200
    assert {group["name"] for group in summary["by_month"]} == {"Enero", "Sin mes"}


def test_planning_update_rejects_null_completed():
    from app.planning.schemas import PlanningItemUpdate

    try:
        planning_service.update_item("planning-id", PlanningItemUpdate(completed=None))
    except ValueError as error:
        assert str(error) == "completed cannot be null"
    else:
        raise AssertionError("Expected completed null to be rejected")


def coding_loop_page(resource):
    common = {"id": f"{resource}-id", "properties": {}}
    if resource == "projects":
        common["properties"] = {
            "Project": {"title": [{"plain_text": "Nexo"}]},
            "Auto commit": {"checkbox": True},
            "Branch": {"rich_text": [{"plain_text": "main"}]},
            "OpenCode Sesion": {"rich_text": []},
            "Priority": {"select": {"name": "High"}},
            "Repo Path": {"url": "https://github.com/example/nexo"},
            "Status": {"select": {"name": "Active"}},
            "Updated": {"date": {"start": "2026-07-18"}},
        }
    elif resource == "tasks":
        common["properties"] = {
            "Task": {"title": [{"plain_text": "Implement API"}]},
            "Approved": {"checkbox": True},
            "Attempts": {"number": 1},
            "Created": {"date": None},
            "Last result": {"rich_text": []},
            "Next actions": {"rich_text": []},
            "Priority": {"select": {"name": "High"}},
            "Project": {"relation": [{"id": "projects-id"}]},
            "Status": {"select": {"name": "in Progress"}},
            "Updated": {"date": None},
        }
    elif resource == "runs":
        common["properties"] = {
            "Run ID": {"title": [{"plain_text": "run-1"}]},
            "Duration": {"number": 20},
            "OpenIA available": {"checkbox": True},
            "Status": {"select": {"name": "Success"}},
            "Summary": {"rich_text": [{"plain_text": "Completed"}]},
            "Task": {"relation": [{"id": "tasks-id"}]},
            "Timestamp": {"date": {"start": "2026-07-18"}},
        }
    else:
        common["properties"] = {
            "Run ID": {"title": [{"plain_text": "run-error"}]},
            "Duration": {"number": 5},
            "Status": {"select": {"name": "Failed"}},
            "Summary": {"rich_text": [{"plain_text": "Test failed"}]},
            "Timestamp": {"date": {"start": "2026-07-18"}},
        }
    return common


def test_coding_loop_requires_admin_key(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    resp = client.get("/coding-loop/projects")
    assert resp.status_code == 401


def test_coding_loop_resources(monkeypatch):
    monkeypatch.setattr(notion_routes, "NOTION_ADMIN_API_KEY", "admin-secret")
    headers = {"X-API-Key": "admin-secret"}

    monkeypatch.setattr(
        coding_loop_repository,
        "query",
        lambda resource, payload: {
            "results": [coding_loop_page(resource)],
            "has_more": False,
        },
    )

    projects = client.get("/coding-loop/projects", headers=headers)
    tasks = client.get(
        "/coding-loop/tasks?status=In%20Progress&approved=true",
        headers=headers,
    )
    runs = client.get("/coding-loop/runs", headers=headers)
    errors = client.get("/coding-loop/test-errors", headers=headers)

    assert projects.json()["items"][0]["project"] == "Nexo"
    assert tasks.json()["items"][0]["status"] == "In Progress"
    assert tasks.json()["items"][0]["project_id"] == "projects-id"
    assert runs.json()["items"][0]["task_id"] == "tasks-id"
    assert errors.json()["items"][0]["summary"] == "Test failed"


def test_coding_loop_task_filter_and_create_mapping(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        coding_loop_repository,
        "query",
        lambda resource, payload: captured.setdefault("query", payload) or {"results": []},
    )

    coding_loop_service.list_records(
        "tasks", "In Progress", "Project", "project-id", "Approved", True, 25, None
    )

    filters = captured["query"]["filter"]["and"]
    assert {"property": "Status", "select": {"equals": "in Progress"}} in filters
    assert {"property": "Approved", "checkbox": {"equals": True}} in filters

    from app.coding_loop.schemas import TaskCreate

    def capture_create(resource, properties):
        captured["resource"] = resource
        captured["properties"] = properties
        return coding_loop_page("tasks")

    monkeypatch.setattr(coding_loop_repository, "create", capture_create)
    coding_loop_service.create_record(
        "tasks",
        TaskCreate(
            task="Implement API",
            project_id="project-id",
            status="In Progress",
            approved=True,
        ),
    )

    assert captured["resource"] == "tasks"
    assert captured["properties"]["Project"] == {"relation": [{"id": "project-id"}]}
    assert captured["properties"]["Status"] == {"select": {"name": "in Progress"}}
