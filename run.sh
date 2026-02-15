#!/usr/bin/env bash
# Daily job search automation wrapper.
# Add to cron: 0 6 * * * /path/to/job-search-tool/run.sh
#
# Cron setup (daily at 6 AM MST):
#   crontab -e
#   0 13 * * * /mnt/c/Users/mhast/Desktop/Job\ Search\ 2025/job-search-tool/run.sh
#   (13:00 UTC = 6:00 AM MST)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "ERROR: .env file not found. Copy .env.example to .env and add your API keys."
    exit 1
fi

# Ensure log directory exists
mkdir -p data/logs

LOG_FILE="data/logs/$(date +%Y-%m-%d).log"

echo "=== Job Search Run: $(date) ===" | tee -a "$LOG_FILE"

# Activate virtual environment
source .venv/bin/activate

python3 -m src.cli run 2>&1 | tee -a "$LOG_FILE"

echo "=== Run complete: $(date) ===" | tee -a "$LOG_FILE"
