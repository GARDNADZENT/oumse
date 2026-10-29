#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PY="${BEST_MDM_TOOL_PYTHON:-python3}"

if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  echo "Error: $PY does not include Tkinter." >&2
  echo "Install python3-tk, or set BEST_MDM_TOOL_PYTHON to a Python with Tkinter." >&2
  exit 1
fi

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
echo "Starting BestMDMTool - Authorized Device Service (no login)..."
exec "$PY" -m bestmdmtool
