from __future__ import annotations

from datetime import datetime
from typing import Any

import requests


class FredProvider:
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, timeout_s: int = 20) -> None:
        self.api_key = api_key
        self.timeout_s = timeout_s

    def fetch_series(self, series_id: str, limit: int = 120) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is required")
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
            "limit": limit,
        }
        resp = requests.get(self.base_url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for r in data.get("observations", []):
            val = r.get("value")
            if val in (".", None):
                continue
            obs_dt = datetime.fromisoformat(f"{r['date']}T00:00:00")
            rows.append({"observation_time": obs_dt, "value": float(val), "source_ref": series_id})
        return rows
