#!/bin/bash

# 1. Get the absolute path to the directory where this script is located
# This works even if you call the script from another folder
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 2. Define the path to your venv and app relative to the script location
VENV_PATH="$SCRIPT_DIR/venv"
APP_PATH="$SCRIPT_DIR/app.py"

# 3. Use the Python interpreter directly from the venv folder
# This bypasses the need for 'source activate' and works with sudo
VENV_PYTHON="$VENV_PATH/bin/python"

# 4. Check if the venv exists before running
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# 5. Run the app with sudo using the venv's Python
"$VENV_PYTHON" "$APP_PATH"
