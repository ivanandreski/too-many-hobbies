"""
Command-line entrypoint for generating the frontend's JSON data files.

Usage:
    hobbies-generate --username <letterboxd_username>              # every feature
    hobbies-generate diary --username <letterboxd_username>
    hobbies-generate favorites --username <letterboxd_username> --out /tmp/fav.json

Each feature writes into frontend/data/ by default. Pass --out to write
somewhere else (e.g. backend/output/, which is gitignored) when you want to
inspect the result before it lands on the real site data.
"""

import argparse
from pathlib import Path

from hobbies.features.diary.pipeline import DiaryPipeline
from hobbies.features.favorites.pipeline import FavoritesPipeline

# main.py lives at backend/src/hobbies/main.py, so the repo root is four up.
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DATA_DIR = REPO_ROOT / "frontend" / "data"

# Feature name → (pipeline class, default output path relative to frontend/data)
FEATURES = {
    "diary": (DiaryPipeline, Path("movies") / "diary.json"),
    "favorites": (FavoritesPipeline, Path("movies") / "favorites.json"),
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hobbies-generate",
        description="Generate the frontend's JSON data files from external sources.",
    )
    parser.add_argument(
        "features",
        nargs="*",
        choices=[*FEATURES, []],
        metavar="FEATURE",
        help=f"Features to generate ({', '.join(FEATURES)}). Defaults to all of them.",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Letterboxd username to pull data for.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path. Only valid when generating a single feature.",
    )
    return parser


def run(feature_names: list[str], username: str, output_path: Path | None) -> None:
    """Run each named pipeline in turn, writing to its default or given path."""
    if output_path is not None and len(feature_names) > 1:
        raise SystemExit("--out can only be used when generating a single feature")

    for feature_name in feature_names:
        pipeline_class, default_relative_path = FEATURES[feature_name]
        destination = output_path or FRONTEND_DATA_DIR / default_relative_path

        print(f"[{feature_name}] generating → {destination}")
        pipeline_class(username=username, output_path=destination).run()


def main() -> None:
    arguments = build_argument_parser().parse_args()
    run(
        feature_names=arguments.features or list(FEATURES),
        username=arguments.username,
        output_path=arguments.out,
    )


if __name__ == "__main__":
    main()
