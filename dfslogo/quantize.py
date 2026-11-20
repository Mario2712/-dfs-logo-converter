"""Farbreduktion auf eine GIF-Palette und GIF-Export.

GIF kennt maximal 256 Palettenfarben und nur binäre Transparenz. Ein Index
wird für "transparent" reserviert, es bleiben also bis zu 255 echte Farben.

Die Palette wird nur aus den *sichtbaren* Pixeln berechnet, damit keine
Paletteneinträge an unsichtbare Pixel verschwendet werden.

Quantisierer (in dieser Reihenfolge):
  1. exakt  - hat das Logo <= 255 Farben, wird nichts reduziert (verlustfrei)
  2. libimagequant (Paket ``imagequant``) - beste Qualität, falls installiert
  3. Pillow Median-Cut mit k-means-Verfeinerung - Fallback
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

try:  # optional, deutlich bessere Paletten
    import imagequant  # type: ignore
except Exception:  # pragma: no cover - abhängig von der Installation
    imagequant = None


def _palette_from_pixels(pixels: np.ndarray, max_colors: int) -> tuple[np.ndarray, str]:
    """pixels: (N, 3) uint8 -> (palette (K, 3) uint8, Name des Verfahrens)."""
    unique = np.unique(pixels, axis=0)
    if len(unique) <= max_colors:
        return unique, "exakt (verlustfrei)"

    strip = Image.fromarray(pixels.reshape(1, -1, 3), "RGB")

    if imagequant is not None:
        try:
            q = imagequant.quantize_pil_image(
                strip.convert("RGBA"),
                dithering_level=0.0,
                max_colors=max_colors,
                min_quality=0,
                max_quality=100,
            )
            used = np.unique(np.asarray(q)).tolist()
            pal = np.array(q.getpalette()[: 3 * 256], dtype=np.uint8).reshape(-1, 3)
            return pal[used], "libimagequant"
        except Exception:
            pass

    q = strip.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT, kmeans=4,
                       dither=Image.Dither.NONE)
    used = np.unique(np.asarray(q)).tolist()
    pal = np.array(q.getpalette()[: 3 * 256], dtype=np.uint8).reshape(-1, 3)
    return pal[used], "Median-Cut (Pillow)"


def quantize_to_gif_palette(
    rgb: np.ndarray,
    visible: np.ndarray,
    matte: tuple[int, int, int],
    max_colors: int = 255,
    dither: bool = False,
) -> tuple[Image.Image, int, int, str]:
    """Erzeugt ein P-Bild mit Transparenzindex.

    rgb:     (H, W, 3) uint8, bereits auf die Matte-Farbe gemischt
    visible: (H, W) bool, True = sichtbares Pixel
    Rückgabe: (P-Bild, Transparenzindex, Anzahl Farben, Verfahren)
    """
    max_colors = max(1, min(int(max_colors), 255))
    h, w = visible.shape
    if not visible.any():
        raise ValueError("Das Bild enthält keine sichtbaren Pixel.")

    palette, method = _palette_from_pixels(rgb[visible], max_colors)
    n = len(palette)

    # Palette auf 256 auffüllen (mit Kopien von Eintrag 0), damit Pillow keine
    # fremden Farben (z. B. Schwarz) als Ziel wählen kann.
    full = np.vstack([palette, np.repeat(palette[:1], 256 - n, axis=0)])
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(full.flatten().tolist())

    # Unsichtbare Pixel mit der Matte-Farbe füllen: beeinflusst beim Dithering
    # die Kantenpixel neutral.
    src = rgb.copy()
    src[~visible] = matte
    mapped = Image.fromarray(src, "RGB").quantize(
        palette=pal_img,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE,
    )
    idx = np.array(mapped, dtype=np.uint8)
    idx[idx >= n] = 0  # Kopien von Eintrag 0 zurückführen

    trans_index = n  # erster freier Index
    idx[~visible] = trans_index

    out = Image.fromarray(idx, "P")
    final_pal = np.vstack([palette, np.array([matte], dtype=np.uint8)])
    out.putpalette(final_pal.flatten().tolist())
    out.info["transparency"] = trans_index
    return out, trans_index, n, method


def save_gif(img: Image.Image, path: str | Path, trans_index: int) -> None:
    # Saubere Kopie mit frischer RGB-Palette speichern (schützt vor
    # Seiteneffekten früherer convert()-Aufrufe), optimize=False: Pillow soll
    # die Palette nicht umsortieren.
    clean = Image.frombytes("P", img.size, img.tobytes())
    clean.putpalette(img.getpalette("RGB"))
    clean.save(path, format="GIF", transparency=trans_index, optimize=False)
