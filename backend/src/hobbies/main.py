"""
Command-line entrypoint for generating the frontend's JSON data files.

Usage:
    hobbies-generate --username <letterboxd_username>       # every feature
    hobbies-generate diary --username <letterboxd_username>
    hobbies-generate gear                                   # needs no username
    hobbies-generate favorites --username <name> --out /tmp/fav.json

Each feature writes into frontend/data/ by default. Pass --out to write
somewhere else (e.g. backend/output/, which is gitignored) when you want to
inspect the result before it lands on the real site data.

Features differ in what they need:
  * diary, favorites — a public Letterboxd username, via --username
  * gear             — Strava API credentials, via the environment or backend/.env
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hobbies.core.env import DEFAULT_ENV_FILENAME, load_env_file
from hobbies.core.http import HttpError
from hobbies.core.pipeline import DataPipeline
from hobbies.features.diary.pipeline import DiaryPipeline
from hobbies.features.favorites.pipeline import FavoritesPipeline
from hobbies.features.gear.pipeline import GearPipeline

# main.py lives at backend/src/hobbies/main.py, so the repo root is four up.
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DATA_DIR = REPO_ROOT / "frontend" / "data"


@dataclass(frozen=True)
class Feature:
    """
    One generatable data file.

    Attributes:
        default_output: Output path relative to frontend/data.
        needs_username: Whether the feature requires --username.
        build:          Constructs the pipeline from a username (empty when not
                        needed) and a resolved output path.
    """
    default_output: Path
    needs_username: bool
    build: Callable[[str, Path], DataPipeline]


FEATURES: dict[str, Feature] = {
    "diary": Feature(
        default_output=Path("movies") / "diary.json",
        needs_username=True,
        build=lambda username, output_path: DiaryPipeline(
            username=username, output_path=output_path
        ),
    ),
    "favorites": Feature(
        default_output=Path("movies") / "favorites.json",
        needs_username=True,
        build=lambda username, output_path: FavoritesPipeline(
            username=username, output_path=output_path
        ),
    ),
    "gear": Feature(
        default_output=Path("gear") / "bikes.json",
        needs_username=False,
        build=lambda username, output_path: GearPipeline(output_path=output_path),
    ),
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
        default=None,
        help="Letterboxd username. Required for the diary and favorites features.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path. Only valid when generating a single feature.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(DEFAULT_ENV_FILENAME),
        help=f"File to load API credentials from (default: {DEFAULT_ENV_FILENAME}). "
             f"Missing files are ignored; real environment variables always win.",
    )
    return parser


def run(
    feature_names: list[str],
    username: str | None,
    output_path: Path | None,
) -> None:
    """Run each named pipeline in turn, writing to its default or given path."""
    if output_path is not None and len(feature_names) > 1:
        raise SystemExit("--out can only be used when generating a single feature")

    features_needing_username = [
        name for name in feature_names if FEATURES[name].needs_username
    ]
    if features_needing_username and not username:
        raise SystemExit(
            f"--username is required for: {', '.join(features_needing_username)}"
        )

    for feature_name in feature_names:
        feature = FEATURES[feature_name]
        destination = output_path or FRONTEND_DATA_DIR / feature.default_output

        print(f"[{feature_name}] generating → {destination}")
        try:
            feature.build(username or "", destination).run()
        except (RuntimeError, ValueError, HttpError) as error:
            # Missing credentials, a rejected token, an unexpected upstream
            # response: all actionable configuration problems rather than bugs,
            # so report them plainly instead of dumping a traceback.
            raise SystemExit(f"[{feature_name}] failed: {error}") from error


def main() -> None:
    arguments = build_argument_parser().parse_args()

    # Credentials come from the environment; a local env file is a convenience
    # for working by hand, so a missing one is not an error.
    load_env_file(arguments.env_file)

    run(
        feature_names=arguments.features or list(FEATURES),
        username=arguments.username,
        output_path=arguments.out,
    )


if __name__ == "__main__":
    main()
