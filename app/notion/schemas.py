from typing import Any

from pydantic import BaseModel, Field


class DatabasePropertySchema(BaseModel):
    name: str
    id: str
    type: str
    configuration: dict[str, Any] = Field(default_factory=dict)


class DatabaseSchemaResponse(BaseModel):
    id: str
    title: str
    url: str | None = None
    properties: list[DatabasePropertySchema]


class DatabaseSummary(BaseModel):
    id: str
    title: str
    url: str | None = None


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseSummary]
    next_cursor: str | None = None
    has_more: bool = False


class DatabaseQuery(BaseModel):
    filter: dict[str, Any] | None = None
    sorts: list[dict[str, Any]] = Field(default_factory=list)
    start_cursor: str | None = None
    page_size: int = Field(default=100, ge=1, le=100)


class PageCreate(BaseModel):
    properties: dict[str, Any]
    children: list[dict[str, Any]] = Field(default_factory=list)
    icon: dict[str, Any] | None = None
    cover: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "properties": {
                    "Nombre": {
                        "title": [{"text": {"content": "Nueva tarea"}}]
                    }
                }
            }
        }
    }


class PageUpdate(BaseModel):
    properties: dict[str, Any] | None = None
    icon: dict[str, Any] | None = None
    cover: dict[str, Any] | None = None
    archived: bool | None = None


class DeleteResponse(BaseModel):
    id: str
    archived: bool
