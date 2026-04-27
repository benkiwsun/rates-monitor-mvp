from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/rates_monitor",
    )
    fred_api_key: str = os.getenv("FRED_API_KEY", "")
    use_sample_fallback: bool = os.getenv("USE_SAMPLE_FALLBACK", "true").lower() == "true"
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    admin_ingest_key: str = os.getenv("ADMIN_INGEST_KEY", "")
    event_calendar_url: str = os.getenv("EVENT_CALENDAR_URL", "")
    event_source_urls: dict[str, str] = None  # type: ignore[assignment]
    market_feed_urls: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        raw = os.getenv("MARKET_FEED_URLS_JSON", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        object.__setattr__(self, "market_feed_urls", {str(k): str(v) for k, v in parsed.items() if v})
        raw_event = os.getenv("EVENT_SOURCE_URLS_JSON", "{}")
        try:
            parsed_event = json.loads(raw_event)
        except json.JSONDecodeError:
            parsed_event = {}
        if not isinstance(parsed_event, dict):
            parsed_event = {}
        object.__setattr__(self, "event_source_urls", {str(k): str(v) for k, v in parsed_event.items() if v})


settings = Settings()
