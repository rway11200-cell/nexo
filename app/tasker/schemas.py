from pydantic import BaseModel, Field


class BudgetSummary(BaseModel):
    spent: int = Field(examples=[150000])
    remaining: int = Field(examples=[850000])
    budget: int = Field(examples=[1000000])
    day: int = Field(examples=[15])
    days_total: int = Field(examples=[31])
    month_pct: int = Field(examples=[48])
    spent_pct: int = Field(examples=[15])
    pace: int = Field(examples=[31])
    advice: str = Field(examples=["🟢 Vas bien! Estás gastando menos de lo esperado"])
    days_remaining: int = Field(examples=[16])
    daily_available: int = Field(examples=[53125])
    daily_average: int = Field(examples=[10000])
    projected_total: int = Field(examples=[310000])
    status: str = Field(examples=["🟢 Ritmo controlado"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "spent": 150000,
                "remaining": 850000,
                "budget": 1000000,
                "day": 15,
                "days_total": 31,
                "month_pct": 48,
                "spent_pct": 15,
                "pace": 31,
                "days_remaining": 16,
                "daily_available": 53125,
                "daily_average": 10000,
                "projected_total": 310000,
                "status": "🟢 Ritmo controlado",
                "advice": "🟢 Vas bien! Estás gastando menos de lo esperado",
            }
        }
    }


class ParseResult(BaseModel):
    amount: int = Field(examples=[15990])
    merchant: str = Field(examples=["Starbucks"])


class TaskerResult(BaseModel):
    ok: bool = True
    reason: str | None = None


class TelegramTestResponse(BaseModel):
    status: bool
    code: int
    response: dict | str
