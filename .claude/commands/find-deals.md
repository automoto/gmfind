---
description: Find discounted Steam games and generate a markdown recommendation document
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Deals Finder

Search for discounted Steam games and generate a detailed markdown report with reviews, scores, and recommendations. This skill is read-only and will NOT purchase any games.

## Arguments
- `$ARGUMENTS` - Format: `[COUNT] [-o PATH] [--skip-inventory]`
  - **COUNT**: Number of games to include (default: 10)
  - **-o PATH** or **--output PATH**: Output path for the report
    - No path: Print markdown to stdout (default)
    - Directory (e.g., `reports/`): Generate timestamped file in that directory
    - File path (e.g., `reports/deals.md`): Write to exact file
  - **--skip-inventory**: Include owned games in report (for public reports)

## Usage Examples
```
/find-deals                         # 10 games, prints markdown to stdout
/find-deals 5                       # 5 games, prints to stdout
/find-deals -o reports/             # 10 games, saves to reports/deals_TIMESTAMP.md
/find-deals -o my-deals.md          # 10 games, saves to my-deals.md
/find-deals 20 -o docs/ --skip-inventory  # 20 games, timestamped file, includes all
```

## Workflow

### Step 1: Read Current Preferences
First, read config.yaml to understand the user's current preferences:

```bash
cat config.yaml
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
- **-o PATH** or **--output PATH**: Output path (value following -o or --output flag)
- **--skip-inventory**: Check if this flag is present

Tell the user:
- How many games you're searching for
- Where the output will go (stdout, directory with timestamp, or specific file)
- Whether inventory check is enabled or skipped

### Step 3: Run Deals Finder
Execute the deals finder command:

```bash
uv run gmfind deals <COUNT> --config config.yaml --block-list block_list.yaml [-o <PATH>] [--skip-inventory]
```

- Add `-o <PATH>` if `-o` or `--output` was specified in the arguments
- Add `--skip-inventory` flag only if it was specified in the arguments
- If no output path specified, markdown is printed to stdout

### Step 4: Display Report
- If output was to stdout: The markdown is already displayed
- If output was to a file: Read the generated report using the file path shown in the CLI output and display the full markdown content to the user

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
- Default output is to stdout (no file created)
- Use `-o <directory>/` to save with timestamped filename
- Use `-o <filepath>` to save to a specific file
- Use `--skip-inventory` when generating reports for public sharing
