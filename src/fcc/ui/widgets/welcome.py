"""First-run / no-project screen with the four setup steps."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from fcc import icons
from fcc.config import ProjectRecord
from fcc.i18n import tr
from fcc.ui.common import button, hline, label, props


class StepCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, icon_name: str, title: str, body: str,
                 action_text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(8)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(30, 30)
        self.icon_label.setAlignment(Qt.AlignCenter)
        head_box.addWidget(self.icon_label)
        self.title_label = QLabel(title)
        font = self.title_label.font()
        font.setWeight(QFont.DemiBold)
        self.title_label.setFont(font)
        head_box.addWidget(self.title_label, 1)
        self.state_label = QLabel("")
        head_box.addWidget(self.state_label)
        box.addWidget(head)

        self.body_label = label(body, wrap=True, muted=True)
        box.addWidget(self.body_label)

        self._icon_name = icon_name
        if action_text:
            self.action = button(action_text, "chevron_right", ghost=True, size=13)
            self.action.setCursor(Qt.PointingHandCursor)
            self.action.clicked.connect(lambda: self.clicked.emit(self.key))
            box.addWidget(self.action, 0, Qt.AlignLeft)
        else:
            self.action = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def set_state(self, text: str, color: str = "#4C8C4A") -> None:
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def set_body(self, text: str) -> None:
        self.body_label.setText(text)

    def set_palette(self, palette) -> None:
        self.icon_label.setPixmap(icons.pixmap(self._icon_name, palette.accent, 20))
        self.icon_label.setStyleSheet(
            f"background-color: {palette.accent_soft}; border-radius: 9px;"
        )
        self.title_label.setStyleSheet(f"color: {palette.text};")
        self.body_label.setStyleSheet(f"color: {palette.text_muted};")
        self.setStyleSheet(
            f"QFrame#Card {{ background-color: {palette.surface}; border: 1px solid {palette.border};"
            f" border-radius: 16px; }}"
            f"QFrame#Card:hover {{ border: 1px solid {palette.accent_border}; }}"
        )


class WelcomeScreen(QWidget):
    openFolderRequested = Signal()
    grantRequested = Signal()
    demoRequested = Signal()
    settingsRequested = Signal()
    projectPicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._palette = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 34, 36, 26)
        outer.setSpacing(18)
        outer.addStretch(1)

        hero = QWidget()
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(0, 0, 0, 0)
        hero_box.setSpacing(10)
        self.logo = QLabel()
        self.logo.setFixedSize(62, 62)
        self.logo.setAlignment(Qt.AlignCenter)
        hero_box.addWidget(self.logo, 0, Qt.AlignHCenter)
        self.title = QLabel(tr("welcome.title"))
        self.title.setObjectName("ModalTitle")
        self.title.setAlignment(Qt.AlignCenter)
        hero_box.addWidget(self.title)
        self.subtitle = label(tr("welcome.subtitle"), wrap=True, muted=True, align=Qt.AlignCenter)
        self.subtitle.setMaximumWidth(620)
        hero_box.addWidget(self.subtitle, 0, Qt.AlignHCenter)
        outer.addWidget(hero)

        self.grid = QWidget()
        grid_box = QGridLayout(self.grid)
        grid_box.setContentsMargins(0, 0, 0, 0)
        grid_box.setSpacing(12)
        self.step_cli = StepCard("cli", "terminal", tr("welcome.step1"), tr("cli.searching"))
        self.step_folder = StepCard("folder", "folder_plus", tr("welcome.step2"),
                                    tr("project.select_hint"), tr("welcome.open_folder"))
        self.step_access = StepCard("access", "shield", tr("welcome.step3"), tr("project.untrusted"))
        self.step_chat = StepCard("chat", "chat", tr("welcome.step4"), tr("chat.empty_body"))
        grid_box.addWidget(self.step_cli, 0, 0)
        grid_box.addWidget(self.step_folder, 0, 1)
        grid_box.addWidget(self.step_access, 1, 0)
        grid_box.addWidget(self.step_chat, 1, 1)
        for step in (self.step_cli, self.step_folder, self.step_access, self.step_chat):
            step.clicked.connect(self._on_step)
        outer.addWidget(self.grid)

        self.recent_row = QWidget()
        self.recent_box = QHBoxLayout(self.recent_row)
        self.recent_box.setContentsMargins(0, 0, 0, 0)
        self.recent_box.setSpacing(8)
        self.recent_label = label(tr("welcome.recent"), faint=True)
        self.recent_box.addWidget(self.recent_label)
        self.recent_box.addStretch(1)
        self.recent_row.setVisible(False)
        outer.addWidget(self.recent_row)

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 0, 0, 0)
        action_box.setSpacing(10)
        action_box.addStretch(1)
        self.demo_button = button(tr("welcome.demo"), "sparkles", size=15,
                                  clicked=self.demoRequested.emit)
        self.settings_button = button(tr("nav.settings"), "settings", ghost=True, size=15,
                                      clicked=self.settingsRequested.emit)
        self.open_button = button(tr("welcome.open_folder"), "folder_plus", primary=True, size=15,
                                  clicked=self.openFolderRequested.emit)
        action_box.addWidget(self.demo_button)
        action_box.addWidget(self.settings_button)
        action_box.addWidget(self.open_button)
        action_box.addStretch(1)
        outer.addWidget(actions)

        self.demo_hint = label(tr("welcome.demo_hint"), faint=True, wrap=True, align=Qt.AlignCenter)
        outer.addWidget(self.demo_hint, 0, Qt.AlignHCenter)
        outer.addStretch(2)

    # ------------------------------------------------------------------ #
    def _on_step(self, key: str) -> None:
        if key == "folder":
            self.openFolderRequested.emit()
        elif key == "access":
            self.grantRequested.emit()
        elif key == "cli":
            self.settingsRequested.emit()
        else:
            self.openFolderRequested.emit()

    def set_cli(self, found: bool, version: str, path: str) -> None:
        if found:
            self.step_cli.set_state(f"v{version}", "#4C8C4A")
            self.step_cli.set_body(path)
        else:
            self.step_cli.set_state(tr("cli.not_found"), "#B3453B")
            self.step_cli.set_body(tr("cli.not_found_body"))

    def set_project(self, record: Optional[ProjectRecord]) -> None:
        if record is None:
            self.step_folder.set_state("", "#9C9A91")
            self.step_folder.set_body(tr("project.select_hint"))
            self.step_access.set_state(tr("project.untrusted"), "#9C9A91")
            self.step_access.set_body(tr("project.select_hint"))
            return
        self.step_folder.set_state(record.name, "#4C8C4A")
        self.step_folder.set_body(record.path)
        if record.trusted:
            self.step_access.set_state(tr("project.trusted"), "#4C8C4A")
            self.step_access.set_body(tr("project.trust_body").format(path=record.path).split("\n\n")[0])
        else:
            self.step_access.set_state(tr("project.untrusted"), "#B4801F")
            self.step_access.set_body(tr("project.trust_body").format(path=record.path))

    def set_recents(self, records: List[ProjectRecord]) -> None:
        while self.recent_box.count() > 2:
            item = self.recent_box.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        if not records:
            self.recent_row.setVisible(False)
            return
        for record in records[:5]:
            chip = button(record.name, "folder", size=12,
                          clicked=lambda _=False, path=record.path: self.projectPicked.emit(path))
            chip.setObjectName("Chip")
            chip.setToolTip(record.path)
            chip.setCursor(Qt.PointingHandCursor)
            self.recent_box.insertWidget(self.recent_box.count() - 1, chip)
        self.recent_row.setVisible(True)

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.logo.setPixmap(icons.pixmap("spark", palette.accent, 54, stroke_width=2.0))
        self.logo.setStyleSheet(
            f"background-color: {palette.accent_soft}; border-radius: 18px;"
        )
        self.title.setStyleSheet(f"color: {palette.text}; font-size: 26px; font-weight: 700;")
        self.subtitle.setStyleSheet(f"color: {palette.text_muted};")
        self.demo_hint.setStyleSheet(f"color: {palette.text_faint}; max-width: 520px;")
        self.recent_label.setStyleSheet(f"color: {palette.text_faint};")
        for step in (self.step_cli, self.step_folder, self.step_access, self.step_chat):
            step.set_palette(palette)
        self.demo_button.setIcon(icons.icon("sparkles", palette.text, 15))
        self.settings_button.setIcon(icons.icon("settings", palette.text_muted, 15))
        self.open_button.setIcon(icons.icon("folder_plus", palette.text_on_accent, 15))
        for index in range(self.recent_box.count()):
            widget = self.recent_box.itemAt(index).widget()
            if isinstance(widget, type(self.demo_button)) and widget.objectName() == "Chip":
                widget.setIcon(icons.icon("folder", palette.text_muted, 12))
