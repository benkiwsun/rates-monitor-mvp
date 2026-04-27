from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


TODAY = date.today()


def _daily_points(base: float, step: float, code: str, source: str = "seed") -> list[dict]:
    points: list[dict] = []
    for i in range(20):
        d = TODAY - timedelta(days=19 - i)
        points.append(
            {
                "code": code,
                "obs_time": d,
                "value": round(base + step * i, 4),
                "unit": "pct",
                "source": source,
            }
        )
    return points


RATE_SERIES: dict[str, list[dict]] = {
    "FED_TARGET_UPPER": _daily_points(3.75, 0.0, "FED_TARGET_UPPER", "fred"),
    "SOFR": _daily_points(3.56, 0.001, "SOFR", "fred"),
    "EFFR": _daily_points(3.58, 0.001, "EFFR", "fred"),
    "US2Y": _daily_points(3.91, 0.002, "US2Y", "fred"),
    "US10Y": _daily_points(4.18, 0.002, "US10Y", "fred"),
    "US30Y": _daily_points(4.35, 0.001, "US30Y", "fred"),
    "CN1Y": _daily_points(1.71, -0.001, "CN1Y", "chinabond"),
    "CN10Y": _daily_points(2.34, -0.0005, "CN10Y", "chinabond"),
    "CN30Y": _daily_points(2.57, -0.0004, "CN30Y", "chinabond"),
    "LPR1Y": _daily_points(3.45, 0.0, "LPR1Y", "pbc"),
    "LPR5Y": _daily_points(3.95, 0.0, "LPR5Y", "pbc"),
    "PBOC_7D_REPO": _daily_points(1.8, 0.0, "PBOC_7D_REPO", "pbc"),
    "BOJ_POLICY_RATE": _daily_points(0.1, 0.0, "BOJ_POLICY_RATE", "boj"),
    "BOE_BANK_RATE": _daily_points(4.25, 0.0, "BOE_BANK_RATE", "boe"),
    "ECB_DFR": _daily_points(2.75, 0.0, "ECB_DFR", "ecb"),
    "SNB_POLICY_RATE": _daily_points(1.25, 0.0, "SNB_POLICY_RATE", "snb"),
    "BOC_POLICY_RATE": _daily_points(3.25, 0.0, "BOC_POLICY_RATE", "boc"),
    "RBA_CASH_RATE": _daily_points(4.1, 0.0, "RBA_CASH_RATE", "rba"),
}


def latest_for(code: str) -> dict | None:
    series = RATE_SERIES.get(code)
    if not series:
        return None
    return series[-1]


def previous_for(code: str) -> dict | None:
    series = RATE_SERIES.get(code)
    if not series or len(series) < 2:
        return None
    return series[-2]


def build_spread(code: str) -> list[dict]:
    if code == "CN_US_10Y":
        left = RATE_SERIES["CN10Y"]
        right = RATE_SERIES["US10Y"]
    elif code == "CN_US_2Y":
        left = RATE_SERIES["CN1Y"]
        right = RATE_SERIES["US2Y"]
    elif code == "US_10Y_2Y":
        left = RATE_SERIES["US10Y"]
        right = RATE_SERIES["US2Y"]
    elif code == "CN_10Y_1Y":
        left = RATE_SERIES["CN10Y"]
        right = RATE_SERIES["CN1Y"]
    elif code == "SOFR_IORB_PROXY":
        left = RATE_SERIES["SOFR"]
        right = RATE_SERIES["FED_TARGET_UPPER"]
    else:
        return []

    spread = []
    for lp, rp in zip(left, right):
        spread.append(
            {
                "code": code,
                "obs_time": lp["obs_time"],
                "value": round(lp["value"] - rp["value"], 4),
                "unit": "pct",
            }
        )
    return spread


SPREAD_SERIES = {
    k: build_spread(k)
    for k in ["CN_US_10Y", "CN_US_2Y", "US_10Y_2Y", "CN_10Y_1Y", "SOFR_IORB_PROXY"]
}


ALERT_RULES = [
    {
        "rule_code": "CN_US_10Y_LT_N200BP",
        "rule_name": "中美10Y利差低于-200bp",
        "metric_code": "CN_US_10Y",
        "condition_expr": "value < -2.00",
        "severity": "critical",
        "cooldown_minutes": 180,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
]


ALERT_EVENTS = [
    {
        "alert_id": 1,
        "rule_code": "CN_US_10Y_LT_N200BP",
        "trigger_time": datetime.now(timezone.utc) - timedelta(hours=2),
        "metric_code": "CN_US_10Y",
        "metric_value": -2.03,
        "status": "open",
        "severity": "critical",
        "message": "中美10Y利差跌破-200bp阈值",
    }
]


SUBSCRIPTIONS: list[dict] = []
