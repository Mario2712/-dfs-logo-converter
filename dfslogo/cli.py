"""Kommandozeile.

Beispiele:
  dfslogo logo.png                     -> logo_dfs.gif (neben der Quelle)
  dfslogo logo.jpg -o rapid.gif        -> rapid.gif
  dfslogo ordner/ -o ausgabe/          -> alle Bilder im Ordner umwandeln
  dfslogo logo.jpg --matte weiss --innen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .pipeline import (
    MATTE_PRESETS,
    SUPPORTED_EXTENSIONS,
    Options,
    convert_file,
    default_output_path,
    parse_color,
)


def collect_inputs(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.iterdir()
                            if f.suffix.lower() in SUPPORTED_EXTENSIONS
                            and not f.stem.endswith("_dfs"))
        elif p.exists():
            files.append(p)
        else:
            print(f"Nicht gefunden: {p}", file=sys.stderr)
    return files


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="dfslogo",
        description="Wandelt Vereinslogos in 144×144-GIFs mit transparentem Hintergrund "
                    "für Das Fußball Studio (DFS) um.",
    )
    ap.add_argument("inputs", nargs="+", help="Bilddatei(en) oder Ordner")
    ap.add_argument("-o", "--output",
                    help="Ziel: .gif-Datei (bei einer Quelle) oder Ordner")
    ap.add_argument("--matte", default="hell",
                    help=f"Kantenfarbe = DFS-Hintergrund: {', '.join(MATTE_PRESETS)} "
                         "oder #RRGGBB (Standard: hell)")
    ap.add_argument("--rand", type=int, default=2, metavar="PX",
                    help="Freier Rand um das Logo in Pixel (Standard: 2)")
    ap.add_argument("--groesse", type=int, default=144, metavar="PX",
                    help="Zielgröße (Standard: 144)")
    ap.add_argument("--hintergrund", choices=["auto", "immer", "nie"], default="auto",
                    help="Hintergrund entfernen (Standard: auto)")
    ap.add_argument("--toleranz", type=float, default=40.0,
                    help="Farbtoleranz für den Hintergrund, 5–120 (Standard: 40)")
    ap.add_argument("--innen", action="store_true",
                    help="Auch eingeschlossene Flächen in Hintergrundfarbe entfernen")
    ap.add_argument("--keine-lueckensperre", action="store_true",
                    help="Engstellen-Sperre abschalten (Flood-Fill auch durch schmale Lücken)")
    ap.add_argument("--schwelle", type=float, default=0.5,
                    help="Alpha-Schwelle für sichtbare Kantenpixel, 0.1–0.9 (Standard: 0.5)")
    ap.add_argument("--dither", action="store_true",
                    help="Dithering bei der Farbreduktion (für Verläufe/Fotos)")
    ap.add_argument("--nicht-schaerfen", action="store_true",
                    help="Kein Nachschärfen nach dem Verkleinern")
    ap.add_argument("-f", "--ueberschreiben", action="store_true",
                    help="Vorhandene Zieldateien überschreiben")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        opts = Options(
            size=args.groesse,
            margin=args.rand,
            matte=parse_color(args.matte),
            alpha_threshold=min(max(args.schwelle, 0.05), 0.95),
            background={"auto": "auto", "immer": "always", "nie": "never"}[args.hintergrund],
            tolerance=args.toleranz,
            remove_enclosed=args.innen,
            close_gaps=not args.keine_lueckensperre,
            sharpen=not args.nicht_schaerfen,
            dither=args.dither,
        )
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    files = collect_inputs(args.inputs)
    if not files:
        print("Keine Eingabebilder gefunden.", file=sys.stderr)
        return 2

    out = Path(args.output) if args.output else None
    single_target = out is not None and out.suffix.lower() == ".gif"
    if single_target and len(files) > 1:
        print("Bei mehreren Quellen muss -o ein Ordner sein.", file=sys.stderr)
        return 2
    if out is not None and not single_target:
        out.mkdir(parents=True, exist_ok=True)

    errors = 0
    for src in files:
        dst = out if single_target else default_output_path(src, out)
        if dst.exists() and not args.ueberschreiben:
            print(f"übersprungen (existiert, -f zum Überschreiben): {dst}")
            continue
        try:
            r = convert_file(src, dst, opts)
        except Exception as exc:
            errors += 1
            print(f"FEHLER {src.name}: {exc}", file=sys.stderr)
            continue
        print(f"OK  {src.name} -> {dst}  [{r.info['background']}, "
              f"{r.info['colors']} Farben, {r.info['quantizer']}]")
        for w in r.warnings:
            print(f"    Hinweis: {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
