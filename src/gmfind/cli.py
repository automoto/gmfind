"""Steam automation CLI - Main entry point with subcommands."""

import argparse
import logging
import sys
import time

from gmfind import __version__
from gmfind.paths import (
    ensure_directories,
    get_blocklist_file,
    get_config_file,
    get_inventory_file,
    get_log_file,
)


def _setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging to XDG cache directory."""
    ensure_directories()
    log_file = get_log_file()

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )
    return logging.getLogger(__name__)


# =============================================================================
# Command Handlers
# =============================================================================


def cmd_init(args) -> int:
    """Handle 'gmfind init' command."""
    from gmfind.setup import run_setup

    return run_setup()


def cmd_balance(args) -> int:
    """Handle 'gmfind balance' command."""
    from gmfind.check_balance import check_balance

    check_balance()
    return 0


def cmd_blocklist(args) -> int:
    """Handle 'gmfind blocklist <TITLE>' command."""
    from gmfind.blocklist_checker import check_blocklist

    # Use custom blocklist if provided
    if args.block_list:
        import gmfind.blocklist_checker as bc

        # Temporarily override the default
        original = bc.BLOCK_LIST_FILE
        bc.BLOCK_LIST_FILE = args.block_list
        check_blocklist(args.title)
        bc.BLOCK_LIST_FILE = original
    else:
        check_blocklist(args.title)
    return 0


def cmd_check(args) -> int:
    """Handle 'gmfind check <APP_ID>' command."""
    from gmfind.game_check import check_game

    config_path = args.config or str(get_config_file())
    block_list_path = args.block_list or str(get_blocklist_file())
    inventory_path = args.inventory or str(get_inventory_file())

    check_game(
        args.app_id,
        config_path=config_path,
        block_list_path=block_list_path,
        inventory_path=inventory_path,
    )
    return 0


def cmd_deals(args) -> int:
    """Handle 'gmfind deals [COUNT]' command."""
    import os

    from gmfind.config import load_config
    from gmfind.deals import DealsAggregator, SteamSpecialsFetcher
    from gmfind.reports import MarkdownReportGenerator
    from gmfind.reports.markdown_generator import ReportConfig, generate_timestamped_filename

    logger = logging.getLogger(__name__)

    config_path = args.config or str(get_config_file())
    inventory_path = args.inventory or str(get_inventory_file())
    block_list_path = args.block_list or str(get_blocklist_file())

    count = args.count or 10
    logger.info(f"Finding {count} best deals...")

    # Determine output behavior
    final_path: str | None = None
    if args.output:
        if os.path.isdir(args.output) or args.output.endswith("/"):
            final_path = generate_timestamped_filename(args.output.rstrip("/"))
        else:
            final_path = args.output

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
    aggregator = DealsAggregator(config_path, block_list_path, inventory_path, args.skip_inventory)
    enriched_deals = aggregator.get_filtered_enriched_deals(
        steam_deals,
        limit=count,
        review_limit=3,
    )

    if not enriched_deals:
        logger.warning("No deals found matching your criteria.")
        print("\n[WARNING] No deals found matching your criteria.")
        print("Try adjusting your config.yaml settings (max_price, min_metacritic_score, etc.)")
        return 1

    # Generate report
    logger.info(f"Generating report with {len(enriched_deals)} deals...")
    generator = MarkdownReportGenerator(preferences)
    report_config = ReportConfig(
        game_count=count,
        min_quotes=3,
    )

    if final_path:
        # Write to file
        generator.generate_report(enriched_deals, report_config, final_path)
        print(f"\n[SUCCESS] Deals report saved to: {final_path}", file=sys.stderr)
        print(
            f"\nFound {len(enriched_deals)} deals matching your criteria:\n",
            file=sys.stderr,
        )
        for i, deal in enumerate(enriched_deals, 1):
            print(
                f"  {i}. {deal.name} - ${deal.sale_price:.2f} (-{deal.discount_percent}%)",
                file=sys.stderr,
            )
        print(f"\nFull report: {final_path}", file=sys.stderr)
    else:
        # Print markdown to stdout
        markdown = generator.generate_report(enriched_deals, report_config)
        print(markdown)

    return 0


def cmd_inventory(args) -> int:
    """Handle 'gmfind inventory --private/--public' command."""
    logger = logging.getLogger(__name__)

    if args.private:
        from gmfind.inventory_private import fetch_and_export

        output = args.output or str(get_inventory_file())
        try:
            logger.info(f"Fetching private inventory to {output}...")
            path = fetch_and_export(output)
            print(f"\n[SUCCESS] Private inventory exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export private inventory: {e}")
            return 1
    else:  # --public
        from gmfind.config import load_config
        from gmfind.inventory import SteamInventory

        output = args.output or str(get_inventory_file("inventory.csv"))
        try:
            config_path = args.config or str(get_config_file())
            config = load_config(config_path)
            inventory = SteamInventory(config.steam.steam_id)
            logger.info(f"Fetching inventory for SteamID {config.steam.steam_id}...")
            path = inventory.export_inventory_csv(output)
            print(f"\n[SUCCESS] Inventory exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export inventory: {e}")
            return 1

    return 0


def cmd_buy(args) -> int:
    """Handle 'gmfind buy <APP_ID>' or 'gmfind buy --auto' command."""
    config_path = args.config or str(get_config_file())
    inventory_path = args.inventory or str(get_inventory_file())
    block_list_path = args.block_list or str(get_blocklist_file())
    headless = not args.headful

    if args.auto:
        # Autonomous buy workflow
        return _run_auto_buy(config_path, inventory_path, block_list_path, headless)
    else:
        # Direct buy with validation
        if not args.app_id:
            print("[ERROR] App ID required. Usage: gmfind buy <APP_ID> or gmfind buy --auto")
            return 1
        return _buy_with_validation(
            args.app_id,
            config_path=config_path,
            inventory_path=inventory_path,
            block_list_path=block_list_path,
            headless=headless,
            force=args.force,
        )


def _buy_with_validation(
    app_id: str,
    config_path: str,
    inventory_path: str,
    block_list_path: str,
    headless: bool = True,
    force: bool = False,
) -> int:
    """Buy a game after validating against config, inventory, and blocklist."""
    from gmfind.buy_game import buy_game
    from gmfind.game_check import check_game_data

    logger = logging.getLogger(__name__)

    if force:
        logger.info(f"Force mode: skipping validation for App ID {app_id}")
        buy_game(app_id, headless=headless)
        return 0

    # Get game details for validation
    logger.info(f"Checking game details for App ID {app_id}...")
    try:
        game_data = check_game_data(
            app_id,
            config_path=config_path,
            block_list_path=block_list_path,
            inventory_path=inventory_path,
        )
    except Exception as e:
        logger.error(f"Failed to check game: {e}")
        print(f"[ERROR] Failed to validate game: {e}")
        print("Use --force to skip validation.")
        return 1

    # Check if already owned
    if game_data.get("owned"):
        print(f"[SKIP] You already own this game (App ID: {app_id})")
        print("Use --force to buy anyway (e.g., as a gift).")
        return 1

    # Check blocklist
    if game_data.get("blocked"):
        blocked_term = game_data.get("blocked_term", "unknown")
        print(f"[SKIP] Game matches blocklist term: '{blocked_term}'")
        print("Use --force to buy anyway.")
        return 1

    # Check price/preferences (warn but don't block)
    recommendation = game_data.get("recommendation", {})
    if not recommendation.get("meets_criteria", True):
        reasons = recommendation.get("fail_reasons", [])
        print("[WARNING] Game doesn't meet your preferences:")
        for reason in reasons:
            print(f"  - {reason}")
        print("\nProceeding with purchase anyway. Use --force to skip this warning.")

    # Proceed with purchase
    logger.info(f"Purchasing App ID {app_id}...")
    try:
        success = buy_game(app_id, headless=headless)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Purchase failed: {e}")
        return 1


def _run_auto_buy(
    config_path: str,
    inventory_path: str,
    block_list_path: str,
    headless: bool = True,
) -> int:
    """Run the fully autonomous buy loop."""
    from gmfind.buy_game import buy_game
    from gmfind.check_balance import get_balance
    from gmfind.config import load_config
    from gmfind.inventory_private import fetch_and_export
    from gmfind.recommend_metacritic import get_owned_app_ids, get_recommendation_with_paths

    logger = logging.getLogger(__name__)
    logger.info("Starting Auto-Buy sequence...")

    # 1. Load Config
    try:
        config = load_config(config_path)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return 1

    max_price = config.preferences.max_price
    logger.info(f"Max configured price: ${max_price:.2f}")

    # 2. Check Balance
    balance = get_balance()
    if balance is None:
        logger.error("Could not retrieve wallet balance. Aborting.")
        return 1

    logger.info(f"Current Wallet Balance: ${balance:.2f}")

    if balance < max_price:
        logger.warning(
            f"Insufficient funds for max price item (${balance:.2f} < ${max_price:.2f}). Aborting."
        )
        return 1

    # 3. Get Recommendation
    logger.info("Searching for recommendation...")
    app_id = get_recommendation_with_paths(config_path, inventory_path, block_list_path)

    if not app_id:
        logger.info("No suitable recommendation found.")
        return 0

    logger.info(f"Recommended App ID: {app_id}")

    # 4. Buy Game
    logger.info(f"Attempting to buy App ID {app_id}...")
    success = False
    try:
        success = buy_game(str(app_id), headless=headless)
    except Exception as e:
        logger.error(f"Purchase failed with exception: {e}")
        return 1

    if success:
        logger.info(f"[VERIFICATION] Purchase of {app_id} successful. Refreshing inventory...")
        # Wait a few seconds for Steam backend to update
        time.sleep(5)
        try:
            # Refresh private inventory
            fetch_and_export(inventory_path)
            owned_ids = get_owned_app_ids(inventory_path)

            if int(app_id) in owned_ids:
                logger.info(f"[VERIFICATION SUCCESS] App ID {app_id} in inventory!")
                print(f"\n[COMPLETE SUCCESS] Purchased and verified: App ID {app_id}")
            else:
                logger.warning(
                    f"[VERIFICATION UNCERTAIN] Purchase reported success, but App ID "
                    f"{app_id} not found in inventory yet. Steam might be slow to update."
                )
        except Exception as e:
            logger.error(f"[VERIFICATION ERROR] Failed to refresh inventory: {e}")
    else:
        logger.error(f"[FAILURE] Purchase of App ID {app_id} failed or could not be confirmed.")
        return 1

    return 0


# =============================================================================
# Argument Parser Setup
# =============================================================================


def _add_config_options(
    parser: argparse.ArgumentParser,
    config: bool = False,
    blocklist: bool = False,
    inventory: bool = False,
    headful: bool = False,
):
    """Add common config options to a subparser."""
    if config:
        parser.add_argument(
            "--config",
            metavar="PATH",
            help=f"Path to config.yaml (default: {get_config_file()})",
        )
    if blocklist:
        parser.add_argument(
            "--block-list",
            metavar="PATH",
            help=f"Path to block_list.yaml (default: {get_blocklist_file()})",
        )
    if inventory:
        parser.add_argument(
            "--inventory",
            metavar="PATH",
            help=f"Path to inventory CSV (default: {get_inventory_file()})",
        )
    if headful:
        parser.add_argument(
            "--headful",
            action="store_true",
            help="Run browser in visible mode (default is headless)",
        )


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="gmfind",
        description="Steam CLI - find games, check deals, purchase, and manage your library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gmfind init                     Initialize config and install Playwright
  gmfind check 1145350            Get full game details
  gmfind deals 5                  Find top 5 deals
  gmfind buy 1145350              Buy a specific game
  gmfind buy --auto               Autonomous buy workflow
  gmfind balance                  Check Steam Wallet balance
  gmfind inventory --private      Export game library
  gmfind blocklist "FIFA"         Check if title is blocked
""",
    )

    # Global options
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"gmfind {__version__}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # --- init ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize config files and install Playwright browsers",
    )
    init_parser.set_defaults(func=cmd_init)

    # --- balance ---
    balance_parser = subparsers.add_parser(
        "balance",
        help="Check Steam Wallet balance (requires login)",
    )
    balance_parser.set_defaults(func=cmd_balance)

    # --- blocklist ---
    blocklist_parser = subparsers.add_parser(
        "blocklist",
        help="Check if a game title matches the blocklist",
    )
    blocklist_parser.add_argument("title", help="Game title to check")
    _add_config_options(blocklist_parser, blocklist=True)
    blocklist_parser.set_defaults(func=cmd_blocklist)

    # --- check ---
    check_parser = subparsers.add_parser(
        "check",
        help="Get full game details (ProtonDB, Deck, price, reviews, ownership)",
    )
    check_parser.add_argument("app_id", help="Steam App ID to check")
    _add_config_options(check_parser, config=True, blocklist=True, inventory=True)
    check_parser.set_defaults(func=cmd_check)

    # --- deals ---
    deals_parser = subparsers.add_parser(
        "deals",
        help="Find discounted games and generate a report",
    )
    deals_parser.add_argument(
        "count",
        nargs="?",
        type=int,
        default=10,
        help="Number of deals to find (default: 10)",
    )
    deals_parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Output file path for the report (default: print to stdout)",
    )
    deals_parser.add_argument(
        "--skip-inventory",
        action="store_true",
        help="Include owned games in report (for public reports)",
    )
    _add_config_options(deals_parser, config=True, blocklist=True, inventory=True)
    deals_parser.set_defaults(func=cmd_deals)

    # --- inventory ---
    inventory_parser = subparsers.add_parser(
        "inventory",
        help="Export game library to CSV",
    )
    inv_group = inventory_parser.add_mutually_exclusive_group(required=True)
    inv_group.add_argument(
        "--private",
        action="store_true",
        help="Export via authenticated browser (for private profiles)",
    )
    inv_group.add_argument(
        "--public",
        action="store_true",
        help="Export via Steam API (for public profiles)",
    )
    inventory_parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help=f"Output CSV path (default: {get_inventory_file()})",
    )
    _add_config_options(inventory_parser, config=True, headful=True)
    inventory_parser.set_defaults(func=cmd_inventory)

    # --- buy ---
    buy_parser = subparsers.add_parser(
        "buy",
        help="Purchase a game (validates against config, inventory, blocklist)",
    )
    buy_parser.add_argument(
        "app_id",
        nargs="?",
        help="Steam App ID to purchase",
    )
    buy_parser.add_argument(
        "--auto",
        action="store_true",
        help="Autonomous mode: check balance -> recommend -> buy",
    )
    buy_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip validation (buy even if owned/blocked/exceeds preferences)",
    )
    _add_config_options(buy_parser, config=True, blocklist=True, inventory=True, headful=True)
    buy_parser.set_defaults(func=cmd_buy)

    return parser


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging before any commands (except init which handles its own)
    if args.command != "init":
        _setup_logging(args.verbose)

    # No command specified - show help
    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch to command handler
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
