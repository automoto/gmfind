import os
import re

from gmfind.playwright_utils import get_sync_playwright
from gmfind.steam_auth import STATE_FILE, USER_AGENT, login


def get_balance(headless: bool = True) -> float | None:
    """Check Steam Wallet balance and return as float."""
    if not os.path.exists(STATE_FILE):
        print(f"[INFO] Session file '{STATE_FILE}' not found. Attempting login...")
        login(headless=headless)
        if not os.path.exists(STATE_FILE):
            print("[ERROR] Login failed. Cannot check balance.")
            return None

    print("Launching browser...")
    with get_sync_playwright()() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=STATE_FILE, user_agent=USER_AGENT)
        page = context.new_page()

        print("Navigating to Store...")
        page.goto("https://store.steampowered.com/account/")
        page.wait_for_load_state("networkidle")

        selectors = [".accountBalance", "#header_wallet_balance", ".wallet_balance"]

        balance_text = None
        for selector in selectors:
            elem = page.query_selector(selector)
            if elem and elem.is_visible():
                balance_text = elem.inner_text()
                break

        browser.close()

        if balance_text:
            # Clean string "$12.34" -> 12.34
            clean_text = re.sub(r"[^\d.]", "", balance_text)
            try:
                return float(clean_text)
            except ValueError:
                print(f"[ERROR] Could not parse balance: {balance_text}")
                return None
        else:
            print("\n[WARNING] Could not find wallet balance.")
            return None


def check_balance():
    """CLI wrapper for get_balance."""
    balance = get_balance()
    if balance is not None:
        print(f"\n[SUCCESS] Steam Wallet Balance: ${balance:.2f}")
    else:
        print("Failed to retrieve balance.")


if __name__ == "__main__":
    check_balance()
