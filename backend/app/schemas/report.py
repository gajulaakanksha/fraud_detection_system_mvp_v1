from datetime import datetime

from pydantic import BaseModel


class TransactionListItem(BaseModel):
    transaction_id: str
    time: datetime
    customer_id: str
    merchant_id: str
    amount: float
    currency: str
    decision_band: str
    risk_level: str


class TransactionListResponse(BaseModel):
    results: list[TransactionListItem]
    page: int
    page_size: int
    total: int
