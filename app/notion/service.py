from typing import Any

from app.notion import repository


def _plain_text(rich_text: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in rich_text)


def get_database_schema(database_id: str) -> dict:
    database = repository.get_database(database_id)
    properties = []

    for name, definition in database.get("properties", {}).items():
        property_type = definition.get("type", "unknown")
        properties.append(
            {
                "name": name,
                "id": definition.get("id", ""),
                "type": property_type,
                "configuration": definition.get(property_type, {}),
            }
        )

    properties.sort(key=lambda item: item["name"].lower())
    return {
        "id": database.get("id", database_id),
        "title": _plain_text(database.get("title", [])),
        "url": database.get("url"),
        "properties": properties,
    }


def search_databases(query: str | None = None, start_cursor: str | None = None) -> dict:
    result = repository.search_databases(query, start_cursor)
    databases = [
        {
            "id": database.get("id", ""),
            "title": _plain_text(database.get("title", [])),
            "url": database.get("url"),
        }
        for database in result.get("results", [])
    ]
    return {
        "databases": databases,
        "next_cursor": result.get("next_cursor"),
        "has_more": result.get("has_more", False),
    }


def query_database(database_id: str, query) -> dict:
    return repository.query_database(
        database_id,
        query.model_dump(exclude_none=True),
    )


def create_page(database_id: str, data) -> dict:
    return repository.create_page(
        database_id,
        data.model_dump(exclude_unset=True),
    )


def get_page(page_id: str) -> dict:
    return repository.get_page(page_id)


def update_page(page_id: str, data) -> dict:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise ValueError("At least one field is required")
    return repository.update_page(page_id, changes)


def delete_page(page_id: str) -> dict:
    page = repository.archive_page(page_id)
    return {"id": page.get("id", page_id), "archived": page.get("archived", True)}
