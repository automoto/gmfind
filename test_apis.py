#!/usr/bin/env python3
"""Test script for ProtonDB and Metacritic APIs."""

import asyncio
from src.recommendations.metacritic import MetacriticScraper
from src.recommendations.protondb import ProtonDBClient


async def test_protondb():
    """Test ProtonDB API with known games."""
    print("=" * 50)
    print("Testing ProtonDB API...")
    print("=" * 50)

    protondb = ProtonDBClient()

    # Test with some known game IDs
    test_games = [
        (1245620, "Elden Ring"),
        (1091500, "Cyberpunk 2077"),
        (367520, "Hollow Knight"),
        (292030, "The Witcher 3"),
        (1174180, "Red Dead Redemption 2"),
    ]

    for app_id, name in test_games:
        report = await protondb.get_rating(app_id)
        print(f"  {name}: {report.tier} (score: {report.score}, confidence: {report.confidence})")

    print()


async def test_metacritic():
    """Test Metacritic scraper."""
    print("=" * 50)
    print("Testing Metacritic Scraper...")
    print("=" * 50)

    metacritic = MetacriticScraper()
    games = await metacritic.fetch_top_rated_games(min_score=85, limit=10)

    if games:
        for game in games:
            user_score = f", user: {game.user_score}" if game.user_score else ""
            print(f"  {game.name}: {game.metascore}{user_score}")
    else:
        print("  No games returned (Metacritic may be blocking scraping)")

    print()


async def main():
    """Run all tests."""
    await test_protondb()
    await test_metacritic()
    print("Tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
