"""XROM entry point: `uv run xrom`, `python -m xrom`, or PyInstaller onefile."""

from __future__ import annotations

try:
    from xrom.app import main
except ImportError:  # frozen entry without package context
    from app import main  # type: ignore[no-redef]

if __name__ == "__main__":
    main()
