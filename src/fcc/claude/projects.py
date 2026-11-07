"""Project folder helpers: facts for the header, and @-mention file lookup."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from fcc.claude import discovery

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".nuxt", ".output", ".cache",
    "target", ".gradle", ".idea", ".vscode", "coverage", ".turbo", ".parcel-cache", "site-packages",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".dylib", ".exe", ".lock", ".png",
                 ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".mp4", ".woff", ".woff2"}
TEXT_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt", ".html", ".css", ".scss", ".yml",
    ".yaml", ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1", ".sql", ".rs", ".go", ".java", ".kt",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".lua", ".r", ".dart", ".vue",
    ".xml", ".svg", ".env", ".gitignore", ".dockerfile", ".ipynb",
}


@dataclass
class ProjectFacts:
    path: str
    name: str
    is_git: bool = False
    branch: str = ""
    dirty: Optional[bool] = None
    file_count: int = 0
    languages: Dict[str, int] = None  # type: ignore[assignment]
    has_claude_md: bool = False
    size_mb: float = 0.0

    def __post_init__(self):
        if self.languages is None:
            self.languages = {}


def git_output(path: str, *args: str) -> str:
    if sys.platform == "win32" and not discovery.node_available():
        pass
    try:
        proc = subprocess.run(
            ["git", *args], cwd=path, capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
            creationflags=discovery.creation_flags(), startupinfo=discovery.startupinfo(),
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def inspect(path: str, deep: bool = False) -> ProjectFacts:
    root = Path(path)
    facts = ProjectFacts(path=str(root), name=root.name or str(root))
    facts.is_git = (root / ".git").exists()
    if facts.is_git:
        facts.branch = git_output(str(root), "rev-parse", "--abbrev-ref", "HEAD") or ""
        if deep:
            status = git_output(str(root), "status", "--porcelain")
            facts.dirty = bool(status)
    facts.has_claude_md = (root / "CLAUDE.md").exists()

    limit = 6000 if deep else 1500
    count = 0
    langs: Dict[str, int] = {}
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for filename in filenames:
                count += 1
                suffix = Path(filename).suffix.lower()
                if suffix in TEXT_SUFFIXES:
                    langs[suffix.lstrip(".")] = langs.get(suffix.lstrip("."), 0) + 1
                if deep and count < 800:
                    try:
                        total += (Path(dirpath) / filename).stat().st_size
                    except OSError:
                        pass
                if count >= limit:
                    break
            if count >= limit:
                break
    except OSError:
        pass
    facts.file_count = count
    facts.languages = dict(sorted(langs.items(), key=lambda kv: -kv[1])[:6])
    facts.size_mb = round(total / (1024 * 1024), 1)
    return facts


def iter_files(path: str, limit: int = 4000):
    """Yield project-relative file paths, skipping noise."""
    root = Path(path)
    produced = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
            for filename in sorted(filenames):
                if Path(filename).suffix.lower() in SKIP_SUFFIXES:
                    continue
                full = Path(dirpath) / filename
                try:
                    yield str(full.relative_to(root)).replace("\\", "/")
                except ValueError:
                    yield str(full)
                produced += 1
                if produced >= limit:
                    return
    except OSError:
        return


def suggest_files(path: str, query: str, limit: int = 12) -> List[str]:
    """Fuzzy-ish file suggestions for @mentions in the composer."""
    query = (query or "").strip().lower().lstrip("@")
    files = list(iter_files(path, limit=4000))
    if not query:
        return files[:limit]
    scored = []
    for item in files:
        low = item.lower()
        base = low.rsplit("/", 1)[-1]
        if base == query or low == query:
            score = 1000
        elif base.startswith(query):
            score = 800 - len(item)
        elif query in base:
            score = 600 - len(item)
        elif low.startswith(query):
            score = 500 - len(item)
        elif query in low:
            score = 300 - len(item)
        elif _subsequence(query, low):
            score = 100 - len(item)
        else:
            continue
        scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [item for _, item in scored[:limit]]


def _subsequence(query: str, text: str) -> bool:
    iterator = iter(text)
    return all(any(ch == c for c in iterator) for ch in query)


def suggest_slash_commands(commands: List[str], query: str, limit: int = 12) -> List[str]:
    query = (query or "").strip().lower()
    if not query.startswith("/"):
        return []
    needle = query[1:]
    out = [c for c in commands if c.lower().startswith(needle)]
    out += [c for c in commands if needle and needle in c.lower() and c not in out]
    return [("/" + c if not c.startswith("/") else c) for c in out[:limit]]


def quick_folders(limit: int = 12) -> List[str]:
    """Likely project roots for the picker shortcut row."""
    home = Path.home()
    candidates = []
    for name in ("Projects", "projects", "Developer", "dev", "Code", "code", "src", "repos",
                 "workspace", "Workspace", "git", "Documents"):
        candidate = home / name
        if candidate.is_dir():
            candidates.append(str(candidate))
    try:
        for entry in sorted(home.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and str(entry) not in candidates:
                candidates.append(str(entry))
    except OSError:
        pass
    return candidates[:limit]


def folder_size_label(path: str) -> str:
    try:
        total = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
    except OSError:
        return ""
    return human_size(total)


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f}{unit}" if unit == "B" else f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}GB"
