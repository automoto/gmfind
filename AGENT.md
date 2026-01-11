# Developer Guide (AGENT.md)

This guide provides instructions for AI agents and developers working on the Steam Bot codebase.

## Project Structure

The project follows a modular structure:

```
steam-bot/
├── main.py                 # CLI entry point
├── src/                    # Source code
│   ├── config.py           # Configuration loading (Pydantic)
│   ├── steam_auth.py       # Headless authentication (Playwright Sync)
│   ├── buy_game.py         # Purchase logic
│   ├── check_balance.py    # Wallet balance checking
│   ├── inventory.py        # Owned games checking (Requests)
│   ├── game_check.py       # Game details aggregator
│   └── recommendations/    # Sub-modules for ratings
│       ├── protondb.py     # ProtonDB API client
│       ├── steam_deck.py   # Official Steam Deck verification
│       └── metacritic.py   # Metacritic scraper
├── venv/                   # Virtual environment (do not commit)
├── Makefile                # Task runner
└── requirements.txt        # Python dependencies
```

## Development Workflow

### 1. Environment Setup

Always use the `Makefile` to set up the environment. This ensures consistent dependencies and browser binaries.

```bash
make install
```

This command will:
1.  Create a virtual environment (`venv`).
2.  Install python dependencies from `requirements.txt`.
3.  Install development tools (`ruff`, `mypy`).
4.  Install Playwright browsers (`chromium`).

### 2. Running Code

**Crucial Rule:** Always use the python interpreter inside the virtual environment (`venv/bin/python`).

*   **CLI:**
    ```bash
    venv/bin/python main.py <args>
    ```
    *   `--login`: Interactive headless login with 2FA support.
    *   `--balance`: Check wallet balance.
    *   `--check-game <APP_ID>`: Get full JSON report for a game.
    *   `--check-blocklist <TITLE>`: Check if a game title matches the blocklist.
    *   `--inventory-csv [FILENAME]`: Export your game library to CSV (default: inventory.csv).
    *   `--buy <APP_ID>`: Purchase a game (safety stop enabled by default).

*   **Shortcuts:**
    *   `make login`: Runs the auth script.
    *   `make balance`: Runs balance check.

### 3. Code Quality Standards

We enforce strict code quality using `ruff` (linting/formatting) and `mypy` (static typing).

*   **Format:**
    ```bash
    make format
    ```
    (Runs `ruff format` and `ruff check --fix`)

*   **Lint:**
    ```bash
    make lint
    ```
    (Runs `ruff check`)

*   **Type Check:**
    ```bash
    make type-check
    ```
    (Runs `mypy` with strict settings)

*   **Run All Checks:**
    ```bash
    make check
    ```

**Do not commit code that fails `make check`.**

### 4. Implementation Guidelines

*   **Synchronous Python:** Prefer synchronous code (`requests`, `playwright.sync_api`) over `asyncio` for simplicity and reliability in CLI contexts.
*   **Robust Selectors:** When interacting with the Steam Store, use multiple fallback selectors (ID, Class, Text) because Valve frequently updates the UI. See `src/steam_auth.py` for examples.
*   **Error Handling:** Wrap external API calls (Steam, ProtonDB) in try/except blocks. Fail gracefully if a service is down.
*   **Safety:** Any code that spends money (clicking "Purchase") must have a safety mechanism (commented out by default or explicit flag) to prevent accidental spending during development.

### 5. Managing Dependencies

If you add a new library:
1.  Add it to `requirements.txt`.
2.  If it's for typing, add the `types-` package as well.
3.  Run `make install` to update your venv.
