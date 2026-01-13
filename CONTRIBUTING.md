# Developer Guide (AGENT.md)

This guide provides instructions for AI agents and developers working on the gmfind codebase.

## Project Structure

```
steam-bot/
├── pyproject.toml              # Package config, dependencies, entry points
├── src/gmfind/                 # Main package
│   ├── __init__.py             # Version info
│   ├── __main__.py             # python -m gmfind support
│   ├── cli.py                  # CLI entry point (argparse subcommands)
│   ├── config.py               # Configuration loading (Pydantic)
│   ├── paths.py                # XDG-compliant path handling
│   ├── setup.py                # Post-install setup (Playwright browsers)
│   ├── steam_auth.py           # Headless authentication (Playwright Sync)
│   ├── buy_game.py             # Purchase logic
│   ├── check_balance.py        # Wallet balance checking
│   ├── game_check.py           # Game details aggregator
│   ├── find_deals.py           # Deal discovery from Steam API
│   ├── report_generator.py     # Markdown report generation
│   ├── blocklist_checker.py    # Game title filtering
│   ├── inventory.py            # API-based library export
│   ├── inventory_private.py    # Browser-based library export
│   └── recommendations/        # Rating clients
│       ├── __init__.py
│       ├── protondb.py         # ProtonDB API
│       ├── steam_deck.py       # Steam Deck verification
│       └── metacritic.py       # Metacritic scraper
```

## Development Workflow

### 1. Environment Setup

Use [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
# Install package in development mode
uv pip install -e .

# Initialize Playwright browsers
gmfind init
```

### 2. Running Commands

The CLI uses subcommands. Always use `uv run` or ensure the package is installed:

```bash
# Via uv run (recommended during development)
uv run gmfind <command>

# Or if installed
gmfind <command>
```

**Available Commands:**

| Command | Description | Auth Required |
|---------|-------------|---------------|
| `init` | Initialize config and Playwright | No |
| `check <APP_ID>` | Get game details (price, ProtonDB, Deck, reviews) | No |
| `deals [COUNT]` | Find discounted games | No |
| `balance` | Check Steam Wallet balance | Yes |
| `buy <APP_ID>` | Purchase a game | Yes |
| `buy --auto` | Autonomous buy workflow | Yes |
| `inventory --private` | Export library via browser | Yes |
| `inventory --public` | Export library via API | No |
| `blocklist <TITLE>` | Check if title matches blocklist | No |

**Per-Command Options:**

Commands that filter games accept these options:
- `--config PATH` - Path to config.yaml
- `--block-list PATH` - Path to block_list.yaml
- `--inventory PATH` - Path to inventory CSV
- `--headful` - Run browser visibly (for `buy`, `inventory --private`)
- `--force` - Skip validation (for `buy`)

**Examples:**
```bash
uv run gmfind check 1145350
uv run gmfind deals 5 --config ./config.yaml
uv run gmfind buy 1145350 --headful
uv run gmfind inventory --private --output ./games.csv
```

### 3. Code Quality Standards

We use `ruff` for linting/formatting and `mypy` for type checking.

```bash
# Format code
uv run ruff format .

# Lint (with auto-fix)
uv run ruff check --fix .

# Type check
uv run mypy src/gmfind

# Run all checks
uv run ruff check . && uv run mypy src/gmfind
```

**Do not commit code that fails these checks.**

### 4. Implementation Guidelines

- **Synchronous Python**: Use `requests` and `playwright.sync_api` for simplicity in CLI contexts.
- **Robust Selectors**: Steam UI changes frequently. Use multiple fallback selectors (ID, class, text). See `steam_auth.py` for examples.
- **Error Handling**: Wrap external API calls in try/except. Fail gracefully if Steam/ProtonDB is down.
- **Safety**: Purchase code has safety mechanisms. The final "Purchase" click is protected.
- **XDG Paths**: Use `paths.py` for all file locations. Never hardcode paths.

### 5. Adding Dependencies

Dependencies are managed in `pyproject.toml`:

```toml
[project]
dependencies = [
    "playwright>=1.40.0",
    "requests>=2.31.0",
    # ... etc
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

After modifying:
```bash
uv pip install -e .
```

### 6. Configuration System

Config is loaded via `config.py` using Pydantic models:

- **Environment Variables** (required):
  - `STEAM_USERNAME`
  - `STEAM_PASSWORD`
  - `STEAM_ID`

- **Config File** (`config.yaml`):
  ```yaml
  preferences:
    max_price: 20.0
    min_metacritic_score: 75
    min_protondb_rating: gold
    min_steam_deck_level: playable
    max_game_age_years: 20
  ```

- **Blocklist** (`block_list.yaml`):
  ```yaml
  - fifa
  - nba 2k
  - madden
  ```

### 7. Key Files Reference

| File | Purpose |
|------|---------|
| `cli.py` | Argparse subcommands, command dispatch |
| `game_check.py` | `check_game_data()` returns structured dict for validation |
| `find_deals.py` | Fetches Steam specials, filters by preferences |
| `steam_auth.py` | Login flow with Steam Guard (email/2FA) |
| `paths.py` | XDG path resolution for all platforms |
