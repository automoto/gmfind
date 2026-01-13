"""Client for checking official Steam Deck verification status."""

import logging
from dataclasses import dataclass
from typing import Literal

import requests

logger = logging.getLogger(__name__)

SteamDeckStatus = Literal["verified", "playable", "unsupported", "unknown"]


@dataclass
class SteamDeckReport:
    app_id: int
    status: SteamDeckStatus
    display_status: str
    categories: list[str]  # e.g. "Controller support", "Small text"


class SteamDeckClient:
    """Checks official Steam Deck compatibility via Steam Store API."""

    API_URL = "https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport"

    def get_status(self, app_id: int) -> SteamDeckReport:
        """Fetch the official Steam Deck compatibility report."""
        try:
            response = requests.get(self.API_URL, params={"nAppID": app_id}, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", {})
            resolved_category = results.get("resolved_category", 0)

            # Correct mapping based on Steam API observation:
            # 0: Unknown, 1: Unsupported, 2: Playable, 3: Verified
            status_map: dict[int, SteamDeckStatus] = {
                0: "unknown",
                1: "unsupported",
                2: "playable",
                3: "verified",
            }

            status = status_map.get(resolved_category, "unknown")

            # Extract detailed categories (why it got that rating)
            # display_types = results.get("display_types", [])
            # This is often raw HTML or localized strings in a real API,
            # simplified here as we just want the high-level status for now.

            return SteamDeckReport(
                app_id=app_id,
                status=status,
                display_status=status.upper(),
                categories=[],
            )

        except Exception as e:
            logger.error(f"Failed to check Steam Deck status for {app_id}: {e}")
            return SteamDeckReport(app_id, "unknown", "UNKNOWN", [])
