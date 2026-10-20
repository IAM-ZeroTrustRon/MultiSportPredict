#!/usr/bin/env bash
# Git Bash: refresh all supported sports through the shared workflow.
set -euo pipefail
cd "$(dirname "$0")"
[[ -x venv/Scripts/python.exe ]] || { echo "Missing venv/Scripts/python.exe" >&2; exit 1; }
exec venv/Scripts/python.exe -u msp.py refresh --all "$@"
