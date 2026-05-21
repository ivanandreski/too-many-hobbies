"""
JSON writer.

Takes a list of dicts and writes them to a JSON file in the standard
{ "data": [...] } envelope used across this project.
"""

import json
from pathlib import Path


def write_json(data: list[dict], output_path: str | Path) -> None:
    """
    Write data to a JSON file wrapped in the project's standard envelope.

    Args:
        data: List of entry dicts.
        output_path: Destination file path. Parent directories are created
                     automatically if they don't exist.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"data": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")  # trailing newline

    print(f"[writer] wrote {len(data)} entries → {path}")
