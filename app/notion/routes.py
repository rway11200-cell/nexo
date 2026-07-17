import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security, status
from fastapi.security import APIKeyHeader

from app.config import NOTION_ADMIN_API_KEY
from app.notion import repository, service
from app.notion.schemas import (
    DatabaseQuery,
    DatabaseListResponse,
    DatabaseSchemaResponse,
    DeleteResponse,
    PageCreate,
    PageUpdate,
)

router = APIRouter(prefix="/notion", tags=["Notion CRUD"])
admin_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin_key(
    x_api_key: Annotated[str | None, Security(admin_key_header)] = None,
):
    if not NOTION_ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NOTION_ADMIN_API_KEY is not configured",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, NOTION_ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )


def _handle_notion_error(error: Exception):
    if isinstance(error, repository.NotionConfigurationError):
        raise HTTPException(status_code=503, detail=str(error)) from error
    if isinstance(error, repository.NotionAPIError):
        status_code = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=status_code, detail=error.message) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise error


@router.get(
    "/databases",
    response_model=DatabaseListResponse,
    dependencies=[Depends(require_admin_key)],
)
def search_databases(
    query: str | None = Query(default=None, max_length=200),
    start_cursor: str | None = Query(default=None),
):
    try:
        return service.search_databases(query, start_cursor)
    except Exception as error:
        _handle_notion_error(error)


@router.get(
    "/databases/{database_id}/schema",
    response_model=DatabaseSchemaResponse,
    dependencies=[Depends(require_admin_key)],
)
def read_database_schema(database_id: str = Path(min_length=1)):
    try:
        return service.get_database_schema(database_id)
    except Exception as error:
        _handle_notion_error(error)


@router.post(
    "/databases/{database_id}/query",
    dependencies=[Depends(require_admin_key)],
)
def query_database(query: DatabaseQuery, database_id: str = Path(min_length=1)):
    try:
        return service.query_database(database_id, query)
    except Exception as error:
        _handle_notion_error(error)


@router.post(
    "/databases/{database_id}/pages",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
)
def create_page(data: PageCreate, database_id: str = Path(min_length=1)):
    try:
        return service.create_page(database_id, data)
    except Exception as error:
        _handle_notion_error(error)


@router.get("/pages/{page_id}", dependencies=[Depends(require_admin_key)])
def read_page(page_id: str = Path(min_length=1)):
    try:
        return service.get_page(page_id)
    except Exception as error:
        _handle_notion_error(error)


@router.patch("/pages/{page_id}", dependencies=[Depends(require_admin_key)])
def update_page(data: PageUpdate, page_id: str = Path(min_length=1)):
    try:
        return service.update_page(page_id, data)
    except Exception as error:
        _handle_notion_error(error)


@router.delete(
    "/pages/{page_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_admin_key)],
)
def delete_page(page_id: str = Path(min_length=1)):
    try:
        return service.delete_page(page_id)
    except Exception as error:
        _handle_notion_error(error)
