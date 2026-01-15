# gmfind: Game Finder

A Python CLI tool for recommendations and purchasing of PC games. Steam is the store front that is primarily supported. 

`gmfind` will look for high quality games based on your configurable preferences for steam and metacritic ratings, discounts and compatibility ratings.

## Features

- **Game Discovery**: Find discounted games filtered by price, Metacritic score, ProtonDB rating, and Steam Deck compatibility.
- **Compatibility Checks**: Get ProtonDB and Steam Deck verification status for any game.
- **Smart Filtering**: Exclude games you already own, match blocklist patterns, and enforce preference criteria.
- **Headless Purchasing**: Buy games using your Steam Wallet with Playwright browser automation.
- **Private Profile Support**: Export your game library even with a private Steam profile.

## Safety Notice

**Purchases use Steam Wallet only.** This tool will never use credit cards, PayPal, or any external payment methods. All purchases are made exclusively from your Steam Wallet balance.

- The `gmfind buy` command validates games against your config before purchasing
- Use `gmfind buy --auto` with caution - it will automatically purchase a recommended game
- Set a conservative `max_price` in your config to limit spending
- Your Steam Wallet balance acts as a natural spending cap

We recommend adding a small amount to your Steam Wallet and testing with `--headful` mode first to observe the purchase flow before enabling autonomous buying.

## Installation

### For Users

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv).

```bash
# Install globally as a CLI tool
uv tool install gmfind

# Initialize (creates config templates)
gmfind init
```

Alternative with pipx:
```bash
pipx install gmfind
gmfind init
```

### Browser Commands (Optional)

Some commands require Playwright for browser automation (see [Command Reference](#command-reference) below). To enable these:

```bash
# Install Playwright
pip install playwright

# Download Chromium browser
playwright install chromium
```

Or install gmfind with browser support in one step:
```bash
uv tool install 'gmfind[browser]'
playwright install chromium
```

### For Developers

See [Development](#development) section below.

## Configuration

Set your Steam credentials as environment variables:

```bash
export STEAM_USERNAME="your_username"
export STEAM_PASSWORD="your_password"
export STEAM_ID="76561198xxxxxxxxx"
```

Add these to your shell profile (`~/.zshrc` or `~/.bashrc`) to make them permanent.

### Config Files

Config files are stored in platform-specific locations:
- **Linux/macOS**: `~/.config/gmfind/`
- **Windows**: `%APPDATA%\gmfind\`

Files:
- `config.yaml` - Preferences (max price, min ratings, etc.)
- `block_list.yaml` - Game title patterns to exclude

## Command Reference

Commands are divided into two categories based on their dependencies:

### API Commands (No Playwright Required)
These work immediately after installation:
| Command | Description |
|---------|-------------|
| `gmfind check <APP_ID>` | Get game details (price, ratings, compatibility) |
| `gmfind deals [N]` | Find N discounted games matching your preferences |
| `gmfind id "<TITLE>"` | Look up a game's Steam App ID |
| `gmfind blocklist "<TITLE>"` | Check if a title matches your blocklist |
| `gmfind inventory --public` | Export game library (requires public Steam profile) |

### Browser Commands (Playwright Required)
These require Playwright installation (see [Browser Commands](#browser-commands-optional)):
| Command | Description |
|---------|-------------|
| `gmfind buy <APP_ID>` | Purchase a game using Steam Wallet |
| `gmfind balance` | Check your Steam Wallet balance |
| `gmfind inventory --private` | Export game library (works with private profiles) |
| `gmfind rec-buy-auto` | Autonomous recommend and purchase workflow |

## Usage

### Check Game Details
Get comprehensive info including price, ProtonDB rating, Steam Deck status, and reviews:
```bash
gmfind check 1145350
```

### Find Deals
Find discounted games matching your preferences:
```bash
gmfind deals           # Find 10 deals
gmfind deals 5         # Find 5 deals
gmfind deals --output ./deals.md   # Save to file
```

### Purchase a Game
Buy a game by App ID (validates against your config first):
```bash
gmfind buy 1145350            # Buy specific game (shows confirmation prompt)
gmfind buy 1145350 --auto     # Skip confirmation prompt
gmfind buy 1145350 --headful  # Show browser window
```

### Autonomous Buy
Automatically find a recommended game and purchase it:
```bash
gmfind rec-buy-auto           # Check balance -> recommend -> buy
```

### Check Wallet Balance
```bash
gmfind balance
```

### Export Game Library
```bash
gmfind inventory --private    # Browser-based (works with private profiles)
gmfind inventory --public     # API-based (requires public profile)
```

### Check Blocklist
```bash
gmfind blocklist "FIFA 24"
```

### Find Steam App ID
Look up a game's Steam App ID by title:
```bash
gmfind id "Hades"
```
Output: `{"steam_id": 1145360, "title": "Hades"}`

### Search by Name
Look up a game by title and get full details in one command:
```bash
gmfind id "Hades II" | jq '.steam_id' | xargs gmfind check
```

### Global Options
```bash
gmfind --version     # Show version
gmfind --verbose     # Enable debug logging
gmfind <cmd> --help  # Command-specific help
```

### Per-Command Options
Most commands accept config overrides:
```bash
gmfind deals 5 --config ./config.yaml --block-list ./blocklist.yaml
gmfind check 1145350 --inventory ./my_games.csv
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/gmfind.git
cd gmfind

# Install in development mode with dev dependencies
make install

# Initialize Playwright browsers
make init
```

### Running Locally

```bash
# Run commands through uv
uv run gmfind --help
uv run gmfind check 1145350

# Or activate the virtual environment
source .venv/bin/activate
gmfind --help
```

### Code Quality

```bash
make lint        # Run ruff linter
make format      # Format code with ruff
make type-check  # Run mypy type checker
make check       # Run all checks
```

### Building

```bash
# Install build tools
uv pip install build twine

# Build the package
uv run python -m build

# This creates:
#   dist/gmfind-0.1.0.tar.gz
#   dist/gmfind-0.1.0-py3-none-any.whl
```

### Testing Locally Before Publishing

```bash
# Create a test environment
uv venv /tmp/test-gmfind
source /tmp/test-gmfind/bin/activate

# Install your local build
pip install dist/gmfind-*.whl

# Test it
gmfind --version
gmfind check 1145350

# Clean up
deactivate
rm -rf /tmp/test-gmfind
```

### Publishing

```bash
# Upload to TestPyPI first
uv run twine upload --repository testpypi dist/*

# Then upload to PyPI
uv run twine upload --repository pypi dist/*
```

### Versioning

Update version in `src/gmfind/__init__.py` before releasing:
```python
__version__ = "0.2.0"
```

Then rebuild and publish.

### Security

- Credentials are read from environment variables, never stored in config files.
- Session data is stored locally in XDG data directory.
- Browser automation uses real Chromium with human-like behavior.

### Troubleshooting

When errors occur during login or purchase, screenshots are automatically saved for debugging.

**File locations** (platform-specific):
- **Linux/macOS**: `~/.cache/gmfind/`
- **Windows**: `%LOCALAPPDATA%\gmfind\Cache\`

**Troubleshooting files:**
- `screenshots/` - Error screenshots (e.g., `login_failed.png`, `purchase_failed.png`)
- `logs/gmfind.log` - Application logs

**Common issues:**
- Login fails: Check `screenshots/login_*.png` for the browser state at failure
- Purchase fails: Check `screenshots/purchase_failed.png` or `checkout_failed.png`
- Run with `--headful` flag to watch the browser in real-time
