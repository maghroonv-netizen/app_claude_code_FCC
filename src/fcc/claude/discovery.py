"""Locating and interrogating the Claude Code CLI without ever showing a terminal."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fcc.logging_setup import get_logger

log = get_logger("cli.discovery")

_WINDOWS = sys.platform == "win32"
_NO_WINDOW = 0x08000000 if _WINDOWS else 0  # CREATE_NO_WINDOW


def creation_flags() -> int:
    return _NO_WINDOW


def startupinfo():
    """Hide any console window on Windows."""
    if not _WINDOWS:
        return None
    info = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    info.wShowWindow = 0  # SW_HIDE
    return info


def is_wrapper(path: str) -> bool:
    return path.lower().endswith((".cmd", ".bat", ".ps1"))


def wrap_command(executable: str, args: List[str]) -> List[str]:
    """Make .cmd/.bat launchers work with CreateProcess on Windows."""
    if _WINDOWS and is_wrapper(executable):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/d", "/s", "/c", executable, *args]
    return [executable, *args]


def candidate_paths(explicit: str = "") -> List[str]:
    """Every plausible location of the `claude` executable, best first."""
    out: List[str] = []
    if explicit:
        out.append(os.path.expanduser(explicit))
    env_path = os.environ.get("FCC_CLAUDE_PATH")
    if env_path:
        out.append(os.path.expanduser(env_path))

    names = ["claude.exe", "claude.cmd", "claude.bat", "claude"] if _WINDOWS else ["claude"]
    for name in names:
        found = shutil.which(name)
        if found:
            out.append(found)

    home = Path.home()
    guesses: List[Path] = []
    if _WINDOWS:
        appdata = os.environ.get("APPDATA")
        local = os.environ.get("LOCALAPPDATA")
        profile = os.environ.get("USERPROFILE", str(home))
        if appdata:
            guesses += [
                Path(appdata) / "npm" / "claude.cmd",
                Path(appdata) / "npm" / "claude.ps1",
                Path(appdata) / "npm" / "claude",
            ]
        if local:
            guesses += [
                Path(local) / "Programs" / "claude" / "claude.exe",
                Path(local) / "claude" / "claude.exe",
                Path(local) / "AnthropicClaude" / "claude.exe",
                Path(local) / "Microsoft" / "WindowsApps" / "claude.exe",
            ]
        guesses += [
            Path(profile) / ".local" / "bin" / "claude.exe",
            Path(profile) / ".claude" / "local" / "claude.exe",
            Path("C:/Program Files/Claude/claude.exe"),
            Path("C:/Program Files (x86)/Claude/claude.exe"),
        ]
    else:
        guesses += [
            home / ".local" / "bin" / "claude",
            home / ".claude" / "local" / "claude",
            home / ".npm-global" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
            Path("/usr/bin/claude"),
            Path("/opt/homebrew/bin/claude"),
        ]
    out.extend(str(g) for g in guesses)

    seen: List[str] = []
    for item in out:
        if item and item not in seen:
            seen.append(item)
    return seen


def find_claude(explicit: str = "") -> Optional[str]:
    for candidate in candidate_paths(explicit):
        path = Path(candidate)
        try:
            if path.is_file() and os.access(path, os.X_OK if not _WINDOWS else os.R_OK):
                return str(path)
        except OSError:
            continue
    return None


@dataclass
class CliInfo:
    path: str = ""
    found: bool = False
    version: str = ""
    raw_version: str = ""
    major: int = 0
    minor: int = 0
    patch: int = 0
    help_text: str = ""
    error: str = ""
    install_hint: str = ""
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def display_version(self) -> str:
        return self.version or "?"

    @property
    def version_tuple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def at_least(self, major: int, minor: int = 0, patch: int = 0) -> bool:
        return self.version_tuple >= (major, minor, patch)


_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def run_capture(argv: List[str], cwd: Optional[str] = None, timeout: int = 25,
                env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    """Run a short-lived command and capture output without a console window."""
    full_env = os.environ.copy()
    if env:
        full_env.update({k: v for k, v in env.items() if v is not None})
    full_env.setdefault("NO_COLOR", "1")
    full_env.setdefault("CI", "1")
    full_env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    try:
        proc = subprocess.run(
            wrap_command(argv[0], argv[1:]),
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=full_env,
            creationflags=creation_flags(),
            startupinfo=startupinfo(),
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", f"executable not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        return 126, "", str(exc)


def probe(explicit: str = "", cwd: Optional[str] = None, timeout: int = 30,
          include_help: bool = True) -> CliInfo:
    """Resolve the CLI, read its version and (optionally) its help text."""
    info = CliInfo()
    path = find_claude(explicit)
    if not path:
        info.error = "not-found"
        info.install_hint = "npm install -g @anthropic-ai/claude-code"
        log.warning("Claude Code CLI not found (explicit=%r)", explicit)
        return info
    info.path = path
    info.found = True

    code, out, err = run_capture([path, "--version"], cwd=cwd, timeout=timeout)
    text = (out or err or "").strip()
    info.raw_version = text.splitlines()[0] if text else ""
    match = _VERSION_RE.search(text)
    if match:
        info.major, info.minor, info.patch = (int(g) for g in match.groups())
        info.version = ".".join(match.groups())
    else:
        info.error = f"version-parse-failed (exit {code}): {text[:200]}"

    if include_help:
        code, out, err = run_capture([path, "--help"], cwd=cwd, timeout=timeout)
        info.help_text = out or err or ""
        if code not in (0,) and not info.help_text:
            info.error = (info.error + f" | help-failed (exit {code})").strip(" |")

    info.extra["auth_hint"] = detect_auth_hint()
    log.info("Claude Code CLI %s at %s", info.version or "(unknown)", path)
    return info


def detect_auth_hint() -> str:
    """Best-effort, non-blocking guess about whether the CLI is signed in."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY"
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "ANTHROPIC_AUTH_TOKEN"
    if os.environ.get("CLAUDE_CODE_USE_BEDROCK"):
        return "bedrock"
    if os.environ.get("CLAUDE_CODE_USE_VERTEX"):
        return "vertex"
    home = Path.home()
    for candidate in (
        home / ".claude" / ".credentials.json",
        home / ".claude" / "auth.json",
        home / ".config" / "claude" / ".credentials.json",
    ):
        try:
            if candidate.exists():
                return "credentials-file"
        except OSError:
            continue
    return "unknown"


def node_available() -> Optional[str]:
    found = shutil.which("node")
    if not found:
        return None
    code, out, _ = run_capture([found, "--version"], timeout=10)
    return out.strip() if code == 0 else None


def npm_available() -> Optional[str]:
    return shutil.which("npm.cmd" if _WINDOWS else "npm") or shutil.which("npm")


def doctor(info: CliInfo, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    if not info.found:
        return 127, "", "Claude Code CLI not found"
    return run_capture([info.path, "doctor"], cwd=cwd, timeout=60)


def open_terminal(cwd: str) -> bool:
    """Open the OS terminal/file manager at `cwd` (used by escape hatches)."""
    try:
        if _WINDOWS:
            os.startfile(cwd)  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", cwd])
            return True
        subprocess.Popen(["xdg-open", cwd])
        return True
    except Exception as exc:  # pragma: no cover - platform specific
        log.warning("Could not open %s: %s", cwd, exc)
        return False


def environment_report(info: CliInfo) -> Dict[str, str]:
    report = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cli_path": info.path or "-",
        "cli_version": info.version or "-",
        "node": node_available() or "-",
        "npm": npm_available() or "-",
        "auth_hint": info.extra.get("auth_hint", "unknown"),
    }
    for key in ("ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "HTTP_PROXY", "HTTPS_PROXY", "CLAUDE_CONFIG_DIR"):
        value = os.environ.get(key)
        if value:
            report[key] = value
    return report
