"""Diagnostics and Windows packaging dialogs."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget)

from fcc import icons, paths
from fcc.claude import discovery
from fcc.config import AppConfig
from fcc.i18n import tr
from fcc.ui.common import button, hline, label, open_path
from fcc.version import __version__, APP_NAME

BUILD_SCRIPT = "tools/build_windows.py"
SPEC_FILE = "build/fcc.spec"
ISS_FILE = "build/installer/ClaudeCodeStudio.iss"
WORKFLOW_FILE = ".github/workflows/windows-build.yml"


def run_build(output_dir: str, onefile: bool = False, installer: bool = True,
              on_line: Optional[Callable[[str], None]] = None,
              parent: Optional[QWidget] = None) -> Optional[QProcess]:
    """Run the packaging script on Windows, explain what to do elsewhere."""
    emit = on_line or (lambda text: None)
    root = paths.repo_root()
    script = root / BUILD_SCRIPT

    if sys.platform != "win32":
        emit(tr("build.needs_windows"))
        emit("")
        emit("What is already in this repository:")
        for relative in (BUILD_SCRIPT, SPEC_FILE, ISS_FILE, WORKFLOW_FILE):
            state = "ok" if (root / relative).exists() else "missing"
            emit(f"  [{state}] {relative}")
        emit("")
        emit("Two ways to get the installer:")
        emit("  1. On any Windows machine:  python " + BUILD_SCRIPT + " --installer")
        emit("  2. In GitHub:  push a tag like v" + __version__ + "  →  Actions → build-windows"
             "  →  download the artifacts.")
        return None

    if not script.exists():
        emit(f"Missing build script: {script}")
        return None

    args = [str(script), "--output", output_dir]
    if onefile:
        args.append("--onefile")
    if installer:
        args.append("--installer")
    emit(f"$ {sys.executable} {' '.join(args)}")
    process = QProcess(parent)
    process.setWorkingDirectory(str(root))
    process.setProgram(sys.executable)
    process.setArguments(args)

    def on_ready() -> None:
        data = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
        error = bytes(process.readAllStandardError()).decode("utf-8", "replace")
        for line in (data + error).splitlines():
            if line.strip():
                emit(line)

    process.readyRead.connect(on_ready)
    process.finished.connect(lambda code, _status: emit(f"… finished with exit code {code}"))
    process.start()
    return process


class DiagnosticsDialog(QDialog):
    def __init__(self, config: AppConfig, backend=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config
        self.backend = backend
        self.setWindowTitle(tr("diag.title"))
        self.setObjectName("Modal")
        self.resize(720, 560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.environment_view = QPlainTextEdit()
        self.capability_view = QPlainTextEdit()
        self.log_view = QPlainTextEdit()
        for view in (self.environment_view, self.capability_view, self.log_view):
            view.setReadOnly(True)
            view.setObjectName("RawLog")
            view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.tabs.addTab(self.environment_view, tr("diag.environment"))
        self.tabs.addTab(self.capability_view, tr("diag.capabilities"))
        self.tabs.addTab(self.log_view, tr("diag.recent_log"))

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 0, 0, 0)
        action_box.setSpacing(8)
        self.doctor_button = button(tr("cli.run_doctor"), "activity", size=14, clicked=self._doctor)
        self.open_log_button = button("Open log folder", "folder", ghost=True, size=14,
                                      clicked=lambda: open_path(str(paths.log_dir())))
        action_box.addWidget(self.doctor_button)
        action_box.addWidget(self.open_log_button)
        action_box.addStretch(1)
        self.copy_button = button(tr("diag.copy"), "copy", size=14, clicked=self._copy)
        self.refresh_button = button(tr("diag.refresh"), "refresh", primary=True, size=14,
                                     clicked=self.refresh)
        action_box.addWidget(self.copy_button)
        action_box.addWidget(self.refresh_button)
        outer.addWidget(actions)
        self.refresh()

    def refresh(self) -> None:
        info = discovery.probe(self.config.cli_path, cwd=self.config.last_project or None,
                               include_help=True)
        from fcc.claude.capabilities import detect

        caps = detect(info.path, info.version, info.help_text) if info.found else None
        environment = discovery.environment_report(info)
        if self.backend is not None and hasattr(self.backend, "diagnostics"):
            environment["backend"] = str(self.backend.diagnostics())
        from fcc.claude import gateway as gateway_module

        gw = gateway_module.detect(self.config)
        environment["fcc_gateway"] = (
            f"{gw.summary()} · token: {gw.token_source}" if gw.detected else gw.summary())
        self.environment_view.setPlainText(
            f"{APP_NAME} {__version__}\n\n"
            + "\n".join(f"{key:<22} {value}" for key, value in environment.items())
        )
        if caps is None:
            self.capability_view.setPlainText(tr("cli.not_found_body"))
        else:
            rows = [f"{key:<26} {value}" for key, value in caps.summary().items()]
            self.capability_view.setPlainText(
                f"claude {caps.cli_version}\n{caps.cli_path}\n\n" + "\n".join(rows)
            )
        try:
            text = paths.log_file().read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        self.log_view.setPlainText("\n".join(text.splitlines()[-400:]))

    def _doctor(self) -> None:
        info = discovery.probe(self.config.cli_path, include_help=False)
        code, out, err = discovery.doctor(info, cwd=self.config.last_project or None)
        self.environment_view.appendPlainText(f"\n$ claude doctor  (exit {code})\n{out}\n{err}")

    def _copy(self) -> None:
        report = "\n\n".join([
            self.environment_view.toPlainText(),
            self.capability_view.toPlainText(),
            self.log_view.toPlainText()[-4000:],
        ])
        QApplication.clipboard().setText(report)

    def set_palette(self, palette) -> None:
        self.setStyleSheet(f"QDialog#Modal {{ background-color: {palette.bg}; }}")
        for view in (self.environment_view, self.capability_view, self.log_view):
            view.setStyleSheet(
                f"QPlainTextEdit#RawLog {{ background-color: {palette.code_bg}; color: {palette.code_text};"
                f" border: 1px solid {palette.code_border}; border-radius: 10px; }}"
            )


class BuildDialog(QDialog):
    """Guided packaging: build the .exe and the installer."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config
        self._process: Optional[QProcess] = None
        self.setWindowTitle(tr("build.title"))
        self.setObjectName("Modal")
        self.resize(780, 620)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("package", "#D97757", 26))
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background-color: #F7E7DF; border-radius: 14px;")
        head_box.addWidget(logo)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(label(tr("build.title"), bold=True))
        column.addWidget(label(tr("build.body"), wrap=True, muted=True))
        head_box.addLayout(column, 1)
        outer.addWidget(head)

        checklist = QPlainTextEdit()
        checklist.setReadOnly(True)
        checklist.setObjectName("RawLog")
        checklist.setMaximumHeight(120)
        root = paths.repo_root()
        lines = [f"repository  {root}"]
        for relative in (BUILD_SCRIPT, SPEC_FILE, ISS_FILE, WORKFLOW_FILE):
            state = "present" if (root / relative).exists() else "MISSING"
            lines.append(f"  [{state:>7}]  {relative}")
        lines.append(f"platform    {sys.platform} ({'packaging supported' if sys.platform == 'win32' else 'use Windows or GitHub Actions'})")
        checklist.setPlainText("\n".join(lines))
        outer.addWidget(checklist)

        options = QWidget()
        option_box = QHBoxLayout(options)
        option_box.setContentsMargins(0, 0, 0, 0)
        option_box.setSpacing(8)
        self.output_edit = QLabel(str(self.config.build_output or paths.build_dir()))
        self.output_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        option_box.addWidget(self.output_edit, 1)
        self.browse_button = button(tr("common.browse"), "folder", ghost=True, size=14,
                                    clicked=self._browse)
        self.open_button = button(tr("settings.open_data"), "external", ghost=True, size=14,
                                  clicked=lambda: open_path(self.output_edit.text()))
        option_box.addWidget(self.browse_button)
        option_box.addWidget(self.open_button)
        outer.addWidget(options)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("RawLog")
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        outer.addWidget(self.log_view, 1)

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 0, 0, 0)
        action_box.setSpacing(8)
        self.workflow_button = button("GitHub Actions workflow", "external", ghost=True, size=14,
                                      clicked=lambda: open_path(str(paths.repo_root() / ".github" / "workflows")))
        action_box.addWidget(self.workflow_button)
        action_box.addStretch(1)
        self.close_button = button(tr("common.close"), ghost=True, size=14, clicked=self.close)
        self.build_button = button(tr("build.button"), "package", primary=True, size=15,
                                   clicked=self._build)
        action_box.addWidget(self.close_button)
        action_box.addWidget(self.build_button)
        outer.addWidget(actions)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("build.output"), self.output_edit.text())
        if chosen:
            self.output_edit.setText(chosen)
            self.config.build_output = chosen

    def _build(self) -> None:
        self.log_view.clear()
        output_dir = self.output_edit.text()
        self._process = run_build(
            output_dir,
            onefile=self.config.build_onefile,
            installer=self.config.build_installer,
            on_line=self._append,
            parent=self,
        )

    def _append(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
        super().closeEvent(event)

    def set_palette(self, palette) -> None:
        self.setStyleSheet(f"QDialog#Modal {{ background-color: {palette.bg}; }}")
        for view in (self.log_view,):
            view.setStyleSheet(
                f"QPlainTextEdit#RawLog {{ background-color: {palette.code_bg}; color: {palette.code_text};"
                f" border: 1px solid {palette.code_border}; border-radius: 10px; }}"
            )
        self.build_button.setIcon(icons.icon("package", palette.text_on_accent, 15))
