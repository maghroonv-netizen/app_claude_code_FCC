"""Settings dialog: appearance, CLI, permissions, packaging and about."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
                               QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
                               QVBoxLayout, QWidget)

from fcc import icons, paths
from fcc.config import ACCENTS, PERMISSION_MODES, THEMES, AppConfig, PermissionRule
from fcc.i18n import available_languages, tr
from fcc.ui.common import button, hline, label, open_path, tool_button
from fcc.version import __version__, APP_NAME


class SettingsDialog(QDialog):
    applied = Signal()
    gatewayChanged = Signal()
    cliPathChanged = Signal(str)
    themeChanged = Signal()
    languageChanged = Signal()

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(tr("settings.title"))
        self.setObjectName("Modal")
        self.resize(760, 640)
        self.setMinimumSize(680, 520)
        self._palette = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.tabs.addTab(self._general_tab(), tr("settings.general"))
        self.tabs.addTab(self._cli_tab(), tr("settings.cli"))
        self.tabs.addTab(self._permissions_tab(), tr("settings.permissions"))
        self.tabs.addTab(self._build_tab(), tr("nav.build"))
        self.tabs.addTab(self._about_tab(), tr("settings.advanced"))

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 0, 0, 0)
        action_box.setSpacing(8)
        action_box.addStretch(1)
        self.reset_button = button(tr("common.reset"), "refresh", ghost=True, size=15,
                                   clicked=self._reset)
        self.close_button = button(tr("common.close"), ghost=True, size=15, clicked=self.reject)
        self.save_button = button(tr("common.save"), "check", primary=True, size=15,
                                  clicked=self._save)
        action_box.addWidget(self.reset_button)
        action_box.addWidget(self.close_button)
        action_box.addWidget(self.save_button)
        outer.addWidget(actions)

    # ------------------------------------------------------------------ #
    def _form(self, rows: List[tuple]) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 18, 18, 18)
        box.setSpacing(12)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(11)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for title, widget in rows:
            if title is None:
                form.addRow(widget)
            else:
                form.addRow(label(title), widget)
        box.addLayout(form)
        box.addStretch(1)
        return page

    def _general_tab(self) -> QWidget:
        config = self.config
        self.language_combo = QComboBox()
        for code, name in available_languages().items():
            self.language_combo.addItem(f"{name} ({code})", code)
        current = config.language or "en"
        index = self.language_combo.findData(current)
        self.language_combo.setCurrentIndex(max(0, index))

        self.theme_combo = QComboBox()
        for value in THEMES:
            self.theme_combo.addItem(tr(f"settings.theme.{value}"), value)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(config.theme)))

        self.accent_combo = QComboBox()
        from fcc import theme as theme_module

        for key in ACCENTS:
            meta = theme_module.ACCENTS.get(key, {})
            self.accent_combo.addItem(str(meta.get("name", key.title())), key)
        self.accent_combo.setCurrentIndex(max(0, self.accent_combo.findData(config.accent)))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(11, 22)
        self.font_spin.setValue(int(config.font_size))
        self.font_spin.setSuffix(" px")

        self.animations_check = QCheckBox(tr("settings.animations"))
        self.animations_check.setChecked(config.animations)
        self.streaming_check = QCheckBox(tr("settings.streaming"))
        self.streaming_check.setChecked(config.streaming)
        self.notifications_check = QCheckBox(tr("settings.notifications"))
        self.notifications_check.setChecked(config.notifications)
        self.sound_check = QCheckBox(tr("settings.sound"))
        self.sound_check.setChecked(config.sound)
        self.autostart_check = QCheckBox(tr("settings.autostart"))
        self.autostart_check.setChecked(config.autostart_session)
        self.autoscroll_check = QCheckBox("Auto-scroll the conversation")
        self.autoscroll_check.setChecked(config.auto_scroll)
        self.raw_check = QCheckBox("Show the raw event panel at startup")
        self.raw_check.setChecked(config.show_raw_events)
        self.demo_check = QCheckBox(tr("settings.demo_mode"))
        self.demo_check.setChecked(config.demo_mode)

        checks = QWidget()
        check_box = QVBoxLayout(checks)
        check_box.setContentsMargins(0, 0, 0, 0)
        check_box.setSpacing(6)
        for widget in (self.animations_check, self.streaming_check, self.notifications_check,
                       self.sound_check, self.autostart_check, self.autoscroll_check,
                       self.raw_check, self.demo_check):
            check_box.addWidget(widget)

        return self._form([
            (tr("settings.language"), self.language_combo),
            (tr("settings.theme"), self.theme_combo),
            (tr("settings.accent"), self.accent_combo),
            (tr("settings.font_size"), self.font_spin),
            (None, hline()),
            (None, checks),
        ])

    def _cli_tab(self) -> QWidget:
        config = self.config
        path_row = QWidget()
        path_box = QHBoxLayout(path_row)
        path_box.setContentsMargins(0, 0, 0, 0)
        path_box.setSpacing(6)
        self.cli_edit = QLineEdit(config.cli_path)
        self.cli_edit.setPlaceholderText("auto-detect")
        path_box.addWidget(self.cli_edit, 1)
        self.browse_button = button(tr("common.browse"), "folder", size=14, clicked=self._browse_cli)
        path_box.addWidget(self.browse_button)
        self.detect_button = button("Detect", "refresh", size=14, clicked=self._detect_cli)
        path_box.addWidget(self.detect_button)

        self.cli_status = QLabel("")
        self.cli_status.setWordWrap(True)
        self.cli_status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.model_edit = QLineEdit(config.model)
        self.model_edit.setPlaceholderText("sonnet / opus / haiku / full model name")
        self.effort_combo = QComboBox()
        self.effort_combo.addItem(tr("model.default"), "")
        for level in ("low", "medium", "high", "xhigh", "max"):
            self.effort_combo.addItem(level, level)
        self.effort_combo.setCurrentIndex(max(0, self.effort_combo.findData(config.effort)))

        self.extra_args_edit = QLineEdit(" ".join(config.extra_args))
        self.extra_args_edit.setPlaceholderText("--autocompact 200k")
        self.extra_args_edit.setProperty("mono", True)

        self.env_edit = QPlainTextEdit()
        self.env_edit.setProperty("mono", True)
        self.env_edit.setPlaceholderText("ANTHROPIC_BASE_URL=https://…\nHTTPS_PROXY=http://127.0.0.1:7890")
        self.env_edit.setPlainText("\n".join(f"{k}={v}" for k, v in (config.env or {}).items()))
        self.env_edit.setMaximumHeight(110)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlainText(config.append_system_prompt)
        self.system_prompt_edit.setPlaceholderText("Always answer in Persian, keep changes minimal…")
        self.system_prompt_edit.setMaximumHeight(90)

        self.startup_spin = QSpinBox()
        self.startup_spin.setRange(10, 600)
        self.startup_spin.setValue(int(config.startup_timeout_sec))
        self.startup_spin.setSuffix(" s")

        self.doctor_button = button(tr("cli.run_doctor"), "activity", size=14, clicked=self._doctor)

        # ---- FCC gateway (free-claude-code server) ----
        self.gateway_mode_combo = QComboBox()
        for value in ("auto", "fcc", "off"):
            self.gateway_mode_combo.addItem(tr(f"gateway.mode.{value}"), value)
        self.gateway_mode_combo.setCurrentIndex(
            max(0, self.gateway_mode_combo.findData(config.gateway_mode)))
        self.gateway_url_edit = QLineEdit(config.gateway_url)
        self.gateway_url_edit.setPlaceholderText("http://127.0.0.1:8082")
        self.gateway_token_edit = QLineEdit(config.gateway_token)
        self.gateway_token_edit.setEchoMode(QLineEdit.Password)
        self.gateway_token_edit.setPlaceholderText("freecc")
        self.gateway_status = QLabel("")
        self.gateway_status.setWordWrap(True)
        self.gateway_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        gateway_buttons = QWidget()
        gb = QHBoxLayout(gateway_buttons)
        gb.setContentsMargins(0, 0, 0, 0)
        gb.setSpacing(8)
        gb.addWidget(button(tr("gateway.test"), "activity", size=14, clicked=self._test_gateway))
        gb.addWidget(button(tr("gateway.open_admin"), "external", ghost=True, size=14,
                            clicked=self._open_gateway_admin))
        gb.addStretch(1)
        self._gateway_initial_status()

        return self._form([
            (tr("cli.path"), path_row),
            (None, self.cli_status),
            (tr("model.label"), self.model_edit),
            (tr("effort.label"), self.effort_combo),
            (tr("settings.extra_args"), self.extra_args_edit),
            (tr("settings.env"), self.env_edit),
            ("Append system prompt", self.system_prompt_edit),
            ("Startup timeout", self.startup_spin),
            (None, self.doctor_button),
            (None, label(tr("gateway.title"), bold=True)),
            (None, label(tr("gateway.hint"), faint=True, wrap=True)),
            (tr("gateway.mode"), self.gateway_mode_combo),
            (tr("gateway.url"), self.gateway_url_edit),
            (tr("gateway.token"), self.gateway_token_edit),
            (None, self.gateway_status),
            (None, gateway_buttons),
        ])

    def _gateway_info(self):
        from fcc.claude import gateway

        probe_config = self.config
        return gateway.detect(probe_config)

    def _gateway_initial_status(self) -> None:
        info = self._gateway_info()
        self._show_gateway_status(info)

    def _show_gateway_status(self, info) -> None:
        if info.detected:
            self.gateway_status.setText(
                tr("gateway.status.on", url=info.base_url) + f" · {info.detail}"
                + f" · token: {info.token_source}")
            self.gateway_status.setStyleSheet("color: #4C8C4A;")
        else:
            self.gateway_status.setText(tr("gateway.status.off") + f" · {info.detail}")
            self.gateway_status.setStyleSheet("")

    def _test_gateway(self) -> None:
        from fcc.claude import gateway

        self.gateway_status.setText(tr("gateway.status.checking"))
        self.gateway_status.setStyleSheet("")
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        info = gateway.detect(self.config, use_cache=False, timeout=2.0)
        gateway.invalidate_cache()
        self._show_gateway_status(info)

    def _open_gateway_admin(self) -> None:
        from fcc.claude import gateway
        from fcc.ui.common import open_url

        explicit = self.gateway_url_edit.text().strip().rstrip("/")
        info = gateway.detect(self.config)
        base = explicit or info.base_url
        if not base:
            self._test_gateway()
            base = explicit or gateway.detect(self.config, use_cache=False).base_url
        if base:
            open_url(base.rstrip("/") + "/admin")

    def _permissions_tab(self) -> QWidget:
        config = self.config
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 18, 18, 18)
        box.setSpacing(10)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(8)
        head_box.addWidget(label(tr("perm.mode")))
        self.mode_combo = QComboBox()
        for value in PERMISSION_MODES:
            self.mode_combo.addItem(tr(f"perm.mode.{value}"), value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(config.permission_mode)))
        head_box.addWidget(self.mode_combo)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 3600)
        self.timeout_spin.setValue(int(config.permission_timeout_sec))
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setToolTip("0 = wait for you forever")
        head_box.addWidget(label("Answer timeout", muted=True))
        head_box.addWidget(self.timeout_spin)
        head_box.addStretch(1)
        box.addWidget(head)

        box.addWidget(label(tr("perm.rules"), bold=True))
        box.addWidget(label(tr("perm.rules_hint"), faint=True, wrap=True))

        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(
            ["Tool", "Pattern", "Behaviour", "Scope", ""])
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        box.addWidget(self.rules_table, 1)

        add_row = QWidget()
        add_box = QHBoxLayout(add_row)
        add_box.setContentsMargins(0, 0, 0, 0)
        add_box.setSpacing(6)
        self.rule_tool = QLineEdit()
        self.rule_tool.setPlaceholderText("Bash")
        self.rule_tool.setMaximumWidth(140)
        self.rule_pattern = QLineEdit()
        self.rule_pattern.setPlaceholderText("git *")
        self.rule_behavior = QComboBox()
        self.rule_behavior.addItems(["allow", "deny"])
        self.rule_scope = QComboBox()
        self.rule_scope.addItem(tr("perm.scope_global"), "global")
        self.rule_scope.addItem(tr("perm.scope_project"), "project")
        add_box.addWidget(self.rule_tool)
        add_box.addWidget(self.rule_pattern, 1)
        add_box.addWidget(self.rule_behavior)
        add_box.addWidget(self.rule_scope)
        self.add_rule_button = button(tr("perm.add_rule"), "plus", size=14, clicked=self._add_rule)
        add_box.addWidget(self.add_rule_button)
        self.clear_rules_button = button("Clear session rules", "trash", ghost=True, size=14,
                                         clicked=self._clear_session_rules)
        add_box.addWidget(self.clear_rules_button)
        box.addWidget(add_row)

        self._reload_rules()
        return page

    def _reload_rules(self) -> None:
        rules = list(self.config.rules)
        self.rules_table.setRowCount(0)
        for rule in rules:
            row = self.rules_table.rowCount()
            self.rules_table.insertRow(row)
            self.rules_table.setItem(row, 0, QTableWidgetItem(rule.tool or "*"))
            self.rules_table.setItem(row, 1, QTableWidgetItem(rule.pattern or "*"))
            self.rules_table.setItem(row, 2, QTableWidgetItem(rule.behavior))
            scope_text = tr(SCOPE_KEYS.get(rule.scope, "perm.scope_global"))
            if rule.scope == "project" and rule.project:
                scope_text += f" · {Path(rule.project).name}"
            self.rules_table.setItem(row, 3, QTableWidgetItem(scope_text))
            remove = QPushButton(icons.icon("trash", "#B3453B", 13), "")
            remove.setObjectName("Icon")
            remove.setCursor(Qt.PointingHandCursor)
            remove.clicked.connect(lambda _=False, rule_id=rule.id: self._remove_rule(rule_id))
            self.rules_table.setCellWidget(row, 4, remove)

    def _remove_rule(self, rule_id: str) -> None:
        self.config.remove_rule(rule_id)
        self._reload_rules()

    def _add_rule(self) -> None:
        tool = self.rule_tool.text().strip()
        if not tool:
            return
        scope = str(self.rule_scope.currentData() or "global")
        project = self.config.last_project if scope == "project" else ""
        rule = PermissionRule(
            tool=tool,
            pattern=self.rule_pattern.text().strip() or "*",
            behavior=str(self.rule_behavior.currentText()),
            scope=scope,
            project=project,
        )
        self.config.add_rule(rule)
        self.rule_tool.clear()
        self.rule_pattern.clear()
        self._reload_rules()

    def _clear_session_rules(self) -> None:
        self.config.clear_session_rules()
        self._reload_rules()

    def _build_tab(self) -> QWidget:
        config = self.config
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 18, 18, 18)
        box.setSpacing(10)
        box.addWidget(label(tr("build.title"), bold=True))
        box.addWidget(label(tr("build.body"), wrap=True, muted=True))

        self.onefile_check = QCheckBox("Single-file .exe (slower start, one download)")
        self.onefile_check.setChecked(config.build_onefile)
        self.installer_check = QCheckBox("Also build the installer (needs Inno Setup)")
        self.installer_check.setChecked(config.build_installer)
        box.addWidget(self.onefile_check)
        box.addWidget(self.installer_check)

        out_row = QWidget()
        out_box = QHBoxLayout(out_row)
        out_box.setContentsMargins(0, 0, 0, 0)
        out_box.setSpacing(6)
        self.output_edit = QLineEdit(config.build_output or str(paths.build_dir()))
        out_box.addWidget(self.output_edit, 1)
        self.output_browse = button(tr("common.browse"), "folder", size=14, clicked=self._browse_output)
        out_box.addWidget(self.output_browse)
        box.addWidget(label(tr("build.output"), muted=True))
        box.addWidget(out_row)

        self.build_button = button(tr("build.button"), "package", primary=True, size=15,
                                   clicked=self._build_now)
        box.addWidget(self.build_button, 0, Qt.AlignLeft)

        self.build_output = QPlainTextEdit()
        self.build_output.setReadOnly(True)
        self.build_output.setProperty("mono", True)
        self.build_output.setObjectName("RawLog")
        box.addWidget(self.build_output, 1)

        box.addWidget(hline())
        box.addWidget(label(tr("build.ci"), bold=True))
        box.addWidget(label(tr("build.ci_hint"), wrap=True, faint=True))
        ci_row = QWidget()
        ci_box = QHBoxLayout(ci_row)
        ci_box.setContentsMargins(0, 0, 0, 0)
        ci_box.setSpacing(6)
        ci_path = QLineEdit(".github/workflows/windows-build.yml")
        ci_path.setReadOnly(True)
        ci_box.addWidget(ci_path, 1)
        self.open_ci = button("Open", "external", ghost=True, size=14,
                              clicked=lambda: open_path(str(paths.repo_root() / ".github" / "workflows")))
        ci_box.addWidget(self.open_ci)
        box.addWidget(ci_row)
        return page

    def _about_tab(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(22, 20, 22, 20)
        box.setSpacing(10)
        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("spark", "#D97757", 40, stroke_width=2.0))
        logo.setFixedSize(56, 56)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background-color: #F7E7DF; border-radius: 16px;")
        head_box.addWidget(logo)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(label(APP_NAME, bold=True))
        column.addWidget(label(f"{tr('app.tagline')} · v{__version__}", muted=True))
        head_box.addLayout(column, 1)
        box.addWidget(head)

        box.addWidget(hline())
        info = QPlainTextEdit()
        info.setReadOnly(True)
        info.setObjectName("RawLog")
        info.setPlainText(
            "Data folder\n  " + str(paths.app_data_dir()) + "\n\n"
            "Log file\n  " + str(paths.log_file()) + "\n\n"
            "Sessions\n  " + str(paths.sessions_dir()) + "\n\n"
            "Repository\n  " + str(paths.repo_root()) + "\n\n"
            "Claude Code is a product of Anthropic. This app is an independent\n"
            "graphical front-end that drives the official `claude` CLI.\n"
        )
        box.addWidget(info, 1)

        row = QWidget()
        row_box = QHBoxLayout(row)
        row_box.setContentsMargins(0, 0, 0, 0)
        row_box.setSpacing(8)
        row_box.addStretch(1)
        self.open_data_button = button(tr("settings.open_data"), "folder", size=14,
                                       clicked=lambda: open_path(str(paths.app_data_dir())))
        self.open_log_button = button("Open log", "log", size=14,
                                      clicked=lambda: open_path(str(paths.log_dir())))
        row_box.addWidget(self.open_data_button)
        row_box.addWidget(self.open_log_button)
        box.addWidget(row)
        return page

    # ------------------------------------------------------------------ #
    def _browse_cli(self) -> None:
        start = str(Path.home())
        chosen = QFileDialog.getOpenFileName(self, tr("cli.choose"), start)
        if chosen and chosen[0]:
            self.cli_edit.setText(chosen[0])

    def _browse_output(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("build.output"), self.output_edit.text())
        if chosen:
            self.output_edit.setText(chosen)

    def _detect_cli(self) -> None:
        from fcc.claude import discovery

        info = discovery.probe(self.cli_edit.text().strip(), include_help=False)
        if info.found:
            self.cli_status.setText(f"{info.path}\n{tr('cli.version')} {info.version or '?'}")
            self.cli_status.setStyleSheet("color: #4C8C4A;")
        else:
            self.cli_status.setText(tr("cli.not_found_body"))
            self.cli_status.setStyleSheet("color: #B3453B;")

    def _doctor(self) -> None:
        from fcc.claude import discovery

        info = discovery.probe(self.cli_edit.text().strip(), include_help=False)
        code, out, err = discovery.doctor(info, cwd=self.config.last_project or None)
        text = (out or "") + ("\n" + err if err else "")
        QInputDialog.getMultiLineText(self, tr("cli.run_doctor"), f"exit {code}", text[:4000] or "-")

    def _build_now(self) -> None:
        from fcc.ui.dialogs.system import run_build

        output_dir = self.output_edit.text().strip() or str(paths.build_dir())
        onefile = self.onefile_check.isChecked()
        installer = self.installer_check.isChecked()

        def on_line(line: str) -> None:
            self.build_output.appendPlainText(line)

        run_build(output_dir, onefile=onefile, installer=installer, on_line=on_line,
                  parent=self)

    def _reset(self) -> None:
        from fcc import config as config_module

        fresh = config_module.AppConfig()
        for field_name in ("theme", "accent", "font_size", "language", "streaming", "animations",
                           "notifications", "permission_mode", "model", "effort", "demo_mode"):
            setattr(self.config, field_name, getattr(fresh, field_name))
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(fresh.theme)))
        self.accent_combo.setCurrentIndex(max(0, self.accent_combo.findData(fresh.accent)))
        self.font_spin.setValue(fresh.font_size)
        self.streaming_check.setChecked(fresh.streaming)
        self.demo_check.setChecked(fresh.demo_mode)

    def _save(self) -> None:
        config = self.config
        language_changed = (config.language or "en") != str(self.language_combo.currentData())
        theme_changed = (config.theme, config.accent, config.font_size) != (
            str(self.theme_combo.currentData()), str(self.accent_combo.currentData()),
            int(self.font_spin.value()))

        config.language = str(self.language_combo.currentData() or "en")
        config.theme = str(self.theme_combo.currentData() or "system")
        config.accent = str(self.accent_combo.currentData() or "coral")
        config.font_size = int(self.font_spin.value())
        config.animations = self.animations_check.isChecked()
        config.streaming = self.streaming_check.isChecked()
        config.notifications = self.notifications_check.isChecked()
        config.sound = self.sound_check.isChecked()
        config.autostart_session = self.autostart_check.isChecked()
        config.auto_scroll = self.autoscroll_check.isChecked()
        config.show_raw_events = self.raw_check.isChecked()
        config.demo_mode = self.demo_check.isChecked()

        cli_changed = config.cli_path != self.cli_edit.text().strip()
        config.cli_path = self.cli_edit.text().strip()
        config.model = self.model_edit.text().strip()
        config.effort = str(self.effort_combo.currentData() or "")
        config.extra_args = [a for a in self.extra_args_edit.text().split() if a]
        config.env = {}
        for line in self.env_edit.toPlainText().splitlines():
            line = line.strip()
            if not line or "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            config.env[key.strip()] = value.strip()
        config.append_system_prompt = self.system_prompt_edit.toPlainText().strip()
        config.startup_timeout_sec = int(self.startup_spin.value())
        config.permission_mode = str(self.mode_combo.currentData() or "default")
        config.permission_timeout_sec = int(self.timeout_spin.value())
        gateway_changed = (config.gateway_mode, config.gateway_url, config.gateway_token) != (
            str(self.gateway_mode_combo.currentData() or "auto"),
            self.gateway_url_edit.text().strip(),
            self.gateway_token_edit.text().strip())
        config.gateway_mode = str(self.gateway_mode_combo.currentData() or "auto")
        config.gateway_url = self.gateway_url_edit.text().strip()
        config.gateway_token = self.gateway_token_edit.text().strip()
        config.build_onefile = self.onefile_check.isChecked()
        config.build_installer = self.installer_check.isChecked()
        config.build_output = self.output_edit.text().strip()

        from fcc import config as config_module

        config_module.save(config)
        self.applied.emit()
        if theme_changed:
            self.themeChanged.emit()
        if language_changed:
            self.languageChanged.emit()
        if gateway_changed:
            from fcc.claude import gateway

            gateway.invalidate_cache()
            self.gatewayChanged.emit()
        if cli_changed:
            self.cliPathChanged.emit(config.cli_path)
        self.accept()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.setStyleSheet(f"QDialog#Modal {{ background-color: {palette.bg}; }}")
        self.save_button.setIcon(icons.icon("check", palette.text_on_accent, 15))
        self.reset_button.setIcon(icons.icon("refresh", palette.text_muted, 15))
        self.browse_button.setIcon(icons.icon("folder", palette.text, 14))
        self.detect_button.setIcon(icons.icon("refresh", palette.text, 14))
        self.doctor_button.setIcon(icons.icon("activity", palette.text, 14))
        self.add_rule_button.setIcon(icons.icon("plus", palette.text, 14))
        self.build_button.setIcon(icons.icon("package", palette.text_on_accent, 15))
        self.open_data_button.setIcon(icons.icon("folder", palette.text, 14))
        self.open_log_button.setIcon(icons.icon("log", palette.text, 14))


SCOPE_KEYS = {
    "session": "perm.scope_session",
    "project": "perm.scope_project",
    "global": "perm.scope_global",
}
