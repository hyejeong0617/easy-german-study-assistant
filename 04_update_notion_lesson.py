#!/usr/bin/env python3
"""Append an A2 Fast Track lesson to a Notion video page."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from notion_client import Client


def rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[:2000]}}]


def paragraph(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text(text)}}


def heading_2(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": rich_text(text)}}


def heading_3(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": rich_text(text)}}


def bulleted(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text(text)},
    }


def divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def build_blocks(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        divider(),
        heading_2("AI Lesson — A2 Fast Track"),
        heading_3("1. Video in 3 Lines"),
    ]

    for sent in lesson.get("video_summary", {}).get("korean_summary", []):
        blocks.append(bulleted(sent))

    blocks.append(heading_3("2. Must-Know Expressions"))
    for item in lesson.get("key_expressions", []):
        blocks.append(bulleted(
            (
                f"{item.get('expression', '')} — {item.get('meaning_ko', '')}\n"
                f"영상: {item.get('example_from_video', '')}\n"
                f"사용: {item.get('use_note_ko', '')}"
            )[:1900]
        ))

    blocks.append(heading_3("3. Vocabulary"))
    for item in lesson.get("key_vocabulary", []):
        blocks.append(bulleted(
            (
                f"{item.get('word', '')} — {item.get('meaning_ko', '')}\n"
                f"영상: {item.get('example_from_video', '')}"
            )[:1900]
        ))

    grammar = lesson.get("grammar_point")
    if grammar:
        blocks.append(heading_3("4. One Grammar Point"))
        blocks.append(paragraph(f"{grammar.get('topic', '')}"))
        blocks.append(paragraph(f"설명: {grammar.get('explanation_ko', '')}"))
        blocks.append(bulleted(f"영상 예문: {grammar.get('example_from_video', '')}"))

    blocks.append(heading_3("5. Listen Again"))
    for item in lesson.get("listen_again", []):
        blocks.append(bulleted(
            f"{item.get('sentence', '')}\n포인트: {item.get('focus_ko', '')}"[:1900]
        ))

    blocks.append(heading_3("6. Say It Yourself"))
    for prompt in lesson.get("speaking_practice", []):
        blocks.append(bulleted(prompt))

    return blocks


def chunked(items: list[dict[str, Any]], size: int = 100):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--lesson-json", required=True)
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing.")

    lesson = json.loads(Path(args.lesson_json).read_text(encoding="utf-8"))
    notion = Client(auth=token)
    now = datetime.now(timezone.utc).isoformat()

    # Keep legacy fields in sync while the new semi-automatic fields become primary.
    notion.pages.update(
        page_id=args.page_id,
        properties={
            "Transcript": {"select": {"name": "Ready"}},
            "Lesson": {"select": {"name": "Generated"}},
            "Lesson Status": {"select": {"name": "Generated"}},
            "Lesson Request": {"checkbox": False},
            "Lesson Generated At": {"date": {"start": now}},
        },
    )

    blocks = build_blocks(lesson)
    for batch in chunked(blocks):
        notion.blocks.children.append(block_id=args.page_id, children=batch)

    print(f"[ok] Notion lesson updated -> {args.page_id}")


if __name__ == "__main__":
    main()
