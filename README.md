# DFS Logo Converter

Wandelt beliebige Vereinslogos in **144×144-GIFs mit transparentem Hintergrund** um, die
direkt in **Das Fußball Studio (DFS)** eingebunden werden können.

- Hintergrund wird transparent (bereits transparente PNGs/SVGs bleiben, wie sie sind)
- Ausgabe immer als **GIF, 144×144 Pixel**
- **Keine Verzerrung**: Das Seitenverhältnis bleibt erhalten, das Logo wird zentriert
- **Hohe Qualität**: Lanczos-Skalierung, entmischte Kanten ohne Halo, optimale 255-Farben-Palette

## Installation

Voraussetzung: Python 3.10 oder neuer (unter Windows von python.org, Tk ist dort enthalten).

```bash
pip install -e .            # Installation inkl. SVG-Unterstützung (resvg-py)
```

### Als eigenständige App (ohne Python auf dem Laptop)

- **Windows:** `build_windows.bat` doppelklicken → `dist\DFS-Logo-Converter.exe`
- **macOS/Linux:** `./build_mac_linux.sh` → `dist/DFS-Logo-Converter`

Die App ist eine einzelne Datei mit etwa 70 MB. Sie muss auf dem jeweiligen Betriebssystem
gebaut werden, also die Windows-EXE auf einem Windows-PC.

## Verwendung

### Oberfläche

```bash
dfslogo-gui          # oder: python -m dfslogo
```

Logo öffnen oder ins Fenster ziehen. Die Vorschau zeigt das Ergebnis 3× vergrößert
(das Karomuster steht für Transparenz) und in Originalgröße auf Weiß, Beige und Grau.
Danach **Als GIF speichern** wählen. Mit **Ordner umwandeln** werden alle Bilder eines
Ordners auf einmal umgewandelt; die Ergebnisse landen im Unterordner `dfs/`.

### Kommandozeile

```bash
dfslogo logo.png                       # -> logo_dfs.gif neben der Quelle
dfslogo logo.jpg -o rapid.gif          # eigener Dateiname
dfslogo logos/ -o fertig/              # ganzer Ordner
dfslogo logo.jpg --matte weiss --innen # Optionen, siehe dfslogo --help
```

| Option | Bedeutung |
|---|---|
| `--matte hell\|weiss\|beige\|grau\|#RRGGBB` | Farbe, auf die die Kanten abgestimmt werden (siehe unten). Standard: `hell` |
| `--hintergrund auto\|immer\|nie` | Hintergrund entfernen. `auto` entfernt ihn nur, wenn der Bildrand einheitlich ist |
| `--toleranz 40` | Wie stark eine Farbe vom Hintergrund abweichen darf, um noch als Hintergrund zu gelten (bei JPG-Artefakten erhöhen) |
| `--innen` | Auch eingeschlossene Flächen in Hintergrundfarbe entfernen (z. B. Lücken zwischen Buchstaben). **Achtung:** Entfernt dann auch weiße Logo-Teile |
| `--keine-lueckensperre` | Engstellen-Sperre abschalten (siehe unten). Normalerweise nicht nötig |
| `--rand 2` | Freier Rand in Pixeln |
| `--schwelle 0.5` | Ab welcher Deckkraft ein Kantenpixel sichtbar bleibt |
| `--dither` | Dithering, nur für Logos mit Verläufen oder Fotos sinnvoll |
| `--nicht-schaerfen` | Nachschärfen nach dem Verkleinern abschalten |
| `-f` | Vorhandene Dateien überschreiben |

## Wie die Verarbeitung funktioniert

GIF kennt **nur binäre Transparenz** (ein Pixel ist entweder ganz sichtbar oder ganz
unsichtbar) und **höchstens 256 Farben**. Die Pipeline ist darauf ausgelegt:

1. **Einlesen:** PNG, JPG, WEBP, GIF, BMP, TIFF, SVG. Das Format wird am Inhalt erkannt,
   eine umbenannte SVG funktioniert also auch. SVGs rendert `resvg-py` ohne zusätzliche
   Systembibliothek. Große Bilder werden auf 1200 px Arbeitsgröße gebracht.
2. **Hintergrund entfernen:** Die Hintergrundfarbe wird aus den Randpixeln geschätzt und
   von außen per Flood-Fill entfernt, sodass Weiß *im* Wappen erhalten bleibt. Im
   Kantenbereich wird die Deckkraft jedes Pixels geschätzt und die Farbe „entmischt“.
   Dadurch entsteht kein heller Saum. Eine **Engstellen-Sperre** verhindert, dass der Fill
   durch schmale Lücken in einer Umrandung ins Logo-Innere „durchsickert“, z. B. zwischen
   Ball und Rahmen. Solche Lücken bis etwa 0,8 % der Bildgröße werden überbrückt.
3. **Zuschneiden** auf den sichtbaren Inhalt.
4. **Seitenverhältnis-treu skalieren** auf 140 px (bei 2 px Rand) an der längeren Seite und
   mittig auf 144×144 setzen.
5. **Lanczos-Skalierung** mit vormultipliertem Alpha, danach leichtes Nachschärfen.
6. **Kanten für GIF:** Halbtransparente Kantenpixel werden mit der **Matte-Farbe** gemischt,
   danach wird über eine Deckkraft-Schwelle entschieden, ob sie sichtbar bleiben.
7. **Farbreduktion:** Hat das Logo höchstens 255 Farben, bleibt es verlustfrei. Sonst
   berechnet libimagequant eine optimale Palette. Ein Index ist für Transparenz reserviert.
8. **Export und Prüfung:** Die gespeicherte Datei wird wieder eingelesen und Pixel für Pixel
   kontrolliert (Größe, Transparenz, Farben).

### Welche Matte-Farbe?

In DFS stehen die Logos meist auf Weiß oder leichtem Beige/Grau. Der Standard **`hell`**
(#F6F4EF) liegt zwischen diesen Tönen und sorgt auf allen dreien für glatte Kanten ohne
sichtbaren Saum. Wenn ein Logo nur auf einem bestimmten Hintergrund erscheint, die passende
Farbe wählen. Auf dunklen Hintergründen sieht man dann einen feinen hellen Rand; das ist bei
GIF unvermeidbar.

### Tipps für beste Qualität

- Möglichst **große** Quellbilder (ab 300 px) oder **SVG** verwenden. Kleine Bilder werden
  hochskaliert und wirken weich; das Tool weist darauf hin.
- PNGs mit Transparenz sind ideal, weil dann keine Hintergrund-Erkennung nötig ist.
- Bleibt bei einem JPG ein Rest des Hintergrunds stehen, die **Toleranz** erhöhen.
  Verschwinden Teile des Logos, die Toleranz senken.

## Entwicklung

```bash
pip install -e ".[dev]"
pytest
```

Aufbau:

```
dfslogo/
  pipeline.py    Kern: convert_image() – alle Schritte, Optionen, Prüfung
  background.py  Hintergrund-Erkennung, Flood-Fill, Kanten-Entmischung
  quantize.py    Palette (exakt / libimagequant / Median-Cut) und GIF-Export
  cli.py         Kommandozeile
  gui.py         Tkinter-Oberfläche
tests/           Tests mit synthetischen Logos
```

## Lizenzhinweis

`imagequant` (libimagequant) steht unter der GPL-3.0. Für die private Nutzung ist das
unproblematisch. Ohne das Paket nutzt das Tool automatisch den Median-Cut aus Pillow.
