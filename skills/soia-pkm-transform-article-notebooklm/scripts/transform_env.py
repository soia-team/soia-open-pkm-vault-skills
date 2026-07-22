"""Load the transform skill's schema-v2 private YAML configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path


SKILL_NAME = Path(__file__).resolve().parents[1].name
OVERRIDE_CONFIG_NAME = "SOIA_PKM_TRANSFORM_ARTICLE_NOTEBOOKLM_CONFIG_FILE"
OVERRIDE_ENV_NAME = "SOIA_PKM_TRANSFORM_ARTICLE_NOTEBOOKLM_ENV_FILE"
DEFAULT_CONFIG_FILE = Path.home() / ".config" / "soia-skills" / SKILL_NAME / "config.yml"
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PATH_LIKE_KEYS = {"OBSIDIAN_VAULT", "NOTEBOOKLM_HOME", "OPEN_DESIGN_HOME"}


def _candidate_paths() -> list[Path]:
    paths = []
    for name in (OVERRIDE_CONFIG_NAME, OVERRIDE_ENV_NAME):
        value = os.environ.get(name)
        if value:
            paths.append(Path(value).expanduser())
    paths.append(DEFAULT_CONFIG_FILE)
    return paths


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if not value or value in {"null", "~"}:
        return ""
    if value[0] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def _load_config_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    in_env = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0:
            in_env = stripped == "env:"
            continue
        if not in_env or indent < 2 or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            continue
        value = _parse_scalar(raw_value)
        if key in PATH_LIKE_KEYS:
            value = os.path.expandvars(os.path.expanduser(value))
        values[key] = value
    return values


def load_private_env() -> Path | None:
    """Load the first existing config without overriding process variables."""
    for path in _candidate_paths():
        if not path.is_file():
            continue
        for key, value in _load_config_env(path).items():
            os.environ.setdefault(key, value)
        return path
    return None
