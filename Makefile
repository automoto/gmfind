.PHONY: install lint format type-check check clean clean-all login balance inventory auto-buy help

VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

# Default target
help:
	@echo "Steam Bot CLI Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install      Create venv and install dependencies"
	@echo "  make login        Run headless login flow"
	@echo "  make balance      Check Steam Wallet balance"
	@echo "  make inventory    Generate owned games list (private/authenticated)"
	@echo "  make auto-buy     Autonomous mode: Check balance -> Recommend -> Buy"
	@echo "  make lint         Run ruff linter"
	@echo "  make format       Format code with ruff"
	@echo "  make check        Run lint and type checks"
	@echo "  make clean        Remove cache files"
	@echo "  make clean-all    Remove cache files and venv"
	@echo "  make schedule     Schedule weekly run (macOS)"
	@echo "  make unschedule   Unschedule weekly run"

# Create virtual environment and install dependencies
venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install ruff mypy
	$(VENV)/bin/playwright install chromium
	@echo "Virtual environment created."

# Install dependencies (into existing venv)
install: venv
	$(PIP) install -r requirements.txt
	$(PIP) install ruff mypy
	$(VENV)/bin/playwright install chromium

# Lint code with ruff
lint: venv
	$(VENV)/bin/ruff check src/ main.py

# Format code with ruff
format: venv
	$(VENV)/bin/ruff format src/ main.py
	$(VENV)/bin/ruff check --fix src/ main.py

# Type checking with mypy
type-check: venv
	$(VENV)/bin/mypy src/ main.py --ignore-missing-imports

# Run all checks
check: lint type-check

# Clean up cache files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .mypy_cache .ruff_cache

# Clean everything including venv
clean-all: clean
	rm -rf $(VENV)

# Shortcuts for common actions
login: venv
	$(PYTHON) src/steam_auth.py

balance: venv
	$(PYTHON) main.py --balance

inventory: venv
	$(PYTHON) main.py --inventory-private

auto-buy: inventory
	$(PYTHON) main.py --auto-buy --config config.yaml --block-list block_list.yaml --inventory inventory_private.csv --headful

# Run manual purchase test with visible browser (Usage: make test-buy APPID=12345)
test-buy: venv
	$(PYTHON) main.py --buy $(APPID) --headful

# Schedule weekly run (macOS launchd)
schedule: venv
	@mkdir -p logs
	@cp scripts/com.steambot.weekly.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.steambot.weekly.plist
	@echo "Scheduled! Will run every Sunday at 10:00 AM"
	@echo "Logs: logs/weekly.log"

# Unschedule weekly run
unschedule:
	-launchctl unload ~/Library/LaunchAgents/com.steambot.weekly.plist 2>/dev/null
	-rm ~/Library/LaunchAgents/com.steambot.weekly.plist 2>/dev/null
	@echo "Unscheduled weekly run"

# Check schedule status
schedule-status:
	@echo "=== Launch Agent Status ==="
	@launchctl list | grep steambot || echo "Not scheduled"
	@echo ""
	@echo "=== Recent Log ==="
	@tail -20 logs/weekly.log 2>/dev/null || echo "No logs yet"

recommend: inventory
	PYTHONPATH=. venv/bin/python src/recommend_metacritic.py --config config.yaml --inventory inventory_private.csv | head -n1 | xargs venv/bin/python main.py --config config.yaml --block-list block_list.yaml --inventory inventory_private.csv --check-game
