from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dfslogo import Options, convert_file, convert_image, parse_color
from dfslogo.cli import main as cli_main

from make_samples import make_all


@pytest.fixture(scope="session")
def samples(tmp_path_factory) -> dict[str, Path]:
    return make_all(tmp_path_factory.mktemp("samples"))


def _load(path: Path):
    im = Image.open(path)
    return im, np.array(im.convert("RGBA"))


@pytest.mark.parametrize("key", ["alpha", "white_jpg", "wide", "tiny"])
def test_dfs_requirements(samples, tmp_path, key):
    out = tmp_path / "out.gif"
    convert_file(samples[key], out)
    im, rgba = _load(out)
    assert im.format == "GIF"                     # (2) GIF
    assert im.size == (144, 144)                  # (3) 144×144
    assert "transparency" in im.info              # (1) Transparenz
    # Ecken sind transparent
    for y, x in [(0, 0), (0, 143), (143, 0), (143, 143)]:
        assert rgba[y, x, 3] == 0
    assert len(im.getcolors(256)) <= 256


def test_aspect_ratio_preserved(samples, tmp_path):
    # Quelle 1600×500 → Inhalt etwa 3.9:1; darf nicht gestaucht werden
    out = tmp_path / "wide.gif"
    r = convert_file(samples["wide"], out)
    _, rgba = _load(out)
    ys, xs = np.nonzero(rgba[..., 3])
    w, h = np.ptp(xs) + 1, np.ptp(ys) + 1
    cw, ch = r.info["content_size"]
    assert abs(w / h - cw / ch) / (cw / ch) < 0.06   # (4) nicht verzerrt
    assert w == 140                                   # nutzt die Breite aus (2 px Rand)
    assert abs((ys.min() + ys.max()) / 2 - 71.5) <= 1  # vertikal zentriert


def test_white_background_removed_inner_white_kept(samples, tmp_path):
    out = tmp_path / "white.gif"
    convert_file(samples["white_jpg"], out)
    _, rgba = _load(out)
    c = rgba[72, 72]                  # Mitte des weißen Innenfelds liegt neben dem gelben Balken
    inner = rgba[72, 72 - 18]
    assert inner[3] == 255 and inner[:3].min() > 235, inner   # Weiß innen bleibt sichtbar
    assert c[3] == 255


def test_colors_preserved(samples, tmp_path):
    """Gespeicherte Farben müssen den Quellfarben entsprechen (Palettenfehler-Regression)."""
    out = tmp_path / "svgish.gif"
    convert_file(samples["alpha"], out)
    _, rgba = _load(out)
    red = rgba[72, 72 - 45]           # roter Ring
    assert red[3] == 255
    assert abs(int(red[0]) - 200) < 12 and red[1] < 40 and red[2] < 50, red


def test_no_halo_on_light_background(samples, tmp_path):
    """Kantenpixel dürfen auf hellem Hintergrund nicht dunkler als der Rand-/Logo-Ton sein,
    und es darf kein dunkler Saum (schwarze Pixel) entstehen."""
    out = tmp_path / "halo.gif"
    convert_file(samples["white_jpg"], out)
    _, rgba = _load(out)
    vis = rgba[..., 3] > 0
    # Logo enthält kein reines Schwarz → im Ergebnis auch nicht (typischer Halo-Fehler)
    assert not np.any(np.all(rgba[vis, :3] < 10, axis=1))


def test_tiny_source_warns(samples):
    from dfslogo import load_image
    r = convert_image(load_image(samples["tiny"]))
    assert any("hochskaliert" in w for w in r.warnings)


def test_svg(samples, tmp_path):
    pytest.importorskip("cairosvg")
    out = tmp_path / "svg.gif"
    r = convert_file(samples["svg"], out)
    assert Image.open(out).size == (144, 144)
    assert r.info["logo_size"] == (140, 66)  # 190×90 → 140×66


def test_parse_color():
    assert parse_color("weiß") == (255, 255, 255)
    assert parse_color("#102030") == (16, 32, 48)
    with pytest.raises(ValueError):
        parse_color("lila")


def test_noisy_background_not_removed_in_auto():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)
    r = convert_image(Image.fromarray(arr, "RGB").convert("RGBA"))
    assert r.warnings and "nicht entfernt" in r.info["background"]


def test_cli_folder(samples, tmp_path):
    out_dir = tmp_path / "cli"
    rc = cli_main([str(samples["alpha"].parent), "-o", str(out_dir), "--matte", "weiss"])
    try:
        import cairosvg  # noqa: F401
        assert rc == 0
    except ImportError:
        assert rc == 1  # SVG ohne cairosvg → gemeldeter Fehler, Rest läuft weiter
    gifs = sorted(out_dir.glob("*_dfs.gif"))
    assert len(gifs) >= 4
    for g in gifs:
        assert Image.open(g).size == (144, 144)
