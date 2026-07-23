import sys

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import DEBUG, TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID
from app.tasker import service

router = APIRouter(tags=["Tasker"])


@router.get("/status")
def budget_status():
    active = service.repository.get_active_period()
    period_page_id = active[1] if active else ""
    budget_val = active[0] if active else 1_000_000
    return service.get_budget_summary(period_page_id, budget_val)


@router.get("/status/text", response_class=PlainTextResponse)
def budget_status_text():
    active = service.repository.get_active_period()
    period_page_id = active[1] if active else ""
    budget_val = active[0] if active else 1_000_000
    summary = service.get_budget_summary(period_page_id, budget_val)
    return service.format_budget_summary(summary)


@router.get("/test-telegram")
def test_telegram():
    if not TELEGRAM_BOT_TOKEN:
        return JSONResponse(
            {"error": "TELEGRAM_BOT_TOKEN not set"}, status_code=400
        )
    if not TELEGRAM_GROUP_ID:
        return JSONResponse(
            {"error": "TELEGRAM_GROUP_ID not set"}, status_code=400
        )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_GROUP_ID,
            "text": "🧪 Test desde budget-webhook — si ves esto, Telegram funciona ✅",
        },
        timeout=10,
    )
    return {
        "status": resp.ok,
        "code": resp.status_code,
        "response": resp.json() if resp.ok else resp.text[:200],
    }


@router.get("/tasker")
def tasker_webhook(text: str = Query("")):
    if DEBUG:
        print(f"DEBUG /tasker text={text[:300]}", flush=True)
        sys.stderr.write(f"DEBUG /tasker text={text[:300]}\n")
        sys.stderr.flush()

    if not text:
        return {"ok": False, "reason": "no text"}

    parsed = service.parse_cmr(text)
    if parsed:
        cat = service.infer_category(parsed["merchant"])
        return service.process_and_respond(
            parsed["amount"], parsed["merchant"], cat, "CMR"
        )

    parsed = service.parse_scotiabank(text)
    if parsed:
        cat = service.infer_category(parsed["merchant"])
        return service.process_and_respond(
            parsed["amount"], parsed["merchant"], cat, "Scotia"
        )

    return {"ok": True, "reason": "not a recognized expense"}


@router.get("/tasker/cmr")
def tasker_cmr(text: str = Query("")):
    if DEBUG:
        print(f"DEBUG /tasker/cmr text={text[:300]}", flush=True)
        sys.stderr.write(f"DEBUG /tasker/cmr text={text[:300]}\n")
        sys.stderr.flush()

    if not text:
        return {"ok": False, "reason": "no text"}

    parsed = service.parse_cmr(text)
    if not parsed:
        return {"ok": True, "reason": "not a CMR purchase"}

    cat = service.infer_category(parsed["merchant"])
    return service.process_and_respond(
        parsed["amount"], parsed["merchant"], cat, "CMR"
    )


@router.get("/tasker/scotiabank")
def tasker_scotiabank(text: str = Query("")):
    if not text:
        return {"ok": False, "reason": "no text"}

    parsed = service.parse_scotiabank(text)
    if not parsed:
        return {"ok": True, "reason": "not a Scotia expense"}

    cat = service.infer_category(parsed["merchant"])
    return service.process_and_respond(
        parsed["amount"], parsed["merchant"], cat, "Scotia"
    )
