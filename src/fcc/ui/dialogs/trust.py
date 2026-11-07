"""The folder-access approval dialog."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QVBoxLayout, QWidget)

from fcc import icons
from fcc.config import PERMISSION_MODES
from fcc.i18n import tr
from fcc.ui.common import button, hline, label


class TrustDialog(QDialog):
    """Explicit consent before Claude Code touches a folder."""

    def __init__(self, path: str, mode: str = "default", trusted: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.path = path
        self.granted = False
        self.mode = mode if mode in PERMISSION_MODES else "default"
        self.remember = True
        self.setWindowTitle(tr("project.trust_title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setMaximumWidth(720)
        self.setObjectName("Modal")
        self._palette = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setObjectName("ModalCard")
        outer.addWidget(card)
        box = QVBoxLayout(card)
        box.setContentsMargins(26, 24, 26, 22)
        box.setSpacing(14)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(13)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(46, 46)
        self.icon_label.setAlignment(Qt.AlignCenter)
        head_box.addWidget(self.icon_label)
        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(3)
        self.title_label = QLabel(tr("project.trust_title"))
        self.title_label.setObjectName("ModalTitle")
        title_column.addWidget(self.title_label)
        self.subtitle_label = label(tr("perm.folder_access"), muted=True)
        title_column.addWidget(self.subtitle_label)
        head_box.addLayout(title_column, 1)
        box.addWidget(head)

        self.path_frame = QFrame()
        self.path_frame.setObjectName("SunkenCard")
        path_box = QHBoxLayout(self.path_frame)
        path_box.setContentsMargins(12, 10, 12, 10)
        path_box.setSpacing(9)
        self.path_icon = QLabel()
        self.path_icon.setPixmap(icons.pixmap("folder", "#6E6C65", 17))
        path_box.addWidget(self.path_icon)
        self.path_label = QLabel(self.path)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setWordWrap(True)
        font = self.path_label.font()
        font.setFamily("Consolas")
        self.path_label.setFont(font)
        path_box.addWidget(self.path_label, 1)
        box.addWidget(self.path_frame)

        try:
            body_text = tr("project.trust_body").format(path=self.path)
        except (KeyError, IndexError, ValueError):
            body_text = f"{tr('project.trust_body')} — {self.path}"
        self.body_label = label(body_text, wrap=True, muted=True)
        box.addWidget(self.body_label)

        box.addWidget(hline())

        mode_head = QWidget()
        mode_box = QHBoxLayout(mode_head)
        mode_box.setContentsMargins(0, 0, 0, 0)
        self.mode_title = label(tr("perm.mode"), bold=True)
        mode_box.addWidget(self.mode_title)
        mode_box.addStretch(1)
        self.mode_combo = QComboBox()
        for value in PERMISSION_MODES:
            self.mode_combo.addItem(tr(f"perm.mode.{value}"), value)
        index = self.mode_combo.findData(self.mode)
        self.mode_combo.setCurrentIndex(max(0, index))
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        mode_box.addWidget(self.mode_combo)
        box.addWidget(mode_head)

        self.mode_warning = label(tr("perm.mode_warn"), wrap=True, faint=True)
        self.mode_warning.setVisible(False)
        box.addWidget(self.mode_warning)

        self.remember_check = QCheckBox(tr("project.trusted"))
        self.remember_check.setChecked(True)
        box.addWidget(self.remember_check)

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 4, 0, 0)
        action_box.setSpacing(9)
        action_box.addStretch(1)
        self.reject_button = button(tr("project.trust_deny"), ghost=True, size=15, clicked=self.reject)
        self.allow_button = button(tr("project.trust_allow"), "check", primary=True, size=15,
                                   clicked=self._allow)
        action_box.addWidget(self.reject_button)
        action_box.addWidget(self.allow_button)
        box.addWidget(actions)

        self._mode_changed()

    # ------------------------------------------------------------------ #
    def _mode_changed(self) -> None:
        value = str(self.mode_combo.currentData() or "default")
        self.mode = value if value in PERMISSION_MODES else "default"
        risky = self.mode in ("bypassPermissions", "dontAsk", "acceptEdits")
        self.mode_warning.setVisible(risky)
        if self.mode == "bypassPermissions":
            self.mode_warning.setText(tr("perm.mode_warn"))
            self.mode_warning.setStyleSheet("color: #B3453B;")
        elif self.mode == "acceptEdits":
            self.mode_warning.setText(tr("perm.mode.acceptEdits"))
            self.mode_warning.setStyleSheet("color: #B4801F;")
        else:
            self.mode_warning.setText(tr("perm.mode.dontAsk"))
            self.mode_warning.setStyleSheet("color: #B4801F;")

    def _allow(self) -> None:
        self.granted = True
        self.remember = self.remember_check.isChecked()
        self.accept()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.setStyleSheet(f"QDialog#Modal {{ background-color: {palette.bg}; }}")
        self.icon_label.setPixmap(icons.pixmap("shield", palette.accent, 26))
        self.icon_label.setStyleSheet(
            f"background-color: {palette.accent_soft}; border-radius: 14px;"
        )
        self.title_label.setStyleSheet(f"color: {palette.text};")
        self.subtitle_label.setStyleSheet(f"color: {palette.text_muted};")
        self.path_frame.setStyleSheet(
            f"QFrame#SunkenCard {{ background-color: {palette.surface_sunken};"
            f" border: 1px solid {palette.border}; border-radius: 10px; }}"
        )
        self.path_label.setStyleSheet(f"color: {palette.text};")
        self.path_icon.setPixmap(icons.pixmap("folder", palette.accent, 17))
        self.body_label.setStyleSheet(f"color: {palette.text_muted};")
        self.mode_title.setStyleSheet(f"color: {palette.text};")
        self.allow_button.setIcon(icons.icon("check", palette.text_on_accent, 15))
