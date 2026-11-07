"""The application window: sidebar, conversation, composer and all wiring."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QMainWindow, QMessageBox, QSplitter, QStackedWidget,
                               QVBoxLayout, QWidget)

from fcc import config as config_module
from fcc import icons, paths, theme
from fcc.claude import discovery, protocol, projects, transcript
from fcc.claude.capabilities import detect
from fcc.claude.control import PermissionAnswer, PermissionAsk
from fcc.claude.permissions import PermissionBroker
from fcc.claude.session import (BUSY, ClaudeBackend, DemoBackend, ENDED, ERROR, READY,
                                STARTING, WAITING)
from fcc.config import AppConfig, ProjectRecord, SessionRecord
from fcc.i18n import is_rtl, set_language, tr
from fcc.logging_setup import get_logger
from fcc.ui.common import button, hline, label, open_path, shortcut, tool_button
from fcc.ui.widgets.chat_view import ChatView
from fcc.ui.widgets.composer import Composer
from fcc.ui.widgets.panels import ActivityPanel, StatusBar, ToastStack
from fcc.ui.widgets.sidebar import Sidebar
from fcc.ui.widgets.tool_card import PermissionCard
from fcc.ui.widgets.welcome import WelcomeScreen
from fcc.version import APP_NAME, __version__

log = get_logger("window")

# Probe threads that are running (or finished but not yet collected).  A QThread
# whose Python wrapper is garbage-collected while its C++ thread still runs makes
# Qt call qFatal/abort — a silent hard crash on Windows.  Holding every probe
# here until it has finished makes that impossible.
_LIVE_PROBES = set()


def drain_probes(timeout_ms: int = 8000) -> None:
    """Wait for in-flight CLI probe threads so nothing is destroyed while running."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    for thread in list(_LIVE_PROBES):
        try:
            if thread.isRunning():
                thread.requestInterruption()
                remaining = max(50, int((deadline - time.monotonic()) * 1000))
                thread.wait(remaining)
        except RuntimeError:  # C++ object already gone
            pass
        _LIVE_PROBES.discard(thread)


class CliProbeThread(QThread):
    """Probing the CLI can take a second — never do it on the GUI thread."""

    finishedProbe = Signal(object, object, object)  # CliInfo, Capabilities, GatewayInfo

    def __init__(self, cli_path: str = "", cwd: str = "", parent=None) -> None:
        super().__init__(parent)
        self.cli_path = cli_path
        self.cwd = cwd or None

    def run(self) -> None:  # noqa: D102
        from fcc.claude import gateway

        info = discovery.probe(self.cli_path, cwd=self.cwd, include_help=True)
        if self.isInterruptionRequested():
            return
        caps = detect(info.path, info.version, info.help_text) if info.found else None
        if self.isInterruptionRequested():
            return
        gw = gateway.detect(None, use_cache=False)
        self.finishedProbe.emit(info, caps, gw)


class MainWindow(QMainWindow):
    notify = Signal(str, str)  # message, level (for tray notifications)

    def __init__(self, config: Optional[AppConfig] = None, demo: bool = False) -> None:
        super().__init__()
        self.config = config or config_module.load()
        set_language(self.config.language or discovery_system_language())
        self.palette = theme.with_font_size(
            theme.palette_for(self.config.theme, self.config.accent), int(self.config.font_size))
        self.font_size = int(self.config.font_size)
        self.cli_info = discovery.CliInfo()
        self.caps = None
        self.gateway_info = None
        self.backend: Optional[Any] = None
        self.current_project: Optional[ProjectRecord] = None
        self.current_session: Optional[SessionRecord] = None
        self._pending_asks: Dict[str, Any] = {}
        self._sent_texts: List[str] = []
        self._probe: Optional[CliProbeThread] = None
        self._turn_started_at = 0.0
        self._closing = False

        self.setWindowTitle(f"{APP_NAME} · {tr('app.tagline')}")
        self.setMinimumSize(1024, 660)
        self.resize(1360, 860)
        self.setWindowIcon(icons.app_logo_icon(self.palette.accent, 64))

        self.broker = PermissionBroker(lambda: self.config, lambda: self._project_path())
        self.broker.ask_user.connect(self._on_permission_ask)
        self.broker.rule_added.connect(self._on_rule_added)

        self._build_ui()
        self._restore_geometry()
        self._apply_layout_direction()
        self.apply_palette()
        self._connect_backend(self._make_backend(demo or self.config.demo_mode))
        self._load_projects()

        QTimer.singleShot(120, self._startup_probe)
        QTimer.singleShot(400, self._maybe_autostart)

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(0)
        self.splitter.setChildrenCollapsible(False)

        main = QWidget()
        main_box = QVBoxLayout(main)
        main_box.setContentsMargins(0, 0, 0, 0)
        main_box.setSpacing(0)
        main_box.addWidget(self._build_top_bar())

        self.stack = QStackedWidget()
        self.welcome = WelcomeScreen()
        self.chat = ChatView()
        self.chat.permissionDecided.connect(self._on_inline_permission)
        self.chat.retryRequested.connect(self._retry_last)
        self.chat.rawRequested.connect(self._show_raw)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.chat)
        main_box.addWidget(self.stack, 1)

        self.composer = Composer()
        self.composer.sendRequested.connect(self.send_message)
        self.composer.stopRequested.connect(self.stop_generation)
        self.composer.modeChangeRequested.connect(self.change_permission_mode)
        self.composer.modelChangeRequested.connect(self.change_model)
        self.composer.attachRequested.connect(self._attach_files)
        main_box.addWidget(self.composer)
        main_box.addWidget(self._build_status_bar())

        self.activity = ActivityPanel()
        self.activity.closed.connect(self.toggle_activity)
        self.activity.setVisible(False)

        self.splitter.addWidget(main)
        self.splitter.addWidget(self.activity)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        root.addWidget(self.splitter, 1)

        self.toasts = ToastStack(self)
        self.toasts.setGeometry(0, 0, 460, 400)

        self._wire_sidebar()
        self._wire_shortcuts()

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(58)
        box = QHBoxLayout(bar)
        box.setContentsMargins(18, 8, 18, 8)
        box.setSpacing(10)

        self.project_icon = QLabel()
        self.project_icon.setPixmap(icons.pixmap("folder", self.palette.text_muted, 17))
        box.addWidget(self.project_icon)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(0)
        self.project_name_label = label(tr("welcome.open_folder"), bold=True)
        title_column.addWidget(self.project_name_label)
        self.project_path_label = label("", faint=True)
        title_column.addWidget(self.project_path_label)
        box.addLayout(title_column, 1)

        self.trust_button = button(tr("project.untrusted"), "lock", size=13)
        self.trust_button.setObjectName("Chip")
        self.trust_button.setCursor(Qt.PointingHandCursor)
        self.trust_button.clicked.connect(self._toggle_trust)
        box.addWidget(self.trust_button)

        self.session_title_label = label("", muted=True)
        box.addWidget(self.session_title_label)

        box.addWidget(_vsep())

        self.new_session_button = tool_button("plus", size=17, tooltip=tr("nav.new_session"),
                                              clicked=self.new_session)
        self.export_button = tool_button("download", size=16, tooltip=tr("chat.export"),
                                         clicked=self.export_conversation)
        self.activity_button = tool_button("activity", size=16, tooltip=tr("chat.raw_events"),
                                           clicked=self.toggle_activity)
        self.settings_button = tool_button("settings", size=16, tooltip=tr("nav.settings"),
                                           clicked=self.open_settings)
        for widget in (self.new_session_button, self.export_button, self.activity_button,
                       self.settings_button):
            box.addWidget(widget)
        self.top_bar = bar
        return bar

    def _build_status_bar(self) -> QWidget:
        self.status_bar = StatusBar()
        return self.status_bar

    def _wire_sidebar(self) -> None:
        self.sidebar.newSessionRequested.connect(self.new_session)
        self.sidebar.addProjectRequested.connect(lambda: self.open_project())
        self.sidebar.projectSelected.connect(self._on_project_selected)
        self.sidebar.sessionSelected.connect(self.switch_session)
        self.sidebar.sessionRenamed.connect(self._rename_session)
        self.sidebar.sessionDeleted.connect(self._delete_session)
        self.sidebar.sessionExported.connect(lambda _id: self.export_conversation())
        self.sidebar.settingsRequested.connect(self.open_settings)
        self.sidebar.diagnosticsRequested.connect(self.open_diagnostics)
        self.sidebar.buildRequested.connect(self.open_build)
        self.sidebar.themeToggled.connect(self.toggle_theme)
        self.sidebar.languageToggled.connect(self.toggle_language)
        self.sidebar.collapseRequested.connect(self.toggle_sidebar)

    def _wire_shortcuts(self) -> None:
        shortcut("Ctrl+N", self, self.new_session)
        shortcut("Ctrl+O", self, lambda: self.open_project())
        shortcut("Ctrl+K", self, lambda: self.composer.focus_input())
        shortcut("Ctrl+,", self, self.open_settings)
        shortcut("Ctrl+J", self, self.toggle_activity)
        shortcut("Ctrl+B", self, self.toggle_sidebar)
        shortcut("Esc", self, self.stop_generation)
        shortcut("Ctrl+Shift+E", self, self.export_conversation)
        shortcut("F5", self, self._startup_probe)

    # ------------------------------------------------------------------ #
    # backend
    # ------------------------------------------------------------------ #
    def _make_backend(self, demo: bool) -> Any:
        if demo:
            backend = DemoBackend()
            backend.set_broker(self.broker)
            return backend
        return ClaudeBackend(lambda: self.config, self.broker)

    def _connect_backend(self, backend) -> None:
        if self.backend is not None:
            try:
                self.backend.stop()
            except Exception:  # pragma: no cover
                pass
        self.backend = backend
        backend.event.connect(self._on_event)
        backend.state_changed.connect(self._on_state_changed)
        backend.turn_finished.connect(self._on_turn_finished)
        backend.error_occurred.connect(self._on_backend_error)
        backend.log_line.connect(self._on_log_line)
        backend.stats_changed.connect(self._on_stats)
        backend.permission_requested.connect(self._on_permission_request_from_backend)
        if hasattr(backend, "backend_notice"):
            backend.backend_notice.connect(self._on_backend_notice)
        self._on_state_changed(backend.state)

    def _project_path(self) -> str:
        return self.current_project.path if self.current_project else ""

    def _startup_probe(self) -> None:
        # The probe is started from a deferred singleShot; if the window was
        # closed in the meantime (or is a test fixture being torn down) starting
        # a thread nobody will ever join risks a hard crash at shutdown.
        if self._closing:
            return
        self.sidebar.set_status(tr("cli.searching"), "idle")
        self.status_bar.set_state("idle")
        thread = CliProbeThread(self.config.cli_path, self.config.last_project)
        thread.finishedProbe.connect(self._on_probe_done)
        thread.finished.connect(lambda: _LIVE_PROBES.discard(thread))
        self._probe = thread
        _LIVE_PROBES.add(thread)
        thread.start()

    def _maybe_autostart(self) -> None:
        """Reopen the last trusted project when the user enabled auto-start."""
        if self._closing:
            return
        if not self.config.autostart_session or self.current_project is not None:
            return
        path = self.config.last_project or ""
        record = self.config.project(path) if path else None
        if record is None or not record.trusted:
            return
        self._activate_project(record, autostart=True, silent=True)

    def _on_probe_done(self, info, caps, gw=None) -> None:
        if self._closing:
            return
        self.cli_info = info
        self.caps = caps
        self.gateway_info = gw
        if gw is not None and gw.detected:
            self.status_bar.set_gateway(f"FCC :{gw.port}", True)
            self.status_bar.gateway_label.setToolTip(
                f"{gw.base_url} · token: {gw.token_source} · {gw.detail}")
        else:
            self.status_bar.set_gateway("")
        self.welcome.set_cli(info.found, info.version, info.path)
        if info.found:
            self.sidebar.set_status(f"claude {info.version}", "ready")
            self.status_bar.set_state("ready" if self.backend and self.backend.is_running() else "idle")
            self.toast(f"{tr('cli.found')} · v{info.version}", "success")
        else:
            self.sidebar.set_status(tr("cli.not_found"), "error")
            self.status_bar.set_state("error", tr("cli.not_found"))
            if not self.config.demo_mode:
                self._show_cli_missing()

    def _show_cli_missing(self) -> None:
        # Never pop a modal dialog while closing / hidden (tests, shutdown):
        # the C++ box would be deleted under us and take the event loop down.
        if self._closing or not self.isVisible() or getattr(self, "_cli_box", None):
            return
        box = QMessageBox(self)
        self._cli_box = box
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("cli.not_found"))
        box.setText(tr("cli.not_found"))
        box.setInformativeText(tr("cli.not_found_body"))
        demo_button = box.addButton(tr("welcome.demo"), QMessageBox.AcceptRole)
        settings_button = box.addButton(tr("nav.settings"), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        clicked = box.clickedButton()
        if clicked is demo_button:
            self.config.demo_mode = True
            config_module.save(self.config)
            self._connect_backend(self._make_backend(True))
            self.toast(tr("status.demo"), "info")
        elif clicked is settings_button:
            self.open_settings()

    # ------------------------------------------------------------------ #
    # projects & sessions
    # ------------------------------------------------------------------ #
    def _load_projects(self) -> None:
        self.sidebar.refresh_projects(self.config.projects, self.config.last_project)
        record = self.config.project(self.config.last_project) if self.config.last_project else None
        if record is not None:
            self._activate_project(record, autostart=False, silent=True)
        else:
            self.welcome.set_project(None)
            self.welcome.set_recents(self.config.projects)
            self.stack.setCurrentWidget(self.welcome)
            self.composer.set_enabled_state(False, tr("chat.placeholder_blocked"))

    def open_project(self, initial: str = "") -> None:
        start = initial or (self.current_project.path if self.current_project else str(Path.home()))
        chosen = QFileDialog.getExistingDirectory(self, tr("project.select"), start)
        if not chosen:
            return
        self._request_trust(chosen)

    def _request_trust(self, path: str) -> None:
        from fcc.ui.dialogs.trust import TrustDialog

        record = self.config.upsert_project(path)
        try:
            dialog = TrustDialog(record.path,
                                 record.permission_mode or self.config.permission_mode,
                                 record.trusted, self)
            dialog.set_palette(self.palette)
            dialog.exec()
        except Exception as exc:  # never let the consent dialog take the app down
            log.exception("trust dialog failed")
            self.toast(f"Trust dialog error: {exc}", "error", 8000)
            return
        if not dialog.granted:
            config_module.save(self.config)
            self.sidebar.refresh_projects(self.config.projects, self.config.last_project)
            return
        record.trusted = True
        record.trusted_at = time.time()
        record.permission_mode = dialog.mode
        self.config.permission_mode = dialog.mode
        self.config.last_project = record.path
        config_module.save(self.config)
        self._activate_project(record, autostart=True)
        self.toast(f"{tr('project.trusted')} · {record.name}", "success")

    def _on_project_selected(self, path: str) -> None:
        if not path:
            return
        record = self.config.project(path)
        if record is None:
            self._request_trust(path)
            return
        if not record.trusted:
            self._request_trust(record.path)
            return
        self._activate_project(record, autostart=self.config.autostart_session)

    def _activate_project(self, record: ProjectRecord, autostart: bool = True,
                          silent: bool = False) -> None:
        self.current_project = record
        record.last_opened = time.time()
        self.config.last_project = record.path
        config_module.save(self.config)

        self.project_name_label.setText(record.name)
        self.project_path_label.setText(record.path)
        self.composer.set_project(record.path)
        self.status_bar.set_project(record.path)
        self.sidebar.refresh_projects(self.config.projects, record.path)
        sessions = self.config.sessions_for(record.path)
        self.sidebar.refresh_sessions(sessions, record.active_session)
        self._refresh_trust_button()

        facts = projects.inspect(record.path, deep=False)
        bits = []
        if facts.branch:
            bits.append(f"\u2387 {facts.branch}")
        if facts.file_count:
            bits.append(f"{facts.file_count:,} {tr('project.files')}")
        if facts.has_claude_md:
            bits.append("CLAUDE.md")
        self.project_path_label.setText("  ·  ".join([record.path] + bits))

        if sessions and not silent:
            self.switch_session(sessions[0].id, autostart=autostart)
        elif not sessions:
            self.current_session = None
            self.chat.clear()
            self.stack.setCurrentWidget(self.chat)
            self.session_title_label.setText("")
            self.welcome.set_project(record)
            self.welcome.set_recents(self.config.projects)
            if autostart and not silent:
                self.new_session()
            else:
                self.stack.setCurrentWidget(self.welcome)
                self.composer.set_enabled_state(False, tr("chat.placeholder_blocked"))
        self.composer.set_enabled_state(bool(record.trusted), tr("chat.placeholder") if record.trusted else tr("chat.placeholder_blocked"))

    def _refresh_trust_button(self) -> None:
        trusted = bool(self.current_project and self.current_project.trusted)
        self.trust_button.setText(tr("project.trusted") if trusted else tr("project.untrusted"))
        self.trust_button.setIcon(icons.icon("unlock" if trusted else "lock",
                                             "#4C8C4A" if trusted else "#B4801F", 13))

    def _toggle_trust(self) -> None:
        if self.current_project is None:
            self.open_project()
            return
        record = self.current_project
        if record.trusted:
            answer = QMessageBox.question(self, tr("project.revoke"),
                                          f"{record.path}\n\n{tr('project.revoke')}?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            record.trusted = False
            self.stop_session()
        else:
            self._request_trust(record.path)
            return
        config_module.save(self.config)
        self._refresh_trust_button()
        self.sidebar.refresh_projects(self.config.projects, record.path)
        self.composer.set_enabled_state(False, tr("chat.placeholder_blocked"))

    def new_session(self) -> None:
        if self.current_project is None:
            self.open_project()
            return
        if not self.current_project.trusted:
            self._request_trust(self.current_project.path)
            if not self.current_project.trusted:
                return
        self.stop_session()
        record = self.config.create_session(self.current_project.path, "", self.config.model)
        self.current_session = record
        self.chat.clear()
        self.stack.setCurrentWidget(self.chat)
        self.session_title_label.setText(tr("nav.new_session"))
        self.sidebar.refresh_sessions(self.config.sessions_for(self.current_project.path), record.id)
        self.sidebar.refresh_projects(self.config.projects, self.current_project.path)
        config_module.save(self.config)
        self._start_backend(record)
        self.composer.focus_input()

    def switch_session(self, session_id: str, autostart: bool = False) -> None:
        record = self.config.session(session_id)
        if record is None:
            return
        self.stop_session()
        self.current_session = record
        if record.project_path and (self.current_project is None or
                                    self.current_project.path != record.project_path):
            project = self.config.project(record.project_path)
            if project is not None:
                self.current_project = project
                self.project_name_label.setText(project.name)
                self.project_path_label.setText(project.path)
                self.composer.set_project(project.path)
                self.status_bar.set_project(project.path)
                self._refresh_trust_button()
        self.chat.clear()
        self.stack.setCurrentWidget(self.chat)
        self.session_title_label.setText(record.title or tr("nav.new_session"))
        restored = 0
        if record.transcript_path.exists():
            events = transcript.replay(record.transcript_path)
            self.chat.replay(events)
            restored = len(events)
        self.sidebar.refresh_sessions(self.config.sessions_for(record.project_path), record.id)
        log.info("switched to session %s (%s events restored)", session_id, restored)
        if autostart or self.config.autostart_session:
            self._start_backend(record)
        else:
            self.status_bar.set_state("idle")

    def _start_backend(self, record: SessionRecord) -> None:
        if self.backend is None:
            self.backend = self._make_backend(self.config.demo_mode)
            self._connect_backend(self.backend)
        self.composer.set_mode(self.config.permission_mode)
        self.composer.set_model(self.config.model)
        self.status_bar.set_mode(self.config.permission_mode)
        self.status_bar.set_model(self.config.model or tr("model.default"))
        self.backend.start(record.project_path, resume_session_id=record.cli_session_id,
                           new_session_id=record.id)

    def stop_session(self) -> None:
        if self.backend is not None and self.backend.is_running():
            self.backend.stop()
        self.broker.cancel_all(tr("status.stopped"))

    def _rename_session(self, session_id: str, title: str) -> None:
        if not title:
            return
        self.config.rename_session(session_id, title)
        config_module.save(self.config)
        if self.current_session and self.current_session.id == session_id:
            self.session_title_label.setText(title)
        self.sidebar.refresh_sessions(
            self.config.sessions_for(self._project_path()), session_id)

    def _delete_session(self, session_id: str) -> None:
        if not session_id:
            return
        answer = QMessageBox.question(self, tr("common.delete"), tr("common.delete") + "?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        if self.current_session and self.current_session.id == session_id:
            self.stop_session()
            self.current_session = None
            self.chat.clear()
            self.stack.setCurrentWidget(self.welcome)
        self.config.delete_session(session_id)
        config_module.save(self.config)
        self.sidebar.refresh_sessions(self.config.sessions_for(self._project_path()), "")
        self.toast("Session deleted", "info")

    # ------------------------------------------------------------------ #
    # conversation
    # ------------------------------------------------------------------ #
    def send_message(self, text: str, attachments: Optional[List[Dict[str, Any]]] = None) -> None:
        if self.current_project is None:
            self.open_project()
            return
        if not self.current_project.trusted:
            self._request_trust(self.current_project.path)
            if not self.current_project.trusted:
                return
        if self.current_session is None:
            self.new_session()
            if self.current_session is None:
                return
        if self.backend is None or not self.backend.is_running():
            self._start_backend(self.current_session)
            QTimer.singleShot(1400, lambda: self._send_now(text, attachments))
            self.chat.add_user(text, attachments)
            self._remember_sent(text)
            return
        self._send_now(text, attachments)

    def _send_now(self, text: str, attachments: Optional[List[Dict[str, Any]]]) -> None:
        if self.backend is None:
            return
        self.chat.add_user(text, attachments)
        self._remember_sent(text)
        self._turn_started_at = time.time()
        if not self.backend.send(text, attachments):
            self.chat.add_notice(tr("error.generic_title"), tr("error.cli_spawn"), "error")
            return
        if self.current_session and not self.current_session.title:
            title = text.strip().splitlines()[0][:52] if text.strip() else "Attachment"
            self.current_session.title = title
            self.session_title_label.setText(title)
            self.sidebar.refresh_sessions(
                self.config.sessions_for(self._project_path()), self.current_session.id)
            config_module.save(self.config)
        self.status_bar.set_state("busy")

    def _remember_sent(self, text: str) -> None:
        normalised = (text or "").strip()
        if normalised:
            self._sent_texts.append(normalised)
            if len(self._sent_texts) > 8:
                self._sent_texts = self._sent_texts[-8:]

    def _retry_last(self) -> None:
        if self._sent_texts:
            self.composer.set_text(self._sent_texts[-1])

    def stop_generation(self) -> None:
        if self.backend is None or not self.backend.is_running():
            return
        self.backend.interrupt()
        self.chat.add_notice(tr("chat.interrupted"), "", "warn", "stop")
        self.status_bar.set_state("ready")

    def change_permission_mode(self, mode: str) -> None:
        self.config.permission_mode = mode
        config_module.save(self.config)
        self.composer.set_mode(mode)
        self.status_bar.set_mode(mode)
        if self.backend is not None and self.backend.is_running():
            self.backend.set_permission_mode(mode)
        if mode == "bypassPermissions":
            self.toast(tr("perm.mode_warn"), "warn", 6000)
        if self.current_project is not None:
            self.current_project.permission_mode = mode

    def change_model(self, model: str) -> None:
        self.config.model = model
        config_module.save(self.config)
        self.composer.set_model(model)
        self.status_bar.set_model(model or tr("model.default"))
        if self.backend is not None and hasattr(self.backend, "set_model") and self.backend.is_running():
            self.backend.set_model(model)

    def export_conversation(self) -> None:
        if not self.chat.items:
            return
        default = f"{self.current_project.name if self.current_project else 'claude'}-" \
                  f"{time.strftime('%Y%m%d-%H%M')}.md"
        chosen, _ = QFileDialog.getSaveFileName(self, tr("chat.export"), str(Path.home() / default),
                                                "Markdown (*.md);;All files (*)")
        if not chosen:
            return
        title = (self.current_session.title if self.current_session else "") or APP_NAME
        try:
            Path(chosen).write_text(self.chat.export_markdown(title), encoding="utf-8")
        except OSError as exc:
            self.toast(f"Export failed: {exc}", "error")
            return
        self.toast(f"Saved to {chosen}", "success")
        open_path(str(Path(chosen).parent))

    def _attach_files(self) -> None:
        chosen, _ = QFileDialog.getOpenFileNames(self, tr("common.browse"),
                                                 self._project_path() or str(Path.home()))
        if chosen:
            count = self.composer.attach_paths(chosen)
            if count:
                self.toast(f"{count} file(s) attached", "info")

    def _show_raw(self, card) -> None:
        import json

        if not self.activity.isVisible():
            self.toggle_activity()
        for item in getattr(card, "raw_events", [])[-20:]:
            self.activity.add("raw", json.dumps(item, ensure_ascii=False)[:1200])

    # ------------------------------------------------------------------ #
    # events
    # ------------------------------------------------------------------ #
    def _on_event(self, event: protocol.UiEvent) -> None:
        kind = event.kind
        payload = event.payload

        if kind == protocol.USER_ECHO:
            text = str(payload.get("text", "")).strip()
            if text and text in self._sent_texts:
                return

        if kind == protocol.SESSION_INIT:
            self._on_session_init(payload)
        elif kind == protocol.TURN_DONE:
            pass  # handled by turn_finished signal
        elif kind == protocol.NOTICE and payload.get("notice") == "permission_ask":
            self.activity.add("permission", f"ask {payload.get('tool_name')} {payload.get('subject')}")
            return

        if kind == protocol.TOOL_START and not payload.get("partial"):
            self.activity.add("tool", f"{payload.get('name')} · {payload.get('tool_use_id', '')[:12]}")
        elif kind == protocol.TOOL_RESULT:
            decision = payload.get("permission_decision") or ""
            self.activity.add("tool", f"result {payload.get('name')} ({decision or 'ok'})")
        elif kind == protocol.TEXT_DELTA:
            return  # too chatty for the log
        elif kind == protocol.ERROR:
            self.activity.add("error", f"{payload.get('code')}: {payload.get('message')}")

        self.chat.handle(event)

    def _on_session_init(self, payload: Dict[str, Any]) -> None:
        session_id = str(payload.get("session_id") or "")
        if self.current_session is not None and session_id:
            self.current_session.cli_session_id = session_id
            if not self.current_session.transcript:
                self.current_session.transcript = str(paths.sessions_dir() / f"{self.current_session.id}.jsonl")
            self.current_session.model = str(payload.get("model") or self.current_session.model)
            self.current_session.updated_at = time.time()
            config_module.save(self.config)
        if self.backend is not None and hasattr(self.backend, "_transcript_path"):
            target = paths.sessions_dir() / f"{session_id or 'session'}.jsonl"
            self.backend._transcript_path = target
        self.composer.set_slash_commands(list(payload.get("slash_commands") or []))
        self.status_bar.set_model(str(payload.get("model") or ""))
        mode = str(payload.get("permission_mode") or "")
        if mode:
            self.status_bar.set_mode(mode)
            self.composer.set_mode(mode)
        if str(payload.get("api_key_source") or "") == "none":
            self.chat.add_notice(tr("cli.not_logged_in"), "", "warn", "key")
        self.welcome.set_project(self.current_project)
        self.stack.setCurrentWidget(self.chat)
        self.composer.set_enabled_state(True)

    def _on_state_changed(self, state: str) -> None:
        mapping = {STARTING: "starting", READY: "ready", BUSY: "busy", WAITING: "waiting_permission",
                   ERROR: "error", ENDED: "ended"}
        self.status_bar.set_state(mapping.get(state, "idle"))
        self.sidebar.set_status(tr(STATE_KEYS.get(state, "status.offline")),
                                {"ready": "ready", "busy": "busy", "error": "error",
                                 "waiting_permission": "waiting"}.get(state, "idle"))
        self.composer.set_running(state in (BUSY, WAITING, STARTING))
        if state == READY and self._turn_started_at:
            self._turn_started_at = 0.0

    def _on_turn_finished(self, payload: Dict[str, Any]) -> None:
        summary = protocol.summarize_result(payload)
        if self.current_session is not None:
            self.current_session.updated_at = time.time()
            self.current_session.message_count += 1
            self.current_session.total_cost_usd += summary["cost_usd"]
            self.current_session.cli_session_id = str(payload.get("session_id") or
                                                      self.current_session.cli_session_id)
            config_module.save(self.config)
            self.sidebar.refresh_sessions(self.config.sessions_for(self._project_path()),
                                          self.current_session.id)
        elapsed = time.time() - self._turn_started_at if self._turn_started_at else 0
        if self.config.notifications and (elapsed > 12 or summary["duration_ms"] > 12000):
            message = f"{tr('tool.finished')} · {protocol.format_duration(summary['duration_ms'])} · " \
                      f"{protocol.format_cost(summary['cost_usd'])}"
            self.toast(message, "success", 6000)
            self.notify.emit(message, "success")
        if payload.get("is_error"):
            self.toast(str(payload.get("result_text") or tr("status.error"))[:160], "error", 7000)

    def _on_stats(self, stats) -> None:
        self.status_bar.set_stats(stats)
        if hasattr(self.backend, "diagnostics"):
            self.activity.set_stats(self.backend.diagnostics())

    def _on_log_line(self, channel: str, text: str) -> None:
        self.activity.add(channel, text[:1200])

    def _on_backend_notice(self, level: str, message: str) -> None:
        self.toast(message, level if level in ("info", "success", "warn", "error") else "info")

    def _on_backend_error(self, code: str, message: str) -> None:
        log.error("backend error %s: %s", code, message)
        if code == "auth":
            self.chat.add_notice(tr("error.auth"), message, "error", "key")
            self.toast(tr("error.auth"), "error", 9000)
        elif code == "cli_not_found":
            self._show_cli_missing()
        else:
            self.chat.add_notice(tr("error.generic_title"), message, "error", "warning")
            self.toast(message[:180], "error", 7000)
        self.status_bar.set_state("error")

    # ------------------------------------------------------------------ #
    # permissions
    # ------------------------------------------------------------------ #
    def _on_permission_request_from_backend(self, ask: PermissionAsk) -> None:
        pass  # the broker drives the UI; this signal exists for other backends

    def _on_permission_ask(self, ask: PermissionAsk) -> None:
        """Runs on the GUI thread when the CLI needs a decision."""
        card = self.chat.add_permission(ask)
        card.decided.connect(self._on_inline_permission)
        self._pending_asks[ask.id] = card
        self.status_bar.set_state("waiting_permission")
        dialog = None
        if not self.isActiveWindow() or self.isMinimized():
            from fcc.ui.dialogs.permission import PermissionDialog

            dialog = PermissionDialog(ask, self._project_path(), self)
            dialog.set_palette(self.palette)
            dialog.decided.connect(self._on_dialog_permission)
            self._pending_asks[ask.id] = (card, dialog)
            self.activateWindow()
            dialog.show()
            dialog.raise_()
        self.chat.scroll_to_bottom()

    def _on_inline_permission(self, card: PermissionCard, behavior: str, remember: str,
                              message: str) -> None:
        ask = card.ask
        entry = self._pending_asks.pop(ask.id, None)
        dialog = None
        if isinstance(entry, tuple):
            dialog = entry[1]
        if dialog is not None:
            dialog.resolve_externally(behavior)
            dialog.close()
        self._finish_permission(ask, behavior, remember, "", message)

    def _on_dialog_permission(self, ask: PermissionAsk, behavior: str, scope: str,
                              pattern: str, message: str) -> None:
        entry = self._pending_asks.pop(ask.id, None)
        card = entry[0] if isinstance(entry, tuple) else entry
        if isinstance(card, PermissionCard):
            card.decide(behavior, scope)
        self._finish_permission(ask, behavior, scope, pattern, message)

    def _finish_permission(self, ask: PermissionAsk, behavior: str, scope: str,
                           pattern: str, message: str) -> None:
        if scope:
            self.broker.remember(ask, behavior, scope, pattern or None)
        answer = PermissionAnswer(behavior=behavior, message=message,
                                  updated_input=ask.tool_input if behavior == "allow" else None)
        self.broker.resolve(ask.id, answer)
        self.status_bar.set_state("busy")
        self.activity.add("permission", f"{behavior} {ask.tool_name} ({scope or 'once'})")

    def _on_rule_added(self, rule) -> None:
        config_module.save(self.config)
        self.toast(f"{rule.behavior}: {rule.display()}", "info")

    # ------------------------------------------------------------------ #
    # appearance
    # ------------------------------------------------------------------ #
    def apply_palette(self) -> None:
        qss, palette = theme.prepare_stylesheet(self.config.theme, self.config.accent,
                                                self.font_size)
        self.palette = palette
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        self.setWindowIcon(icons.app_logo_icon(palette.accent, 64))
        for widget in (self.sidebar, self.chat, self.composer, self.status_bar, self.welcome,
                       self.activity, self.toasts):
            if hasattr(widget, "set_palette"):
                widget.set_palette(palette)
        self.chat.set_palette(palette, self.font_size)
        self.composer.set_palette(palette)
        self.top_bar.setStyleSheet(
            f"QFrame#TopBar {{ background-color: {palette.bg}; border-bottom: 1px solid {palette.border}; }}"
        )
        self.project_name_label.setStyleSheet(f"color: {palette.text};")
        self.project_path_label.setStyleSheet(f"color: {palette.text_faint}; font-size: 11px;")
        self.session_title_label.setStyleSheet(f"color: {palette.text_muted};")
        self.project_icon.setPixmap(icons.pixmap("folder", palette.accent, 17))
        for widget, name in ((self.new_session_button, "plus"), (self.export_button, "download"),
                             (self.activity_button, "activity"), (self.settings_button, "settings")):
            widget.setIcon(icons.icon(name, palette.text_muted, 16))
        self.trust_button.setIcon(icons.icon("unlock" if (self.current_project and self.current_project.trusted) else "lock",
                                             palette.success if (self.current_project and self.current_project.trusted) else palette.warn, 13))
        self.status_bar.set_palette(palette)
        self._apply_layout_direction()

    def _apply_layout_direction(self) -> None:
        direction = Qt.RightToLeft if is_rtl() else Qt.LeftToRight
        self.setLayoutDirection(direction)

    def toggle_theme(self) -> None:
        order = ["light", "dark", "system"]
        current = self.config.theme if self.config.theme in order else "light"
        self.config.theme = order[(order.index(current) + 1) % len(order)]
        config_module.save(self.config)
        self.apply_palette()
        self.toast(f"{tr('settings.theme')}: {tr(f'settings.theme.{self.config.theme}')}", "info", 2200)

    def toggle_language(self) -> None:
        from fcc.i18n import get_language

        self.config.language = "fa" if get_language() == "en" else "en"
        set_language(self.config.language)
        config_module.save(self.config)
        self.retranslate()
        self.apply_palette()

    def retranslate(self) -> None:
        self.setWindowTitle(f"{APP_NAME} · {tr('app.tagline')}")
        self.sidebar.title_label.setText(tr("app.name"))
        self.sidebar.subtitle_label.setText(tr("app.tagline"))
        self.sidebar.new_button.setText(tr("nav.new_session"))
        self.sidebar.search.setPlaceholderText(tr("common.search"))
        self.sidebar.projects_label.setText(tr("nav.projects").upper())
        self.sidebar.sessions_label.setText(tr("nav.sessions").upper())
        self.composer.edit.setPlaceholderText(tr("chat.placeholder"))
        self.composer.set_mode(self.config.permission_mode)
        self.composer.set_model(self.config.model)
        self.status_bar.set_mode(self.config.permission_mode)
        self._refresh_trust_button()
        self.welcome.title.setText(tr("welcome.title"))
        self.welcome.subtitle.setText(tr("welcome.subtitle"))
        self.welcome.demo_button.setText(tr("welcome.demo"))
        self.welcome.open_button.setText(tr("welcome.open_folder"))
        self.welcome.demo_hint.setText(tr("welcome.demo_hint"))
        self._apply_layout_direction()

    def toggle_sidebar(self) -> None:
        self.config.sidebar_collapsed = not self.config.sidebar_collapsed
        self.sidebar.setVisible(not self.config.sidebar_collapsed)
        config_module.save(self.config)

    def toggle_activity(self) -> None:
        visible = not self.activity.isVisible()
        self.activity.setVisible(visible)
        self.config.show_raw_events = visible
        if visible:
            self.splitter.setSizes([max(600, self.width() - 400), 392])
        else:
            self.splitter.setSizes([self.width(), 0])

    def toast(self, message: str, level: str = "info", timeout: int = 4200) -> None:
        self.toasts.show_toast(message, level, timeout)
        self.toasts._relayout()

    # ------------------------------------------------------------------ #
    # dialogs
    # ------------------------------------------------------------------ #
    def open_settings(self) -> None:
        from fcc.ui.dialogs.settings import SettingsDialog

        dialog = SettingsDialog(self.config, self)
        dialog.set_palette(self.palette)
        dialog.applied.connect(self._on_settings_applied)
        dialog.themeChanged.connect(self.apply_palette)
        dialog.languageChanged.connect(self.retranslate)
        dialog.cliPathChanged.connect(lambda _path: self._startup_probe())
        dialog.gatewayChanged.connect(self._on_gateway_changed)
        dialog.exec()

    def _on_gateway_changed(self) -> None:
        self._startup_probe()
        if self.backend is not None and self.backend.is_running():
            self.toast(tr("gateway.restart"), "warn", 6000)

    def _on_settings_applied(self) -> None:
        set_language(self.config.language or "en")
        self.font_size = int(self.config.font_size)
        self.retranslate()
        self.apply_palette()
        if self.config.demo_mode and getattr(self.backend, "kind", "") != "demo":
            self._connect_backend(self._make_backend(True))
        elif not self.config.demo_mode and getattr(self.backend, "kind", "") == "demo":
            self._connect_backend(self._make_backend(False))
            self._startup_probe()

    def open_diagnostics(self) -> None:
        from fcc.ui.dialogs.system import DiagnosticsDialog

        dialog = DiagnosticsDialog(self.config, self.backend, self)
        dialog.set_palette(self.palette)
        dialog.exec()

    def open_build(self) -> None:
        from fcc.ui.dialogs.system import BuildDialog

        dialog = BuildDialog(self.config, self)
        dialog.set_palette(self.palette)
        dialog.exec()

    # ------------------------------------------------------------------ #
    def _restore_geometry(self) -> None:
        try:
            if self.config.window_geometry:
                from PySide6.QtCore import QByteArray

                self.restoreGeometry(QByteArray.fromBase64(self.config.window_geometry.encode("ascii")))
            if self.config.sidebar_collapsed:
                self.sidebar.setVisible(False)
            if self.config.show_raw_events:
                self.activity.setVisible(True)
        except Exception as exc:  # pragma: no cover
            log.warning("could not restore geometry: %s", exc)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.toasts._relayout()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._closing = True
        try:
            from PySide6.QtCore import QByteArray

            self.config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.config.sidebar_width = self.sidebar.width()
            config_module.save(self.config)
        except Exception:  # pragma: no cover
            pass
        self.stop_session()
        if self.backend is not None and hasattr(self.backend, "shutdown"):
            self.backend.shutdown()
        probe = getattr(self, "_probe", None)
        if probe is not None and probe.isRunning():
            probe.requestInterruption()
            # Generous wait: gateway probes are bounded by their HTTP timeouts.
            # If it still does not finish, _LIVE_PROBES keeps the wrapper alive
            # (drain_probes() joins it at app/test teardown) so the C++ thread
            # is never destroyed while running.
            probe.wait(5000)
        super().closeEvent(event)


STATE_KEYS = {
    STARTING: "status.starting",
    READY: "status.ready",
    BUSY: "status.busy",
    WAITING: "status.waiting",
    ERROR: "status.error",
    ENDED: "status.stopped",
    "idle": "status.offline",
}


def discovery_system_language() -> str:
    from fcc.i18n import detect_system_language

    return detect_system_language()


def _vsep() -> QWidget:
    widget = QFrame()
    widget.setFixedWidth(1)
    widget.setFixedHeight(20)
    widget.setProperty("vsep", True)
    return widget
