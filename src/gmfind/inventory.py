"""Steam inventory checker - fetches user's owned games."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

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

    def fetch_owned_games(self) -> list[OwnedGame]:
        """Fetch the list of games owned by the user.

        Uses the public Steam API endpoint.

        Returns:
            List of owned games.

        Raises:
            SteamInventoryError: If the request fails or profile is private.
        """
        if self._owned_games is not None:
            return self._owned_games

        url = f"https://steamcommunity.com/profiles/{self.steam_id}/games/?tab=all&xml=1"

        try:
            response = requests.get(url, timeout=30.0, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException as e:
            raise SteamInventoryError(f"Failed to fetch owned games: {e}") from e

        if "/login/" in str(response.url) or "This profile is private" in response.text:
            raise SteamInventoryError(
                "Steam profile game library is private. "
                "Please set your game details to public in Steam privacy settings."
            )

        games = self._parse_games_xml(response.text)
        self._owned_games = games
        self._owned_app_ids = {g.app_id for g in games}

        logger.info(f"Fetched {len(games)} owned games from Steam")
        return games

    def _parse_games_xml(self, xml_content: str) -> list[OwnedGame]:
        """Parse the games XML response from Steam using xml.etree.

        Args:
            xml_content: Raw XML string from Steam's games endpoint.

        Returns:
            List of OwnedGame objects parsed from the XML.
        """
        games = []
        try:
            root = ET.fromstring(xml_content)
            for game_elem in root.findall(".//game"):
                app_id_text = game_elem.findtext("appID")
                name = game_elem.findtext("name")
                hours_text = game_elem.findtext("hoursOnRecord", "0")

                if app_id_text and name:
                    try:
                        app_id = int(app_id_text)
                        playtime_minutes = int(float(hours_text) * 60)
                        games.append(OwnedGame(app_id, name, playtime_minutes))
                    except ValueError:
                        logger.debug(f"Failed to parse game: appID={app_id_text}, name={name}")
                        continue
        except ET.ParseError as e:
            logger.warning(f"Failed to parse games XML: {e}")

        return games

    def get_owned_app_ids(self) -> set[int]:
        if self._owned_app_ids is None:
            self.fetch_owned_games()
        return self._owned_app_ids or set()

    def get_game_tags(self, app_id: int) -> list[str]:
        try:
            response = requests.get(
                self.STORE_API_URL,
                params={"appids": str(app_id), "cc": "us", "l": "en"},
                timeout=15.0,
            )
            data = response.json()
            game_data = data.get(str(app_id), {}).get("data", {})
            tags = [g.get("description") for g in game_data.get("genres", [])]
            tags.extend([c.get("description") for c in game_data.get("categories", [])])
            return [t for t in tags if t]
        except Exception:
            return []

    def analyze_preferences(self) -> dict[str, int]:
        self.fetch_owned_games()
        tag_counts: dict[str, int] = {}
        sorted_games = sorted(
            self._owned_games or [], key=lambda g: g.playtime_minutes, reverse=True
        )[:20]
        for game in sorted_games:
            for tag in self.get_game_tags(game.app_id):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts

    def export_inventory_csv(self, filename: str = "inventory.csv") -> str:
        import csv

        games = self.fetch_owned_games()
        with open(filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Steam ID"])
            for game in games:
                writer.writerow([game.name, game.app_id])
        return filename
