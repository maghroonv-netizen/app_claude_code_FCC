"""Application bootstrap: Qt setup, tray icon, command line, crash safety."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from fcc import config as config_module
from fcc import icons, paths, theme
from fcc.i18n import detect_system_language, set_language, tr
from fcc.logging_setup import get_logger, install_crash_hook, setup_logging
from fcc.version import APP_NAME, ORG_NAME, __version__

log = get_logger("app")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcc",
        description=f"{APP_NAME} — a native desktop GUI for the Claude Code CLI.",
    )
    parser.add_argument("project", nargs="?", default="", help="project folder to open")
    parser.add_argument("--demo", action="store_true", help="run against the built-in simulator")
    parser.add_argument("--new-session", action="store_true", help="start a fresh conversation")
    parser.add_argument("--theme", choices=["light", "dark", "system"], default="")
    parser.add_argument("--accent", default="", help="coral, clay, ember, olive or slate")
    parser.add_argument("--lang", default="", help="en or fa")
    parser.add_argument("--font-size", type=int, default=0)
    parser.add_argument("--mode", default="", help="permission mode override")
    parser.add_argument("--model", default="", help="model override")
    parser.add_argument("--cli", default="", help="path to the claude executable")
    parser.add_argument("--console-log", action="store_true", help="also log to stderr")
    parser.add_argument("--reset-config", action="store_true", help="forget settings and exit")
    parser.add_argument("--diagnostics", action="store_true", help="print CLI diagnostics and exit")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    return parser


def create_application(argv: Optional[List[str]] = None) -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setDesktopFileName("claude-code-studio")

    try:
        families = set(QFontDatabase.families())
    except Exception:  # pragma: no cover - very old Qt
        families = set()
    preferred = [family for family in ("Inter", "Segoe UI Variable Text", "Segoe UI",
                                       "Vazirmatn", "Noto Sans", "Ubuntu") if family in families]
    font = QFont(preferred[0] if preferred else app.font().family(), 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    mono_families = [family for family in ("Cascadia Mono", "JetBrains Mono", "Consolas",
                                           "SF Mono", "DejaVu Sans Mono") if family in families]
    if mono_families:
        mono = QFont(mono_families[0], 9)
        mono.setStyleHint(QFont.TypeWriter)
        app.setProperty("fcc_mono_font", mono)

    app.setWindowIcon(icons.app_logo_icon(theme.CORAL, 64))
    return app


class TrayIcon(QSystemTrayIcon):
    """Background presence: notifications when a long Claude run finishes."""

    def __init__(self, window, parent=None) -> None:
        super().__init__(window.windowIcon(), parent)
        self.window = window
        self.setToolTip(APP_NAME)
        menu_actions: List[QAction] = []
        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        show_action = QAction(tr("app.name"), menu)
        show_action.triggered.connect(self._show)
        new_action = QAction(tr("nav.new_session"), menu)
        new_action.triggered.connect(lambda: (self._show(), self.window.new_session()))
        quit_action = QAction(tr("common.close"), menu)
        quit_action.triggered.connect(self._quit)
        for action in (show_action, new_action):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.setContextMenu(menu)
        self._menu_actions = menu_actions
        self.activated.connect(self._activated)
        if self.window.backend is not None:
            self.window.notify.connect(self.notify)

    def _show(self) -> None:
        self.window.showNormal()
        self.window.activateWindow()
        self.window.raise_()

    def _quit(self) -> None:
        self.window.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.window.isVisible() and not self.window.isMinimized():
                self.window.hide()
            else:
                self._show()

    def notify(self, message: str, level: str = "info") -> None:
        if not self.supportsMessages():
            return
        icon = {"error": QSystemTrayIcon.Critical, "warn": QSystemTrayIcon.Warning,
                "success": QSystemTrayIcon.Information}.get(level, QSystemTrayIcon.Information)
        self.showMessage(APP_NAME, message, icon, 6000)


def apply_overrides(config, args: argparse.Namespace) -> None:
    if args.theme:
        config.theme = args.theme
    if args.accent:
        config.accent = args.accent
    if args.lang:
        config.language = args.lang
    if args.font_size:
        config.font_size = max(11, min(22, args.font_size))
    if args.mode:
        config.permission_mode = args.mode
    if args.model:
        config.model = args.model
    if args.cli:
        config.cli_path = args.cli
    if args.demo:
        config.demo_mode = True


def print_diagnostics(config) -> int:
    from fcc.claude import discovery
    from fcc.claude.capabilities import detect

    info = discovery.probe(config.cli_path, include_help=True)
    print(f"{APP_NAME} {__version__}")
    print(f"python      {sys.version.split()[0]} ({sys.executable})")
    print(f"platform    {sys.platform}")
    for key, value in discovery.environment_report(info).items():
        print(f"{key:<12}{value}")
    if not info.found:
        print("\nclaude CLI NOT FOUND. Install: npm install -g @anthropic-ai/claude-code")
        return 1
    caps = detect(info.path, info.version, info.help_text, use_cache=False)
    print("\ncapabilities")
    for key, value in caps.summary().items():
        print(f"  {key:<24}{value}")
    return 0


def run(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.version:
        print(f"{APP_NAME} {__version__}")
        return 0

    paths.ensure_runtime_dirs()
    setup_logging(logging.DEBUG if args.console_log else logging.INFO, console=args.console_log)
    log.info("starting %s %s (python %s, %s)", APP_NAME, __version__,
             sys.version.split()[0], sys.platform)

    config = config_module.load()
    if args.reset_config:
        config_module.reset()
        print(f"config reset: {paths.config_file()}")
        return 0
    if args.diagnostics:
        return print_diagnostics(config)

    apply_overrides(config, args)
    set_language(config.language or detect_system_language())
    config_module.save(config)

    app = create_application(sys.argv[:1])
    install_crash_hook(on_crash=lambda text: log.error("crash hook: %s", text[:400]))

    from fcc.ui.main_window import MainWindow

    window = MainWindow(config, demo=args.demo)
    window.show()

    tray: Optional[TrayIcon] = None
    if QSystemTrayIcon.isSystemTrayAvailable() and config.notifications:
        try:
            tray = TrayIcon(window, app)
            tray.show()
        except Exception as exc:  # pragma: no cover - tray is optional
            log.warning("tray unavailable: %s", exc)

    if args.project:
        target = str(Path(args.project).expanduser().resolve())
        if Path(target).is_dir():
            QTimer.singleShot(200, lambda: window.open_project(target))
        else:
            QTimer.singleShot(300, lambda: window.toast(f"Not a folder: {target}", "error", 6000))
    elif args.new_session:
        QTimer.singleShot(600, window.new_session)

    code = app.exec()

    # Join any probe thread still in flight before the interpreter starts
    # tearing objects down — a QThread destroyed while running aborts the
    # whole process (silently on Windows).
    try:
        from fcc.ui.main_window import drain_probes

        drain_probes(8000)
    except Exception:  # pragma: no cover - shutdown best-effort
        pass

    log.info("application exited with code %s", code)
    return int(code)
