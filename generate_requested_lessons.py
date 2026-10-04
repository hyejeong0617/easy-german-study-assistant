#!/usr/bin/env python3
"""Generate lessons only for Notion rows explicitly requested by the learner.

Queue rule:
- Lesson Request = checked
- Lesson Status != Generated

The script never generates lessons just because a Study Date has arrived.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
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


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run(args, check=True)


def title_text(prop: dict[str, Any]) -> str:
    return "".join(x.get("plain_text", "") for x in prop.get("title", [])).strip()


def rich_text(prop: dict[str, Any]) -> str:
    return "".join(x.get("plain_text", "") for x in prop.get("rich_text", [])).strip()


def select_name(prop: dict[str, Any]) -> str | None:
    return (prop.get("select") or {}).get("name")


def query_queue(notion: Client, data_source_id: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        def _query():
            kwargs: dict[str, Any] = {
                "data_source_id": data_source_id,
                "filter": {
                    "and": [
                        {"property": "Lesson Request", "checkbox": {"equals": True}},
                        {"property": "Lesson Status", "select": {"does_not_equal": "Generated"}},
                    ]
                },
                "sorts": [
                    {"property": "Study Date", "direction": "ascending"},
                    {"property": "Playlist Order", "direction": "ascending"},
                ],
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor
            return notion.data_sources.query(**kwargs)

        response = retry(_query, "query lesson queue")
        pages.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return pages


def set_status(notion: Client, page_id: str, status: str, transcript: str | None = None) -> None:
    props: dict[str, Any] = {"Lesson Status": {"select": {"name": status}}}
    if transcript:
        props["Transcript"] = {"select": {"name": transcript}}
    retry(
        lambda: notion.pages.update(page_id=page_id, properties=props),
        f"set status {status}",
    )


def main() -> None:
    load_dotenv()

    token = os.getenv("NOTION_TOKEN")
    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing.")
    if not data_source_id:
        raise SystemExit("NOTION_DATA_SOURCE_ID is missing.")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing.")

    notion = Client(auth=token)
    pages = query_queue(notion, data_source_id)
    if not pages:
        print("[info] Lesson Queue is empty. Nothing to generate.")
        return

    print(f"[info] {len(pages)} requested lesson(s) found.")
    base = Path("data/requested_lessons")
    tdir = base / "transcripts"
    ldir = base / "lessons"
    tdir.mkdir(parents=True, exist_ok=True)
    ldir.mkdir(parents=True, exist_ok=True)

    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
    succeeded = 0
    failed = 0

    for page in pages:
        page_id = page["id"]
        props = page["properties"]
        title = title_text(props.get("Video", {})) or "Easy German lesson"
        video_id = rich_text(props.get("Video ID", {}))
        video_url = props.get("Video URL", {}).get("url")
        level = select_name(props.get("Level", {})) or "A2"
        order = int(props.get("Playlist Order", {}).get("number") or 0)
        stem = f"{level.lower()}_{order:03d}_{video_id or 'unknown'}"
        transcript_path = tdir / f"{stem}.txt"
        lesson_path = ldir / f"{stem}.json"

        print(f"\n=== {level} #{order:03d} | {title} ===")
        set_status(notion, page_id, "Requested")

        try:
            extract_cmd = [
                sys.executable,
                "02_extract_transcript.py",
                "--output",
                str(transcript_path),
            ]
            if video_id:
                extract_cmd.extend(["--video-id", video_id])
            if video_url:
                extract_cmd.extend(["--video-url", video_url])
            if cookies_file and Path(cookies_file).exists():
                extract_cmd.extend(["--cookies-file", cookies_file])

            run(*extract_cmd)
            run(
                sys.executable,
                "03_generate_lesson.py",
                "--transcript",
                str(transcript_path),
                "--output",
                str(lesson_path),
                "--level",
                level,
                "--title",
                title,
            )
            run(
                sys.executable,
                "04_update_notion_lesson.py",
                "--page-id",
                page_id,
                "--lesson-json",
                str(lesson_path),
            )
            succeeded += 1
        except Exception as exc:
            failed += 1
            print(f"[error] {title}: {exc}")
            try:
                set_status(notion, page_id, "Failed", transcript="Failed")
            except Exception as status_exc:
                print(f"[warn] could not update failure status: {status_exc}")

    print(f"\nDone. generated={succeeded}, failed={failed}")
    if failed:
        raise SystemExit(f"{failed} requested lesson(s) failed.")


if __name__ == "__main__":
    main()
