#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This launcher is for macOS."
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Run Setup.command first (or: bash Setup.command)."
  read -r -p "Press Return to close..."
  exit 1
fi
.venv/bin/python app.py
result=$?
if [ "$result" -ne 0 ]; then
  read -r -p "An error occurred. Press Return to close..."
fi
exit "$result"
