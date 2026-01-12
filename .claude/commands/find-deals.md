---
description: Find discounted Steam games and generate a markdown recommendation document
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Deals Finder

Search for discounted Steam games and generate a detailed markdown report with reviews, scores, and recommendations. This skill is read-only and will NOT purchase any games.

## Arguments
- `$ARGUMENTS` - Format: `[COUNT] [--skip-inventory]`
  - **COUNT**: Number of games to include (default: 10)
  - **--skip-inventory**: Include owned games in report (for public reports)

## Usage Examples
```
/find-deals                      # 10 games, excludes owned games
/find-deals 5                    # 5 games, excludes owned games
/find-deals --skip-inventory     # 10 games, includes all games (public report)
/find-deals 20 --skip-inventory  # 20 games, includes all games (public report)
```

## Workflow

### Step 1: Read Current Preferences
First, read config.yaml to understand the user's current preferences:

```bash
cat /Users/mydev/code/steam-bot/config.yaml
```

Display a summary of the current criteria:
- max_price
- min_metacritic_score
- max_game_age_years
- min_protondb_rating
- min_steam_deck_level

### Step 2: Parse Arguments
Parse `$ARGUMENTS` to extract:
- **COUNT**: First numeric value, or 10 if not provided
- **--skip-inventory**: Check if this flag is present

Tell the user:
- How many games you're searching for
- Whether inventory check is enabled or skipped

### Step 3: Run Deals Finder
Execute the deals finder command:

```bash
cd /Users/mydev/code/steam-bot && venv/bin/python main.py --find-deals <COUNT> --config config.yaml --block-list block_list.yaml [--skip-inventory]
```

Add `--skip-inventory` flag only if it was specified in the arguments.

The report will be automatically saved to `docs/deals_YYYYMMDD_HHMMSS.md`.

### Step 4: Display Report
Read the generated report using the file path shown in the CLI output and display the full markdown content to the user.

## Data Sources
- **Steam Store API** - Official Steam sales and specials

## Review Sources
- **Steam** - User review percentages and summary
- **Metacritic** - Critic score and review quotes

## Report Contents
Each game includes:
- About This Game (description, genre, features)
- Why This Deal is Worth It (recommendation)
- Pricing table (original, sale, discount %)
- Scores (Steam, Metacritic, individual outlets)
- Critic Reviews (up to 5 quotes)
- Compatibility (Steam Deck, ProtonDB)

## Filters Applied
From config.yaml:
- **max_price**: Maximum price after discount
- **min_metacritic_score**: Minimum critic score
- **max_game_age_years**: Maximum game age

Additional automatic filters:
- Excludes DLC (type must be "game")
- Excludes games matching blocklist terms
- Excludes owned games (unless --skip-inventory is used)
- Flags games requiring 3rd party accounts

## Important Notes
- This skill is read-only and does NOT purchase games
- Report files are saved with unique timestamps to docs/ directory
- Use `--skip-inventory` when generating reports for public sharing
