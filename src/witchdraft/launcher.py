from __future__ import annotations

import sys


def _run_gui() -> int:
    try:
        from .app import main as gui_main
    except ModuleNotFoundError as exc:
        missing = (exc.name or "").split(".")[0]
        if missing == "PyQt6":
            print("PyQt6 not installed. Run: pip install -e .")
            return 1
        raise
    gui_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print("CLI/TUI entry points are disabled. Launching the GUI.")
    return _run_gui()
