"""Tests for recommendations/metacritic.py - Metacritic scraper."""

import pytest

from tests.fixtures.sample_data import (
    METACRITIC_REVIEWS_HTML,
    METACRITIC_SLUG_TEST_CASES,
)


class TestExtractSlugFromUrl:
    """Tests for URL slug extraction."""

    @pytest.mark.parametrize("url,expected_slug", METACRITIC_SLUG_TEST_CASES)
    def test_extract_slug_from_url(self, url: str, expected_slug: str):
        """Test extracting slugs from various Metacritic URL formats."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._extract_slug_from_url(url)
        assert result == expected_slug

    def test_extract_slug_empty_url(self):
        """Test with empty URL."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._extract_slug_from_url("")
        assert result == ""


class TestExtractReviewsViaRegex:
    """Tests for Nuxt.js review extraction."""

    def test_extract_reviews_from_nuxt_data(self):
        """Test extracting reviews from Nuxt.js embedded data."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        # Extract the script content
        script_content = METACRITIC_REVIEWS_HTML

        reviews = scraper._extract_reviews_via_regex(script_content)

        # Should find 2 reviews
        assert reviews is not None
        assert len(reviews) == 2

        # Check first review (IGN)
        ign_review = next((r for r in reviews if r["publicationName"] == "IGN"), None)
        assert ign_review is not None
        assert ign_review["score"] == 100
        assert "masterpiece" in ign_review["quote"].lower()

    def test_extract_reviews_empty_script(self):
        """Test with script containing no review data."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._extract_reviews_via_regex("<script>var x = 1;</script>")

        assert result is None


class TestNormalizeTitle:
    """Tests for title normalization."""

    def test_normalize_removes_colons(self):
        """Test that colons are removed from titles."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._normalize_title("The Witcher 3: Wild Hunt")
        assert ":" not in result

    def test_normalize_roman_numerals(self):
        """Test Roman numeral conversion."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()

        assert "2" in scraper._normalize_title("Final Fantasy II")
        assert "3" in scraper._normalize_title("Dark Souls III")

    def test_normalize_edition_suffixes(self):
        """Test that edition suffixes are removed."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()

        result = scraper._normalize_title("Skyrim Special Edition")
        assert "edition" not in result

        result = scraper._normalize_title("Witcher 3 GOTY Edition")
        assert "goty" not in result


class TestTitleSimilarity:
    """Tests for title similarity calculation."""

    def test_identical_titles(self):
        """Test that identical titles have similarity of 1.0."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._title_similarity("elden ring", "elden ring")
        assert result == 1.0

    def test_completely_different_titles(self):
        """Test that different titles have low similarity."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._title_similarity("elden ring", "minecraft")
        assert result < 0.5

    def test_partial_overlap(self):
        """Test titles with partial word overlap."""
        from gmfind.recommendations.metacritic import MetacriticScraper

        scraper = MetacriticScraper()
        result = scraper._title_similarity("dark souls 3", "dark souls remastered")
        # Should have some overlap due to "dark" and "souls"
        assert result > 0.3


class TestMetacriticGame:
    """Tests for MetacriticGame dataclass."""

    def test_metacritic_game_creation(self):
        """Test creating a MetacriticGame instance."""
        from gmfind.recommendations.metacritic import MetacriticGame

        game = MetacriticGame(
            name="Elden Ring",
            slug="elden-ring",
            metascore=96,
            user_score=8.1,
            platform="PC",
            release_date="Feb 25, 2022",
            url="https://www.metacritic.com/game/elden-ring/",
        )

        assert game.name == "Elden Ring"
        assert game.metascore == 96
        assert game.user_score == 8.1
