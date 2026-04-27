# 数据库字段设计（MVP）

数据库采用 PostgreSQL，分四层：

- 维表：`dim_country`, `dim_indicator`, `dim_source`
- 时序事实表：`fact_indicator_value`, `fact_indicator_daily_snapshot`
- 告警与订阅：`rule_alert`, `fact_alert_event`, `alert_subscription`
- 任务与质量：`etl_job_run`, `data_quality_issue`

完整 SQL 见：`backend/sql/schema.sql`。

## 核心设计要点

- 指标统一以 `indicator_code` 建模（例如 `US10Y`, `CN10Y`, `SOFR`, `CN_US_10Y`）。
- 原始值与计算值同存 `fact_indicator_value`，通过 `value_type` 区分。
- 首页性能通过 `fact_indicator_daily_snapshot` 预聚合保证。
- 告警支持规则、事件生命周期（open/ack/closed）和订阅通知。
