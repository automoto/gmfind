"""Steam store browser automation using Playwright."""

import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

# Path to save session state
SESSION_FILE = Path("steam_session.json")


class SteamStoreError(Exception):
    """Raised when Steam store automation fails."""

    pass


class SteamStoreAutomation:
    """Automates Steam store interactions using Playwright."""

    STEAM_LOGIN_URL = "https://store.steampowered.com/login/"
    STEAM_STORE_URL = "https://store.steampowered.com"
    STEAM_CART_URL = "https://store.steampowered.com/cart/"

    def __init__(self, username: str, password: str, headless: bool = False):
        """Initialize the Steam store automation.

        Args:
            username: Steam username.
            password: Steam password.
            headless: Run browser in headless mode.
        """
        self.username = username
        self.password = password
        self.headless = headless
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._logged_in = False
        self._playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Start the browser and create a context."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Try to load saved session state
        storage_state = None
        if SESSION_FILE.exists():
            logger.info("Loading saved session...")
            storage_state = str(SESSION_FILE)

        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            storage_state=storage_state,
        )
        self._page = await self._context.new_page()

    async def save_session(self):
        """Save the current session state for reuse."""
        if self._context:
            await self._context.storage_state(path=str(SESSION_FILE))
            logger.info(f"Session saved to {SESSION_FILE}")

    async def close(self):
        """Close the browser, saving session state."""
        if self._context:
            # Save session state before closing
            try:
                await self.save_session()
            except Exception as e:
                logger.warning(f"Failed to save session: {e}")
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def login(self) -> bool:
        """Log in to Steam.

        Returns:
            True if login successful, False otherwise.

        Raises:
            SteamStoreError: If login fails after retries.
        """
        if self._logged_in:
            return True

        if not self._page:
            raise SteamStoreError("Browser not started. Call start() first.")

        logger.info("Logging in to Steam...")

        # First, go to the store and check if session is still valid
        await self._page.goto(self.STEAM_STORE_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # Check if already logged in from saved session
        if await self._is_logged_in():
            logger.info("Already logged in to Steam (session restored)")
            self._logged_in = True
            return True

        # Session invalid or not present, do full login
        logger.info("Session not valid, performing login...")
        await self._page.goto(self.STEAM_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(3)  # Wait for page to fully load

        # Check if already logged in (redirected from login page)
        if await self._is_logged_in():
            logger.info("Already logged in to Steam")
            self._logged_in = True
            return True

        # Steam's new login page selectors (2024+)
        # Find and fill username
        username_selectors = [
            'input[type="text"]._2GBWeup5cttgbTw8FM3tfx',
            'input[type="text"][class*="newlogindialog"]',
            'input[type="text"][class*="login"]',
            'form input[type="text"]',
            'input[name="username"]',
        ]

        username_input = None
        for selector in username_selectors:
            username_input = await self._page.query_selector(selector)
            if username_input:
                logger.debug(f"Found username input with selector: {selector}")
                break

        if not username_input:
            # Take screenshot for debugging
            await self._page.screenshot(path="debug_login.png")
            raise SteamStoreError("Could not find username input field. Screenshot saved to debug_login.png")

        await username_input.fill(self.username)
        await asyncio.sleep(0.5)

        # Find and fill password
        password_selectors = [
            'input[type="password"]._2GBWeup5cttgbTw8FM3tfx',
            'input[type="password"][class*="newlogindialog"]',
            'input[type="password"]',
        ]

        password_input = None
        for selector in password_selectors:
            password_input = await self._page.query_selector(selector)
            if password_input:
                logger.debug(f"Found password input with selector: {selector}")
                break

        if not password_input:
            raise SteamStoreError("Could not find password input field")

        await password_input.fill(self.password)
        await asyncio.sleep(0.5)

        # Press Enter to submit the login form
        logger.debug("Pressing Enter to submit login")
        await password_input.press("Enter")

        # Wait for login to complete
        verification_warned = False
        for i in range(120):  # Wait up to 2 minutes total
            await asyncio.sleep(1)

            try:
                current_url = self._page.url
                logger.debug(f"Login wait {i+1}/120 - URL: {current_url}")

                # Check if logged in
                if await self._is_logged_in():
                    logger.info("Successfully logged in to Steam")
                    self._logged_in = True
                    return True

                # Check for email verification prompt
                needs_verification = await self._page.query_selector('text="Enter the code"') or \
                   await self._page.query_selector('[class*="newlogindialog_ConfirmationEntryContainer"]') or \
                   await self._page.query_selector('[class*="verifycode"]') or \
                   await self._page.query_selector('[class*="twofactor"]')

                if needs_verification and not verification_warned:
                    logger.warning("Email verification required. Please enter the code in the browser window.")
                    verification_warned = True

                # Check for CAPTCHA
                if await self._page.query_selector('[class*="captcha"], #captcha'):
                    logger.warning("CAPTCHA detected. Please solve it in the browser window.")

                # Check for error messages
                error = await self._page.query_selector('[class*="FormError"], .form_error, [class*="error"]')
                if error:
                    error_text = await error.inner_text()
                    if error_text and "error" in error_text.lower():
                        raise SteamStoreError(f"Login failed: {error_text}")

            except Exception as e:
                if "Execution context was destroyed" in str(e) or "navigation" in str(e).lower():
                    # Page is navigating, this is expected - wait and check again
                    logger.debug("Page navigating, waiting...")
                    await asyncio.sleep(2)
                    continue
                raise

        raise SteamStoreError("Login timed out")

    async def _is_logged_in(self) -> bool:
        """Check if currently logged in to Steam."""
        if not self._page:
            return False

        # Check various indicators of being logged in
        logged_in_selectors = [
            '#account_pulldown',
            '.user_avatar',
            '[class*="accountName"]',
            '.playerAvatar',
            '#global_action_menu .user_avatar',
            'a[href*="/logout/"]',
            '.persona_name',
        ]

        for selector in logged_in_selectors:
            elem = await self._page.query_selector(selector)
            if elem:
                logger.debug(f"Logged in - found element: {selector}")
                return True

        # Also check if we're no longer on the login page
        current_url = self._page.url
        if "/login" not in current_url and "store.steampowered.com" in current_url:
            # We're on the store but not login page, might be logged in
            # Do a more thorough check
            page_content = await self._page.content()
            if "Sign in" not in page_content or "logout" in page_content.lower():
                logger.debug("Logged in - no longer on login page")
                return True

        return False

    async def get_wallet_balance(self) -> float:
        """Get the current Steam Wallet balance.

        Returns:
            Wallet balance in USD.

        Raises:
            SteamStoreError: If unable to fetch balance.
        """
        if not self._page or not self._logged_in:
            raise SteamStoreError("Not logged in")

        # Navigate to account page or wallet page
        await self._page.goto(
            "https://store.steampowered.com/account/", wait_until="networkidle"
        )
        await asyncio.sleep(2)

        # Find wallet balance
        wallet_elem = await self._page.query_selector(
            '.accountBalance .price, .account_balance_value, .wallet_balance'
        )

        if not wallet_elem:
            # Try alternative location
            await self._page.goto(
                "https://store.steampowered.com/account/store_transactions/",
                wait_until="networkidle",
            )
            await asyncio.sleep(2)
            wallet_elem = await self._page.query_selector(
                '.accountBalance, .wallet_balance'
            )

        if not wallet_elem:
            raise SteamStoreError("Could not find wallet balance")

        balance_text = await wallet_elem.inner_text()

        # Parse balance (e.g., "$23.45" or "23,45€")
        match = re.search(r'[\d.,]+', balance_text)
        if not match:
            raise SteamStoreError(f"Could not parse wallet balance: {balance_text}")

        # Handle different decimal separators
        balance_str = match.group().replace(",", ".")
        return float(balance_str)

    async def navigate_to_game(self, app_id: int) -> dict:
        """Navigate to a game's store page.

        Args:
            app_id: Steam app ID.

        Returns:
            Dictionary with game info (name, price, available).
        """
        if not self._page:
            raise SteamStoreError("Browser not started")

        url = f"https://store.steampowered.com/app/{app_id}/"
        await self._page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)

        # Handle age verification if present
        age_gate = await self._page.query_selector('#ageYear, .agegate_birthday_selector')
        if age_gate:
            # Select year (1990)
            await self._page.select_option('#ageYear', '1990')
            await asyncio.sleep(0.5)

            # Click view page button
            view_btn = await self._page.query_selector('#view_product_page_btn, .btnv6_blue_hoverfade')
            if view_btn:
                await view_btn.click()
                await asyncio.sleep(2)

        # Get game info
        name_elem = await self._page.query_selector('.apphub_AppName, #appHubAppName')
        name = await name_elem.inner_text() if name_elem else "Unknown"

        # Check price
        price = 0.0
        price_elem = await self._page.query_selector(
            '.game_purchase_price.price, .discount_final_price'
        )
        if price_elem:
            price_text = await price_elem.inner_text()
            match = re.search(r'[\d.,]+', price_text)
            if match:
                price = float(match.group().replace(",", "."))
        elif await self._page.query_selector('.game_area_comingsoon'):
            return {"name": name, "price": 0, "available": False, "reason": "Coming soon"}

        # Check if already owned
        owned_elem = await self._page.query_selector('.already_in_library, .game_area_already_owned')
        if owned_elem:
            return {"name": name, "price": price, "available": False, "reason": "Already owned"}

        return {"name": name, "price": price, "available": True}

    async def fetch_owned_games(self) -> list[dict]:
        """Fetch owned games while authenticated.

        Returns:
            List of dicts with app_id and name.
        """
        if not self._page or not self._logged_in:
            raise SteamStoreError("Not logged in")

        logger.info("Fetching owned games (authenticated)...")

        # Go to the games list page
        await self._page.goto(
            "https://steamcommunity.com/my/games/?tab=all&sort=name",
            wait_until="networkidle"
        )
        await asyncio.sleep(5)

        # Take screenshot for debugging
        await self._page.screenshot(path="debug_games.png")
        logger.debug(f"Games page URL: {self._page.url}")

        # Extract games from the page - try multiple methods
        games = await self._page.evaluate("""
            () => {
                const games = [];

                // Method 1: New Steam UI - game cards with data-appid
                document.querySelectorAll('[data-appid]').forEach(el => {
                    const appId = el.getAttribute('data-appid');
                    const nameEl = el.querySelector('.gameListRowItemName, .game_name, .title, a');
                    const name = nameEl ? nameEl.textContent.trim() : '';
                    if (appId && name) {
                        games.push({ app_id: parseInt(appId), name: name });
                    }
                });

                // Method 2: Old Steam UI - gameListRow elements
                if (games.length === 0) {
                    document.querySelectorAll('.gameListRow').forEach(row => {
                        const appId = row.id?.replace('game_', '');
                        const nameEl = row.querySelector('.gameListRowItemName');
                        if (appId && nameEl) {
                            games.push({ app_id: parseInt(appId), name: nameEl.textContent.trim() });
                        }
                    });
                }

                // Method 3: Check for rgGames JavaScript variable
                if (games.length === 0 && typeof rgGames !== 'undefined' && rgGames) {
                    rgGames.forEach(game => {
                        games.push({ app_id: game.appid, name: game.name });
                    });
                }

                // Method 4: Parse from script tags containing game data
                if (games.length === 0) {
                    const scripts = document.querySelectorAll('script');
                    scripts.forEach(script => {
                        const text = script.textContent;
                        if (text && text.includes('rgGames')) {
                            const match = text.match(/rgGames\s*=\s*(\[.*?\]);/s);
                            if (match) {
                                try {
                                    const parsed = JSON.parse(match[1]);
                                    parsed.forEach(g => {
                                        games.push({ app_id: g.appid, name: g.name });
                                    });
                                } catch(e) {}
                            }
                        }
                    });
                }

                return games;
            }
        """)

        logger.info(f"Found {len(games)} owned games")

        # If still no games, log the page content for debugging
        if len(games) == 0:
            logger.warning("No games found. Check debug_games.png for page state.")

        return games

    async def add_to_cart(self, app_id: int) -> bool:
        """Add a game to the cart.

        Args:
            app_id: Steam app ID.

        Returns:
            True if successfully added.
        """
        if not self._page:
            raise SteamStoreError("Browser not started")

        # Make sure we're on the game page
        current_url = self._page.url
        if f"/app/{app_id}" not in current_url:
            await self.navigate_to_game(app_id)

        # Find and click add to cart button
        add_btn = await self._page.query_selector(
            '.btn_addtocart a, #btn_add_to_cart, .btnv6_green_white_innerfade'
        )

        if not add_btn:
            raise SteamStoreError("Add to cart button not found")

        await add_btn.click()
        await asyncio.sleep(3)

        # Verify added to cart - check multiple indicators
        success = await self._page.query_selector('.cart_status_message')
        if not success:
            success = await self._page.query_selector('.added_to_cart')
        if not success:
            # Check if we're now on the cart page or see cart confirmation
            page_content = await self._page.content()
            if "added to your cart" in page_content.lower() or "/cart" in self._page.url:
                return True

        return success is not None
