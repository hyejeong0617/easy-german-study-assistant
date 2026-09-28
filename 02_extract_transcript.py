#!/usr/bin/env python3
"""
Extract a German transcript from a YouTube video.

Priority:
1) yt-dlp WITHOUT cookies
2) youtube-transcript-api
3) yt-dlp WITH cookies (GitHub Secret fallback)

Output:
- plain text transcript file

Cookie fallback is optional. If --cookies-file is not provided or the file does
not exist, step 3 is skipped.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


class TranscriptExtractionError(RuntimeError):
    pass


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


def classify_error(message: str) -> str:
    m = message.lower()

    if "sign in to confirm you’re not a bot" in m or "sign in to confirm you're not a bot" in m:
        return "YOUTUBE_BOT_CHECK"
    if "requestblocked" in m or "blocking requests from your ip" in m:
        return "YOUTUBE_IP_BLOCK"
    if "no subtitles" in m or "subtitles are disabled" in m:
        return "NO_SUBTITLES"
    if "cookies" in m and ("expired" in m or "invalid" in m):
        return "COOKIE_ERROR"
    if "private video" in m:
        return "PRIVATE_VIDEO"
    if "video unavailable" in m:
        return "VIDEO_UNAVAILABLE"

    return "UNKNOWN"


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

        line = re.sub(r"<[^>]+>", "", line)
        line = line.replace("&nbsp;", " ").strip()

        if line:
            cleaned.append(line)

    deduped = []
    prev = None
    for line in cleaned:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped)


def fetch_ytdlp_subtitles(
    video_url: str,
    video_id: str,
    cookies_file: str | None = None,
) -> str:
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
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "-o", outtmpl,
        ]

        if cookies_file:
            cmd.extend(["--cookies", cookies_file])

        cmd.append(video_url)

        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        combined = f"{proc.stdout}\n{proc.stderr}".strip()

        if proc.returncode != 0:
            code = classify_error(combined)
            raise TranscriptExtractionError(
                f"{code}: yt-dlp subtitle download failed:\n{combined[-3500:]}"
            )

        tmp = Path(tmpdir)
        candidates = sorted(tmp.glob(f"{video_id}*.vtt"))

        if not candidates:
            raise TranscriptExtractionError(
                "NO_SUBTITLES: yt-dlp did not produce a VTT subtitle file."
            )

        vtt_text = candidates[0].read_text(
            encoding="utf-8",
            errors="replace",
        )
        transcript = parse_vtt_text(vtt_text)

        if not transcript.strip():
            raise TranscriptExtractionError(
                "EMPTY_TRANSCRIPT: Parsed VTT transcript is empty."
            )

        return transcript


def fetch_transcript_api(video_id: str) -> str:
    api = YouTubeTranscriptApi()

    try:
        fetched = api.fetch(
            video_id,
            languages=["de", "de-DE"],
        )
    except Exception as exc:
        message = str(exc)
        code = classify_error(message)
        raise TranscriptExtractionError(
            f"{code}: youtube-transcript-api failed:\n{message}"
        ) from exc

    lines = []

    for snippet in fetched:
        text = (snippet.text or "").replace("\n", " ").strip()
        if text:
            lines.append(text)

    if not lines:
        raise TranscriptExtractionError(
            "EMPTY_TRANSCRIPT: transcript-api returned no text."
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--video-url")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cookies-file")
    args = parser.parse_args()

    vid = extract_video_id(args.video_url, args.video_id)
    url = args.video_url or f"https://www.youtube.com/watch?v={vid}"

    failures: list[str] = []

    # 1. yt-dlp without cookies
    try:
        transcript = fetch_ytdlp_subtitles(url, vid)
        method = "yt-dlp-no-cookies"
    except Exception as exc:
        failures.append(f"1) {exc}")
        print(f"[warn] yt-dlp without cookies failed:\n{exc}")
        transcript = None
        method = None

    # 2. youtube-transcript-api
    if transcript is None:
        try:
            transcript = fetch_transcript_api(vid)
            method = "youtube-transcript-api"
        except Exception as exc:
            failures.append(f"2) {exc}")
            print(f"[warn] transcript-api failed:\n{exc}")

    # 3. yt-dlp with cookies
    cookies_path = Path(args.cookies_file) if args.cookies_file else None

    if transcript is None and cookies_path and cookies_path.exists():
        try:
            transcript = fetch_ytdlp_subtitles(
                url,
                vid,
                cookies_file=str(cookies_path),
            )
            method = "yt-dlp-with-cookies"
        except Exception as exc:
            failures.append(f"3) {exc}")
            print(f"[warn] yt-dlp with cookies failed:\n{exc}")

    if transcript is None:
        summary = "\n\n".join(failures)
        raise SystemExit(
            "Transcript extraction failed after all available methods.\n\n"
            + summary
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(transcript, encoding="utf-8")

    print(f"[ok] transcript extracted with {method} -> {out}")


if __name__ == "__main__":
    main()
