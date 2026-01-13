.PHONY: install init lint format type-check check clean help
.PHONY: balance inventory deals auto-buy schedule unschedule
.PHONY: build publish-test publish

# Default target
help:
	@echo "gmfind - Steam Game Finder CLI"
	@echo ""
	@echo "Setup:"
	@echo "  make install      Install package and dependencies"
	@echo "  make init         Initialize Playwright browsers"
	@echo ""
	@echo "Development:"
	@echo "  make lint         Run ruff linter"
	@echo "  make format       Format code with ruff"
	@echo "  make type-check   Run mypy type checker"
	@echo "  make check        Run all checks (lint + type-check)"
	@echo "  make clean        Remove cache files"
	@echo ""
	@echo "Publishing:"
	@echo "  make build        Build package (dist/)"
	@echo "  make publish-test Upload to TestPyPI"
	@echo "  make publish      Upload to PyPI"
	@echo ""
	@echo "Commands:"
	@echo "  make balance      Check Steam Wallet balance"
	@echo "  make inventory    Export game library (private/authenticated)"
	@echo "  make deals        Find 10 game deals"
	@echo "  make auto-buy     Run autonomous buy workflow"
	@echo ""
	@echo "Scheduling (macOS):"
	@echo "  make schedule     Schedule weekly auto-buy (Sundays 10am)"
	@echo "  make unschedule   Remove scheduled job"
	@echo "  make schedule-status  Check schedule status"

# ============ Setup ============

install:
	uv pip install -e ".[dev]"

init: install
	uv run gmfind init

# ============ Development ============

lint:
	uv run ruff check src/

format:
	uv run ruff format src/
	uv run ruff check --fix src/

type-check:
	uv run mypy src/gmfind

check: lint type-check

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf dist/*
	rm -rf .mypy_cache .ruff_cache .pytest_cache

# ============ Commands ============

balance:
	uv run gmfind balance

inventory:
	uv run gmfind inventory --private

deals:
	uv run gmfind deals 10

auto-buy: inventory
	uv run gmfind buy --auto

# ============ Scheduling (macOS) ============

schedule:
	@mkdir -p logs
	@cp scripts/com.steambot.weekly.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.steambot.weekly.plist
	@echo "Scheduled! Will run every Sunday at 10:00 AM"
	@echo "Logs: logs/weekly.log"

unschedule:
	-launchctl unload ~/Library/LaunchAgents/com.steambot.weekly.plist 2>/dev/null
	-rm ~/Library/LaunchAgents/com.steambot.weekly.plist 2>/dev/null
	@echo "Unscheduled weekly run"

schedule-status:
	@echo "=== Launch Agent Status ==="
	@launchctl list | grep steambot || echo "Not scheduled"
	@echo ""
	@echo "=== Recent Log ==="
	@tail -20 logs/weekly.log 2>/dev/null || echo "No logs yet"

# ============ Publishing ============

build: clean
	uv pip install build
	uv run python -m build
	@echo "Built: dist/"
	@ls -la dist/

publish-test: build
	uv pip install twine
	uv run twine upload --repository testpypi --verbose dist/*

publish: build
	uv pip install twine
	uv run twine upload --repository pypi --verbose dist/*
