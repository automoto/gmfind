"""Steam inventory checker - fetches user's owned games."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OwnedGame:
    """Represents a game owned by the user."""

    app_id: int
    name: str
    playtime_minutes: int


class SteamInventoryError(Exception):
    """Raised when there's an error fetching Steam inventory."""

    pass


class SteamInventory:
    """Fetches and manages Steam user inventory data."""

    OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    STORE_API_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(self, steam_id: str):
        """Initialize the inventory checker.

        Args:
            steam_id: The user's 64-bit Steam ID.
        """
        self.steam_id = steam_id
        self._owned_games: list[OwnedGame] | None = None
        self._owned_app_ids: set[int] | None = None

    async def fetch_owned_games(self) -> list[OwnedGame]:
        """Fetch the list of games owned by the user.

        Uses the public Steam API endpoint that doesn't require an API key
        if the user's game list is set to public.

        Returns:
            List of owned games.

        Raises:
            SteamInventoryError: If the request fails or profile is private.
        """
        if self._owned_games is not None:
            return self._owned_games

        # Use the public endpoint via Steam's community data
        url = f"https://steamcommunity.com/profiles/{self.steam_id}/games/?tab=all&xml=1"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise SteamInventoryError(f"Failed to fetch owned games: {e}") from e

            # Check if redirected to login (profile is private)
            if "/login/" in str(response.url):
                raise SteamInventoryError(
                    "Steam profile game library is private. "
                    "Please set your game details to public in Steam privacy settings."
                )

            # Parse XML response
            content = response.text

            if "This profile is private" in content:
                raise SteamInventoryError(
                    "Steam profile is private. Please set your game library to public."
                )

            games = self._parse_games_xml(content)
            self._owned_games = games
            self._owned_app_ids = {g.app_id for g in games}

            logger.info(f"Fetched {len(games)} owned games from Steam")
            return games

    def _parse_games_xml(self, xml_content: str) -> list[OwnedGame]:
        """Parse the games XML response from Steam.

        Args:
            xml_content: Raw XML string from Steam.

        Returns:
            List of OwnedGame objects.
        """
        import re

        games = []

        # Extract game entries using regex (avoiding heavy XML parsing deps)
        game_pattern = re.compile(
            r"<game>.*?<appID>(\d+)</appID>.*?<name><!\[CDATA\[(.*?)\]\]></name>.*?"
            r"<hoursOnRecord>([\d.]+)</hoursOnRecord>.*?</game>",
            re.DOTALL,
        )

        # Also match games with no playtime
        game_pattern_no_hours = re.compile(
            r"<game>.*?<appID>(\d+)</appID>.*?<name><!\[CDATA\[(.*?)\]\]></name>.*?</game>",
            re.DOTALL,
        )

        for match in game_pattern.finditer(xml_content):
            app_id = int(match.group(1))
            name = match.group(2)
            hours = float(match.group(3))
            games.append(
                OwnedGame(app_id=app_id, name=name, playtime_minutes=int(hours * 60))
            )

        # Get games without hours that weren't already matched
        matched_ids = {g.app_id for g in games}
        for match in game_pattern_no_hours.finditer(xml_content):
            app_id = int(match.group(1))
            if app_id not in matched_ids:
                name = match.group(2)
                games.append(OwnedGame(app_id=app_id, name=name, playtime_minutes=0))

        return games

    async def get_owned_app_ids(self) -> set[int]:
        """Get the set of app IDs owned by the user.

        Returns:
            Set of owned app IDs.
        """
        if self._owned_app_ids is None:
            await self.fetch_owned_games()
        return self._owned_app_ids or set()

    def is_owned(self, app_id: int) -> bool:
        """Check if a game is already owned.

        Args:
            app_id: The Steam app ID to check.

        Returns:
            True if owned, False otherwise.

        Raises:
            RuntimeError: If owned games haven't been fetched yet.
        """
        if self._owned_app_ids is None:
            raise RuntimeError("Call fetch_owned_games() first")
        return app_id in self._owned_app_ids

    async def get_game_tags(self, app_id: int) -> list[str]:
        """Fetch tags/genres for a specific game from Steam store.

        Args:
            app_id: The Steam app ID.

        Returns:
            List of tag/genre strings.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.STORE_API_URL,
                    params={"appids": app_id, "cc": "us", "l": "en"},
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

                app_data = data.get(str(app_id), {})
                if not app_data.get("success"):
                    return []

                game_data = app_data.get("data", {})
                tags = []

                # Get genres
                for genre in game_data.get("genres", []):
                    tags.append(genre.get("description", ""))

                # Get categories
                for cat in game_data.get("categories", []):
                    tags.append(cat.get("description", ""))

                return [t for t in tags if t]

            except (httpx.HTTPError, KeyError):
                logger.warning(f"Failed to fetch tags for app {app_id}")
                return []

    async def analyze_preferences(self) -> dict[str, int]:
        """Analyze owned games to determine user preferences.

        Returns:
            Dictionary mapping tags/genres to frequency counts.
        """
        await self.fetch_owned_games()

        tag_counts: dict[str, int] = {}

        # Sample top played games for preference analysis
        sorted_games = sorted(
            self._owned_games or [], key=lambda g: g.playtime_minutes, reverse=True
        )
        top_games = sorted_games[:20]  # Analyze top 20 most played

        for game in top_games:
            tags = await self.get_game_tags(game.app_id)
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return tag_counts
