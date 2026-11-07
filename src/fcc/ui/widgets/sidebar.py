"""Left navigation: brand, projects, sessions and global actions."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QSizePolicy, QVBoxLayout, QWidget)

from fcc import icons
from fcc.config import ProjectRecord, SessionRecord
from fcc.i18n import tr
from fcc.ui.common import Pill, button, hline, label, props, spacer, tool_button


class ProjectRow(QWidget):
    def __init__(self, record: ProjectRecord, active: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.record = record
        box = QHBoxLayout(self)
        box.setContentsMargins(6, 5, 6, 5)
        box.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap("folder", "#6E6C65", 16))
        box.addWidget(self.icon_label)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)
        self.name = QLabel(record.name)
        font = self.name.font()
        font.setWeight(QFont.DemiBold if active else QFont.Normal)
        self.name.setFont(font)
        column.addWidget(self.name)
        self.path = QLabel(record.path)
        self.path.setProperty("faint", True)
        font = self.path.font()
        font.setPointSize(max(7, font.pointSize() - 2))
        self.path.setFont(font)
        self.path.setTextInteractionFlags(Qt.NoTextInteraction)
        column.addWidget(self.path)
        box.addLayout(column, 1)
        self.trust_dot = QLabel()
        self.trust_dot.setFixedSize(10, 10)
        self.trust_dot.setToolTip(tr("project.trusted") if record.trusted else tr("project.untrusted"))
        box.addWidget(self.trust_dot)
        self._active = active

    def set_palette(self, palette) -> None:
        color = palette.accent if self._active else palette.text_muted
        self.icon_label.setPixmap(icons.pixmap("folder_open" if self._active else "folder", color, 16))
        self.name.setStyleSheet(f"color: {palette.text};")
        self.path.setStyleSheet(f"color: {palette.text_faint};")
        dot_color = palette.success if self.record.trusted else palette.text_faint
        self.trust_dot.setPixmap(_dot(9, dot_color))


class SessionRow(QFrame):
    """A polished session entry: accent bar, title, model chip and recency."""

    def __init__(self, record: SessionRecord, active: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.record = record
        self._active = active
        self.setObjectName("SessionItem")
        self.setProperty("active", "true" if active else "false")
        box = QHBoxLayout(self)
        box.setContentsMargins(10, 7, 10, 7)
        box.setSpacing(9)

        self.bar = QFrame()
        self.bar.setFixedSize(3, 26)
        box.addWidget(self.bar, 0, Qt.AlignVCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        box.addWidget(self.icon_label, 0, Qt.AlignVCenter)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.name = QLabel(record.title or tr("nav.new_session"))
        self.name.setTextFormat(Qt.PlainText)
        font = self.name.font()
        font.setWeight(QFont.DemiBold if active else QFont.Medium)
        self.name.setFont(font)
        top.addWidget(self.name, 1)
        self.chip = QLabel((record.model or "").split("/")[-1][:18])
        self.chip.setObjectName("Chip")
        self.chip.setVisible(bool(record.model))
        top.addWidget(self.chip, 0, Qt.AlignVCenter)
        column.addLayout(top)
        self.meta = QLabel(_when(record.updated_at))
        self.meta.setProperty("faint", True)
        font = self.meta.font()
        font.setPointSize(max(7, font.pointSize() - 2))
        self.meta.setFont(font)
        column.addWidget(self.meta)
        box.addLayout(column, 1)

    def set_palette(self, palette) -> None:
        color = palette.accent if self._active else palette.text_faint
        self.icon_label.setPixmap(icons.pixmap("chat", color, 16))
        self.bar.setStyleSheet(
            f"background: {palette.accent if self._active else 'transparent'};"
            f" border-radius: 2px;")
        self.name.setStyleSheet(f"color: {palette.text};")
        self.meta.setStyleSheet(f"color: {palette.text_faint};")
        self.chip.setStyleSheet(
            f"background: {palette.accent_soft if self._active else palette.surface_alt};"
            f" color: {palette.accent if self._active else palette.text_muted};"
            f" border-radius: 8px; padding: 1px 7px; font-size: 9px; font-weight: 600;")


def _dot(size: int, color: str):
    from PySide6.QtGui import QColor, QPainter, QPixmap

    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(0, 0, pixmap.width(), pixmap.height())
    painter.end()
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _when(timestamp: float) -> str:
    if not timestamp:
        return ""
    delta = time.time() - timestamp
    if delta < 60:
        return "now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)}d ago"
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


class Sidebar(QFrame):
    newSessionRequested = Signal()
    addProjectRequested = Signal()
    projectSelected = Signal(str)
    sessionSelected = Signal(str)
    sessionRenamed = Signal(str, str)
    sessionDeleted = Signal(str)
    sessionExported = Signal(str)
    settingsRequested = Signal()
    diagnosticsRequested = Signal()
    buildRequested = Signal()
    themeToggled = Signal()
    languageToggled = Signal()
    collapseRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(288)
        self._palette = None
        self._projects: List[ProjectRecord] = []
        self._sessions: List[SessionRecord] = []
        self.active_project = ""
        self.active_session = ""
        self._filter = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 14, 12, 10)
        outer.setSpacing(10)

        # ---- brand ---- #
        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(2, 0, 0, 0)
        head_box.setSpacing(9)
        self.logo = QLabel()
        self.logo.setFixedSize(32, 32)
        head_box.addWidget(self.logo)
        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(0)
        self.title_label = QLabel(tr("app.name"))
        font = self.title_label.font()
        font.setWeight(QFont.Bold)
        font.setPointSize(font.pointSize() + 1)
        self.title_label.setFont(font)
        title_column.addWidget(self.title_label)
        self.subtitle_label = QLabel(tr("app.tagline"))
        self.subtitle_label.setProperty("faint", True)
        font = self.subtitle_label.font()
        font.setPointSize(max(7, font.pointSize() - 2))
        self.subtitle_label.setFont(font)
        title_column.addWidget(self.subtitle_label)
        head_box.addLayout(title_column, 1)
        self.collapse_button = tool_button("sidebar", size=15, tooltip=tr("nav.collapse"),
                                           clicked=self.collapseRequested.emit)
        head_box.addWidget(self.collapse_button)
        outer.addWidget(head)

        self.new_button = button(tr("nav.new_session"), "plus", primary=True, size=15,
                                 clicked=self.newSessionRequested.emit)
        outer.addWidget(self.new_button)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("common.search"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        outer.addWidget(self.search)

        # ---- projects ---- #
        projects_head = QWidget()
        projects_box = QHBoxLayout(projects_head)
        projects_box.setContentsMargins(2, 4, 2, 0)
        projects_box.setSpacing(6)
        self.projects_label = QLabel(tr("nav.projects").upper())
        self.projects_label.setObjectName("SectionTitle")
        projects_box.addWidget(self.projects_label)
        projects_box.addStretch(1)
        self.add_project_button = tool_button("folder_plus", size=14, tooltip=tr("nav.add_project"),
                                              clicked=self.addProjectRequested.emit)
        projects_box.addWidget(self.add_project_button)
        outer.addWidget(projects_head)

        self.project_list = QListWidget()
        self.project_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.project_list.setMinimumHeight(96)
        self.project_list.setMaximumHeight(190)
        self.project_list.itemClicked.connect(self._on_project_clicked)
        self.project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self._project_menu)
        outer.addWidget(self.project_list)

        outer.addWidget(hline())

        # ---- sessions ---- #
        sessions_head = QWidget()
        sessions_box = QHBoxLayout(sessions_head)
        sessions_box.setContentsMargins(2, 4, 2, 0)
        sessions_box.setSpacing(6)
        self.sessions_label = QLabel(tr("nav.sessions").upper())
        self.sessions_label.setObjectName("SectionTitle")
        sessions_box.addWidget(self.sessions_label)
        sessions_box.addStretch(1)
        self.session_count = QLabel("")
        self.session_count.setProperty("faint", True)
        sessions_box.addWidget(self.session_count)
        outer.addWidget(sessions_head)

        self.session_list = QListWidget()
        self.session_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.session_list.itemClicked.connect(self._on_session_clicked)
        self.session_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self._session_menu)
        outer.addWidget(self.session_list, 1)

        # ---- footer ---- #
        outer.addWidget(hline())
        self.status_pill = Pill(tr("status.offline"), "cpu", "#9C9A91", size=12)
        outer.addWidget(self.status_pill)

        footer = QWidget()
        footer_box = QHBoxLayout(footer)
        footer_box.setContentsMargins(2, 0, 2, 0)
        footer_box.setSpacing(2)
        self.theme_button = tool_button("moon", size=16, tooltip=tr("settings.theme"),
                                        clicked=self.themeToggled.emit)
        self.language_button = tool_button("globe", size=16, tooltip=tr("settings.language"),
                                           clicked=self.languageToggled.emit)
        self.build_button = tool_button("package", size=16, tooltip=tr("nav.build"),
                                        clicked=self.buildRequested.emit)
        self.diagnostic_button = tool_button("activity", size=16, tooltip=tr("nav.diagnostics"),
                                             clicked=self.diagnosticsRequested.emit)
        footer_box.addWidget(self.theme_button)
        footer_box.addWidget(self.language_button)
        footer_box.addWidget(self.build_button)
        footer_box.addStretch(1)
        footer_box.addWidget(self.diagnostic_button)
        self.settings_button = tool_button("settings", size=16, tooltip=tr("nav.settings"),
                                           clicked=self.settingsRequested.emit)
        footer_box.addWidget(self.settings_button)
        outer.addWidget(footer)

    # ------------------------------------------------------------------ #
    def _on_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self.refresh_sessions(self._sessions, self.active_session)

    def _on_project_clicked(self, item: QListWidgetItem) -> None:
        row = self.project_list.itemWidget(item)
        if isinstance(row, ProjectRow):
            self.projectSelected.emit(row.record.path)

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        row = self.session_list.itemWidget(item)
        if isinstance(row, SessionRow):
            self.sessionSelected.emit(row.record.id)

    def _project_menu(self, position: QPoint) -> None:
        item = self.project_list.itemAt(position)
        if item is None:
            return
        row = self.project_list.itemWidget(item)
        if not isinstance(row, ProjectRow):
            return
        record = row.record
        menu = QMenu(self)
        open_action = menu.addAction(icons.icon("folder_open", "#6E6C65", 14), tr("project.open_external"))
        grant_action = menu.addAction(
            icons.icon("unlock" if not record.trusted else "lock", "#6E6C65", 14),
            tr("project.grant") if not record.trusted else tr("project.revoke"))
        menu.addSeparator()
        remove_action = menu.addAction(icons.icon("trash", "#B3453B", 14), tr("project.remove"))
        chosen = menu.exec(self.project_list.mapToGlobal(position))
        if chosen is open_action:
            from fcc.ui.common import open_path

            open_path(record.path)
        elif chosen is grant_action:
            self.projectSelected.emit(record.path)
        elif chosen is remove_action:
            from PySide6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self, tr("project.remove"), f"{record.name}\n\n{tr('project.remove')}?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer == QMessageBox.Yes:
                self.sessionDeleted.emit("")  # placeholder, handled by main window
                self.projectSelected.emit("")

    def _session_menu(self, position: QPoint) -> None:
        item = self.session_list.itemAt(position)
        if item is None:
            return
        row = self.session_list.itemWidget(item)
        if not isinstance(row, SessionRow):
            return
        record = row.record
        menu = QMenu(self)
        rename = menu.addAction(icons.icon("pencil", "#6E6C65", 14), tr("common.rename"))
        export = menu.addAction(icons.icon("download", "#6E6C65", 14), tr("chat.export"))
        menu.addSeparator()
        delete = menu.addAction(icons.icon("trash", "#B3453B", 14), tr("common.delete"))
        chosen = menu.exec(self.session_list.mapToGlobal(position))
        if chosen is rename:
            from PySide6.QtWidgets import QInputDialog

            text, ok = QInputDialog.getText(self, tr("common.rename"), "Title:", text=record.title)
            if ok:
                self.sessionRenamed.emit(record.id, text.strip())
        elif chosen is export:
            self.sessionExported.emit(record.id)
        elif chosen is delete:
            self.sessionDeleted.emit(record.id)

    # ------------------------------------------------------------------ #
    def refresh_projects(self, records: List[ProjectRecord], active: str = "") -> None:
        self._projects = records
        self.active_project = active
        self.project_list.clear()
        for record in records:
            if self._filter and self._filter not in record.name.lower() and self._filter not in record.path.lower():
                continue
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 46))
            row = ProjectRow(record, active=(_norm(record.path) == _norm(active)))
            self.project_list.addItem(item)
            self.project_list.setItemWidget(item, row)
            if self._palette is not None:
                row.set_palette(self._palette)
        self.projects_label.setText(f"{tr('nav.projects').upper()}  ({len(records)})")
        self.project_list.setVisible(bool(records) or not self._filter)

    def refresh_sessions(self, records: List[SessionRecord], active: str = "") -> None:
        self._sessions = records
        self.active_session = active
        self.session_list.clear()
        shown = 0
        for record in records:
            haystack = f"{record.title} {record.model}".lower()
            if self._filter and self._filter not in haystack:
                continue
            shown += 1
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 52))
            row = SessionRow(record, active=(record.id == active))
            self.session_list.addItem(item)
            self.session_list.setItemWidget(item, row)
            if self._palette is not None:
                row.set_palette(self._palette)
        self.session_count.setText(str(shown) if shown else "")
        if not records:
            placeholder = QListWidgetItem(tr("nav.no_sessions"))
            placeholder.setFlags(Qt.NoItemFlags)
            self.session_list.addItem(placeholder)

    def set_status(self, text: str, state: str = "idle") -> None:
        colors = {"ready": "#4C8C4A", "busy": "#D97757", "error": "#B3453B",
                  "waiting": "#B4801F", "demo": "#7A8450"}
        color = colors.get(state, "#9C9A91")
        self.status_pill.set_text(text)
        self.status_pill.set_color(color, "cpu")

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.setStyleSheet(
            f"QFrame#Sidebar {{ background-color: {palette.sidebar}; border-right: 1px solid {palette.border}; }}"
        )
        self.logo.setPixmap(icons.pixmap("spark", palette.accent, 30, stroke_width=2.1))
        self.title_label.setStyleSheet(f"color: {palette.text};")
        self.subtitle_label.setStyleSheet(f"color: {palette.text_faint};")
        self.new_button.setIcon(icons.icon("plus", palette.text_on_accent, 15))
        self.search.setStyleSheet(
            f"QLineEdit {{ background-color: {palette.surface}; border: 1px solid {palette.border};"
            f" border-radius: 9px; color: {palette.text}; padding: 6px 10px; }}"
        )
        self.projects_label.setStyleSheet(f"color: {palette.text_faint};")
        self.sessions_label.setStyleSheet(f"color: {palette.text_faint};")
        self.session_count.setStyleSheet(f"color: {palette.text_faint};")
        for widget, name in ((self.theme_button, "moon"), (self.language_button, "globe"),
                             (self.build_button, "package"), (self.diagnostic_button, "activity"),
                             (self.settings_button, "settings"), (self.collapse_button, "sidebar"),
                             (self.add_project_button, "folder_plus")):
            widget.setIcon(icons.icon(name, palette.text_muted, 16 if widget is not self.add_project_button else 14))
        self.status_pill.set_color(palette.text_faint, "cpu")
        self.refresh_projects(self._projects, self.active_project)
        self.refresh_sessions(self._sessions, self.active_session)


def _norm(path: str) -> str:
    from pathlib import Path

    try:
        return str(Path(path).resolve())
    except OSError:
        return path
