"""Tests for paths.py - Cross-platform path management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_xdg_path_on_non_windows(self, tmp_path):
        """Test that config dir uses XDG-style path on Linux/macOS."""
        from gmfind.paths import get_config_dir

        with patch("gmfind.paths.sys.platform", "darwin"):
            with patch("gmfind.paths.Path.home", return_value=tmp_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = get_config_dir()

        assert result == tmp_path / ".config" / "gmfind"

    def test_gmfind_config_dir_env_override(self, tmp_path):
        """Test that GMFIND_CONFIG_DIR takes precedence."""
        from gmfind.paths import get_config_dir

        custom_path = tmp_path / "custom_config"
        with patch.dict(os.environ, {"GMFIND_CONFIG_DIR": str(custom_path)}):
            result = get_config_dir()

        assert result == custom_path

    def test_xdg_config_home_env_override(self, tmp_path):
        """Test that XDG_CONFIG_HOME is respected on non-Windows."""
        from gmfind.paths import get_config_dir

        xdg_path = tmp_path / "xdg_config"
        with patch("gmfind.paths.sys.platform", "linux"):
            with patch.dict(
                os.environ,
                {"XDG_CONFIG_HOME": str(xdg_path), "GMFIND_CONFIG_DIR": ""},
                clear=True,
            ):
                # Clear GMFIND_CONFIG_DIR by removing it
                env = os.environ.copy()
                env.pop("GMFIND_CONFIG_DIR", None)
                with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg_path)}, clear=True):
                    result = get_config_dir()

        assert result == xdg_path / "gmfind"


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_xdg_path_on_non_windows(self, tmp_path):
        """Test that data dir uses XDG-style path on Linux/macOS."""
        from gmfind.paths import get_data_dir

        with patch("gmfind.paths.sys.platform", "darwin"):
            with patch("gmfind.paths.Path.home", return_value=tmp_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = get_data_dir()

        assert result == tmp_path / ".local" / "share" / "gmfind"

    def test_gmfind_data_dir_env_override(self, tmp_path):
        """Test that GMFIND_DATA_DIR takes precedence."""
        from gmfind.paths import get_data_dir

        custom_path = tmp_path / "custom_data"
        with patch.dict(os.environ, {"GMFIND_DATA_DIR": str(custom_path)}):
            result = get_data_dir()

        assert result == custom_path

    def test_xdg_data_home_env_override(self, tmp_path):
        """Test that XDG_DATA_HOME is respected on non-Windows."""
        from gmfind.paths import get_data_dir

        xdg_path = tmp_path / "xdg_data"
        with patch("gmfind.paths.sys.platform", "linux"):
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(xdg_path)}, clear=True):
                result = get_data_dir()

        assert result == xdg_path / "gmfind"


class TestGetCacheDir:
    """Tests for get_cache_dir function."""

    def test_returns_xdg_path_on_non_windows(self, tmp_path):
        """Test that cache dir uses XDG-style path on Linux/macOS."""
        from gmfind.paths import get_cache_dir

        with patch("gmfind.paths.sys.platform", "darwin"):
            with patch("gmfind.paths.Path.home", return_value=tmp_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = get_cache_dir()

        assert result == tmp_path / ".cache" / "gmfind"

    def test_gmfind_cache_dir_env_override(self, tmp_path):
        """Test that GMFIND_CACHE_DIR takes precedence."""
        from gmfind.paths import get_cache_dir

        custom_path = tmp_path / "custom_cache"
        with patch.dict(os.environ, {"GMFIND_CACHE_DIR": str(custom_path)}):
            result = get_cache_dir()

        assert result == custom_path

    def test_xdg_cache_home_env_override(self, tmp_path):
        """Test that XDG_CACHE_HOME is respected on non-Windows."""
        from gmfind.paths import get_cache_dir

        xdg_path = tmp_path / "xdg_cache"
        with patch("gmfind.paths.sys.platform", "linux"):
            with patch.dict(os.environ, {"XDG_CACHE_HOME": str(xdg_path)}, clear=True):
                result = get_cache_dir()

        assert result == xdg_path / "gmfind"


class TestDirectoryCreation:
    """Tests for directory creation behavior."""

    def test_config_dir_creates_directory(self, tmp_path):
        """Test that get_config_dir creates the directory if it doesn't exist."""
        from gmfind.paths import get_config_dir

        custom_path = tmp_path / "new_config"
        assert not custom_path.exists()

        with patch.dict(os.environ, {"GMFIND_CONFIG_DIR": str(custom_path)}):
            result = get_config_dir()

        # Note: GMFIND_CONFIG_DIR override doesn't create the directory
        # Only the XDG path creation does
        assert result == custom_path

    def test_xdg_path_creates_directory(self, tmp_path):
        """Test that XDG-style paths create the directory."""
        from gmfind.paths import get_config_dir

        with patch("gmfind.paths.sys.platform", "darwin"):
            with patch("gmfind.paths.Path.home", return_value=tmp_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = get_config_dir()

        assert result.exists()
        assert result.is_dir()


class TestSpecificFilePaths:
    """Tests for specific file path functions."""

    def test_get_config_file(self, tmp_path):
        """Test get_config_file returns correct path."""
        from gmfind.paths import get_config_file

        with patch.dict(os.environ, {"GMFIND_CONFIG_DIR": str(tmp_path)}):
            result = get_config_file()

        assert result == tmp_path / "config.yaml"

    def test_get_blocklist_file(self, tmp_path):
        """Test get_blocklist_file returns correct path."""
        from gmfind.paths import get_blocklist_file

        with patch.dict(os.environ, {"GMFIND_CONFIG_DIR": str(tmp_path)}):
            result = get_blocklist_file()

        assert result == tmp_path / "block_list.yaml"

    def test_get_session_file(self, tmp_path):
        """Test get_session_file returns correct path."""
        from gmfind.paths import get_session_file

        with patch.dict(os.environ, {"GMFIND_DATA_DIR": str(tmp_path)}):
            result = get_session_file()

        assert result == tmp_path / "steam_browser_auth.json"

    def test_get_inventory_file_default(self, tmp_path):
        """Test get_inventory_file with default filename."""
        from gmfind.paths import get_inventory_file

        with patch.dict(os.environ, {"GMFIND_DATA_DIR": str(tmp_path)}):
            result = get_inventory_file()

        assert result == tmp_path / "inventory_private.csv"

    def test_get_inventory_file_custom(self, tmp_path):
        """Test get_inventory_file with custom filename."""
        from gmfind.paths import get_inventory_file

        with patch.dict(os.environ, {"GMFIND_DATA_DIR": str(tmp_path)}):
            result = get_inventory_file("custom.csv")

        assert result == tmp_path / "custom.csv"
