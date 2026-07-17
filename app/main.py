import os

from fastapi import FastAPI

from app.health.routes import router as health_router
from app.notion.routes import router as notion_router
from app.tasker.routes import router as tasker_router

app = FastAPI(
    title="Budget Webhook API",
    summary="FastAPI webhook que procesa notificaciones bancarias y las registra en Notion",
    description=(
        "Recibe notificaciones de gastos desde Tasker (CMR, Scotiabank), "
        "las parsea, registra en Notion, descuenta del presupuesto mensual "
        "y responde el saldo disponible por Telegram."
    ),
    version="0.2.0",
)

app.include_router(health_router)
app.include_router(tasker_router)
app.include_router(notion_router)


@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "service": "budget-webhook"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
