"""Rotating file logging + an exception hook that never loses a crash silently."""

from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback
from pathlib import Path

from fcc import paths

LOGGER_NAME = "fcc"
_configured = False


def setup_logging(level: int = logging.INFO, console: bool = False) -> logging.Logger:
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger
    paths.ensure_runtime_dirs()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(threadName)-14s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            paths.log_file(), maxBytes=4_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except OSError:
        pass

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        stream.setLevel(level)
        logger.addHandler(stream)

    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    base = logging.getLogger(LOGGER_NAME)
    return base.getChild(name) if name else base


def install_crash_hook(on_crash=None) -> None:
    """Write unhandled exceptions to a crash file and optionally notify the UI."""
    log = get_logger("crash")

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error("Unhandled exception:\n%s", text)
        try:
            paths.crash_dir().mkdir(parents=True, exist_ok=True)
            import time

            stamp = time.strftime("%Y%m%d-%H%M%S")
            Path(paths.crash_dir() / f"crash-{stamp}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
        if on_crash is not None:
            try:
                on_crash(text)
            except Exception:  # pragma: no cover - the notifier must never raise
                pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook
