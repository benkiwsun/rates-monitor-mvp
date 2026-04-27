from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

import requests
from dateutil import parser as date_parser

from ..http_utils import DEFAULT_HEADERS


class CentralBankProvider:
    """Official central-bank HTTP sources (non-FRED).

    Implemented:
    - ECB deposit facility (data-api.ecb.europa.eu)
    - Bank of Canada Valet API
    - Bank of England IADB CSV (Official Bank Rate daily, IUDBEDR)
    - Swiss National Bank data.snb.ch CSV (SNB policy rate, D0=LZ)
    - Bank of Japan stat-search API (Basic discount/loan rate monthly, MADR1M)
    - Reserve Bank of Australia cash rate target (statistics page HTML table)
    """

    def __init__(self, timeout_s: int = 30) -> None:
        self.timeout_s = timeout_s
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

    # --- ECB (existing) ---
    def fetch_ecb_dfr(self) -> list[dict[str, Any]]:
        url = "https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.DFR.LEV"
        params = {"format": "jsondata", "lastNObservations": "120"}
        resp = self._session.get(url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        data = resp.json()

        rows: list[dict[str, Any]] = []
        series = data.get("dataSets", [{}])[0].get("series", {})
        if not series:
            return rows
        first_key = next(iter(series.keys()))
        obs_map = series[first_key].get("observations", {})

        time_values = data.get("structure", {}).get("dimensions", {}).get("observation", [])[0].get("values", [])
        for k, v in obs_map.items():
            idx = int(k)
            if idx >= len(time_values):
                continue
            obs_date = time_values[idx]["id"]
            rows.append(
                {
                    "observation_time": datetime.fromisoformat(f"{obs_date}T00:00:00"),
                    "value": float(v[0]),
                    "source_ref": "ECB_DFR",
                }
            )
        rows.sort(key=lambda x: x["observation_time"])
        return rows

    # --- Bank of Canada (existing) ---
    def fetch_boc_policy_rate(self) -> list[dict[str, Any]]:
        url = "https://www.bankofcanada.ca/valet/observations/V39079/json"
        params = {"recent": "120"}
        resp = self._session.get(url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        rows: list[dict[str, Any]] = []
        for obs in data.get("observations", []):
            raw = obs.get("V39079", {}).get("v")
            if raw is None:
                continue
            rows.append(
                {
                    "observation_time": datetime.fromisoformat(f"{obs['d']}T00:00:00"),
                    "value": float(raw),
                    "source_ref": "BOC_V39079",
                }
            )
        return rows

    # --- Bank of England: Official Bank Rate daily (IUDBEDR) ---
    def fetch_boe_official_bank_rate(self) -> list[dict[str, Any]]:
        """BoE Database CSV export (official). Requires browser-like User-Agent."""
        url = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
        params = {
            "csv.x": "yes",
            "Datefrom": "01/Jan/2015",
            "Dateto": "now",
            "SeriesCodes": "IUDBEDR",
            "UsingCodes": "Y",
            "CSVF": "TN",
        }
        resp = self._session.get(url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        text = resp.text
        # Tabular no titles: first line header DATE,IUDBEDR then rows
        reader = csv.reader(io.StringIO(text.strip()))
        header = next(reader, None)
        if not header or len(header) < 2:
            return []
        rows: list[dict[str, Any]] = []
        for parts in reader:
            if len(parts) < 2:
                continue
            d_raw, val_raw = parts[0].strip(), parts[1].strip()
            if not d_raw or not val_raw:
                continue
            try:
                obs = date_parser.parse(d_raw, dayfirst=True)
            except (ValueError, TypeError):
                continue
            rows.append(
                {
                    "observation_time": datetime(obs.year, obs.month, obs.day),
                    "value": float(val_raw),
                    "source_ref": "IUDBEDR",
                }
            )
        rows.sort(key=lambda x: x["observation_time"])
        return rows

    # --- Swiss National Bank: policy rate (monthly) ---
    def fetch_snb_policy_rate(self) -> list[dict[str, Any]]:
        url = "https://data.snb.ch/api/cube/snboffzisa/data/csv/en"
        resp = self._session.get(url, timeout=self.timeout_s)
        resp.raise_for_status()
        resp.encoding = "utf-8-sig"
        reader = csv.reader(io.StringIO(resp.text), delimiter=";")
        rows_out: list[dict[str, Any]] = []
        for row in reader:
            if len(row) < 3:
                continue
            period, dim0, val = row[0].strip(), row[1].strip(), row[2].strip()
            if dim0 != "LZ" or not val:
                continue
            # period like 2019-06 (monthly)
            try:
                y, m = period.split("-")
                obs = datetime(int(y), int(m), 1)
            except (ValueError, IndexError):
                continue
            rows_out.append(
                {
                    "observation_time": obs,
                    "value": float(val),
                    "source_ref": "snboffzisa_LZ",
                }
            )
        rows_out.sort(key=lambda x: x["observation_time"])
        return rows_out

    # --- Bank of Japan: Basic discount/loan rate (monthly) ---
    def fetch_boj_basic_rate_monthly(self) -> list[dict[str, Any]]:
        """BoJ Time-Series Data Search API (/getDataCode), series MADR1M, DB IR01."""
        url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
        params = {
            "format": "json",
            "lang": "en",
            "db": "IR01",
            "startDate": "200001",
            "endDate": datetime.now().strftime("%Y%m"),
            "code": "MADR1M",
        }
        resp = self._session.get(url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        if data.get("STATUS") != 200:
            return []
        result_set = data.get("RESULTSET") or []
        if not result_set:
            return []
        block = result_set[0]
        values_block = block.get("VALUES") or {}
        dates = values_block.get("SURVEY_DATES") or []
        vals = values_block.get("VALUES") or []
        rows: list[dict[str, Any]] = []
        for ym, v in zip(dates, vals):
            if v is None:
                continue
            ym_int = int(ym)
            year, month = ym_int // 100, ym_int % 100
            rows.append(
                {
                    "observation_time": datetime(year, month, 1),
                    "value": float(v),
                    "source_ref": "IR01_MADR1M",
                }
            )
        rows.sort(key=lambda x: x["observation_time"])
        return rows

    # --- Reserve Bank of Australia: cash rate target ---
    def fetch_rba_cash_rate_target(self) -> list[dict[str, Any]]:
        url = "https://www.rba.gov.au/statistics/cash-rate/"
        resp = self._session.get(url, timeout=self.timeout_s)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
        pat = re.compile(
            r'<th scope="row">(\d{1,2} \w{3} \d{4})</th>\s*<td>[^<]*</td>\s*<td>([0-9.]+)</td>',
            re.I,
        )
        rows: list[dict[str, Any]] = []
        for m in pat.finditer(html):
            d_raw, val_raw = m.group(1), m.group(2)
            try:
                obs = date_parser.parse(d_raw, dayfirst=True)
            except (ValueError, TypeError):
                continue
            rows.append(
                {
                    "observation_time": datetime(obs.year, obs.month, obs.day),
                    "value": float(val_raw),
                    "source_ref": "rba.gov.au/statistics/cash-rate",
                }
            )
        rows.sort(key=lambda x: x["observation_time"])
        return rows
