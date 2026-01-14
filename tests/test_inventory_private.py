"""Tests for inventory_private.py - Private Steam inventory parsing."""

import pytest

from tests.fixtures.sample_data import (
    STEAM_LIBRARY_HTML,
    STEAM_LIBRARY_HTML_LEGACY,
    STEAM_LIBRARY_HTML_NO_JSON,
    URL_TEST_CASES,
)


class TestExtractGamesFromHtml:
    """Tests for extract_games_from_html function."""

    def test_extract_from_render_context(self):
        """Test extracting games from SSR.renderContext JSON."""
        from gmfind.inventory_private import extract_games_from_html

        games = extract_games_from_html(STEAM_LIBRARY_HTML)

        assert len(games) == 2
        app_ids = {g.app_id for g in games}
        assert 1245620 in app_ids  # Elden Ring
        assert 292030 in app_ids  # Witcher 3

    def test_extract_from_legacy_loader_data(self):
        """Test extracting games from legacy loaderData format."""
        from gmfind.inventory_private import extract_games_from_html

        games = extract_games_from_html(STEAM_LIBRARY_HTML_LEGACY)

        assert len(games) == 1
        assert games[0].app_id == 730  # CS2

    def test_extract_from_empty_html(self):
        """Test extracting from HTML with no game data."""
        from gmfind.inventory_private import extract_games_from_html

        games = extract_games_from_html("<html><body></body></html>")

        assert len(games) == 0


class TestExtractAppIdFromUrl:
    """Tests for URL app_id extraction."""

    @pytest.mark.parametrize("url,expected_id", URL_TEST_CASES)
    def test_extract_app_id_from_url(self, url: str, expected_id: int | None):
        """Test extracting app IDs from various URL formats."""
        from gmfind.inventory_private import extract_app_id_from_url

        result = extract_app_id_from_url(url)
        assert result == expected_id

    def test_extract_app_id_empty_string(self):
        """Test with empty string."""
        from gmfind.inventory_private import extract_app_id_from_url

        assert extract_app_id_from_url("") is None

    def test_extract_app_id_relative_path(self):
        """Test with relative path."""
        from gmfind.inventory_private import extract_app_id_from_url

        result = extract_app_id_from_url("/app/12345/Game_Name/")
        assert result == 12345
