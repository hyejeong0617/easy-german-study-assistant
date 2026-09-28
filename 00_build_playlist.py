#!/usr/bin/env python3
"""
Read Easy German playlist metadata with yt-dlp.

MVP goal:
- read playlist order
- collect first N videos
- resolve title / video id / URL / duration
- save to data/a2_playlist.json

No YouTube Data API key is required.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_yt_dlp(args: list[str]) -> str:
    cmd = ["yt-dlp", *args]
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "yt-dlp failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr:\n{proc.stderr[-4000:]}"
        )
    return proc.stdout


def get_flat_playlist(playlist_url: str) -> list[dict[str, Any]]:
    raw = run_yt_dlp([
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        playlist_url,
    ])
    data = json.loads(raw)
    return data.get("entries") or []


def get_video_details(video_id: str) -> dict[str, Any]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    raw = run_yt_dlp([
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        "--no-warnings",
        url,
    ])
    return json.loads(raw)


def build_playlist(playlist_url: str, level: str, limit: int) -> list[dict[str, Any]]:
    entries = get_flat_playlist(playlist_url)
    selected = entries[:limit]

    result: list[dict[str, Any]] = []

    for order, entry in enumerate(selected, start=1):
        video_id = entry.get("id")
        if not video_id:
            print(f"[skip] #{order}: missing video id", file=sys.stderr)
            continue

        title = entry.get("title")
        duration = entry.get("duration")

        # Flat playlist metadata sometimes omits duration.
        # Resolve the individual video only when necessary.
        if not title or duration is None:
            try:
                details = get_video_details(video_id)
                title = title or details.get("title")
                duration = duration if duration is not None else details.get("duration")
            except Exception as exc:
                print(
                    f"[warn] detailed metadata failed for #{order} {video_id}: {exc}",
                    file=sys.stderr,
                )

        result.append({
            "level": level,
            "playlist_order": order,
            "video_id": video_id,
            "title": title or f"{level} #{order:02d}",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration_seconds": duration,
            "duration_minutes": round(duration / 60, 1) if duration else None,
        })

        print(
            f"[ok] #{order:02d} | {video_id} | "
            f"{result[-1]['duration_minutes']} min | {result[-1]['title']}"
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist-url", required=True)
    parser.add_argument("--level", default="A2")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--output", default="data/a2_playlist.json")
    args = parser.parse_args()

    rows = build_playlist(args.playlist_url, args.level, args.limit)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {len(rows)} videos -> {out}")


if __name__ == "__main__":
    main()
