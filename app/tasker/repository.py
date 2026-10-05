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


def get_active_periods() -> list[tuple[int, str, str]]:
    """Return every Periodo page marked as active: (budget, page_id, name)."""
    if not NOTION_API_TOKEN:
        return []
    data = {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "page_size": 100}
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{PERIODO_DB}/query",
        headers=_NOTION_HEADERS,
        json=data,
    )
    if resp.status_code != 200:
        return []
    periods = []
    for result in resp.json().get("results", []):
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
    periods = get_active_periods()
    if len(periods) != 1:
        return None
    budget, page_id, _ = periods[0]
    return (budget, page_id)


def get_period_by_name(name: str) -> dict | None:
    """Return the first Periodo page whose title (Name) matches name."""
    if not NOTION_API_TOKEN:
        return None
    payload = {
        "filter": {"property": "Name", "title": {"equals": name}},
        "page_size": 1,
    }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{PERIODO_DB}/query",
        headers=_NOTION_HEADERS,
        json=payload,
    )
    if resp.status_code != 200:
        return None
    return next(iter(resp.json().get("results", [])), None)


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
