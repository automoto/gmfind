"""Playwright lazy-loading utilities.

Provides helper functions to import Playwright only when needed,
allowing non-browser commands to work without Playwright installed.
"""

import sys
from typing import Any


def get_sync_playwright() -> Any:
    """Get sync_playwright context manager.

    Returns:
        sync_playwright from playwright.sync_api

    Raises:
        SystemExit: If Playwright is not installed
    """
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError:
        sys.exit(
            "This command requires Playwright browser automation.\n\n"
            "Install with:\n"
            "  pip install playwright && playwright install chromium\n\n"
            "Or install gmfind with browser support:\n"
            "  pip install 'gmfind[browser]'"
        )
