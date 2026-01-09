.PHONY: install lint format type-check test clean run dry-run venv clean-all schedule unschedule schedule-status

VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

# Create virtual environment and install dependencies
venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install ruff mypy
	$(VENV)/bin/playwright install chromium
	@echo "Virtual environment created. Run 'make run' or 'make dry-run'"

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

# Run the bot (dry run)
dry-run: venv
	$(PYTHON) main.py --dry-run

# Run the bot for real
run: venv
	$(PYTHON) main.py

# Run headless
run-headless: venv
	$(PYTHON) main.py --headless

dry-run-headless: venv
	$(PYTHON) main.py --dry-run --headless

# Test checkout selectors interactively
test-checkout: venv
	$(PYTHON) test_checkout.py

# Schedule weekly run (macOS launchd)
schedule: venv
	@mkdir -p logs
	@cp scripts/com.steambot.weekly.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.steambot.weekly.plist
	@echo "Scheduled! Will run every Sunday at 10:00 AM"
	@echo "View status: make schedule-status"
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

# Test the scheduled script manually
test-schedule:
	./scripts/run-weekly.sh
