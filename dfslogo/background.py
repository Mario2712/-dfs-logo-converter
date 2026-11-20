"""Hintergrund-Erkennung und -Entfernung.

Vorgehen (ohne KI, rein bildbasiert):

1. Die Hintergrundfarbe wird aus den Randpixeln des Bildes geschätzt (Median).
2. Alle Pixel, die farblich nah an dieser Farbe liegen *und* über eine
   zusammenhängende Fläche mit dem Bildrand verbunden sind, werden transparent
   (Flood-Fill von außen). Weiße Flächen *innerhalb* eines Wappens bleiben so
   erhalten.
3. In einem schmalen Kantenband um die entfernte Fläche wird für jedes Pixel
   ein weicher Alpha-Wert geschätzt (Mischung aus Vordergrund- und
   Hintergrundfarbe) und die Farbe "entmischt". Dadurch verschwinden helle
   Säume, die sonst als Halo sichtbar wären.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass
class BackgroundInfo:
    color: tuple[int, int, int]
    uniformity: float  # Anteil der Randpixel, die zur Hintergrundfarbe passen (0..1)


def has_transparency(rgba: np.ndarray, min_fraction: float = 0.01) -> bool:
    """True, wenn das Bild bereits nennenswert transparente Pixel enthält."""
    return float((rgba[..., 3] < 250).mean()) >= min_fraction


def _border_pixels(rgb: np.ndarray) -> np.ndarray:
    return np.concatenate([rgb[0, :], rgb[-1, :], rgb[1:-1, 0], rgb[1:-1, -1]], axis=0)


def estimate_background(rgb: np.ndarray, tolerance: float) -> BackgroundInfo:
    border = _border_pixels(rgb).astype(np.float32)
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(border - bg, axis=1)
    uniformity = float((dist < tolerance).mean())
    return BackgroundInfo(tuple(int(round(c)) for c in bg), uniformity)


def auto_gap_radius(h: int, w: int) -> float:
    return max(3.0, 0.008 * max(h, w))


def _border_connected(candidate: np.ndarray, labels: np.ndarray, gap_radius: float) -> np.ndarray:
    """Hintergrundflächen, die mit dem Bildrand verbunden sind.

    Mit gap_radius > 0 als morphologisches Öffnen: Nur der "Kern" der
    Kandidatenfläche (Abstand zur nächsten Logo-Kante > gap_radius) wird vom
    Rand aus geflutet, danach wird er wieder um gap_radius aufgeweitet. Schmale
    Kanäle (z. B. eine Lücke zwischen Umrandung und Ball) unterbrechen den Fill.
    """
    if gap_radius <= 0:
        border_labels = np.unique(
            np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
        )
        keep = np.zeros(labels.max() + 1, dtype=bool)
        keep[border_labels] = True
        keep[0] = False
        return keep[labels]

    # Außerhalb des Bildes gilt als Hintergrund: schmale Streifen zwischen
    # Logo und Bildrand bleiben so erreichbar.
    p = int(np.ceil(gap_radius)) + 2
    pad = np.pad(candidate, p, constant_values=True)
    core = ndimage.distance_transform_edt(pad) > gap_radius
    core_labels, _ = ndimage.label(core)
    seeds = np.unique(core_labels[0, :])
    seeds = seeds[seeds > 0]
    kept = np.isin(core_labels, seeds)
    opened = (ndimage.distance_transform_edt(~kept) <= gap_radius + 0.5) & pad
    return opened[p:-p, p:-p]


def remove_background(
    rgba: np.ndarray,
    bg: BackgroundInfo,
    tolerance: float = 40.0,
    edge_band: int = 2,
    remove_enclosed: bool = False,
    gap_radius: float | None = None,
) -> np.ndarray:
    """Entfernt den Hintergrund und gibt ein neues RGBA-Array (uint8) zurück.

    tolerance:       maximaler Farbabstand (RGB, euklidisch, 0..441) zur
                     Hintergrundfarbe, der noch als Hintergrund zählt.
    edge_band:       Breite (Pixel) des Kantenbandes mit weichem Alpha.
    remove_enclosed: auch eingeschlossene Flächen in Hintergrundfarbe
                     entfernen (z. B. Lücken in einem Schriftzug). Vorsicht:
                     entfernt dann auch weiße Logo-Bestandteile.
    gap_radius:      Engstellen-Sperre (Pixel). Der Flood-Fill läuft nur durch
                     Durchgänge, die breiter als 2*gap_radius sind. So "sickert"
                     er nicht durch kleine Lücken in einer Umrandung ins
                     Logo-Innere. None = automatisch (0,8 % der Bildgröße),
                     0 = aus.
    """
    rgb = rgba[..., :3].astype(np.float32)
    h, w = rgb.shape[:2]
    bg_color = np.array(bg.color, dtype=np.float32)

    diff = rgb - bg_color
    dist = np.linalg.norm(diff, axis=2)
    candidate = dist < tolerance

    # 4er-Nachbarschaft: verhindert, dass der Fill diagonal durch
    # geglättete Konturen "durchsickert".
    labels, n = ndimage.label(candidate)
    if n == 0:
        return rgba.copy()

    if remove_enclosed:
        sizes = ndimage.sum_labels(candidate, labels, index=np.arange(1, n + 1))
        min_area = max(16, int(0.0005 * h * w))  # Winzige Glanzpunkte behalten
        keep = np.zeros(n + 1, dtype=bool)
        keep[1:] = sizes >= min_area
        background = keep[labels]
    else:
        if gap_radius is None:
            gap_radius = auto_gap_radius(h, w)
        background = _border_connected(candidate, labels, gap_radius)

    if not background.any():
        return rgba.copy()

    band = ndimage.binary_dilation(background, iterations=edge_band) & ~background
    opaque = ~background & ~band

    alpha = np.ones((h, w), dtype=np.float32)
    alpha[background] = 0.0
    out_rgb = rgb.copy()

    if opaque.any() and band.any():
        # Für jedes Kantenpixel: Farbe des nächstgelegenen sicheren
        # Vordergrundpixels als Schätzung der "reinen" Vordergrundfarbe.
        _, (iy, ix) = ndimage.distance_transform_edt(~opaque, return_indices=True)
        by, bx = np.nonzero(band)
        fg = rgb[iy[by, bx], ix[by, bx]]
        px = rgb[by, bx]

        fb = fg - bg_color
        pb = px - bg_color
        denom = np.sum(fb * fb, axis=1)
        a = np.where(
            denom > tolerance**2,
            np.sum(pb * fb, axis=1) / np.maximum(denom, 1e-6),
            1.0,  # Vordergrund ≈ Hintergrundfarbe: keine verlässliche Schätzung
        )
        a = np.clip(a, 0.0, 1.0).astype(np.float32)

        # Farbe entmischen: I = a*F + (1-a)*B  =>  F = B + (I-B)/a
        safe = a > 0.05
        unmixed = px.copy()
        unmixed[safe] = bg_color + pb[safe] / a[safe, None]
        out_rgb[by, bx] = np.clip(unmixed, 0, 255)
        alpha[by, bx] = a

    # Vorhandenen Alpha-Kanal respektieren (falls teilweise vorhanden)
    alpha = np.minimum(alpha, rgba[..., 3].astype(np.float32) / 255.0)

    out = np.empty_like(rgba)
    out[..., :3] = np.round(out_rgb).astype(np.uint8)
    out[..., 3] = np.round(alpha * 255).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out
