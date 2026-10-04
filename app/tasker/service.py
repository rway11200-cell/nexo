import re
from datetime import datetime

from app.config import DEBUG
from app.tasker import repository

CATEGORY_KEYWORDS = {
    "comida": [
        "restaurant", "starbucks", "café", "sushi", "pizza", "delivery",
        "pedidos", "super", "tottus", "lider", "jumbo", "mercado",
    ],
    "salud": ["farmacia", "salud", "médico", "indisa", "red salud", "clínica"],
    "transporte": ["uber", "taxi", "cabify", "benzo", "metro", "bip", "pasaje"],
    "auto": ["benzo", "automotora", "neumático", "bencina", "copec", "shell"],
    "perritos": ["mascota", "dog", "perro", "veterinaria", "pet"],
    "vestuario": ["zara", "h&m", "ripley", "falabella", "paris", "vestuario", "ropa"],
    "suscripciones": ["apple", "netflix", "spotify", "disney", "hbomax", "amazon"],
}


def clean_text(text: str) -> str:
    return re.sub(r"%20|%evtprm\d|%NTITLE|%NTEXT|cl\.android", "", text).strip()


def infer_category(comercio: str) -> str:
    comercio_lower = comercio.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in comercio_lower:
                return category
    return "otro"


def parse_cmr(text: str) -> dict | None:
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


def get_budget_summary(period_page_id: str = "", budget: int = 1_000_000) -> dict:
    spent = repository.get_monthly_spent(period_page_id)
    remaining = budget - spent
    today = datetime.now()
    days_in_month = (
        today.replace(month=today.month % 12 + 1, day=1) - today.replace(day=1)
    ).days
    day_of_month = today.day
    month_pct = round(day_of_month / days_in_month * 100)
    spent_pct = round(spent / budget * 100) if budget > 0 else 0
    pace = round(spent_pct / month_pct * 100) if month_pct > 0 else 0
    days_remaining = max(days_in_month - day_of_month, 0)
    daily_available = (
        round(remaining / days_remaining) if days_remaining > 0 else remaining
    )
    daily_average = round(spent / day_of_month) if day_of_month > 0 else 0
    projected_total = round(daily_average * days_in_month)

    if remaining < 0:
        advice = "🔴 ¡Te pasaste del presupuesto!"
    elif spent_pct > month_pct + 10:
        advice = "⚠️ Vas más gastado de lo que deberías al día de hoy"
    elif spent_pct > month_pct:
        advice = "🟡 Llevas un poco más gastado del ideal"
    elif spent_pct < month_pct - 10:
        advice = "🟢 Vas bien! Estás gastando menos de lo esperado"
    else:
        advice = "✅ Vas al día con el presupuesto"

    if projected_total > budget * 1.10:
        status = "🔴 Ritmo alto"
    elif projected_total > budget:
        status = "🟡 Ritmo elevado"
    else:
        status = "🟢 Ritmo controlado"

    return {
        "spent": spent,
        "remaining": remaining,
        "budget": budget,
        "day": day_of_month,
        "days_total": days_in_month,
        "month_pct": month_pct,
        "spent_pct": spent_pct,
        "pace": pace,
        "advice": advice,
        "days_remaining": days_remaining,
        "daily_available": daily_available,
        "daily_average": daily_average,
        "projected_total": projected_total,
        "status": status,
    }


def format_budget_summary(
    s: dict,
    merchant: str = "",
    amount: int = 0,
    category: str = "",
    source: str = "",
):
    lines = []
    if merchant:
        lines.append(f"🧾 **${amount:,}** en *{merchant}*")
    lines.append(f"💰 Restan **${s['remaining']:,}**")
    lines.append(f"💵 Disponible promedio: **${s['daily_available']:,}/día**")
    lines.append(f"📈 Proyección: **${s['projected_total']:,}**")
    lines.append(s["status"])
    return "\n".join(lines)


def process_and_respond(amount: int, merchant: str, category: str, source: str) -> dict:
    active = repository.get_active_period()
    period_page_id = active[1] if active else ""
    budget_val = active[0] if active else 1_000_000

    repository.register_notion(amount, merchant, category, source, period_page_id)

    summary = get_budget_summary(period_page_id, budget_val)

    msg = format_budget_summary(summary, merchant, amount, category, source)
    repository.send_telegram(msg)

    return summary
