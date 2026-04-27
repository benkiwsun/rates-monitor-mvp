from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .db import get_conn

# When multiple rows share the same calendar day (e.g. legacy FRED + new official feed),
# prefer official central-bank sources over FRED for reads.
_SOURCE_RANK = """
  case v.source_code
    when 'pboc' then 1
    when 'boe' then 1
    when 'boj' then 1
    when 'snb' then 1
    when 'rba' then 1
    when 'ecb' then 1
    when 'boc' then 1
    when 'computed' then 3
    when 'fred' then 10
    else 5
  end
"""


def get_latest_points(codes: list[str]) -> list[dict[str, Any]]:
    if not codes:
        return []
    sql = f"""
    with ranked as (
      select
        v.indicator_code,
        v.observation_time::date as obs_d,
        v.value::float8 as value,
        v.unit,
        v.source_code,
        row_number() over (
          partition by v.indicator_code, (v.observation_time::date)
          order by {_SOURCE_RANK}, v.updated_at desc
        ) as rn
      from fact_indicator_value v
      where v.indicator_code = any(%s)
    ),
    dedup as (
      select indicator_code, obs_d, value, unit, source_code from ranked where rn = 1
    )
    select distinct on (indicator_code)
      indicator_code as code,
      obs_d as obs_time,
      value,
      unit,
      source_code as source
    from dedup
    order by indicator_code, obs_d desc
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (codes,))
        return list(cur.fetchall())


def get_previous_point(code: str) -> dict[str, Any] | None:
    sql = f"""
    with ranked as (
      select
        v.indicator_code,
        v.observation_time::date as obs_d,
        v.value::float8 as value,
        v.unit,
        v.source_code,
        row_number() over (
          partition by v.indicator_code, (v.observation_time::date)
          order by {_SOURCE_RANK}, v.updated_at desc
        ) as rn
      from fact_indicator_value v
      where v.indicator_code = %s
    ),
    dedup as (
      select indicator_code, obs_d, value, unit, source_code from ranked where rn = 1
    )
    select
      indicator_code as code,
      obs_d as obs_time,
      value,
      unit,
      source_code as source
    from dedup
    order by obs_d desc
    offset 1
    limit 1
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (code,))
        row = cur.fetchone()
    return row


def get_series(code: str, start: date | None, end: date | None) -> list[dict[str, Any]]:
    sql = f"""
    with ranked as (
      select
        v.indicator_code,
        v.observation_time::date as obs_d,
        v.value::float8 as value,
        v.unit,
        v.source_code,
        row_number() over (
          partition by v.indicator_code, (v.observation_time::date)
          order by {_SOURCE_RANK}, v.updated_at desc
        ) as rn
      from fact_indicator_value v
      where v.indicator_code = %s
        and (%s::date is null or v.observation_time::date >= %s::date)
        and (%s::date is null or v.observation_time::date <= %s::date)
    )
    select
      indicator_code as code,
      obs_d as obs_time,
      value,
      unit,
      source_code as source
    from ranked
    where rn = 1
    order by obs_d asc
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (code, start, start, end, end))
        return list(cur.fetchall())


def upsert_indicator_value(
    indicator_code: str,
    observation_time: datetime,
    value: float,
    unit: str,
    source_code: str,
    value_type: str = "raw",
    source_ref: str | None = None,
) -> None:
    sql = """
    insert into fact_indicator_value (
      indicator_code, observation_time, value, value_type, unit, source_code, source_ref
    ) values (%s,%s,%s,%s,%s,%s,%s)
    on conflict (indicator_code, observation_time, value_type, source_code)
    do update set
      value = excluded.value,
      unit = excluded.unit,
      source_ref = excluded.source_ref,
      updated_at = now()
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                indicator_code,
                observation_time,
                value,
                value_type,
                unit,
                source_code,
                source_ref,
            ),
        )


def insert_alert_rule(payload: dict[str, Any]) -> dict[str, Any]:
    sql = """
    insert into rule_alert (
      rule_code, rule_name, metric_code, condition_expr, severity, cooldown_minutes, is_active
    ) values (%s,%s,%s,%s,%s,%s,%s)
    on conflict (rule_code)
    do update set
      rule_name = excluded.rule_name,
      metric_code = excluded.metric_code,
      condition_expr = excluded.condition_expr,
      severity = excluded.severity,
      cooldown_minutes = excluded.cooldown_minutes,
      is_active = excluded.is_active,
      updated_at = now()
    returning rule_code, rule_name, metric_code, condition_expr, severity, cooldown_minutes, is_active, created_at
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                payload["rule_code"],
                payload["rule_name"],
                payload["metric_code"],
                payload["condition_expr"],
                payload["severity"],
                payload["cooldown_minutes"],
                payload["is_active"],
            ),
        )
        return cur.fetchone()


def list_alert_rules() -> list[dict[str, Any]]:
    sql = """
    select rule_code, rule_name, metric_code, condition_expr, severity, cooldown_minutes, is_active, created_at
    from rule_alert
    order by created_at desc
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def list_alert_events(status: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
    sql = """
    select alert_id, rule_code, trigger_time, metric_code, metric_value::float8 as metric_value,
           status, severity, message
    from fact_alert_event
    where (%s is null or status = %s)
      and (%s is null or severity = %s)
    order by trigger_time desc
    limit 100
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, status, severity, severity))
        return list(cur.fetchall())


def update_alert_status(alert_id: int, status: str) -> dict[str, Any] | None:
    sql = """
    update fact_alert_event
       set status = %s,
           ack_time = case when %s = 'acknowledged' then now() else ack_time end,
           closed_time = case when %s = 'closed' then now() else closed_time end,
           updated_at = now()
     where alert_id = %s
     returning alert_id, rule_code, trigger_time, metric_code, metric_value::float8 as metric_value,
               status, severity, message
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, status, status, alert_id))
        return cur.fetchone()


def list_subscriptions() -> list[dict[str, Any]]:
    sql = """
    select subscription_id, user_id, channel, target, min_severity, is_active, created_at
    from alert_subscription
    order by created_at desc
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def create_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    sql = """
    insert into alert_subscription (user_id, channel, target, min_severity, is_active)
    values (%s,%s,%s,%s,%s)
    returning subscription_id, user_id, channel, target, min_severity, is_active, created_at
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                payload["user_id"],
                payload["channel"],
                payload["target"],
                payload["min_severity"],
                payload["is_active"],
            ),
        )
        return cur.fetchone()
