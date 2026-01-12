"""Metacritic scraper for game ratings and recommendations."""

import logging
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MetacriticGame:
    """Game information from Metacritic."""

    name: str
    slug: str
    metascore: int
    user_score: float | None
    platform: str
    release_date: str | None
    url: str


class MetacriticScraper:
    """Scrapes Metacritic for highly-rated PC games."""

    BASE_URL = "https://www.metacritic.com"
    BROWSE_URL = f"{BASE_URL}/browse/game/pc/all/all-time/metascore/"

    # Request headers to avoid blocking
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self):
        """Initialize the scraper."""
        self._cache: list[MetacriticGame] = []

    def fetch_top_rated_games(
        self, min_score: int = 75, limit: int = 500, min_year: int | None = None
    ) -> list[MetacriticGame]:
        """Fetch top-rated PC games from Metacritic.

        Args:
            min_score: Minimum Metascore to include.
            limit: Maximum number of games to fetch.
            min_year: Only include games released in this year or later.

        Returns:
            List of MetacriticGame objects sorted by score.
        """
        # Optimization: If min_year is provided, fetch by specific years
        if min_year:
            import datetime
            current_year = datetime.datetime.now().year
            return self.fetch_games_by_year_range(
                start_year=min_year,
                end_year=current_year,
                min_score=min_score,
                limit=limit
            )

        if self._cache:
            filtered = [g for g in self._cache if g.metascore >= min_score]
            return filtered[:limit]

        return self._fetch_paginated_list(self.BROWSE_URL, min_score, limit)

    def fetch_games_by_year_range(
        self, start_year: int, end_year: int, min_score: int = 75, limit: int = 200
    ) -> list[MetacriticGame]:
        """Fetch top games by iterating through a randomized list of years."""
        all_games: list[MetacriticGame] = []
        
        # Create a list of years and randomize them for more diverse recommendations
        years = list(range(start_year, end_year + 1))
        import random
        random.shuffle(years)
        
        for year in years:
            if len(all_games) >= limit:
                break
                
            logger.info(f"Scraping Metacritic for year: {year}...")
            year_url = f"{self.BASE_URL}/browse/game/pc/all/{year}/metascore/"
            
            # Fetch first page for each year
            year_games = self._fetch_paginated_list(year_url, min_score, limit=50)
            all_games.extend(year_games)
            
            # Rate limiting between years
            if len(all_games) < limit:
                time.sleep(0.5)

        # Shuffle combined results so the final selection isn't just the top of the first year scraped
        random.shuffle(all_games)
        return all_games[:limit]

    def _fetch_paginated_list(self, base_url: str, min_score: int, limit: int) -> list[MetacriticGame]:
        """Internal helper to fetch games from a paginated Metacritic list."""
        games: list[MetacriticGame] = []
        page = 1

        while len(games) < limit:
            try:
                # Append page param correctly
                separator = "&" if "?" in base_url else "?"
                url = f"{base_url}{separator}page={page}"
                
                response = requests.get(
                    url, headers=self.HEADERS, timeout=30.0, allow_redirects=True
                )

                if response.status_code == 404:
                    break

                response.raise_for_status()
                page_games = self._parse_browse_page(response.text)

                if not page_games:
                    break

                found_new = False
                for game in page_games:
                    if game.metascore >= min_score:
                        games.append(game)
                        found_new = True

                # Stop if scores on this page drop below minimum
                if page_games and page_games[-1].metascore < min_score:
                    break
                
                if not found_new:
                    break

                page += 1
                time.sleep(0.3)

            except requests.RequestException as e:
                logger.warning(f"Failed to fetch Metacritic page {page}: {e}")
                break
        
        return games[:limit]

    def _parse_browse_page(self, html: str) -> list[MetacriticGame]:
        """Parse a Metacritic browse page for game entries.

        Args:
            html: Raw HTML content.

        Returns:
            List of MetacriticGame objects.
        """
        soup = BeautifulSoup(html, "html.parser")
        games = []

        # Find game cards - Metacritic uses various class patterns
        # Try multiple selectors for robustness
        game_cards = soup.select(
            ".c-finderProductCard, .clamp-summary-wrap, [data-testid='product-card']"
        )

        for card in game_cards:
            try:
                game = self._parse_game_card(card)
                if game:
                    games.append(game)
            except Exception as e:
                logger.debug(f"Failed to parse game card: {e}")
                continue

        return games

    def _parse_game_card(self, card) -> MetacriticGame | None:
        """Parse a single game card element.

        Args:
            card: BeautifulSoup element for a game card.

        Returns:
            MetacriticGame object or None if parsing fails.
        """
        # Try to find title
        title_elem = card.select_one(
            ".c-finderProductCard_title, .title h3, [data-testid='product-title'], a.title"
        )
        if not title_elem:
            return None

        name = title_elem.get_text(strip=True)
        # Remove ranking prefix like "1." or "65."
        if name and name[0].isdigit():
            name = name.lstrip("0123456789.").strip()

        # Find link/slug
        link_elem = card.select_one("a[href*='/game/']")
        url = ""
        slug = ""
        if link_elem:
            url = link_elem.get("href", "")
            if not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"
            # Extract slug from URL
            slug_match = re.search(r"/game/(?:pc/)?([^/]+)", url)
            if slug_match:
                slug = slug_match.group(1)

        # Find metascore
        score_elem = card.select_one(
            ".c-siteReviewScore span, .metascore_w, [data-testid='critic-score']"
        )
        if not score_elem:
            return None

        try:
            metascore = int(score_elem.get_text(strip=True))
        except ValueError:
            return None

        # Find user score (optional)
        user_score = None
        user_elem = card.select_one(
            ".c-siteReviewScore_user, .user, [data-testid='user-score']"
        )
        if user_elem:
            try:
                user_text = user_elem.get_text(strip=True)
                user_score = float(user_text)
            except ValueError:
                pass

        # Find release date (optional)
        date_elem = card.select_one(".c-finderProductCard_meta, .clamp-details span")
        release_date = date_elem.get_text(strip=True) if date_elem else None

        return MetacriticGame(
            name=name,
            slug=slug,
            metascore=metascore,
            user_score=user_score,
            platform="PC",
            release_date=release_date,
            url=url,
        )

    def search_game(self, name: str) -> MetacriticGame | None:
        """Search for a specific game on Metacritic.

        Args:
            name: Game name to search for.

        Returns:
            MetacriticGame if found, None otherwise.
        """
        search_url = f"{self.BASE_URL}/search/{name.replace(' ', '%20')}/?category=13"

        try:
            response = requests.get(
                search_url, headers=self.HEADERS, timeout=15.0, allow_redirects=True
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find first PC game result
            results = soup.select(".c-pageSiteSearch-results .g-grid-container")
            for result in results:
                platform_elem = result.select_one(".c-tagList")
                if platform_elem and "PC" in platform_elem.get_text():
                    game = self._parse_game_card(result)
                    if game:
                        return game

        except requests.RequestException as e:
            logger.warning(f"Metacritic search failed for '{name}': {e}")

        return None
