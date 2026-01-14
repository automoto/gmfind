"""Cross-platform path management using XDG paths on Linux/macOS, AppData on Windows."""

import os
import sys
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_data_path

APP_NAME = "gmfind"
APP_AUTHOR = "gmfind"


def get_config_dir() -> Path:
    """~/.config/gmfind/ (override: GMFIND_CONFIG_DIR)"""
    if env_path := os.environ.get("GMFIND_CONFIG_DIR"):
        return Path(env_path)

    if sys.platform == "win32":
        return user_config_path(APP_NAME, APP_AUTHOR, ensure_exists=True)

    xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    path = Path(xdg_config) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """~/.local/share/gmfind/ (override: GMFIND_DATA_DIR)"""
    if env_path := os.environ.get("GMFIND_DATA_DIR"):
        return Path(env_path)

    if sys.platform == "win32":
        return user_data_path(APP_NAME, APP_AUTHOR, ensure_exists=True)

    xdg_data = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    path = Path(xdg_data) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    """~/.cache/gmfind/ (override: GMFIND_CACHE_DIR)"""
    if env_path := os.environ.get("GMFIND_CACHE_DIR"):
        return Path(env_path)

    if sys.platform == "win32":
        return user_cache_path(APP_NAME, APP_AUTHOR, ensure_exists=True)

    xdg_cache = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    path = Path(xdg_cache) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_file() -> Path:
    return get_config_dir() / "config.yaml"


def get_blocklist_file() -> Path:
    return get_config_dir() / "block_list.yaml"


def get_session_file() -> Path:
    return get_data_dir() / "steam_browser_auth.json"


def get_inventory_file(filename: str = "inventory_private.csv") -> Path:
    return get_data_dir() / filename


def get_reports_dir() -> Path:
    reports_dir = get_data_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_log_dir() -> Path:
    log_dir = get_cache_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_screenshots_dir() -> Path:
    screenshots_dir = get_cache_dir() / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


def get_log_file() -> Path:
    return get_log_dir() / "gmfind.log"


def ensure_directories() -> None:
    """Create all necessary directories."""
    get_config_dir()
    get_data_dir()
    get_cache_dir()
    get_log_dir()
    get_reports_dir()
    get_screenshots_dir()


def get_example_config() -> str:
    """Return example config.yaml content."""
    return """preferences:
  # Maximum price in USD for a game purchase
  max_price: 50.00

  # Minimum Metacritic score (0-100)
  min_metacritic_score: 75

  # Require games to have a Metacritic score (true/false)
  # When false: games without scores are allowed (good for indie games)
  # When true: games must have a score >= min_metacritic_score
  require_metacritic_score: false

  # Minimum ProtonDB rating for Steam Deck compatibility
  # Options: platinum, gold, silver, bronze, borked, unknown
  min_protondb_rating: "unknown"

  # Maximum age of games to consider (in years)
  max_game_age_years: 10

  # Minimum steam deck compatbility level. verified, playable, unsupported, unknown
  min_steam_deck_level: "unknown"
"""


def get_example_blocklist() -> str:
    """Return example block_list.yaml content."""
    return """# Games to exclude from recommendations
# Any game whose name partially matches these terms (case-insensitive) will be skipped
# Examples: "FIFA" would block "FIFA 23", "FIFA 24", etc.

blocked_terms:
  # Add terms here, one per line
  - ""
"""
