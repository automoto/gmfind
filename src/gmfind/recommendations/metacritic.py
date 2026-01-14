"""Metacritic scraper for game ratings and recommendations."""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

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


@dataclass
class MetacriticReviewQuote:
    """A critic review quote from Metacritic."""

    outlet: str
    score: int | None
    quote: str
    url: str | None


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

    # -------------------------------------------------------------------------
    # Nuxt.js Review Extraction Patterns
    # -------------------------------------------------------------------------
    # These regex patterns extract review data from Metacritic's embedded
    # JavaScript (window.__NUXT__). The data is stored in JavaScript object
    # notation (NOT valid JSON), making regex the pragmatic choice over
    # adding a JavaScript parser dependency.
    #
    # Example format in the script:
    #   {publicationName:"IGN",score:100,quote:"A masterpiece",url:"https://..."}
    #
    # We extract each field type separately and align them by position.
    # -------------------------------------------------------------------------

    # Matches: publicationName:"IGN" -> captures "IGN"
    _NUXT_PUBLICATION_PATTERN = re.compile(r'publicationName:"([^"]+)"')

    # Matches: score:100 (but not metascore:100) -> captures "100"
    # The negative lookbehind (?<![a-zA-Z]) prevents matching "metascore"
    _NUXT_SCORE_PATTERN = re.compile(r"(?<![a-zA-Z])score:(\d+)")

    # Matches: quote:"A masterpiece..." -> captures the quote text
    _NUXT_QUOTE_PATTERN = re.compile(r'quote:"([^"]+)"')

    # Matches: url:"https://..." -> captures the external review URL
    _NUXT_URL_PATTERN = re.compile(r'url:"(https?://[^"]+)"')

    def __init__(self):
        """Initialize the scraper."""
        self._cache: list[MetacriticGame] = []

    def _extract_slug_from_url(self, url: str) -> str:
        """Extract game slug from a Metacritic URL using urllib.parse.

        Handles URL formats:
        - /game/pc/elden-ring/
        - /game/elden-ring/
        - https://www.metacritic.com/game/pc/elden-ring/

        Args:
            url: A Metacritic game URL.

        Returns:
            The game slug (e.g., 'elden-ring'), or empty string if not found.
        """
        if not url:
            return ""

        path = urlparse(url).path.strip("/")
        parts = path.split("/")

        # URL format: game/[pc/]slug or just the path after /game/
        if "game" not in parts:
            return ""

        game_idx = parts.index("game")
        # Get parts after 'game', skip 'pc' if present
        for part in parts[game_idx + 1 :]:
            if part and part != "pc":
                return part

        return ""

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
                limit=limit,
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

        # Shuffle combined results so the selection isn't just the first year scraped
        random.shuffle(all_games)
        return all_games[:limit]

    def _fetch_paginated_list(
        self, base_url: str, min_score: int, limit: int
    ) -> list[MetacriticGame]:
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
            # Extract slug from URL using path parsing
            slug = self._extract_slug_from_url(url)

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

            # Collect all game results that could be on PC
            candidates: list[MetacriticGame] = []
            results = soup.select(".c-pageSiteSearch-results .g-grid-container")

            for result in results:
                platform_elem = result.select_one('[data-testid="product-platform"]')
                platform_text = platform_elem.get_text() if platform_elem else ""

                # Accept games with PC or multi-platform ("and more")
                if "PC" not in platform_text and "and more" not in platform_text:
                    continue

                game = self._parse_search_result(result)
                if game:
                    candidates.append(game)

            # Find best match by title similarity
            if candidates:
                return self._find_best_title_match(name, candidates)

        except requests.RequestException as e:
            logger.warning(f"Metacritic search failed for '{name}': {e}")

        return None

    def _find_best_title_match(
        self, search_name: str, games: list[MetacriticGame]
    ) -> MetacriticGame | None:
        """Find the best matching game by title similarity.

        Args:
            search_name: The name being searched for.
            games: List of candidate games.

        Returns:
            Best matching game or first game if no good match found.
        """
        if not games:
            return None

        # Normalize search name for comparison
        search_normalized = self._normalize_title(search_name)

        best_match = None
        best_score = 0.0

        for game in games:
            game_normalized = self._normalize_title(game.name)

            # Calculate similarity score
            score = self._title_similarity(search_normalized, game_normalized)

            # Bonus for exact match
            if search_normalized == game_normalized:
                return game

            # Bonus for containing the search term
            if search_normalized in game_normalized or game_normalized in search_normalized:
                score += 0.3

            if score > best_score:
                best_score = score
                best_match = game

        # Return best match if similarity is reasonable, otherwise first result
        return best_match if best_score > 0.4 else games[0]

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        # Lowercase, remove special chars, normalize spaces
        normalized = title.lower()
        # Replace common variations
        normalized = normalized.replace(":", "").replace("-", " ").replace("  ", " ")
        # Convert roman numerals to arabic for consistency
        roman_map = {
            " ii ": " 2 ",
            " iii ": " 3 ",
            " iv ": " 4 ",
            " v ": " 5 ",
            " vi ": " 6 ",
            " vii ": " 7 ",
            " viii ": " 8 ",
            " ix ": " 9 ",
            " x ": " 10 ",
        }
        # Add spaces for end-of-string matching
        normalized = f" {normalized} "
        for roman, arabic in roman_map.items():
            normalized = normalized.replace(roman, arabic)
        normalized = normalized.strip()
        # Remove edition suffixes for better matching
        for suffix in [" edition", " remaster", " definitive", " complete", " goty"]:
            if suffix in normalized:
                normalized = normalized.split(suffix)[0]
        return normalized.strip()

    def _title_similarity(self, a: str, b: str) -> float:
        """Calculate simple word overlap similarity between two titles."""
        words_a = set(a.split())
        words_b = set(b.split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union)

    def _parse_search_result(self, result) -> MetacriticGame | None:
        """Parse a search result element from Metacritic search page.

        Args:
            result: BeautifulSoup element for a search result.

        Returns:
            MetacriticGame object or None if parsing fails.
        """
        try:
            # Get title
            title_elem = result.select_one('[data-testid="product-title"]')
            if not title_elem:
                return None
            name = title_elem.get_text(strip=True)

            # Get URL and slug from the link
            link_elem = result.select_one('a[href*="/game/"]')
            if not link_elem:
                return None

            url = link_elem.get("href", "")
            if not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            # Extract slug from URL using path parsing
            slug = self._extract_slug_from_url(url)

            if not slug:
                return None

            # Get metascore
            score_elem = result.select_one(
                ".c-siteReviewScore span, [data-testid='critic-score'], "
                ".c-siteReviewScore_background"
            )
            metascore = 0
            if score_elem:
                score_text = score_elem.get_text(strip=True)
                try:
                    metascore = int(score_text)
                except ValueError:
                    pass

            # Get release date
            date_elem = result.select_one('[data-testid="product-release-date"]')
            release_date = date_elem.get_text(strip=True) if date_elem else None

            return MetacriticGame(
                name=name,
                slug=slug,
                metascore=metascore,
                user_score=None,
                platform="PC",
                release_date=release_date,
                url=url,
            )

        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse search result: {e}")
            return None

    def get_critic_reviews(self, game_slug: str, limit: int = 5) -> list[MetacriticReviewQuote]:
        """Fetch critic review quotes for a game.

        Args:
            game_slug: The game's URL slug (e.g., "elden-ring").
            limit: Maximum number of reviews to return.

        Returns:
            List of MetacriticReviewQuote objects.
        """
        reviews = []
        reviews_url = f"{self.BASE_URL}/game/{game_slug}/critic-reviews/"

        try:
            response = requests.get(
                reviews_url, headers=self.HEADERS, timeout=15.0, allow_redirects=True
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            reviews = self._parse_critic_reviews(soup, limit)

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch Metacritic reviews for '{game_slug}': {e}")

        return reviews

    def _parse_critic_reviews(self, soup: BeautifulSoup, limit: int) -> list[MetacriticReviewQuote]:
        """Parse critic reviews from a Metacritic reviews page.

        Metacritic uses Nuxt.js with client-side rendering, so reviews are
        embedded in the window.__NUXT__ JavaScript object rather than HTML.

        Args:
            soup: BeautifulSoup object of the reviews page.
            limit: Maximum number of reviews to return.

        Returns:
            List of MetacriticReviewQuote objects.
        """
        reviews: list[MetacriticReviewQuote] = []

        # Extract reviews from embedded Nuxt.js data
        nuxt_reviews = self._extract_nuxt_reviews(soup)
        if nuxt_reviews:
            for review_data in nuxt_reviews[:limit]:
                review = self._parse_nuxt_review(review_data)
                if review and review.quote:
                    reviews.append(review)
            return reviews

        # Fallback: Try legacy CSS selectors for older page versions
        review_cards = soup.select(".c-siteReview, .review_content, [data-testid='critic-review']")

        for card in review_cards:
            if len(reviews) >= limit:
                break

            review = self._parse_review_card(card)
            if review and review.quote:
                reviews.append(review)

        return reviews

    def _extract_nuxt_reviews(self, soup: BeautifulSoup) -> list[dict] | None:
        """Extract review data from embedded Nuxt.js state.

        Metacritic embeds review data in window.__NUXT__ using JavaScript
        object notation (not valid JSON), so we use regex to extract reviews.

        Args:
            soup: BeautifulSoup object of the page.

        Returns:
            List of review dictionaries or None if not found.
        """
        # Find script tags containing __NUXT__
        for script in soup.find_all("script"):
            script_text = script.string or ""
            if "window.__NUXT__" not in script_text:
                continue

            # Extract reviews directly using regex (more reliable than JSON parsing)
            reviews = self._extract_reviews_via_regex(script_text)
            if reviews:
                return reviews

        return None

    def _extract_reviews_via_regex(self, script_text: str) -> list[dict] | None:
        """Extract review data from Nuxt.js embedded JavaScript using regex.

        Metacritic embeds review data in window.__NUXT__ using JavaScript object
        notation (not valid JSON). This method uses regex patterns to extract
        the structured data. See class-level pattern constants for details.

        Args:
            script_text: The raw script content containing __NUXT__ data.

        Returns:
            List of review dictionaries with keys:
            - publicationName: Name of the reviewing outlet
            - score: Numeric score (0-100)
            - quote: Review quote/snippet
            - url: External URL to full review (optional)

            Returns None if no reviews found.
        """
        # Extract each field type using the pre-compiled patterns
        publications = self._NUXT_PUBLICATION_PATTERN.findall(script_text)
        scores = self._NUXT_SCORE_PATTERN.findall(script_text)
        quotes = self._NUXT_QUOTE_PATTERN.findall(script_text)
        urls = self._NUXT_URL_PATTERN.findall(script_text)

        # Match them up - they should appear in order in the data
        # Take the minimum length to avoid misalignment
        count = min(len(publications), len(scores), len(quotes))

        if count == 0:
            logger.debug(
                f"Regex extraction found: {len(publications)} pubs, "
                f"{len(scores)} scores, {len(quotes)} quotes"
            )
            return None

        reviews = []
        for i in range(count):
            try:
                review = {
                    "publicationName": publications[i],
                    "score": int(scores[i]),
                    "quote": quotes[i],
                    "url": urls[i] if i < len(urls) else None,
                }
                reviews.append(review)
            except (IndexError, ValueError) as e:
                logger.debug(f"Failed to construct review {i}: {e}")
                continue

        return reviews if reviews else None

    def _parse_nuxt_review(self, review_data: dict) -> MetacriticReviewQuote | None:
        """Parse a review from Nuxt data structure.

        Args:
            review_data: Dictionary containing review information.

        Returns:
            MetacriticReviewQuote or None.
        """
        try:
            outlet = review_data.get("publicationName") or review_data.get("publication", {}).get(
                "name", "Unknown"
            )
            score = review_data.get("score")
            quote = review_data.get("quote", "")
            url = review_data.get("url") or review_data.get("externalUrl")

            if not quote:
                return None

            return MetacriticReviewQuote(
                outlet=outlet,
                score=int(score) if score is not None else None,
                quote=quote,
                url=url,
            )
        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse Nuxt review: {e}")
            return None

    def _parse_review_card(self, card) -> MetacriticReviewQuote | None:
        """Parse a single review card.

        Args:
            card: BeautifulSoup element for a review card.

        Returns:
            MetacriticReviewQuote or None if parsing fails.
        """
        try:
            # Get outlet name
            outlet_elem = card.select_one(
                ".c-siteReview_publicationName, .source, [data-testid='publication-name']"
            )
            outlet = outlet_elem.get_text(strip=True) if outlet_elem else "Unknown"

            # Get score
            score = None
            score_elem = card.select_one(
                ".c-siteReviewScore span, .metascore_w, [data-testid='critic-score']"
            )
            if score_elem:
                try:
                    score = int(score_elem.get_text(strip=True))
                except ValueError:
                    pass

            # Get review quote/snippet
            quote_elem = card.select_one(
                ".c-siteReview_quote, .review_body, [data-testid='review-quote']"
            )
            quote = quote_elem.get_text(strip=True) if quote_elem else ""

            # Get review URL
            url = None
            link_elem = card.select_one("a[href*='http']")
            if link_elem:
                url = link_elem.get("href")

            if not quote:
                return None

            return MetacriticReviewQuote(
                outlet=outlet,
                score=score,
                quote=quote,
                url=url,
            )

        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse Metacritic review card: {e}")
            return None

    def get_game_with_reviews(
        self, name: str, review_limit: int = 5
    ) -> tuple[MetacriticGame | None, list[MetacriticReviewQuote]]:
        """Search for a game and fetch its critic reviews.

        Args:
            name: Game name to search for.
            review_limit: Maximum number of reviews to return.

        Returns:
            Tuple of (MetacriticGame or None, list of reviews).
        """
        game = self.search_game(name)
        if not game or not game.slug:
            return game, []

        reviews = self.get_critic_reviews(game.slug, review_limit)
        return game, reviews
