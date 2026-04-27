from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import requests

from ..http_utils import DEFAULT_HEADERS

PBC_BASE = "http://www.pbc.gov.cn"

LPR_LIST_PATH = "/zhengcehuobisi/125207/125213/125440/index.html"
LPR_DETAIL_PREFIX = "/zhengcehuobisi/125207/125213/125440/3876551/"

OMO_LIST_PATH = "/zhengcehuobisi/125207/125213/125431/125475/index.html"
OMO_DETAIL_PREFIX = "/zhengcehuobisi/125207/125213/125431/125475/"


class PBOCProvider:
    """Official People’s Bank of China (www.pbc.gov.cn) HTML sources.

    - LPR: 货币政策司 → 利率政策 → 贷款市场报价利率（LPR）公告列表与正文
    - 7天逆回购中标利率: 公开市场业务交易公告列表与正文 / meta 摘要
    """

    def __init__(self, timeout_s: int = 30) -> None:
        self.timeout_s = timeout_s
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

    def _get_text(self, path: str) -> str:
        url = urljoin(PBC_BASE, path)
        resp = self._session.get(url, timeout=self.timeout_s)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def fetch_lpr_announcements(self, max_pages: int = 36) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (lpr1y_rows, lpr5y_rows) each with observation_time, value, source_ref."""
        html = self._get_text(LPR_LIST_PATH)
        pat = re.compile(
            r'href="(/zhengcehuobisi/125207/125213/125440/3876551/\d+/index\.html)"'
            r'[^>]*title="([^"]*公布贷款市场报价利率[^"]*)"',
        )
        seen: set[str] = set()
        paths: list[str] = []
        for m in pat.finditer(html):
            p, title = m.group(1), m.group(2)
            if "报价行名单" in title:
                continue
            if p in seen:
                continue
            seen.add(p)
            paths.append(p)
            if len(paths) >= max_pages:
                break

        rows_1y: list[dict[str, Any]] = []
        rows_5y: list[dict[str, Any]] = []
        for path in paths:
            body = self._get_text(path)
            dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", body)
            if not dm:
                continue
            obs = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            m1 = re.search(r"1年期LPR为(\d+\.\d+)%", body)
            m5 = re.search(r"5年期以上LPR为(\d+\.\d+)%", body)
            if m1:
                rows_1y.append(
                    {
                        "observation_time": obs,
                        "value": float(m1.group(1)),
                        "source_ref": path,
                    }
                )
            if m5:
                rows_5y.append(
                    {
                        "observation_time": obs,
                        "value": float(m5.group(1)),
                        "source_ref": path,
                    }
                )
        rows_1y.sort(key=lambda x: x["observation_time"])
        rows_5y.sort(key=lambda x: x["observation_time"])
        return rows_1y, rows_5y

    def fetch_omo_7d_reverse_repo(self, max_items: int = 90) -> list[dict[str, Any]]:
        """7天期逆回购操作利率（公告日），来自公开市场业务交易公告。"""
        html = self._get_text(OMO_LIST_PATH)
        pat = re.compile(
            r'href="(/zhengcehuobisi/125207/125213/125431/125475/\d+/index\.html)"'
            r'[^>]*title="([^"]*公开市场业务交易公告[^"]*)"',
        )
        seen: set[str] = set()
        paths: list[str] = []
        for m in pat.finditer(html):
            p = m.group(1)
            if p in seen:
                continue
            seen.add(p)
            paths.append(p)
            if len(paths) >= max_items:
                break

        rows: list[dict[str, Any]] = []
        for path in paths:
            body = self._get_text(path)
            meta = re.search(
                r'<meta\s+name="Description"\s+content="([^"]+)"',
                body,
                re.I,
            )
            blob = meta.group(1) if meta else body
            # e.g. ...7天1.40%... 或 7天期 ... 1.40%
            rate_m = re.search(r"7天\s*([0-9]+\.[0-9]+)\s*%", blob)
            if not rate_m:
                rate_m = re.search(r"7天期[^%]{0,80}?([0-9]+\.[0-9]+)\s*%", blob)
            if not rate_m:
                continue
            dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", blob)
            if not dm:
                dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", body)
            if not dm:
                continue
            obs = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            rows.append(
                {
                    "observation_time": obs,
                    "value": float(rate_m.group(1)),
                    "source_ref": path,
                }
            )
        rows.sort(key=lambda x: x["observation_time"])
        return rows
