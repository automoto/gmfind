#!/usr/bin/env python3
"""Integration test for checkout flow - verifies selectors without purchasing."""

import asyncio
import logging

from src.config import load_config
from src.store import SteamStoreAutomation, CheckoutFlow

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test game - use a cheap/free game for testing
# Portal 2: 620, Terraria: 105, Half-Life 2: 220
TEST_APP_ID = 620  # Portal 2


async def test_checkout_flow():
    """Test the checkout flow without completing purchase."""
    config = load_config()

    store = SteamStoreAutomation(
        username=config.steam.username,
        password=config.steam.password,
        headless=False,  # Run with visible browser for debugging
    )

    await store.start()

    try:
        # Step 1: Login
        logger.info("=" * 60)
        logger.info("STEP 1: Logging in...")
        logger.info("=" * 60)
        await store.login()
        logger.info("Login successful!")

        # Step 2: Clear cart
        logger.info("=" * 60)
        logger.info("STEP 2: Clearing cart...")
        logger.info("=" * 60)
        checkout = CheckoutFlow(store)
        await checkout.remove_all_from_cart()
        logger.info("Cart cleared!")

        # Step 3: Navigate to game
        logger.info("=" * 60)
        logger.info(f"STEP 3: Navigating to game {TEST_APP_ID}...")
        logger.info("=" * 60)
        game_info = await store.navigate_to_game(TEST_APP_ID)
        logger.info(f"Game info: {game_info}")

        # Step 4: Add to cart
        logger.info("=" * 60)
        logger.info("STEP 4: Adding to cart...")
        logger.info("=" * 60)
        success = await store.add_to_cart(TEST_APP_ID)
        logger.info(f"Add to cart result: {success}")

        # Step 5: Go to cart and test selectors
        logger.info("=" * 60)
        logger.info("STEP 5: Testing cart page selectors...")
        logger.info("=" * 60)
        await test_cart_selectors(checkout)

        # Step 6: Click continue to payment and test checkout selectors
        logger.info("=" * 60)
        logger.info("STEP 6: Testing checkout page selectors...")
        logger.info("=" * 60)
        await test_checkout_selectors(checkout)

        logger.info("=" * 60)
        logger.info("TEST COMPLETE - All selectors verified!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await store.close()


async def test_cart_selectors(checkout: CheckoutFlow):
    """Test all cart page selectors."""
    page = checkout._page

    await page.goto("https://store.steampowered.com/cart/", wait_until="networkidle")
    await asyncio.sleep(2)
    await page.screenshot(path="test_cart.png")

    logger.info(f"Cart URL: {page.url}")

    # Test cart item selectors
    cart_items = await page.query_selector_all('.cart_item, .cart_row, [class*="Cart"]')
    logger.info(f"Found {len(cart_items)} cart items with standard selectors")

    # Test remove button selectors
    remove_selectors = [
        '.remove_link',
        '.btn_remove',
        '[class*="remove"]',
        '[class*="Remove"]',
    ]
    for selector in remove_selectors:
        elem = await page.query_selector(selector)
        logger.info(f"Remove selector '{selector}': {'FOUND' if elem else 'NOT FOUND'}")

    # Also try text search
    links = await page.query_selector_all('a, button, span')
    remove_by_text = None
    for link in links:
        text = await link.inner_text()
        if text.strip().lower() in ["remove", "x", "×", "delete"]:
            remove_by_text = link
            break
    logger.info(f"Remove by text 'Remove/X': {'FOUND' if remove_by_text else 'NOT FOUND'}")

    # Look for small buttons that might be X icons
    logger.info("Looking for small buttons (potential X icons)...")
    cart_items = await page.query_selector_all('[class*="Cart"], [class*="cart"], .cart_item')
    logger.info(f"Found {len(cart_items)} cart-related elements")
    for i, item in enumerate(cart_items[:5]):  # Check first 5
        btns = await item.query_selector_all('button, a, span')
        for btn in btns:
            try:
                visible = await btn.is_visible()
                if visible:
                    box = await btn.bounding_box()
                    text = await btn.inner_text()
                    classes = await btn.get_attribute("class") or ""
                    if box:
                        logger.info(f"  Cart item {i} button: size={box['width']:.0f}x{box['height']:.0f}, text='{text.strip()[:20]}', class='{classes[:40]}'")
            except Exception:
                pass

    # Test checkout/purchase button selectors
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
    for selector in purchase_selectors:
        elem = await page.query_selector(selector)
        if elem:
            text = await elem.inner_text()
            visible = await elem.is_visible()
            logger.info(f"Purchase selector '{selector}': FOUND - text='{text}', visible={visible}")
        else:
            logger.info(f"Purchase selector '{selector}': NOT FOUND")

    # Try text search for purchase button
    buttons = await page.query_selector_all('button, a.btn, a[class*="btn"], a[class*="Btn"]')
    logger.info(f"Found {len(buttons)} button-like elements")
    for btn in buttons:
        text = await btn.inner_text()
        text_lower = text.lower().strip()
        if any(x in text_lower for x in ["continue", "purchase", "checkout", "payment"]):
            visible = await btn.is_visible()
            tag = await btn.evaluate("el => el.tagName")
            classes = await btn.get_attribute("class") or ""
            logger.info(f"  Potential checkout button: tag={tag}, text='{text.strip()}', visible={visible}, class='{classes[:50]}'")


async def test_checkout_selectors(checkout: CheckoutFlow):
    """Test checkout page selectors after clicking continue to payment."""
    page = checkout._page

    # First, find and click the continue to payment button
    logger.info("Looking for 'Continue to payment' button...")

    # Try to find by text
    buttons = await page.query_selector_all('button, a')
    continue_btn = None
    for btn in buttons:
        text = await btn.inner_text()
        if "continue to payment" in text.lower():
            visible = await btn.is_visible()
            if visible:
                continue_btn = btn
                logger.info(f"Found 'Continue to payment' button: {text.strip()}")
                break

    if not continue_btn:
        logger.error("Could not find 'Continue to payment' button!")
        # Dump all visible buttons for debugging
        logger.info("All visible buttons on page:")
        for btn in buttons:
            try:
                visible = await btn.is_visible()
                if visible:
                    text = await btn.inner_text()
                    if text.strip():
                        logger.info(f"  - '{text.strip()[:50]}'")
            except:
                pass
        return

    # Click it
    logger.info("Clicking 'Continue to payment'...")
    await continue_btn.click()
    await asyncio.sleep(3)

    await page.screenshot(path="test_checkout.png")
    logger.info(f"Checkout URL: {page.url}")

    # Test wallet payment selectors
    wallet_selectors = [
        '#payment_method_wallet',
        'input[value="steamaccount"]',
        '.payment_method_wallet',
        '[class*="wallet"]',
        '[class*="Wallet"]',
    ]
    for selector in wallet_selectors:
        elem = await page.query_selector(selector)
        if elem:
            visible = await elem.is_visible()
            logger.info(f"Wallet selector '{selector}': FOUND, visible={visible}")
        else:
            logger.info(f"Wallet selector '{selector}': NOT FOUND")

    # Test SSA checkbox selectors
    ssa_selectors = [
        '#accept_ssa',
        'input[name="accept_ssa"]',
        '[class*="ssa"]',
        '[class*="SSA"]',
        'input[type="checkbox"]',
    ]
    for selector in ssa_selectors:
        elem = await page.query_selector(selector)
        if elem:
            visible = await elem.is_visible()
            logger.info(f"SSA selector '{selector}': FOUND, visible={visible}")
        else:
            logger.info(f"SSA selector '{selector}': NOT FOUND")

    # Test final purchase button selectors
    final_selectors = [
        '#purchase_button',
        '.purchase_button',
        '#purchase_confirm_btn',
        'button[class*="purchase"]',
        'button[class*="Primary"]',
        '[class*="ConfirmPurchase"]',
    ]
    for selector in final_selectors:
        elem = await page.query_selector(selector)
        if elem:
            text = await elem.inner_text()
            visible = await elem.is_visible()
            logger.info(f"Final purchase selector '{selector}': FOUND - text='{text}', visible={visible}")
        else:
            logger.info(f"Final purchase selector '{selector}': NOT FOUND")

    # Search by text
    logger.info("Searching for purchase button by text...")
    buttons = await page.query_selector_all('button')
    for btn in buttons:
        text = await btn.inner_text()
        visible = await btn.is_visible()
        if visible and text.strip():
            logger.info(f"  Visible button: '{text.strip()}'")


if __name__ == "__main__":
    asyncio.run(test_checkout_flow())
