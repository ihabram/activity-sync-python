#!/usr/bin/env bash
set -e

# Move to the project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "[Deploy] Pulling latest changes from git..."
git fetch origin main
git reset --hard origin/main

if [ -d "venv" ]; then
    echo "[Deploy] Updating virtualenv dependencies..."
    source venv/bin/activate
    pip install --no-cache-dir -r requirements.txt
fi

echo "[Deploy] Restarting systemd service..."
sudo systemctl restart activity-sync

echo "[Deploy] Deployment complete!"
