"""Module to aggregate game data into structured JSON."""

import json
import logging
from typing import Any
import requests
from src.recommendations.protondb import ProtonDBClient
from src.recommendations.steam_deck import SteamDeckClient

logger = logging.getLogger(__name__)


def check_game(app_id: str):
    """Fetch and print structured JSON data for a game."""
    try:
        app_id_int = int(app_id)
    except ValueError:
        print(json.dumps({"error": "Invalid App ID. Must be an integer."}, indent=2))
        return

    output: dict[str, Any] = {
        "app_id": app_id_int,
        "name": None,
        "price": None,
        "steam_deck": None,
        "protondb": None,
        "metacritic": None,
        "steam_reviews": None,
    }

    # 1. Store API (Core Info, Price, Metacritic)
    try:
        store_url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": str(app_id), "cc": "us", "l": "en"}
        resp = requests.get(store_url, params=params, timeout=10)
        data = resp.json()

        if data and data.get(str(app_id), {}).get("success"):
            game_data = data[str(app_id)]["data"]
            output["name"] = game_data.get("name")

            # Price
            if game_data.get("is_free"):
                output["price"] = "Free"
            elif "price_overview" in game_data:
                output["price"] = game_data["price_overview"]["final_formatted"]
            else:
                output["price"] = "Not Available"

            # Metacritic (from Steam Metadata)
            if "metacritic" in game_data:
                output["metacritic"] = {
                    "score": game_data["metacritic"].get("score"),
                    "url": game_data["metacritic"].get("url"),
                }
        else:
            output["error"] = "Game not found on Steam Store or Region Locked"
            print(json.dumps(output, indent=2))
            return

    except Exception as e:
        output["error"] = f"Store API Error: {str(e)}"
        # If store fails, we might still want other info, but name is crucial.
        # We continue to try others.

    # 2. Steam Deck
    try:
        sd_client = SteamDeckClient()
        sd_report = sd_client.get_status(app_id_int)
        output["steam_deck"] = {
            "status": sd_report.status,
            "display": sd_report.display_status,
        }
    except Exception as e:
        logger.debug(f"Steam Deck check failed: {e}")

    # 3. ProtonDB
    try:
        pdb_client = ProtonDBClient()
        pdb_report = pdb_client.get_rating(app_id_int)
        output["protondb"] = {
            "tier": pdb_report.tier,
            "score": pdb_report.score,
            "confidence": pdb_report.confidence,
        }
    except Exception as e:
        logger.debug(f"ProtonDB check failed: {e}")

    # 4. Steam Reviews
    try:
        review_url = f"https://store.steampowered.com/appreviews/{app_id}"
        rev_params: dict[str, str | int] = {"json": "1", "language": "all"}
        rev_resp = requests.get(review_url, params=rev_params, timeout=10)
        rev_data = rev_resp.json()

        if "query_summary" in rev_data:
            qs = rev_data["query_summary"]
            output["steam_reviews"] = {
                "summary": qs.get("review_score_desc"),
                "total": qs.get("total_reviews"),
                "positive": qs.get("total_positive"),
                "negative": qs.get("total_negative"),
            }
            # Calculate percent manually
            total = qs.get("total_reviews", 0)
            pos = qs.get("total_positive", 0)
            if total > 0:
                output["steam_reviews"]["percent_positive"] = int((pos / total) * 100)
            else:
                output["steam_reviews"]["percent_positive"] = 0

    except Exception as e:
        logger.debug(f"Review check failed: {e}")

    print(json.dumps(output, indent=2))
