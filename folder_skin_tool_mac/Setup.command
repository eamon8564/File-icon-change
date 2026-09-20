#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This launcher is for macOS."
  exit 1
fi
PYTHON_BIN="${FOLDER_SKIN_PYTHON:-python3}"
echo "Creating a local Python environment..."
"$PYTHON_BIN" -c 'import sys, tkinter; assert sys.version_info >= (3,10), "Python 3.10+ required"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x Start.command Setup.command
echo "Setup complete. Open Start.command to launch."
read -r -p "Press Return to close..."
