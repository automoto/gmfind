---
description: Get PC games and purchase with confirmation
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# Steam Game Finder (with Purchase Option)

Search the internet for highly-rated PC games, validate them, and purchase with user confirmation.

## Arguments
- `$ARGUMENTS` - Optional genre(s) to search for. If not provided, randomly selects from defaults.

## Configuration
Default genres and search year ranges are defined in `.claude/skill-config.yaml`. Read this file at the start of the workflow.

## Usage Examples
```
/get-game                              # Random genre from defaults
/get-game Metroidvania                 # Single genre
/get-game "Souls-like, Action RPG"     # Multiple genres
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
cat ~/.config/gmfind/config.yaml
```

```bash
wc -l ~/.local/share/gmfind/inventory_private.csv 2>/dev/null | awk '{print $1 - 1}' || echo "0"
```

Display summary:
- "Wallet balance: $X.XX"
- "Preferences: max_price=$X, min_metacritic=X, protondb=X, steam_deck=X"
- "X owned games will be excluded"

If balance is $0 or retrieval fails, warn that purchases may fail.

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

### Step 4: Validate Each Game
For each game title found, check it directly (the CLI resolves the Steam ID automatically):

```bash
gmfind check "<game title>"
```

Run multiple `gmfind check` calls in parallel when possible. Skip games that return an error.

The CLI validates against ALL criteria in config.yaml:
- Price, Metacritic score, ProtonDB rating, Steam Deck compatibility
- Game age, blocklist, and ownership (auto-excludes games you own)

A game passes if `"recommended": true` in the JSON output.

### Step 5: Present Top Recommendation
Present the FIRST validated game with full details:

```
## Recommended: [Game Name]

**Source**: Found via [PC Gamer/Rock Paper Shotgun/etc.]
**Steam Link**: https://store.steampowered.com/app/[APP_ID]

| Attribute | Value | Requirement | Status |
|-----------|-------|-------------|--------|
| Price | $XX.XX | ≤$XX | Pass |
| Metacritic | XX | ≥XX | Pass |
| ProtonDB | [tier] | ≥[tier] | Pass |
| Steam Deck | [status] | ≥[level] | Pass |
| Age | X years | ≤X years | Pass |
```

### Step 6: Ask for Purchase Confirmation
**CRITICAL**: You MUST ask the user for explicit confirmation before purchasing.

Ask: "Would you like to purchase [GAME NAME] for [PRICE]? (yes/no)"

- Wait for the user's response
- Only proceed if they explicitly say "yes"
- If they say "no" or anything else, do NOT purchase

### Step 7: Execute Purchase (if confirmed)
If and only if the user confirmed with "yes", use `--auto` to skip CLI confirmation (since we already confirmed above):

```bash
gmfind buy <APP_ID> --auto
```

The CLI will display:
- `[SUCCESS] Purchased: [GAME NAME] (App ID [APP_ID])` on success
- Error details on failure

On failure, suggest running with `--headful` flag for debugging.

## Important Notes
- **ALWAYS ask for user confirmation before purchasing**
- This uses real money from your Steam Wallet
- Games MUST be available on Steam
- Always show the Steam store link so the user can review the game page
- Always show which website the recommendation came from
