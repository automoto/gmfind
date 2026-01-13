"""Module to check game titles against the blocklist."""

import logging
from pathlib import Path

import yaml

from gmfind.paths import get_blocklist_file

logger = logging.getLogger(__name__)

BLOCK_LIST_FILE = get_blocklist_file()


def load_block_list(file_path: Path | str = BLOCK_LIST_FILE) -> list[str]:
    """Load blocked terms from a YAML file.

    Args:
        file_path: Path to the blocklist YAML file. Defaults to "block_list.yaml".

    Returns:
        List of blocked terms (lowercase).
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"{path} not found.")
        return []

    try:
        with open(path) as f:
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
