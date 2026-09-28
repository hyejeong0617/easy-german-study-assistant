#!/usr/bin/env python3
"""
One-command MVP metadata sync:
1) fetch first 6 A2 playlist videos
2) update existing Notion rows A2 #01-#06
"""

from __future__ import annotations

import os
import subprocess
import sys

from dotenv import load_dotenv


def run(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run(args, check=True)


def main() -> None:
    load_dotenv()

    playlist_url = os.getenv(
        "A2_PLAYLIST_URL",
        "https://www.youtube.com/playlist?list=PLk1fjOl39-5201BUdhtOM_x23poNvLouT",
    )

    run(
        sys.executable,
        "00_build_playlist.py",
        "--playlist-url",
        playlist_url,
        "--level",
        "A2",
        "--limit",
        "6",
        "--output",
        "data/a2_playlist.json",
    )

    run(
        sys.executable,
        "01_sync_notion.py",
        "--input",
        "data/a2_playlist.json",
    )


if __name__ == "__main__":
    main()
