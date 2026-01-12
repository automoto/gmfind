---
description: Find PC games and purchase with confirmation
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Game Finder (with Purchase Option)

Search the internet for highly-rated PC games, validate them, and purchase with user confirmation.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Default Genres (Steam Tags)
```
Action, Action-Adventure, Action RPG, Platformer, 2D Platformer, Indie,
Metroidvania, Adventure, RTS, Strategy, Fighting, Military, FPS, Souls-like
```

## Usage Examples
```
/find-game                              # Random genre from defaults
/find-game Metroidvania                 # Single genre
/find-game "Souls-like, Action RPG"     # Multiple genres
```

## Workflow

### Step 1: Check Wallet Balance
First, check the Steam Wallet balance:

```bash
cd /Users/mydev/code/steam-bot && venv/bin/python main.py --balance
```

Report the current balance to the user. If balance is $0 or retrieval fails, warn that purchases may fail.

### Step 2: Read Current Preferences
Read config.yaml to understand the user's current preferences:

```bash
cat /Users/mydev/code/steam-bot/config.yaml
```

Display a summary of the current criteria so the user knows what filters will be applied.

### Step 3: Parse Genre(s)
- If `$ARGUMENTS` is empty: randomly select 1-2 genres from the default list above
- If `$ARGUMENTS` contains commas: split into multiple genres and search each
- Otherwise: use `$ARGUMENTS` as a single genre

Tell the user which genre(s) you're searching for.

### Step 4: Search for Games
Use the WebSearch tool to find highly-rated games. There is a slight preference for recent games, but classic/older games are welcome as long as they meet the max_game_age_years setting in config.yaml.

Try these queries:

1. **Primary (recent focus)**: `best [genre] PC games 2024 2025 Steam highly rated`
2. **Site-specific**: `site:pcgamer.com OR site:rockpapershotgun.com OR site:ign.com best [genre] games`
3. **Classic games**: `best [genre] PC games all time Steam classics` (for variety)
4. **Fallback**: `top [genre] Steam games Metacritic high score`

Extract 5-10 game titles from the search results. Track which source each game came from.

### Step 5: Find Steam App IDs
For each game title, resolve its Steam App ID:

1. Use WebFetch on: `https://store.steampowered.com/search/?term=[URL-encoded game name]&category1=998`
2. Look for URLs matching pattern: `/app/(\d+)/`
3. Extract the App ID from the first matching result
4. If WebFetch fails, try WebSearch: `[game name] Steam store app id`

Skip games that can't be found on Steam. Games MUST be available on Steam.

### Step 6: Validate Each Game
For each App ID found, run this command using Bash:

```bash
cd /Users/mydev/code/steam-bot && venv/bin/python main.py --check-game <APP_ID> --config config.yaml --block-list block_list.yaml
```

The CLI will validate the game against ALL criteria in config.yaml:
- Price (max_price)
- Metacritic score (min_metacritic_score)
- ProtonDB rating (min_protondb_rating)
- Steam Deck compatibility (min_steam_deck_level)
- Game age (max_game_age_years)
- Blocklist check (block_list.yaml)
- Ownership check (not already owned)

Parse the JSON output. A game passes if `"recommended": true`.

### Step 7: Present Top Recommendation
Present the FIRST validated game with full details and source attribution:

```
## Recommended: [Game Name]

**Source**: Found via [PC Gamer/Rock Paper Shotgun/IGN/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]
**Validated by**: steam-bot --check-game (passed all config.yaml criteria)

**Current config.yaml preferences applied:**
[Show the relevant settings from config.yaml]

| Attribute | Value | Your Requirement | Status |
|-----------|-------|------------------|--------|
| Price | $XX.XX | From config.yaml | Pass |
| Metacritic | XX | From config.yaml | Pass |
| ProtonDB | [tier] | From config.yaml | Pass |
| Steam Deck | [status] | From config.yaml | Pass |
| Age | X years | From config.yaml | Pass |
```

### Step 8: Ask for Purchase Confirmation
**CRITICAL**: You MUST ask the user for explicit confirmation before purchasing.

Ask: "Would you like to purchase [GAME NAME] for [PRICE]? (yes/no)"

- Wait for the user's response
- Only proceed if they explicitly say "yes"
- If they say "no" or anything else, do NOT purchase

### Step 9: Execute Purchase (if confirmed)
If and only if the user confirmed with "yes", run:

```bash
cd /Users/mydev/code/steam-bot && venv/bin/python main.py --buy <APP_ID>
```

Report the result:
- On success: "Successfully purchased [GAME NAME] for [PRICE]!"
- On failure: Report the error and suggest checking `purchase_failed.png` or running with `--headful` flag for debugging

## Dynamic Configuration
All validation criteria come from `config.yaml`. The user can modify this file anytime to change their preferences:

```yaml
preferences:
  max_price: 60.00              # Maximum price in USD
  min_metacritic_score: 91      # Minimum Metacritic score (0-100)
  min_protondb_rating: "gold"   # Options: platinum, gold, silver, bronze, borked
  min_steam_deck_level: "playable"  # Options: verified, playable, unsupported
  max_game_age_years: 2         # Maximum age of games to consider
```

Games on `block_list.yaml` are always excluded.

## Important Notes
- **ALWAYS ask for user confirmation before purchasing**
- This uses real money from your Steam Wallet
- Games MUST be available on Steam
- Always show the Steam store link so the user can review the game page
- Always show which website the recommendation came from
- Slight preference for recent games, but classics within max_game_age_years are welcome
- If purchase fails, the user can check `purchase_failed.png` for a screenshot
