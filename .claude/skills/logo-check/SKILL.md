---
name: logo-check
description: Gesamtprüfung des DFS Logo Converters – Tests plus echter CLI-Durchlauf über alle Beispiel-Logos (inkl. SVG und umbenannter SVG) mit Prüfung der GIF-Anforderungen. Nach Änderungen an pipeline.py, background.py, quantize.py oder cli.py verwenden, oder wenn der Nutzer "prüfen", "verify" oder /logo-check sagt.
---

Führe die Schritte der Reihe nach aus und berichte am Ende kurz pro Schritt: OK / FEHLER (mit Ausgabe).

1. **Abhängigkeiten:** `python -c "import numpy, scipy, PIL, cairosvg, pytest"`. Schlägt das fehl: `pip install -e ".[dev,svg]"`. Fehlt danach nur die Cairo-Systembibliothek, das melden und die SVG-Schritte als übersprungen kennzeichnen (nicht als bestanden).

2. **Tests:** `pytest -q`.

3. **Beispiel-Logos erzeugen** im Scratchpad (nicht im Repo):
   `python tests/make_samples.py <scratch>/samples`
   Zusätzlich die SVG kopieren und umbenennen: `<scratch>/samples/logo.svg` → `<scratch>/samples/logo_svg_als.png`.

4. **CLI-Durchlauf:** `dfslogo <scratch>/samples -o <scratch>/out -f` (falls `dfslogo` nicht im PATH: `python -m dfslogo.cli`). Dateien, die nicht umgewandelt wurden, einzeln melden – insbesondere die umbenannte SVG (bekanntes Problem, siehe CLAUDE.md).

5. **Ausgaben prüfen** mit einem kurzen Python-Skript (im Scratchpad) für jede `.gif` in `<scratch>/out`:
   - `format == "GIF"`, `size == (144, 144)`, `"transparency" in info`
   - alle vier Eckpixel transparent
   - `len(im.getcolors(256)) <= 256`
   - Alpha nur 0 oder 255 (binäre Transparenz)

6. Wenn `$ARGUMENTS` einen Pfad zu einem echten Logo enthält: diesen ebenfalls umwandeln und wie in Schritt 5 prüfen.

Nichts im Repo ändern; nur berichten.
