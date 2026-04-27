# API 清单（MVP）

Base URL: `/api/v1`

## Rates

- `GET /rates/latest?codes=FED_TARGET_UPPER,US10Y,CN10Y`
- `GET /rates/series?codes=US2Y,US10Y&start=2026-01-01&end=2026-04-22`
- `GET /rates/curve?country=US&date=2026-04-22`
- `GET /rates/policy`

## Spreads

- `GET /spreads/latest?codes=CN_US_10Y,US_10Y_2Y`
- `GET /spreads/series?code=CN_US_10Y&start=2026-01-01&end=2026-04-22`
- `POST /spreads/calculate`
  - body:
    ```json
    {
      "left_code": "CN10Y",
      "right_code": "US10Y",
      "op": "minus",
      "start": "2026-01-01",
      "end": "2026-04-22"
    }
    ```
- `GET /spreads/heatmap?date=2026-04-22&type=policy_rate`

## Alerts

- `GET /alerts/rules`
- `POST /alerts/rules`
- `GET /alerts/events?status=open&severity=critical`
- `POST /alerts/events/{alert_id}/ack`
- `POST /alerts/events/{alert_id}/close`
- `GET /alerts/subscriptions`
- `POST /alerts/subscriptions`
