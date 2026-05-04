#!/usr/bin/env bash
# F5 EoS / EoL Finder — Mac & Linux launcher.
# Creates a virtualenv on first run, installs deps, starts the web app,
# and opens it in your browser.

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Error: python3 is not installed."
  echo "Install Python 3.10+ from https://www.python.org/downloads/ and re-run."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Setting up virtualenv (one-time, ~10 seconds)..."
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

URL="http://127.0.0.1:5000"
echo
echo "Starting F5 EoS / EoL Finder at $URL"
echo "Press Ctrl+C to stop."
echo

# open the browser shortly after the server starts
( sleep 1.5 && (open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true) ) &

exec python app.py
