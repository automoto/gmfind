"""Tests for inventory.py - Steam inventory parsing."""

import pytest

from tests.fixtures.sample_data import (
    STEAM_GAMES_XML,
    STEAM_GAMES_XML_EMPTY,
    STEAM_GAMES_XML_MALFORMED,
)


class TestParseGamesXml:
    """Tests for _parse_games_xml method."""

    def test_parse_games_with_playtime(self):
        """Test parsing XML with games that have playtime recorded."""
        from gmfind.inventory import SteamInventory

        inventory = SteamInventory("76561198012345678")
        games = inventory._parse_games_xml(STEAM_GAMES_XML)

        # Should find 3 games
        assert len(games) == 3

        # Check Elden Ring (has playtime)
        elden_ring = next(g for g in games if g.app_id == 1245620)
        assert elden_ring.name == "Elden Ring"
        assert elden_ring.playtime_minutes == int(125.5 * 60)

        # Check Witcher 3 (has playtime)
        witcher = next(g for g in games if g.app_id == 292030)
        assert witcher.name == "The Witcher 3: Wild Hunt"
        assert witcher.playtime_minutes == int(85.2 * 60)

        # Check CS2 (no playtime)
        cs2 = next(g for g in games if g.app_id == 730)
        assert cs2.name == "Counter-Strike 2"
        assert cs2.playtime_minutes == 0

    def test_parse_empty_games_list(self):
        """Test parsing XML with no games."""
        from gmfind.inventory import SteamInventory

        inventory = SteamInventory("76561198012345678")
        games = inventory._parse_games_xml(STEAM_GAMES_XML_EMPTY)

        assert len(games) == 0

    def test_parse_malformed_xml(self):
        """Test parsing malformed XML returns empty list."""
        from gmfind.inventory import SteamInventory

        inventory = SteamInventory("76561198012345678")
        games = inventory._parse_games_xml(STEAM_GAMES_XML_MALFORMED)

        # Should handle gracefully and return empty or partial list
        assert isinstance(games, list)

    def test_parse_games_order_independent(self):
        """Test that parsing works regardless of element order in XML."""
        # XML with different element ordering
        xml_reordered = """<?xml version="1.0" encoding="UTF-8"?>
        <gamesList>
            <games>
                <game>
                    <name><![CDATA[Test Game]]></name>
                    <hoursOnRecord>10.0</hoursOnRecord>
                    <appID>12345</appID>
                </game>
            </games>
        </gamesList>
        """
        from gmfind.inventory import SteamInventory

        inventory = SteamInventory("76561198012345678")
        games = inventory._parse_games_xml(xml_reordered)

        assert len(games) == 1
        assert games[0].app_id == 12345
        assert games[0].name == "Test Game"
        assert games[0].playtime_minutes == 600


class TestGetOwnedAppIds:
    """Tests for get_owned_app_ids method."""

    def test_get_owned_app_ids_returns_set(self):
        """Test that get_owned_app_ids returns a set of integers."""
        from gmfind.inventory import SteamInventory

        inventory = SteamInventory("76561198012345678")
        # Mock the _owned_app_ids
        inventory._owned_app_ids = {1245620, 292030, 730}

        result = inventory.get_owned_app_ids()

        assert isinstance(result, set)
        assert 1245620 in result
        assert 292030 in result
        assert 730 in result
