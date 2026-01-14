---
description: Search for PC games matching your preferences (no purchase)
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Game Recommendation

Search the internet for highly-rated PC games and validate them against your preferences. This skill is read-only and will NOT purchase any games.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Configuration
Default genres and search year ranges are defined in `.claude/skill-config.yaml`. Read this file at the start of the workflow.

## Usage Examples
```
/recommend-game                              # Random genre from defaults
/recommend-game Metroidvania                 # Single genre
/recommend-game "Souls-like, Action RPG"     # Multiple genres
```

## Workflow

### Step 1: Load Configuration
Read skill config, user preferences, and check inventory in parallel:

```bash
cat .claude/skill-config.yaml
```

```bash
cat ~/.config/gmfind/config.yaml
```

```bash
wc -l ~/.local/share/gmfind/inventory_private.csv 2>/dev/null | awk '{print $1 - 1}' || echo "0"
```

Display: "Loaded preferences. X owned games will be excluded from recommendations."

### Step 2: Parse Genre(s)
- If `$ARGUMENTS` is empty: than just search for games without a genre
- If `$ARGUMENTS` contains commas: split into multiple genres and search each
- Otherwise: use `$ARGUMENTS` as a single genre

Tell the user which genre(s) you're searching for.

### Step 3: Search for Games
Use WebSearch to find highly-rated games. Calculate years from skill-config.yaml (e.g., if `recent: 2` and current year is 2026, use "2025 2026"). Run 2-4 queries in parallel:

1. **Recent + highly rated**: `best [genre] PC games [recent years] Steam highly rated`
2. **Gaming sites**: `site:pcgamer.com OR site:rockpapershotgun.com best [genre] games since [current_year - extended]`
3. **Budget-friendly** (if max_price < $20): `best [genre] PC games Steam under $[max_price]`
4. **Steam 250 deals**: `site:steam250.com [genre] discounts OR deals`

Also use WebFetch to check Steam 250 discounts directly:
```
WebFetch: https://steam250.com/discounts
Prompt: "List game titles that match [genre] genre, showing name and discount percentage"
```

Extract 5-10 game titles from the search results. Track which source each game came from.

### Step 4: Resolve Steam IDs
For each game title, get its Steam App ID using the CLI:

```bash
gmfind id "<game title>"
```

This returns JSON: `{"steam_id": 123456, "title": "Game Name"}`

Run multiple `gmfind id` calls in parallel when possible. Skip games that return an error or aren't found on Steam.

### Step 5: Validate Each Game
For each App ID found, validate against your preferences:

```bash
gmfind check <APP_ID>
```

The CLI validates against ALL criteria in config.yaml:
- Price, Metacritic score, ProtonDB rating, Steam Deck compatibility
- Game age, blocklist, and ownership (auto-excludes games you own)

A game passes if `"recommended": true` in the JSON output.

### Step 6: Present Results
Display all validated games with source attribution:

```
## Recommendations for [Genre]

**Preferences applied:** max_price=$X, min_metacritic=X, protondb=X, steam_deck=X
**Inventory:** X owned games excluded

### 1. [Game Name]
**Source**: Found via [PC Gamer/Rock Paper Shotgun/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]

| Attribute | Value | Requirement | Status |
|-----------|-------|-------------|--------|
| Price | $XX.XX | ≤$XX | Pass/Fail |
| Metacritic | XX | ≥XX | Pass/Fail |
| ProtonDB | [tier] | ≥[tier] | Pass/Fail |
| Steam Deck | [status] | ≥[level] | Pass/Fail |
| Age | X years | ≤X years | Pass/Fail |

---
```

If no games pass validation, show rejection reasons and suggest adjusting config.yaml.

## Important Notes
- This skill does NOT purchase games
- Games MUST be available on Steam
- Always show which website each recommendation came from
- Always include the Steam store link
- If all games fail validation, suggest adjusting config.yaml settings
