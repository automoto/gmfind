"""Aggregate, filter, and enrich deals from Steam."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from gmfind.blocklist_checker import load_block_list
from gmfind.config import Config, PreferencesConfig, load_config
from gmfind.game_check import (
    _load_owned_games,
    fetch_protondb_rating,
    fetch_steam_deck_status,
    fetch_steam_reviews,
    fetch_store_data,
)
from gmfind.recommendations.metacritic import MetacriticScraper

from .steam_specials import SteamDeal

logger = logging.getLogger(__name__)


def _normalize_metacritic_url(url: str | None) -> str | None:
    """Ensure Metacritic URL links to PC version with critic-reviews.

    Args:
        url: Raw Metacritic URL.

    Returns:
        URL with /critic-reviews/ and ?platform=pc appended.
    """
    if not url:
        return url
    # Remove trailing slash for consistent handling
    url = url.rstrip("/")
    # Add /critic-reviews if not present
    if "/critic-reviews" not in url:
        url = f"{url}/critic-reviews/"
    # Add platform=pc parameter
    if "platform=pc" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}platform=pc"
    return url


@dataclass
class AggregatedDeal:
    """Unified deal representation with all metadata."""

    app_id: int
    name: str
    original_price: float
    sale_price: float
    discount_percent: int

    # Game info
    short_description: str | None = None
    genres: list[str] = field(default_factory=list)
    app_type: str = "unknown"
    release_year: int | None = None

    # Review data
    steam_reviews: dict | None = None
    metacritic_score: int | None = None
    metacritic_url: str | None = None
    metacritic_quotes: list[dict] = field(default_factory=list)

    # Compatibility
    steam_deck_status: str | None = None
    steam_deck_display: str | None = None
    protondb_tier: str | None = None
    protondb_score: float | None = None

    # Flags
    requires_3rd_party_account: bool = False
    account_details: str | None = None


class DealsAggregator:
    """Aggregates and filters deals from Steam."""

    def __init__(
        self,
        config_path: str = "config.yaml",
        block_list_path: str = "block_list.yaml",
        inventory_path: str = "inventory_private.csv",
        skip_inventory: bool = False,
    ):
        """Initialize the aggregator.

        Args:
            config_path: Path to config.yaml.
            block_list_path: Path to block_list.yaml.
            inventory_path: Path to inventory CSV.
            skip_inventory: If True, skip inventory check (for public reports).
        """
        self.config_path = config_path
        self.block_list_path = block_list_path
        self.inventory_path = inventory_path
        self.skip_inventory = skip_inventory

        self.config: Config | None = None
        self.prefs: PreferencesConfig | None = None

        try:
            self.config = load_config(config_path, require_credentials=False)
            self.prefs = self.config.preferences
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

        try:
            self.blocked_terms = load_block_list(block_list_path)
        except Exception as e:
            logger.warning(f"Failed to load blocklist: {e}")
            self.blocked_terms = []

        if skip_inventory:
            self.owned_ids: set[int] = set()
        else:
            try:
                self.owned_ids = _load_owned_games(inventory_path)
            except Exception as e:
                logger.warning(f"Failed to load inventory: {e}")
                self.owned_ids = set()

        self.metacritic_client = MetacriticScraper()

    def convert_deals(self, steam_deals: list[SteamDeal]) -> list[AggregatedDeal]:
        """Convert Steam deals to AggregatedDeal format.

        Args:
            steam_deals: Deals from Steam API.

        Returns:
            List of AggregatedDeal objects.
        """
        seen_ids: dict[int, AggregatedDeal] = {}

        for deal in steam_deals:
            if deal.app_id not in seen_ids:
                seen_ids[deal.app_id] = AggregatedDeal(
                    app_id=deal.app_id,
                    name=deal.name,
                    original_price=deal.original_price,
                    sale_price=deal.sale_price,
                    discount_percent=deal.discount_percent,
                )

        logger.info(f"Converted {len(seen_ids)} unique deals")
        return list(seen_ids.values())

    def filter_deals(self, deals: list[AggregatedDeal]) -> list[AggregatedDeal]:
        """Apply config.yaml filters to deals.

        Args:
            deals: List of deals to filter.

        Returns:
            Filtered list of deals.
        """
        filtered = []

        for deal in deals:
            if deal.app_id in self.owned_ids:
                logger.debug(f"Skipping owned game: {deal.name}")
                continue

            if self._is_blocked(deal.name):
                logger.debug(f"Skipping blocked game: {deal.name}")
                continue

            if self.prefs and deal.sale_price > self.prefs.max_price:
                logger.debug(f"Skipping expensive game: {deal.name} (${deal.sale_price})")
                continue

            filtered.append(deal)

        logger.info(f"Filtered to {len(filtered)} deals")
        return filtered

    def enrich_deals(
        self,
        deals: list[AggregatedDeal],
        review_limit: int = 5,
    ) -> list[AggregatedDeal]:
        """Fetch additional data for each deal.

        Args:
            deals: List of deals to enrich.
            review_limit: Number of review quotes to fetch per game.

        Returns:
            List of enriched deals.
        """
        enriched = []

        for i, deal in enumerate(deals):
            logger.info(f"Enriching deal {i + 1}/{len(deals)}: {deal.name}")

            try:
                store_data = fetch_store_data(deal.app_id)
                if "error" not in store_data:
                    deal.app_type = store_data.get("type", "unknown")
                    deal.release_year = store_data.get("release_year")
                    deal.short_description = store_data.get("short_description")
                    deal.requires_3rd_party_account = store_data.get(
                        "requires_3rd_party_account", False
                    )
                    deal.account_details = store_data.get("3rd_party_account_details")

                    if store_data.get("metacritic"):
                        deal.metacritic_score = store_data["metacritic"].get("score")
                        deal.metacritic_url = _normalize_metacritic_url(
                            store_data["metacritic"].get("url")
                        )

                if deal.app_type != "game":
                    logger.debug(f"Skipping non-game: {deal.name} ({deal.app_type})")
                    continue

                if not self._passes_filters(deal):
                    continue

                # Fetch compatibility data before compatibility filtering
                deck_status = fetch_steam_deck_status(deal.app_id)
                if deck_status:
                    deal.steam_deck_status = deck_status.get("status")
                    deal.steam_deck_display = deck_status.get("display")

                proton_data = fetch_protondb_rating(deal.app_id)
                if proton_data:
                    deal.protondb_tier = proton_data.get("tier")
                    deal.protondb_score = proton_data.get("score")

                if not self._passes_compatibility_filters(deal):
                    continue

                steam_reviews = fetch_steam_reviews(deal.app_id)
                if steam_reviews:
                    deal.steam_reviews = steam_reviews

                self._fetch_metacritic_reviews(deal, review_limit)

                enriched.append(deal)

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"Failed to enrich deal {deal.name}: {e}")
                continue

        logger.info(f"Enriched {len(enriched)} deals")
        return enriched

    def _is_blocked(self, name: str) -> bool:
        """Check if a game name matches any blocked terms."""
        name_lower = name.lower()
        for term in self.blocked_terms:
            if term in name_lower:
                return True
        return False

    def _passes_filters(self, deal: AggregatedDeal) -> bool:
        """Check if a deal passes all config filters."""
        if not self.prefs:
            return True

        if deal.metacritic_score is not None:
            if deal.metacritic_score < self.prefs.min_metacritic_score:
                logger.debug(
                    f"Skipping low score: {deal.name} (Metacritic {deal.metacritic_score})"
                )
                return False
        elif self.prefs.require_metacritic_score:
            logger.debug(f"Skipping game without Metacritic score: {deal.name}")
            return False

        if deal.release_year:
            current_year = datetime.now().year
            age = current_year - deal.release_year
            if age > self.prefs.max_game_age_years:
                logger.debug(f"Skipping old game: {deal.name} ({age} years)")
                return False

        return True

    def _passes_compatibility_filters(self, deal: AggregatedDeal) -> bool:
        """Check if a deal passes Steam Deck and ProtonDB compatibility filters."""
        if not self.prefs:
            return True

        # Steam Deck level ranking (higher is better)
        deck_levels = {"verified": 3, "playable": 2, "unsupported": 1, "unknown": 0}
        min_deck_level = self.prefs.min_steam_deck_level.lower()
        min_deck_rank = deck_levels.get(min_deck_level, 0)

        if deal.steam_deck_status:
            deal_deck_rank = deck_levels.get(deal.steam_deck_status.lower(), 0)
            if deal_deck_rank < min_deck_rank:
                logger.debug(
                    f"Skipping incompatible Steam Deck: {deal.name} "
                    f"({deal.steam_deck_status}, need {min_deck_level})"
                )
                return False
        elif min_deck_rank > 0:
            # No Steam Deck status and we require at least some compatibility
            logger.debug(f"Skipping game without Steam Deck status: {deal.name}")
            return False

        # ProtonDB tier ranking (higher is better)
        proton_tiers = {
            "platinum": 5,
            "gold": 4,
            "silver": 3,
            "bronze": 2,
            "borked": 1,
            "unknown": 0,
        }
        min_proton_tier = self.prefs.min_protondb_rating.lower()
        min_proton_rank = proton_tiers.get(min_proton_tier, 0)

        if deal.protondb_tier:
            deal_proton_rank = proton_tiers.get(deal.protondb_tier.lower(), 0)
            if deal_proton_rank < min_proton_rank:
                logger.debug(
                    f"Skipping low ProtonDB rating: {deal.name} "
                    f"({deal.protondb_tier}, need {min_proton_tier})"
                )
                return False
        # Note: We don't require ProtonDB if missing - Steam Deck status is primary

        return True

    def _fetch_metacritic_reviews(self, deal: AggregatedDeal, limit: int):
        """Fetch Metacritic review quotes for a deal."""
        try:
            game, reviews = self.metacritic_client.get_game_with_reviews(
                deal.name, review_limit=limit
            )

            if game:
                if not deal.metacritic_score:
                    deal.metacritic_score = game.metascore
                if not deal.metacritic_url:
                    deal.metacritic_url = _normalize_metacritic_url(game.url)

            for review in reviews:
                deal.metacritic_quotes.append(
                    {
                        "outlet": review.outlet,
                        "score": review.score,
                        "quote": review.quote,
                        "url": review.url,
                    }
                )

        except Exception as e:
            logger.debug(f"Failed to fetch Metacritic reviews for {deal.name}: {e}")

    def get_filtered_enriched_deals(
        self,
        steam_deals: list[SteamDeal],
        limit: int = 10,
        review_limit: int = 5,
    ) -> list[AggregatedDeal]:
        """Full pipeline: convert, filter, and enrich deals.

        Args:
            steam_deals: Deals from Steam API.
            limit: Maximum number of deals to return.
            review_limit: Number of review quotes per game.

        Returns:
            List of filtered and enriched deals.
        """
        all_deals = self.convert_deals(steam_deals)

        all_deals.sort(key=lambda d: d.discount_percent, reverse=True)

        filtered = self.filter_deals(all_deals)

        enriched = self.enrich_deals(filtered[: limit * 2], review_limit)

        enriched.sort(key=lambda d: d.discount_percent, reverse=True)

        return enriched[:limit]
