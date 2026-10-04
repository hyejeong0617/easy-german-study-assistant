#!/usr/bin/env python3
"""Fetch the full Easy German playlist with as few YouTube requests as possible.

For playlist metadata we first try WITHOUT cookies because stale YouTube account
cookies can make an otherwise public playlist request fail. If that fails and
YOUTUBE_COOKIES_FILE exists, we retry once with cookies.

The sprint scheduler only needs playlist order, title, video ID and URL.
Duration is kept when yt-dlp exposes it in flat-playlist metadata; we do not
make one extra request per video just to resolve missing durations.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def run_yt_dlp(args: list[str], use_cookies: bool = False) -> str:
    cmd = [
        "yt-dlp",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        *args,
    ]

    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
    if use_cookies and cookies_file and Path(cookies_file).exists():
        cmd.extend(["--cookies", cookies_file])

    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-4000:] or proc.stdout[-4000:])
    return proc.stdout


def get_flat_playlist(playlist_url: str) -> list[dict[str, Any]]:
    args = [
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        playlist_url,
    ]

    try:
        raw = run_yt_dlp(args, use_cookies=False)
        print("[ok] playlist metadata fetched without cookies")
    except Exception as first_exc:
        cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
        if not cookies_file or not Path(cookies_file).exists():
            raise RuntimeError(
                "Public playlist fetch failed and no cookie fallback is available.\n"
                f"{first_exc}"
            ) from first_exc

        print("[warn] public playlist fetch failed; retrying with cookies")
        raw = run_yt_dlp(args, use_cookies=True)

    data = json.loads(raw)
    return [entry for entry in (data.get("entries") or []) if entry]


def build_playlist(
    playlist_url: str,
    level: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    entries = get_flat_playlist(playlist_url)
    if limit:
        entries = entries[:limit]

    result: list[dict[str, Any]] = []
    for order, entry in enumerate(entries, start=1):
        video_id = entry.get("id")
        if not video_id:
            continue

        duration = entry.get("duration")
        row = {
            "level": level,
            "playlist_order": order,
            "video_id": video_id,
            "title": entry.get("title") or f"{level} #{order:03d}",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration_seconds": duration,
            "duration_minutes": round(float(duration) / 60, 1) if duration else None,
        }
        result.append(row)
        print(
            f"[ok] #{order:03d} | {video_id} | "
            f"{row['duration_minutes'] or '?'} min | {row['title']}"
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist-url", required=True)
    parser.add_argument("--level", default="A2")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional test limit. Omit to fetch the full playlist.",
    )
    parser.add_argument("--output", default="data/a2_playlist.json")
    args = parser.parse_args()

    rows = build_playlist(args.playlist_url, args.level, args.limit)
    if not rows:
        raise SystemExit("No playlist entries were returned.")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {len(rows)} videos -> {out}")


if __name__ == "__main__":
    main()
