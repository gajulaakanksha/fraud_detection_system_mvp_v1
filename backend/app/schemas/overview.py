from datetime import date

from pydantic import BaseModel


class OverviewSummary(BaseModel):
    transactions_analyzed: int
    decline_hold_rate: float
    avg_risk_score: float
    avg_processing_time_ms: float


class RiskTrendPoint(BaseModel):
    day: date
    avg_risk_score: float
    transactions: int


class TopRule(BaseModel):
    rule_code: str
    hit_count: int
