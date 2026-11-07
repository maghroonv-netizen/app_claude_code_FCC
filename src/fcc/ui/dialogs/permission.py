"""Modal permission prompt (mirrors the inline card in the chat)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QVBoxLayout, QWidget)

from fcc import icons
from fcc.claude import toolmeta
from fcc.claude.control import PermissionAsk
from fcc.claude.permissions import rule_options
from fcc.i18n import tr
from fcc.ui.common import button, hline, label, tool_button
from fcc.ui.widgets.detail_views import DetailBody


class PermissionDialog(QDialog):
    """Blocking, window-level approval prompt with 'always allow' memory."""

    decided = Signal(object, str, str, str, str)  # ask, behavior, scope, pattern, message

    def __init__(self, ask: PermissionAsk, project_path: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ask = ask
        self.project_path = project_path
        self.answered = False
        self.behavior = "deny"
        self.scope = ""
        self.pattern = ""
        self.message = ""
        self.setWindowTitle(tr("perm.request_title"))
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setObjectName("Modal")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._palette = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setObjectName("ModalCard")
        outer.addWidget(card)
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(12)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(12)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignCenter)
        head_box.addWidget(self.icon_label)
        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)
        self.title_label = QLabel(tr("perm.request_title"))
        self.title_label.setObjectName("ModalTitle")
        title_column.addWidget(self.title_label)
        self.subject_label = QLabel(toolmeta.title_for(ask.tool_name, ask.tool_input))
        self.subject_label.setWordWrap(True)
        self.subject_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        font = self.subject_label.font()
        font.setWeight(QFont.DemiBold)
        self.subject_label.setFont(font)
        title_column.addWidget(self.subject_label)
        head_box.addLayout(title_column, 1)
        self.tool_pill = QLabel()
        head_box.addWidget(self.tool_pill, 0, Qt.AlignTop)
        box.addWidget(head)

        if ask.decision_reason:
            self.reason_label = label(ask.decision_reason, wrap=True, muted=True)
            box.addWidget(self.reason_label)

        self.detail = DetailBody()
        self.detail.set_detail(toolmeta.describe_input(ask.tool_name, ask.tool_input))
        scroll_frame = QFrame()
        scroll_frame.setObjectName("SunkenCard")
        scroll_layout = QVBoxLayout(scroll_frame)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.addWidget(self.detail)
        box.addWidget(scroll_frame)

        memory_row = QWidget()
        memory_box = QHBoxLayout(memory_row)
        memory_box.setContentsMargins(0, 0, 0, 0)
        memory_box.setSpacing(8)
        self.scope_label = label(tr("perm.allow_always"), muted=True)
        memory_box.addWidget(self.scope_label)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(tr("perm.scope_session"), "session")
        self.scope_combo.addItem(tr("perm.scope_project"), "project")
        self.scope_combo.addItem(tr("perm.scope_global"), "global")
        self.scope_combo.setCurrentIndex(1)
        memory_box.addWidget(self.scope_combo)
        self.pattern_combo = QComboBox()
        self.pattern_combo.setMinimumWidth(240)
        memory_box.addWidget(self.pattern_combo, 1)
        box.addWidget(memory_row)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText(tr("perm.deny_reason"))
        self.message_edit.setVisible(False)
        box.addWidget(self.message_edit)

        box.addWidget(hline())

        actions = QWidget()
        action_box = QHBoxLayout(actions)
        action_box.setContentsMargins(0, 2, 0, 0)
        action_box.setSpacing(8)
        self.deny_button = button(tr("perm.deny_once"), "x", danger=True, size=15,
                                  clicked=lambda: self._decide("deny", ""))
        self.message_button = tool_button("chat", size=14, tooltip=tr("perm.deny_reason"),
                                          clicked=self._toggle_message)
        action_box.addWidget(self.deny_button)
        action_box.addWidget(self.message_button)
        action_box.addStretch(1)
        self.always_button = button(tr("perm.allow_always"), "shield", size=15,
                                    clicked=self._always)
        self.allow_button = button(tr("perm.allow_once"), "check", primary=True, size=15,
                                   clicked=lambda: self._decide("allow", ""))
        action_box.addWidget(self.always_button)
        action_box.addWidget(self.allow_button)
        box.addWidget(actions)

        self._fill_patterns()

    # ------------------------------------------------------------------ #
    def _fill_patterns(self) -> None:
        self.pattern_combo.clear()
        for text, rule in rule_options(self.ask, self.project_path):
            self.pattern_combo.addItem(text, rule.pattern)

    def _toggle_message(self) -> None:
        self.message_edit.setVisible(not self.message_edit.isVisible())
        if self.message_edit.isVisible():
            self.message_edit.setFocus()

    def _always(self) -> None:
        scope = str(self.scope_combo.currentData() or "project")
        pattern = str(self.pattern_combo.currentData() or "*")
        self._decide("allow", scope, pattern)

    def _decide(self, behavior: str, scope: str = "", pattern: str = "") -> None:
        if self.answered:
            return
        self.answered = True
        self.behavior = behavior
        self.scope = scope
        self.pattern = pattern
        self.message = self.message_edit.text().strip() if behavior == "deny" else ""
        self.decided.emit(self.ask, behavior, scope, pattern, self.message)
        self.accept()

    def resolve_externally(self, behavior: str) -> None:
        """The inline card already answered — close without emitting again."""
        self.answered = True
        self.behavior = behavior
        self.close()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.setStyleSheet(f"QDialog#Modal {{ background-color: {palette.bg}; }}")
        self.icon_label.setPixmap(icons.pixmap("shield_alert", palette.warn, 24))
        self.icon_label.setStyleSheet(f"background-color: {palette.warn_soft}; border-radius: 13px;")
        self.title_label.setStyleSheet(f"color: {palette.text};")
        self.subject_label.setStyleSheet(f"color: {palette.text};")
        self.tool_pill.setText(self.ask.tool_name)
        self.tool_pill.setStyleSheet(
            f"color: {palette.text_muted}; background-color: {palette.surface_alt};"
            f" border: 1px solid {palette.border}; border-radius: 10px; padding: 3px 9px;"
        )
        self.detail.set_palette(palette, 13)
        self.deny_button.setIcon(icons.icon("x", palette.danger, 15))
        self.allow_button.setIcon(icons.icon("check", palette.text_on_accent, 15))
        self.always_button.setIcon(icons.icon("shield", palette.text, 15))
        self.message_button.setIcon(icons.icon("chat", palette.text_muted, 14))
        self.scope_label.setStyleSheet(f"color: {palette.text_muted};")
        scroll = self.detail.parentWidget().parentWidget()
        if isinstance(scroll, QFrame):
            scroll.setStyleSheet(
                f"QFrame#SunkenCard {{ background-color: {palette.surface_sunken};"
                f" border: 1px solid {palette.border}; border-radius: 12px; }}"
            )
