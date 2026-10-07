"""Send one simple question to DeepSeek.

Examples:
    python scripts/test_deepseek.py
    python scripts/test_deepseek.py "Thu do cua Viet Nam la gi?"

Environment variables are loaded from backend/.env:
    LLM_API_KEY or LLM_API
    LLM_BASE_URL (optional, defaults to https://api.deepseek.com)
    LLM_MODEL (optional, defaults to deepseek-flash)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / "backend" / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask DeepSeek one question")
    parser.add_argument(
        "question",
        nargs="?",
        default="Thu do cua Viet Nam la gi? Tra loi ngan gon.",
        help="Question sent to DeepSeek",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="HTTP timeout in seconds (default: 30)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ENV_PATH)

    api_key = (os.getenv("LLM_API_KEY") or os.getenv("LLM_API") or "").strip()
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

    if not api_key:
        print(
            f"ERROR: Missing LLM_API_KEY or LLM_API in {ENV_PATH}",
            file=sys.stderr,
        )
        return 2

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": args.question}],
                "max_tokens": 200,
                "temperature": 0,
            },
            timeout=args.timeout,
        )
    except requests.Timeout:
        print(
            f"ERROR: Timed out connecting to {base_url} after {args.timeout:g}s",
            file=sys.stderr,
        )
        return 3
    except requests.RequestException as exc:
        print(f"ERROR: Cannot connect to DeepSeek: {exc}", file=sys.stderr)
        return 3

    try:
        payload = response.json()
    except requests.JSONDecodeError:
        print(
            f"ERROR: DeepSeek returned HTTP {response.status_code} with non-JSON content",
            file=sys.stderr,
        )
        return 4

    if not response.ok:
        error = payload.get("error") or {}
        message = error.get("message") or str(error) or "Unknown API error"
        print(f"ERROR: DeepSeek HTTP {response.status_code}: {message}", file=sys.stderr)
        return 4

    choices = payload.get("choices") or []
    if not choices:
        print("ERROR: DeepSeek response has no choices", file=sys.stderr)
        return 4

    answer = choices[0].get("message", {}).get("content")
    if not answer:
        print("ERROR: DeepSeek returned an empty answer", file=sys.stderr)
        return 4

    print(answer.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
