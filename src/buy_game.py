"""Steam game purchasing script using Playwright (Sync)."""

import os
import argparse
import time
import logging
from playwright.sync_api import sync_playwright
from src.steam_auth import login, STATE_FILE, USER_AGENT

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SteamCheckout:
    """Synchronous Steam checkout automation."""

    def __init__(self, page):
        self.page = page

    def find_purchase_button(self):
        """Find the final purchase/confirm button."""
        # Selectors from archive/src/store/checkout.py
        selectors = [
            "#purchase_button",
            ".purchase_button",
            "#purchase_confirm_btn",
            'button[class*="purchase"]',
            'button[class*="Primary"]',
            # Additional known IDs
            "#submit_payment_button",
            "#purchase_button_bottom_text",
        ]

        for s in selectors:
            if self.page.is_visible(s):
                return self.page.locator(s)

        # Fallback text search
        return self.page.get_by_text("Purchase").last

    def checkout_with_wallet(self):
        """Complete checkout flow."""
        logger.info("Navigating to Cart...")
        self.page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        time.sleep(2)

        # 1. Click "Continue to Payment"
        # Try finding the button
        continue_btn = None

        # Priority: Text match (New UI)
        text_match = self.page.get_by_text("Continue to payment")
        if text_match.count() > 0 and text_match.first.is_visible():
            continue_btn = text_match.first
        else:
            # Fallback selectors from archive
            selectors = [
                "#btn_purchase_self",
                ".btn_checkout",
                "button.Primary",
                "a.Primary",
            ]
            for s in selectors:
                if self.page.is_visible(s):
                    continue_btn = self.page.locator(s)
                    break

        if not continue_btn:
            logger.error("Could not find 'Continue to Payment' button.")
            self.page.screenshot(path="cart_failed.png")
            return False

        logger.info("Clicking 'Continue to Payment'...")
        continue_btn.click()

        # Wait for Checkout Page
        logger.info("Waiting for checkout page...")
        try:
            self.page.wait_for_url("**/checkout/**", timeout=15000)
        except Exception as e:
            logger.warning(
                f"URL did not change to /checkout/?state={self.page.url}. Error: {e}"
            )

        self.page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 2. Review Page
        # Handle Terms of Service (SSA)
        ssa_checkbox = self.page.locator("#accept_ssa")
        if ssa_checkbox.is_visible():
            if not ssa_checkbox.is_checked():
                logger.info("Accepting SSA...")
                ssa_checkbox.click()
                time.sleep(0.5)

        # Find Final Button
        final_btn = self.find_purchase_button()

        if final_btn and final_btn.is_visible():
            logger.info("Final Purchase button found.")

            # --- SAFETY CHECK ---
            logger.warning(
                "[SAFETY] Stopping before final click. Uncomment in 'buy_game.py' to enable."
            )
            # final_btn.click()
            # --------------------

            self.page.screenshot(path="checkout_ready.png")
            return True
        else:
            logger.error("Could not find final Purchase button.")
            self.page.screenshot(path="checkout_failed.png")
            return False


def buy_game(app_id):
    if not os.path.exists(STATE_FILE):
        logger.info("Session not found. Attempting login...")
        login()
        if not os.path.exists(STATE_FILE):
            logger.error("Login failed or cancelled.")
            return

    logger.info(f"Launching browser to buy AppID: {app_id}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=STATE_FILE, user_agent=USER_AGENT)
        page = context.new_page()

        checkout = SteamCheckout(page)

        try:
            # 1. Add to Cart
            logger.info(f"Adding AppID {app_id} to cart...")
            page.goto(f"https://store.steampowered.com/app/{app_id}")
            page.wait_for_load_state("networkidle")

            # Handle age gate
            if page.query_selector("#ageYear"):
                logger.info("Passing age gate...")
                page.select_option("#ageYear", "1990")
                page.click(".btnv6_blue_hoverfade")
                page.wait_for_load_state("networkidle")

            if page.query_selector(".already_in_library"):
                logger.info("Game already owned.")
                return

            # Add to cart selector from archive
            add_btn = page.query_selector(".btn_addtocart a")
            if add_btn:
                add_btn.click()
            else:
                logger.error("Add to cart button not found.")
                return

            # 2. Checkout
            checkout.checkout_with_wallet()

        except Exception as e:
            logger.error(f"Error: {e}")
            page.screenshot(path="error.png")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true", help="Force login")
    parser.add_argument("--app-id", type=str, help="App ID to purchase")
    args = parser.parse_args()

    if args.login:
        login()
    elif args.app_id:
        buy_game(args.app_id)
    else:
        parser.print_help()
