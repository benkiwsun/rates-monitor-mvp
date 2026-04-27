from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class RatePoint(BaseModel):
    code: str
    obs_time: date
    value: float
    unit: str
    source: str


class RateLatestItem(BaseModel):
    code: str
    value: float
    unit: str
    chg_1d: float | None = None
    source: str
    obs_time: date


class RatesLatestResponse(BaseModel):
    as_of: datetime
    items: list[RateLatestItem]


class RatesSeriesResponse(BaseModel):
    code: str
    series: list[RatePoint]


class CurvePoint(BaseModel):
    tenor: str
    value: float
    unit: str = "pct"


class CurveResponse(BaseModel):
    country: str
    as_of: date
    points: list[CurvePoint]


class SpreadItem(BaseModel):
    code: str
    value: float
    unit: str = "pct"
    obs_time: date


class SpreadSeriesResponse(BaseModel):
    code: str
    series: list[SpreadItem]


class SpreadCalculateRequest(BaseModel):
    left_code: str = Field(..., description="Left indicator code")
    right_code: str = Field(..., description="Right indicator code")
    op: Literal["minus"] = "minus"
    start: date
    end: date


class AlertRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    metric_code: str
    condition_expr: str
    severity: Literal["info", "warning", "critical"]
    cooldown_minutes: int = 60
    is_active: bool = True


class AlertRule(BaseModel):
    rule_code: str
    rule_name: str
    metric_code: str
    condition_expr: str
    severity: str
    cooldown_minutes: int
    is_active: bool
    created_at: datetime


class AlertEvent(BaseModel):
    alert_id: int
    rule_code: str
    trigger_time: datetime
    metric_code: str
    metric_value: float
    status: Literal["open", "acknowledged", "closed"]
    severity: Literal["info", "warning", "critical"]
    message: str


class SubscriptionCreate(BaseModel):
    user_id: str
    channel: Literal["email", "webhook", "wecom", "telegram"]
    target: str
    min_severity: Literal["info", "warning", "critical"] = "warning"
    is_active: bool = True


class Subscription(BaseModel):
    subscription_id: int
    user_id: str
    channel: str
    target: str
    min_severity: str
    is_active: bool
    created_at: datetime


class IngestJobResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    fred_rows: int
    central_bank_rows: int
    pboc_rows: int
    spread_rows: int
    total: int


class IngestJobLatestResponse(BaseModel):
    last: IngestJobResponse | None = None
