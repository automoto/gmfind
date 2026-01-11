"""Steam inventory fetcher for private profiles using authenticated browser session."""

import csv
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page

from src.steam_auth import get_authenticated_context, login, STATE_FILE

logger = logging.getLogger(__name__)


@dataclass
class OwnedGame:
    """Represents a game owned by the user."""
    app_id: int
    title: str


def fetch_games_from_library(page: Page) -> list[OwnedGame]:
    """
    Fetch all games from the user's Steam library page.

    Args:
        page: Authenticated Playwright page

    Returns:
        List of OwnedGame objects
    """
    games = []

    # Navigate to user's game library
    logger.info("Navigating to game library...")
    page.goto("https://steamcommunity.com/my/games/?tab=all", wait_until="networkidle")
    time.sleep(2)

    # Check if we're on the games page (with or without trailing slash variations)
    if "/games" not in page.url:
        logger.warning(f"Unexpected URL: {page.url}")
        return games

    # Wait for games to load - Steam loads them dynamically
    logger.info("Waiting for games to load...")
    try:
        page.wait_for_selector(".gameListRow, .gameslistitems_GamesListItemContainer_29H3o, [class*='GamesListItemContainer']", timeout=5000)
    except Exception:
        logger.info("No games found in library")
        return games

    # Scroll to load all games (Steam uses infinite scroll)
    logger.info("Scrolling to load all games...")
    last_count = 0
    scroll_attempts = 0
    max_scrolls = 50

    while scroll_attempts < max_scrolls:
        # Scroll down
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)

        # Count current games
        current_count = page.locator(".gameListRow, [class*='GamesListItemContainer']").count()

        if current_count == last_count:
            scroll_attempts += 1
            if scroll_attempts >= 3:
                break
        else:
            scroll_attempts = 0
            last_count = current_count

    logger.info(f"Found {last_count} game elements")

    # Try new Steam UI first (class names with hashes)
    game_rows = page.locator("[class*='GamesListItemContainer']").all()

    if game_rows:
        logger.info("Parsing new Steam UI format...")
        for row in game_rows:
            try:
                # Get the link which contains the app ID
                link = row.locator("a[href*='/app/']").first
                href = link.get_attribute("href") or ""

                # Extract app ID from URL
                app_match = re.search(r"/app/(\d+)", href)
                if not app_match:
                    continue
                app_id = int(app_match.group(1))

                # Get game title
                title_elem = row.locator("[class*='GameName'], [class*='gamename']").first
                title = title_elem.inner_text().strip() if title_elem.count() > 0 else ""

                if not title:
                    # Fallback: try to get text from the link
                    title = link.inner_text().strip()

                if title and app_id:
                    games.append(OwnedGame(app_id=app_id, title=title))
            except Exception as e:
                logger.debug(f"Error parsing game row: {e}")
                continue

    # Fallback to old Steam UI
    if not games:
        logger.info("Trying old Steam UI format...")
        game_rows = page.locator(".gameListRow").all()

        for row in game_rows:
            try:
                # Get app ID from the row's ID attribute (format: "game_APPID")
                row_id = row.get_attribute("id") or ""
                app_match = re.search(r"game_(\d+)", row_id)
                if not app_match:
                    continue
                app_id = int(app_match.group(1))

                # Get game title
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

    logger.info(f"Successfully parsed {len(unique_games)} unique games")
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
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["title", "steam_id"])
        for game in sorted(games, key=lambda g: g.title.lower()):
            writer.writerow([game.title, game.app_id])

    return filename


def fetch_and_export(filename: str = "inventory_private.csv") -> str:
    """
    Main function: Login, fetch games, and export to CSV.

    Args:
        filename: Output CSV filename

    Returns:
        Path to the created file

    Raises:
        RuntimeError: If login fails or no games found
    """
    # Ensure we're logged in
    if not STATE_FILE.exists():
        logger.info("No session found, performing login...")
        if not login():
            raise RuntimeError("Failed to login to Steam")

    # Fetch games using authenticated session
    logger.info("Fetching game library...")

    with get_authenticated_context() as (context, page):
        games = fetch_games_from_library(page)

    # Export to CSV (empty CSV with headers if no games)
    output_path = export_inventory_csv(games, filename)
    logger.info(f"Exported {len(games)} games to {output_path}")

    return output_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Export Steam game library to CSV")
    parser.add_argument(
        "-o", "--output",
        default="inventory_private.csv",
        help="Output CSV filename (default: inventory_private.csv)"
    )
    args = parser.parse_args()

    try:
        path = fetch_and_export(args.output)
        print(f"\n[SUCCESS] Inventory exported to: {path}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        exit(1)
