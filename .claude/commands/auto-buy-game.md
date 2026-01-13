---
description: Auto-purchase first game matching your config.yaml preferences
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Auto-Buy Game

Automatically search for, validate, and purchase the first game matching your criteria.

## WARNING
This skill will automatically purchase a game WITHOUT further confirmation.
Real money will be spent from your Steam Wallet.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Default Genres (Steam Tags)
```
Action, Action-Adventure, Action RPG, Platformer, 2D Platformer, Indie,
Metroidvania, Adventure, RTS, Strategy, Fighting, Military, FPS, Souls-like
```

## Usage Examples
```
/auto-buy-game                              # Random genre from defaults
/auto-buy-game Metroidvania                 # Single genre
/auto-buy-game "Souls-like, Action RPG"     # Multiple genres
```

## Workflow

### Step 1: Read Current Preferences
First, read config.yaml to understand the user's current preferences:

```bash
cat config.yaml
```

Display a summary of the current criteria so the user knows what filters will be applied.

### Step 2: Pre-flight Balance Check
Check the Steam Wallet balance:

```bash
uv run gmfind balance
```

**CRITICAL**: Compare the balance against max_price from config.yaml. If the balance is less than max_price, STOP immediately and report:
"Insufficient Steam Wallet balance. Current balance: $X.XX. Required: at least $[max_price from config] to ensure purchase can complete."

If balance is sufficient, report it and proceed.

### Step 3: Parse Genre(s)
- If `$ARGUMENTS` is empty: randomly select 1-2 genres from the default list above
- If `$ARGUMENTS` contains commas: split into multiple genres and search each
- Otherwise: use `$ARGUMENTS` as a single genre

Tell the user: "Searching for [genre] games..."

### Step 4: Search for Games
Use the WebSearch tool to find highly-rated games. There is a slight preference for recent games, but classic/older games are welcome as long as they meet the max_game_age_years setting in config.yaml.

Try these queries:

1. **Primary (recent focus)**: `best [genre] PC games 2024 2025 Steam highly rated`
2. **Site-specific**: `site:pcgamer.com OR site:rockpapershotgun.com OR site:ign.com best [genre] games`
3. **Classic games**: `best [genre] PC games all time Steam classics` (for variety)
4. **Fallback**: `top [genre] Steam games Metacritic high score`

Extract 10-15 game titles from the search results (more candidates = better chances). Track which source each game came from.

### Step 5: Find Steam App IDs
For each game title, resolve its Steam App ID:

1. Use WebFetch on: `https://store.steampowered.com/search/?term=[URL-encoded game name]&category1=998`
2. Look for URLs matching pattern: `/app/(\d+)/`
3. Extract the App ID from the first matching result
4. If WebFetch fails, try WebSearch: `[game name] Steam store app id`

Skip games that can't be found on Steam. Games MUST be available on Steam.

### Step 6: Find First Valid Game
For each App ID in order, run this command using Bash:

```bash
uv run gmfind check <APP_ID> --config config.yaml --block-list block_list.yaml
```

The CLI will validate the game against ALL criteria in config.yaml:
- Price (max_price)
- Metacritic score (min_metacritic_score)
- ProtonDB rating (min_protondb_rating)
- Steam Deck compatibility (min_steam_deck_level)
- Game age (max_game_age_years)
- Blocklist check (block_list.yaml)
- Ownership check (not already owned)

**STOP at the FIRST game where `"recommended": true`.**

If no games pass validation after checking all candidates:
- Report: "No games found matching your current config.yaml criteria."
- List the most common rejection reasons seen
- Suggest adjusting config.yaml settings

### Step 7: Execute Purchase
For the validated game, display its details first:

```
## Auto-Purchasing: [Game Name]

**Source**: Found via [PC Gamer/Rock Paper Shotgun/IGN/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]
**Price**: $XX.XX

**Validated against config.yaml:**
[Show the relevant settings that were checked]

Proceeding with automatic purchase...
```

Then run:

```bash
uv run gmfind buy <APP_ID>
```

### Step 8: Report Results
Based on the purchase command output:

**On success**:
```
Successfully purchased [GAME NAME] for [PRICE]!

Source: [Website where the recommendation was found]
Steam Link: https://store.steampowered.com/app/[APP_ID]
```

**On failure**:
```
Purchase failed for [GAME NAME].

Error: [error message from output]

Troubleshooting:
- Try running with --headful flag for visual debugging
- Verify Steam login session is still valid
```

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

## Safety Measures
- Balance is verified against max_price from config.yaml BEFORE searching
- Only games passing ALL config.yaml criteria are considered
- Blocklist and owned-game checks prevent duplicates
- Single purchase per invocation (no loops)
- Source attribution is always shown so user knows where recommendation came from

## Important Notes
- This skill purchases games WITHOUT confirmation
- Real money from your Steam Wallet will be spent
- Games MUST be available on Steam
- One game is purchased per invocation
- Always shows the source of the recommendation
- Slight preference for recent games, but classics within max_game_age_years are welcome
- If you want to review before buying, use `/find-game` instead
