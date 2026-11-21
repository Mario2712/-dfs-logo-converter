"""Kern-Pipeline: beliebiges Bild -> 144x144 GIF mit transparentem Hintergrund.

Schritte:
  1. Einlesen (Raster oder SVG) -> RGBA
  2. Hintergrund entfernen (falls nicht schon transparent)
  3. Leerraum abschneiden
  4. Seitenverhältnis-treu skalieren und mittig platzieren
  5. Hochwertig skalieren (Lanczos, vormultipliertes Alpha) + leicht schärfen
  6. Kanten für GIF vorbereiten (Matte-Farbe + Alpha-Schwelle)
  7. Farbreduktion (<= 255 Farben + 1 Transparenzindex)
  8. Export + Prüfung
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from . import background as bgmod
from .quantize import quantize_to_gif_palette, save_gif

# Matte-Farben: Hintergründe, auf denen DFS die Logos typischerweise zeigt.
MATTE_PRESETS: dict[str, tuple[int, int, int]] = {
    "hell": (246, 244, 239),   # Standard: Kompromiss aus Weiß, Beige und Hellgrau
    "weiss": (255, 255, 255),
    "beige": (242, 236, 224),
    "grau": (230, 230, 230),
}

RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = RASTER_EXTENSIONS | {".svg"}

# Große Quellbilder vorab verkleinern: für 144 px Ausgabe reicht das locker
# und hält die Verarbeitung schnell.
WORKING_MAX = 1200
SVG_RENDER_SIZE = 1200
# So viele Bytes werden gelesen, um eine SVG am Inhalt zu erkennen
# (reicht auch für lange Kommentare/DOCTYPE vor dem <svg>-Element).
SVG_SNIFF_BYTES = 64 * 1024


@dataclass
class Options:
    size: int = 144
    margin: int = 2
    matte: tuple[int, int, int] = MATTE_PRESETS["hell"]
    alpha_threshold: float = 0.5
    background: str = "auto"  # "auto" | "always" | "never"
    tolerance: float = 40.0
    remove_enclosed: bool = False
    close_gaps: bool = True   # Engstellen-Sperre gegen "Durchsickern" ins Logo
    sharpen: bool = True
    dither: bool = False
    max_colors: int = 255


@dataclass
class Result:
    gif: Image.Image                 # P-Bild, fertig zum Speichern
    trans_index: int
    preview: Image.Image             # RGBA-Ansicht des GIF-Ergebnisses
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        save_gif(self.gif, path, self.trans_index)
        verify_gif(path, self.gif.size[0], expected=self.preview)
        return path


def parse_color(value: str) -> tuple[int, int, int]:
    """'weiss', 'beige', 'grau', 'hell' oder '#RRGGBB'."""
    v = value.strip().lower().replace("ß", "ss")
    if v in MATTE_PRESETS:
        return MATTE_PRESETS[v]
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 6:
        try:
            return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    raise ValueError(
        f"Unbekannte Farbe '{value}'. Erlaubt: {', '.join(MATTE_PRESETS)} oder #RRGGBB."
    )


# --------------------------------------------------------------------------- 1
def is_svg_file(path: str | Path) -> bool:
    """Erkennt SVG am Inhalt statt an der Endung (z. B. eine in .png umbenannte SVG)."""
    with open(path, "rb") as f:
        head = f.read(SVG_SNIFF_BYTES)
    start = head.removeprefix(b"\xef\xbb\xbf").lstrip()
    # Vor <svg dürfen XML-Deklaration, Kommentare und DOCTYPE stehen.
    return start.startswith(b"<") and re.search(rb"<svg[\s>]", head, re.IGNORECASE) is not None


def _render_svg(path: Path) -> Image.Image:
    """Rendert eine SVG so, dass die längere Seite SVG_RENDER_SIZE Pixel hat."""
    try:
        import resvg_py  # type: ignore
    except ImportError:
        resvg_py = None

    try:
        if resvg_py is not None:
            # Erst in Originalgröße rendern, um das Seitenverhältnis zu kennen.
            w, h = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_path=str(path))))).size
            zoom = SVG_RENDER_SIZE / max(w, h, 1)
            data = bytes(resvg_py.svg_to_bytes(svg_path=str(path), zoom=zoom,
                                               resources_dir=str(path.parent)))
        else:
            try:
                import cairosvg  # type: ignore
            except Exception as exc:  # ImportError oder fehlende Cairo-Bibliothek (OSError)
                raise RuntimeError(
                    "Für SVG-Dateien wird das Paket 'resvg-py' benötigt "
                    "(pip install resvg-py). Alternativ das Logo als PNG exportieren."
                ) from exc
            data = cairosvg.svg2png(bytestring=path.read_bytes(), url=str(path),
                                    output_width=SVG_RENDER_SIZE)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"SVG-Datei konnte nicht gelesen werden: {exc}") from exc

    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGBA")


def load_image(path: str | Path) -> Image.Image:
    """Lädt ein Bild als RGBA. SVG (am Inhalt erkannt) wird in hoher Auflösung gerendert."""
    path = Path(path)
    if is_svg_file(path):
        return _limit_size(_render_svg(path))

    img = Image.open(path)
    img.seek(0)  # bei animierten GIFs: erstes Bild
    img = ImageOps.exif_transpose(img)
    return _limit_size(to_rgba(img))


def to_rgba(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        return img.copy()
    if img.mode == "P" or img.mode == "LA" or img.mode == "PA":
        return img.convert("RGBA")
    if img.mode == "CMYK":
        return img.convert("RGB").convert("RGBA")
    if img.mode.startswith("I;16") or img.mode == "I":
        arr = np.array(img, dtype=np.float32)
        arr = (arr / max(arr.max(), 1) * 255).astype(np.uint8)
        return Image.fromarray(arr, "L").convert("RGBA")
    return img.convert("RGBA")


def _limit_size(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) <= WORKING_MAX:
        return img
    s = WORKING_MAX / max(w, h)
    return img.resize((max(1, round(w * s)), max(1, round(h * s))),
                      Image.Resampling.LANCZOS, reducing_gap=3.0)


# ---------------------------------------------------------------- Pipeline
def convert_image(img: Image.Image, opts: Options | None = None) -> Result:
    """Wandelt ein RGBA-Bild in ein DFS-taugliches GIF um (im Speicher)."""
    opts = opts or Options()
    warnings: list[str] = []
    info: dict = {"source_size": img.size}

    rgba = np.array(to_rgba(img))

    # 2 ── Hintergrund
    if opts.background != "never" and bgmod.has_transparency(rgba):
        info["background"] = "Transparenz aus der Datei übernommen"
    elif opts.background == "never":
        info["background"] = "nicht entfernt (abgeschaltet)"
    else:
        bg = bgmod.estimate_background(rgba[..., :3], opts.tolerance)
        info["background_color"] = "#%02X%02X%02X" % bg.color
        if opts.background == "auto" and bg.uniformity < 0.6:
            warnings.append(
                "Der Bildrand hat keine einheitliche Hintergrundfarbe – Hintergrund wurde "
                "nicht entfernt. Option 'Hintergrund: immer' erzwingt die Entfernung."
            )
            info["background"] = "nicht entfernt (Rand uneinheitlich)"
        else:
            rgba = bgmod.remove_background(
                rgba, bg, tolerance=opts.tolerance, remove_enclosed=opts.remove_enclosed,
                gap_radius=None if opts.close_gaps else 0,
            )
            info["background"] = f"entfernt ({info['background_color']})"

    # 3 ── Zuschneiden auf sichtbaren Inhalt
    ys, xs = np.nonzero(rgba[..., 3] > 10)
    if len(ys) == 0:
        raise ValueError("Nach der Hintergrundentfernung ist nichts mehr übrig "
                         "(Toleranz zu hoch?).")
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    content = Image.fromarray(rgba, "RGBA")
    cw, ch = content.size
    info["content_size"] = (cw, ch)

    # 4/5 ── Seitenverhältnis-treu skalieren
    box = opts.size - 2 * opts.margin
    if box < 8:
        raise ValueError("Rand zu groß für die Zielgröße.")
    scale = box / max(cw, ch)
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    if scale > 1.0:
        warnings.append(
            f"Die Quelle ist klein ({cw}×{ch} px) und wird hochskaliert – für beste "
            "Qualität ein größeres Bild (mind. 300 px) verwenden."
        )
    # Pillow skaliert RGBA intern mit vormultipliertem Alpha → keine dunklen Säume
    resized = content.resize((nw, nh), Image.Resampling.LANCZOS, reducing_gap=3.0)

    canvas = Image.new("RGBA", (opts.size, opts.size), (0, 0, 0, 0))
    canvas.paste(resized, ((opts.size - nw) // 2, (opts.size - nh) // 2))
    info["logo_size"] = (nw, nh)

    # 6 ── Kanten für GIF: auf Matte-Farbe mischen, dann Alpha-Schwelle
    arr = np.array(canvas).astype(np.float32)
    a = arr[..., 3:4] / 255.0
    matte = np.array(opts.matte, dtype=np.float32)
    comp = arr[..., :3] * a + matte * (1.0 - a)
    comp_img = Image.fromarray(np.clip(np.round(comp), 0, 255).astype(np.uint8), "RGB")
    if opts.sharpen and scale < 1.0:
        comp_img = comp_img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=2))
    visible = a[..., 0] >= opts.alpha_threshold

    # 7 ── Farbreduktion
    gif, tidx, ncolors, method = quantize_to_gif_palette(
        np.array(comp_img), visible, opts.matte, opts.max_colors, opts.dither
    )
    info["colors"] = ncolors
    info["quantizer"] = method

    # Kopie! Pillow verändert bei convert("RGBA") sonst die interne Palette
    # des Originals, was beim Speichern zu falschen Farben führt.
    preview = gif.copy().convert("RGBA")
    return Result(gif=gif, trans_index=tidx, preview=preview, warnings=warnings, info=info)


def convert_file(src: str | Path, dst: str | Path, opts: Options | None = None) -> Result:
    result = convert_image(load_image(src), opts)
    result.save(dst)
    return result


# --------------------------------------------------------------------------- 8
def verify_gif(path: str | Path, size: int = 144, expected: Image.Image | None = None) -> None:
    """Prüft das geschriebene GIF auf die DFS-Anforderungen.

    expected: optional die erwartete RGBA-Ansicht; dann wird die Datei
    zusätzlich pixelgenau verglichen (Farben + Transparenz).
    """
    with Image.open(path) as im:
        if im.format != "GIF":
            raise AssertionError(f"{path}: kein GIF")
        if im.size != (size, size):
            raise AssertionError(f"{path}: Größe {im.size} statt {size}×{size}")
        if "transparency" not in im.info:
            raise AssertionError(f"{path}: kein Transparenzindex gesetzt")
        if expected is not None:
            got = np.array(im.convert("RGBA"))
            exp = np.array(expected)
            vis = exp[..., 3] > 0
            if not (np.array_equal(got[..., 3] > 0, vis)
                    and np.array_equal(got[vis, :3], exp[vis, :3])):
                raise AssertionError(f"{path}: gespeicherte Datei weicht vom Ergebnis ab")


def preview_on(result_rgba: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Ergebnis auf einer Hintergrundfarbe darstellen (für Vorschauen)."""
    bg = Image.new("RGBA", result_rgba.size, color + (255,))
    return Image.alpha_composite(bg, result_rgba).convert("RGB")


def default_output_path(src: Path, out_dir: Path | None = None) -> Path:
    return (out_dir or src.parent) / f"{src.stem}_dfs.gif"
