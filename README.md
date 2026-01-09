# Steam Auto-Buyer Bot

A Python CLI bot that automatically purchases games on Steam based on your preferences. It uses Metacritic for quality ratings and ProtonDB for Steam Deck compatibility.

## Features

- Finds game recommendations based on Metacritic scores and ProtonDB ratings
- Analyzes your existing game library to match preferences
- Checks Steam Deck compatibility via ProtonDB
- Verifies wallet balance before purchase
- Prevents duplicate purchases by checking owned games
- Dry-run mode for testing without purchasing

## Requirements

- Python 3.10+
- Steam account with:
  - Public game library (for inventory checking)
  - Steam Wallet balance (for purchases)

## Installation

```bash
# Clone the repository
cd steam-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Configuration

### 1. Set Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
STEAM_USERNAME=your_username
STEAM_PASSWORD=your_password
STEAM_ID=76561198xxxxxxxxx  # Your 64-bit Steam ID
```

Find your Steam ID at: https://steamid.io/

### 2. Configure Preferences

Edit `config.yaml`:

```yaml
steam:
  steam_id: "76561198xxxxxxxxx"  # Can also use STEAM_ID env var

preferences:
  max_price: 20.00              # Maximum price in USD
  min_metacritic_score: 75      # Minimum Metacritic score (0-100)
  min_protondb_rating: "gold"   # Minimum ProtonDB rating
```

ProtonDB rating options (best to worst):
- `platinum` - Perfect compatibility
- `gold` - Works well
- `silver` - Works with minor issues
- `bronze` - Works with significant issues
- `borked` - Does not work

## Usage

### Dry Run (Recommended First)

Test without making a purchase:

```bash
python main.py --dry-run
```

### Make a Purchase

```bash
python main.py
```

### Options

```
--dry-run    Find a recommendation but don't purchase
--headless   Run browser without visible window
--config     Path to config file (default: config.yaml)
-v           Enable verbose debug logging
```

## How It Works

1. **Load Configuration** - Reads credentials from environment and preferences from config file
2. **Analyze Library** - Fetches your owned games and analyzes genre/tag preferences
3. **Find Recommendations** - Scrapes Metacritic for highly-rated PC games
4. **Filter Games** - Filters by:
   - Not already owned
   - Within price limit
   - Meets Metacritic score threshold
   - Meets ProtonDB compatibility rating
   - Matches your preference profile
5. **Purchase** - Uses Playwright to automate the Steam store checkout

## Logging

Logs are written to both console and `steam_bot.log`.

## Security Notes

- Credentials are stored in environment variables, not in config files
- The `.env` file is gitignored to prevent accidental commits
- Browser automation runs with your actual Steam session
