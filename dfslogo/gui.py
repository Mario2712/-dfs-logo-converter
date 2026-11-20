"""Schlanke Oberfläche (Tkinter): Bild öffnen/hineinziehen, Vorschau, GIF speichern."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import __version__
from .pipeline import (
    MATTE_PRESETS,
    SUPPORTED_EXTENSIONS,
    Options,
    Result,
    convert_image,
    default_output_path,
    load_image,
    preview_on,
)

try:  # optional: Drag & Drop
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
except Exception:  # pragma: no cover
    TkinterDnD = None
    DND_FILES = None

PREVIEW_BGS = [("Weiß", MATTE_PRESETS["weiss"]),
               ("Beige", MATTE_PRESETS["beige"]),
               ("Grau", MATTE_PRESETS["grau"])]
MATTE_LABELS = [("Hell (Standard)", "hell"), ("Weiß", "weiss"),
                ("Beige", "beige"), ("Grau", "grau")]
ZOOM = 3
FILETYPES = [("Bilder", " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))),
             ("Alle Dateien", "*.*")]


def _checkerboard(size: int, cell: int = 8) -> Image.Image:
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    px = img.load()
    for y in range(size):
        for x in range(size):
            if (x // cell + y // cell) % 2:
                px[x, y] = (204, 204, 204, 255)
    return img


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source: Image.Image | None = None
        self.source_path: Path | None = None
        self.result: Result | None = None
        self.custom_matte: tuple[int, int, int] | None = None
        self._pending: str | None = None
        self._photos: list[ImageTk.PhotoImage] = []  # Referenzen halten
        self._checker = _checkerboard(144 * ZOOM, 12)

        root.title(f"DFS Logo Converter {__version__}")
        root.minsize(1060, 620)
        root.geometry("1080x640")
        self._build()
        self._show_empty()

    # ------------------------------------------------------------- Aufbau
    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Bild öffnen…", command=self.open_file).pack(side="left")
        self.save_btn = ttk.Button(bar, text="Als GIF speichern…", command=self.save_file,
                                   state="disabled")
        self.save_btn.pack(side="left", padx=6)
        ttk.Button(bar, text="Ordner umwandeln…", command=self.convert_folder).pack(side="left")

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8)

        # Einstellungen
        s = ttk.LabelFrame(body, text="Einstellungen")
        s.pack(side="left", fill="y", padx=(0, 8), pady=(0, 8))

        ttk.Label(s, text="Kantenfarbe (DFS-Hintergrund):").pack(anchor="w", **pad)
        self.matte_var = tk.StringVar(value="hell")
        for label, key in MATTE_LABELS:
            ttk.Radiobutton(s, text=label, value=key, variable=self.matte_var,
                            command=self.schedule).pack(anchor="w", padx=20)
        row = ttk.Frame(s)
        row.pack(anchor="w", padx=20)
        ttk.Radiobutton(row, text="Eigene:", value="custom", variable=self.matte_var,
                        command=self._pick_custom).pack(side="left")
        self.custom_swatch = tk.Label(row, width=3, relief="sunken", bg="#ffffff")
        self.custom_swatch.pack(side="left", padx=4)

        ttk.Separator(s).pack(fill="x", pady=6)
        ttk.Label(s, text="Hintergrund entfernen:").pack(anchor="w", **pad)
        self.bg_var = tk.StringVar(value="auto")
        cb = ttk.Combobox(s, textvariable=self.bg_var, state="readonly", width=12,
                          values=["auto", "immer", "nie"])
        cb.pack(anchor="w", padx=20)
        cb.bind("<<ComboboxSelected>>", lambda e: self.schedule())

        self.tol_var = tk.DoubleVar(value=40)
        self._slider(s, "Farbtoleranz", self.tol_var, 5, 120, "{:.0f}")

        self.enclosed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(s, text="Auch eingeschlossene Flächen\nentfernen (z. B. Lücken)",
                        variable=self.enclosed_var, command=self.schedule).pack(anchor="w", **pad)
        self.gaps_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(s, text="Kleine Lücken in Umrandungen\nüberbrücken (empfohlen)",
                        variable=self.gaps_var, command=self.schedule).pack(anchor="w", **pad)

        ttk.Separator(s).pack(fill="x", pady=6)
        r = ttk.Frame(s)
        r.pack(anchor="w", **pad)
        ttk.Label(r, text="Rand (px):").pack(side="left")
        self.margin_var = tk.IntVar(value=2)
        ttk.Spinbox(r, from_=0, to=20, width=4, textvariable=self.margin_var,
                    command=self.schedule).pack(side="left", padx=6)
        self.margin_var.trace_add("write", lambda *a: self.schedule())

        self.thr_var = tk.DoubleVar(value=0.5)
        self._slider(s, "Kantenschwelle", self.thr_var, 0.1, 0.9, "{:.2f}")

        self.sharpen_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(s, text="Nachschärfen", variable=self.sharpen_var,
                        command=self.schedule).pack(anchor="w", **pad)
        self.dither_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(s, text="Dithering (Verläufe/Fotos)", variable=self.dither_var,
                        command=self.schedule).pack(anchor="w", **pad)

        # Vorschau
        pv = ttk.LabelFrame(body, text="Vorschau")
        pv.pack(side="left", fill="both", expand=True, pady=(0, 8))
        top = ttk.Frame(pv)
        top.pack(fill="x", padx=8, pady=8)

        left = ttk.Frame(top)
        left.pack(side="left", anchor="n")
        ttk.Label(left, text=f"Ergebnis {ZOOM}× vergrößert (Karo = transparent)").pack(anchor="w")
        self.zoom_label = tk.Label(left, bd=1, relief="solid")
        self.zoom_label.pack()

        # 2×2-Raster: Original | Weiß / Beige | Grau (Ergebnis in Originalgröße)
        right = ttk.Frame(top)
        right.pack(side="left", anchor="n", padx=(16, 0))
        ttk.Label(right, text="Originalgröße auf DFS-Hintergründen").grid(
            row=0, column=0, columnspan=2, sticky="w")
        cells = [("Original", None)] + PREVIEW_BGS
        self.tile_labels = []
        for i, (name, _) in enumerate(cells):
            f = ttk.Frame(right)
            f.grid(row=1 + i // 2, column=i % 2, padx=(0, 8), pady=(4, 4), sticky="n")
            box = tk.Frame(f, width=146, height=146)
            box.pack_propagate(False)
            box.pack()
            lbl = tk.Label(box, bd=0)
            lbl.pack(expand=True)
            ttk.Label(f, text=name).pack()
            if i == 0:
                self.orig_label = lbl
            else:
                self.tile_labels.append(lbl)

        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, anchor="w", justify="left",
                  wraplength=820).pack(fill="x", padx=8, pady=(0, 8))

        if TkinterDnD is not None:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _slider(self, parent, label, var, lo, hi, fmt) -> None:
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=8, pady=4)
        txt = tk.StringVar()

        def upd(*_):
            txt.set(f"{label}: {fmt.format(var.get())}")
        upd()
        ttk.Label(f, textvariable=txt).pack(anchor="w")
        ttk.Scale(f, from_=lo, to=hi, variable=var,
                  command=lambda v: (upd(), self.schedule())).pack(fill="x")

    # ------------------------------------------------------------ Optionen
    def options(self) -> Options:
        key = self.matte_var.get()
        matte = (self.custom_matte or MATTE_PRESETS["hell"]) if key == "custom" \
            else MATTE_PRESETS[key]
        try:
            margin = max(0, min(20, int(self.margin_var.get())))
        except (tk.TclError, ValueError):
            margin = 2
        return Options(
            margin=margin,
            matte=matte,
            alpha_threshold=float(self.thr_var.get()),
            background={"auto": "auto", "immer": "always", "nie": "never"}[self.bg_var.get()],
            tolerance=float(self.tol_var.get()),
            remove_enclosed=self.enclosed_var.get(),
            close_gaps=self.gaps_var.get(),
            sharpen=self.sharpen_var.get(),
            dither=self.dither_var.get(),
        )

    def _pick_custom(self) -> None:
        initial = "#%02x%02x%02x" % (self.custom_matte or MATTE_PRESETS["hell"])
        rgb, hexval = colorchooser.askcolor(color=initial, title="Hintergrundfarbe in DFS")
        if rgb:
            self.custom_matte = tuple(int(c) for c in rgb)  # type: ignore[assignment]
            self.custom_swatch.configure(bg=hexval)
        elif self.custom_matte is None:
            self.matte_var.set("hell")
        self.schedule()

    # ------------------------------------------------------------- Aktionen
    def _on_drop(self, event) -> None:
        files = self.root.tk.splitlist(event.data)
        if files:
            self.load(Path(files[0]))

    def open_file(self) -> None:
        p = filedialog.askopenfilename(title="Logo öffnen", filetypes=FILETYPES)
        if p:
            self.load(Path(p))

    def load(self, path: Path) -> None:
        try:
            self.source = load_image(path)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Bild konnte nicht geladen werden:\n{exc}")
            return
        self.source_path = path
        thumb = self.source.copy()
        thumb.thumbnail((144, 144), Image.Resampling.LANCZOS)
        bg = _checkerboard(max(thumb.size), 8).crop((0, 0, *thumb.size))
        bg.alpha_composite(thumb)
        self._set(self.orig_label, bg, slot=0)
        self.process()

    def schedule(self, *_):
        if self.source is None:
            return
        if self._pending:
            self.root.after_cancel(self._pending)
        self._pending = self.root.after(200, self.process)

    def process(self) -> None:
        self._pending = None
        if self.source is None:
            return
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            self.result = convert_image(self.source, self.options())
        except Exception as exc:
            self.result = None
            self.save_btn.configure(state="disabled")
            self.status.set(f"Fehler: {exc}")
            return
        finally:
            self.root.config(cursor="")
        r = self.result
        big = self._checker.copy()
        big.alpha_composite(r.preview.resize((144 * ZOOM, 144 * ZOOM), Image.Resampling.NEAREST))
        self._set(self.zoom_label, big, slot=1)
        for i, (lbl, (_, color)) in enumerate(zip(self.tile_labels, PREVIEW_BGS)):
            self._set(lbl, preview_on(r.preview, color), slot=2 + i)
        msg = (f"{self.source_path.name}:  Hintergrund {r.info['background']}  ·  "
               f"Logo {r.info['logo_size'][0]}×{r.info['logo_size'][1]} px in 144×144  ·  "
               f"{r.info['colors']} Farben ({r.info['quantizer']})")
        if r.warnings:
            msg += "\n⚠ " + "\n⚠ ".join(r.warnings)
        self.status.set(msg)
        self.save_btn.configure(state="normal")

    def save_file(self) -> None:
        if not self.result or not self.source_path:
            return
        initial = default_output_path(self.source_path)
        p = filedialog.asksaveasfilename(
            title="GIF speichern", defaultextension=".gif",
            initialdir=str(initial.parent), initialfile=initial.name,
            filetypes=[("GIF", "*.gif")])
        if not p:
            return
        try:
            self.result.save(p)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen:\n{exc}")
            return
        self.status.set(f"Gespeichert: {p}")

    def convert_folder(self) -> None:
        src = filedialog.askdirectory(title="Ordner mit Logos wählen")
        if not src:
            return
        src_dir = Path(src)
        files = sorted(f for f in src_dir.iterdir()
                       if f.suffix.lower() in SUPPORTED_EXTENSIONS and not f.stem.endswith("_dfs"))
        if not files:
            messagebox.showinfo("Ordner umwandeln", "Keine Bilder im Ordner gefunden.")
            return
        out_dir = src_dir / "dfs"
        out_dir.mkdir(exist_ok=True)
        opts = self.options()
        ok, failed = 0, []
        for i, f in enumerate(files, 1):
            self.status.set(f"Wandle um ({i}/{len(files)}): {f.name}")
            self.root.update()
            try:
                convert_image(load_image(f), opts).save(default_output_path(f, out_dir))
                ok += 1
            except Exception as exc:
                failed.append(f"{f.name}: {exc}")
        text = f"{ok} von {len(files)} Logos umgewandelt.\nZiel: {out_dir}"
        if failed:
            text += "\n\nFehler:\n" + "\n".join(failed[:10])
        self.status.set(text.replace("\n", "  "))
        messagebox.showinfo("Ordner umwandeln", text)

    # -------------------------------------------------------------- Helfer
    def _set(self, label: tk.Label, img: Image.Image, slot: int) -> None:
        photo = ImageTk.PhotoImage(img)
        while len(self._photos) <= slot:
            self._photos.append(None)  # type: ignore[arg-type]
        self._photos[slot] = photo
        label.configure(image=photo)

    def _show_empty(self) -> None:
        self._set(self.zoom_label, self._checker, slot=1)
        hint = ("Logo öffnen" + (" oder ins Fenster ziehen" if TkinterDnD else "") +
                " – das Ergebnis erscheint sofort hier.")
        self.status.set(hint)


def main() -> None:
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    try:
        ttk.Style(root).theme_use("clam" if root.tk.call("tk", "windowingsystem") == "x11"
                                  else ttk.Style(root).theme_use())
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
