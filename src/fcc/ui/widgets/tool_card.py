"""The collapsible card that shows one Claude Code tool call, live."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)

from fcc import icons
from fcc.claude import toolmeta
from fcc.claude.toolmeta import ToolDetail
from fcc.i18n import tr
from fcc.ui.common import Spinner, button, copy_to_clipboard, elide, label, props, tool_button
from fcc.ui.widgets.detail_views import DetailBody
from fcc.ui.widgets.markdown_view import MarkdownView

RUNNING = "running"
DONE = "done"
ERROR = "error"
DENIED = "denied"


class ToolCard(QFrame):
    """One tool call: what Claude wants to do, what happened, how long it took."""

    expandToggled = Signal(object, bool)
    rawRequested = Signal(object)

    def __init__(self, tool_use_id: str, name: str, tool_input: Optional[Dict[str, Any]] = None,
                 parent_tool_use_id: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.tool_use_id = tool_use_id
        self.name = name or "tool"
        self.input = tool_input or {}
        self.parent_tool_use_id = parent_tool_use_id or ""
        self.state = RUNNING
        self.started_at = time.time()
        self.finished_at = 0.0
        self.detail_input: Optional[ToolDetail] = None
        self.detail_output: Optional[ToolDetail] = None
        self.raw_events: list = []
        self._expanded = False
        self._palette = None
        self.setObjectName("ToolCard")
        props(self, state=RUNNING)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(7)

        # ---- header ---- #
        self.header = QWidget()
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(9)

        self.icon_box = QLabel()
        self.icon_box.setFixedSize(26, 26)
        self.icon_box.setAlignment(Qt.AlignCenter)
        head.addWidget(self.icon_box, 0, Qt.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(1)
        self.title_label = QLabel()
        self.title_label.setObjectName("ToolTitle")
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_column.addWidget(self.title_label)
        self.subject_label = QLabel()
        self.subject_label.setObjectName("ToolMeta")
        self.subject_label.setProperty("mono", True)
        self.subject_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_column.addWidget(self.subject_label)
        head.addLayout(text_column, 1)

        self.badge_subagent = QLabel()
        self.badge_subagent.setPixmap(icons.pixmap("agent", "#9C9A91", 13))
        self.badge_subagent.setToolTip(tr("tool.subagent"))
        self.badge_subagent.setVisible(bool(self.parent_tool_use_id))
        head.addWidget(self.badge_subagent)

        self.spinner = Spinner(13)
        head.addWidget(self.spinner)

        self.status_label = QLabel()
        self.status_label.setObjectName("ToolMeta")
        head.addWidget(self.status_label)

        self.duration_label = QLabel()
        self.duration_label.setObjectName("ToolMeta")
        head.addWidget(self.duration_label)

        self.chevron = QLabel()
        self.chevron.setFixedSize(16, 16)
        self.chevron.setAlignment(Qt.AlignCenter)
        head.addWidget(self.chevron)
        outer.addWidget(self.header)

        # ---- body ---- #
        self.body = QWidget()
        self.body_box = QVBoxLayout(self.body)
        self.body_box.setContentsMargins(0, 2, 0, 0)
        self.body_box.setSpacing(7)
        self.input_body = DetailBody()
        self.input_body.expandRequested.connect(self._on_expand_request)
        self.output_body = DetailBody()
        self.output_body.expandRequested.connect(self._on_expand_request)
        self.input_caption = QLabel()
        self.output_caption = QLabel()
        for caption in (self.input_caption, self.output_caption):
            caption.setObjectName("ToolMeta")
            caption.setProperty("faint", True)
        self.body_box.addWidget(self.input_caption)
        self.body_box.addWidget(self.input_body)
        self.body_box.addWidget(self.output_caption)
        self.body_box.addWidget(self.output_body)

        self.footer = QWidget()
        footer_box = QHBoxLayout(self.footer)
        footer_box.setContentsMargins(0, 0, 0, 0)
        footer_box.setSpacing(4)
        self.copy_button = tool_button("copy", size=13, tooltip=tr("common.copy"),
                                       clicked=self.copy_output)
        self.raw_button = tool_button("log", size=13, tooltip=tr("chat.raw_events"),
                                      clicked=lambda: self.rawRequested.emit(self))
        footer_box.addStretch(1)
        footer_box.addWidget(self.copy_button)
        footer_box.addWidget(self.raw_button)
        self.body_box.addWidget(self.footer)
        self.body.setVisible(False)
        outer.addWidget(self.body)

        self.header.mousePressEvent = self._on_header_click  # type: ignore[assignment]

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.refresh()

    # ------------------------------------------------------------------ #
    def _on_header_click(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton:
            self.toggle()

    def _on_expand_request(self, expanded: bool) -> None:
        self._detail_expanded = expanded
        self.input_body.set_expanded(expanded)
        self.output_body.set_expanded(expanded)

    def toggle(self, force: Optional[bool] = None) -> None:
        self._expanded = force if force is not None else not self._expanded
        self.body.setVisible(self._expanded)
        self.expandToggled.emit(self, self._expanded)
        self.refresh()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_state(self, state: str) -> None:
        self.state = state
        props(self, state=state)
        if state == RUNNING:
            self.spinner.start()
            self._timer.start()
        else:
            self.spinner.stop()
            self.spinner.setVisible(False)
            self._timer.stop()
            self.finished_at = time.time()
        self.refresh()

    def set_input(self, tool_input: Dict[str, Any]) -> None:
        self.input = tool_input or {}
        self.detail_input = toolmeta.describe_input(self.name, self.input)
        self.refresh()

    def append_input_json(self, partial: str) -> None:
        """Live-stream the arguments while Claude is still writing them."""
        self._partial_json = getattr(self, "_partial_json", "") + (partial or "")
        text = self._partial_json
        if self._expanded:
            self.output_body.set_detail(ToolDetail(kind="json", title="Arguments", body=text, language="json"))

    def set_result(self, content: Any, structured: Any = None, is_error: bool = False,
                   decision: str = "") -> None:
        self.detail_output = toolmeta.describe_output(self.name, self.input, content, structured)
        self.result_is_error = bool(is_error)
        self.permission_decision = decision or ""
        if decision in ("reject", "deny") or str(structured or "").startswith("Error: Claude requested permissions"):
            self.set_state(DENIED)
        elif is_error:
            self.set_state(ERROR)
        else:
            self.set_state(DONE)
        if not self._expanded and self.detail_output is not None and not self.detail_output.is_empty:
            pass

    def add_raw(self, payload: Dict[str, Any]) -> None:
        self.raw_events.append(payload)
        if len(self.raw_events) > 40:
            self.raw_events = self.raw_events[-40:]

    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)

    def _tick(self) -> None:
        self.duration_label.setText(self._duration_text())

    def _duration_text(self) -> str:
        seconds = self.elapsed()
        if seconds < 1:
            return ""
        if seconds < 60:
            return f"{seconds:.1f}s"
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"

    def copy_output(self) -> None:
        parts = [toolmeta.title_for(self.name, self.input)]
        detail = self.detail_output or self.detail_input
        if detail is not None:
            parts.append(self.output_body.as_text() if self.detail_output else self.input_body.as_text())
        copy_to_clipboard("\n\n".join(part for part in parts if part))

    def as_text(self) -> str:
        detail = self.detail_output or self.detail_input
        body = ""
        if detail is not None:
            body = detail.body or "\n".join(f"{k}: {v}" for k, v in detail.rows)
        return f"[{self.name}] {toolmeta.title_for(self.name, self.input)}\n{body}".strip()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        palette = self._palette
        accent = palette.accent if palette else "#D97757"
        muted = palette.text_muted if palette else "#6E6C65"
        faint = palette.text_faint if palette else "#9C9A91"
        surface_alt = palette.surface_alt if palette else "#F3F1EA"
        title = toolmeta.title_for(self.name, self.input)
        self.title_label.setText(title)
        subject = toolmeta.subtitle_for(self.name, self.input) or toolmeta.subject_for(self.name, self.input)
        self.subject_label.setText(elide(subject, 110))
        self.subject_label.setVisible(bool(subject))

        color = {RUNNING: accent, DONE: (palette.success if palette else "#4C8C4A"),
                 ERROR: (palette.danger if palette else "#B3453B"),
                 DENIED: (palette.warn if palette else "#B4801F")}[self.state]
        self.icon_box.setPixmap(icons.pixmap(toolmeta.icon_name(self.name), color, 18))
        self.icon_box.setStyleSheet(
            f"background-color: {surface_alt}; border-radius: 7px; border: 1px solid "
            f"{palette.border if palette else '#E3E1D8'};"
        )
        text = {RUNNING: tr("tool.running"), DONE: tr("tool.finished"),
                ERROR: tr("tool.failed"), DENIED: tr("tool.denied")}[self.state]
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.duration_label.setText(self._duration_text())
        self.duration_label.setStyleSheet(f"color: {faint};")
        self.chevron.setPixmap(icons.pixmap("chevron_up" if self._expanded else "chevron_down", faint, 14))
        self.spinner.set_color(accent)

        self.input_caption.setText(tr("tool.input"))
        self.output_caption.setText(tr("tool.output"))
        self.input_body.set_detail(self.detail_input)
        self.output_body.set_detail(self.detail_output)
        self.input_caption.setVisible(self.detail_input is not None and not self.detail_input.is_empty)
        self.input_body.setVisible(self.detail_input is not None and not self.detail_input.is_empty)
        self.output_caption.setVisible(self.detail_output is not None and not self.detail_output.is_empty)
        self.output_body.setVisible(self.detail_output is not None and not self.detail_output.is_empty)
        self.badge_subagent.setVisible(bool(self.parent_tool_use_id))

    def set_palette(self, palette, font_size: int = 14) -> None:
        self._palette = palette
        self.input_body.set_palette(palette, font_size)
        self.output_body.set_palette(palette, font_size)
        self.copy_button.setIcon(icons.icon("copy", palette.text_muted, 13))
        self.raw_button.setIcon(icons.icon("log", palette.text_muted, 13))
        self.input_caption.setStyleSheet(f"color: {palette.text_faint}; font-size: {max(9, font_size - 4)}px;"
                                         " font-weight: 700; letter-spacing: 0.6px;")
        self.output_caption.setStyleSheet(self.input_caption.styleSheet())
        self.refresh()


class PermissionCard(QFrame):
    """Inline approval request with Allow / Always allow / Deny."""

    decided = Signal(object, str, str, str)  # card, behavior, remember-scope, message

    def __init__(self, ask, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ask = ask
        self.answered = False
        self.setObjectName("PermissionCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(9)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap("shield_alert", "#B4801F", 18))
        head_box.addWidget(self.icon_label)
        self.title_label = label(tr("perm.request_title"), bold=True)
        head_box.addWidget(self.title_label)
        head_box.addStretch(1)
        self.spinner = Spinner(13, "#B4801F")
        head_box.addWidget(self.spinner)
        outer.addWidget(head)

        self.subject_row = QWidget()
        subject_box = QHBoxLayout(self.subject_row)
        subject_box.setContentsMargins(0, 0, 0, 0)
        subject_box.setSpacing(8)
        self.tool_pill = QLabel()
        subject_box.addWidget(self.tool_pill)
        self.subject_label = label("", wrap=True)
        self.subject_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        subject_box.addWidget(self.subject_label, 1)
        outer.addWidget(self.subject_row)

        self.detail = DetailBody()
        outer.addWidget(self.detail)

        self.reason_edit = None
        self.buttons = QWidget()
        button_box = QHBoxLayout(self.buttons)
        button_box.setContentsMargins(0, 0, 0, 0)
        button_box.setSpacing(8)
        self.allow_button = button(tr("perm.allow_once"), "check", primary=True, size=15,
                                   clicked=lambda: self.decide("allow", ""))
        self.always_button = button(tr("perm.allow_always"), "shield", size=15,
                                    clicked=lambda: self.decide("allow", "project"))
        self.deny_button = button(tr("perm.deny_once"), "x", danger=True, size=15,
                                  clicked=lambda: self.decide("deny", ""))
        self.reason_button = tool_button("chat", size=14, tooltip=tr("perm.deny_reason"),
                                         clicked=self._toggle_reason)
        button_box.addWidget(self.allow_button)
        button_box.addWidget(self.always_button)
        button_box.addStretch(1)
        button_box.addWidget(self.reason_button)
        button_box.addWidget(self.deny_button)
        outer.addWidget(self.buttons)

        self.outcome = label("", faint=True)
        self.outcome.setVisible(False)
        outer.addWidget(self.outcome)

        self.refresh()

    # ------------------------------------------------------------------ #
    def _toggle_reason(self) -> None:
        from PySide6.QtWidgets import QLineEdit

        if self.reason_edit is None:
            self.reason_edit = QLineEdit()
            self.reason_edit.setPlaceholderText(tr("perm.deny_reason"))
            layout = self.layout()
            layout.insertWidget(layout.count() - 1, self.reason_edit)
        self.reason_edit.setVisible(not self.reason_edit.isVisible())
        if self.reason_edit.isVisible():
            self.reason_edit.setFocus()

    def reason(self) -> str:
        return self.reason_edit.text().strip() if self.reason_edit is not None else ""

    def decide(self, behavior: str, remember: str) -> None:
        if self.answered:
            return
        self.answered = True
        self.spinner.stop()
        self.spinner.setVisible(False)
        self.buttons.setVisible(False)
        if self.reason_edit is not None:
            self.reason_edit.setVisible(False)
        self.outcome.setVisible(True)
        if behavior == "allow":
            self.outcome.setText(tr("perm.decided_allow") + (f" · {tr(SCOPE_KEYS[remember])}" if remember else ""))
            self.setObjectName("ToolCard")
        else:
            message = self.reason() or ""
            self.outcome.setText(tr("perm.decided_deny") + (f" · {message}" if message else ""))
        props(self, state=DENIED if behavior == "deny" else DONE)
        self.decided.emit(self, behavior, remember, self.reason())

    def cancel(self, reason: str = "") -> None:
        if self.answered:
            return
        self.answered = True
        self.spinner.stop()
        self.spinner.setVisible(False)
        self.buttons.setVisible(False)
        self.outcome.setVisible(True)
        self.outcome.setText(reason or tr("chat.interrupted"))

    def refresh(self) -> None:
        from fcc.claude.toolmeta import describe_input, subject_for

        self.tool_pill.setPixmap(icons.pixmap(toolmeta.icon_name(self.ask.tool_name), "#B4801F", 16))
        self.subject_label.setText(toolmeta.title_for(self.ask.tool_name, self.ask.tool_input))
        font = self.subject_label.font()
        font.setWeight(QFont.DemiBold)
        self.subject_label.setFont(font)
        self.detail.set_detail(describe_input(self.ask.tool_name, self.ask.tool_input))
        if self.ask.decision_reason:
            self.title_label.setToolTip(self.ask.decision_reason)

    def set_palette(self, palette, font_size: int = 14) -> None:
        self._palette = palette
        color = palette.warn
        self.icon_label.setPixmap(icons.pixmap("shield_alert", color, 18))
        self.tool_pill.setPixmap(icons.pixmap(toolmeta.icon_name(self.ask.tool_name), color, 16))
        self.spinner.set_color(color)
        self.detail.set_palette(palette, font_size)
        self.allow_button.setIcon(icons.icon("check", "#FFFFFF", 15))
        self.always_button.setIcon(icons.icon("shield", palette.text, 15))
        self.deny_button.setIcon(icons.icon("x", palette.danger, 15))
        self.reason_button.setIcon(icons.icon("chat", palette.text_muted, 14))
        self.outcome.setStyleSheet(f"color: {palette.text_faint};")
        self.title_label.setStyleSheet(f"color: {palette.text};")


SCOPE_KEYS = {
    "session": "perm.scope_session",
    "project": "perm.scope_project",
    "global": "perm.scope_global",
    "": "perm.allow_once",
}
