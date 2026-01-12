import argparse
import logging
import time
from pathlib import Path

from src.buy_game import buy_game
from src.check_balance import check_balance, get_balance
from src.recommendations.protondb import ProtonDBClient
from src.recommendations.steam_deck import SteamDeckClient
from src.game_check import check_game
from src.blocklist_checker import check_blocklist
from src.inventory import SteamInventory
from src.inventory_private import fetch_and_export
from src.config import load_config
from src.recommend_metacritic import get_recommendation_with_paths
from src.deals import SteamSpecialsFetcher, DealsAggregator
from src.reports import MarkdownReportGenerator
from src.reports.markdown_generator import ReportConfig, generate_timestamped_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/steam_bot.log"),
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

        print("\n" + "=" * 40)
        print(f"STEAM DECK VERIFICATION (AppID: {app_id})")
        print("=" * 40)
        print(f"Status:  {report.display_status}")
        print("=" * 40 + "\n")

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

        print("\n" + "=" * 40)
        print(f"PROTONDB REPORT (AppID: {app_id})")
        print("=" * 40)
        print(f"Tier:       {report.tier.upper()}")
        print(f"Confidence: {report.confidence}")
        print(f"Trend:      {report.trend}")
        print(f"Score:      {report.score}")
        print("=" * 40 + "\n")

    except ValueError:
        logger.error("App ID must be an integer.")
    except Exception as e:
        logger.error(f"Failed to check ProtonDB: {e}")


def run_auto_buy(
    config_path="config.yaml",
    inventory_path="inventory_private.csv",
    block_list_path="block_list.yaml",
    headless=True,
):
    """Run the fully autonomous buy loop."""
    logger.info("Starting Auto-Buy sequence...")

    # 1. Load Config
    try:
        config = load_config(config_path)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    max_price = config.preferences.max_price
    logger.info(f"Max configured price: ${max_price:.2f}")

    # 2. Check Balance
    balance = get_balance()
    if balance is None:
        logger.error("Could not retrieve wallet balance. Aborting.")
        return

    logger.info(f"Current Wallet Balance: ${balance:.2f}")

    if balance < max_price:
        logger.warning(
            f"Insufficient funds for max price item (${balance:.2f} < ${max_price:.2f}). Aborting."
        )
        return

    # 3. Get Recommendation
    logger.info("Searching for recommendation...")
    app_id = get_recommendation_with_paths(config_path, inventory_path, block_list_path)

    if not app_id:
        logger.info("No suitable recommendation found.")
        return

    logger.info(f"Recommended App ID: {app_id}")

    # 4. Buy Game
    logger.info(f"Attempting to buy App ID {app_id}...")
    success = False
    try:
        success = buy_game(str(app_id), headless=headless)
    except Exception as e:
        logger.error(f"Purchase failed with exception: {e}")

    if success:
        logger.info(
            f"[VERIFICATION] Purchase of App ID {app_id} reported successful. Refreshing inventory..."
        )
        # Wait a few seconds for Steam backend to update
        time.sleep(5)
        try:
            # Refresh private inventory
            # fetch_and_export already creates its own authenticated context
            fetch_and_export(inventory_path)

            # Verify app_id is now in owned_games
            from src.recommend_metacritic import get_owned_app_ids

            owned_ids = get_owned_app_ids(inventory_path)

            if int(app_id) in owned_ids:
                logger.info(
                    f"[VERIFICATION SUCCESS] App ID {app_id} found in updated inventory!"
                )
                print(f"\n[COMPLETE SUCCESS] Purchased and verified: App ID {app_id}")
            else:
                logger.warning(
                    f"[VERIFICATION UNCERTAIN] Purchase reported success, but App ID {app_id} not found in inventory yet. Steam might be slow to update."
                )
        except Exception as e:
            logger.error(f"[VERIFICATION ERROR] Failed to refresh inventory: {e}")
    else:
        logger.error(
            f"[FAILURE] Purchase of App ID {app_id} failed or could not be confirmed."
        )


def find_deals(
    count: int = 10,
    output_path: str | None = None,
    config_path: str = "config.yaml",
    block_list_path: str = "block_list.yaml",
    inventory_path: str = "inventory_private.csv",
    skip_inventory: bool = False,
):
    """Find discounted games and generate a markdown report.

    Args:
        count: Number of games to include in the report.
        output_path: Path to save the report (default: docs/deals_TIMESTAMP.md).
        config_path: Path to config.yaml.
        block_list_path: Path to block_list.yaml.
        inventory_path: Path to inventory CSV.
        skip_inventory: If True, include owned games (for public reports).
    """
    logger.info(f"Finding {count} best deals...")

    # Generate output path if not specified
    if not output_path:
        output_path = generate_timestamped_filename("docs")

    # Load config for preferences
    try:
        config = load_config(config_path)
        preferences = {
            "max_price": config.preferences.max_price,
            "min_metacritic_score": config.preferences.min_metacritic_score,
            "max_game_age_years": config.preferences.max_game_age_years,
        }
        logger.info(f"Loaded preferences: {preferences}")
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        preferences = {}

    # Fetch deals from Steam
    logger.info("Fetching deals from Steam...")
    steam_fetcher = SteamSpecialsFetcher()
    steam_deals = steam_fetcher.fetch_deals(limit=count * 5)
    logger.info(f"Found {len(steam_deals)} Steam deals")

    # Filter and enrich
    logger.info("Filtering and enriching deals...")
    aggregator = DealsAggregator(
        config_path, block_list_path, inventory_path, skip_inventory
    )
    enriched_deals = aggregator.get_filtered_enriched_deals(
        steam_deals,
        limit=count,
        review_limit=3,
    )

    if not enriched_deals:
        logger.warning("No deals found matching your criteria.")
        print("\n[WARNING] No deals found matching your criteria.")
        print(
            "Try adjusting your config.yaml settings (max_price, min_metacritic_score, etc.)"
        )
        return

    # Generate report
    logger.info(f"Generating report with {len(enriched_deals)} deals...")
    generator = MarkdownReportGenerator(preferences)
    report_config = ReportConfig(
        game_count=count,
        min_quotes=3,
    )

    generator.generate_report(enriched_deals, report_config, output_path)

    # Output
    print(f"\n[SUCCESS] Deals report saved to: {output_path}")
    print(f"\nFound {len(enriched_deals)} deals matching your criteria:\n")

    for i, deal in enumerate(enriched_deals, 1):
        print(
            f"  {i}. {deal.name} - ${deal.sale_price:.2f} (-{deal.discount_percent}%)"
        )

    print(f"\nFull report: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Steam Auto-Buyer CLI")
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
        "--auto-buy",
        action="store_true",
        help="Autonomous mode: Check balance -> Recommend -> Buy (Requires Login)",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in visible mode (default is headless)",
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
        "--inventory-private",
        nargs="?",
        const="inventory_private.csv",
        metavar="FILENAME",
        help="Export user game library to CSV using authenticated browser (for private profiles, default: inventory_private.csv)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        metavar="PATH",
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--block-list",
        type=str,
        default="block_list.yaml",
        metavar="PATH",
        help="Path to block_list.yaml",
    )
    parser.add_argument(
        "--inventory",
        type=str,
        default="inventory_private.csv",
        metavar="PATH",
        help="Path to inventory CSV",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--find-deals",
        type=int,
        nargs="?",
        const=10,
        metavar="COUNT",
        help="Find discounted games and generate markdown report (default: 10 games)",
    )
    parser.add_argument(
        "--deals-output",
        type=str,
        default=None,
        metavar="PATH",
        help="Output path for deals report (default: docs/deals_TIMESTAMP.md)",
    )
    parser.add_argument(
        "--skip-inventory",
        action="store_true",
        help="Skip inventory check - include owned games in report (for public reports)",
    )

    args = parser.parse_args()

    # Ensure log directory exists
    Path("logs").mkdir(exist_ok=True)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    headless = not args.headful

    if args.auto_buy:
        run_auto_buy(args.config, args.inventory, args.block_list, headless=headless)
    elif args.buy:
        buy_game(args.buy, headless=headless)
    elif args.balance:
        check_balance()
    elif args.protondb:
        check_protondb(args.protondb)
    elif args.deck:
        check_steam_deck(args.deck)
    elif args.check_game:
        check_game(
            args.check_game,
            config_path=args.config,
            block_list_path=args.block_list,
            inventory_path=args.inventory,
        )
    elif args.check_blocklist:
        check_blocklist(args.check_blocklist)
    elif args.inventory_csv:
        export_inventory(args.inventory_csv)
    elif args.inventory_private:
        try:
            logger.info(f"Fetching private inventory to {args.inventory_private}...")
            path = fetch_and_export(args.inventory_private)
            print(f"\n[SUCCESS] Private inventory exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export private inventory: {e}")
    elif args.find_deals is not None:
        find_deals(
            count=args.find_deals,
            output_path=args.deals_output,
            config_path=args.config,
            block_list_path=args.block_list,
            inventory_path=args.inventory,
            skip_inventory=args.skip_inventory,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
