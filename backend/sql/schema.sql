-- Rates Monitor MVP database schema (PostgreSQL)

create table if not exists dim_country (
  country_code varchar(8) primary key,
  country_name_cn varchar(64) not null,
  country_name_en varchar(64) not null,
  timezone varchar(64) not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists dim_indicator (
  indicator_id bigserial primary key,
  indicator_code varchar(64) unique not null,
  indicator_name_cn varchar(128) not null,
  indicator_name_en varchar(128) not null,
  category varchar(32) not null,
  country_code varchar(8) references dim_country(country_code),
  unit varchar(16) not null,
  frequency varchar(16) not null,
  source_priority jsonb,
  is_computed boolean not null default false,
  formula_expr text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists dim_source (
  source_id bigserial primary key,
  source_code varchar(32) unique not null,
  source_name varchar(128) not null,
  base_url text,
  auth_type varchar(32) not null default 'none',
  rate_limit_per_min int,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists fact_indicator_value (
  id bigserial primary key,
  indicator_code varchar(64) not null references dim_indicator(indicator_code),
  observation_time timestamptz not null,
  value numeric(18,8) not null,
  value_type varchar(16) not null default 'raw',
  unit varchar(16) not null,
  source_code varchar(32) not null,
  source_ref text,
  is_final boolean not null default true,
  ingested_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (indicator_code, observation_time, value_type, source_code)
);

create index if not exists idx_fact_indicator_time
  on fact_indicator_value (indicator_code, observation_time desc);

create table if not exists fact_indicator_daily_snapshot (
  snapshot_date date not null,
  indicator_code varchar(64) not null references dim_indicator(indicator_code),
  latest_value numeric(18,8) not null,
  prev_1d_value numeric(18,8),
  chg_1d numeric(18,8),
  chg_5d numeric(18,8),
  pct_rank_3y numeric(6,2),
  updated_at timestamptz not null default now(),
  primary key (snapshot_date, indicator_code)
);

create table if not exists rule_alert (
  rule_id bigserial primary key,
  rule_code varchar(64) unique not null,
  rule_name varchar(128) not null,
  metric_code varchar(64) not null,
  condition_expr text not null,
  severity varchar(16) not null,
  cooldown_minutes int not null default 60,
  is_active boolean not null default true,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists fact_alert_event (
  alert_id bigserial primary key,
  rule_code varchar(64) not null references rule_alert(rule_code),
  trigger_time timestamptz not null,
  metric_code varchar(64) not null,
  metric_value numeric(18,8) not null,
  status varchar(16) not null,
  severity varchar(16) not null,
  message text not null,
  context_json jsonb,
  ack_by varchar(64),
  ack_time timestamptz,
  closed_time timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists alert_subscription (
  subscription_id bigserial primary key,
  user_id varchar(64) not null,
  channel varchar(16) not null,
  target varchar(256) not null,
  min_severity varchar(16) not null default 'warning',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists etl_job_run (
  job_run_id bigserial primary key,
  job_name varchar(64) not null,
  start_time timestamptz not null,
  end_time timestamptz,
  status varchar(16) not null,
  rows_written int default 0,
  error_message text,
  meta_json jsonb,
  created_at timestamptz not null default now()
);

create table if not exists data_quality_issue (
  issue_id bigserial primary key,
  indicator_code varchar(64) not null references dim_indicator(indicator_code),
  issue_date date not null,
  issue_type varchar(32) not null,
  issue_level varchar(16) not null,
  detail text,
  resolved boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
