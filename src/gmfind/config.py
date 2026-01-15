"""Configuration loader for Steam Auto-Buyer Bot."""

import os
from pathlib import Path
from typing import Literal

import msgspec
import yaml

from gmfind.paths import get_config_file

# ProtonDB ratings (order matters: best to worst)
ProtonDBRating = Literal["platinum", "gold", "silver", "bronze", "borked", "unknown"]
PROTONDB_RATING_ORDER = ["platinum", "gold", "silver", "bronze", "borked", "unknown"]

# Steam Deck levels (order matters: best to worst)
SteamDeckLevel = Literal["verified", "playable", "unsupported", "unknown"]
STEAM_DECK_LEVEL_ORDER = ["verified", "playable", "unsupported", "unknown"]


class SteamConfig(msgspec.Struct):
    """Steam account configuration."""

    username: str | None = None
    password: str | None = None
    steam_id: str | None = None


class PreferencesConfig(msgspec.Struct):
    """Game preference configuration."""

    max_price: float = 20.0
    min_metacritic_score: int = 75
    require_metacritic_score: bool = False
    min_protondb_rating: ProtonDBRating = "gold"
    max_game_age_years: int = 20
    min_steam_deck_level: SteamDeckLevel = "playable"

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if self.max_price <= 0:
            raise ValueError("max_price must be greater than 0")
        if not 0 <= self.min_metacritic_score <= 100:
            raise ValueError("min_metacritic_score must be between 0 and 100")
        if not 1 <= self.max_game_age_years <= 50:
            raise ValueError("max_game_age_years must be between 1 and 50")

    def meets_protondb_rating(self, rating: str) -> bool:
        """Check if a game's ProtonDB rating meets the minimum requirement."""
        rating_lower = rating.lower()
        if rating_lower not in PROTONDB_RATING_ORDER:
            return False
        min_index = PROTONDB_RATING_ORDER.index(self.min_protondb_rating)
        rating_index = PROTONDB_RATING_ORDER.index(rating_lower)
        return rating_index <= min_index

    def meets_steam_deck_level(self, level: str) -> bool:
        """Check if a game's Steam Deck level meets the minimum requirement."""
        level_lower = level.lower()
        if level_lower not in STEAM_DECK_LEVEL_ORDER:
            return False
        min_index = STEAM_DECK_LEVEL_ORDER.index(self.min_steam_deck_level)
        level_index = STEAM_DECK_LEVEL_ORDER.index(level_lower)
        return level_index <= min_index


class Config(msgspec.Struct):
    """Main configuration model."""

    steam: SteamConfig
    preferences: PreferencesConfig = msgspec.field(default_factory=PreferencesConfig)


def load_config(config_path: str | Path | None = None, require_credentials: bool = True) -> Config:
    """Load configuration from YAML file and environment variables.

    Environment variables take precedence over config file values for credentials.

    Args:
        config_path: Path to the YAML configuration file.
        require_credentials: If True, raise error when credentials are missing.
            Set to False for commands that only need preferences (e.g., deals).

    Returns:
        Validated Config object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required credentials are missing (when require_credentials=True).
        msgspec.ValidationError: If configuration is invalid.
    """
    # Use XDG default if no path specified
    if config_path is None:
        config_path = get_config_file()
    else:
        config_path = Path(config_path)

    # Use existing config.yaml if it exists, otherwise use defaults/env vars
    yaml_config: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}

    # Get credentials from environment variables
    username = os.getenv("STEAM_USERNAME")
    password = os.getenv("STEAM_PASSWORD")
    steam_id = os.getenv("STEAM_ID") or yaml_config.get("steam", {}).get("steam_id")

    # Only validate credentials if required
    if require_credentials:
        if not username:
            raise ValueError("STEAM_USERNAME environment variable is required")
        if not password:
            raise ValueError("STEAM_PASSWORD environment variable is required")
        if not steam_id:
            raise ValueError(
                "Steam ID is required. Set STEAM_ID env var or steam.steam_id in config.yaml"
            )

    # Get preferences from env vars with fallback to YAML config
    yaml_prefs = yaml_config.get("preferences", {})

    def get_pref(env_var: str, yaml_key: str, default, convert=str):
        """Get preference from env var, falling back to YAML, then default."""
        env_val = os.getenv(env_var)
        if env_val is not None:
            return convert(env_val)
        yaml_val = yaml_prefs.get(yaml_key)
        if yaml_val is not None:
            return yaml_val
        return default

    preferences = {
        "max_price": get_pref("STEAM_MAX_PRICE", "max_price", 20.0, float),
        "min_metacritic_score": get_pref(
            "STEAM_MIN_METACRITIC_SCORE", "min_metacritic_score", 75, int
        ),
        "require_metacritic_score": get_pref(
            "STEAM_REQUIRE_METACRITIC",
            "require_metacritic_score",
            False,
            lambda x: x.lower() in ("true", "1", "yes") if isinstance(x, str) else bool(x),
        ),
        "min_protondb_rating": get_pref(
            "STEAM_MIN_PROTONDB_RATING", "min_protondb_rating", "gold", str
        ).lower(),
        "max_game_age_years": get_pref("STEAM_MAX_GAME_AGE_YEARS", "max_game_age_years", 20, int),
        "min_steam_deck_level": get_pref(
            "STEAM_MIN_DECK_LEVEL", "min_steam_deck_level", "playable", str
        ).lower(),
    }

    # Build configuration
    steam_config = SteamConfig(
        username=username,
        password=password,
        steam_id=steam_id,
    )

    preferences_config = PreferencesConfig(**preferences)

    return Config(steam=steam_config, preferences=preferences_config)
