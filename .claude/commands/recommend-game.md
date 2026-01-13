---
description: Search for PC games matching your preferences (no purchase)
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Game Recommendation

Search the internet for highly-rated PC games and validate them against your preferences. This skill is read-only and will NOT purchase any games.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Default Genres (Steam Tags)
```
Action, Action-Adventure, Action RPG, Platformer, 2D Platformer, Indie,
Metroidvania, Adventure, RTS, Strategy, Fighting, Military, FPS, Souls-like
```

## Usage Examples
```
/recommend-game                              # Random genre from defaults
/recommend-game Metroidvania                 # Single genre
/recommend-game "Souls-like, Action RPG"     # Multiple genres
```

## Workflow

### Step 1: Read Current Preferences
First, read config.yaml to understand the user's current preferences:

```bash
cat config.yaml
```

Display a summary of the current criteria to the user so they know what filters will be applied.

### Step 2: Parse Genre(s)
- If `$ARGUMENTS` is empty: randomly select 1-2 genres from the default list above
- If `$ARGUMENTS` contains commas: split into multiple genres and search each
- Otherwise: use `$ARGUMENTS` as a single genre

Tell the user which genre(s) you're searching for.

### Step 3: Search for Games
Use the WebSearch tool to find highly-rated games. There is a slight preference for recent games, but classic/older games are welcome as long as they meet the max_game_age_years setting in config.yaml.

Try these queries:

1. **Primary (recent focus)**: `best [genre] PC games 2024 2025 Steam highly rated`
2. **Site-specific**: `site:pcgamer.com OR site:rockpapershotgun.com OR site:ign.com best [genre] games`
3. **Classic games**: `best [genre] PC games all time Steam classics` (for variety)
4. **Fallback**: `top [genre] Steam games Metacritic high score`

Extract 5-10 game titles from the search results. Track which source each game came from.

### Step 4: Find Steam App IDs
For each game title, resolve its Steam App ID:

1. Use WebFetch on: `https://store.steampowered.com/search/?term=[URL-encoded game name]&category1=998`
2. Look for URLs matching pattern: `/app/(\d+)/`
3. Extract the App ID from the first matching result
4. If WebFetch fails, try WebSearch: `[game name] Steam store app id`

**Verify the result** using the CLI:
```bash
uv run gmfind id "<game title>"
```
This returns JSON with `steam_id` and `title` to confirm you have the correct App ID.

Skip games that can't be found on Steam. Games MUST be available on Steam.

### Step 5: Validate Each Game
For each App ID found, run this command using Bash:

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

Parse the JSON output. A game passes if `"recommended": true`.

### Step 6: Present Results
Display all validated games with clear source attribution:

```
## Recommendations for [Genre]

**Current config.yaml preferences applied:**
[Show the relevant settings from config.yaml]

### 1. [Game Name]
**Source**: Found via [PC Gamer/Rock Paper Shotgun/IGN/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]

| Attribute | Value | Your Requirement | Status |
|-----------|-------|------------------|--------|
| Price | $XX.XX | From config.yaml | Pass/Fail |
| Metacritic | XX | From config.yaml | Pass/Fail |
| ProtonDB | [tier] | From config.yaml | Pass/Fail |
| Steam Deck | [status] | From config.yaml | Pass/Fail |
| Age | X years | From config.yaml | Pass/Fail |

---
```

If no games pass validation, show the rejection reasons from the JSON output and suggest the user adjust their config.yaml settings.

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
- This skill does NOT purchase games
- Games MUST be available on Steam
- Always show which website each recommendation came from
- Always include the Steam store link
- Slight preference for recent games, but classics within max_game_age_years are welcome
- If all games fail validation, suggest adjusting config.yaml settings
