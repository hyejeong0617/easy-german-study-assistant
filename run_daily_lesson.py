#!/usr/bin/env python3
"""
Daily pipeline for a given study date.

Flow:
1) query Notion rows for Study Date
2) extract transcript per video
3) generate AI lesson JSON
4) append lesson to the Notion page
5) update Transcript / Lesson properties

The process exits non-zero when any scheduled lesson fails, so GitHub Actions
correctly shows a red failure instead of a false green success.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from notion_client import Client


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run(args, check=True)


def get_plain_title(prop: dict[str, Any]) -> str:
    title_items = prop.get("title", [])
    return "".join(
        [t.get("plain_text", "") for t in title_items]
    ).strip()


def get_rich_text(prop: dict[str, Any]) -> str:
    items = prop.get("rich_text", [])
    return "".join(
        [t.get("plain_text", "") for t in items]
    ).strip()


def get_url(prop: dict[str, Any]) -> str | None:
    return prop.get("url")


def get_number(prop: dict[str, Any]) -> int | None:
    value = prop.get("number")
    if value is None:
        return None
    return int(value)


def query_study_rows(
    notion: Client,
    data_source_id: str,
    study_date: str,
) -> list[dict[str, Any]]:
    response = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "property": "Study Date",
            "date": {"equals": study_date},
        },
        page_size=20,
    )

    results = response.get("results", [])
    results.sort(
        key=lambda p: int(
            p["properties"]
            .get("Playlist Order", {})
            .get("number")
            or 9999
        )
    )
    return results


def append_error_note(
    notion: Client,
    page_id: str,
    reason: str,
) -> None:
    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    f"[자동화 실패] {reason}"
                                )[:1900]
                            },
                        }
                    ]
                },
            }
        ],
    )


def mark_failed(
    notion: Client,
    page_id: str,
    reason: str,
) -> None:
    notion.pages.update(
        page_id=page_id,
        properties={
            "Transcript": {
                "select": {"name": "Failed"}
            },
            "Lesson": {
                "select": {"name": "Pending"}
            },
        },
    )
    append_error_note(notion, page_id, reason)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--study-date",
        default=date.today().isoformat(),
    )
    parser.add_argument("--level", default="A2")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--data-source-id",
        default=os.getenv("NOTION_DATA_SOURCE_ID"),
    )
    parser.add_argument(
        "--cookies-file",
        default=os.getenv("YOUTUBE_COOKIES_FILE"),
    )
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    data_source_id = args.data_source_id

    if not token:
        raise SystemExit("NOTION_TOKEN is missing.")
    if not data_source_id:
        raise SystemExit("NOTION_DATA_SOURCE_ID is missing.")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing.")

    notion = Client(auth=token)
    pages = query_study_rows(
        notion,
        data_source_id,
        args.study_date,
    )

    if not pages:
        print(
            f"[info] No study rows found for "
            f"{args.study_date}"
        )
        return

    base = Path("data") / args.study_date
    tdir = base / "transcripts"
    ldir = base / "lessons"
    tdir.mkdir(parents=True, exist_ok=True)
    ldir.mkdir(parents=True, exist_ok=True)

    processed = 0
    failures = 0

    for page in pages[: args.limit]:
        page_id = page["id"]
        props = page["properties"]

        title = (
            get_plain_title(props["Video"])
            or "Easy German lesson"
        )
        video_id = get_rich_text(
            props.get("Video ID", {})
        )
        video_url = get_url(
            props.get("Video URL", {})
        )
        order = (
            get_number(
                props.get("Playlist Order", {})
            )
            or 0
        )
        level = (
            props.get("Level", {})
            .get("select", {})
            .get("name")
            or args.level
        )
        lesson_status = (
            props.get("Lesson", {})
            .get("select", {})
            .get("name")
        )

        safe_stem = (
            f"{level.lower()}_"
            f"{order:02d}_"
            f"{video_id or 'unknown'}"
        )
        transcript_path = (
            tdir / f"{safe_stem}.txt"
        )
        lesson_path = (
            ldir / f"{safe_stem}.json"
        )

        print(
            f"\n=== {level} #{order:02d} "
            f"| {title} ==="
        )

        if lesson_status == "Generated":
            print(
                "[skip] Lesson already generated."
            )
            continue

        if not video_id and not video_url:
            mark_failed(
                notion,
                page_id,
                "Video ID / URL missing",
            )
            failures += 1
            continue

        try:
            extract_cmd = [
                sys.executable,
                "02_extract_transcript.py",
                "--output",
                str(transcript_path),
            ]

            if video_id:
                extract_cmd.extend(
                    ["--video-id", video_id]
                )

            if video_url:
                extract_cmd.extend(
                    ["--video-url", video_url]
                )

            if (
                args.cookies_file
                and Path(args.cookies_file).exists()
            ):
                extract_cmd.extend(
                    [
                        "--cookies-file",
                        args.cookies_file,
                    ]
                )

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
                "--transcript-status",
                "Ready",
                "--lesson-status",
                "Generated",
            )

            processed += 1

        except subprocess.CalledProcessError as exc:
            failures += 1
            reason = (
                f"pipeline failed for {title}: "
                f"{exc}"
            )
            print(f"[error] {reason}")

            try:
                mark_failed(
                    notion,
                    page_id,
                    reason,
                )
            except Exception as second_exc:
                print(
                    "[warn] could not mark failure "
                    f"in Notion: {second_exc}"
                )

    print(
        f"\nDone. processed={processed}, "
        f"failures={failures}"
    )

    if failures > 0:
        raise SystemExit(
            f"{failures} scheduled lesson(s) failed."
        )


if __name__ == "__main__":
    main()
