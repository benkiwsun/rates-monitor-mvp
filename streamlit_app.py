"""
Streamlit UI for Rates Monitor MVP.

Run locally:  streamlit run streamlit_app.py

On Streamlit Community Cloud, set secrets (DATABASE_URL, FRED_API_KEY, …) in the app settings.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import streamlit as st

st.set_page_config(page_title="Rates Monitor", layout="wide", initial_sidebar_state="expanded")


def _secrets_into_environ() -> None:
    try:
        sec = st.secrets
        for key in (
            "DATABASE_URL",
            "FRED_API_KEY",
            "USE_SAMPLE_FALLBACK",
            "SCHEDULER_ENABLED",
            "ADMIN_INGEST_KEY",
        ):
            if key in sec and str(sec[key]).strip():
                os.environ[key] = str(sec[key]).strip()
    except FileNotFoundError:
        pass


_secrets_into_environ()

from dotenv import load_dotenv

load_dotenv(override=False)

from backend.app.config import settings
from backend.app.ingest import run_full_ingest
from backend.app.repository import get_latest_points, get_previous_point, get_series
from backend.app.sample_data import RATE_SERIES, SPREAD_SERIES, latest_for, previous_for

POLICY_CODES = [
    "FED_TARGET_UPPER",
    "PBOC_7D_REPO",
    "BOJ_POLICY_RATE",
    "BOE_BANK_RATE",
    "ECB_DFR",
    "SNB_POLICY_RATE",
    "BOC_POLICY_RATE",
    "RBA_CASH_RATE",
]

KPI_CODES = ["FED_TARGET_UPPER", "US10Y", "CN10Y", "CN_US_10Y", "US_10Y_2Y", "SOFR", "EFFR", "LPR1Y"]

CHART_CANDIDATES = sorted(
    set(POLICY_CODES)
    | {
        "US2Y",
        "US10Y",
        "US30Y",
        "CN1Y",
        "CN10Y",
        "CN30Y",
        "SOFR",
        "EFFR",
        "LPR1Y",
        "LPR5Y",
        "CN_US_10Y",
        "US_10Y_2Y",
    }
)


def _db_ok() -> bool:
    try:
        from backend.app.db import get_conn

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def _latest_row(code: str) -> dict | None:
    rows = get_latest_points([code])
    if rows:
        return rows[0]
    if settings.use_sample_fallback:
        if code in SPREAD_SERIES:
            s = SPREAD_SERIES[code]
            return {"code": code, "value": s[-1]["value"], "unit": "pct", "source": "sample", "obs_time": s[-1]["obs_time"]}
        return latest_for(code)
    return None


def _prev_row(code: str) -> dict | None:
    row = get_previous_point(code)
    if row:
        return row
    if settings.use_sample_fallback:
        if code in SPREAD_SERIES:
            s = SPREAD_SERIES[code]
            if len(s) >= 2:
                return {"value": s[-2]["value"], "obs_time": s[-2]["obs_time"]}
        return previous_for(code)
    return None


def _series(code: str, start: date | None, end: date | None) -> list[dict]:
    raw = get_series(code, start, end)
    if not raw and settings.use_sample_fallback:
        if code in SPREAD_SERIES:
            return list(SPREAD_SERIES.get(code, []))
        return list(RATE_SERIES.get(code, []))
    return raw


def main() -> None:
    st.title("Rates Monitor · Streamlit")
    st.caption("政策利率、市场利率与利差（数据来自 PostgreSQL；可一键全量采集）")

    with st.sidebar:
        st.subheader("连接与配置")
        ok = _db_ok()
        st.write("PostgreSQL:", "已连接" if ok else "未连接（请检查 DATABASE_URL）")
        st.caption(f"`USE_SAMPLE_FALLBACK` = `{settings.use_sample_fallback}`")
        if st.button("全量采集（FRED + 央行 + PBoC + 利差）", type="primary"):
            if not ok:
                st.error("数据库未连接，无法写入采集结果。")
            else:
                with st.spinner("正在采集，可能需要 1–3 分钟…"):
                    try:
                        result = run_full_ingest()
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(
                            f"完成：FRED {result['fred_rows']} 行，"
                            f"央行 {result['central_bank_rows']} 行，"
                            f"人行 {result['pboc_rows']} 行，"
                            f"利差 {result['spread_rows']} 行。"
                        )
                        st.session_state["ingest_last"] = result
        if "ingest_last" in st.session_state:
            with st.expander("上次采集详情"):
                st.json(st.session_state["ingest_last"])

    tab_overview, tab_policy, tab_charts = st.tabs(["总览 KPI", "政策利率表", "序列图"])

    with tab_overview:
        cols = st.columns(4)
        for i, code in enumerate(KPI_CODES):
            cur = _latest_row(code)
            prev = _prev_row(code) if cur else None
            with cols[i % 4]:
                if cur:
                    delta = None
                    if prev:
                        delta = round(float(cur["value"]) - float(prev["value"]), 4)
                    st.metric(
                        label=code,
                        value=f"{cur['value']:.4f}",
                        delta=delta,
                        help=f"来源: {cur.get('source', '')} · {cur.get('obs_time', '')}",
                    )
                else:
                    st.metric(label=code, value="—")

    with tab_policy:
        rows_out = []
        for code in POLICY_CODES:
            cur = _latest_row(code)
            prev = _prev_row(code) if cur else None
            if not cur:
                rows_out.append({"code": code, "value": None, "chg": None, "source": None, "obs_time": None})
                continue
            chg = round(float(cur["value"]) - float(prev["value"]), 4) if prev else None
            rows_out.append(
                {
                    "code": code,
                    "value": cur["value"],
                    "chg_1d": chg,
                    "source": cur.get("source"),
                    "obs_time": str(cur.get("obs_time")),
                }
            )
        st.dataframe(rows_out, use_container_width=True, hide_index=True)

    with tab_charts:
        default_codes = ["US10Y", "CN10Y", "FED_TARGET_UPPER"]
        picked = st.multiselect("指标（可多选）", list(CHART_CANDIDATES), default=[c for c in default_codes if c in CHART_CANDIDATES])
        days = st.slider("回溯天数", 30, 730, 365)
        end_d = date.today()
        start_d = end_d - timedelta(days=days)
        if not picked:
            st.info("请至少选择一个指标。")
        else:
            try:
                import plotly.graph_objects as go

                fig = go.Figure()
                for code in picked:
                    ser = _series(code, start_d, end_d)
                    if not ser:
                        continue
                    fig.add_trace(
                        go.Scatter(
                            x=[p["obs_time"] for p in ser],
                            y=[p["value"] for p in ser],
                            mode="lines",
                            name=code,
                        )
                    )
                fig.update_layout(
                    height=520,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    yaxis_title="%",
                    margin=dict(l=40, r=20, t=40, b=40),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.warning("未安装 plotly，请执行 pip install plotly")


if __name__ == "__main__":
    main()
