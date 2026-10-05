from datetime import datetime

import requests

from app.config import (
    MOVIMIENTOS_DB,
    NOTION_API_TOKEN,
    PERIODO_DB,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_GROUP_ID,
)

_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


class NotionUnavailableError(RuntimeError):
    """Raised when the Notion API cannot be reached or returns an error."""


def _query_periodos(payload: dict) -> list[dict]:
    """Run a Periodo DB query, following pagination. Raises on transport/API failure."""
    results: list[dict] = []
    cursor = None
    while True:
        body = dict(payload)
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{PERIODO_DB}/query",
            headers=_NOTION_HEADERS,
            json=body,
        )
        if resp.status_code != 200:
            raise NotionUnavailableError(
                f"Notion rechazó la consulta de periodos (HTTP {resp.status_code})"
            )
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            return results
        cursor = data.get("next_cursor")
        if not cursor:
            return results


def get_active_periods() -> list[tuple[int, str, str]]:
    """Return every Periodo page marked as active: (budget, page_id, name)."""
    if not NOTION_API_TOKEN:
        return []
    results = _query_periodos(
        {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "page_size": 100}
    )
    periods = []
    for result in results:
        page_id = result.get("id", "")
        props = result.get("properties", {})
        budget = props.get("Presupuesto", {}).get("number")
        if budget is None:
            continue
        title = props.get("Name", {}).get("title", [])
        name = title[0].get("plain_text", "") if title else ""
        periods.append((int(budget), page_id, name))
    return periods


def get_active_period() -> tuple[int, str] | None:
    """Return the single active Periodo, or None if there is not exactly one.

    Read paths must not change behaviour when Notion is unreachable: on a
    transport/API error the previous period (first active page) is returned so
    the caller can keep operating, and the failure is swallowed by design.
    """
    try:
        periods = get_active_periods()
    except NotionUnavailableError:
        return None
    if len(periods) != 1:
        return None
    budget, page_id, _ = periods[0]
    return (budget, page_id)


def get_active_period_lenient() -> tuple[int, str] | None:
    """Return the first active Periodo regardless of duplicates, or None if none.

    Used by read paths (/status, /status/text, transaction webhook) so a
    duplicated Activo flag degrades to 'use one real period' instead of
    silently falling back to a hardcoded budget of 1_000_000.
    """
    try:
        periods = get_active_periods()
    except NotionUnavailableError:
        return None
    if not periods:
        return None
    budget, page_id, _ = periods[0]
    return (budget, page_id)


def get_period_by_name(name: str) -> dict | None:
    """Return the earliest Periodo page whose title (Name) matches name."""
    if not NOTION_API_TOKEN:
        return None
    results = _query_periodos(
        {"filter": {"property": "Name", "title": {"equals": name}}, "page_size": 100}
    )
    if not results:
        return None
    results.sort(key=lambda page: page.get("created_time", ""))
    return results[0]


def update_period_active(page_id: str, active: bool) -> bool:
    if not NOTION_API_TOKEN:
        return False
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_NOTION_HEADERS,
        json={"properties": {"Activo": {"checkbox": active}}},
    )
    return resp.status_code == 200


def create_period(name: str, budget: int, active: bool = False) -> dict | None:
    if not NOTION_API_TOKEN:
        return None
    payload = {
        "parent": {"database_id": PERIODO_DB},
        "properties": {
            "Name": {"title": [{"text": {"content": name}}]},
            "Presupuesto": {"number": budget},
            "Activo": {"checkbox": active},
        },
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_NOTION_HEADERS,
        json=payload,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def get_budget_from_page(page: dict) -> int | None:
    """Read the Presupuesto number from a raw Periodo page."""
    budget = page.get("properties", {}).get("Presupuesto", {}).get("number")
    return int(budget) if budget is not None else None


def register_notion(
    amount: int, merchant: str, category: str, source: str = "CMR", period_page_id: str = ""
) -> bool:
    if not NOTION_API_TOKEN:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    merchant_display = f"{merchant} [{source}]"[:60]
    props = {
        "Nombre": {"title": [{"text": {"content": merchant_display}}]},
        "Monto": {"number": amount},
        "Fecha": {"date": {"start": today}},
        "Categoría": {"select": {"name": category}},
    }
    if period_page_id:
        props["Periodo"] = {"relation": [{"id": period_page_id}]}
    data = {"parent": {"database_id": MOVIMIENTOS_DB}, "properties": props}
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_NOTION_HEADERS,
        json=data,
    )
    return resp.status_code == 200


def get_monthly_spent(period_page_id: str = "") -> int:
    if not NOTION_API_TOKEN:
        return 0
    data = {"page_size": 100}
    if period_page_id:
        data["filter"] = {
            "property": "Periodo",
            "relation": {"contains": period_page_id},
        }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{MOVIMIENTOS_DB}/query",
        headers=_NOTION_HEADERS,
        json=data,
    )
    if resp.status_code != 200:
        return 0
    total = 0
    for result in resp.json().get("results", []):
        props = result.get("properties", {})
        for v in props.values():
            if v.get("type") == "number":
                total += v.get("number", 0)
    return total


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_GROUP_ID, "text": message}, timeout=10)
