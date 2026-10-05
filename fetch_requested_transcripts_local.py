#!/usr/bin/env python3
"""Fetch transcripts locally for Notion rows with Lesson Request checked.

Designed for a learner-run Windows workflow:
1. Check Lesson Request in Notion.
2. Run this script locally (normally via EasyGermanLesson.bat).
3. Transcripts are extracted from the user's normal home connection.
4. Transcript files are committed and pushed to GitHub.
5. GitHub Actions generates lessons from those transcript files.

No OpenAI API call is made by this script.
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


REPO_ROOT = Path(__file__).resolve().parent
TRANSCRIPT_DIR = REPO_ROOT / "data" / "requested_lessons" / "transcripts"


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


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("\n$", " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        check=check,
        capture_output=capture,
        encoding="utf-8",
        errors="replace",
    )


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


def set_status(notion: Client, page_id: str, *, lesson_status: str | None = None, transcript: str | None = None) -> None:
    props: dict[str, Any] = {}
    if lesson_status:
        props["Lesson Status"] = {"select": {"name": lesson_status}}
    if transcript:
        props["Transcript"] = {"select": {"name": transcript}}
    if not props:
        return
    retry(lambda: notion.pages.update(page_id=page_id, properties=props), "update Notion status")


def extract_transcript(video_url: str, output: Path, browser: str) -> None:
    """Use local yt-dlp. Try public access first, then browser cookies."""
    output.parent.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output.parent / "%(id)s.%(ext)s")

    common = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--write-auto-sub",
        "--write-sub",
        "--sub-langs",
        "de,de-DE",
        "--sub-format",
        "vtt",
        "--no-playlist",
        "--js-runtimes",
        "node",
        "--remote-components",
        "ejs:github",
        "-o",
        outtmpl,
    ]

    attempts = [common + [video_url]]
    if browser:
        attempts.append(common + ["--cookies-from-browser", browser, video_url])

    errors: list[str] = []
    for index, cmd in enumerate(attempts, start=1):
        proc = run(cmd, check=False, capture=True)
        if proc.returncode == 0:
            vtts = sorted(output.parent.glob("*.vtt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if vtts:
                vtt = vtts[0]
                clean = vtt_to_text(vtt.read_text(encoding="utf-8", errors="replace"))
                if clean.strip():
                    output.write_text(clean, encoding="utf-8")
                    for candidate in output.parent.glob("*.vtt"):
                        candidate.unlink(missing_ok=True)
                    print(f"[ok] transcript saved -> {output.relative_to(REPO_ROOT)}")
                    return
        errors.append((proc.stdout + "\n" + proc.stderr)[-2500:])
        print(f"[warn] local transcript attempt {index} failed")

    raise RuntimeError("Local transcript extraction failed.\n\n" + "\n---\n".join(errors))


def vtt_to_text(vtt: str) -> str:
    import html
    import re

    lines: list[str] = []
    previous = ""
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines)


def git_push_transcripts(paths: list[Path]) -> None:
    if not paths:
        return

    rel_paths = [str(p.relative_to(REPO_ROOT)) for p in paths]
    run(["git", "add", "--", *rel_paths])

    diff = run(["git", "diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        print("[info] No new transcript changes to commit.")
        return

    names = ", ".join(p.stem for p in paths[:3])
    if len(paths) > 3:
        names += f" +{len(paths) - 3} more"
    run(["git", "commit", "-m", f"Add requested Easy German transcripts: {names}"])
    run(["git", "push"])
    print("[ok] transcripts pushed. GitHub will generate the requested lesson(s).")


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    token = os.getenv("NOTION_TOKEN")
    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID", "6878c89b-220b-4dc4-96a1-ae021d37a2b3")
    browser = os.getenv("YOUTUBE_BROWSER", "chrome").strip()

    if not token:
        raise SystemExit(
            "NOTION_TOKEN is missing from .env. Copy .env.example to .env and add your Notion integration token."
        )

    notion = Client(auth=token)
    pages = query_queue(notion, data_source_id)
    if not pages:
        print("[info] Lesson Queue is empty. Check Lesson Request in Notion first.")
        return

    print(f"[info] {len(pages)} requested lesson(s) found.")
    saved: list[Path] = []
    failures = 0

    for page in pages:
        page_id = page["id"]
        props = page["properties"]
        title = title_text(props.get("Video", {})) or "Easy German lesson"
        video_id = rich_text(props.get("Video ID", {}))
        video_url = (props.get("Video URL", {}) or {}).get("url")
        level = select_name(props.get("Level", {})) or "A2"
        order = int((props.get("Playlist Order", {}) or {}).get("number") or 0)

        print(f"\n=== {level} #{order:03d} | {title} ===")
        if not video_url:
            print("[error] Video URL is missing in Notion.")
            failures += 1
            continue

        stem = f"{level.lower()}_{order:03d}_{video_id or 'unknown'}"
        path = TRANSCRIPT_DIR / f"{stem}.txt"

        if path.exists() and path.stat().st_size > 50:
            print(f"[skip] transcript already exists -> {path.relative_to(REPO_ROOT)}")
            saved.append(path)
            set_status(notion, page_id, lesson_status="Requested", transcript="Ready")
            continue

        try:
            set_status(notion, page_id, lesson_status="Requested")
            extract_transcript(video_url, path, browser)
            set_status(notion, page_id, lesson_status="Requested", transcript="Ready")
            saved.append(path)
        except Exception as exc:
            failures += 1
            print(f"[error] {title}: {exc}")

    if saved:
        git_push_transcripts(saved)

    print(f"\nDone. transcripts_ready={len(saved)}, failed={failures}")
    if failures:
        raise SystemExit(f"{failures} transcript(s) could not be extracted locally.")


if __name__ == "__main__":
    main()
