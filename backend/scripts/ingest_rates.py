from __future__ import annotations

from backend.app.ingest import run_full_ingest


def main() -> None:
    result = run_full_ingest()
    print(
        "Ingestion complete. "
        f"fred_rows={result['fred_rows']}, "
        f"central_bank_rows={result['central_bank_rows']}, "
        f"pboc_rows={result['pboc_rows']}, "
        f"spread_rows={result['spread_rows']}, "
        f"total={result['total']}"
    )


if __name__ == "__main__":
    main()
