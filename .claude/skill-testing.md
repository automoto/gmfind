# Skill Testing Plan

Guide for testing the Claude Code skills after efficiency updates.

## Quick Test (Recommended)

Run the read-only skill first to verify the workflow without spending money:

```bash
# In Claude Code, run:
/recommend-game FPS
```

This exercises the full flow:
1. Config + inventory loading
2. Web search
3. `gmfind id` lookups
4. `gmfind check` validation
5. Results presentation

## What to Verify

| Check | Expected Behavior |
|-------|-------------------|
| Commands use `gmfind` | No `uv run` in the bash calls |
| Inventory count shown | "X owned games will be excluded" message |
| No WebFetch calls | Only WebSearch + Bash tools used |
| Fewer searches | 2-3 web queries instead of 4 |
| Owned games filtered | Games in your inventory don't appear |

## Test Each Skill

```bash
# 1. Recommendations only (safe, no purchase)
/recommend-game Metroidvania

# 2. Find with confirmation (will ask before buying)
/find-game "Action RPG"
# → Answer "no" when asked to purchase

# 3. Auto-buy (only if you want to actually purchase)
# /auto-buy-game Indie
```

## Dry Run for Auto-Buy

Test auto-buy without risking a purchase by temporarily setting impossible criteria:

```bash
# Backup current config
cp ~/Library/Application\ Support/gmfind/config.yaml ~/Library/Application\ Support/gmfind/config.yaml.bak

# Temporarily make config impossible to match
cat > ~/Library/Application\ Support/gmfind/config.yaml << 'EOF'
preferences:
  max_price: 0.01
  min_metacritic_score: 99
  min_protondb_rating: "platinum"
  max_game_age_years: 1
  min_steam_deck_level: "verified"
  require_metacritic_score: true
EOF

# Run auto-buy - should find no matches
/auto-buy-game FPS

# Restore your real config after
cp ~/Library/Application\ Support/gmfind/config.yaml.bak ~/Library/Application\ Support/gmfind/config.yaml
```

## CLI Verification

Verify the CLI works without `uv run`:

```bash
gmfind --version
gmfind id "Hades"
gmfind check 1145360
```

## Expected Efficiency Gains

| Metric | Before | After |
|--------|--------|-------|
| Web searches per genre | 4 | 2-3 |
| ID lookup steps | WebFetch + regex + gmfind id | gmfind id only |
| Token usage per run | ~10,000+ | ~4,000-6,000 |
| Tools required | Bash, Read, WebSearch, WebFetch | Bash, Read, WebSearch |
