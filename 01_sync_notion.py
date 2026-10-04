#!/usr/bin/env python3
"""Upsert the full A2 playlist into Notion and assign weekday study dates.

Default sprint:
- start: 2026-10-05
- end:   2026-12-10
- weekdays only (Mon-Fri)

Videos are distributed as evenly as possible by count. Existing pages are
updated in place, so generated lessons and user progress are preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from notion_client import Client


def retry(call: Callable[[], Any], label: str, attempts: int = 4) -> Any:
    delay = 1.5
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            last_exc = exc
            if attempt == attempts:
                break
            print(f"[retry] {label} failed ({attempt}/{attempts}): {exc}")
            time.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc


def weekday_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def assign_schedule(rows: list[dict[str, Any]], days: list[date]) -> None:
    if not days:
        raise ValueError("No weekdays available in the requested date range.")
    if not rows:
        raise ValueError("Playlist is empty.")

    base, remainder = divmod(len(rows), len(days))
    index = 0
    for day_index, study_day in enumerate(days):
        count = base + (1 if day_index < remainder else 0)
        for _ in range(count):
            if index >= len(rows):
                return
            rows[index]["study_date"] = study_day.isoformat()
            index += 1


def rich_text_value(text: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def title_value(text: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def select_name(prop: dict[str, Any]) -> str | None:
    item = prop.get("select") or {}
    return item.get("name")


def checkbox_value(prop: dict[str, Any]) -> bool:
    return bool(prop.get("checkbox"))


def find_existing_page(
    notion: Client,
    data_source_id: str,
    level: str,
    playlist_order: int,
) -> dict[str, Any] | None:
    def _query():
        return notion.data_sources.query(
            data_source_id=data_source_id,
            filter={
                "and": [
                    {"property": "Level", "select": {"equals": level}},
                    {"property": "Playlist Order", "number": {"equals": playlist_order}},
                ]
            },
            page_size=5,
        )

    response = retry(_query, f"find {level} #{playlist_order}")
    results = response.get("results", [])
    return results[0] if results else None


def page_properties(row: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {
        "Video": title_value(row["title"]),
        "Level": {"select": {"name": row["level"]}},
        "Playlist Order": {"number": int(row["playlist_order"])},
        "Video ID": rich_text_value(row["video_id"]),
        "Video URL": {"url": row["url"]},
        "Study Date": {"date": {"start": row["study_date"]}},
    }
    if row.get("duration_minutes") is not None:
        props["Duration (min)"] = {"number": float(row["duration_minutes"])}
    return props


def update_existing(
    notion: Client,
    page: dict[str, Any],
    row: dict[str, Any],
) -> None:
    props = page_properties(row)
    existing = page.get("properties", {})

    # Initialize new semi-automatic fields only when they are still empty.
    if not select_name(existing.get("Study Status", {})):
        props["Study Status"] = {"select": {"name": "To Watch"}}

    if not select_name(existing.get("Lesson Status", {})):
        legacy_lesson = select_name(existing.get("Lesson", {}))
        new_status = "Generated" if legacy_lesson == "Generated" else "Not Requested"
        props["Lesson Status"] = {"select": {"name": new_status}}

    retry(
        lambda: notion.pages.update(page_id=page["id"], properties=props),
        f"update {row['level']} #{row['playlist_order']}",
    )


def create_new(notion: Client, data_source_id: str, row: dict[str, Any]) -> None:
    props = page_properties(row)
    props.update({
        "Study Status": {"select": {"name": "To Watch"}},
        "Lesson Request": {"checkbox": False},
        "Lesson Status": {"select": {"name": "Not Requested"}},
    })

    retry(
        lambda: notion.pages.create(
            parent={"type": "data_source_id", "data_source_id": data_source_id},
            properties=props,
        ),
        f"create {row['level']} #{row['playlist_order']}",
    )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/a2_playlist.json")
    parser.add_argument("--start-date", default="2026-10-05")
    parser.add_argument("--end-date", default="2026-12-10")
    parser.add_argument("--data-source-id", default=os.getenv("NOTION_DATA_SOURCE_ID"))
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing.")
    if not args.data_source_id:
        raise SystemExit("NOTION_DATA_SOURCE_ID is missing.")

    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    days = weekday_dates(start, end)
    assign_schedule(rows, days)

    notion = Client(auth=token)
    created = 0
    updated = 0

    for row in rows:
        page = find_existing_page(
            notion,
            args.data_source_id,
            row["level"],
            int(row["playlist_order"]),
        )
        if page:
            update_existing(notion, page, row)
            updated += 1
            action = "updated"
        else:
            create_new(notion, args.data_source_id, row)
            created += 1
            action = "created"

        print(
            f"[{action}] {row['level']} #{row['playlist_order']:03d} "
            f"-> {row['study_date']} | {row['title']}"
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["study_date"]] = counts.get(row["study_date"], 0) + 1

    print("\n=== Sprint summary ===")
    print(f"videos: {len(rows)}")
    print(f"weekdays: {len(days)}")
    print(f"created: {created}, updated: {updated}")
    print(f"daily video count: min={min(counts.values())}, max={max(counts.values())}")
    print(f"first date: {min(counts)}, last date: {max(counts)}")


if __name__ == "__main__":
    main()
