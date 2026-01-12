"""Fetch discounted games from Steam Store API."""

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class SteamDeal:
    """Represents a Steam game on sale."""

    app_id: int
    name: str
    original_price: float
    sale_price: float
    discount_percent: int


class SteamSpecialsFetcher:
    """Fetches discounted games from Steam Store."""

    FEATURED_URL = "https://store.steampowered.com/api/featuredcategories"
    SEARCH_URL = "https://store.steampowered.com/search/results/"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def fetch_featured_deals(self, limit: int = 100) -> list[SteamDeal]:
        """Fetch deals from Steam Featured Categories API.

        Args:
            limit: Maximum number of deals to return.

        Returns:
            List of SteamDeal objects.
        """
        deals = []

        try:
            response = requests.get(
                self.FEATURED_URL,
                params={"cc": "us", "l": "en"},
                headers=self.HEADERS,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Parse specials section
            specials = data.get("specials", {}).get("items", [])
            for item in specials:
                if not item.get("discounted"):
                    continue

                deal = self._parse_featured_item(item)
                if deal:
                    deals.append(deal)
                    if len(deals) >= limit:
                        break

            logger.info(f"Fetched {len(deals)} deals from Steam Featured API")

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch Steam featured deals: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse Steam featured response: {e}")

        return deals

    def fetch_search_deals(self, limit: int = 100) -> list[SteamDeal]:
        """Fetch deals via Steam search with specials filter.

        Args:
            limit: Maximum number of deals to return.

        Returns:
            List of SteamDeal objects.
        """
        deals: list[SteamDeal] = []
        start = 0
        count = 50

        while len(deals) < limit:
            try:
                response = requests.get(
                    self.SEARCH_URL,
                    params={
                        "query": "",
                        "start": str(start),
                        "count": str(count),
                        "specials": "1",
                        "category1": "998",
                        "cc": "us",
                        "l": "en",
                        "json": "1",
                    },
                    headers=self.HEADERS,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    deal = self._parse_search_item(item)
                    if deal:
                        deals.append(deal)
                        if len(deals) >= limit:
                            break

                # Check if there are more results
                total = data.get("total_count", 0)
                start += count
                if start >= total:
                    break

            except requests.RequestException as e:
                logger.warning(f"Failed to fetch Steam search deals: {e}")
                break
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse Steam search response: {e}")
                break

        logger.info(f"Fetched {len(deals)} deals from Steam Search API")
        return deals

    def fetch_deals(self, limit: int = 100) -> list[SteamDeal]:
        """Fetch deals from both Steam APIs and combine results.

        Args:
            limit: Maximum number of deals to return.

        Returns:
            List of SteamDeal objects, deduplicated by app_id.
        """
        # Fetch from both sources
        featured = self.fetch_featured_deals(limit)
        search = self.fetch_search_deals(limit)

        # Deduplicate by app_id
        seen_ids: set[int] = set()
        combined: list[SteamDeal] = []

        for deal in featured + search:
            if deal.app_id not in seen_ids:
                seen_ids.add(deal.app_id)
                combined.append(deal)
                if len(combined) >= limit:
                    break

        # Sort by discount percentage (highest first)
        combined.sort(key=lambda d: d.discount_percent, reverse=True)

        logger.info(f"Combined {len(combined)} unique deals from Steam")
        return combined[:limit]

    def _parse_featured_item(self, item: dict) -> SteamDeal | None:
        """Parse a featured item from the Steam API.

        Args:
            item: Raw item dict from API response.

        Returns:
            SteamDeal or None if parsing fails.
        """
        try:
            app_id = item.get("id")
            name = item.get("name")
            discount_percent = item.get("discount_percent", 0)

            # Prices are in cents
            original_cents = item.get("original_price", 0)
            final_cents = item.get("final_price", 0)

            if not app_id or not name:
                return None

            return SteamDeal(
                app_id=int(app_id),
                name=name,
                original_price=original_cents / 100.0,
                sale_price=final_cents / 100.0,
                discount_percent=discount_percent,
            )
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to parse featured item: {e}")
            return None

    def _parse_search_item(self, item: dict) -> SteamDeal | None:
        """Parse a search result item from the Steam API.

        Args:
            item: Raw item dict from search response.

        Returns:
            SteamDeal or None if parsing fails.
        """
        try:
            app_id = item.get("id")
            name = item.get("name")

            # Check for discount
            if not item.get("discount_block"):
                return None

            discount_percent = item.get("discount_percent", 0)
            if discount_percent == 0:
                return None

            # Parse prices from formatted strings or raw values
            original_price = 0.0
            sale_price = 0.0

            # Try to get prices from price data
            if "original_price" in item:
                original_price = item["original_price"] / 100.0
            if "final_price" in item:
                sale_price = item["final_price"] / 100.0

            if not app_id or not name:
                return None

            return SteamDeal(
                app_id=int(app_id),
                name=name,
                original_price=original_price,
                sale_price=sale_price,
                discount_percent=abs(discount_percent),
            )
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to parse search item: {e}")
            return None
