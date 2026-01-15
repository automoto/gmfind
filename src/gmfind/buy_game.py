"""Steam game purchasing script using Playwright (Sync)."""

import argparse
import logging
import os
import time

from gmfind.paths import get_screenshots_dir
from gmfind.playwright_utils import get_sync_playwright
from gmfind.steam_auth import STATE_FILE, USER_AGENT, login

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SteamCheckout:
    """Synchronous Steam checkout automation."""

    def __init__(self, page):
        self.page = page

    def find_purchase_button(self):
        """Find the final purchase/confirm button."""
        selectors = [
            "#purchase_button_bottom",  # Confirmed selector
            "#purchase_button",
            ".purchase_button",
            "#purchase_confirm_btn",
            'button[class*="purchase"]',
            'button[class*="Primary"]',
            "#submit_payment_button",
            "#purchase_button_bottom_text",
        ]

        for s in selectors:
            try:
                # Use .first to avoid strict mode violations if multiple exist
                loc = self.page.locator(s).filter(visible=True).first
                if loc.count() > 0:
                    return loc
            except Exception:
                continue

        # Fallback text search
        for text in ["Purchase", "Authenticate Payment"]:
            loc = self.page.get_by_text(text).filter(visible=True).last
            if loc.count() > 0:
                return loc

        return None

    def _cart_has_items(self) -> bool:
        """Check if the shopping cart has any items without attempting to clear."""
        # Use the same Remove button selectors that clear_cart() uses in its DOM fallback
        remove_btns = (
            self.page.get_by_role("button", name="Remove")
            .or_(self.page.get_by_text("Remove"))
            .filter(visible=True)
        )
        return bool(remove_btns.count() > 0)

    def clear_cart(self):
        """Remove all items currently in the cart using Steam API or DOM fallback."""
        print("[1/5] Checking shopping cart...", flush=True)
        logger.info("Navigating to Cart to ensure it's clear...")
        self.page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        time.sleep(1)

        # Check if cart is already empty before attempting to clear
        if not self._cart_has_items():
            print("      Cart is already empty, skipping clear.", flush=True)
            logger.info("Cart is already empty, skipping clear.")
            return

        print("      Cart has items, clearing...", flush=True)
        logger.info("Cart has items, proceeding to clear...")

        # 1. Attempt API clear if token is available
        try:
            token = self.page.evaluate("""() => {
                try {
                    // Try to find token in SSR data
                    for (let i=0; i < window.SSR.loaderData.length; i++) {
                        const data = JSON.parse(window.SSR.loaderData[i]);
                        if (data.strWebAPIToken) return data.strWebAPIToken;
                    }
                } catch (e) {}
                return null;
            }""")

            if token:
                print("      Clearing cart via API...", flush=True)
                logger.info("Found WebAPIToken, clearing cart via API...")
                self.page.evaluate(
                    """(t) => {
                    const url = 'https://api.steampowered.com/IAccountCartService/DeleteCart/v1';
                    fetch(url + '?access_token=' + t, {
                        method: 'POST',
                        body: new FormData()
                    });
                }""",
                    token,
                )
                time.sleep(1)
                self.page.reload()
                time.sleep(1)
        except Exception as e:
            logger.debug(f"API cart clear failed: {e}")

        # 2. DOM Fallback (Remove items one by one)
        while True:
            remove_btns = (
                self.page.get_by_role("button", name="Remove")
                .or_(self.page.get_by_text("Remove"))
                .filter(visible=True)
            )
            if remove_btns.count() > 0:
                remaining = remove_btns.count()
                print(f"      Removing item from cart ({remaining} remaining)...", flush=True)
                logger.info(f"Removing item from cart via DOM (Items: {remove_btns.count()})...")
                remove_btns.first.click()
                time.sleep(1)
            else:
                break

        print("      Cart cleared.", flush=True)
        logger.info("Cart is clear.")

    def checkout_with_wallet(self):
        """Complete checkout flow."""
        print("[4/5] Navigating to checkout...", flush=True)
        logger.info("Navigating to Cart...")
        self.page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        time.sleep(2)

        # 1. Select recipient choice to ensure cart is ready for checkout
        recipient_selectors = [
            "button:has-text('For my account')",
            "button:has-text('Purchase for myself')",
            "#btn_purchase_self",
        ]

        for s in recipient_selectors:
            try:
                loc = self.page.locator(s).filter(visible=True).first
                if loc.count() > 0:
                    logger.info(f"Selecting recipient using: {s}")
                    loc.click()
                    time.sleep(1)
                    break
            except Exception:
                continue

        # 2. Directly navigate to the checkout page as a more robust method than clicking
        logger.info("Navigating directly to checkout URL...")
        self.page.goto(
            "https://checkout.steampowered.com/checkout/?accountcart=1",
            wait_until="networkidle",
        )
        time.sleep(2)

        # 3. Final Review Page
        # SSA (Steam Subscriber Agreement) check - Prioritize #accept_ssa
        ssa_selectors = ["#accept_ssa", "[name='accept_ssa']"]
        for s in ssa_selectors:
            try:
                ssa_loc = self.page.locator(s).filter(visible=True).first
                if ssa_loc.count() > 0:
                    # Check if it's a checkbox input
                    is_checkbox = self.page.evaluate(
                        "el => el.tagName === 'INPUT' && el.type === 'checkbox'",
                        ssa_loc.element_handle(),
                    )

                    if is_checkbox:
                        if not ssa_loc.is_checked():
                            print("      Accepting Steam Subscriber Agreement...", flush=True)
                            logger.info(f"Checking SSA checkbox ({s})...")
                            ssa_loc.check()
                    else:
                        # Click styled elements (div/span acting as checkbox)
                        print("      Accepting Steam Subscriber Agreement...", flush=True)
                        logger.info(f"Clicking SSA agreement element ({s})...")
                        ssa_loc.click()

                    time.sleep(0.5)
                    break
            except Exception as e:
                logger.debug(f"SSA selector {s} failed: {e}")
                continue

        # Find Final Button
        final_btn = self.find_purchase_button()

        if final_btn and final_btn.is_visible():
            print("[5/5] Completing purchase...", flush=True)
            logger.info("Final Purchase button found. Clicking...")
            final_btn.click()

            # 4. Verify Success
            print("      Waiting for confirmation...", flush=True)
            logger.info("Waiting for purchase confirmation...")
            try:
                # Use a combined locator but take .first to avoid strict mode violations
                # matching multiple "Thank you" elements.
                success_indicator = (
                    self.page.locator("#receipt_link")
                    .or_(self.page.locator(".checkout_receipt_area"))
                    .or_(self.page.get_by_text("Thank you"))
                    .first
                )

                success_indicator.wait_for(state="visible", timeout=30000)
                print("      Purchase confirmed!", flush=True)
                logger.info("[SUCCESS] Purchase confirmed by Steam UI.")
                return True
            except Exception as e:
                # Check if we're actually on the receipt page even if wait_for failed
                if "thankyou" in self.page.url.lower() or "receipt" in self.page.url.lower():
                    print("      Purchase confirmed!", flush=True)
                    logger.info("[SUCCESS] Purchase confirmed by URL.")
                    return True

                print("      Purchase verification failed.", flush=True)
                logger.error(f"[FAILURE] Verification timed out or failed: {e}")
                self.page.screenshot(path=str(get_screenshots_dir() / "purchase_failed.png"))
                return False
        else:
            print("      Could not find purchase button.", flush=True)
            logger.error("Could not find final Purchase button.")
            self.page.screenshot(path=str(get_screenshots_dir() / "checkout_failed.png"))
            return False


def buy_game(app_id, headless=True):
    if not os.path.exists(STATE_FILE):
        print("Session not found. Attempting login...", flush=True)
        logger.info("Session not found. Attempting login...")
        login(headless=headless)
        if not os.path.exists(STATE_FILE):
            print("Login failed or cancelled.", flush=True)
            logger.error("Login failed or cancelled.")
            return

    print(f"\nStarting purchase for App ID: {app_id}", flush=True)
    logger.info(f"Launching browser to buy AppID: {app_id}...")

    with get_sync_playwright()() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=STATE_FILE, user_agent=USER_AGENT)
        page = context.new_page()

        checkout = SteamCheckout(page)

        try:
            # 0. Clear Cart first
            checkout.clear_cart()

            # 1. Add to Cart
            print("[2/5] Opening product page...", flush=True)
            logger.info(f"Adding AppID {app_id} to cart...")
            page.goto(f"https://store.steampowered.com/app/{app_id}")
            page.wait_for_load_state("networkidle")

            # Handle age gate
            if page.query_selector("#ageYear"):
                print("      Passing age verification...", flush=True)
                logger.info("Passing age gate...")
                page.select_option("#ageYear", "1990")
                page.click(".btnv6_blue_hoverfade")
                try:
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                except Exception:
                    logger.warning("Timeout waiting for age gate redirect")

            if page.query_selector(".already_in_library"):
                print("      Game already owned. Aborting.", flush=True)
                logger.info("Game already owned.")
                return

            # Find and click Add to Cart button
            print("[3/5] Adding to cart...", flush=True)
            logger.info("Looking for 'Add to Cart' button...")

            cart_btn = page.get_by_text("Add to Cart", exact=True).first
            cart_btn.wait_for(state="visible", timeout=10000)
            cart_btn.click()
            print("      Added to cart.", flush=True)
            logger.info("Clicked Add to Cart")
            time.sleep(2)

            # 2. Checkout
            return checkout.checkout_with_wallet()

        except Exception as e:
            print(f"      Error: {e}", flush=True)
            logger.error(f"Error: {e}")
            page.screenshot(path=str(get_screenshots_dir() / "error.png"))
            return False
        finally:
            # If headful, wait a bit so user can see
            if not headless:
                time.sleep(5)
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
