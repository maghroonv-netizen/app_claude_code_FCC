"""Permission policy: remembered rules first, then a real prompt in the GUI."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from fcc.claude.control import PermissionAnswer, PermissionAsk
from fcc.config import AppConfig, PermissionRule
from fcc.logging_setup import get_logger

log = get_logger("permissions")

SCOPE_LABELS = {
    "session": "perm.scope_session",
    "project": "perm.scope_project",
    "global": "perm.scope_global",
}


def relative_to(path: str, root: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return path
    rel = rel.replace("\\", "/")
    return rel if not rel.startswith("..") else path.replace("\\", "/")


def bash_rule_pattern(command: str) -> str:
    """`git status --short` -> `git *`; `ls` -> `ls`."""
    command = (command or "").strip()
    if not command:
        return "*"
    first_line = command.splitlines()[0].strip()
    tokens = first_line.split()
    if not tokens:
        return "*"
    head = tokens[0].split("/")[-1].split("\\")[-1]
    if len(tokens) == 1:
        return head
    if len(tokens) >= 2 and not tokens[1].startswith("-"):
        return f"{head} {tokens[1]}*"
    return f"{head} *"


def url_rule_pattern(url: str) -> str:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).netloc
    except ValueError:
        host = ""
    return f"domain:{host}" if host else "*"


def rule_options(ask: PermissionAsk, project_path: str = "") -> List[Tuple[str, PermissionRule]]:
    """The 'always allow' choices offered for one ask, most specific first."""
    tool = ask.tool_name or "*"
    subject = ask.subject or ""
    lower = tool.lower()
    options: List[Tuple[str, PermissionRule]] = []

    if lower in ("bash", "shell", "powershell"):
        pattern = bash_rule_pattern(subject)
        options.append((f"Always allow `{pattern}`", PermissionRule(tool=tool, pattern=pattern, behavior="allow")))
        options.append((f"Always allow every {tool} command", PermissionRule(tool=tool, pattern="*", behavior="allow")))
    elif lower in ("read", "write", "edit", "multiedit", "notebookedit", "view", "glob", "grep"):
        rel = relative_to(subject, project_path) if subject and project_path else subject
        if rel and rel != "*":
            options.append((f"Always allow {tool} on `{Path(rel).name}`",
                            PermissionRule(tool=tool, pattern=rel, behavior="allow")))
            parent = str(Path(rel).parent).replace("\\", "/")
            if parent and parent not in (".", "/"):
                options.append((f"Always allow {tool} inside `{parent}/`",
                                PermissionRule(tool=tool, pattern=f"{parent}/**", behavior="allow")))
        options.append((f"Always allow {tool}", PermissionRule(tool=tool, pattern="*", behavior="allow")))
    elif lower in ("webfetch",):
        pattern = url_rule_pattern(subject)
        options.append((f"Always allow {pattern}", PermissionRule(tool=tool, pattern=pattern, behavior="allow")))
        options.append(("Always allow WebFetch", PermissionRule(tool=tool, pattern="*", behavior="allow")))
    elif lower in ("websearch",):
        options.append(("Always allow WebSearch", PermissionRule(tool=tool, pattern="*", behavior="allow")))
    else:
        options.append((f"Always allow {tool}", PermissionRule(tool=tool, pattern="*", behavior="allow")))
        if subject and subject != tool.lower():
            options.append((f"Always allow {tool}({subject[:40]})",
                            PermissionRule(tool=tool, pattern=subject, behavior="allow")))
    return options


class PermissionBroker(QObject):
    """Bridges the CLI's blocking permission call to the (non-blocking) GUI."""

    ask_user = Signal(object)          # PermissionAsk
    decided = Signal(object, object)   # PermissionAsk, PermissionAnswer
    rule_added = Signal(object)        # PermissionRule
    auto_decided = Signal(object, object, str)  # ask, answer, rule description

    def __init__(self, config_getter: Callable[[], AppConfig], project_getter: Callable[[], str] = lambda: "",
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config_getter
        self._project = project_getter
        self._waiters: Dict[str, Tuple[PermissionAsk, PermissionAnswer, threading.Event]] = {}
        self._lock = threading.RLock()
        self.history: List[Dict[str, Any]] = []
        self.paused = False

    # ------------------------------------------------------------------ #
    def decide(self, ask: PermissionAsk) -> PermissionAnswer:
        """Called on the CLI reader thread; blocks until the user answers."""
        config = self._config()
        project_path = self._project()
        rule = config.find_rule(ask.tool_name, ask.subject, project_path)
        if rule is not None and not self.paused:
            answer = PermissionAnswer(
                behavior=rule.behavior,
                updated_input=ask.tool_input if rule.behavior == "allow" else None,
                message="" if rule.behavior == "allow" else f"Denied by saved rule: {rule.display()}",
                remember="",
            )
            self._record(ask, answer, rule=rule)
            self.auto_decided.emit(ask, answer, rule.display())
            return answer

        mode = (config.permission_mode or "default").lower()
        if mode == "bypasspermissions":
            answer = PermissionAnswer(behavior="allow", updated_input=ask.tool_input,
                                      message="", remember="")
            self._record(ask, answer, auto="mode:bypassPermissions")
            self.auto_decided.emit(ask, answer, "perm.mode.bypassPermissions")
            return answer

        event = threading.Event()
        answer = PermissionAnswer(behavior="deny", message="Cancelled.", timed_out=True)
        with self._lock:
            self._waiters[ask.id] = (ask, answer, event)
        self.ask_user.emit(ask)

        timeout = float(config.permission_timeout_sec or 0)
        deadline = time.time() + timeout if timeout > 0 else None
        while not event.wait(0.25):
            with self._lock:
                if ask.id not in self._waiters:
                    break
            if deadline is not None and time.time() > deadline:
                with self._lock:
                    entry = self._waiters.pop(ask.id, None)
                if entry:
                    entry[1].behavior = "deny"
                    entry[1].message = f"No answer within {int(timeout)}s."
                    entry[1].timed_out = True
                    entry[2].set()
                break
        with self._lock:
            entry = self._waiters.pop(ask.id, None)
        final = entry[1] if entry else answer
        self._record(ask, final)
        self.decided.emit(ask, final)
        return final

    def resolve(self, ask_id: str, answer: PermissionAnswer) -> bool:
        with self._lock:
            entry = self._waiters.get(ask_id)
            if not entry:
                return False
            ask, stored, event = entry
            stored.behavior = answer.behavior
            stored.updated_input = answer.updated_input if answer.behavior == "allow" else ask.tool_input
            stored.message = answer.message
            stored.remember = answer.remember
            stored.remember_behavior = answer.remember_behavior or answer.behavior
            stored.timed_out = False
            event.set()
            return True

    def cancel_all(self, reason: str = "Session stopped") -> int:
        with self._lock:
            entries = list(self._waiters.items())
            self._waiters.clear()
        for _, (ask, answer, event) in entries:
            answer.behavior = "deny"
            answer.message = reason
            answer.timed_out = True
            event.set()
        return len(entries)

    def pending(self) -> List[PermissionAsk]:
        with self._lock:
            return [entry[0] for entry in self._waiters.values()]

    # ------------------------------------------------------------------ #
    def remember(self, ask: PermissionAsk, behavior: str, scope: str, pattern: Optional[str] = None) -> Optional[PermissionRule]:
        if scope not in SCOPE_LABELS:
            return None
        config = self._config()
        project_path = self._project()
        if pattern is None:
            options = rule_options(ask, project_path)
            pattern = options[0][1].pattern if options else "*"
        rule = PermissionRule(
            tool=ask.tool_name or "*",
            pattern=pattern or "*",
            behavior=behavior,
            scope=scope,
            project=project_path if scope == "project" else "",
            label=f"{behavior.title()} {ask.tool_name}({pattern})" if pattern and pattern != "*" else f"{behavior.title()} {ask.tool_name}",
        )
        stored = config.add_rule(rule)
        self.rule_added.emit(stored)
        return stored

    def _record(self, ask: PermissionAsk, answer: PermissionAnswer,
                rule: Optional[PermissionRule] = None, auto: str = "") -> None:
        self.history.append({
            "at": time.time(),
            "tool": ask.tool_name,
            "subject": ask.subject,
            "behavior": answer.behavior,
            "rule": rule.display() if rule else "",
            "auto": auto,
            "remember": answer.remember,
        })
        if len(self.history) > 500:
            self.history = self.history[-500:]
