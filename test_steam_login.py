#!/usr/bin/env python3
"""Integration test for Steam login flow.

Run this to verify the login selectors and flow continue to work.
Uses saved session if available, otherwise tests up to 2FA prompt.

Usage:
    python test_steam_login.py           # Test with saved session or up to 2FA
    python test_steam_login.py --fresh   # Force fresh login (will need 2FA code)
    python test_steam_login.py --visible # Run with visible browser for debugging
"""

import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = Path("steam_browser_auth.json")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def find_username_input(page):
    """Find username input, skip search bar."""
    for inp in page.locator('input[type="text"]').all():
        if inp.is_visible() and inp.get_attribute("name") != "term":
            return inp
    return None


def find_password_input(page):
    """Find password input."""
    inp = page.locator('input[type="password"]').first
    return inp if inp.is_visible() else None


def find_submit_button(page):
    """Find login submit button."""
    btn = page.locator('button[type="submit"]:has-text("Sign in")')
    return btn.first if btn.count() > 0 and btn.first.is_visible() else None


def is_logged_in(page):
    """Check if logged in."""
    for sel in ["#account_pulldown", ".user_avatar", ".playerAvatar"]:
        try:
            if page.locator(sel).first.is_visible():
                return True
        except:
            pass
    return False


def detect_2fa(page):
    """Detect 2FA prompt."""
    content = page.content().lower()
    if "enter the code from your email" in content:
        return "email"
    if "mobile authenticator" in content or "logintwofactorcodemodal" in content:
        return "mobile"
    return None


def test_login_flow(headless=True, fresh=False):
    """Test the Steam login flow."""
    username = os.getenv("STEAM_USERNAME")
    password = os.getenv("STEAM_PASSWORD")

    if not username or not password:
        print("[FAIL] STEAM_USERNAME or STEAM_PASSWORD not set in .env")
        return False

    # Check for existing session
    if not fresh and STATE_FILE.exists():
        print("[TEST] Validating existing session...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(storage_state=str(STATE_FILE), user_agent=USER_AGENT)
            page = context.new_page()
            page.goto("https://store.steampowered.com/", wait_until="domcontentloaded")
            time.sleep(2)
            if is_logged_in(page):
                print("[PASS] Existing session is valid")
                browser.close()
                return True
            print("[INFO] Session expired, testing fresh login...")
            browser.close()

    # Test fresh login flow
    print(f"[TEST] Testing login flow for: {username}")
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        try:
            # Navigate
            page.goto("https://store.steampowered.com/login/", wait_until="networkidle")
            time.sleep(1)
            results["navigate"] = True

            # Find & fill username
            username_input = find_username_input(page)
            results["find_username"] = username_input is not None
            if not username_input:
                raise Exception("Username input not found")
            username_input.fill(username)
            results["fill_username"] = username_input.input_value() == username

            # Find & fill password
            password_input = find_password_input(page)
            results["find_password"] = password_input is not None
            if not password_input:
                raise Exception("Password input not found")
            password_input.fill(password)
            results["fill_password"] = password_input.input_value() == password

            # Find & click submit
            submit_btn = find_submit_button(page)
            results["find_submit"] = submit_btn is not None
            if not submit_btn:
                raise Exception("Submit button not found")
            submit_btn.click()
            results["click_submit"] = True

            # Wait for result
            time.sleep(5)

            if is_logged_in(page):
                results["login_success"] = True
                context.storage_state(path=str(STATE_FILE))
                print("[PASS] Login successful (no 2FA required)")
            else:
                twofa = detect_2fa(page)
                results["detect_2fa"] = twofa is not None
                if twofa:
                    print(f"[PASS] 2FA prompt detected: {twofa}")
                    print("       (Credentials accepted, selectors working)")

                    # If visible mode, allow manual 2FA entry
                    if not headless:
                        code = input("\nEnter 2FA code (or press Enter to skip): ").strip()
                        if code:
                            inputs = [i for i in page.locator('input[type="text"]').all()
                                     if i.is_visible() and i.get_attribute("name") != "term"
                                     and i.input_value() != username]
                            if len(inputs) >= 5:
                                inputs[0].click()
                                time.sleep(0.3)
                                for char in code[:5]:
                                    page.keyboard.type(char)
                                    time.sleep(0.2)
                            time.sleep(5)
                            if is_logged_in(page):
                                context.storage_state(path=str(STATE_FILE))
                                print("[PASS] Login complete, session saved")
                                results["login_success"] = True

        except Exception as e:
            print(f"[FAIL] {e}")
            page.screenshot(path="test_login_error.png")
            return False
        finally:
            browser.close()

    # Print results
    print("\n" + "=" * 40)
    print("TEST RESULTS")
    print("=" * 40)
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    return all_pass or results.get("detect_2fa", False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Steam login flow")
    parser.add_argument("--fresh", action="store_true", help="Force fresh login test")
    parser.add_argument("--visible", action="store_true", help="Run with visible browser")
    args = parser.parse_args()

    success = test_login_flow(headless=not args.visible, fresh=args.fresh)
    print("\n" + ("=" * 40))
    print("[SUCCESS] All tests passed" if success else "[FAILED] Some tests failed")
    print("=" * 40)
    sys.exit(0 if success else 1)
