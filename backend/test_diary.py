"""
Smoke test for the Letterboxd diary pipeline.

Usage:
    cd backend
    python test_diary.py <letterboxd_username>

Output is written to backend/output/diary.json so you can inspect it
before anything touches the real frontend data directory.
"""

import sys
from pathlib import Path

# Allow running from the backend/ directory without installing
sys.path.insert(0, str(Path(__file__).parent))

from fetcher import fetch_url
from parsers.letterboxd import parse_diary
from writers.json_writer import write_json

RSS_URL = "https://letterboxd.com/{username}/rss/"
OUTPUT_PATH = Path(__file__).parent / "output" / "diary.json"


def run(username: str) -> None:
    url = RSS_URL.format(username=username)
    print(f"[fetcher] GET {url}")
    rss_text = fetch_url(url)

    print("[parser] parsing diary entries …")
    entries = parse_diary(rss_text)
    print(f"[parser] found {len(entries)} entries")

    write_json(entries, OUTPUT_PATH)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_diary.py <letterboxd_username>")
        sys.exit(1)
    run(sys.argv[1])
