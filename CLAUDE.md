# Claude Code Guidelines

Project-specific instructions for Claude when working on the gmfind codebase.

## Build and Quality Commands

Always use Makefile commands for building, linting, and testing:

```bash
make check      # Run all checks (lint + type-check) - REQUIRED before committing
make lint       # Run ruff linter only
make format     # Format code with ruff
make type-check # Run mypy type checker
make install    # Install package with dev dependencies
make init       # Initialize Playwright browsers
```

Never run linting or type-checking commands directly (e.g., `ruff check`, `mypy`). Always use the Makefile.

## Browser Automation / Playwright

### Page Selectors

**Never guess page selectors or assume common patterns.** Always verify selectors by:

1. Using selectors already proven to work in the existing codebase
2. Actually inspecting the real webpage to confirm selectors exist

Incorrect selectors will silently fail or break automation flows. When adding new selectors:
- Check existing files like `steam_auth.py`, `buy_game.py` for working patterns
- Use multiple fallback selectors (ID, class, text) since Steam UI changes frequently
- Test against the real Steam website when possible

### Existing Selector Patterns

The codebase uses these proven selector strategies:
- Primary: CSS selectors (`#id`, `.class`, `[attribute]`)
- Fallback: Text matching (`get_by_text()`, `get_by_role()`)
- Multiple attempts with try/except for robustness

## Code Style

- Synchronous Python with `requests` and `playwright.sync_api`
- Use `paths.py` for all file locations (XDG-compliant)
- Wrap external API calls in try/except
- All code must pass `make check` before committing
- Try not too use alot of regular expressions as these are hard to troubleshoot unless they are really needed.
- Dont add alot of verbose comments, only add comments where its needed and helpful.
