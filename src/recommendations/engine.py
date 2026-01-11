"""Game recommendation engine combining multiple data sources."""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import yaml

from ..config import PreferencesConfig
from ..inventory import SteamInventory
from .metacritic import MetacriticScraper
from .protondb import ProtonDBClient

logger = logging.getLogger(__name__)

BLOCK_LIST_FILE = Path("block_list.yaml")


@dataclass
class GameRecommendation:
    """A recommended game with all relevant data."""

    app_id: int
    name: str
    price: float
    price_formatted: str
    metascore: int
    protondb_rating: str
    protondb_tier: str
    steam_url: str
    preference_score: float  # How well it matches user preferences
    overall_score: float  # Combined score for ranking


class RecommendationEngine:
    """Engine for generating game recommendations."""

    STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch"
    STEAM_APP_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(
        self,
        inventory: SteamInventory,
        preferences: PreferencesConfig,
    ):
        """Initialize the recommendation engine.

        Args:
            inventory: Steam inventory checker instance.
            preferences: User's preference configuration.
        """
        self.inventory = inventory
        self.preferences = preferences
        self.protondb = ProtonDBClient()
        self.metacritic = MetacriticScraper()
        self._blocked_terms = self._load_block_list()

    def _load_block_list(self) -> list[str]:
        """Load blocked terms from block_list.yaml.

        Returns:
            List of blocked terms (lowercase).
        """
        if not BLOCK_LIST_FILE.exists():
            return []

        try:
            with open(BLOCK_LIST_FILE) as f:
                data = yaml.safe_load(f)

            terms = data.get("blocked_terms", []) if data else []
            # Filter out None/empty and convert to lowercase
            terms = [t.lower().strip() for t in terms if t]
            if terms:
                logger.info(f"Loaded {len(terms)} blocked terms from {BLOCK_LIST_FILE}")
            return terms
        except Exception as e:
            logger.warning(f"Failed to load block list: {e}")
            return []

    def _is_blocked(self, game_name: str) -> bool:
        """Check if a game name matches any blocked term.

        Args:
            game_name: Name of the game to check.

        Returns:
            True if the game should be blocked.
        """
        if not self._blocked_terms:
            return False

        name_lower = game_name.lower()
        for term in self._blocked_terms:
            if term in name_lower:
                return True
        return False

    async def get_recommendations(
        self, limit: int = 10
    ) -> list[GameRecommendation]:
        """Get game recommendations based on user preferences.

        Args:
            limit: Maximum number of recommendations to return.

        Returns:
            List of GameRecommendation objects, sorted by overall score.
        """
        logger.info("Fetching game recommendations...")

        # Step 1: Get owned games and analyze preferences
        owned_ids = await self.inventory.get_owned_app_ids()
        user_tags = await self.inventory.analyze_preferences()

        logger.info(f"User owns {len(owned_ids)} games")
        logger.info(f"Top preferences: {list(user_tags.keys())[:5]}")

        # Step 2: Get highly rated games from Metacritic (within configured age limit)
        min_year = datetime.now().year - self.preferences.max_game_age_years
        metacritic_games = await self.metacritic.fetch_top_rated_games(
            min_score=self.preferences.min_metacritic_score,
            limit=500,
            min_year=min_year,
        )
        logger.info(f"Filtering to games from {min_year} or later ({self.preferences.max_game_age_years} year limit)")

        logger.info(f"Found {len(metacritic_games)} games meeting Metacritic threshold")

        # Step 3: Find Steam app IDs and filter
        recommendations = []

        # Track filter stats
        filter_stats = {
            "blocked": 0,
            "not_on_steam": 0,
            "already_owned": 0,
            "free_game": 0,
            "too_expensive": 0,
            "mod_or_dlc": 0,
            "third_party_account": 0,
            "deck_unsupported": 0,
            "protondb_low": 0,
            "passed": 0,
        }

        for mc_game in metacritic_games:
            if len(recommendations) >= limit * 3:  # Get extra for filtering
                break

            # Early block list check on Metacritic name
            if self._is_blocked(mc_game.name):
                logger.debug(f"Skipping {mc_game.name} - matches block list")
                filter_stats["blocked"] += 1
                continue

            # Search for game on Steam
            steam_data = await self._find_steam_game(mc_game.name)
            if not steam_data:
                filter_stats["not_on_steam"] += 1
                continue

            app_id = steam_data["app_id"]

            # Check block list
            if self._is_blocked(steam_data["name"]):
                logger.debug(f"Skipping {steam_data['name']} - matches block list")
                filter_stats["blocked"] += 1
                continue

            # Skip if already owned
            if app_id in owned_ids:
                logger.debug(f"Skipping {mc_game.name} - already owned")
                filter_stats["already_owned"] += 1
                continue

            # Skip free games (no free-to-play or mods)
            if steam_data["price"] <= 0:
                logger.debug(f"Skipping {mc_game.name} - free game/mod")
                filter_stats["free_game"] += 1
                continue

            # Check price
            if steam_data["price"] > self.preferences.max_price:
                logger.debug(f"Skipping {mc_game.name} - price ${steam_data['price']:.2f} exceeds limit")
                filter_stats["too_expensive"] += 1
                continue

            # Skip if it looks like a mod or DLC (basic heuristic)
            name_lower = steam_data["name"].lower()
            if any(x in name_lower for x in ["mod", "dlc", "soundtrack", "artbook", "skin pack"]):
                logger.debug(f"Skipping {mc_game.name} - appears to be mod/DLC")
                filter_stats["mod_or_dlc"] += 1
                continue

            # Skip games requiring 3rd party accounts
            if steam_data.get("requires_3rd_party"):
                logger.debug(f"Skipping {steam_data['name']} - requires 3rd party account: {steam_data.get('third_party_notice', '')[:50]}")
                filter_stats["third_party_account"] += 1
                continue

            # Check Steam Deck compatibility (from Steam's own verification)
            deck_status = await self._get_steam_deck_status(app_id)
            if deck_status == "unsupported":
                logger.debug(f"Skipping {steam_data['name']} - Steam Deck unsupported")
                filter_stats["deck_unsupported"] += 1
                continue

            # Check ProtonDB rating
            protondb_report = await self.protondb.get_rating(app_id)
            if not self.protondb.meets_minimum_rating(
                protondb_report, self.preferences.min_protondb_rating
            ):
                logger.debug(f"Skipping {mc_game.name} - ProtonDB rating '{protondb_report.tier}' below threshold")
                filter_stats["protondb_low"] += 1
                continue

            filter_stats["passed"] += 1

            # Calculate preference match score
            game_tags = steam_data.get("tags", [])
            pref_score = self._calculate_preference_score(game_tags, user_tags)

            # Calculate overall score (weighted combination)
            overall_score = (
                (mc_game.metascore / 100) * 0.4  # Metacritic weight
                + protondb_report.score * 0.3  # ProtonDB weight
                + pref_score * 0.3  # Preference match weight
            )

            recommendation = GameRecommendation(
                app_id=app_id,
                name=steam_data["name"],
                price=steam_data["price"],
                price_formatted=steam_data["price_formatted"],
                metascore=mc_game.metascore,
                protondb_rating=protondb_report.tier,
                protondb_tier=protondb_report.tier,
                steam_url=f"https://store.steampowered.com/app/{app_id}",
                preference_score=pref_score,
                overall_score=overall_score,
            )
            recommendations.append(recommendation)

            # Rate limiting
            await asyncio.sleep(0.5)

        # Log filter statistics
        logger.info(f"Filter results: {filter_stats['passed']} passed, "
                    f"{filter_stats['too_expensive']} too expensive, "
                    f"{filter_stats['not_on_steam']} not on Steam, "
                    f"{filter_stats['blocked']} blocked, "
                    f"{filter_stats['already_owned']} owned, "
                    f"{filter_stats['free_game']} free, "
                    f"{filter_stats['third_party_account']} 3rd party account, "
                    f"{filter_stats['deck_unsupported']} Deck unsupported, "
                    f"{filter_stats['protondb_low']} ProtonDB low")

        # Shuffle and return random selection from qualifying games
        if recommendations:
            random.shuffle(recommendations)
            logger.info(f"Found {len(recommendations)} qualifying games, selecting randomly")
        return recommendations[:limit]

    async def _get_steam_deck_status(self, app_id: int) -> str:
        """Get Steam Deck compatibility status from Steam.

        Args:
            app_id: Steam app ID.

        Returns:
            Status string: "verified", "playable", "unsupported", or "unknown".
        """
        # Steam Deck compatibility API
        url = f"https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?nAppID={app_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                # Steam returns category: 1=unknown, 2=unsupported, 3=playable, 4=verified
                results = data.get("results", {})
                resolved_category = results.get("resolved_category", 1)

                status_map = {
                    1: "unknown",
                    2: "unsupported",
                    3: "playable",
                    4: "verified",
                }
                status = status_map.get(resolved_category, "unknown")
                logger.debug(f"Steam Deck status for {app_id}: {status}")
                return status

            except Exception as e:
                logger.debug(f"Failed to get Steam Deck status for {app_id}: {e}")
                return "unknown"

    async def _find_steam_game(self, name: str) -> dict | None:
        """Find a game on Steam by name and get its details.

        Args:
            name: Game name to search for.

        Returns:
            Dictionary with app_id, name, price, tags, or None if not found.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Search Steam store
                response = await client.get(
                    self.STEAM_SEARCH_URL,
                    params={"term": name, "cc": "us", "l": "en"},
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                if not items:
                    return None

                # Find best match - be strict about name matching
                app_id = None
                search_name = name.lower().strip()
                # Remove common prefixes like "1." or "65." from Metacritic numbering
                if search_name and search_name[0].isdigit():
                    search_name = search_name.lstrip("0123456789.").strip()

                for item in items:
                    item_name = item.get("name", "").lower().strip()

                    # Require substantial match - not just a number
                    if item_name == search_name:
                        app_id = item.get("id")
                        break
                    # Check if search name is contained in item name (but not just numbers)
                    if len(search_name) > 3 and search_name in item_name:
                        app_id = item.get("id")
                        break
                    # Check if item name is contained in search name
                    if len(item_name) > 3 and item_name in search_name:
                        app_id = item.get("id")
                        break

                if not app_id:
                    # No good match found - skip this game rather than use wrong one
                    logger.debug(f"No good Steam match for '{name}'")
                    return None

                # Get detailed app info
                details_response = await client.get(
                    self.STEAM_APP_URL,
                    params={"appids": app_id, "cc": "us", "l": "en"},
                    timeout=15.0,
                )
                details_response.raise_for_status()
                details_data = details_response.json()

                app_data = details_data.get(str(app_id), {})
                if not app_data.get("success"):
                    return None

                game_data = app_data.get("data", {})

                # Extract price
                price = 0.0
                price_formatted = "Free"
                if game_data.get("is_free"):
                    price = 0.0
                elif "price_overview" in game_data:
                    price_info = game_data["price_overview"]
                    # Use final price (accounts for discounts)
                    price = price_info.get("final", 0) / 100
                    price_formatted = price_info.get("final_formatted", f"${price:.2f}")

                # Extract tags/genres
                tags = []
                for genre in game_data.get("genres", []):
                    tags.append(genre.get("description", ""))
                for cat in game_data.get("categories", []):
                    tags.append(cat.get("description", ""))

                # Check for 3rd party account requirements
                requires_3rd_party = False
                third_party_notice = ""

                # Check ext_user_account_notice (e.g., "Requires 3rd-Party Account: Xbox Live")
                if game_data.get("ext_user_account_notice"):
                    requires_3rd_party = True
                    third_party_notice = game_data["ext_user_account_notice"]

                # Check drm_notice field
                if game_data.get("drm_notice"):
                    drm = game_data["drm_notice"].lower()
                    if "account" in drm or "login" in drm or "requires" in drm:
                        requires_3rd_party = True
                        third_party_notice = game_data["drm_notice"]

                # Check legal_notice for account requirements
                if game_data.get("legal_notice"):
                    legal = game_data["legal_notice"].lower()
                    if "requires" in legal and "account" in legal:
                        requires_3rd_party = True
                        third_party_notice = game_data["legal_notice"][:100]

                return {
                    "app_id": app_id,
                    "name": game_data.get("name", name),
                    "price": price,
                    "price_formatted": price_formatted,
                    "tags": [t for t in tags if t],
                    "requires_3rd_party": requires_3rd_party,
                    "third_party_notice": third_party_notice,
                }

            except httpx.HTTPError as e:
                logger.warning(f"Failed to find Steam game '{name}': {e}")
                return None

    def _calculate_preference_score(
        self, game_tags: list[str], user_tags: dict[str, int]
    ) -> float:
        """Calculate how well a game matches user preferences.

        Args:
            game_tags: Tags/genres of the game.
            user_tags: User's tag preferences with frequency counts.

        Returns:
            Score from 0.0 to 1.0.
        """
        if not user_tags or not game_tags:
            return 0.5  # Neutral score if no data

        total_weight = sum(user_tags.values())
        if total_weight == 0:
            return 0.5

        match_weight = 0
        for tag in game_tags:
            tag_lower = tag.lower()
            for user_tag, count in user_tags.items():
                if tag_lower == user_tag.lower() or tag_lower in user_tag.lower():
                    match_weight += count
                    break

        return min(match_weight / total_weight, 1.0)

    async def get_best_recommendation(self) -> GameRecommendation | None:
        """Get the single best game recommendation.

        Returns:
            The highest-scored GameRecommendation or None if no suitable games found.
        """
        recommendations = await self.get_recommendations(limit=1)
        return recommendations[0] if recommendations else None
