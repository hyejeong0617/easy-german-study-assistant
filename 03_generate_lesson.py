#!/usr/bin/env python3
"""
Generate a German study lesson JSON from a transcript using OpenAI.

Output JSON keys:
- video_summary
- key_vocabulary
- key_expressions
- grammar_points
- listening_points
- speaking_practice
- todays_core
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_PROMPT = """You are a German tutor for a Korean learner.

Learner profile:
- native language: Korean
- current level: A2 (moving toward B1/B2)
- goal: understand and use practical spoken German

Analyze the provided Easy German transcript and return a compact study pack.

Important rules:
- Do not explain every sentence.
- Focus on useful real-life German.
- Keep explanations simple and practical.
- Use Korean for explanations.
- Preserve German examples in natural German.
- Avoid advanced linguistic jargon.
- If the transcript is long, still keep the lesson concise.

Return STRICT JSON only with this structure:

{
  "video_summary": {
    "korean_summary": ["sentence1", "sentence2", "sentence3"]
  },
  "key_vocabulary": [
    {
      "word": "German word",
      "meaning_ko": "Korean meaning",
      "example_from_video": "German example from transcript or close paraphrase",
      "simple_example": "Simple German example"
    }
  ],
  "key_expressions": [
    {
      "expression": "German expression",
      "meaning_ko": "Korean meaning",
      "when_to_use": "short Korean explanation",
      "example": "German example"
    }
  ],
  "grammar_points": [
    {
      "topic": "grammar topic",
      "explanation_ko": "short Korean explanation",
      "examples": ["German example 1", "German example 2"]
    }
  ],
  "listening_points": [
    {
      "expression": "German word or phrase",
      "why_it_is_hard": "short Korean explanation",
      "tip": "short Korean listening tip"
    }
  ],
  "speaking_practice": [
    "Question 1 in German",
    "Question 2 in German",
    "Question 3 in German"
  ],
  "todays_core": {
    "words": ["w1", "w2", "w3"],
    "expressions": ["e1", "e2"],
    "grammar": "one grammar point"
  }
}

Quantity targets:
- key_vocabulary: 8 to 12 items
- key_expressions: 5 to 8 items
- grammar_points: 1 to 2 items
- listening_points: 2 to 3 items
- speaking_practice: exactly 3 items
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

    user_prompt = USER_TEMPLATE.format(
        level=args.level,
        title=args.title,
        transcript=transcript[:120000],  # defensive truncation
    )

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
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
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] lesson JSON saved -> {out}")


if __name__ == "__main__":
    main()
