#!/usr/bin/env python3
"""Launch Claude Code Studio from a source checkout.

    python run.py                 # normal start
    python run.py --demo          # explore the UI without the CLI
    python run.py C:\\path\\project  # open a folder directly
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    try:
        from fcc.ui.app import run
    except ImportError as exc:  # pragma: no cover
        print(f"Missing dependency: {exc}", file=sys.stderr)
        print("Install requirements first:  pip install -r requirements.txt", file=sys.stderr)
        return 2
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
