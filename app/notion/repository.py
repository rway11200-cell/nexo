from typing import Any

import requests

from app.config import NOTION_API_TOKEN

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
REQUEST_TIMEOUT = 20


class NotionConfigurationError(Exception):
    pass


class NotionAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
    if not NOTION_API_TOKEN:
        raise NotionConfigurationError("NOTION_API_TOKEN is not configured")

    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    try:
        response = requests.request(
            method,
            f"{NOTION_API_URL}{path}",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise NotionAPIError(502, f"Could not connect to Notion: {error}") from error

    if not response.ok:
        try:
            body = response.json()
            message = body.get("message", "Notion API request failed")
        except ValueError:
            message = response.text[:500] or "Notion API request failed"
        raise NotionAPIError(response.status_code, message)

    return response.json()


def get_database(database_id: str) -> dict:
    return _request("GET", f"/databases/{database_id}")


def search_databases(query: str | None = None, start_cursor: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "filter": {"property": "object", "value": "database"},
        "page_size": 100,
    }
    if query:
        payload["query"] = query
    if start_cursor:
        payload["start_cursor"] = start_cursor
    return _request("POST", "/search", payload)


def query_database(database_id: str, payload: dict) -> dict:
    return _request("POST", f"/databases/{database_id}/query", payload)


def create_page(database_id: str, payload: dict) -> dict:
    return _request(
        "POST",
        "/pages",
        {"parent": {"database_id": database_id}, **payload},
    )


def get_page(page_id: str) -> dict:
    return _request("GET", f"/pages/{page_id}")


def update_page(page_id: str, payload: dict) -> dict:
    return _request("PATCH", f"/pages/{page_id}", payload)


def archive_page(page_id: str) -> dict:
    return _request("PATCH", f"/pages/{page_id}", {"archived": True})
