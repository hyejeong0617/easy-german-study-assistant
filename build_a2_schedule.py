#!/usr/bin/env python3
"""Build the full Easy German A2 sprint schedule and sync it to Notion."""

from __future__ import annotations

import os
import subprocess
import sys


A2_PLAYLIST_URL = os.getenv(
    "A2_PLAYLIST_URL",
    "https://www.youtube.com/playlist?list=PLk1fjOl39-5201BUdhtOM_x23poNvLouT",
)
START_DATE = os.getenv("A2_SPRINT_START", "2026-10-05")
END_DATE = os.getenv("A2_SPRINT_END", "2026-12-10")


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run(args, check=True)


def main() -> None:
    run(
        sys.executable,
        "00_build_playlist.py",
        "--playlist-url",
        A2_PLAYLIST_URL,
        "--level",
        "A2",
        "--output",
        "data/a2_playlist.json",
    )

    run(
        sys.executable,
        "01_sync_notion.py",
        "--input",
        "data/a2_playlist.json",
        "--start-date",
        START_DATE,
        "--end-date",
        END_DATE,
    )


if __name__ == "__main__":
    main()
