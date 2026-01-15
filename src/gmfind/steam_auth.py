"""Steam authentication module using Playwright (Sync).

Provides reliable headless Steam login with session persistence
and Steam Guard (2FA) code handling.

Usage:
    # Simple login (saves session for future use)
    from gmfind.steam_auth import login
    login()

    # Use authenticated session
    from gmfind.steam_auth import get_authenticated_context
    with get_authenticated_context() as (context, page):
        page.goto("https://store.steampowered.com/account/")
        # ... do authenticated operations

    # Or use the lower-level API
    from gmfind.steam_auth import SteamAuth
    auth = SteamAuth()
    if auth.ensure_logged_in():
        # Session is ready to use
        pass
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Optional, Tuple

from gmfind.paths import get_screenshots_dir, get_session_file
from gmfind.playwright_utils import get_sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants (exported for backward compatibility)
STATE_FILE = get_session_file()
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Steam URLs
STEAM_LOGIN_URL = "https://store.steampowered.com/login/"
STEAM_STORE_URL = "https://store.steampowered.com/"
STEAM_COMMUNITY_URL = "https://steamcommunity.com/"


class SteamAuth:
    """Steam authentication handler with session persistence."""

    def __init__(
        self,
        state_file: Path = STATE_FILE,
        headless: bool = True,
        timeout: int = 60,
    ):
        """
        Initialize Steam authenticator.

        Args:
            state_file: Path to save/load browser session state
            headless: Run browser in headless mode
            timeout: Maximum time (seconds) to wait for login completion
        """
        self.state_file = Path(state_file)
        self.headless = headless
        self.timeout = timeout
        self._username = os.getenv("STEAM_USERNAME")
        self._password = os.getenv("STEAM_PASSWORD")

    def _find_username_input(self, page: Page):
        """Find the username input field, avoiding the search bar."""
        text_inputs = page.locator('input[type="text"]').all()
        for inp in text_inputs:
            if not inp.is_visible():
                continue
            # Skip search bar (has name="term")
            name = inp.get_attribute("name") or ""
            if name == "term":
                continue
            return inp
        return None

    def _find_password_input(self, page: Page):
        """Find the password input field."""
        pw_input = page.locator('input[type="password"]').first
        if pw_input.is_visible():
            return pw_input
        return None

    def _find_submit_button(self, page: Page):
        """Find the login submit button."""
        # The login button is a submit button with "Sign in" text
        btn = page.locator('button[type="submit"]:has-text("Sign in")')
        if btn.count() > 0 and btn.first.is_visible():
            return btn.first
        return None

    def _is_logged_in(self, page: Page) -> bool:
        """Check if the user is currently logged into Steam."""
        logged_in_selectors = [
            "#account_pulldown",
            ".user_avatar",
            '[class*="accountName"]',
            ".playerAvatar",
        ]
        for selector in logged_in_selectors:
            try:
                if page.locator(selector).first.is_visible():
                    return True
            except Exception:
                pass
        return False

    def _detect_2fa_prompt(self, page: Page) -> Optional[str]:
        """
        Detect if a 2FA prompt is shown.

        Returns:
            "email" - Email code prompt
            "mobile" - Mobile authenticator prompt
            None - No 2FA prompt detected
        """
        content = page.content().lower()

        # Check for email code prompt
        if "enter the code from your email" in content:
            return "email"

        if "check your email" in content and "code" in content:
            return "email"

        # Check for email code modal class
        if "loginauthcodemodal" in content:
            return "email"

        # Check for mobile authenticator modal
        if "logintwofactorcodemodal" in content:
            return "mobile"

        if "enter the code from your mobile authenticator" in content:
            return "mobile"

        if "steam guard mobile authenticator" in content:
            return "mobile"

        return None

    def _find_2fa_inputs(self, page: Page, username: str) -> list:
        """Find the 2FA code input field(s)."""
        text_inputs = page.locator('input[type="text"]').all()
        candidates = []

        for inp in text_inputs:
            if not inp.is_visible():
                continue

            # Skip search bar
            name = inp.get_attribute("name") or ""
            if name == "term":
                continue

            # Skip username field
            try:
                val = inp.input_value()
                if val == username:
                    continue
            except Exception:
                pass

            candidates.append(inp)

        return candidates

    def _enter_2fa_code(self, page: Page, code: str, username: str) -> bool:
        """
        Enter a 2FA code into the appropriate input field(s).

        Returns:
            True if code was entered successfully
        """
        # Wait a moment for the 2FA UI to fully render
        time.sleep(1)

        inputs = self._find_2fa_inputs(page, username)

        if not inputs:
            logger.warning("No 2FA input fields found, trying keyboard entry...")
            page.keyboard.type(code)
            page.keyboard.press("Enter")
            return True

        # Steam uses 5 separate inputs for each digit of the code
        if len(inputs) >= 5:
            logger.info(f"Detected multi-segment 2FA input ({len(inputs)} fields)")
            # Click the first input to focus
            inputs[0].click()
            time.sleep(0.3)
            # Type each character with delay - Steam auto-advances to next field
            for char in code[:5]:
                page.keyboard.type(char)
                time.sleep(0.2)
            # Wait for Steam to process
            time.sleep(1)
        else:
            # Single input field
            logger.info("Detected single 2FA input field")
            target = inputs[-1]
            target.click()
            time.sleep(0.2)
            target.fill(code)
            time.sleep(0.5)
            page.keyboard.press("Enter")

        return True

    def _detect_error(self, page: Page) -> Optional[str]:
        """Detect login errors."""
        content = page.content().lower()

        # Check for password/account error phrases (use partial matching)
        if "check your password" in content or "check your account" in content:
            return "Incorrect username or password"

        if "password" in content and "incorrect" in content:
            return "Incorrect username or password"

        if "account name" in content and "incorrect" in content:
            return "Incorrect username or password"

        if "too many login" in content or "too many attempts" in content:
            return "Rate limited - too many login attempts"

        # Look for specific error message elements/classes
        error_selectors = [
            '[class*="FormError"]',
            ".newlogindialog_FormError",
            '[class*="Error"]',
        ]

        for selector in error_selectors:
            try:
                error_elem = page.locator(selector).first
                if error_elem.is_visible():
                    error_text = error_elem.inner_text().lower()
                    if not error_text.strip():
                        continue
                    if "password" in error_text or "account" in error_text:
                        return "Incorrect username or password"
                    if "too many" in error_text:
                        return "Rate limited - too many login attempts"
                    # Return the actual error text if it looks like an error
                    if len(error_text) < 200:
                        return f"Login error: {error_text.strip()}"
            except Exception:
                pass

        return None

    def has_valid_session(self) -> bool:
        """Check if a saved session exists and is valid."""
        if not self.state_file.exists():
            return False

        # Quick validation - try loading the session and checking logged in status
        try:
            with get_sync_playwright()() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=str(self.state_file),
                    user_agent=USER_AGENT,
                )
                page = context.new_page()
                page.goto(STEAM_STORE_URL, wait_until="domcontentloaded")
                time.sleep(1)
                is_logged_in = self._is_logged_in(page)
                browser.close()
                return is_logged_in
        except Exception as e:
            logger.debug(f"Session validation failed: {e}")
            return False

    def login(self, force: bool = False) -> bool:
        """
        Perform Steam login.

        Args:
            force: Force re-login even if session exists

        Returns:
            True if login successful, False otherwise
        """
        if not self._username or not self._password:
            logger.error("STEAM_USERNAME or STEAM_PASSWORD environment variables not set")
            return False

        # Check for existing valid session
        if not force and self.has_valid_session():
            logger.info("Valid session found, skipping login")
            return True

        logger.info(f"Starting login for user: {self._username}")

        with get_sync_playwright()() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = context.new_page()

            try:
                # Navigate to login page
                logger.info("Navigating to Steam login page...")
                page.goto(STEAM_LOGIN_URL, wait_until="networkidle")
                time.sleep(1)

                # Check if already logged in
                if self._is_logged_in(page):
                    logger.info("Already logged in from previous session")
                    self._save_session(context)
                    return True

                # Find and fill username
                username_input = self._find_username_input(page)
                if not username_input:
                    logger.error("Could not find username input field")
                    page.screenshot(path=str(get_screenshots_dir() / "login_error_username.png"))
                    return False

                print(f"Entering username: {self._username}", flush=True)
                logger.info("Entering username...")
                username_input.click()
                time.sleep(0.2)
                username_input.fill("")  # Clear first
                username_input.fill(self._username)
                time.sleep(0.5)

                # Find and fill password
                password_input = self._find_password_input(page)
                if not password_input:
                    logger.error("Could not find password input field")
                    page.screenshot(path=str(get_screenshots_dir() / "login_error_password.png"))
                    return False

                print("Entering password...", flush=True)
                logger.info("Entering password...")
                password_input.click()
                time.sleep(0.2)
                password_input.fill("")  # Clear first
                # Use type() instead of fill() for password - more reliable with special chars
                password_input.type(self._password, delay=50)
                time.sleep(0.5)

                # Find and click submit button
                submit_btn = self._find_submit_button(page)
                if not submit_btn:
                    logger.error("Could not find login submit button")
                    page.screenshot(path=str(get_screenshots_dir() / "login_error_submit.png"))
                    return False

                logger.info("Submitting login...")
                submit_btn.click()

                # Wait for login result
                return self._wait_for_login_result(page, context)

            except Exception as e:
                logger.error(f"Login error: {e}")
                page.screenshot(path=str(get_screenshots_dir() / "login_crash.png"))
                return False
            finally:
                browser.close()

    def _wait_for_login_result(self, page: Page, context: BrowserContext) -> bool:
        """Wait for and handle login result, including 2FA prompts."""
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            time.sleep(1)

            # Check for successful login FIRST
            if self._is_logged_in(page):
                logger.info("Login successful!")
                print("[SUCCESS] Login successful!", flush=True)
                # Sync cookies across Steam domains
                page.goto(STEAM_COMMUNITY_URL, wait_until="domcontentloaded")
                time.sleep(1)
                self._save_session(context)
                return True

            # Check for errors BEFORE 2FA (error pages might contain 2FA-like text)
            error = self._detect_error(page)
            if error:
                logger.error(f"Login failed: {error}")
                print(f"\n[ERROR] Login failed: {error}", flush=True)
                page.screenshot(path=str(get_screenshots_dir() / "login_failed.png"))
                return False

            # Check for 2FA prompt
            twofa_type = self._detect_2fa_prompt(page)
            if twofa_type:
                logger.info(f"2FA prompt detected: {twofa_type}")

                # Request code from user
                print("\n" + "=" * 50)
                if twofa_type == "email":
                    print("STEAM GUARD - Enter the code from your EMAIL")
                else:
                    print("STEAM GUARD - Enter the code from your MOBILE APP")
                print("=" * 50)

                code = input("Enter code: ").strip()

                if not code:
                    logger.error("No code entered, aborting login")
                    print("[ERROR] No code entered, aborting login", flush=True)
                    return False

                logger.info("Entering 2FA code...")
                self._enter_2fa_code(page, code, self._username or "")
                time.sleep(2)

                # Reset timeout after code entry
                start_time = time.time()
                continue  # Go back to check login status

        logger.error("Login timed out")
        print("[ERROR] Login timed out", flush=True)
        page.screenshot(path=str(get_screenshots_dir() / "login_timeout.png"))
        return False

    def _save_session(self, context: BrowserContext) -> None:
        """Save browser session state to file."""
        context.storage_state(path=str(self.state_file))
        logger.info(f"Session saved to {self.state_file}")

    def ensure_logged_in(self) -> bool:
        """
        Ensure a valid login session exists.

        Attempts to use existing session or performs login if needed.

        Returns:
            True if logged in successfully
        """
        if self.has_valid_session():
            logger.info("Using existing valid session")
            return True
        return self.login()


@contextmanager
def get_authenticated_context(
    headless: bool = True,
    state_file: Path = STATE_FILE,
) -> Generator[Tuple[BrowserContext, Page], None, None]:
    """
    Context manager that provides an authenticated Steam browser context.

    Usage:
        with get_authenticated_context() as (context, page):
            page.goto("https://store.steampowered.com/account/")
            # ... do authenticated operations

    Args:
        headless: Run browser in headless mode
        state_file: Path to session state file

    Yields:
        Tuple of (BrowserContext, Page)

    Raises:
        RuntimeError: If login fails
    """
    auth = SteamAuth(state_file=state_file, headless=headless)

    if not auth.ensure_logged_in():
        raise RuntimeError("Failed to authenticate with Steam")

    with get_sync_playwright()() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=str(state_file),
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        try:
            yield context, page
        finally:
            # Update session state before closing
            context.storage_state(path=str(state_file))
            browser.close()


def login(force: bool = False, headless: bool = True) -> bool:
    """
    Simple login function for backward compatibility.

    Args:
        force: Force re-login even if session exists
        headless: Run browser in headless mode (set False to see browser)

    Returns:
        True if login successful
    """
    auth = SteamAuth(headless=headless)
    return auth.login(force=force)


def is_logged_in() -> bool:
    """Check if there's a valid Steam session."""
    auth = SteamAuth()
    return auth.has_valid_session()


if __name__ == "__main__":
    import sys

    if "--force" in sys.argv:
        success = login(force=True)
    else:
        success = login()

    if success:
        print("\n[SUCCESS] Steam login completed")
    else:
        print("\n[FAILED] Steam login failed")
        sys.exit(1)
