"""Configuration loader for Steam Auto-Buyer Bot."""

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


# Load environment variables from .env file
load_dotenv()


ProtonDBRating = Literal["platinum", "gold", "silver", "bronze", "borked"]

PROTONDB_RATING_ORDER = ["platinum", "gold", "silver", "bronze", "borked"]


class SteamConfig(BaseModel):
    """Steam account configuration."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    steam_id: str = Field(..., pattern=r"^\d{17}$")


class PreferencesConfig(BaseModel):
    """Game preference configuration."""

    max_price: float = Field(default=20.0, gt=0)
    min_metacritic_score: int = Field(default=75, ge=0, le=100)
    min_protondb_rating: ProtonDBRating = Field(default="gold")
    max_game_age_years: int = Field(default=20, ge=1, le=50)

    def meets_protondb_rating(self, rating: str) -> bool:
        """Check if a game's ProtonDB rating meets the minimum requirement."""
        rating_lower = rating.lower()
        if rating_lower not in PROTONDB_RATING_ORDER:
            return False
        min_index = PROTONDB_RATING_ORDER.index(self.min_protondb_rating)
        rating_index = PROTONDB_RATING_ORDER.index(rating_lower)
        return rating_index <= min_index


class Config(BaseModel):
    """Main configuration model."""

    steam: SteamConfig
    preferences: PreferencesConfig = Field(default_factory=PreferencesConfig)


def load_config(config_path: str | Path = "config.yaml") -> Config:
    """Load configuration from YAML file and environment variables.

    Environment variables take precedence over config file values for credentials.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated Config object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required credentials are missing.
        pydantic.ValidationError: If configuration is invalid.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        yaml_config = yaml.safe_load(f) or {}

    # Get credentials from environment variables (required)
    username = os.getenv("STEAM_USERNAME")
    password = os.getenv("STEAM_PASSWORD")

    if not username:
        raise ValueError("STEAM_USERNAME environment variable is required")
    if not password:
        raise ValueError("STEAM_PASSWORD environment variable is required")

    # Get steam_id from env var or config file
    steam_id = os.getenv("STEAM_ID") or yaml_config.get("steam", {}).get("steam_id")

    if not steam_id:
        raise ValueError(
            "Steam ID is required. Set STEAM_ID environment variable or steam.steam_id in config.yaml"
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
        "min_metacritic_score": get_pref("STEAM_MIN_METACRITIC_SCORE", "min_metacritic_score", 75, int),
        "min_protondb_rating": get_pref("STEAM_MIN_PROTONDB_RATING", "min_protondb_rating", "gold", str).lower(),
        "max_game_age_years": get_pref("STEAM_MAX_GAME_AGE_YEARS", "max_game_age_years", 20, int),
    }

    # Build configuration
    config_dict = {
        "steam": {
            "username": username,
            "password": password,
            "steam_id": steam_id,
        },
        "preferences": preferences,
    }

    return Config(**config_dict)
