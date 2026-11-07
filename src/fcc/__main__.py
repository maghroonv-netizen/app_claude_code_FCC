"""`python -m fcc` entry point."""

from __future__ import annotations

import sys


def main(argv=None) -> int:
    from fcc.ui.app import run

    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
