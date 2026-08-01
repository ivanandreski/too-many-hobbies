"""
Command-line entrypoint for generating the frontend's JSON data files.

Usage:
    hobbies-generate --username <letterboxd_username>       # every feature
    hobbies-generate diary --username <letterboxd_username>
    hobbies-generate gear cycling running                   # all Strava outputs
    hobbies-generate favorites --username <name> --out /tmp/fav.json

Each feature writes into frontend/data/ by default. Pass --out to write
somewhere else (e.g. backend/output/, which is gitignored) when you want to
inspect the result before it lands on the real site data.

Features differ in what they need:
  * diary, favorites          a public Letterboxd username, via --username
  * gear, cycling, running    a logged-in Strava session; see
                              hobbies.features.strava.login

The three Strava features share one scraper, so asking for all of them logs in
once and reads each page once rather than three times.
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
from hobbies.features.strava.pipelines import CyclingPipeline, GearPipeline, RunningPipeline
from hobbies.features.strava.scraper import StravaScraper

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
        needs_strava:   Whether the feature uses the shared Strava scraper.
        build:          Constructs the pipeline. Receives the username (empty
                        when not needed), the resolved output path, and the
                        shared scraper (None for non-Strava features).
    """
    default_output: Path
    needs_username: bool
    needs_strava: bool
    build: Callable[[str, Path, StravaScraper | None], DataPipeline]


FEATURES: dict[str, Feature] = {
    "diary": Feature(
        default_output=Path("movies") / "diary.json",
        needs_username=True,
        needs_strava=False,
        build=lambda username, output_path, _scraper: DiaryPipeline(
            username=username, output_path=output_path
        ),
    ),
    "favorites": Feature(
        default_output=Path("movies") / "favorites.json",
        needs_username=True,
        needs_strava=False,
        build=lambda username, output_path, _scraper: FavoritesPipeline(
            username=username, output_path=output_path
        ),
    ),
    "gear": Feature(
        default_output=Path("gear") / "bikes.json",
        needs_username=False,
        needs_strava=True,
        build=lambda _username, output_path, scraper: GearPipeline(
            output_path=output_path, scraper=scraper
        ),
    ),
    "cycling": Feature(
        default_output=Path("strava") / "cycling.json",
        needs_username=False,
        needs_strava=True,
        build=lambda _username, output_path, scraper: CyclingPipeline(
            output_path=output_path, scraper=scraper
        ),
    ),
    "running": Feature(
        default_output=Path("strava") / "running.json",
        needs_username=False,
        needs_strava=True,
        build=lambda _username, output_path, scraper: RunningPipeline(
            output_path=output_path, scraper=scraper
        ),
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
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Run Strava scraping in a visible browser. Useful when a scrape "
             "fails and you want to watch what the page does.",
    )
    return parser


def run(
    feature_names: list[str],
    username: str | None,
    output_path: Path | None,
    show_browser: bool = False,
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

    # One scraper shared by every Strava feature: one login, one pass over the
    # pages, regardless of how many files are being generated.
    scraper = (
        StravaScraper(headless=not show_browser)
        if any(FEATURES[name].needs_strava for name in feature_names)
        else None
    )

    for feature_name in feature_names:
        feature = FEATURES[feature_name]
        destination = output_path or FRONTEND_DATA_DIR / feature.default_output

        print(f"[{feature_name}] generating → {destination}")
        try:
            feature.build(username or "", destination, scraper).run()
        except (RuntimeError, ValueError, HttpError) as error:
            # Missing credentials, an expired session, changed markup: all
            # actionable problems rather than bugs, so report them plainly
            # instead of dumping a traceback.
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
        show_browser=arguments.show_browser,
    )


if __name__ == "__main__":
    main()
