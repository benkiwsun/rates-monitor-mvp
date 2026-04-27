#!/usr/bin/env python3
"""Container entrypoint: init DB, optional first ingest, then uvicorn (or one-off migrate)."""
from __future__ import annotations

import os
import subprocess
import sys
import time


def _wait_pg(url: str, attempts: int = 30, delay_s: float = 2.0) -> None:
    try:
        import psycopg
    except ImportError:
        return
    for i in range(attempts):
        try:
            conn = psycopg.connect(url, connect_timeout=5)
            conn.close()
            return
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(delay_s)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "web"
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        _wait_pg(db_url)

    subprocess.run([sys.executable, "-m", "backend.scripts.init_db"], check=True)
    if os.environ.get("SKIP_FIRST_INGEST", "").lower() not in ("1", "true", "yes"):
        subprocess.run([sys.executable, "-m", "backend.scripts.ingest_rates"], check=False)

    if mode == "migrate":
        sys.exit(0)

    port = os.environ.get("PORT", "8000")
    sys.exit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ]
        )
    )


if __name__ == "__main__":
    main()
