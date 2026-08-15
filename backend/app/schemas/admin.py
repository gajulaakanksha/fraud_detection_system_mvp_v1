import uuid
from datetime import datetime

from pydantic import BaseModel


class RuleOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    rule_code: str
    description: str
    severity: str
    is_active: bool
    config: dict
    updated_at: datetime


class RuleUpdateRequest(BaseModel):
    is_active: bool | None = None
    severity: str | None = None
    config: dict | None = None


class DecisionThresholdOut(BaseModel):
    model_config = {"from_attributes": True}

    band: str
    min_score: float
    max_score: float
    recommended_action: str
    policy_version: str
    updated_at: datetime


class DecisionThresholdUpdateRequest(BaseModel):
    min_score: float | None = None
    max_score: float | None = None
    recommended_action: str | None = None
