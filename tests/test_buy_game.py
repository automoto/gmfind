"""Tests for buy_game.py - Steam checkout automation."""

from unittest.mock import MagicMock, patch

import pytest


class TestSteamCheckoutCartHasItems:
    """Tests for SteamCheckout._cart_has_items method."""

    def test_cart_has_items_returns_true_when_remove_buttons_exist(self):
        """Test that _cart_has_items returns True when Remove buttons are visible."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 2

        mock_page.get_by_role.return_value.or_.return_value.filter.return_value = (
            mock_locator
        )

        checkout = SteamCheckout(mock_page)
        result = checkout._cart_has_items()

        assert result is True
        mock_page.get_by_role.assert_called_once_with("button", name="Remove")

    def test_cart_has_items_returns_false_when_no_remove_buttons(self):
        """Test that _cart_has_items returns False when no Remove buttons exist."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0

        mock_page.get_by_role.return_value.or_.return_value.filter.return_value = (
            mock_locator
        )

        checkout = SteamCheckout(mock_page)
        result = checkout._cart_has_items()

        assert result is False


class TestSteamCheckoutClearCart:
    """Tests for SteamCheckout.clear_cart method."""

    def test_clear_cart_skips_when_cart_empty(self, capsys):
        """Test that clear_cart skips clearing when cart is already empty."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0

        mock_page.get_by_role.return_value.or_.return_value.filter.return_value = (
            mock_locator
        )

        checkout = SteamCheckout(mock_page)

        with patch.object(checkout, "_cart_has_items", return_value=False):
            checkout.clear_cart()

        captured = capsys.readouterr()
        assert "Cart is already empty" in captured.out
        mock_page.evaluate.assert_not_called()

    def test_clear_cart_attempts_api_clear_when_cart_has_items(self, capsys):
        """Test that clear_cart attempts API clear when cart has items."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_locator.first = MagicMock()

        mock_page.get_by_role.return_value.or_.return_value.filter.return_value = (
            mock_locator
        )
        mock_page.evaluate.return_value = "fake_token"

        checkout = SteamCheckout(mock_page)

        with patch.object(checkout, "_cart_has_items", return_value=True):
            with patch("gmfind.buy_game.time.sleep"):
                checkout.clear_cart()

        captured = capsys.readouterr()
        assert "Cart has items, clearing" in captured.out
        assert mock_page.evaluate.called


class TestSteamCheckoutFindPurchaseButton:
    """Tests for SteamCheckout.find_purchase_button method."""

    def test_find_purchase_button_returns_first_matching_selector(self):
        """Test that find_purchase_button returns first visible matching button."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1

        mock_page.locator.return_value.filter.return_value.first = mock_locator

        checkout = SteamCheckout(mock_page)
        result = checkout.find_purchase_button()

        assert result == mock_locator

    def test_find_purchase_button_returns_none_when_no_button_found(self):
        """Test that find_purchase_button returns None when no button is visible."""
        from gmfind.buy_game import SteamCheckout

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0

        mock_page.locator.return_value.filter.return_value.first = mock_locator
        mock_page.get_by_text.return_value.filter.return_value.last = mock_locator

        checkout = SteamCheckout(mock_page)
        result = checkout.find_purchase_button()

        assert result is None


class TestBuyGameFunction:
    """Tests for the buy_game function."""

    def test_buy_game_attempts_login_when_no_session(self, capsys):
        """Test that buy_game attempts login when STATE_FILE doesn't exist."""
        from gmfind.buy_game import buy_game

        with patch("gmfind.buy_game.os.path.exists", return_value=False):
            with patch("gmfind.buy_game.login") as mock_login:
                result = buy_game("12345")

        mock_login.assert_called_once()
        captured = capsys.readouterr()
        assert "Session not found" in captured.out
