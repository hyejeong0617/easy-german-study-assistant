#!/usr/bin/env python3
"""Generate a concise A2 Fast Track lesson JSON from a transcript using OpenAI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_PROMPT = """You are a German tutor for a Korean learner doing an A2 listening sprint.

Learner goal:
- move quickly through many Easy German A2 videos
- understand the main idea
- collect useful spoken expressions
- avoid over-studying easy material
- prepare to start B1 in January

Use ONLY information supported by the transcript for claims about the video.
Do not invent quotes from the video. German text labeled as coming from the
video must be copied or minimally cleaned from the transcript.

Keep the lesson compact. This is a 5-10 minute review, not a full textbook lesson.
Use Korean for explanations and natural German for examples.

Return STRICT JSON only with this structure:
{
  "video_summary": {
    "korean_summary": ["2-3 concise Korean sentences"]
  },
  "key_expressions": [
    {
      "expression": "useful German phrase from the transcript",
      "meaning_ko": "Korean meaning",
      "example_from_video": "actual or minimally cleaned transcript sentence",
      "use_note_ko": "when/how to use it"
    }
  ],
  "key_vocabulary": [
    {
      "word": "German word",
      "meaning_ko": "Korean meaning",
      "example_from_video": "actual or minimally cleaned transcript sentence"
    }
  ],
  "grammar_point": {
    "topic": "one useful grammar point",
    "explanation_ko": "short practical explanation",
    "example_from_video": "actual or minimally cleaned transcript example"
  },
  "listen_again": [
    {
      "sentence": "actual transcript sentence worth replaying",
      "focus_ko": "what to listen for"
    }
  ],
  "speaking_practice": [
    "German prompt 1",
    "German prompt 2"
  ]
}

Rules:
- video_summary: 2-3 sentences
- key_expressions: exactly 5 unless the transcript truly contains fewer useful A2 expressions
- key_vocabulary: 5-7 items; skip very basic A1 words unless central to the video
- grammar_point: at most 1; if no useful grammar point is evident, return null
- listen_again: exactly 3 transcript sentences when possible
- speaking_practice: exactly 2 prompts
- prioritize reusable spoken German over isolated vocabulary
- do not add a Today's Core section; the 5 expressions are the core material
"""

USER_TEMPLATE = """Level: {level}
Video title: {title}

Transcript:
\"\"\"
{transcript}
\"\"\"
"""


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--level", default="A2")
    parser.add_argument("--title", default="Easy German lesson")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing.")

    transcript = Path(args.transcript).read_text(encoding="utf-8")
    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    level=args.level,
                    title=args.title,
                    transcript=transcript[:120000],
                ),
            },
        ],
    )

    raw = (response.output_text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Model did not return valid JSON.\n"
            f"Raw response:\n{raw[:3000]}"
        ) from exc

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[ok] lesson JSON saved -> {out}")


if __name__ == "__main__":
    main()
