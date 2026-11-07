"""Runs the Claude Code CLI as a long-lived streaming subprocess."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from fcc import paths
from fcc.claude import discovery, protocol
from fcc.claude.capabilities import (Capabilities, LaunchOptions, build_command,
                                     detect, flags_rejected_by_cli)
from fcc.claude.control import ControlChannel, PermissionAnswer, PermissionAsk
from fcc.logging_setup import get_logger

log = get_logger("session")

IDLE = "idle"
STARTING = "starting"
READY = "ready"
BUSY = "busy"
WAITING = "waiting_permission"
STOPPING = "stopping"
ERROR = "error"
ENDED = "ended"


@dataclass
class TurnStats:
    turns: int = 0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    context_window: int = 0
    started_at: float = field(default_factory=time.time)
    last_result_at: float = 0.0

    def add(self, summary: Dict[str, Any]) -> None:
        self.turns += 1
        self.cost_usd += float(summary.get("cost_usd") or 0.0)
        self.tokens_in += int(summary.get("tokens_in") or 0)
        self.tokens_out += int(summary.get("tokens_out") or 0)
        self.duration_ms += int(summary.get("duration_ms") or 0)
        self.context_window = int(summary.get("context_window") or self.context_window)
        self.last_result_at = time.time()


class BaseBackend(QObject):
    """Interface shared by the real CLI backend and the demo simulator."""

    state_changed = Signal(str)
    event = Signal(object)                 # protocol.UiEvent
    turn_finished = Signal(dict)           # summarised result payload
    error_occurred = Signal(str, str)      # code, human message
    log_line = Signal(str, str)            # channel, text
    stats_changed = Signal(object)         # TurnStats
    permission_requested = Signal(object)  # PermissionAsk
    permission_resolved = Signal(object, object)
    backend_notice = Signal(str, str)      # level, message

    kind = "base"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.state = IDLE
        self.project_path = ""
        self.session_id = ""
        self.model = ""
        self.cli_version = ""
        self.permission_mode = "default"
        self.slash_commands: List[str] = []
        self.tools: List[str] = []
        self.stats = TurnStats()
        self.busy = False

    # -- api ------------------------------------------------------------- #
    def start(self, project_path: str, resume_session_id: str = "", new_session_id: str = "") -> None:
        raise NotImplementedError

    def send(self, text: str, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        raise NotImplementedError

    def interrupt(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def set_permission_mode(self, mode: str) -> None:
        self.permission_mode = mode

    def is_running(self) -> bool:
        return self.state in (STARTING, READY, BUSY, WAITING)

    # -- helpers --------------------------------------------------------- #
    def _set_state(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self.busy = state in (BUSY, WAITING, STARTING)
        log.debug("state -> %s", state)
        self.state_changed.emit(state)

    def _emit(self, ui_event: protocol.UiEvent) -> None:
        if ui_event.kind == protocol.TURN_DONE:
            self.stats.add(protocol.summarize_result(ui_event.payload))
            self.stats_changed.emit(self.stats)
            self.turn_finished.emit(ui_event.payload)
        self.event.emit(ui_event)


class ClaudeBackend(BaseBackend):
    """Owns one `claude -p --input-format stream-json` process per conversation."""

    kind = "claude"

    def __init__(self, config_getter, permission_broker=None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config_getter = config_getter
        self.broker = permission_broker
        self._proc: Optional[subprocess.Popen] = None
        self._write_lock = threading.RLock()
        self._threads: List[threading.Thread] = []
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fcc-control")
        self._stderr_tail: List[str] = []
        self._started_at = 0.0
        self._retries = 0
        self._disabled_flags: List[str] = []
        self._launch: Optional[LaunchOptions] = None
        self.caps: Capabilities = Capabilities()
        self.cli_info = discovery.CliInfo()
        self.interpreter = protocol.StreamInterpreter()
        self.control: Optional[ControlChannel] = None
        self._transcript_path: Optional[Path] = None
        self._transcript_lock = threading.Lock()
        self._stop_requested = False
        self._last_user_text = ""

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def start(self, project_path: str, resume_session_id: str = "", new_session_id: str = "") -> None:
        config = self._config_getter()
        self.project_path = str(project_path)
        self._stop_requested = False
        self._set_state(STARTING)
        self._emit(protocol.UiEvent(protocol.NOTICE, {
            "notice": "starting", "title": "Starting Claude Code",
            "message": f"Working folder: {self.project_path}"}))

        self.cli_info = discovery.probe(config.cli_path, cwd=self.project_path, include_help=True)
        if not self.cli_info.found:
            self._set_state(ERROR)
            self.error_occurred.emit("cli_not_found", "Claude Code CLI not found")
            return
        self.caps = detect(self.cli_info.path, self.cli_info.version, self.cli_info.help_text)
        self.cli_version = self.cli_info.version

        self.session_id = resume_session_id or new_session_id or str(uuid.uuid4())
        self._launch = LaunchOptions(
            project_path=self.project_path,
            resume_session_id=resume_session_id,
            new_session_id="" if resume_session_id else self.session_id,
            model=config.model,
            effort=config.effort,
            permission_mode=config.permission_mode,
            allowed_tools=list(config.allowed_tools),
            disallowed_tools=list(config.disallowed_tools),
            add_dirs=list(config.add_dirs),
            append_system_prompt=config.append_system_prompt,
            session_name="",
            streaming=config.streaming,
            host_permissions=self.broker is not None,
            persist_session=True,
            extra_args=list(config.extra_args),
            disabled_flags=list(self._disabled_flags),
        )
        self.permission_mode = self._launch.permission_mode
        self._spawn(self._launch)

    def _spawn(self, opts: LaunchOptions) -> bool:
        argv = build_command(self.cli_info.path, self.caps, opts)
        env = os.environ.copy()
        config = self._config_getter()
        from fcc.claude import gateway

        gw = gateway.detect(config)
        self.gateway = gw if gw.detected else None
        if gw.detected:
            gateway.apply_to_env(env, gw)
            log.info("FCC gateway active: %s", gw.base_url)
        elif getattr(config, "gateway_mode", "auto") == "fcc":
            self.backend_notice.emit("warn",
                                     "FCC gateway forced in settings but no server responded.")
        env.update({k: str(v) for k, v in (config.env or {}).items() if v is not None})
        env["NO_COLOR"] = "1"
        env["CLAUDE_CODE_ENTRYPOINT"] = env.get("CLAUDE_CODE_ENTRYPOINT", "fcc-studio")
        if not config.streaming:
            env.pop("CLAUDE_CODE_STREAM", None)

        log.info("spawn: %s", " ".join(shlex.quote(a) for a in discovery.wrap_command(argv[0], argv[1:])))
        self.log_line.emit("cli", " ".join(argv))
        try:
            self._proc = subprocess.Popen(
                discovery.wrap_command(argv[0], argv[1:]),
                cwd=self.project_path or os.getcwd(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=discovery.creation_flags(),
                startupinfo=discovery.startupinfo(),
            )
        except (OSError, ValueError) as exc:
            self._set_state(ERROR)
            self.error_occurred.emit("spawn_failed", f"{exc}")
            return False

        self._started_at = time.time()
        self._stderr_tail = []
        self.interpreter = protocol.StreamInterpreter()
        self.control = ControlChannel(
            writer=self._write_json,
            ask_permission=self._ask_permission,
            permission_timeout=float(config.permission_timeout_sec or 0),
        )
        self._open_transcript()
        self._handshake()

        for target, name, args in (
            (self._read_stdout, "reader", ()),
            (self._read_stderr, "stderr", ()),
            (self._watch_process, "watcher", ()),
        ):
            thread = threading.Thread(target=target, name=f"fcc-{name}", args=args, daemon=True)
            thread.start()
            self._threads.append(thread)
        return True

    def _handshake(self) -> None:
        """Tell the CLI we host the permission tool, and learn its commands."""
        if self.control is None:
            return
        request_id = f"fcc_init_{uuid.uuid4().hex[:8]}"
        payload = {
            "type": "control_request",
            "request_id": request_id,
            "request": {
                "subtype": "initialize",
                "hooks": None,
                "sdkMcpServers": [self.control.server_name],
            },
        }
        self._write_json(payload)

    def _open_transcript(self) -> None:
        try:
            paths.sessions_dir().mkdir(parents=True, exist_ok=True)
            self._transcript_path = paths.sessions_dir() / f"{self.session_id or uuid.uuid4().hex}.jsonl"
        except OSError as exc:
            log.warning("transcript disabled: %s", exc)
            self._transcript_path = None

    # ------------------------------------------------------------------ #
    # io
    # ------------------------------------------------------------------ #
    def _write_json(self, payload: Dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            log.debug("dropping write, process not running: %s", payload.get("type"))
            return
        line = json.dumps(payload, ensure_ascii=False)
        with self._write_lock:
            try:
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, ValueError, OSError) as exc:
                log.warning("write failed: %s", exc)
        self._record_raw({"direction": "out", "payload": payload})

    def _record_raw(self, item: Dict[str, Any]) -> None:
        if self._transcript_path is None:
            return
        try:
            with self._transcript_lock:
                with self._transcript_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"t": round(time.time(), 3), **item}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _read_stdout(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while True:
            try:
                line = proc.stdout.readline()
            except (ValueError, OSError):
                break
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            self._record_raw({"direction": "in", "line": line[:20000]})
            event = protocol.parse_line(line)
            if event is None:
                self.log_line.emit("stdout", line[:4000])
                continue
            self._dispatch(event)
        log.debug("stdout closed")

    def _dispatch(self, event: Dict[str, Any]) -> None:
        kind = event.get("type")
        if kind in ("control_request", "control_response", "control_error", "control_cancel_request"):
            if self.control is None:
                return
            if kind == "control_request":
                # Never block the reader: permission prompts can take minutes.
                self._executor.submit(self._run_control, event)
            else:
                for ui_event in self.control.handle(event):
                    self._emit(ui_event)
            return
        for ui_event in self.interpreter.feed(event):
            self._on_ui_event(ui_event)

    def _run_control(self, event: Dict[str, Any]) -> None:
        try:
            for ui_event in (self.control.handle(event) if self.control else []):
                self._on_ui_event(ui_event)
        except Exception as exc:  # pragma: no cover
            log.exception("control handling failed: %s", exc)

    def _on_ui_event(self, ui_event: protocol.UiEvent) -> None:
        kind = ui_event.kind
        if kind == protocol.SESSION_INIT:
            self.session_id = ui_event.get("session_id") or self.session_id
            self.model = ui_event.get("model") or self.model
            self.cli_version = ui_event.get("cli_version") or self.cli_version
            self.permission_mode = ui_event.get("permission_mode") or self.permission_mode
            self.tools = list(ui_event.get("tools") or [])
            self._set_state(READY)
        elif kind == protocol.TOOL_START and not ui_event.get("partial"):
            if self.state == READY:
                self._set_state(BUSY)
        elif kind == protocol.TEXT_DELTA or kind == protocol.THINKING_DELTA:
            if self.state in (READY, WAITING):
                self._set_state(BUSY)
        elif kind == protocol.TURN_DONE:
            self._set_state(READY)
        elif kind == protocol.ERROR:
            code = ui_event.get("code", "error")
            message = ui_event.get("message", "")
            self.error_occurred.emit(code, message)
            if code == "auth":
                self._set_state(ERROR)
        elif kind == protocol.PERMISSION_DENIED:
            self._set_state(BUSY)
        self._emit(ui_event)

    def _read_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        while True:
            try:
                line = proc.stderr.readline()
            except (ValueError, OSError):
                break
            if not line:
                break
            text = line.rstrip()
            if not text:
                continue
            self._stderr_tail.append(text)
            if len(self._stderr_tail) > 400:
                self._stderr_tail = self._stderr_tail[-400:]
            self.log_line.emit("stderr", text[:4000])
            log.debug("cli stderr: %s", text[:400])

    def _watch_process(self) -> None:
        proc = self._proc
        if proc is None:
            return
        code = proc.wait()
        elapsed = time.time() - self._started_at
        stderr_text = "\n".join(self._stderr_tail)
        log.info("claude exited with code %s after %.1fs", code, elapsed)
        self._record_raw({"direction": "exit", "code": code, "elapsed": round(elapsed, 2)})

        if self._stop_requested:
            self._set_state(ENDED)
            return

        rejected = flags_rejected_by_cli(stderr_text)
        if code != 0 and rejected and self._retries < 3 and self._launch is not None:
            self._retries += 1
            self._disabled_flags.extend(f for f in rejected if f not in self._disabled_flags)
            self.backend_notice.emit(
                "warn",
                "Claude Code rejected " + ", ".join(rejected) + " — retrying without them.",
            )
            self._launch.disabled_flags = list(self._disabled_flags)
            self._launch.resume_session_id = self.interpreter.session_id or self._launch.resume_session_id
            self._launch.new_session_id = "" if self._launch.resume_session_id else self._launch.new_session_id
            threading.Thread(target=self._spawn, args=(self._launch,), name="fcc-respawn", daemon=True).start()
            return

        if code != 0 and elapsed < 20:
            self._set_state(ERROR)
            hint = stderr_text.strip().splitlines()[-1] if stderr_text.strip() else f"exit code {code}"
            if "not logged in" in stderr_text.lower() or "invalid api key" in stderr_text.lower():
                self.error_occurred.emit("auth", hint)
            else:
                self.error_occurred.emit("cli_exit", hint)
            return

        if self.state not in (ERROR,):
            self._set_state(ENDED)
        if code != 0:
            self.error_occurred.emit("cli_exit", stderr_text.strip()[-600:] or f"exit code {code}")

    # ------------------------------------------------------------------ #
    # sending
    # ------------------------------------------------------------------ #
    def send(self, text: str, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        if self._proc is None or self._proc.poll() is not None:
            self.error_occurred.emit("not_running", "Claude Code is not running. Start a session first.")
            return False
        content: List[Dict[str, Any]] = []
        if text.strip():
            content.append({"type": "text", "text": text})
        for item in attachments or []:
            if item.get("type") == "image" and item.get("source"):
                content.append({"type": "image", "source": item["source"]})
            elif item.get("type") == "text" and item.get("text"):
                content.append({"type": "text", "text": item["text"]})
        if not content:
            return False
        payload = {
            "type": "user",
            "message": {"role": "user", "content": content},
            "parent_tool_use_id": None,
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        self._last_user_text = text
        self._set_state(BUSY)
        self._write_json(payload)
        return True

    def send_raw(self, payload: Dict[str, Any]) -> bool:
        if self._proc is None or self._proc.poll() is not None:
            return False
        self._write_json(payload)
        return True

    def slash_command(self, command: str, args: str = "") -> bool:
        """Slash commands travel as plain user text in stream-json mode."""
        text = command if not args else f"{command} {args}"
        return self.send(text)

    def interrupt(self) -> None:
        if self.control is not None and self._proc is not None and self._proc.poll() is None:
            self.control.interrupt()
            self.backend_notice.emit("info", "Interrupt requested")
            if self.broker is not None:
                self.broker.cancel_all("Interrupted by user")
        self._set_state(READY)

    def set_permission_mode(self, mode: str) -> None:
        super().set_permission_mode(mode)
        if self.control is not None and self.is_running():
            self.control.set_permission_mode(mode)

    def set_model(self, model: str) -> None:
        self.model = model
        if self.control is not None and self.is_running():
            self.control.set_model(model)

    def stop(self) -> None:
        self._stop_requested = True
        self._set_state(STOPPING)
        if self.broker is not None:
            self.broker.cancel_all("Session stopped")
        proc = self._proc
        if proc is None:
            self._set_state(ENDED)
            return
        try:
            if self.control is not None and proc.poll() is None:
                self.control.end_session()
        except Exception:  # pragma: no cover
            pass
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            log.info("terminating claude")
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                log.warning("killing claude")
                proc.kill()
        self._set_state(ENDED)

    def shutdown(self) -> None:
        self.stop()
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - Python < 3.9
            self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------ #
    # permissions
    # ------------------------------------------------------------------ #
    def _ask_permission(self, ask: PermissionAsk) -> PermissionAnswer:
        if self.broker is None:
            return PermissionAnswer(behavior="deny", message="No permission handler configured.")
        self._set_state(WAITING)
        self.permission_requested.emit(ask)
        answer = self.broker.decide(ask)
        if self.state == WAITING:
            self._set_state(BUSY)
        self.permission_resolved.emit(ask, answer)
        return answer

    # ------------------------------------------------------------------ #
    def diagnostics(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "cli": self.cli_info.path,
            "cli_version": self.cli_info.version,
            "session_id": self.session_id,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "disabled_flags": self._disabled_flags,
            "retries": self._retries,
            "control": self.control.stats() if self.control else {},
            "process_alive": bool(self._proc and self._proc.poll() is None),
            "pid": self._proc.pid if self._proc else None,
            "stderr_tail": self._stderr_tail[-20:],
        }


class DemoBackend(BaseBackend):
    """Simulates a Claude Code session so the UI can be explored offline."""

    kind = "demo"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.cli_version = "demo"
        self.model = "claude-sonnet-4-5 (demo)"
        self._timer = None
        self._script: List[Any] = []
        self._broker = None

    def set_broker(self, broker) -> None:
        self._broker = broker

    def start(self, project_path: str, resume_session_id: str = "", new_session_id: str = "") -> None:
        from PySide6.QtCore import QTimer

        self.project_path = project_path
        self.session_id = resume_session_id or new_session_id or str(uuid.uuid4())
        self._set_state(STARTING)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._ready)
        self._timer.start(500)

    def _ready(self) -> None:
        self._emit(protocol.UiEvent(protocol.SESSION_INIT, {
            "session_id": self.session_id, "cwd": self.project_path, "model": self.model,
            "cli_version": "2.1.0-demo", "permission_mode": "default", "api_key_source": "demo",
            "tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "Task", "TodoWrite"],
            "mcp_servers": [], "slash_commands": ["help", "clear", "compact", "model", "init"],
            "agents": ["general-purpose"], "skills": [], "capabilities": ["demo"], "output_style": "default",
        }))
        self._set_state(READY)

    def send(self, text: str, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        from PySide6.QtCore import QTimer

        if not text.strip():
            return False
        self._set_state(BUSY)
        from fcc.claude.demo_script import build_script

        self._script = build_script(text, self.project_path)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._timer.start(220)
        return True

    def _step(self) -> None:
        from PySide6.QtCore import QTimer

        if not self._script:
            self._set_state(READY)
            return
        item = self._script.pop(0)
        delay = 120
        if callable(item):
            delay = item(self)
        elif isinstance(item, tuple):
            kind, payload, delay = item[0], item[1], (item[2] if len(item) > 2 else 140)
            self._emit(protocol.UiEvent(kind, payload))
        if self._script:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._step)
            self._timer.start(int(delay))
        else:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._step)
            self._timer.start(int(delay))

    def interrupt(self) -> None:
        self._script = []
        self._set_state(READY)

    def stop(self) -> None:
        self._script = []
        self._set_state(ENDED)

    def ask_demo_permission(self, ask: PermissionAsk) -> None:
        """Used by the demo script to exercise the real permission UI."""
        self._set_state(WAITING)
        self.permission_requested.emit(ask)
        if self._broker is None:
            return

        def worker() -> None:
            answer = self._broker.decide(ask)
            self.permission_resolved.emit(ask, answer)

        threading.Thread(target=worker, name="fcc-demo-perm", daemon=True).start()
