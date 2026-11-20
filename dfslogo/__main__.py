"""`python -m dfslogo` startet ohne Argumente die GUI, mit Argumenten die CLI."""

import sys


def run() -> int:
    if len(sys.argv) > 1:
        from .cli import main
        return main()
    from .gui import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(run())
