import os
import re
import json
from datetime import datetime

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NOTION_API_KEY = os.environ.get("NOTION_API_TOKEN", "")
MOVIMIENTOS_DB = os.environ.get("MOVIMIENTOS_DB", "")
BUDGET_MONTHLY = 1_000_000  # $1,000,000/month

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


def parse_cmr(text: str) -> dict | None:
    """Parse CMR notification text. Returns {amount, merchant, date} or None."""
    # Pattern: "Compraste $X.XXX en MERCHANT ... CHL"
    pattern = r"Compraste\s+\$?([\d.]+)\s+en\s+(.+?)(?:\s+(?:SANTIAGO|CHL|Las Condes|Con tu))"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        # Try simpler: "Compraste $X.XXX en ..."
        pattern2 = r"Compraste\s+\$?([\d.]+)\s+en\s+(.+)"
        match = re.search(pattern2, text, re.IGNORECASE)
    if match:
        amount_str = match.group(1).replace(".", "")
        merchant = match.group(2).strip()[:60]
        try:
            amount = int(amount_str)
        except ValueError:
            return None
        return {
            "amount": amount,
            "merchant": merchant,
        }
    return None


def register_notion(amount: int, merchant: str, category: str) -> bool:
    """Register expense in Notion Movimientos DB."""
    if not NOTION_API_KEY:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
    data = {
        "parent": {"type": "data_source_id", "data_source_id": MOVIMIENTOS_DB},
        "properties": {
            "Name": {"title": [{"text": {"content": merchant}}]},
            "$": {"number": amount},
            "Fecha": {"date": {"start": today}},
            "Categoria": {"select": {"name": category}},
        },
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
    return resp.status_code == 200


def get_monthly_spent() -> int:
    """Get total spent this month from Notion."""
    if not NOTION_API_KEY:
        return 0
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
    month_start = datetime.now().strftime("%Y-%m-01")
    month_end = datetime.now().strftime("%Y-%m-%d")
    data = {
        "filter": {
            "property": "Fecha",
            "date": {"on_or_after": month_start, "on_or_before": month_end},
        }
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


@app.route("/")
def home():
    return jsonify({"status": "ok", "service": "budget-webhook"})


@app.route("/tasker", methods=["GET"])
def tasker_webhook():
    """Endpoint that Tasker calls with CMR notifications."""
    text = request.args.get("text", "")
    if not text:
        return jsonify({"error": "no text"}), 400

    parsed = parse_cmr(text)
    if not parsed:
        return jsonify({"error": "could not parse", "text": text[:100]}), 400

    amount = parsed["amount"]
    merchant = parsed["merchant"]
    category = infer_category(merchant)

    # Register in Notion
    registered = register_notion(amount, merchant, category)

    # Get budget remaining
    spent = get_monthly_spent()
    remaining = BUDGET_MONTHLY - spent - amount

    # Format response
    response = (
        f"✅ **${amount:,}** registrado en *{merchant}*\n"
        f"📂 Categoría: {category}\n"
        f"💰 Te quedan **${remaining:,}** del presupuesto de julio"
    )

    # Send to Telegram group
    send_telegram(response)

    return jsonify({
        "status": "ok",
        "amount": amount,
        "merchant": merchant,
        "category": category,
        "remaining": remaining,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
