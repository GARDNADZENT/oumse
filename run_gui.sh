#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PY="${OUMSE_GUI_PYTHON:-python3}"

if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  echo "Error: $PY does not include Tkinter." >&2
  echo "Install python3-tk, or set OUMSE_GUI_PYTHON to a Python with Tkinter." >&2
  exit 1
fi

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
echo "Starting Oumse GSM Tool Pro - Community Edition (no login)..."
exec "$PY" -m app
