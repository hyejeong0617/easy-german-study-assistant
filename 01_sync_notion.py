#!/usr/bin/env python3
"""
Sync playlist metadata into the existing Notion Easy German Study database.

Matching key:
    Level + Playlist Order

This updates only metadata:
- Video title
- Video ID
- Video URL
- Duration (min)

It does NOT overwrite Study Date, Status, Difficulty, or lesson content.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from notion_client import Client


def title_value(text: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def rich_text_value(text: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def find_existing_page(
    notion: Client,
    data_source_id: str,
    level: str,
    playlist_order: int,
) -> dict[str, Any] | None:
    response = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "and": [
                {
                    "property": "Level",
                    "select": {"equals": level},
                },
                {
                    "property": "Playlist Order",
                    "number": {"equals": playlist_order},
                },
            ]
        },
        page_size=5,
    )
    results = response.get("results", [])
    return results[0] if results else None


def update_page(
    notion: Client,
    page_id: str,
    row: dict[str, Any],
) -> None:
    properties: dict[str, Any] = {
        "Video": title_value(row["title"]),
        "Video ID": rich_text_value(row["video_id"]),
        "Video URL": {"url": row["url"]},
    }

    if row.get("duration_minutes") is not None:
        properties["Duration (min)"] = {
            "number": float(row["duration_minutes"])
        }

    notion.pages.update(
        page_id=page_id,
        properties=properties,
    )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/a2_playlist.json")
    parser.add_argument(
        "--data-source-id",
        default=os.getenv("NOTION_DATA_SOURCE_ID"),
    )
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    data_source_id = args.data_source_id

    if not token:
        raise SystemExit(
            "NOTION_TOKEN is missing. Put it in .env locally "
            "or GitHub Actions Secrets."
        )

    if not data_source_id:
        raise SystemExit(
            "NOTION_DATA_SOURCE_ID is missing."
        )

    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    notion = Client(auth=token)

    updated = 0
    missing = 0

    for row in rows:
        page = find_existing_page(
            notion,
            data_source_id,
            row["level"],
            int(row["playlist_order"]),
        )

        if not page:
            print(
                f"[missing] {row['level']} #{row['playlist_order']:02d} "
                "- create this Notion row first."
            )
            missing += 1
            continue

        update_page(notion, page["id"], row)
        print(
            f"[updated] {row['level']} #{row['playlist_order']:02d} "
            f"-> {row['title']}"
        )
        updated += 1

    print(f"\nDone. updated={updated}, missing={missing}")


if __name__ == "__main__":
    main()
