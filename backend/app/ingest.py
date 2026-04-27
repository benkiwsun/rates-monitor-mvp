from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .config import settings
from .providers.central_banks import CentralBankProvider
from .providers.fred import FredProvider
from .providers.pboc import PBOCProvider
from .repository import upsert_indicator_value

logger = logging.getLogger(__name__)

FRED_SERIES_MAPPING = {
    "FED_TARGET_UPPER": "DFEDTARU",
    "SOFR": "SOFR",
    "EFFR": "EFFR",
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "US30Y": "DGS30",
    "CN1Y": "IRLTLT01CNM156N",
    "CN10Y": "IRLTLT01CNM157N",
    "CN30Y": "IRLTLT01CNM159N",
}


def _upsert_rows(indicator_code: str, rows: list[dict], source_code: str) -> int:
    written = 0
    for r in rows:
        upsert_indicator_value(
            indicator_code=indicator_code,
            observation_time=r["observation_time"],
            value=r["value"],
            unit="pct",
            source_code=source_code,
            source_ref=r.get("source_ref"),
        )
        written += 1
    return written


def ingest_from_fred() -> int:
    provider = FredProvider(api_key=settings.fred_api_key)
    total = 0
    for code, series_id in FRED_SERIES_MAPPING.items():
        try:
            rows = provider.fetch_series(series_id=series_id, limit=120)
            total += _upsert_rows(code, rows, "fred")
        except Exception:
            logger.exception("FRED ingest failed for %s", code)
            continue
    return total


def ingest_from_central_banks() -> int:
    provider = CentralBankProvider()
    total = 0
    jobs: list[tuple[str, str, str]] = [
        ("ECB_DFR", "fetch_ecb_dfr", "ecb"),
        ("BOC_POLICY_RATE", "fetch_boc_policy_rate", "boc"),
        ("BOE_BANK_RATE", "fetch_boe_official_bank_rate", "boe"),
        ("SNB_POLICY_RATE", "fetch_snb_policy_rate", "snb"),
        ("BOJ_POLICY_RATE", "fetch_boj_basic_rate_monthly", "boj"),
        ("RBA_CASH_RATE", "fetch_rba_cash_rate_target", "rba"),
    ]
    for indicator, method_name, source in jobs:
        try:
            method = getattr(provider, method_name)
            rows = method()
            total += _upsert_rows(indicator, rows, source)
        except Exception:
            logger.exception("Central bank ingest failed: %s (%s)", indicator, source)
            continue
    return total


def ingest_from_pboc() -> int:
    provider = PBOCProvider()
    total = 0
    try:
        lpr1y, lpr5y = provider.fetch_lpr_announcements()
        total += _upsert_rows("LPR1Y", lpr1y, "pboc")
        total += _upsert_rows("LPR5Y", lpr5y, "pboc")
    except Exception:
        logger.exception("PBoC LPR ingest failed")
    try:
        rows = provider.fetch_omo_7d_reverse_repo()
        total += _upsert_rows("PBOC_7D_REPO", rows, "pboc")
    except Exception:
        logger.exception("PBoC OMO 7D ingest failed")
    return total


def compute_spreads() -> int:
    """Compute key spreads and persist as computed values."""
    from .repository import get_series

    pairs = {
        "CN_US_10Y": ("CN10Y", "US10Y"),
        "CN_US_2Y": ("CN1Y", "US2Y"),
        "US_10Y_2Y": ("US10Y", "US2Y"),
        "CN_10Y_1Y": ("CN10Y", "CN1Y"),
        "SOFR_IORB_PROXY": ("SOFR", "FED_TARGET_UPPER"),
    }
    total = 0
    start = (datetime.now(timezone.utc) - timedelta(days=365)).date()
    for spread_code, (l_code, r_code) in pairs.items():
        left = {row["obs_time"]: row for row in get_series(l_code, start, None)}
        right = {row["obs_time"]: row for row in get_series(r_code, start, None)}
        common_dates = sorted(set(left.keys()) & set(right.keys()))
        for d in common_dates:
            value = round(float(left[d]["value"]) - float(right[d]["value"]), 6)
            upsert_indicator_value(
                indicator_code=spread_code,
                observation_time=datetime.fromisoformat(f"{d}T00:00:00"),
                value=value,
                unit="pct",
                source_code="computed",
                value_type="computed",
                source_ref=f"{l_code}-{r_code}",
            )
            total += 1
    return total


_last_ingest_status: dict | None = None


def get_last_ingest_status() -> dict | None:
    return _last_ingest_status


def run_full_ingest() -> dict:
    """Run FRED, all official central banks, PBoC, then spread recompute."""
    global _last_ingest_status
    started = datetime.now(timezone.utc)
    fred_rows = ingest_from_fred()
    cb_rows = ingest_from_central_banks()
    pboc_rows = ingest_from_pboc()
    spread_rows = compute_spreads()
    finished = datetime.now(timezone.utc)
    _last_ingest_status = {
        "started_at": started,
        "finished_at": finished,
        "fred_rows": fred_rows,
        "central_bank_rows": cb_rows,
        "pboc_rows": pboc_rows,
        "spread_rows": spread_rows,
        "total": fred_rows + cb_rows + pboc_rows + spread_rows,
    }
    return _last_ingest_status
