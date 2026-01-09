#!/usr/bin/env python3
"""Steam Auto-Buyer Bot - Main entry point."""

import argparse
import asyncio
import logging
import sys

from src.config import load_config
from src.inventory import SteamInventory
from src.recommendations import RecommendationEngine
from src.store import SteamStoreAutomation, CheckoutFlow

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


async def run_bot(dry_run: bool = False, headless: bool = False):
    """Run the Steam auto-buyer bot.

    Args:
        dry_run: If True, don't actually purchase anything.
        headless: Run browser in headless mode.
    """
    # Load configuration
    logger.info("Loading configuration...")
    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    logger.info(f"Max price: ${config.preferences.max_price:.2f}")
    logger.info(f"Min Metacritic score: {config.preferences.min_metacritic_score}")
    logger.info(f"Min ProtonDB rating: {config.preferences.min_protondb_rating}")
    logger.info(f"Max game age: {config.preferences.max_game_age_years} years")

    # Start browser and authenticate first
    logger.info("Starting browser and logging in...")
    store = SteamStoreAutomation(
        username=config.steam.username,
        password=config.steam.password,
        headless=headless,
    )
    await store.start()

    try:
        await store.login()
    except Exception as e:
        logger.error(f"Login failed: {e}")
        await store.close()
        sys.exit(1)

    # Clear cart first - fail early if we can't
    logger.info("Clearing shopping cart...")
    try:
        checkout = CheckoutFlow(store)
        await checkout.remove_all_from_cart()
        logger.info("Cart cleared successfully")
    except Exception as e:
        logger.error(f"Failed to clear cart: {e}")
        await store.close()
        sys.exit(1)

    # Fetch owned games via authenticated session
    try:
        owned_games = await store.fetch_owned_games()
        owned_app_ids = {g["app_id"] for g in owned_games}
        logger.info(f"Found {len(owned_app_ids)} owned games")
    except Exception as e:
        logger.error(f"Failed to fetch owned games: {e}")
        await store.close()
        sys.exit(1)

    # Initialize inventory with pre-fetched data
    inventory = SteamInventory(config.steam.steam_id)
    inventory._owned_app_ids = owned_app_ids
    inventory._owned_games = [
        type("OwnedGame", (), {"app_id": g["app_id"], "name": g["name"], "playtime_minutes": 0})()
        for g in owned_games
    ]

    # Get recommendation
    logger.info("Finding game recommendations...")
    engine = RecommendationEngine(inventory, config.preferences)

    try:
        recommendation = await engine.get_best_recommendation()
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        await store.close()
        sys.exit(1)

    if not recommendation:
        logger.info("No suitable games found matching your criteria.")
        await store.close()
        sys.exit(0)

    # Display recommendation
    logger.info("=" * 60)
    logger.info("RECOMMENDED GAME:")
    logger.info(f"  Name: {recommendation.name}")
    logger.info(f"  Price: {recommendation.price_formatted}")
    logger.info(f"  Metascore: {recommendation.metascore}")
    logger.info(f"  ProtonDB: {recommendation.protondb_rating}")
    logger.info(f"  Steam URL: {recommendation.steam_url}")
    logger.info(f"  Match Score: {recommendation.overall_score:.2%}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN - Not purchasing. Run without --dry-run to buy.")
        await store.close()
        return

    # Continue with purchase using existing authenticated session
    try:
        # Check wallet balance
        balance = await store.get_wallet_balance()
        logger.info(f"Steam Wallet balance: ${balance:.2f}")

        if balance < recommendation.price:
            logger.error(
                f"Insufficient wallet balance. "
                f"Need ${recommendation.price:.2f}, have ${balance:.2f}"
            )
            await store.close()
            sys.exit(1)

        # Navigate to game and verify
        logger.info(f"Navigating to {recommendation.name}...")
        game_info = await store.navigate_to_game(recommendation.app_id)

        if not game_info.get("available", False):
            reason = game_info.get("reason", "Unknown reason")
            logger.error(f"Game not available for purchase: {reason}")
            await store.close()
            sys.exit(1)

        # Verify price hasn't changed
        if game_info["price"] > config.preferences.max_price:
            logger.error(
                f"Price has changed! "
                f"Expected ${recommendation.price:.2f}, now ${game_info['price']:.2f}"
            )
            await store.close()
            sys.exit(1)

        # Add to cart (cart was already cleared at start)
        logger.info("Adding to cart...")
        if not await store.add_to_cart(recommendation.app_id):
            logger.error("Failed to add game to cart")
            await store.close()
            sys.exit(1)

        # Checkout
        logger.info("Proceeding to checkout...")

        success = await checkout.checkout_with_wallet()
        if success:
            logger.info("=" * 60)
            logger.info("PURCHASE SUCCESSFUL!")
            logger.info(f"  Game: {recommendation.name}")
            logger.info(f"  Price: {recommendation.price_formatted}")
            logger.info("=" * 60)

            # Verify the game is now in the library
            verified = await store.verify_game_owned(
                recommendation.app_id, recommendation.name
            )
            if verified:
                logger.info("Purchase verified - game is in library!")
            else:
                logger.warning("Could not verify game in library - please check manually")
        else:
            logger.error("Purchase may have failed - check your Steam account")

    except Exception as e:
        logger.error(f"Purchase failed: {e}")
    finally:
        await store.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Steam Auto-Buyer Bot - Automatically purchase games based on your preferences"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Find a recommendation but don't purchase",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(run_bot(dry_run=args.dry_run, headless=args.headless))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
