"""
JSON writer.

Writes a payload to a JSON file in the standard { "data": ... } envelope used
across this project.

Most features produce a list of entries (diary, favorites), but some produce a
keyed object instead — frontend/data/gear/bikes.json maps role names like
"mainBike" to a single entry each — so both shapes are supported.
"""

import json
from pathlib import Path

# The envelope payload: either a list of entries or a mapping of key → entry.
JsonPayload = list[dict] | dict[str, dict]


def write_json(data: JsonPayload, output_path: str | Path) -> None:
    """
    Write data to a JSON file wrapped in the project's standard envelope.

    Args:
        data: List of entry dicts, or a dict mapping keys to entry dicts.
        output_path: Destination file path. Parent directories are created
                     automatically if they don't exist.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"data": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")  # trailing newline

    print(f"[writer] wrote {_describe_size(data)} → {path}")


def _describe_size(data: JsonPayload) -> str:
    """Describe the payload for the log line, in terms suited to its shape."""
    if isinstance(data, dict):
        return f"{len(data)} keys ({', '.join(data)})" if data else "0 keys"
    return f"{len(data)} entries"
