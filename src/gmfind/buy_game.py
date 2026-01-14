"""Steam game purchasing script using Playwright (Sync)."""

import argparse
import logging
import os
import time

from playwright.sync_api import sync_playwright

from gmfind.paths import get_screenshots_dir
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

    def clear_cart(self):
        """Remove all items currently in the cart using Steam API or DOM fallback."""
        logger.info("Navigating to Cart to ensure it's clear...")
        self.page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        time.sleep(1)

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
                logger.info("Found WebAPIToken, clearing cart via API...")
                self.page.evaluate(
                    """(t) => {
                    fetch('https://api.steampowered.com/IAccountCartService/DeleteCart/v1?access_token=' + t, {
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
                logger.info(f"Removing item from cart via DOM (Items: {remove_btns.count()})...")
                remove_btns.first.click()
                time.sleep(1)
            else:
                break

        logger.info("Cart is clear.")

    def checkout_with_wallet(self):
        """Complete checkout flow."""
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
                            logger.info(f"Checking SSA checkbox ({s})...")
                            ssa_loc.check()
                    else:
                        # Just click it if it's a styled element (like a div or span acting as a checkbox)
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
            logger.info("Final Purchase button found. Clicking...")
            final_btn.click()

            # 4. Verify Success
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
                logger.info("[SUCCESS] Purchase confirmed by Steam UI.")
                return True
            except Exception as e:
                # Check if we're actually on the receipt page even if wait_for failed
                if "thankyou" in self.page.url.lower() or "receipt" in self.page.url.lower():
                    logger.info("[SUCCESS] Purchase confirmed by URL.")
                    return True

                logger.error(f"[FAILURE] Verification timed out or failed: {e}")
                self.page.screenshot(path=str(get_screenshots_dir() / "purchase_failed.png"))
                return False
        else:
            logger.error("Could not find final Purchase button.")
            self.page.screenshot(path=str(get_screenshots_dir() / "checkout_failed.png"))
            return False


def buy_game(app_id, headless=True):
    if not os.path.exists(STATE_FILE):
        logger.info("Session not found. Attempting login...")
        login()
        if not os.path.exists(STATE_FILE):
            logger.error("Login failed or cancelled.")
            return

    logger.info(f"Launching browser to buy AppID: {app_id}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=STATE_FILE, user_agent=USER_AGENT)
        page = context.new_page()

        checkout = SteamCheckout(page)

        try:
            # 0. Clear Cart first
            checkout.clear_cart()

            # 1. Add to Cart
            logger.info(f"Adding AppID {app_id} to cart...")
            page.goto(f"https://store.steampowered.com/app/{app_id}")
            page.wait_for_load_state("networkidle")

            # Handle age gate
            if page.query_selector("#ageYear"):
                logger.info("Passing age gate...")
                page.select_option("#ageYear", "1990")
                page.click(".btnv6_blue_hoverfade")
                try:
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                except Exception:
                    logger.warning("Timeout waiting for age gate redirect")

            if page.query_selector(".already_in_library"):
                logger.info("Game already owned.")
                return

            # Check for Free to Play / Free content (skips "Install" prompt issues)
            # "Play Game" or "Free" price usually indicates we shouldn't "buy" it
            # in the standard way.
            if (
                page.get_by_text("Play Game").first.is_visible()
                or page.locator(".game_purchase_price").filter(has_text="Free").first.is_visible()
            ):
                logger.info("Game appears to be Free/Free to Play. Skipping purchase.")
                return

            # Find Add to Cart button
            logger.info("Looking for 'Add to Cart' button...")
            add_btn = None
            cart_selectors = [
                ".btn_addtocart a",
                "a:has-text('Add to Cart')",
                "#btn_add_to_cart",
                "[data-tooltip-text='Add to Cart']",
            ]

            for selector in cart_selectors:
                try:
                    if page.is_visible(selector):
                        add_btn = page.locator(selector).first
                        logger.info(f"Found Add to Cart with selector: {selector}")
                        break
                except Exception:
                    continue

            if not add_btn:
                try:
                    add_btn = page.wait_for_selector(".btn_addtocart a", timeout=3000)
                except Exception:
                    pass

            if add_btn:
                add_btn.click()
            else:
                logger.error("Add to cart button not found.")
                page.screenshot(path=str(get_screenshots_dir() / "add_to_cart_failed.png"))
                return False

            # 2. Checkout
            return checkout.checkout_with_wallet()

        except Exception as e:
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
