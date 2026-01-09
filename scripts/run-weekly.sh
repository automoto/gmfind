#!/bin/bash
# Weekly Steam bot runner script
# This script is called by launchd

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Create logs directory if needed
mkdir -p logs

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Log start time
echo "=== Steam Bot Run: $(date) ===" >> logs/weekly.log

# Run the bot using the venv (headless since no display)
./venv/bin/python3 main.py --headless >> logs/weekly.log 2>&1
EXIT_CODE=$?

echo "=== Completed: $(date) (exit code: $EXIT_CODE) ===" >> logs/weekly.log

exit $EXIT_CODE
