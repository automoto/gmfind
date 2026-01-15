"""Steam inventory fetcher for private profiles using authenticated browser session."""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from gmfind.steam_auth import STATE_FILE, get_authenticated_context, login

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def extract_app_id_from_url(url: str) -> int | None:
    """Extract Steam app ID from a URL using urllib.parse.

    Args:
        url: A Steam URL like '/app/12345/Game_Name/' or full URL.

    Returns:
        The app ID as an integer, or None if not found.
    """
    if not url:
        return None

    path = urlparse(url).path
    parts = path.strip("/").split("/")

    try:
        app_idx = parts.index("app")
        return int(parts[app_idx + 1])
    except (ValueError, IndexError):
        return None


@dataclass
class OwnedGame:
    """Represents a game owned by the user."""

    app_id: int
    title: str


def _extract_render_context(html_content: str) -> dict[str, Any] | None:
    """Extract render context from window.SSR.renderContext using string operations.

    Steam embeds data in a double-escaped JSON string inside JSON.parse().
    Format: window.SSR.renderContext=JSON.parse("...");

    Args:
        html_content: The HTML page content.

    Returns:
        Parsed render context dict, or None if not found.
    """
    marker_start = 'window.SSR.renderContext=JSON.parse("'
    start_idx = html_content.find(marker_start)
    if start_idx == -1:
        return None

    start_idx += len(marker_start)
    # Find the closing ");
    end_idx = html_content.find('");', start_idx)
    if end_idx == -1:
        return None

    json_str = html_content[start_idx:end_idx]

    try:
        # Unescape the JS string by parsing it as a JSON string literal
        render_context_str = json.loads(f'"{json_str}"')
        result: dict[str, Any] = json.loads(render_context_str)
        return result
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_loader_data(html_content: str) -> list[Any] | None:
    """Extract loader data from window.SSR.loaderData using string operations.

    Legacy fallback format: window.SSR.loaderData = [...];

    Args:
        html_content: The HTML page content.

    Returns:
        Parsed loader data list, or None if not found.
    """
    # Look for the start marker (with optional whitespace)
    marker = "window.SSR.loaderData"
    start_idx = html_content.find(marker)
    if start_idx == -1:
        return None

    # Find the equals sign and opening bracket
    equals_idx = html_content.find("=", start_idx)
    if equals_idx == -1:
        return None

    # Find the opening bracket
    bracket_idx = html_content.find("[", equals_idx)
    if bracket_idx == -1:
        return None

    # Find matching closing bracket by counting brackets
    depth = 1
    end_idx = bracket_idx + 1
    while end_idx < len(html_content) and depth > 0:
        char = html_content[end_idx]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        end_idx += 1

    if depth != 0:
        return None

    json_str = html_content[bracket_idx:end_idx]

    try:
        result: list[Any] = json.loads(json_str)
        return result
    except (json.JSONDecodeError, ValueError):
        return None


def extract_games_from_html(html_content: str) -> list[OwnedGame]:
    """Extract games from the user's Steam library page HTML using embedded JSON.

    Tries multiple extraction strategies:
    1. window.SSR.renderContext - Modern Steam format
    2. window.SSR.loaderData - Legacy fallback

    Args:
        html_content: The HTML page content.

    Returns:
        List of OwnedGame objects extracted from the page.
    """
    games = []

    # Strategy 1: Extract from window.SSR.renderContext
    render_context = _extract_render_context(html_content)
    if render_context:
        try:
            query_data_str = render_context.get("queryData", "{}")
            query_data = json.loads(query_data_str)

            queries = query_data.get("queries", [])
            for query in queries:
                query_key = query.get("queryKey", [])
                if (
                    isinstance(query_key, list)
                    and len(query_key) > 0
                    and query_key[0] == "OwnedGames"
                ):
                    game_list = query.get("state", {}).get("data", [])
                    for game in game_list:
                        app_id = game.get("appid")
                        name = game.get("name")
                        if app_id and name:
                            games.append(OwnedGame(app_id=int(app_id), title=str(name)))

                    if games:
                        logger.info(f"Extracted {len(games)} games from renderContext")
                        return games
        except Exception as e:
            logger.debug(f"Failed to parse renderContext data: {e}")

    # Strategy 2: Extract from window.SSR.loaderData (legacy fallback)
    loader_data = _extract_loader_data(html_content)
    if loader_data:
        try:
            for item in loader_data:
                if isinstance(item, str) and "OwnedGames" in item:
                    data = json.loads(item)
                    game_list = data.get("listData", {}).get("rgRecentlyPlayedGames", [])
                    for game in game_list:
                        app_id = game.get("appid")
                        name = game.get("name")
                        if app_id and name:
                            games.append(OwnedGame(app_id=int(app_id), title=str(name)))
        except Exception as e:
            logger.debug(f"Failed to parse loaderData: {e}")

    return games


def fetch_games_from_library(page: Page) -> list[OwnedGame]:
    """
    Fetch all games from the user's Steam library page.

    Args:
        page: Authenticated Playwright page

    Returns:
        List of OwnedGame objects
    """
    # Navigate to user's game library
    logger.info("Navigating to game library...")
    page.goto("https://steamcommunity.com/my/games/?tab=all", wait_until="networkidle")

    # Wait a bit for the page context to be fully populated
    time.sleep(2)

    # Check if we're on the games page
    if "/games" not in page.url:
        logger.warning(f"Unexpected URL: {page.url}")
        return []

    # Get page content and try JSON extraction first (fastest and most reliable)
    html_content = page.content()
    games = extract_games_from_html(html_content)

    if games:
        # Deduplicate and return
        seen = set()
        unique_games = []
        for game in games:
            if game.app_id not in seen:
                seen.add(game.app_id)
                unique_games.append(game)
        logger.info(f"Successfully extracted {len(unique_games)} unique games from JSON")
        return unique_games

    # Fallback to DOM parsing if JSON extraction failed
    logger.info("JSON extraction failed, falling back to DOM parsing...")

    # Try new Steam UI DOM format
    game_rows = page.locator("[class*='GamesListItemContainer']").all()
    games = []

    if game_rows:
        logger.info("Parsing new Steam UI DOM format...")
        for row in game_rows:
            try:
                link = row.locator("a[href*='/app/']").first
                href = link.get_attribute("href") or ""
                app_id = extract_app_id_from_url(href)
                if not app_id:
                    continue
                title_elem = row.locator("[class*='GameName'], [class*='gamename']").first
                title = title_elem.inner_text().strip() if title_elem.count() > 0 else ""
                if not title:
                    title = link.inner_text().strip()
                if title and app_id:
                    games.append(OwnedGame(app_id=app_id, title=title))
            except Exception as e:
                logger.debug(f"Error parsing game row: {e}")
                continue

    # Fallback to old Steam UI DOM format
    if not games:
        logger.info("Trying old Steam UI DOM format...")
        game_rows = page.locator(".gameListRow").all()

        for row in game_rows:
            try:
                row_id = row.get_attribute("id") or ""
                # Extract app ID from row ID format: "game_12345"
                if not row_id.startswith("game_"):
                    continue
                try:
                    app_id = int(row_id[5:])  # Skip "game_" prefix
                except ValueError:
                    continue
                title_elem = row.locator(".gameListRowItemName").first
                title = title_elem.inner_text().strip() if title_elem.count() > 0 else ""
                if title and app_id:
                    games.append(OwnedGame(app_id=app_id, title=title))
            except Exception as e:
                logger.debug(f"Error parsing game row: {e}")
                continue

    # Deduplicate by app_id
    seen = set()
    unique_games = []
    for game in games:
        if game.app_id not in seen:
            seen.add(game.app_id)
            unique_games.append(game)

    logger.info(f"Successfully parsed {len(unique_games)} unique games from DOM")
    return unique_games


def export_inventory_csv(games: list[OwnedGame], filename: str = "inventory_private.csv") -> str:
    """
    Export games to CSV file.

    Args:
        games: List of OwnedGame objects
        filename: Output filename

    Returns:
        Path to the created file
    """
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "steam_id"])
        for game in sorted(games, key=lambda g: g.title.lower()):
            writer.writerow([game.title, game.app_id])

    return filename


def fetch_and_export(filename: str = "inventory_private.csv", headless: bool = True) -> str:
    """
    Main function: Login, fetch games, and export to CSV.

    Args:
        filename: Output CSV filename
        headless: Run browser in headless mode

    Returns:
        Path to the created file

    Raises:
        RuntimeError: If login fails or no games found
    """
    # Ensure we're logged in
    if not STATE_FILE.exists():
        logger.info("No session found, performing login...")
        if not login(headless=headless):
            raise RuntimeError("Failed to login to Steam")

    # Fetch games using authenticated session
    logger.info("Fetching game library...")

    with get_authenticated_context(headless=headless) as (context, page):
        games = fetch_games_from_library(page)

    # Export to CSV (empty CSV with headers if no games)
    output_path = export_inventory_csv(games, filename)
    logger.info(f"Exported {len(games)} games to {output_path}")

    return output_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Export Steam game library to CSV")
    parser.add_argument(
        "-o",
        "--output",
        default="inventory_private.csv",
        help="Output CSV filename (default: inventory_private.csv)",
    )
    args = parser.parse_args()

    try:
        path = fetch_and_export(args.output)
        print(f"\n[SUCCESS] Inventory exported to: {path}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        exit(1)
