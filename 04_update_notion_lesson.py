#!/usr/bin/env python3
"""
Append generated lesson content to a Notion page and update page properties.

This script appends blocks to the page.
It does not delete existing template content.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from notion_client import Client


def rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[:2000]}}]


def paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text(text)},
    }


def heading_2(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": rich_text(text)},
    }


def heading_3(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": rich_text(text)},
    }


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
        heading_2("AI Lesson Pack"),
        heading_3("오늘 영상 핵심"),
    ]

    for sent in lesson.get("video_summary", {}).get("korean_summary", []):
        blocks.append(bulleted(sent))

    blocks.append(heading_3("핵심 단어"))
    for item in lesson.get("key_vocabulary", []):
        text = (
            f"{item.get('word', '')} — {item.get('meaning_ko', '')}\n"
            f"영상 예문: {item.get('example_from_video', '')}\n"
            f"쉬운 예문: {item.get('simple_example', '')}"
        )
        blocks.append(bulleted(text[:1900]))

    blocks.append(heading_3("주요 표현"))
    for item in lesson.get("key_expressions", []):
        text = (
            f"{item.get('expression', '')} — {item.get('meaning_ko', '')}\n"
            f"언제 쓰나: {item.get('when_to_use', '')}\n"
            f"예문: {item.get('example', '')}"
        )
        blocks.append(bulleted(text[:1900]))

    blocks.append(heading_3("문법"))
    for item in lesson.get("grammar_points", []):
        blocks.append(paragraph(f"{item.get('topic', '')}"))
        blocks.append(paragraph(f"설명: {item.get('explanation_ko', '')}"))
        for ex in item.get("examples", []):
            blocks.append(bulleted(ex))

    blocks.append(heading_3("Listening Point"))
    for item in lesson.get("listening_points", []):
        text = (
            f"{item.get('expression', '')}\n"
            f"왜 어렵나: {item.get('why_it_is_hard', '')}\n"
            f"팁: {item.get('tip', '')}"
        )
        blocks.append(bulleted(text[:1900]))

    blocks.append(heading_3("Speaking Practice"))
    for q in lesson.get("speaking_practice", []):
        blocks.append(bulleted(q))

    core = lesson.get("todays_core", {})
    blocks.append(heading_3("Today’s Core"))
    blocks.append(paragraph("단어"))
    for w in core.get("words", []):
        blocks.append(bulleted(w))
    blocks.append(paragraph("표현"))
    for e in core.get("expressions", []):
        blocks.append(bulleted(e))
    if core.get("grammar"):
        blocks.append(paragraph(f"문법: {core.get('grammar')}"))

    return blocks


def chunked(items: list[dict[str, Any]], size: int = 100):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--lesson-json", required=True)
    parser.add_argument("--transcript-status", default="Ready")
    parser.add_argument("--lesson-status", default="Generated")
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing.")

    lesson = json.loads(Path(args.lesson_json).read_text(encoding="utf-8"))
    notion = Client(auth=token)

    # Update properties first
    notion.pages.update(
        page_id=args.page_id,
        properties={
            "Transcript": {"select": {"name": args.transcript_status}},
            "Lesson": {"select": {"name": args.lesson_status}},
        },
    )

    blocks = build_blocks(lesson)
    for batch in chunked(blocks, 100):
        notion.blocks.children.append(
            block_id=args.page_id,
            children=batch,
        )

    print(f"[ok] Notion page updated -> {args.page_id}")


if __name__ == "__main__":
    main()
