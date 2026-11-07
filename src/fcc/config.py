"""Persistent application state: settings, trusted folders, projects, sessions."""

from __future__ import annotations

import fnmatch
import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from fcc import paths
from fcc.logging_setup import get_logger

log = get_logger("config")

SCHEMA_VERSION = 3
PERMISSION_MODES = ["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk", "auto"]
THEMES = ["light", "dark", "system"]
ACCENTS = ["coral", "clay", "ember", "olive", "slate"]


def _now() -> float:
    return time.time()


@dataclass
class PermissionRule:
    """A remembered allow/deny decision, matched before Claude Code asks."""

    tool: str
    pattern: str = "*"
    behavior: str = "allow"  # allow | deny
    scope: str = "project"  # global | project | session
    project: str = ""
    label: str = ""
    created_at: float = field(default_factory=_now)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def matches(self, tool_name: str, subject: str, project_path: str = "") -> bool:
        if self.tool and self.tool != "*" and self.tool.lower() != (tool_name or "").lower():
            return False
        if self.scope == "project" and project_path and self.project and _norm(self.project) != _norm(project_path):
            return False
        pattern = self.pattern or "*"
        if pattern == "*":
            return True
        subject = subject or ""
        if fnmatch.fnmatch(subject, pattern) or fnmatch.fnmatch(subject.lower(), pattern.lower()):
            return True
        # path-aware matching for file tools
        if "/" in pattern or "\\" in pattern:
            tail = pattern.rstrip("/*\\")
            if tail and (subject.startswith(tail) or _norm(subject).startswith(_norm(tail))):
                return True
        return False

    def display(self) -> str:
        if self.label:
            return self.label
        if self.pattern and self.pattern != "*":
            return f"{self.tool}({self.pattern})"
        return self.tool or "*"


@dataclass
class SessionRecord:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    project_path: str = ""
    title: str = ""
    cli_session_id: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    model: str = ""
    message_count: int = 0
    total_cost_usd: float = 0.0
    transcript: str = ""

    @property
    def transcript_path(self) -> Path:
        if self.transcript:
            return Path(self.transcript)
        return paths.sessions_dir() / f"{self.id}.jsonl"


@dataclass
class ProjectRecord:
    path: str
    name: str = ""
    trusted: bool = False
    trusted_at: float = 0.0
    added_at: float = field(default_factory=_now)
    last_opened: float = 0.0
    permission_mode: str = ""
    model: str = ""
    active_session: str = ""
    session_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.path = _norm(self.path)
        if not self.name:
            self.name = Path(self.path).name or self.path


def _norm(p: str) -> str:
    try:
        return str(Path(os.path.expanduser(p)).resolve())
    except OSError:
        return p


@dataclass
class AppConfig:
    schema_version: int = SCHEMA_VERSION

    # appearance
    theme: str = "system"
    accent: str = "coral"
    font_size: int = 14
    language: str = ""  # "" = follow system
    animations: bool = True
    density: float = 1.0

    # behaviour
    streaming: bool = True
    notifications: bool = True
    sound: bool = False
    autostart_session: bool = True
    confirm_stop: bool = False
    show_raw_events: bool = False
    auto_scroll: bool = True

    # claude code
    cli_path: str = ""
    model: str = ""
    effort: str = ""
    permission_mode: str = "default"
    allowed_tools: List[str] = field(default_factory=list)
    disallowed_tools: List[str] = field(default_factory=list)
    extra_args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    add_dirs: List[str] = field(default_factory=list)
    append_system_prompt: str = ""
    permission_timeout_sec: int = 0  # 0 = wait for the user
    startup_timeout_sec: int = 90

    # demo
    demo_mode: bool = False
    gateway_mode: str = "auto"      # auto | fcc | off  (FCC = free-claude-code server)
    gateway_url: str = ""
    gateway_token: str = ""

    # storage
    projects: List[ProjectRecord] = field(default_factory=list)
    sessions: List[SessionRecord] = field(default_factory=list)
    rules: List[PermissionRule] = field(default_factory=list)
    last_project: str = ""
    window_geometry: str = ""
    window_state: str = ""
    sidebar_width: int = 288
    sidebar_collapsed: bool = False

    # build
    build_onefile: bool = False
    build_installer: bool = True
    build_output: str = ""

    # ------------------------------------------------------------------ #
    def project(self, path: str) -> Optional[ProjectRecord]:
        target = _norm(path)
        for record in self.projects:
            if _norm(record.path) == target:
                return record
        return None

    def upsert_project(self, path: str, **updates) -> ProjectRecord:
        record = self.project(path)
        if record is None:
            record = ProjectRecord(path=path)
            self.projects.insert(0, record)
        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)
        record.path = _norm(record.path)
        record.name = record.name or Path(record.path).name
        return record

    def is_trusted(self, path: str) -> bool:
        record = self.project(path)
        return bool(record and record.trusted)

    def set_trusted(self, path: str, trusted: bool) -> ProjectRecord:
        record = self.upsert_project(path)
        record.trusted = trusted
        record.trusted_at = _now() if trusted else 0.0
        return record

    def remove_project(self, path: str) -> None:
        record = self.project(path)
        if not record:
            return
        self.projects.remove(record)
        self.sessions = [s for s in self.sessions if _norm(s.project_path) != _norm(record.path)]
        if _norm(self.last_project) == _norm(record.path):
            self.last_project = ""

    def sessions_for(self, path: str) -> List[SessionRecord]:
        target = _norm(path)
        items = [s for s in self.sessions if _norm(s.project_path) == target]
        items.sort(key=lambda s: s.updated_at, reverse=True)
        return items

    def session(self, session_id: str) -> Optional[SessionRecord]:
        for item in self.sessions:
            if item.id == session_id:
                return item
        return None

    def create_session(self, project_path: str, title: str = "", model: str = "") -> SessionRecord:
        record = SessionRecord(project_path=_norm(project_path), title=title, model=model or self.model)
        self.sessions.append(record)
        project = self.upsert_project(project_path)
        project.session_ids.insert(0, record.id)
        project.active_session = record.id
        project.last_opened = _now()
        self.last_project = project.path
        return record

    def delete_session(self, session_id: str) -> None:
        record = self.session(session_id)
        if not record:
            return
        self.sessions.remove(record)
        try:
            record.transcript_path.unlink(missing_ok=True)
        except OSError:
            pass
        for project in self.projects:
            if session_id in project.session_ids:
                project.session_ids.remove(session_id)
            if project.active_session == session_id:
                project.active_session = project.session_ids[0] if project.session_ids else ""

    def rename_session(self, session_id: str, title: str) -> None:
        record = self.session(session_id)
        if record:
            record.title = title
            record.updated_at = _now()

    # ---- permission rules ---- #
    def rules_for(self, project_path: str = "") -> List[PermissionRule]:
        target = _norm(project_path) if project_path else ""
        out = []
        for rule in self.rules:
            if rule.scope == "global":
                out.append(rule)
            elif rule.scope == "project" and target and _norm(rule.project) == target:
                out.append(rule)
        return out

    def find_rule(self, tool_name: str, subject: str, project_path: str = "") -> Optional[PermissionRule]:
        # deny wins over allow, most specific pattern wins
        candidates = [r for r in self.rules_for(project_path) if r.matches(tool_name, subject, project_path)]
        if not candidates:
            return None
        candidates.sort(key=lambda r: (r.behavior != "deny", -(len(r.pattern or "*"))))
        return candidates[0]

    def add_rule(self, rule: PermissionRule) -> PermissionRule:
        rule.id = rule.id or uuid.uuid4().hex[:12]
        if rule.scope == "project" and rule.project:
            rule.project = _norm(rule.project)
        for existing in self.rules:
            if (
                existing.tool == rule.tool
                and existing.pattern == rule.pattern
                and existing.behavior == rule.behavior
                and existing.scope == rule.scope
                and _norm(existing.project or "") == _norm(rule.project or "")
            ):
                return existing
        self.rules.append(rule)
        return rule

    def remove_rule(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.id != rule_id]

    def clear_session_rules(self) -> None:
        self.rules = [r for r in self.rules if r.scope != "session"]


# --------------------------------------------------------------------------- #
# load / save
# --------------------------------------------------------------------------- #

_lock = threading.RLock()
_current: Optional[AppConfig] = None


def _coerce(data: dict) -> AppConfig:
    config = AppConfig()
    known = {f for f in config.__dataclass_fields__}  # type: ignore[attr-defined]
    for key, value in data.items():
        if key not in known or value is None:
            continue
        current = getattr(config, key)
        try:
            if key == "projects":
                setattr(config, key, [ProjectRecord(**_pick(ProjectRecord, item)) for item in value if isinstance(item, dict)])
            elif key == "sessions":
                setattr(config, key, [SessionRecord(**_pick(SessionRecord, item)) for item in value if isinstance(item, dict)])
            elif key == "rules":
                setattr(config, key, [PermissionRule(**_pick(PermissionRule, item)) for item in value if isinstance(item, dict)])
            elif isinstance(current, bool):
                setattr(config, key, bool(value))
            elif isinstance(current, int) and not isinstance(current, bool):
                setattr(config, key, int(value))
            elif isinstance(current, float):
                setattr(config, key, float(value))
            elif isinstance(current, str):
                setattr(config, key, str(value))
            elif isinstance(current, list) and isinstance(value, list):
                setattr(config, key, list(value))
            elif isinstance(current, dict) and isinstance(value, dict):
                setattr(config, key, dict(value))
        except (TypeError, ValueError) as exc:
            log.warning("Ignoring invalid config value for %s: %s", key, exc)
    if config.theme not in THEMES:
        config.theme = "system"
    if config.accent not in ACCENTS:
        config.accent = "coral"
    if config.permission_mode not in PERMISSION_MODES:
        config.permission_mode = "default"
    if config.gateway_mode not in ("auto", "fcc", "off"):
        config.gateway_mode = "auto"
    for project in config.projects:
        if project.permission_mode and project.permission_mode not in PERMISSION_MODES:
            project.permission_mode = ""
    config.font_size = max(11, min(22, int(config.font_size or 14)))
    config.projects.sort(key=lambda p: p.last_opened or p.added_at, reverse=True)
    return config


def _pick(cls, item: dict) -> dict:
    fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
    return {k: v for k, v in item.items() if k in fields}


def load(path: Optional[Path] = None) -> AppConfig:
    global _current
    with _lock:
        if _current is not None and path is None:
            return _current
        file = path or paths.config_file()
        data: dict = {}
        try:
            if file.exists():
                data = json.loads(file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read config %s: %s", file, exc)
            try:
                file.replace(file.with_suffix(".broken.json"))
            except OSError:
                pass
            data = {}
        version = int(data.get("schema_version", 0) or 0)
        if version and version != SCHEMA_VERSION:
            log.info("Migrating config schema %s -> %s", version, SCHEMA_VERSION)
        config = _coerce(data)
        config.schema_version = SCHEMA_VERSION
        if path is None:
            _current = config
        return config


def save(config: Optional[AppConfig] = None, path: Optional[Path] = None) -> bool:
    config = config or _current
    if config is None:
        return False
    file = path or paths.config_file()
    with _lock:
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(asdict(config), indent=2, ensure_ascii=False, default=str)
            tmp = file.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, file)
            return True
        except OSError as exc:
            log.error("Could not save config to %s: %s", file, exc)
            return False


def get() -> AppConfig:
    return load()


def reset() -> AppConfig:
    global _current
    with _lock:
        _current = AppConfig()
        save(_current)
        return _current
