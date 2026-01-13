"""Post-install setup for gmfind.

Handles:
1. Creating config directories
2. Generating example config files
3. Installing Playwright browsers
"""

import subprocess
import sys

from gmfind.paths import (
    ensure_directories,
    get_blocklist_file,
    get_config_dir,
    get_config_file,
    get_data_dir,
    get_example_blocklist,
    get_example_config,
    get_log_dir,
)


def install_playwright_browsers() -> bool:
    """Install Playwright Chromium browser."""
    print("Installing Playwright Chromium browser...")
    print("This may take a few minutes on first run.\n")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error installing Playwright browsers: {e}")
        return False
    except FileNotFoundError:
        print("Error: Playwright not found. Please reinstall gmfind.")
        return False


def create_config_files() -> None:
    """Create example config files if they don't exist."""
    config_file = get_config_file()
    blocklist_file = get_blocklist_file()

    if not config_file.exists():
        print(f"Creating config file: {config_file}")
        config_file.write_text(get_example_config())
    else:
        print(f"Config file exists: {config_file}")

    if not blocklist_file.exists():
        print(f"Creating blocklist file: {blocklist_file}")
        blocklist_file.write_text(get_example_blocklist())
    else:
        print(f"Blocklist file exists: {blocklist_file}")


def print_env_instructions() -> None:
    """Print instructions for setting environment variables."""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("\n1. Set your Steam credentials as environment variables:")
    print("   export STEAM_USERNAME='your_username'")
    print("   export STEAM_PASSWORD='your_password'")
    print("   export STEAM_ID='76561198xxxxxxxxx'")
    print("\n   Add these to your ~/.bashrc, ~/.zshrc, or shell profile.")
    print("\n2. Edit your config file:")
    print(f"   {get_config_file()}")
    print("\n3. Run your first command:")
    print("   gmfind deals 2")
    print("=" * 60 + "\n")


def run_setup() -> int:
    """Run the complete setup process."""
    print("=" * 60)
    print("gmfind Setup")
    print("=" * 60 + "\n")

    # 1. Create directories
    print("Creating directories...")
    ensure_directories()
    print(f"  Config: {get_config_dir()}")
    print(f"  Data: {get_data_dir()}")
    print(f"  Logs: {get_log_dir()}")
    print()

    # 2. Create config files
    create_config_files()
    print()

    # 3. Install Playwright browsers
    success = install_playwright_browsers()
    if not success:
        print("\nWarning: Playwright browser installation failed.")
        print("You can manually install with: playwright install chromium")

    # 4. Print instructions
    print_env_instructions()

    return 0 if success else 1


def main() -> int:
    """Entry point for gmfind-setup command."""
    return run_setup()


if __name__ == "__main__":
    sys.exit(main())
