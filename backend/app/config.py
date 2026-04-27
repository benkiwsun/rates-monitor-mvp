from __future__ import annotations

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


settings = Settings()
