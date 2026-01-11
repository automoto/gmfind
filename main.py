#!/usr/bin/env python3
"""Steam Auto-Buyer Bot - Main entry point."""

import argparse
import logging
import sys
from pathlib import Path

from src.buy_game import buy_game
from src.check_balance import check_balance
from src.recommendations.protondb import ProtonDBClient
from src.recommendations.steam_deck import SteamDeckClient
from src.game_check import check_game
from src.blocklist_checker import check_blocklist
from src.inventory import SteamInventory
from src.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("steam_bot.log"),
    ],
)
logger = logging.getLogger(__name__)


def export_inventory(filename: str = "inventory.csv"):
    """Export user inventory to CSV."""
    try:
        config = load_config()
        inventory = SteamInventory(config.steam.steam_id)
        logger.info(f"Fetching inventory for SteamID {config.steam.steam_id}...")
        path = inventory.export_inventory_csv(filename)
        print(f"\n[SUCCESS] Inventory exported to {path}")
    except Exception as e:
        logger.error(f"Failed to export inventory: {e}")


def check_steam_deck(app_id: str):
    """Check official Steam Deck verification status."""
    try:
        app_id_int = int(app_id)
        client = SteamDeckClient()
        logger.info(f"Checking Steam Deck status for AppID {app_id}...")
        report = client.get_status(app_id_int)
        
        print("\n" + "="*40)
        print(f"STEAM DECK VERIFICATION (AppID: {app_id})")
        print("="*40)
        print(f"Status:  {report.display_status}")
        print("="*40 + "\n")
        
    except ValueError:
        logger.error("App ID must be an integer.")
    except Exception as e:
        logger.error(f"Failed to check Steam Deck status: {e}")


def check_protondb(app_id: str):
    """Check ProtonDB rating for a game."""
    try:
        app_id_int = int(app_id)
        client = ProtonDBClient()
        logger.info(f"Checking ProtonDB rating for AppID {app_id}...")
        report = client.get_rating(app_id_int)
        
        print("\n" + "="*40)
        print(f"PROTONDB REPORT (AppID: {app_id})")
        print("="*40)
        print(f"Tier:       {report.tier.upper()}")
        print(f"Confidence: {report.confidence}")
        print(f"Trend:      {report.trend}")
        print(f"Score:      {report.score}")
        print("="*40 + "\n")
        
    except ValueError:
        logger.error("App ID must be an integer.")
    except Exception as e:
        logger.error(f"Failed to check ProtonDB: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Steam Auto-Buyer CLI"
    )
    parser.add_argument(
        "--buy",
        type=str,
        metavar="APP_ID",
        help="Purchase a game by App ID (Requires Login)",
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        help="Check Steam Wallet balance (Requires Login)",
    )
    parser.add_argument(
        "--protondb",
        type=str,
        metavar="APP_ID",
        help="Check ProtonDB rating for a game (No Login Required)",
    )
    parser.add_argument(
        "--deck",
        type=str,
        metavar="APP_ID",
        help="Check official Steam Deck Verification status (No Login Required)",
    )
    parser.add_argument(
        "--check-game",
        type=str,
        metavar="APP_ID",
        help="Get full game details (JSON) including Price, Reviews, Deck & ProtonDB (No Login Required)",
    )
    parser.add_argument(
        "--check-blocklist",
        type=str,
        metavar="TITLE",
        help="Check if a game title matches the blocklist",
    )
    parser.add_argument(
        "--inventory-csv",
        nargs="?",
        const="inventory.csv",
        metavar="FILENAME",
        help="Export user game library to CSV (default: inventory.csv)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.buy:
        buy_game(args.buy)
    elif args.balance:
        check_balance()
    elif args.protondb:
        check_protondb(args.protondb)
    elif args.deck:
        check_steam_deck(args.deck)
    elif args.check_game:
        check_game(args.check_game)
    elif args.check_blocklist:
        check_blocklist(args.check_blocklist)
    elif args.inventory_csv:
        export_inventory(args.inventory_csv)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()