---
description: Auto-purchase first game matching your config.yaml preferences
allowed-tools: Bash, Read, WebSearch
---

# Steam Auto-Buy Game

Automatically search for, validate, and purchase the first game matching your criteria.

## WARNING
This skill will automatically purchase a game WITHOUT further confirmation.
Real money will be spent from your Steam Wallet.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Configuration
Default genres and search year ranges are defined in `.claude/skill-config.yaml`. Read this file at the start of the workflow.

## Usage Examples
```
/auto-buy-game                              # Random genre from defaults
/auto-buy-game Metroidvania                 # Single genre
/auto-buy-game "Souls-like, Action RPG"     # Multiple genres
```

## Workflow

### Step 1: Pre-flight Checks
Run these commands in parallel:

```bash
cat .claude/skill-config.yaml
```

```bash
gmfind balance
```

```bash
cat ~/Library/Application\ Support/gmfind/config.yaml
```

```bash
wc -l ~/Library/Application\ Support/gmfind/inventory_private.csv 2>/dev/null | awk '{print $1 - 1}' || echo "0"
```

**CRITICAL**: Compare balance against max_price from config.yaml.
- If balance < max_price: **STOP** and report "Insufficient Steam Wallet balance. Current: $X.XX. Required: at least $[max_price]."
- If balance is sufficient: Display summary and proceed.

### Step 2: Parse Genre(s)
- If `$ARGUMENTS` is empty: randomly select 1-2 genres from `default_genres` in skill-config.yaml
- If `$ARGUMENTS` contains commas: split into multiple genres and search each
- Otherwise: use `$ARGUMENTS` as a single genre

Tell the user: "Searching for [genre] games..."

### Step 3: Search for Games
Use WebSearch to find highly-rated games. Calculate years from skill-config.yaml (e.g., if `recent: 2` and current year is 2026, use "2025 2026"). Run 2-3 queries in parallel:

1. **Recent + highly rated**: `best [genre] PC games [recent years] Steam highly rated`
2. **Gaming sites**: `site:pcgamer.com OR site:rockpapershotgun.com best [genre] games since [current_year - extended]`
3. **Budget-friendly** (if max_price < $20): `best [genre] PC games Steam under $[max_price]`

Extract 10-15 game titles (more candidates = better chances). Track which source each game came from.

### Step 4: Resolve Steam IDs
For each game title, get its Steam App ID:

```bash
gmfind id "<game title>"
```

Returns JSON: `{"steam_id": 123456, "title": "Game Name"}`

Run multiple `gmfind id` calls in parallel when possible. Skip games that aren't found on Steam.

### Step 5: Find First Valid Game
For each App ID in order:

```bash
gmfind check <APP_ID>
```

The CLI validates against ALL criteria in config.yaml:
- Price, Metacritic score, ProtonDB rating, Steam Deck compatibility
- Game age, blocklist, and ownership (auto-excludes games you own)

**STOP at the FIRST game where `"recommended": true`.**

If no games pass validation after checking all candidates:
- Report: "No games found matching your current config.yaml criteria."
- List the most common rejection reasons seen
- Suggest adjusting config.yaml settings

### Step 6: Execute Purchase
For the validated game, display details first:

```
## Auto-Purchasing: [Game Name]

**Source**: Found via [PC Gamer/Rock Paper Shotgun/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]
**Price**: $XX.XX

Proceeding with automatic purchase...
```

Then run:

```bash
gmfind buy <APP_ID>
```

### Step 7: Report Results

**On success**:
```
Successfully purchased [GAME NAME] for [PRICE]!

Source: [Website where found]
Steam Link: https://store.steampowered.com/app/[APP_ID]
```

**On failure**:
```
Purchase failed for [GAME NAME].

Error: [error message]

Troubleshooting:
- Try running with --headful flag for visual debugging
- Verify Steam login session is still valid
```

## Safety Measures
- Balance is verified against max_price BEFORE searching
- Only games passing ALL config.yaml criteria are considered
- Blocklist and owned-game checks prevent duplicates
- Single purchase per invocation (no loops)
- Source attribution is always shown

## Important Notes
- This skill purchases games WITHOUT confirmation
- Real money from your Steam Wallet will be spent
- Games MUST be available on Steam
- One game is purchased per invocation
- If you want to review before buying, use `/find-game` instead
