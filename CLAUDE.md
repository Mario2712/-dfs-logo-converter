# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sprache

Alles auf Deutsch: Kommentare, Docstrings, GUI-Texte, Fehlermeldungen, CLI-Optionen (`--hintergrund`, `--keine-lueckensperre` …), README und Commit-Messages.

## Setup & Tests

- Abhängigkeiten sind lokal evtl. nicht installiert (kein `.venv`). Vor dem Testen: `pip install -e ".[dev,svg]"`.
- `pytest` erzeugt die Testlogos selbst (`tests/make_samples.py`, synthetisch). Für manuelle Tests: `python tests/make_samples.py samples` (`samples/` ist gitignored).
- Linter: `ruff check .` (Konfiguration in `pyproject.toml`). Ein Hook führt ihn nach jeder Bearbeitung einer `.py`-Datei automatisch aus. Kein Formatter.

## Workflow

Änderungen über Feature-Branch + GitHub-PR auf `main`, nicht direkt auf `main` committen.

## Darf nicht kaputtgehen

- **Ausgabe:** immer GIF, exakt 144×144, binäre Transparenz, ≤256 Farben (ein Palettenindex für Transparenz reserviert), Seitenverhältnis erhalten. `verify_gif()` in `pipeline.py` prüft das nach dem Export – nicht abschwächen.
- **PyInstaller-Build:** `build_windows.bat` und `build_mac_linux.sh` müssen synchron bleiben. Neue Abhängigkeiten brauchen dort ggf. `--collect-all` / `--hidden-import`. Einstiegspunkt ist `run_gui.py`.
- **SVG-Verarbeitung** muss funktionieren (`cairosvg`, optionales Extra `svg`).
- Optionale Pakete haben Fallbacks: ohne `imagequant` → Median-Cut aus Pillow; ohne `cairosvg` → verständliche Fehlermeldung.

## Bekannte Probleme

- `load_image()` erkennt SVG nur an der Endung `.svg`. Eine in `.png` umbenannte SVG-Datei wird nicht erkannt – Format sollte am Inhalt erkannt werden.
- Die Build-Skripte installieren nur `.[dev]` und sammeln `cairosvg` nicht ein → die gebaute App kann vermutlich keine SVGs lesen.
