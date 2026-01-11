import os
from playwright.sync_api import sync_playwright
from src.steam_auth import login, STATE_FILE, USER_AGENT


def check_balance():
    if not os.path.exists(STATE_FILE):
        print(f"[INFO] Session file '{STATE_FILE}' not found. Attempting login...")
        login()
        if not os.path.exists(STATE_FILE):
            print("[ERROR] Login failed. Cannot check balance.")
            return

    print("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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

        if balance_text:
            print(f"\n[SUCCESS] Steam Wallet Balance: {balance_text.strip()}")
        else:
            print("\n[WARNING] Could not find wallet balance.")
            if page.query_selector(".login_btn") or page.query_selector("text=Sign In"):
                print("Detected 'Sign In' button - Session likely expired.")

            page.screenshot(path="balance_error.png")

        browser.close()


if __name__ == "__main__":
    check_balance()
