"""DFS Logo Converter – Vereinslogos in 144×144-GIFs für Das Fußball Studio umwandeln."""

from .pipeline import (  # noqa: F401
    MATTE_PRESETS,
    Options,
    Result,
    convert_file,
    convert_image,
    load_image,
    parse_color,
)

__version__ = "1.0.0"
