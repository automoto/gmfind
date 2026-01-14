"""Module to aggregate game data into structured JSON."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from gmfind.blocklist_checker import load_block_list
from gmfind.config import load_config
from gmfind.recommendations.protondb import ProtonDBClient
from gmfind.recommendations.steam_deck import SteamDeckClient

logger = logging.getLogger(__name__)


def _load_owned_games(csv_path: str) -> set[int]:
    """Load owned game App IDs from a CSV file.

    Expects CSV to have a header with 'steam_id'.
    """
    owned_ids: set[int] = set()
    path = Path(csv_path)
    if not path.exists():
        logger.debug(f"Inventory file not found: {path}")
        return owned_ids

    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "steam_id" in row and row["steam_id"]:
                    try:
                        owned_ids.add(int(row["steam_id"]))
                    except ValueError:
                        continue
    except Exception as e:
        logger.error(f"Failed to load inventory: {e}")

    return owned_ids


def fetch_store_data(app_id: int) -> dict[str, Any]:
    """Fetch core game data from Steam Store API."""
    try:
        url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": str(app_id), "cc": "us", "l": "en"}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if not data or not data.get(str(app_id), {}).get("success"):
            return {"error": "Game not found or Region Locked"}

        game_data = data[str(app_id)]["data"]
        result = {
            "name": game_data.get("name"),
            "type": game_data.get("type", "unknown"),
            "short_description": game_data.get("short_description", ""),
            "price_str": "Not Available",
            "price_val": None,
            "metacritic": None,
            "metacritic_score": None,
            "release_year": None,
            "requires_3rd_party_account": False,
            "3rd_party_account_details": None,
        }

        # 3rd-party account check
        drm_notice = game_data.get("drm_notice", "")
        if "Requires 3rd-Party Account" in drm_notice or "Requires account from" in drm_notice:
            result["requires_3rd_party_account"] = True
            result["3rd_party_account_details"] = drm_notice

        ext_notice = game_data.get("ext_user_account_notice", "")
        if ext_notice:
            result["requires_3rd_party_account"] = True
            result["3rd_party_account_details"] = ext_notice

        # Price parsing
        if game_data.get("is_free"):
            result["price_str"] = "Free"
            result["price_val"] = 0.0
        elif "price_overview" in game_data:
            result["price_str"] = game_data["price_overview"]["final_formatted"]
            result["price_val"] = game_data["price_overview"]["final"] / 100.0

        # Metacritic parsing
        if "metacritic" in game_data:
            result["metacritic"] = {
                "score": game_data["metacritic"].get("score"),
                "url": game_data["metacritic"].get("url"),
            }
            result["metacritic_score"] = game_data["metacritic"].get("score")

        # Release Date parsing
        release_date = game_data.get("release_date", {})
        date_str = release_date.get("date")
        if date_str:
            try:
                if len(date_str) >= 4:
                    result["release_year"] = int(date_str.split(",")[-1].strip()[:4])
            except (ValueError, IndexError):
                logger.debug(f"Failed to parse release year from: {date_str}")

        return result

    except Exception as e:
        return {"error": f"Store API Error: {str(e)}"}


def fetch_steam_deck_status(app_id: int) -> dict[str, Any] | None:
    """Fetch Steam Deck verification status."""
    try:
        report = SteamDeckClient().get_status(app_id)
        return {
            "status": report.status,
            "display": report.display_status,
        }
    except Exception as e:
        logger.debug(f"Steam Deck check failed: {e}")
        return None


def fetch_protondb_rating(app_id: int) -> dict[str, Any] | None:
    """Fetch ProtonDB rating."""
    try:
        report = ProtonDBClient().get_rating(app_id)
        return {
            "tier": report.tier,
            "score": report.score,
            "confidence": report.confidence,
        }
    except Exception as e:
        logger.debug(f"ProtonDB check failed: {e}")
        return None


def fetch_steam_reviews(app_id: int) -> dict[str, Any] | None:
    """Fetch Steam user reviews summary."""
    try:
        url = f"https://store.steampowered.com/appreviews/{app_id}"
        params = {"json": "1", "language": "all"}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if "query_summary" not in data:
            return None

        qs = data["query_summary"]
        total = qs.get("total_reviews", 0)
        pos = qs.get("total_positive", 0)
        percent = int((pos / total) * 100) if total > 0 else 0

        return {
            "summary": qs.get("review_score_desc"),
            "total": total,
            "positive": pos,
            "negative": qs.get("total_negative"),
            "percent_positive": percent,
        }
    except Exception as e:
        logger.debug(f"Review check failed: {e}")
        return None


def check_recommendation(
    game_data: dict[str, Any],
    config_path: str | None,
    block_list_path: str | None,
    owned_games: set[int] | None = None,
) -> dict[str, Any] | None:
    """Determine if the game is recommended based on config, blocklist and inventory."""
    if not config_path and not block_list_path and not owned_games:
        return None

    is_recommended = True
    reasons = []

    # Check Inventory
    if owned_games and game_data["app_id"] in owned_games:
        is_recommended = False
        reasons.append("Game is already owned")

    # Check App Type (Exclude DLC, etc.)
    if game_data.get("type") != "game":
        is_recommended = False
        reasons.append(f"App type is {game_data.get('type')}, not 'game'")

    # Check Blocklist
    if block_list_path and is_recommended:
        name = game_data.get("name")
        if name:
            blocked_terms = load_block_list(block_list_path)
            name_lower = name.lower()
            for term in blocked_terms:
                if term in name_lower:
                    is_recommended = False
                    reasons.append(f"Blocked term: {term}")
                    break

    # Check Config Criteria
    if config_path and is_recommended:
        try:
            config = load_config(config_path, require_credentials=False)
            prefs = config.preferences

            # Price Check
            price = game_data.get("_price_val")
            if price is not None:
                if price == 0:
                    is_recommended = False
                    reasons.append("Game is free (auto-buy skips free games)")
                elif price > prefs.max_price:
                    is_recommended = False
                    reasons.append(f"Price ${price} > ${prefs.max_price}")

            # Metacritic Check
            meta_score = game_data.get("_metacritic_score")
            if meta_score is not None:
                if meta_score < prefs.min_metacritic_score:
                    is_recommended = False
                    reasons.append(f"Metacritic {meta_score} < {prefs.min_metacritic_score}")
            elif prefs.require_metacritic_score:
                # No score available and score is required
                is_recommended = False
                reasons.append("No Metacritic score available (required by config)")

            # Age Check
            release_year = game_data.get("release_year")
            if release_year:
                current_year = datetime.now().year
                age = current_year - release_year
                if age > prefs.max_game_age_years:
                    is_recommended = False
                    reasons.append(f"Game age {age} years > {prefs.max_game_age_years}")

            # ProtonDB Check
            proton = game_data.get("protondb")
            if proton:
                tier = proton.get("tier")
                if tier and not prefs.meets_protondb_rating(tier):
                    is_recommended = False
                    reasons.append(f"ProtonDB {tier} < {prefs.min_protondb_rating}")

            # Steam Deck Check
            deck = game_data.get("steam_deck")
            if deck:
                status = deck.get("status")
                if status and not prefs.meets_steam_deck_level(status):
                    is_recommended = False
                    reasons.append(f"Steam Deck {status} < {prefs.min_steam_deck_level}")

            # 3rd Party Account Check
            if game_data.get("requires_3rd_party_account"):
                is_recommended = False
                reasons.append(
                    f"Requires 3rd-party account: {game_data.get('3rd_party_account_details')}"
                )

        except Exception as e:
            logger.error(f"Config check failed: {e}")

    result: dict[str, Any] = {"recommended": is_recommended}
    if not is_recommended:
        result["reasons"] = reasons
    return result


def check_game_data(
    app_id: str,
    config_path: str | None = None,
    block_list_path: str | None = None,
    inventory_path: str | None = None,
) -> dict[str, Any]:
    """Fetch structured game data for validation.

    Returns a dictionary with game info and validation status:
    - owned: bool - whether game is in inventory
    - blocked: bool - whether game matches blocklist
    - blocked_term: str | None - the matching blocklist term
    - meets_criteria: bool - whether game meets config preferences
    - fail_reasons: list[str] - reasons for failing criteria
    """
    try:
        app_id_int = int(app_id)
    except ValueError:
        return {"error": "Invalid App ID. Must be an integer."}

    # 1. Store Data
    store_info = fetch_store_data(app_id_int)
    if "error" in store_info:
        return store_info

    output: dict[str, Any] = {
        "app_id": app_id_int,
        "name": store_info.get("name"),
        "type": store_info.get("type"),
        "release_year": store_info.get("release_year"),
        "price": store_info.get("price_str"),
        "price_val": store_info.get("price_val"),
        "steam_deck": fetch_steam_deck_status(app_id_int),
        "protondb": fetch_protondb_rating(app_id_int),
        "metacritic": store_info.get("metacritic"),
        "metacritic_score": store_info.get("metacritic_score"),
        "steam_reviews": fetch_steam_reviews(app_id_int),
        "requires_3rd_party_account": store_info.get("requires_3rd_party_account"),
        "3rd_party_account_details": store_info.get("3rd_party_account_details"),
        # Validation fields
        "owned": False,
        "blocked": False,
        "blocked_term": None,
        "meets_criteria": True,
        "fail_reasons": [],
    }

    # 2. Check Inventory
    if inventory_path:
        owned_games = _load_owned_games(inventory_path)
        if app_id_int in owned_games:
            output["owned"] = True
            output["meets_criteria"] = False
            output["fail_reasons"].append("Game is already owned")

    # 3. Check Blocklist
    if block_list_path and output.get("name"):
        blocked_terms = load_block_list(block_list_path)
        name_lower = output["name"].lower()
        for term in blocked_terms:
            if term in name_lower:
                output["blocked"] = True
                output["blocked_term"] = term
                output["meets_criteria"] = False
                output["fail_reasons"].append(f"Blocked term: {term}")
                break

    # 4. Check App Type (Exclude DLC, etc.)
    if output.get("type") != "game":
        output["meets_criteria"] = False
        output["fail_reasons"].append(f"App type is '{output.get('type')}', not 'game'")

    # 5. Check Config Criteria
    if config_path:
        try:
            config = load_config(config_path, require_credentials=False)
            prefs = config.preferences

            # Price Check
            price = output.get("price_val")
            if price is not None:
                if price == 0:
                    output["meets_criteria"] = False
                    output["fail_reasons"].append("Game is free (we skip free games)")
                elif price > prefs.max_price:
                    output["meets_criteria"] = False
                    output["fail_reasons"].append(f"Price ${price:.2f} > ${prefs.max_price:.2f}")

            # Metacritic Check
            meta_score = output.get("metacritic_score")
            if meta_score is not None:
                if meta_score < prefs.min_metacritic_score:
                    output["meets_criteria"] = False
                    output["fail_reasons"].append(
                        f"Metacritic {meta_score} < {prefs.min_metacritic_score}"
                    )
            elif prefs.require_metacritic_score:
                output["meets_criteria"] = False
                output["fail_reasons"].append("No Metacritic score available (required by config)")

            # Age Check
            release_year = output.get("release_year")
            if release_year:
                current_year = datetime.now().year
                age = current_year - release_year
                if age > prefs.max_game_age_years:
                    output["meets_criteria"] = False
                    output["fail_reasons"].append(
                        f"Game age {age} years > {prefs.max_game_age_years}"
                    )

            # ProtonDB Check
            proton = output.get("protondb")
            if proton:
                tier = proton.get("tier")
                if tier and not prefs.meets_protondb_rating(tier):
                    output["meets_criteria"] = False
                    output["fail_reasons"].append(
                        f"ProtonDB '{tier}' < '{prefs.min_protondb_rating}'"
                    )

            # Steam Deck Check
            deck = output.get("steam_deck")
            if deck:
                status = deck.get("status")
                if status and not prefs.meets_steam_deck_level(status):
                    output["meets_criteria"] = False
                    output["fail_reasons"].append(
                        f"Steam Deck '{status}' < '{prefs.min_steam_deck_level}'"
                    )

            # 3rd Party Account Check
            if output.get("requires_3rd_party_account"):
                output["meets_criteria"] = False
                output["fail_reasons"].append(
                    f"Requires 3rd-party account: {output.get('3rd_party_account_details')}"
                )

        except Exception as e:
            logger.debug(f"Config not available, skipping preference checks: {e}")

    return output


def check_game(
    app_id: str,
    config_path: str | None = None,
    block_list_path: str | None = None,
    inventory_path: str | None = None,
):
    """Fetch and print structured JSON data for a game."""
    data = check_game_data(app_id, config_path, block_list_path, inventory_path)

    # Format output for display (remove internal fields)
    output = {
        "app_id": data.get("app_id"),
        "name": data.get("name"),
        "type": data.get("type"),
        "release_year": data.get("release_year"),
        "price": data.get("price"),
        "steam_deck": data.get("steam_deck"),
        "protondb": data.get("protondb"),
        "metacritic": data.get("metacritic"),
        "steam_reviews": data.get("steam_reviews"),
        "requires_3rd_party_account": data.get("requires_3rd_party_account"),
    }

    # Always add recommendation status
    output["recommended"] = data.get("meets_criteria", True)
    if not output["recommended"]:
        output["reasons"] = data.get("fail_reasons", [])

    print(json.dumps(output, indent=2))
