#!/usr/bin/env python3
"""
Extract a German transcript from a YouTube video.

Priority:
1) youtube-transcript-api
2) yt-dlp auto subtitles fallback (.vtt)

Output:
- plain text transcript file
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(video_url: str | None, video_id: str | None) -> str:
    if video_id:
        return video_id

    if not video_url:
        raise ValueError("Provide either --video-id or --video-url.")

    patterns = [
        r"v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, video_url)
        if m:
            return m.group(1)

    raise ValueError(f"Could not parse video ID from URL: {video_url}")


def fetch_transcript_api(video_id: str) -> str:
    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=["de", "de-DE"])
    lines = []
    for snippet in fetched:
        text = (snippet.text or "").replace("\n", " ").strip()
        if text:
            lines.append(text)
    if not lines:
        raise RuntimeError("Transcript API returned no text.")
    return "\n".join(lines)


def parse_vtt_text(vtt_text: str) -> str:
    cleaned = []
    for line in vtt_text.splitlines():
        line = line.strip()

        if not line:
            continue
        if line == "WEBVTT":
            continue
        if "-->" in line:
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.fullmatch(r"\d+", line):
            continue

        # remove basic cue markup
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&nbsp;", " ", line).strip()

        if line:
            cleaned.append(line)

    # de-duplicate repeated consecutive captions
    deduped = []
    prev = None
    for line in cleaned:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped)


def fetch_ytdlp_subtitles(video_url: str, video_id: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-langs", "de,de-DE",
            "--sub-format", "vtt",
            "--no-playlist",
            "-o", outtmpl,
            video_url,
        ]
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp subtitle download failed:\n{proc.stderr[-3000:]}")

        tmp = Path(tmpdir)
        candidates = list(tmp.glob(f"{video_id}*.vtt"))
        if not candidates:
            raise RuntimeError("yt-dlp did not produce a VTT subtitle file.")

        vtt_text = candidates[0].read_text(encoding="utf-8", errors="replace")
        transcript = parse_vtt_text(vtt_text)

        if not transcript.strip():
            raise RuntimeError("Parsed VTT transcript is empty.")

        return transcript


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--video-url")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    vid = extract_video_id(args.video_url, args.video_id)
    url = args.video_url or f"https://www.youtube.com/watch?v={vid}"

    transcript = None
    method = None

    try:
        transcript = fetch_transcript_api(vid)
        method = "youtube-transcript-api"
    except Exception as first_error:
        print(f"[warn] transcript-api failed: {first_error}")
        transcript = fetch_ytdlp_subtitles(url, vid)
        method = "yt-dlp"

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(transcript, encoding="utf-8")

    print(f"[ok] transcript extracted with {method} -> {out}")


if __name__ == "__main__":
    main()
