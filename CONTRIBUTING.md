# Developer Guide

This guide provides instructions for developers or AI agents working on the gmfind codebase.

## Development Workflow

### 1. Environment Setup

Use [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
# Install package in development mode with dev dependencies
make install

# Initialize Playwright browsers
make init
```

Or manually:
```bash
uv pip install -e ".[dev]"
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
| `buy <APP_ID>` | Purchase a game (with confirmation) | Yes |
| `rec-buy-auto` | Autonomous: balance -> recommend -> buy | Yes |
| `inventory --private` | Export library via browser | Yes |
| `inventory --public` | Export library via API | No |
| `blocklist <TITLE>` | Check if title matches blocklist | No |

**Per-Command Options:**

Commands that filter games accept these options:
- `--config PATH` - Path to config.yaml
- `--block-list PATH` - Path to block_list.yaml
- `--inventory PATH` - Path to inventory CSV
- `--headful` - Run browser visibly (for `buy`, `inventory --private`)
- `--auto` - Skip confirmation prompt (for `buy`)

**Examples:**
```bash
uv run gmfind check 1145350
uv run gmfind deals 5 --config ./config.yaml
uv run gmfind buy 1145350 --headful
uv run gmfind inventory --private --output ./games.csv
```

### 3. Code Quality Standards

We use `ruff` for linting/formatting and `mypy` for type checking. Use the Makefile commands:

```bash
# Run all checks (lint + type-check) - required before committing
make check

# Individual commands
make lint         # Run ruff linter
make format       # Format code with ruff
make type-check   # Run mypy type checker

# Run tests
uv run pytest tests/ -v
```

**Do not commit code that fails `make check`.**

To see all available make commands:
```bash
make help
```

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
make install
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
