from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests
from dateutil import parser as date_parser

from backend.app.config import settings
from backend.app.http_utils import DEFAULT_HEADERS


@dataclass(frozen=True)
class EventRow:
    event_date: date
    event_type: str
    country: str
    title: str
    importance: str

    @property
    def key(self) -> tuple:
        return (self.event_date, self.event_type, self.country, self.title)


def _parse_rows(text: str) -> list[EventRow]:
    rows: list[EventRow] = []
    if not text.strip():
        return rows
    reader = csv.DictReader(text.splitlines())
    required = {"date", "type", "country", "title", "importance"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        return rows
    for r in reader:
        try:
            d = date_parser.parse((r.get("date") or "").strip()).date()
        except (ValueError, TypeError):
            continue
        event_type = (r.get("type") or "").strip().upper()
        country = (r.get("country") or "").strip().upper()
        title = (r.get("title") or "").strip()
        importance = (r.get("importance") or "").strip().lower() or "medium"
        if not event_type or not title:
            continue
        rows.append(EventRow(d, event_type, country, title, importance))
    return rows


def _load_local(path: Path) -> list[EventRow]:
    if not path.exists():
        return []
    return _parse_rows(path.read_text(encoding="utf-8"))


def _load_remote(url: str) -> list[EventRow]:
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)
    resp = sess.get(url, timeout=20)
    resp.raise_for_status()
    return _parse_rows(resp.text)


def main() -> None:
    out_path = Path("desktop_terminal/feeds/events_calendar.csv")
    merged: dict[tuple, EventRow] = {}

    for row in _load_local(out_path):
        merged[row.key] = row

    source_urls = settings.event_source_urls or {}
    for source_name, url in source_urls.items():
        try:
            rows = _load_remote(url)
        except Exception as exc:
            print(f"[warn] failed source {source_name}: {exc}")
            continue
        for row in rows:
            merged[row.key] = row

    final_rows = sorted(merged.values(), key=lambda x: x.event_date)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "type", "country", "title", "importance"])
        for row in final_rows:
            writer.writerow(
                [
                    row.event_date.isoformat(),
                    row.event_type,
                    row.country,
                    row.title,
                    row.importance,
                ]
            )
    print(f"calendar updated: {out_path} rows={len(final_rows)}")


if __name__ == "__main__":
    main()

