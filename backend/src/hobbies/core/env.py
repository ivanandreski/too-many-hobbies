"""
Environment variable helpers for API credentials.

Secrets are read from the process environment, so they can come from a local
.env file when working by hand or from repository secrets in CI. Nothing here
writes credentials to disk — backend/.gitignore excludes *.env precisely so
they never get committed.
"""

import os
from pathlib import Path

# Default location for local credentials, relative to the backend/ directory.
DEFAULT_ENV_FILENAME = ".env"

COMMENT_PREFIX = "#"
ASSIGNMENT_SEPARATOR = "="


def load_env_file(env_file_path: str | Path) -> int:
    """
    Load KEY=VALUE lines from a file into os.environ.

    Existing environment variables win, so an explicitly exported value or a CI
    secret is never silently overridden by a stale local file. Blank lines and
    lines starting with '#' are ignored, as are surrounding quotes on values.

    Args:
        env_file_path: File to read. Missing files are not an error — the
                       credentials may well come from the environment instead.

    Returns:
        Number of variables actually set.
    """
    path = Path(env_file_path)
    if not path.is_file():
        return 0

    loaded_count = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue
        if ASSIGNMENT_SEPARATOR not in line:
            continue

        name, _, value = line.partition(ASSIGNMENT_SEPARATOR)
        name = name.strip()
        if name in os.environ:
            continue

        os.environ[name] = value.strip().strip("'\"")
        loaded_count += 1

    return loaded_count


def require_env(variable_name: str) -> str:
    """
    Read a required environment variable.

    Raises:
        RuntimeError: If the variable is missing or empty, naming the variable
                      so the fix is obvious.
    """
    value = os.environ.get(variable_name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {variable_name}. "
            f"Set it in backend/{DEFAULT_ENV_FILENAME} or export it before running."
        )
    return value
