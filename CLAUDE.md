# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sprache

Alles auf Deutsch: Kommentare, Docstrings, GUI-Texte, Fehlermeldungen, CLI-Optionen (`--hintergrund`, `--keine-lueckensperre` …), README und Commit-Messages.

## Setup & Tests

- Abhängigkeiten liegen im `.venv` (gitignored, wird auch von den Build-Skripten genutzt). Tests mit `.venv/Scripts/python -m pytest`; fehlt das `.venv`: `python -m venv .venv` und `pip install -e ".[dev]"`.
- `pytest` erzeugt die Testlogos selbst (`tests/make_samples.py`, synthetisch). Für manuelle Tests: `python tests/make_samples.py samples` (`samples/` ist gitignored).
- Linter: `ruff check .` (Konfiguration in `pyproject.toml`). Ein Hook führt ihn nach jeder Bearbeitung einer `.py`-Datei automatisch aus. Kein Formatter.

## Workflow

Änderungen über Feature-Branch + GitHub-PR auf `main`, nicht direkt auf `main` committen.

## Darf nicht kaputtgehen

- **Ausgabe:** immer GIF, exakt 144×144, binäre Transparenz, ≤256 Farben (ein Palettenindex für Transparenz reserviert), Seitenverhältnis erhalten. `verify_gif()` in `pipeline.py` prüft das nach dem Export – nicht abschwächen.
- **PyInstaller-Build:** `build_windows.bat` und `build_mac_linux.sh` müssen synchron bleiben. Neue Abhängigkeiten brauchen dort ggf. `--collect-all` / `--hidden-import`. Einstiegspunkt ist `run_gui.py`.
- **SVG-Verarbeitung** muss funktionieren, auch unter Windows und in der gebauten App. Renderer ist `resvg-py` (keine Systembibliothek). `cairosvg` ist nur Fallback – unter Windows fehlt meist `libcairo-2.dll`, nicht darauf verlassen.
- **Format am Inhalt erkennen, nicht an der Endung** (`is_svg_file()`): umbenannte Dateien müssen funktionieren.
- Optionale Pakete haben Fallbacks: ohne `imagequant` → Median-Cut aus Pillow; ohne SVG-Renderer → verständliche Fehlermeldung.
