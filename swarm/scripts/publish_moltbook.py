#!/usr/bin/env python3
"""
Publish research posts to Moltbook.

Reads a markdown post from research/posts/, strips frontmatter,
creates the post via the Moltbook API, solves the CAPTCHA verification
challenge, and tracks published IDs to prevent double-posting.

Usage:
    python -m swarm.scripts.publish_moltbook research/posts/circuit_breakers_dominate.md
    python -m swarm.scripts.publish_moltbook --dry-run research/posts/smarter_agents_earn_less.md
    python -m swarm.scripts.publish_moltbook --submolt aisafety research/posts/governance_lessons_70_runs.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "https://www.moltbook.com/api/v1"
CREDENTIALS_PATH = Path.home() / ".config" / "moltbook" / "credentials.json"
PUBLISHED_PATH = Path("research/posts/.published.json")

# Number words for CAPTCHA solving
_ONES = [
    "zero", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine",
]
_TEENS = [
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
]


def _word_to_number(word: str) -> Optional[float]:
    """Convert a spelled-out number back to a float."""
    word = word.lower().strip()
    if not word:
        return None

    # Handle "point" for decimals
    if " point " in word:
        parts = word.split(" point ", 1)
        integer = _word_to_number(parts[0])
        if integer is None:
            return None
        # Fractional digits spelled individually
        frac_digits = parts[1].strip().split()
        frac_str = ""
        for d in frac_digits:
            v = _word_to_number(d)
            if v is not None and 0 <= v <= 9:
                frac_str += str(int(v))
        if frac_str:
            return float(f"{int(integer)}.{frac_str}")
        return integer

    # Handle "hundred"
    if "hundred" in word:
        parts = word.split("hundred", 1)
        hundreds = _word_to_number(parts[0].strip())
        if hundreds is None:
            return None
        remainder = parts[1].strip()
        if remainder:
            rem_val = _word_to_number(remainder)
            return hundreds * 100 + (rem_val or 0)
        return hundreds * 100

    # Direct lookup
    if word in _ONES:
        return float(_ONES.index(word))
    if word in _TEENS:
        return float(_TEENS.index(word) + 10)

    # Compound tens: "twenty three" etc.
    for i, t in enumerate(_TENS):
        if t and word.startswith(t):
            rest = word[len(t):].strip()
            if not rest:
                return float(i * 10)
            ones_val = _word_to_number(rest)
            if ones_val is not None:
                return float(i * 10 + int(ones_val))

    return None


def _strip_obfuscation(text: str) -> str:
    """Remove Moltbook CAPTCHA obfuscation: alternating case, punctuation, filler."""
    # Remove injected punctuation characters
    cleaned = re.sub(r'[\\^/~|\\]}<*+]', '', text)
    # Remove filler words
    fillers = {"um", "uh", "erm", "like", "eh"}
    words = cleaned.split()
    words = [w for w in words if w.lower().strip(".,!?;:'\"") not in fillers]
    cleaned = " ".join(words)
    # Normalize case
    cleaned = cleaned.lower()
    return cleaned


def _extract_numbers_from_text(text: str) -> list[float]:
    """Extract all numbers (digit or spelled) from cleaned challenge text."""
    numbers = []
    # First try digit numbers
    for m in re.finditer(r'\b\d+(?:\.\d+)?\b', text):
        numbers.append(float(m.group()))

    if numbers:
        return numbers

    # Try spelled-out numbers
    # Build a combined pattern
    # Multi-word numbers: "twenty three", "five hundred twelve"
    tokens = text.split()
    i = 0
    while i < len(tokens):
        # Try multi-word sequences
        for length in range(min(4, len(tokens) - i), 0, -1):
            chunk = " ".join(tokens[i:i + length])
            val = _word_to_number(chunk)
            if val is not None:
                numbers.append(val)
                i += length
                break
        else:
            i += 1

    return numbers


def solve_captcha(challenge_text: str) -> Optional[float]:
    """Solve a Moltbook obfuscated math challenge."""
    cleaned = _strip_obfuscation(challenge_text)

    numbers = _extract_numbers_from_text(cleaned)
    if len(numbers) < 2:
        return None

    a, b = numbers[0], numbers[1]

    # Detect operation from keywords
    text_lower = cleaned.lower()
    if any(kw in text_lower for kw in ["total force", "how much total", "how many", "total", "finds"]):
        if any(kw in text_lower for kw in ["claw", "per second", "seconds", "force"]):
            # Could be multiply or add - check context
            if "claws" in text_lower or "per second" in text_lower or "per claw" not in text_lower:
                if "finds" in text_lower or "shells" in text_lower:
                    result = a + b
                else:
                    result = a * b
            else:
                result = a * b
        else:
            result = a + b
    elif "how far" in text_lower or "how much total" in text_lower:
        result = a * b
    elif "remains" in text_lower or "loses" in text_lower:
        result = a - b
    elif "per claw" in text_lower or "splits" in text_lower:
        result = a / b if b != 0 else 0
    elif "how many" in text_lower and "more" in text_lower:
        result = a + b
    else:
        # Default: try multiply (most common challenge type)
        result = a * b

    return round(result, 2)


def load_credentials() -> dict:
    """Load Moltbook API credentials."""
    if not CREDENTIALS_PATH.exists():
        print(f"Error: No credentials at {CREDENTIALS_PATH}", file=sys.stderr)
        sys.exit(1)
    data: dict = json.loads(CREDENTIALS_PATH.read_text())
    creds: dict = data["current"]
    return creds


def load_published() -> dict:
    """Load the published posts tracking file."""
    if PUBLISHED_PATH.exists():
        result: dict = json.loads(PUBLISHED_PATH.read_text())
        return result
    return {}


def save_published(data: dict) -> None:
    """Save the published posts tracking file."""
    PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED_PATH.write_text(json.dumps(data, indent=2) + "\n")


def parse_post(filepath: Path) -> dict:
    """Parse a Moltbook post markdown file into title, content, submolt."""
    text = filepath.read_text()
    lines = text.split("\n")

    title = ""
    submolt = "general"
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("**submolt:**"):
            raw = stripped.replace("**submolt:**", "").strip()
            # Handle both m/name and r/name formats
            submolt = raw.split("/")[-1] if "/" in raw else raw
        elif stripped.startswith("## ") and not title:
            title = stripped[3:].strip()
            # Content starts after this heading
            content_start = i

    # Extract body: everything from the ## heading onward
    body_lines = lines[content_start:]
    content = "\n".join(body_lines).strip()

    return {"title": title, "content": content, "submolt": submolt}


def api_call(method: str, endpoint: str, api_key: str, data: Optional[dict] = None) -> dict:
    """Make an API call to Moltbook."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=30) as resp:
            result: dict = json.loads(resp.read())
            return result
    except HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            err = {"error": body_text}

        if e.code == 429:
            retry = err.get("retry_after", "unknown")
            print(f"Rate limited. Retry after {retry} seconds.", file=sys.stderr)
            sys.exit(1)

        print(f"API error {e.code}: {err}", file=sys.stderr)
        sys.exit(1)


def create_submolt(api_key: str, name: str, display_name: str, description: str) -> dict:
    """Create a new submolt."""
    return api_call("POST", "/submolts", api_key, {
        "name": name,
        "display_name": display_name,
        "description": description,
    })


def publish_post(filepath: Path, submolt_override: Optional[str] = None, dry_run: bool = False) -> Optional[str]:
    """Publish a post to Moltbook. Returns the post ID on success."""
    published = load_published()
    file_key = str(filepath)

    if file_key in published:
        print(f"Already published: {filepath.name}")
        print(f"  Post ID: {published[file_key]['post_id']}")
        print(f"  URL: {published[file_key].get('url', 'unknown')}")
        return str(published[file_key]["post_id"])

    post = parse_post(filepath)
    if submolt_override:
        post["submolt"] = submolt_override

    print(f"Title:   {post['title']}")
    print(f"Submolt: {post['submolt']}")
    print(f"Length:  {len(post['content'])} chars")
    print()

    if dry_run:
        print("--- DRY RUN (content preview) ---")
        preview = post["content"][:500]
        print(preview)
        if len(post["content"]) > 500:
            print(f"... ({len(post['content']) - 500} more chars)")
        return None

    creds = load_credentials()

    # Step 1: Create the post
    print("Creating post...")
    result = api_call("POST", "/posts", creds["api_key"], {
        "title": post["title"],
        "content": post["content"],
        "submolt": post["submolt"],
    })

    if not result.get("success"):
        print(f"Failed to create post: {result}", file=sys.stderr)
        sys.exit(1)

    post_id: str = result["post"]["id"]
    post_url = result["post"].get("url", "")
    print(f"Post created: {post_id}")

    # Step 2: Solve CAPTCHA verification
    verification = result.get("verification", {})
    if verification:
        challenge = verification.get("challenge", "")
        verify_code = verification.get("code", "")
        print("Solving verification challenge...")

        answer = solve_captcha(challenge)
        if answer is None:
            print(f"Could not solve CAPTCHA: {challenge}", file=sys.stderr)
            print("Post created but not verified. Verify manually.", file=sys.stderr)
            return post_id

        print(f"Answer: {answer:.2f}")
        verify_result = api_call("POST", "/verify", creds["api_key"], {
            "verification_code": verify_code,
            "answer": f"{answer:.2f}",
        })

        if verify_result.get("success"):
            print("Verified and published!")
        else:
            print(f"Verification failed: {verify_result}", file=sys.stderr)
            print("Post created but not verified.", file=sys.stderr)
    else:
        print("No verification required.")

    # Step 3: Track publication
    published[file_key] = {
        "post_id": post_id,
        "url": f"https://www.moltbook.com{post_url}",
        "submolt": post["submolt"],
        "title": post["title"],
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    save_published(published)
    print(f"Tracked in {PUBLISHED_PATH}")

    return post_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish research posts to Moltbook",
    )
    parser.add_argument("file", type=Path, help="Markdown post file to publish")
    parser.add_argument("--submolt", help="Override the submolt from the post frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be posted")
    parser.add_argument(
        "--create-submolt",
        metavar="NAME",
        help="Create a submolt before posting (e.g. multiagent-safety)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if args.create_submolt:
        creds = load_credentials()
        print(f"Creating submolt: {args.create_submolt}")
        result = create_submolt(
            creds["api_key"],
            name=args.create_submolt,
            display_name=args.create_submolt.replace("-", " ").title(),
            description="Distributional safety research for multi-agent AI systems.",
        )
        print(f"Result: {result}")
        print()

    publish_post(args.file, submolt_override=args.submolt, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
