# Steam Bot CLI

A Python CLI tool for managing Steam account actions like checking wallet balance and purchasing games headlessly using Playwright.

## Features

- **Headless Login**: Authenticate with Steam Guard (Email/2FA) directly from your terminal.
- **Session Persistence**: Login once and stay authenticated for future commands.
- **Check Balance**: Quickly check your Steam Wallet balance.
- **Automated Purchase**: Purchase games by App ID using your Steam Wallet.
- **ProtonDB Checks**: Check Steam Deck compatibility ratings without logging in.

## Requirements

- Python 3.10+
- Steam account with Steam Wallet funds for purchases.

## Installation

1. **Clone the repository:**
   ```bash
   cd steam-bot
   ```

2. **Setup environment and dependencies:**
   ```bash
   make install
   ```
   This will create a virtual environment, install dependencies from `requirements.txt`, and install the Playwright Chromium browser.

## Configuration

Set up your credentials in a `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
STEAM_USERNAME=your_username
STEAM_PASSWORD=your_password
STEAM_ID=76561198xxxxxxxxx
```

## Usage

All commands are executed through `main.py`. Ensure you are using the virtual environment python.

**Option 1: Explicit path**
```bash
venv/bin/python main.py <args>
```

**Option 2: Activate venv first**
```bash
source venv/bin/activate
python main.py <args>
```

The tool will automatically prompt for login if a command requires authentication.

### 1. Purchase a Game (Requires Login)
Add a game to your library using its App ID.
```bash
venv/bin/python main.py --buy <APP_ID>
```
*Example: `venv/bin/python main.py --buy 1145350` (Hades II)*

**Note:** By default, the script stops right before the final "Purchase" click for safety. To enable real transactions, you must uncomment the click action in `src/buy_game.py`.

### 2. Check Wallet Balance (Requires Login)
```bash
venv/bin/python main.py --balance
```

### 3. Check Game Details (No Login Required)
Get a structured JSON report including Price, Metacritic, ProtonDB, and Steam Deck status.
```bash
venv/bin/python main.py --check-game <APP_ID>
```

### 4. Check Specific Ratings (No Login Required)
```bash
venv/bin/python main.py --protondb <APP_ID>
venv/bin/python main.py --deck <APP_ID>
```

## Project Structure

- `main.py`: CLI entry point.
- `src/steam_auth.py`: Headless login and 2FA handling.
- `src/buy_game.py`: Store navigation and checkout flow.
- `src/check_balance.py`: Account balance retrieval.
- `src/recommendations/protondb.py`: ProtonDB API client.

## Development

- **Linting**: `make lint`
- **Formatting**: `make format`
- **Type Checking**: `make type-check`

## Security

- Credentials are read from `.env` and never hardcoded.
- Session data is stored locally in `steam_browser_auth.json`.
- Headless automation mimics real browser behavior.
