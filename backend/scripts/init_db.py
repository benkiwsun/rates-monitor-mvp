from __future__ import annotations

from pathlib import Path

from backend.app.db import get_conn


COUNTRIES = [
    ("US", "美国", "United States", "America/New_York"),
    ("CN", "中国", "China", "Asia/Shanghai"),
    ("JP", "日本", "Japan", "Asia/Tokyo"),
    ("GB", "英国", "United Kingdom", "Europe/London"),
    ("EU", "欧元区", "Euro Area", "Europe/Brussels"),
    ("CH", "瑞士", "Switzerland", "Europe/Zurich"),
    ("CA", "加拿大", "Canada", "America/Toronto"),
    ("AU", "澳大利亚", "Australia", "Australia/Sydney"),
]


INDICATORS = [
    ("FED_TARGET_UPPER", "美联储目标利率上限", "Fed Target Upper", "policy_rate", "US"),
    ("SOFR", "SOFR", "SOFR", "money_market", "US"),
    ("EFFR", "EFFR", "EFFR", "money_market", "US"),
    ("US2Y", "美国2Y国债", "US 2Y Treasury", "gov_bond_yield", "US"),
    ("US10Y", "美国10Y国债", "US 10Y Treasury", "gov_bond_yield", "US"),
    ("US30Y", "美国30Y国债", "US 30Y Treasury", "gov_bond_yield", "US"),
    ("CN1Y", "中国1Y国债", "China 1Y Gov Bond", "gov_bond_yield", "CN"),
    ("CN10Y", "中国10Y国债", "China 10Y Gov Bond", "gov_bond_yield", "CN"),
    ("CN30Y", "中国30Y国债", "China 30Y Gov Bond", "gov_bond_yield", "CN"),
    ("LPR1Y", "LPR1Y", "LPR 1Y", "policy_rate", "CN"),
    ("LPR5Y", "LPR5Y", "LPR 5Y", "policy_rate", "CN"),
    ("PBOC_7D_REPO", "PBOC 7D逆回购", "PBOC 7D Repo", "policy_rate", "CN"),
    ("BOJ_POLICY_RATE", "日本央行政策利率", "BoJ Policy Rate", "policy_rate", "JP"),
    ("BOE_BANK_RATE", "英国央行政策利率", "BoE Bank Rate", "policy_rate", "GB"),
    ("ECB_DFR", "欧央行存款便利利率", "ECB Deposit Facility Rate", "policy_rate", "EU"),
    ("SNB_POLICY_RATE", "瑞士央行政策利率", "SNB Policy Rate", "policy_rate", "CH"),
    ("BOC_POLICY_RATE", "加拿大央行政策利率", "BoC Policy Rate", "policy_rate", "CA"),
    ("RBA_CASH_RATE", "澳央行现金利率", "RBA Cash Rate", "policy_rate", "AU"),
    ("CN_US_10Y", "中美10Y利差", "CN-US 10Y Spread", "spread", "CN"),
    ("CN_US_2Y", "中美2Y利差", "CN-US 2Y Spread", "spread", "CN"),
    ("US_10Y_2Y", "美国10Y-2Y", "US 10Y-2Y", "spread", "US"),
    ("CN_10Y_1Y", "中国10Y-1Y", "CN 10Y-1Y", "spread", "CN"),
    ("SOFR_IORB_PROXY", "SOFR-IORB代理", "SOFR-IORB Proxy", "spread", "US"),
]


SOURCES = [
    ("fred", "FRED", "https://fred.stlouisfed.org"),
    ("ecb", "ECB Data API", "https://data-api.ecb.europa.eu"),
    ("boc", "BoC Valet API", "https://www.bankofcanada.ca/valet"),
    ("boe", "Bank of England IADB", "https://www.bankofengland.co.uk"),
    ("boj", "Bank of Japan stat-search", "https://www.stat-search.boj.or.jp"),
    ("snb", "SNB data portal", "https://data.snb.ch"),
    ("rba", "Reserve Bank of Australia", "https://www.rba.gov.au"),
    ("pboc", "People's Bank of China", "http://www.pbc.gov.cn"),
    ("computed", "Internal Compute", ""),
]


def main() -> None:
    schema_sql = Path("backend/sql/schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(schema_sql)

        for code, cn, en, tz in COUNTRIES:
            cur.execute(
                """
                insert into dim_country(country_code, country_name_cn, country_name_en, timezone)
                values (%s,%s,%s,%s)
                on conflict (country_code) do update set
                  country_name_cn = excluded.country_name_cn,
                  country_name_en = excluded.country_name_en,
                  timezone = excluded.timezone,
                  updated_at = now()
                """,
                (code, cn, en, tz),
            )

        for code, cn, en, category, country in INDICATORS:
            cur.execute(
                """
                insert into dim_indicator(
                  indicator_code, indicator_name_cn, indicator_name_en, category, country_code, unit, frequency, is_computed
                )
                values (%s,%s,%s,%s,%s,'pct','daily',%s)
                on conflict (indicator_code) do update set
                  indicator_name_cn = excluded.indicator_name_cn,
                  indicator_name_en = excluded.indicator_name_en,
                  category = excluded.category,
                  country_code = excluded.country_code,
                  updated_at = now()
                """,
                (code, cn, en, category, country, category == "spread"),
            )

        for source_code, source_name, base_url in SOURCES:
            cur.execute(
                """
                insert into dim_source(source_code, source_name, base_url)
                values (%s,%s,%s)
                on conflict (source_code) do update set
                  source_name = excluded.source_name,
                  base_url = excluded.base_url,
                  updated_at = now()
                """,
                (source_code, source_name, base_url),
            )

    print("Database initialized and seed metadata upserted.")


if __name__ == "__main__":
    main()
