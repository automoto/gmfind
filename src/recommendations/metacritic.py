"""Metacritic scraper for game ratings and recommendations."""

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx
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

    async def fetch_top_rated_games(
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
        if self._cache:
            filtered = [g for g in self._cache if g.metascore >= min_score]
            if min_year:
                filtered = [g for g in filtered if self._game_year(g) >= min_year]
            return filtered[:limit]

        games = []
        page = 1

        async with httpx.AsyncClient(headers=self.HEADERS, follow_redirects=True) as client:
            while len(games) < limit:
                try:
                    url = f"{self.BROWSE_URL}?page={page}"
                    response = await client.get(url, timeout=30.0)

                    if response.status_code == 404:
                        break

                    response.raise_for_status()

                    page_games = self._parse_browse_page(response.text)

                    if not page_games:
                        break

                    # Filter by minimum score and year
                    for game in page_games:
                        if game.metascore >= min_score:
                            if min_year and self._game_year(game) < min_year:
                                continue  # Skip old games
                            games.append(game)

                    # Stop if scores drop below minimum
                    if page_games and page_games[-1].metascore < min_score:
                        break

                    page += 1
                    await asyncio.sleep(0.5)  # Rate limiting

                except httpx.HTTPError as e:
                    logger.warning(f"Failed to fetch Metacritic page {page}: {e}")
                    break

        self._cache = games[:limit]
        logger.info(f"Fetched {len(self._cache)} games from Metacritic (min_year={min_year})")
        return self._cache

    def _game_year(self, game: MetacriticGame) -> int:
        """Extract release year from game's release_date string.

        Args:
            game: MetacriticGame object.

        Returns:
            Year as int, or 0 if unable to parse.
        """
        if not game.release_date:
            return 0

        # Try to extract 4-digit year from date string
        match = re.search(r'\b(19|20)\d{2}\b', game.release_date)
        if match:
            return int(match.group())
        return 0

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
        game_cards = soup.select(".c-finderProductCard, .clamp-summary-wrap, [data-testid='product-card']")

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
        user_elem = card.select_one(".c-siteReviewScore_user, .user, [data-testid='user-score']")
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

    async def search_game(self, name: str) -> MetacriticGame | None:
        """Search for a specific game on Metacritic.

        Args:
            name: Game name to search for.

        Returns:
            MetacriticGame if found, None otherwise.
        """
        search_url = f"{self.BASE_URL}/search/{name.replace(' ', '%20')}/?category=13"

        async with httpx.AsyncClient(headers=self.HEADERS, follow_redirects=True) as client:
            try:
                response = await client.get(search_url, timeout=15.0)
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

            except httpx.HTTPError as e:
                logger.warning(f"Metacritic search failed for '{name}': {e}")

        return None
