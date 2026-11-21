#!/usr/bin/env bash
# Baut eine eigenständige App (macOS: .app, Linux: Binary) mit PyInstaller.
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

pyinstaller --noconfirm --onefile --windowed \
    --name "DFS-Logo-Converter" \
    --collect-all tkinterdnd2 \
    --collect-all imagequant \
    --collect-all resvg_py \
    --hidden-import PIL._tkinter_finder \
    run_gui.py

echo "Fertig: dist/DFS-Logo-Converter"
