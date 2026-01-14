"""Tests for recommend_metacritic.py - Game recommendation functions."""

import pytest

from tests.fixtures.sample_data import NORMALIZATION_TEST_CASES, URL_TEST_CASES


class TestNormalize:
    """Tests for the normalize function."""

    @pytest.mark.parametrize("input_str,expected", NORMALIZATION_TEST_CASES)
    def test_normalize_various_inputs(self, input_str: str, expected: str):
        """Test normalization with various input strings."""
        from gmfind.recommend_metacritic import normalize

        result = normalize(input_str)
        assert result == expected

    def test_normalize_unicode_characters(self):
        """Test normalization handles unicode properly."""
        from gmfind.recommend_metacritic import normalize

        # isalnum() considers accented chars as alphanumeric
        result = normalize("Pokémon Red")
        # The é is kept since it's alphanumeric
        assert result == "pokémonred"

    def test_normalize_numbers_preserved(self):
        """Test that numbers are preserved in normalization."""
        from gmfind.recommend_metacritic import normalize

        result = normalize("Final Fantasy 7")
        assert "7" in result


class TestSearchSteam:
    """Tests for Steam search functionality."""

    def test_search_steam_returns_tuple_or_none(self):
        """Test that search_steam returns correct type."""
        from gmfind.recommend_metacritic import search_steam

        # With mocked response, this would test the parsing logic
        # For now, just verify the function signature works
        result = search_steam("")
        assert result is None or isinstance(result, tuple)


class TestGetOwnedAppIds:
    """Tests for loading owned app IDs from CSV."""

    def test_get_owned_app_ids_missing_file(self, tmp_path):
        """Test handling of missing inventory file."""
        from gmfind.recommend_metacritic import get_owned_app_ids

        result = get_owned_app_ids(str(tmp_path / "nonexistent.csv"))
        assert result == set()

    def test_get_owned_app_ids_valid_csv(self, tmp_path):
        """Test loading app IDs from valid CSV."""
        from gmfind.recommend_metacritic import get_owned_app_ids

        csv_path = tmp_path / "inventory.csv"
        csv_path.write_text("title,steam_id\nElden Ring,1245620\nWitcher 3,292030\n")

        result = get_owned_app_ids(str(csv_path))

        assert 1245620 in result
        assert 292030 in result
        assert len(result) == 2

    def test_get_owned_app_ids_invalid_ids_skipped(self, tmp_path):
        """Test that invalid IDs are skipped gracefully."""
        from gmfind.recommend_metacritic import get_owned_app_ids

        csv_path = tmp_path / "inventory.csv"
        csv_path.write_text("title,steam_id\nValid Game,12345\nInvalid,not_a_number\n")

        result = get_owned_app_ids(str(csv_path))

        assert 12345 in result
        assert len(result) == 1
