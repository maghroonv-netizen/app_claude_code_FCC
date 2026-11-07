"""Filesystem locations used by the app (config, logs, sessions, build output)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Root of the source checkout (meaningful only when not frozen)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _windows_base() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Roaming"


def app_data_dir() -> Path:
    """Writable per-user data directory."""
    override = os.environ.get("FCC_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = _windows_base() / "ClaudeCodeStudio"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "ClaudeCodeStudio"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "ClaudeCodeStudio"
    return base


def config_dir() -> Path:
    return app_data_dir()


def config_file() -> Path:
    return app_data_dir() / "config.json"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def log_file() -> Path:
    return log_dir() / "studio.log"


def sessions_dir() -> Path:
    """Local transcript storage for conversations started from the GUI."""
    return app_data_dir() / "sessions"


def cache_dir() -> Path:
    return app_data_dir() / "cache"


def crash_dir() -> Path:
    return app_data_dir() / "crashes"


def build_dir() -> Path:
    """Where packaged installers/executables are written."""
    return repo_root() / "build" / "output"


def asset_path(*parts: str) -> Path:
    """Resolve a bundled asset for both source and frozen runs."""
    relative = Path(*parts)
    candidates = []
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / relative)
        candidates.append(Path(sys.executable).resolve().parent / relative)
    candidates.append(repo_root() / relative)
    candidates.append(Path(__file__).resolve().parents[2] / relative)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def ensure_runtime_dirs() -> None:
    for directory in (app_data_dir(), log_dir(), sessions_dir(), cache_dir(), crash_dir()):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
