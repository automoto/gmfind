"""ProtonDB API client for Steam Deck compatibility ratings."""

import logging
from dataclasses import dataclass
from typing import Literal

import requests

logger = logging.getLogger(__name__)


ProtonDBTier = Literal["platinum", "gold", "silver", "bronze", "borked", "pending", "unknown"]


@dataclass
class ProtonDBReport:
    """ProtonDB compatibility report for a game."""

    app_id: int
    tier: ProtonDBTier
    confidence: str  # "good", "adequate", "low"
    score: float  # 0.0 to 1.0
    trend: str  # "stable", "declining", "improving"


class ProtonDBClient:
    """Client for fetching ProtonDB Steam Deck compatibility ratings."""

    API_URL = "https://www.protondb.com/api/v1/reports/summaries"

    # Tier to numeric score for comparison
    TIER_SCORES = {
        "platinum": 1.0,
        "gold": 0.8,
        "silver": 0.6,
        "bronze": 0.4,
        "borked": 0.2,
        "pending": 0.0,
        "unknown": 0.0,
    }

    def __init__(self):
        """Initialize the ProtonDB client."""
        self._cache: dict[int, ProtonDBReport] = {}

    def get_rating(self, app_id: int) -> ProtonDBReport:
        """Get the ProtonDB rating for a Steam game.

        Args:
            app_id: The Steam app ID.

        Returns:
            ProtonDBReport with compatibility information.
        """
        if app_id in self._cache:
            return self._cache[app_id]

        url = f"{self.API_URL}/{app_id}.json"

        try:
            response = requests.get(url, timeout=10.0)

            if response.status_code == 404:
                # No reports for this game
                report = ProtonDBReport(
                    app_id=app_id,
                    tier="unknown",
                    confidence="low",
                    score=0.0,
                    trend="stable",
                )
                self._cache[app_id] = report
                return report

            response.raise_for_status()
            data = response.json()

            tier = data.get("tier", "unknown").lower()
            if tier not in self.TIER_SCORES:
                tier = "unknown"

            report = ProtonDBReport(
                app_id=app_id,
                tier=tier,
                confidence=data.get("confidence", "low"),
                score=self.TIER_SCORES.get(tier, 0.0),
                trend=data.get("trend", "stable"),
            )

            self._cache[app_id] = report
            return report

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch ProtonDB rating for {app_id}: {e}")
            return ProtonDBReport(
                app_id=app_id,
                tier="unknown",
                confidence="low",
                score=0.0,
                trend="stable",
            )

    def get_ratings_batch(self, app_ids: list[int]) -> dict[int, ProtonDBReport]:
        """Get ProtonDB ratings for multiple games.

        Args:
            app_ids: List of Steam app IDs.

        Returns:
            Dictionary mapping app IDs to their reports.
        """
        results = {}
        for app_id in app_ids:
            results[app_id] = self.get_rating(app_id)
        return results

    def meets_minimum_rating(self, report: ProtonDBReport, min_rating: str) -> bool:
        """Check if a report meets the minimum rating requirement.

        Args:
            report: The ProtonDB report to check.
            min_rating: Minimum required rating (platinum, gold, silver, bronze, borked).

        Returns:
            True if the game meets or exceeds the minimum rating.
        """
        min_score = self.TIER_SCORES.get(min_rating.lower(), 0.0)
        return report.score >= min_score
