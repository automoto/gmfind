"""Steam checkout flow automation."""

import asyncio
import logging
import re

from playwright.async_api import Page

from .automation import SteamStoreAutomation, SteamStoreError

logger = logging.getLogger(__name__)


class CheckoutFlow:
    """Handles the Steam checkout process."""

    def __init__(self, store: SteamStoreAutomation):
        """Initialize checkout flow.

        Args:
            store: SteamStoreAutomation instance with active session.
        """
        self.store = store

    @property
    def _page(self) -> Page:
        """Get the browser page."""
        if not self.store._page:
            raise SteamStoreError("Browser not started")
        return self.store._page

    async def _find_checkout_button(self):
        """Find a checkout/continue/purchase button on the current page."""
        # Try common selectors first
        selectors = [
            '#purchase_button',
            '.purchase_button',
            '#purchase_confirm_btn',
            'button[class*="purchase"]',
            'button[class*="Primary"]',
        ]

        for selector in selectors:
            btn = await self._page.query_selector(selector)
            if btn:
                visible = await btn.is_visible()
                if visible:
                    return btn

        # Search by text content - check all buttons and links
        elements = await self._page.query_selector_all('button, a, input[type="submit"]')
        for elem in elements:
            try:
                visible = await elem.is_visible()
                if not visible:
                    continue
                text = await elem.inner_text()
                text_lower = text.lower().strip()
                # Look for purchase/continue buttons but not "back" or "cancel"
                if any(x in text_lower for x in ["purchase", "continue", "place order", "buy", "confirm"]):
                    if not any(x in text_lower for x in ["back", "cancel", "shopping"]):
                        logger.debug(f"Found checkout button by text: '{text.strip()}'")
                        return elem
            except Exception:
                continue

        # Also try finding by ID patterns
        id_patterns = ['#purchase_button', '#btn_purchase', '#purchase', '#confirm_purchase']
        for pattern in id_patterns:
            elem = await self._page.query_selector(pattern)
            if elem:
                try:
                    visible = await elem.is_visible()
                    if visible:
                        logger.debug(f"Found checkout button by ID: {pattern}")
                        return elem
                except Exception:
                    continue

        return None

    async def go_to_cart(self) -> dict:
        """Navigate to shopping cart.

        Returns:
            Cart info with items and total.
        """
        await self._page.goto(
            "https://store.steampowered.com/cart/", wait_until="networkidle"
        )
        await asyncio.sleep(2)

        # Get cart items
        items = []
        cart_rows = await self._page.query_selector_all('.cart_item, .cart_row')

        for row in cart_rows:
            name_elem = await row.query_selector('.cart_item_desc a, .app_name')
            price_elem = await row.query_selector('.cart_item_price .price, .price')

            if name_elem:
                name = await name_elem.inner_text()
                price = 0.0
                if price_elem:
                    price_text = await price_elem.inner_text()
                    match = re.search(r'[\d.,]+', price_text)
                    if match:
                        price = float(match.group().replace(",", "."))
                items.append({"name": name.strip(), "price": price})

        # Get total
        total = 0.0
        total_elem = await self._page.query_selector(
            '.cart_total_row .price, #cart_estimated_total'
        )
        if total_elem:
            total_text = await total_elem.inner_text()
            match = re.search(r'[\d.,]+', total_text)
            if match:
                total = float(match.group().replace(",", "."))

        return {"items": items, "total": total}

    async def checkout_with_wallet(self) -> bool:
        """Complete checkout using Steam Wallet only.

        Returns:
            True if purchase successful.

        Raises:
            SteamStoreError: If checkout fails or wallet balance insufficient.
        """
        # Always navigate to cart page to ensure clean state
        await self._page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        await asyncio.sleep(3)

        # Take screenshot for debugging
        await self._page.screenshot(path="debug_cart.png")
        logger.debug(f"Cart page URL: {self._page.url}")

        # Click continue to payment / checkout - try multiple selectors
        purchase_selectors = [
            '#btn_purchase_self',
            '.btn_checkout',
            '.checkout_btn',
            'button.Primary',
            'a.Primary',
            '[class*="CheckoutButton"]',
            'button[class*="purchase"]',
            'a[class*="purchase"]',
            'a[class*="continue"]',
            'button[class*="continue"]',
        ]

        purchase_btn = None
        for selector in purchase_selectors:
            elements = await self._page.query_selector_all(selector)
            for elem in elements:
                try:
                    visible = await elem.is_visible()
                    if visible:
                        purchase_btn = elem
                        logger.debug(f"Found visible purchase button with selector: {selector}")
                        break
                except Exception:
                    continue
            if purchase_btn:
                break

        # Try finding by text content if selectors fail
        if not purchase_btn:
            buttons = await self._page.query_selector_all('button, a.btn, a[class*="btn"], a[class*="Btn"]')
            for btn in buttons:
                try:
                    visible = await btn.is_visible()
                    if not visible:
                        continue
                    text = await btn.inner_text()
                    text_lower = text.lower()
                    if any(x in text_lower for x in ["continue to payment", "purchase", "checkout"]):
                        purchase_btn = btn
                        logger.debug(f"Found purchase button by text: {text}")
                        break
                except Exception:
                    continue

        if not purchase_btn:
            raise SteamStoreError("Purchase button not found - check debug_cart.png")

        # Scroll to button and click
        await purchase_btn.scroll_into_view_if_needed()
        await asyncio.sleep(1)
        try:
            await purchase_btn.click(timeout=10000)
        except Exception:
            # Try force click if normal click fails
            logger.debug("Normal click failed, trying force click")
            await purchase_btn.click(force=True)
        await asyncio.sleep(3)

        # Wait for checkout page to load
        try:
            await self._page.wait_for_url("**/checkout/**", timeout=10000)
        except Exception:
            logger.debug(f"Checkout URL: {self._page.url}")

        await asyncio.sleep(2)
        await self._page.screenshot(path="debug_checkout.png")

        # Check for insufficient wallet balance warning - only in error elements
        error_elem = await self._page.query_selector(
            '.checkout_error, .error_display, .error_message, [class*="error"]'
        )
        if error_elem:
            try:
                error_text = await error_elem.inner_text()
                if "wallet balance" in error_text.lower() and "too low" in error_text.lower():
                    raise SteamStoreError(
                        "Steam Wallet balance is too low to cover this transaction. "
                        "Please add funds to your Steam Wallet first."
                    )
            except Exception:
                pass

        # The checkout flow may have multiple steps:
        # Step 1: Payment Info (select payment method)
        # Step 2: Review + Purchase (confirm)

        # Look for "Continue" or "Purchase" button
        continue_btn = await self._find_checkout_button()
        if not continue_btn:
            raise SteamStoreError("Checkout button not found - check debug_checkout.png")

        logger.info("Clicking checkout button...")
        await continue_btn.click()
        await asyncio.sleep(3)

        # Check again if we're on a review page
        await self._page.screenshot(path="debug_review.png")
        page_content = await self._page.content()

        # If there's a review step, we need to click again
        if "review" in page_content.lower() or "confirm" in page_content.lower():
            logger.info("On review page, looking for final purchase button...")

            # Accept Steam Subscriber Agreement if present
            # Wait for page to fully load before interacting
            await asyncio.sleep(5)
            logger.debug("Looking for SSA checkbox...")
            ssa_checkbox = await self._page.query_selector('#accept_ssa')
            if ssa_checkbox:
                try:
                    is_visible = await ssa_checkbox.is_visible()
                    logger.debug(f"SSA checkbox found, visible={is_visible}")
                    if is_visible:
                        is_checked = await ssa_checkbox.is_checked()
                        logger.debug(f"SSA checkbox checked={is_checked}")
                        if not is_checked:
                            logger.info("Accepting Steam Subscriber Agreement...")
                            await ssa_checkbox.click()
                            await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to click SSA checkbox: {e}")
                    # Try clicking the label instead
                    try:
                        ssa_label = await self._page.query_selector('label[for="accept_ssa"]')
                        if ssa_label:
                            await ssa_label.click()
                            await asyncio.sleep(1)
                    except Exception:
                        pass
            else:
                logger.debug("SSA checkbox not found")

            # Find the final purchase button
            final_btn = await self._find_checkout_button()
            if final_btn:
                logger.info("Clicking final purchase button...")
                await final_btn.click()

        # Wait for confirmation
        for i in range(30):
            await asyncio.sleep(1)

            # Check for success - element selectors
            success_elem = await self._page.query_selector(
                '.receipt_success, .checkout_success, .transactionSuccess, [class*="success"]'
            )
            if success_elem:
                logger.info("Purchase completed successfully!")
                return True

            # Check page content for success message
            page_content = await self._page.content()
            if "thank you for your purchase" in page_content.lower():
                logger.info("Purchase completed successfully!")
                return True

            # Check for receipt/confirmation URL
            if "/receipt" in self._page.url or "transid=" in self._page.url:
                logger.info("Purchase completed - on receipt page")
                return True

            # Check for error
            error_elem = await self._page.query_selector(
                '.checkout_error, .error_display, .purchase_error, [class*="error"]'
            )
            if error_elem:
                error_text = await error_elem.inner_text()
                if error_text.strip():
                    raise SteamStoreError(f"Checkout failed: {error_text}")

            # Log progress
            if i % 5 == 0:
                logger.debug(f"Waiting for purchase confirmation... ({i}/30)")

        raise SteamStoreError("Checkout timed out")

    async def remove_all_from_cart(self):
        """Remove all items from the cart using 'Remove all items' link."""
        # Navigate to cart page
        await self._page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
        await asyncio.sleep(2)
        await self._page.screenshot(path="debug_cart_remove.png")

        # Check if cart is already empty
        page_content = await self._page.content()
        if "your cart is empty" in page_content.lower():
            logger.info("Cart is already empty")
            return

        # Look for "Remove all items" link - search all clickable elements
        remove_all_link = None

        # Try by text content - check all clickable elements and divs
        all_elements = await self._page.query_selector_all('a, button, span, div')
        for elem in all_elements:
            try:
                text = await elem.inner_text()
                text_lower = text.lower().strip()
                # Look for various "remove all" patterns
                if any(pattern in text_lower for pattern in ["remove all", "clear cart", "empty cart"]):
                    visible = await elem.is_visible()
                    if visible:
                        # Make sure it's a reasonably small element (not a container)
                        box = await elem.bounding_box()
                        if box and box['width'] < 300 and box['height'] < 100:
                            remove_all_link = elem
                            logger.debug(f"Found 'Remove all' link: '{text.strip()}'")
                            break
            except Exception:
                continue

        if not remove_all_link:
            # Try common selectors for Steam's cart
            selectors = [
                'a[href*="remove"]',
                '[class*="removeAll"]',
                '[class*="RemoveAll"]',
                '[class*="CartRemove"]',
                '[class*="remove_all"]',
                '[class*="RemoveLink"]',
                '[class*="removelink"]',
                '[data-action="remove-all"]',
            ]
            for selector in selectors:
                elem = await self._page.query_selector(selector)
                if elem:
                    try:
                        visible = await elem.is_visible()
                        if visible:
                            remove_all_link = elem
                            logger.debug(f"Found remove all link with selector: {selector}")
                            break
                    except Exception:
                        continue

        if not remove_all_link:
            # Log all visible text containing "remove" for debugging
            logger.debug("Searching for any 'remove' text on page...")
            for elem in all_elements:
                try:
                    text = await elem.inner_text()
                    if "remove" in text.lower() and len(text.strip()) < 50:
                        visible = await elem.is_visible()
                        tag = await elem.evaluate("el => el.tagName")
                        classes = await elem.get_attribute("class") or ""
                        logger.debug(f"  Found 'remove' text: tag={tag}, visible={visible}, text='{text.strip()}', class='{classes[:40]}'")
                except Exception:
                    continue
            raise SteamStoreError("Could not find 'Remove all items' link - check debug_cart_remove.png")

        # Click the remove all link
        logger.info("Clicking 'Remove all items'...")
        await remove_all_link.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await remove_all_link.click()
        await asyncio.sleep(3)

        # Verify cart is now empty
        page_content = await self._page.content()
        if "your cart is empty" in page_content.lower():
            logger.info("Cart cleared successfully")
        else:
            # Take another screenshot and raise error
            await self._page.screenshot(path="debug_cart_after_remove.png")
            raise SteamStoreError("Failed to clear cart - check debug_cart_after_remove.png")
