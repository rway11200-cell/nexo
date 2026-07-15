import os
import re
import json
from datetime import datetime

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NOTION_API_KEY = os.environ.get("NOTION_API_TOKEN", "")
MOVIMIENTOS_DB = os.environ.get("MOVIMIENTOS_DB", "")
PERIODO_DB = "39d06589-4ee5-8036-a3ef-c73eadeae4f8"

CATEGORY_KEYWORDS = {
    "comida": ["restaurant", "starbucks", "café", "sushi", "pizza", "delivery", "pedidos", "super", "tottus", "lider", "jumbo", "mercado"],
    "salud": ["farmacia", "salud", "médico", "indisa", "red salud", "clínica"],
    "transporte": ["uber", "taxi", "cabify", "benzo", "metro", "bip", "pasaje"],
    "auto": ["benzo", "automotora", "neumático", "bencina", "copec", "shell"],
    "perritos": ["mascota", "dog", "perro", "veterinaria", "pet"],
    "vestuario": ["zara", "h&m", "ripley", "falabella", "paris", "vestuario", "ropa"],
    "suscripciones": ["apple", "netflix", "spotify", "disney", "hbomax", "amazon"],
}

# Telegram config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")


def infer_category(comercio: str) -> str:
    comercio_lower = comercio.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in comercio_lower:
                return category
    return "otro"


def clean_text(text: str) -> str:
    """Remove Tasker placeholders and common junk."""
    return re.sub(r'%20|%evtprm\d|%NTITLE|%NTEXT|cl\.android', '', text).strip()


def get_active_period() -> tuple[int, str] | None:
    """Fetch the active period from Notion Periodo DB.
    Returns (budget, page_id) or None if no active period found."""
    if not NOTION_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "page_size": 1}
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{PERIODO_DB}/query",
        headers=headers,
        json=data,
    )
    if resp.status_code != 200:
        return None
    for result in resp.json().get("results", []):
        page_id = result.get("id", "")
        props = result.get("properties", {})
        budget = 1_000_000
        for k, v in props.items():
            if v.get("type") == "number":
                budget = v.get("number", 1_000_000)
        return (budget, page_id)
    return None


def register_notion(amount: int, merchant: str, category: str, source: str = "CMR", period_page_id: str = "") -> bool:
    """Register expense in Notion Movimientos DB with period relation."""
    if not NOTION_API_KEY:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    merchant_display = f"{merchant} [{source}]"[:60]
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    props = {
        "Nombre": {"title": [{"text": {"content": merchant_display}}]},
        "Monto": {"number": amount},
        "Fecha": {"date": {"start": today}},
        "Categoría": {"select": {"name": category}},
    }
    if period_page_id:
        props["Periodo"] = {"relation": [{"id": period_page_id}]}
    data = {
        "parent": {"database_id": MOVIMIENTOS_DB},
        "properties": props,
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
    app.logger.info(f"Notion create page: {resp.status_code}")
    if not resp.ok:
        app.logger.error(f"Notion error: {resp.text[:200]}")
    return resp.status_code == 200


def get_monthly_spent(period_page_id: str = "") -> int:
    """Get total spent from Notion, filtered by period relation."""
    if not NOTION_API_KEY:
        return 0
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = {"page_size": 100}
    if period_page_id:
        data["filter"] = {
            "property": "Periodo",
            "relation": {"contains": period_page_id},
        }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{MOVIMIENTOS_DB}/query",
        headers=headers,
        json=data,
    )
    if resp.status_code != 200:
        return 0
    total = 0
    for result in resp.json().get("results", []):
        props = result.get("properties", {})
        for k, v in props.items():
            if v.get("type") == "number":
                total += v.get("number", 0)
    return total


def send_telegram(message: str):
    """Send message to the budget Telegram group."""
    if not TELEGRAM_BOT_TOKEN:
        app.logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    if not TELEGRAM_GROUP_ID:
        app.logger.error("TELEGRAM_GROUP_ID not set")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": TELEGRAM_GROUP_ID, "text": message}, timeout=10)
    if not resp.ok:
        app.logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")


def process_and_respond(amount: int, merchant: str, category: str, source: str):
    """Register expense, get budget, send Telegram, return JSON."""
    active = get_active_period()
    period_page_id = active[1] if active else ""
    budget = active[0] if active else 1_000_000

    registered = register_notion(amount, merchant, category, source, period_page_id)
    spent = get_monthly_spent(period_page_id)
    remaining = budget - spent - amount

    # Get period name from active
    period_name = "del periodo"
    if active:
        period_name = f"de {active[1][:8]}..."  # Will be replaced with proper name

    response = (
        f"✅ **${amount:,}** registrado en *{merchant}* ({source})\n"
        f"📂 Categoría: {category}\n"
        f"💰 Te quedan **${remaining:,}** del presupuesto"
    )
    send_telegram(response)

    return jsonify({
        "status": "ok",
        "amount": amount,
        "merchant": merchant,
        "category": category,
        "source": source,
        "remaining": remaining,
        "budget": budget,
    })


# ---- PARSERS ----

def parse_cmr(text: str) -> dict | None:
    """Parse CMR notification: 'Compraste $X.XXX en MERCHANT ... CHL'"""
    clean = clean_text(text)
    patterns = [
        r"Compraste\s+\$?([\d.]+)\s+en\s+(.+?)(?:\s+(?:SANTIAGO|CHL|Las Condes|Con tu))",
        r"Compraste\s+\$?([\d.]+)\s+en\s+(.+?)(?:\s+Con tu)",
    ]
    for p in patterns:
        m = re.search(p, clean, re.IGNORECASE)
        if m:
            try:
                amount_str = m.group(1).replace(".", "")
                return {
                    "amount": int(amount_str),
                    "merchant": m.group(2).strip()[:60],
                }
            except ValueError:
                return None
    return None


def parse_scotiabank(text: str) -> dict | None:
    """Parse Scotia notification: 'App Scotia. Se realizó un pago ... por $X.XXX en MERCHANT.'"""
    clean = clean_text(text)
    pattern = r"pago[^$]*\$?([\d.]+)\s+en\s+(.+?)(?:\.|$|Si\s+desconoces)"
    m = re.search(pattern, clean, re.IGNORECASE)
    if m:
        try:
            amount_str = m.group(1).replace(".", "")
            return {
                "amount": int(amount_str),
                "merchant": m.group(2).strip()[:60],
            }
        except ValueError:
            return None
    return None


# ---- ENDPOINTS ----

@app.route("/")
def home():
    return jsonify({"status": "ok", "service": "budget-webhook"})


@app.route("/test-telegram", methods=["GET"])
def test_telegram():
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"}), 400
    if not TELEGRAM_GROUP_ID:
        return jsonify({"error": "TELEGRAM_GROUP_ID not set"}), 400
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_GROUP_ID,
        "text": "🧪 Test desde budget-webhook — si ves esto, Telegram funciona ✅"
    }, timeout=10)
    return jsonify({
        "status": resp.ok,
        "code": resp.status_code,
        "response": resp.json() if resp.ok else resp.text[:200],
    })


@app.route("/tasker", methods=["GET"])
def tasker_webhook():
    """Generic endpoint — auto-detect CMR or Scotia."""
    text = request.args.get("text", "")
    if not text:
        return jsonify({"ok": False, "reason": "no text"}), 200

    parsed = parse_cmr(text)
    if parsed:
        cat = infer_category(parsed["merchant"])
        return process_and_respond(parsed["amount"], parsed["merchant"], cat, "CMR")

    parsed = parse_scotiabank(text)
    if parsed:
        cat = infer_category(parsed["merchant"])
        return process_and_respond(parsed["amount"], parsed["merchant"], cat, "Scotia")

    return jsonify({"ok": True, "reason": "not a recognized expense"}), 200


@app.route("/tasker/cmr", methods=["GET"])
def tasker_cmr():
    """CMR-only endpoint."""
    text = request.args.get("text", "")
    if not text:
        return jsonify({"ok": False, "reason": "no text"}), 200
    parsed = parse_cmr(text)
    if not parsed:
        return jsonify({"ok": True, "reason": "not a CMR purchase"}), 200
    cat = infer_category(parsed["merchant"])
    return process_and_respond(parsed["amount"], parsed["merchant"], cat, "CMR")


@app.route("/tasker/scotiabank", methods=["GET"])
def tasker_scotiabank():
    """Scotia-only endpoint."""
    text = request.args.get("text", "")
    if not text:
        return jsonify({"ok": False, "reason": "no text"}), 200
    parsed = parse_scotiabank(text)
    if not parsed:
        return jsonify({"ok": True, "reason": "not a Scotia expense"}), 200
    cat = infer_category(parsed["merchant"])
    return process_and_respond(parsed["amount"], parsed["merchant"], cat, "Scotia")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
