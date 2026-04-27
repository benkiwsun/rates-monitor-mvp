from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .ingest import get_last_ingest_status, run_full_ingest
from .repository import (
    create_subscription as repo_create_subscription,
    get_latest_points,
    get_previous_point,
    get_series,
    insert_alert_rule,
    list_alert_events,
    list_alert_rules,
    list_subscriptions as repo_list_subscriptions,
    update_alert_status,
)
from .sample_data import ALERT_EVENTS, SPREAD_SERIES, latest_for, previous_for
from .schemas import (
    AlertEvent,
    AlertRule,
    AlertRuleCreate,
    CurvePoint,
    CurveResponse,
    IngestJobLatestResponse,
    IngestJobResponse,
    RateLatestItem,
    RatePoint,
    RatesLatestResponse,
    RatesSeriesResponse,
    SpreadCalculateRequest,
    SpreadItem,
    SpreadSeriesResponse,
    Subscription,
    SubscriptionCreate,
)
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Rates Monitor MVP API",
    version="0.1.0",
    description="Interest rates monitoring API for US/CN and major non-US economies.",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="backend/app/templates")
app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")


def _parse_codes(codes: str) -> list[str]:
    return [c.strip() for c in codes.split(",") if c.strip()]


def _verify_ingest_auth(
    x_ingest_key: str | None = Header(None, alias="X-Ingest-Key"),
    ingest_key: str | None = Query(None, description="Same as X-Ingest-Key when ADMIN_INGEST_KEY is set"),
) -> None:
    expected = settings.admin_ingest_key
    if not expected:
        return
    if (x_ingest_key or ingest_key or "") != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid ingest key")


def _latest_with_fallback(code: str) -> dict | None:
    rows = get_latest_points([code])
    if rows:
        return rows[0]
    if settings.use_sample_fallback:
        return latest_for(code)
    return None


def _prev_with_fallback(code: str) -> dict | None:
    row = get_previous_point(code)
    if row:
        return row
    if settings.use_sample_fallback:
        return previous_for(code)
    return None


@app.post("/api/v1/jobs/ingest", response_model=IngestJobResponse)
def trigger_full_ingest(_: None = Depends(_verify_ingest_auth)) -> IngestJobResponse:
    """Run FRED + official central banks + PBoC + spread recompute (same as hourly job)."""
    result = run_full_ingest()
    return IngestJobResponse(**result)


@app.get("/api/v1/jobs/ingest/latest", response_model=IngestJobLatestResponse)
def latest_ingest_job(_: None = Depends(_verify_ingest_auth)) -> IngestJobLatestResponse:
    """Last completed full-ingest summary (manual or scheduled)."""
    last = get_last_ingest_status()
    if not last:
        return IngestJobLatestResponse(last=None)
    return IngestJobLatestResponse(last=IngestJobResponse(**last))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    cards = ["FED_TARGET_UPPER", "US10Y", "CN10Y", "CN_US_10Y", "US_10Y_2Y", "SOFR", "EFFR", "LPR1Y"]
    latest_cards = []
    for code in cards:
        if code in SPREAD_SERIES:
            row_db = _latest_with_fallback(code)
            prev_db = _prev_with_fallback(code)
            if row_db:
                row = row_db
                prev = prev_db
                chg = round(row["value"] - prev["value"], 4) if prev else 0.0
            else:
                row = SPREAD_SERIES[code][-1]
                prev = SPREAD_SERIES[code][-2]
                chg = round(row["value"] - prev["value"], 4)
            latest_cards.append(
                {"code": code, "value": row["value"], "unit": row.get("unit", "pct"), "chg_1d": chg}
            )
        else:
            row = _latest_with_fallback(code)
            prev = _prev_with_fallback(code)
            if row:
                latest_cards.append(
                    {
                        "code": code,
                        "value": row["value"],
                        "unit": row["unit"],
                        "chg_1d": round(row["value"] - prev["value"], 4) if prev else 0.0,
                    }
                )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "as_of": datetime.now(timezone.utc),
            "cards": latest_cards,
            "alerts": list_alert_events()[:6] or ALERT_EVENTS,
            "sections": [
                "KPI卡片区",
                "中美利率与利差主图",
                "央行政策利率热力图",
                "US/CN收益率曲线截面对比",
                "传导洞察与告警摘要",
            ],
        },
    )


@app.get("/api/v1/rates/latest", response_model=RatesLatestResponse)
def rates_latest(codes: str = Query(..., description="Comma-separated indicator codes")) -> RatesLatestResponse:
    items: list[RateLatestItem] = []
    requested = _parse_codes(codes)
    db_rows = {r["code"]: r for r in get_latest_points(requested)}
    for code in requested:
        cur = db_rows.get(code) or (_latest_with_fallback(code) if settings.use_sample_fallback else None)
        prev = get_previous_point(code) or (_prev_with_fallback(code) if settings.use_sample_fallback else None)
        if not cur:
            continue
        items.append(
            RateLatestItem(
                code=code,
                value=cur["value"],
                unit=cur["unit"],
                chg_1d=round(cur["value"] - prev["value"], 4) if prev else None,
                source=cur["source"],
                obs_time=cur["obs_time"],
            )
        )
    return RatesLatestResponse(as_of=datetime.now(timezone.utc), items=items)


@app.get("/api/v1/rates/series", response_model=list[RatesSeriesResponse])
def rates_series(
    codes: str = Query(...),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> list[RatesSeriesResponse]:
    out: list[RatesSeriesResponse] = []
    for code in _parse_codes(codes):
        raw = get_series(code, start, end)
        if not raw and settings.use_sample_fallback:
            from .sample_data import RATE_SERIES
            raw = RATE_SERIES.get(code, [])
        pts = []
        for p in raw:
            if start and p["obs_time"] < start:
                continue
            if end and p["obs_time"] > end:
                continue
            pts.append(RatePoint(**p))
        out.append(RatesSeriesResponse(code=code, series=pts))
    return out


@app.get("/api/v1/rates/curve", response_model=CurveResponse)
def rates_curve(country: str = Query(..., pattern="^(US|CN)$"), date_: date | None = Query(None, alias="date")) -> CurveResponse:
    date_ = date_ or date.today()
    if country == "US":
        mapping = [("2Y", "US2Y"), ("10Y", "US10Y"), ("30Y", "US30Y")]
    else:
        mapping = [("1Y", "CN1Y"), ("10Y", "CN10Y"), ("30Y", "CN30Y")]
    points: list[CurvePoint] = []
    for tenor, code in mapping:
        row = _latest_with_fallback(code)
        if row:
            points.append(CurvePoint(tenor=tenor, value=row["value"]))
    return CurveResponse(country=country, as_of=date_, points=points)


@app.get("/api/v1/rates/policy", response_model=list[RateLatestItem])
def rates_policy() -> list[RateLatestItem]:
    policy_codes = [
        "FED_TARGET_UPPER",
        "PBOC_7D_REPO",
        "BOJ_POLICY_RATE",
        "BOE_BANK_RATE",
        "ECB_DFR",
        "SNB_POLICY_RATE",
        "BOC_POLICY_RATE",
        "RBA_CASH_RATE",
    ]
    result = []
    db_rows = {r["code"]: r for r in get_latest_points(policy_codes)}
    for code in policy_codes:
        cur = db_rows.get(code) or (_latest_with_fallback(code) if settings.use_sample_fallback else None)
        prev = get_previous_point(code) or (_prev_with_fallback(code) if settings.use_sample_fallback else None)
        if not cur:
            continue
        result.append(
            RateLatestItem(
                code=code,
                value=cur["value"],
                unit=cur["unit"],
                chg_1d=round(cur["value"] - prev["value"], 4) if prev else None,
                source=cur["source"],
                obs_time=cur["obs_time"],
            )
        )
    return result


@app.get("/api/v1/spreads/latest", response_model=list[SpreadItem])
def spreads_latest(codes: str = Query(...)) -> list[SpreadItem]:
    out = []
    for code in _parse_codes(codes):
        row = _latest_with_fallback(code)
        if row:
            out.append(SpreadItem(code=code, value=row["value"], obs_time=row["obs_time"], unit=row.get("unit", "pct")))
    return out


@app.get("/api/v1/spreads/series", response_model=SpreadSeriesResponse)
def spreads_series(code: str = Query(...), start: date | None = Query(None), end: date | None = Query(None)) -> SpreadSeriesResponse:
    series = get_series(code, start, end)
    if not series and settings.use_sample_fallback:
        series = SPREAD_SERIES.get(code)
    if series is None:
        raise HTTPException(status_code=404, detail=f"Unknown spread code: {code}")
    out = []
    for p in series:
        if start and p["obs_time"] < start:
            continue
        if end and p["obs_time"] > end:
            continue
        out.append(SpreadItem(**p))
    return SpreadSeriesResponse(code=code, series=out)


@app.post("/api/v1/spreads/calculate", response_model=SpreadSeriesResponse)
def spreads_calculate(req: SpreadCalculateRequest) -> SpreadSeriesResponse:
    left = get_series(req.left_code, req.start, req.end)
    right = get_series(req.right_code, req.start, req.end)
    if (not left or not right) and settings.use_sample_fallback:
        from .sample_data import RATE_SERIES
        left = left or RATE_SERIES.get(req.left_code, [])
        right = right or RATE_SERIES.get(req.right_code, [])
    if not left or not right:
        raise HTTPException(status_code=404, detail="left_code or right_code not found")

    out = []
    for l, r in zip(left, right):
        d = l["obs_time"]
        if d < req.start or d > req.end:
            continue
        out.append(
            SpreadItem(
                code=f"{req.left_code}_{req.right_code}",
                obs_time=d,
                value=round(l["value"] - r["value"], 4),
                unit="pct",
            )
        )
    return SpreadSeriesResponse(code=f"{req.left_code}_{req.right_code}", series=out)


@app.get("/api/v1/spreads/heatmap")
def spreads_heatmap(date_: date | None = Query(None, alias="date"), type_: str = Query("policy_rate", alias="type")) -> dict:
    date_ = date_ or date.today()
    if type_ == "policy_rate":
        rows = [
            ("US", "FED_TARGET_UPPER"),
            ("CN", "PBOC_7D_REPO"),
            ("JP", "BOJ_POLICY_RATE"),
            ("GB", "BOE_BANK_RATE"),
            ("EU", "ECB_DFR"),
            ("CH", "SNB_POLICY_RATE"),
            ("CA", "BOC_POLICY_RATE"),
            ("AU", "RBA_CASH_RATE"),
        ]
    else:
        rows = [("US", "US10Y"), ("CN", "CN10Y")]
    data = []
    for c, code in rows:
        row = _latest_with_fallback(code)
        if row:
            data.append({"country": c, "code": code, "value": row["value"]})
    return {"as_of": str(date_), "type": type_, "data": data}


@app.get("/api/v1/alerts/rules", response_model=list[AlertRule])
def alert_rules() -> list[AlertRule]:
    rows = list_alert_rules()
    if not rows and settings.use_sample_fallback:
        from .sample_data import ALERT_RULES
        rows = ALERT_RULES
    return [AlertRule(**r) for r in rows]


@app.post("/api/v1/alerts/rules", response_model=AlertRule)
def create_alert_rule(payload: AlertRuleCreate) -> AlertRule:
    row = insert_alert_rule(payload.model_dump())
    return AlertRule(**row)


@app.get("/api/v1/alerts/events", response_model=list[AlertEvent])
def alert_events(status: str | None = Query(None), severity: str | None = Query(None)) -> list[AlertEvent]:
    rows = list_alert_events(status=status, severity=severity)
    if not rows and settings.use_sample_fallback:
        rows = ALERT_EVENTS
        if status:
            rows = [x for x in rows if x["status"] == status]
        if severity:
            rows = [x for x in rows if x["severity"] == severity]
    return [AlertEvent(**r) for r in rows]


@app.post("/api/v1/alerts/events/{alert_id}/ack", response_model=AlertEvent)
def ack_alert(alert_id: int) -> AlertEvent:
    row = update_alert_status(alert_id, "acknowledged")
    if row:
        return AlertEvent(**row)
    if settings.use_sample_fallback:
        for row in ALERT_EVENTS:
            if row["alert_id"] == alert_id:
                row["status"] = "acknowledged"
                return AlertEvent(**row)
    raise HTTPException(status_code=404, detail="alert not found")


@app.post("/api/v1/alerts/events/{alert_id}/close", response_model=AlertEvent)
def close_alert(alert_id: int) -> AlertEvent:
    row = update_alert_status(alert_id, "closed")
    if row:
        return AlertEvent(**row)
    if settings.use_sample_fallback:
        for row in ALERT_EVENTS:
            if row["alert_id"] == alert_id:
                row["status"] = "closed"
                return AlertEvent(**row)
    raise HTTPException(status_code=404, detail="alert not found")


@app.get("/api/v1/alerts/subscriptions", response_model=list[Subscription])
def list_subscriptions() -> list[Subscription]:
    rows = repo_list_subscriptions()
    if not rows and settings.use_sample_fallback:
        from .sample_data import SUBSCRIPTIONS
        rows = SUBSCRIPTIONS
    return [Subscription(**x) for x in rows]


@app.post("/api/v1/alerts/subscriptions", response_model=Subscription)
def create_subscription(payload: SubscriptionCreate) -> Subscription:
    row = repo_create_subscription(payload.model_dump())
    return Subscription(**row)
