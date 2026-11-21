"""Erzeugt synthetische Testlogos (werden von den Tests genutzt)."""
from pathlib import Path

from PIL import Image, ImageDraw


def _crest(size, bg):
    """Wappen: roter Schild mit weißem Innenfeld und dunklem Ring, 4x supersampled."""
    s = 4
    W, H = size[0] * s, size[1] * s
    im = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(im)
    cx, cy = W // 2, H // 2
    r = min(W, H) * 0.42
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(20, 30, 90, 255))
    r2 = r * 0.85
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(200, 20, 30, 255))
    r3 = r * 0.45
    d.ellipse([cx - r3, cy - r3, cx + r3, cy + r3], fill=(255, 255, 255, 255))  # weißes Innenfeld
    d.rectangle([cx - r3 * 0.2, cy - r3 * 0.8, cx + r3 * 0.2, cy + r3 * 0.8], fill=(240, 200, 0, 255))
    return im.resize(size, Image.Resampling.LANCZOS)


def make_all(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    # 1) PNG mit echter Transparenz, quadratisch
    p = out / "crest_alpha.png"; _crest((800, 800), (0, 0, 0, 0)).save(p); paths["alpha"] = p
    # 2) JPG auf weißem Hintergrund, Hochformat (nicht quadratisch!)
    p = out / "crest_white.jpg"; _crest((600, 900), (255, 255, 255, 255)).convert("RGB").save(p, quality=85); paths["white_jpg"] = p
    # 3) Breites Logo auf beigem Hintergrund
    im = Image.new("RGB", (1600, 500), (240, 232, 215))
    big = Image.new("RGB", (6400, 2000), (240, 232, 215))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([400, 300, 6000, 1700], radius=500, fill=(0, 110, 50))
    d.rounded_rectangle([900, 700, 5500, 1300], radius=200, fill=(255, 255, 255))
    im = big.resize((1600, 500), Image.Resampling.LANCZOS)
    p = out / "wide_beige.png"; im.save(p); paths["wide"] = p
    # 4) Sehr kleines Logo (Hochskalieren)
    p = out / "tiny.png"; _crest((60, 60), (0, 0, 0, 0)).save(p); paths["tiny"] = p
    # 5) Umrandung mit schmaler Lücke, weißes Innenfeld (wie UFC Hallein)
    im = Image.new("RGB", (600, 600), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 100, 500, 500], outline=(20, 20, 20), width=14)
    d.rectangle([297, 90, 303, 116], fill=(255, 255, 255))   # 7 px Lücke oben
    d.rectangle([200, 250, 400, 350], fill=(200, 20, 30))
    p = out / "gap_outline.png"; im.save(p); paths["gap"] = p
    # 6) SVG
    p = out / "logo.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">'
                 '<rect x="5" y="5" width="190" height="90" rx="20" fill="#1a3c8f"/>'
                 '<circle cx="100" cy="50" r="30" fill="#ffffff"/></svg>')
    paths["svg"] = p
    return paths


if __name__ == "__main__":
    import sys
    print(make_all(Path(sys.argv[1] if len(sys.argv) > 1 else "samples")))
