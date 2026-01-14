"""Recommend a random game from Metacritic that meets criteria."""

import csv
import datetime
import logging
import random
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from gmfind.config import load_config
from gmfind.game_check import (
    check_recommendation,
    fetch_protondb_rating,
    fetch_steam_deck_status,
    fetch_store_data,
)
from gmfind.recommendations.metacritic import MetacriticScraper

logger = logging.getLogger(__name__)


def get_owned_app_ids(inventory_path: str) -> set[int]:
    """Load owned App IDs from CSV."""
    owned: set[int] = set()
    path = Path(inventory_path)
    if not path.exists():
        return owned

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("steam_id"):
                try:
                    owned.add(int(row["steam_id"]))
                except (ValueError, KeyError):
                    continue
    return owned


def search_steam_for_app_id(game_name: str) -> int | None:
    """Search Steam for a game and return the first matching App ID."""
    result = search_steam(game_name)
    return result[0] if result else None


def normalize(s: str) -> str:
    """Normalize a string for comparison by keeping only alphanumeric chars.

    Args:
        s: Input string to normalize.

    Returns:
        Lowercase string with only alphanumeric characters.
    """
    return "".join(c.lower() for c in s if c.isalnum())


def _extract_app_id_from_url(url: str) -> int | None:
    """Extract Steam app ID from a URL using urllib.parse.

    Args:
        url: A Steam URL like '/app/12345/Game_Name/' or full URL.

    Returns:
        The app ID as an integer, or None if not found.
    """
    if not url:
        return None

    path = urlparse(url).path
    parts = path.strip("/").split("/")

    try:
        app_idx = parts.index("app")
        return int(parts[app_idx + 1])
    except (ValueError, IndexError):
        return None


def search_steam(game_name: str) -> tuple[int, str] | None:
    """Search Steam for a game and return (app_id, title) or None."""
    requested_norm = normalize(game_name)
    if not requested_norm:
        return None

    try:
        url = f"https://store.steampowered.com/search/?term={quote(game_name)}&category1=998"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.select(".search_result_row")

        for result in results:
            title_elem = result.select_one(".title")
            if not title_elem:
                continue

            result_name = title_elem.get_text(strip=True)
            result_norm = normalize(result_name)

            # Ensure we don't match on empty strings
            if not result_norm:
                continue

            # Priority 1: Exact match (normalized)
            # Priority 2: One is a subset of the other (fallback)
            if (
                requested_norm == result_norm
                or requested_norm in result_norm
                or result_norm in requested_norm
            ):
                href = str(result.get("href", ""))
                app_id = _extract_app_id_from_url(href)
                if app_id:
                    logger.info(
                        f"  - Search match: '{result_name}' for query "
                        f"'{game_name}' (AppID: {app_id})"
                    )
                    return (app_id, result_name)

    except Exception as e:
        logger.warning(f"Failed to search Steam for '{game_name}': {e}")

    return None


def get_recommendation_with_paths(
    config_path: str, inventory_path: str, block_list_path: str
) -> int | None:
    """Find a random recommended game meeting all criteria using file paths."""
    config = load_config(config_path)
    owned_ids = get_owned_app_ids(inventory_path)

    current_year = datetime.datetime.now().year
    min_year = current_year - config.preferences.max_game_age_years
    min_score = config.preferences.min_metacritic_score

    logger.info(
        f"Fetching top PC games from Metacritic (Score >= {min_score}, Year >= {min_year})..."
    )

    scraper = MetacriticScraper()
    games = scraper.fetch_top_rated_games(min_score=min_score, min_year=min_year, limit=100)

    if not games:
        logger.error("No games found meeting criteria.")
        return None

    random.shuffle(games)

    logger.info(f"Found {len(games)} candidates. Checking against all criteria...")

    for game in games:
        logger.info(f"Checking candidate: {game.name}")

        app_id = search_steam_for_app_id(game.name)
        if not app_id:
            continue

        store_info = fetch_store_data(app_id)
        if "error" in store_info:
            continue

        game_data = {
            "app_id": app_id,
            "name": store_info.get("name"),
            "type": store_info.get("type"),
            "release_year": store_info.get("release_year"),
            "steam_deck": fetch_steam_deck_status(app_id),
            "protondb": fetch_protondb_rating(app_id),
            "requires_3rd_party_account": store_info.get("requires_3rd_party_account"),
            "3rd_party_account_details": store_info.get("3rd_party_account_details"),
            "_price_val": store_info.get("price_val"),
            "_metacritic_score": store_info.get("metacritic_score"),
        }

        rec = check_recommendation(game_data, config_path, block_list_path, owned_ids)

        if rec and rec.get("recommended"):
            logger.info(f"  - Found valid recommendation: {game.name} (AppID: {app_id})")
            return app_id
        else:
            reasons = ", ".join(rec.get("reasons", [])) if rec else "Unknown"
            logger.info(f"  - Rejected: {reasons}")

        time.sleep(0.5)

    return None


def main():
    """CLI entry point for the recommendation script."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--inventory", default="inventory_private.csv")
    parser.add_argument("--block-list", default="block_list.yaml")
    args = parser.parse_args()

    app_id = get_recommendation_with_paths(args.config, args.inventory, args.block_list)

    if app_id:
        print(app_id)
    else:
        logger.error("Could not find any suitable games from the candidates.")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
