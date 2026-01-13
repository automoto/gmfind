"""Cross-platform path management for gmfind.

Uses platformdirs for XDG-compliant paths on Linux/macOS
and appropriate locations on Windows.

Directory structure:
    ~/.config/gmfind/           # Config files (config.yaml, block_list.yaml)
    ~/.local/share/gmfind/      # Data files (session, inventory exports)
    ~/.cache/gmfind/            # Cache (logs)
"""

import os
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_data_path

APP_NAME = "gmfind"
APP_AUTHOR = "gmfind"  # Used on Windows


def get_config_dir() -> Path:
    """Get the configuration directory.

    Linux/macOS: ~/.config/gmfind/
    Windows: C:/Users/<user>/AppData/Local/gmfind/

    Environment variable override: GMFIND_CONFIG_DIR
    """
    if env_path := os.environ.get("GMFIND_CONFIG_DIR"):
        return Path(env_path)
    return user_config_path(APP_NAME, APP_AUTHOR, ensure_exists=True)


def get_data_dir() -> Path:
    """Get the data directory for session and exports.

    Linux/macOS: ~/.local/share/gmfind/
    Windows: C:/Users/<user>/AppData/Local/gmfind/

    Environment variable override: GMFIND_DATA_DIR
    """
    if env_path := os.environ.get("GMFIND_DATA_DIR"):
        return Path(env_path)
    return user_data_path(APP_NAME, APP_AUTHOR, ensure_exists=True)


def get_cache_dir() -> Path:
    """Get the cache directory for logs.

    Linux/macOS: ~/.cache/gmfind/
    Windows: C:/Users/<user>/AppData/Local/gmfind/Cache/

    Environment variable override: GMFIND_CACHE_DIR
    """
    if env_path := os.environ.get("GMFIND_CACHE_DIR"):
        return Path(env_path)
    return user_cache_path(APP_NAME, APP_AUTHOR, ensure_exists=True)


# Specific file paths
def get_config_file() -> Path:
    """Get config.yaml path."""
    return get_config_dir() / "config.yaml"


def get_blocklist_file() -> Path:
    """Get block_list.yaml path."""
    return get_config_dir() / "block_list.yaml"


def get_session_file() -> Path:
    """Get steam_browser_auth.json path."""
    return get_data_dir() / "steam_browser_auth.json"


def get_inventory_file(filename: str = "inventory_private.csv") -> Path:
    """Get inventory CSV path."""
    return get_data_dir() / filename


def get_reports_dir() -> Path:
    """Get reports directory for markdown output."""
    reports_dir = get_data_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_log_dir() -> Path:
    """Get logs directory."""
    log_dir = get_cache_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_screenshots_dir() -> Path:
    """Get screenshots directory for error debugging."""
    screenshots_dir = get_cache_dir() / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


def get_log_file() -> Path:
    """Get main log file path."""
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
