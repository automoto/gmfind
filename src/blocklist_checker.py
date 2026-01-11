"""Module to check game titles against the blocklist."""

import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

BLOCK_LIST_FILE = Path("block_list.yaml")


def load_block_list() -> list[str]:
    """Load blocked terms from block_list.yaml.

    Returns:
        List of blocked terms (lowercase).
    """
    if not BLOCK_LIST_FILE.exists():
        logger.warning(f"{BLOCK_LIST_FILE} not found.")
        return []

    try:
        with open(BLOCK_LIST_FILE) as f:
            data = yaml.safe_load(f)

        terms = data.get("blocked_terms", []) if data else []
        # Filter out None/empty and convert to lowercase
        return [str(t).lower().strip() for t in terms if t]
    except Exception as e:
        logger.error(f"Failed to load block list: {e}")
        return []


def check_blocklist(game_title: str):
    """Check if a game title matches any blocked terms and print result."""
    blocked_terms = load_block_list()

    if not blocked_terms:
        print("Blocklist is empty or could not be loaded.")
        return

    title_lower = game_title.lower().strip()
    matches = []

    for term in blocked_terms:
        if term in title_lower:
            matches.append(term)

    print("\n" + "=" * 40)
    print(f"BLOCKLIST CHECK: '{game_title}'")
    print("=" * 40)

    if matches:
        print(f"[BLOCKED] Match found: {', '.join(matches)}")
        print("This game would be excluded from recommendations.")
    else:
        print("[ALLOWED] No matches found in blocklist.")
    print("=" * 40 + "\n")
