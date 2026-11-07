"""The conversation surface: maps stream events onto chat widgets."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from fcc import icons
from fcc.claude import protocol, toolmeta
from fcc.claude.control import PermissionAsk
from fcc.i18n import tr
from fcc.ui.common import button, label, props
from fcc.ui.widgets.markdown_view import MarkdownView
from fcc.ui.widgets.message_items import (AssistantMessage, NoticeItem, TurnSeparator, UserMessage)
from fcc.ui.widgets.tool_card import PermissionCard, ToolCard

NEAR_BOTTOM = 60


class EmptyState(QFrame):
    """Shown before the first message of a conversation."""

    suggestionPicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(30, 40, 30, 40)
        box.setSpacing(14)
        box.addStretch(1)
        self.mark = QWidget()
        mark_box = QHBoxLayout(self.mark)
        mark_box.setContentsMargins(0, 0, 0, 0)
        mark_box.addStretch(1)
        self.mark_label = QLabelHolder(56)
        mark_box.addWidget(self.mark_label)
        mark_box.addStretch(1)
        box.addWidget(self.mark)
        self.title = label(tr("chat.empty_title"), align=Qt.AlignCenter)
        self.title.setObjectName("ModalTitle")
        box.addWidget(self.title)
        self.body = label(tr("chat.empty_body"), wrap=True, muted=True, align=Qt.AlignCenter)
        box.addWidget(self.body)
        self.chips = QWidget()
        chip_box = QHBoxLayout(self.chips)
        chip_box.setContentsMargins(0, 8, 0, 0)
        chip_box.setSpacing(8)
        chip_box.addStretch(1)
        self._chip_buttons: List[QWidget] = []
        for key in ("chat.suggestion1", "chat.suggestion2", "chat.suggestion3", "chat.suggestion4"):
            chip = button(tr(key), "sparkles", size=13,
                          clicked=lambda _=False, text=tr(key): self.suggestionPicked.emit(text))
            chip.setObjectName("Chip")
            chip.setCursor(Qt.PointingHandCursor)
            self._chip_buttons.append(chip)
            chip_box.addWidget(chip)
        chip_box.addStretch(1)
        chip_box.setSpacing(8)
        box.addWidget(self.chips)
        box.addStretch(2)

    def set_palette(self, palette) -> None:
        self.mark_label.set_color(palette.accent, palette.accent_soft)
        self.title.setStyleSheet(f"color: {palette.text};")
        self.body.setStyleSheet(f"color: {palette.text_muted}; max-width: 520px;")


class QLabelHolder(QFrame):
    """Big rounded spark badge for the empty state."""

    def __init__(self, size: int = 56, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size = size
        self._color = "#D97757"
        self._bg = "#F7E7DF"
        self.setFixedSize(size, size)
        self._repaint()

    def set_color(self, color: str, bg: str) -> None:
        self._color, self._bg = color, bg
        self._repaint()

    def _repaint(self) -> None:
        from PySide6.QtGui import QColor, QPainter, QPixmap

        scale = 2
        pixmap = QPixmap(self._size * scale, self._size * scale)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._bg))
        painter.drawRoundedRect(0, 0, pixmap.width(), pixmap.height(),
                                self._size * 0.32 * scale, self._size * 0.32 * scale)
        painter.end()
        mark = icons.pixmap("spark", self._color, int(self._size * 0.62 * scale), stroke_width=2.0)
        painter = QPainter(pixmap)
        painter.drawPixmap(int((pixmap.width() - mark.width()) / 2),
                           int((pixmap.height() - mark.height()) / 2), mark)
        painter.end()
        self._pixmap = pixmap.scaled(self._size, self._size, Qt.KeepAspectRatio,
                                     Qt.SmoothTransformation)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()


class ChatView(QScrollArea):
    """Owns the message list and turns protocol events into widgets."""

    permissionDecided = Signal(object, str, str, str)  # ask, behavior, remember, message
    jumpRequested = Signal()
    retryRequested = Signal()
    rawRequested = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.container = QWidget()
        self.layout_box = QVBoxLayout(self.container)
        self.layout_box.setContentsMargins(0, 10, 0, 16)
        self.layout_box.setSpacing(2)
        self.setWidget(self.container)

        self.items: List[QWidget] = []
        self._assistant: Dict[str, AssistantMessage] = {}
        self._tools: Dict[str, ToolCard] = {}
        self._permissions: Dict[str, PermissionCard] = {}
        self._current_assistant: Optional[AssistantMessage] = None
        self._palette = None
        self._stick = True
        self._empty = EmptyState()
        self._empty.suggestionPicked.connect(lambda text: self.jumpRequested.emit())
        self.suggestionPicked = self._empty.suggestionPicked
        self.layout_box.addWidget(self._empty)
        self.layout_box.addStretch(1)

        self.jump_button = button("Jump to latest", "chevron_down", size=14)
        self.jump_button.setObjectName("Chip")
        self.jump_button.setCursor(Qt.PointingHandCursor)
        self.jump_button.setParent(self.viewport())
        self.jump_button.hide()
        self.jump_button.clicked.connect(self.scroll_to_bottom)

        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().rangeChanged.connect(self._on_range)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(60)
        self._scroll_timer.timeout.connect(self._stick_if_needed)

    # ------------------------------------------------------------------ #
    def _spacer_index(self) -> int:
        return self.layout_box.count() - 1

    def _add(self, widget: QWidget) -> None:
        self._empty.setVisible(False)
        self.layout_box.insertWidget(self._spacer_index(), widget)
        self.items.append(widget)
        if self._palette is not None and hasattr(widget, "set_palette"):
            try:
                widget.set_palette(self._palette)
            except TypeError:
                widget.set_palette(self._palette, 14)
        self._scroll_timer.start()

    def _on_scroll(self, value: int) -> None:
        maximum = self.verticalScrollBar().maximum()
        self._stick = value >= maximum - NEAR_BOTTOM
        self.jump_button.setVisible(not self._stick and bool(self.items))

    def _on_range(self, _min: int, _max: int) -> None:
        if self._stick:
            self.verticalScrollBar().setValue(_max)
        self._place_jump_button()

    def _stick_if_needed(self) -> None:
        if self._stick:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        self._place_jump_button()

    def _place_jump_button(self) -> None:
        if not self.jump_button.isVisible():
            return
        self.jump_button.adjustSize()
        x = int((self.viewport().width() - self.jump_button.width()) / 2)
        y = int(self.viewport().height() - self.jump_button.height() - 14)
        self.jump_button.move(max(8, x), max(8, y))
        self.jump_button.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_jump_button()

    def scroll_to_bottom(self) -> None:
        self._stick = True
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        self.jump_button.hide()

    # ------------------------------------------------------------------ #
    # content
    # ------------------------------------------------------------------ #
    def add_user(self, text: str, attachments: Optional[List[Dict[str, Any]]] = None) -> UserMessage:
        item = UserMessage(text, attachments)
        item.editRequested.connect(self._on_edit)
        self._add(item)
        self._current_assistant = None
        return item

    def _on_edit(self, text: str) -> None:
        self.retryRequested.emit()

    def add_notice(self, title: str, message: str, level: str = "info", icon_name: str = "") -> NoticeItem:
        item = NoticeItem(title, message, level, icon_name)
        self._add(item)
        return item

    def add_separator(self, text: str = "") -> TurnSeparator:
        item = TurnSeparator(text)
        self._add(item)
        return item

    def assistant_for(self, message_id: str) -> AssistantMessage:
        existing = self._assistant.get(message_id)
        if existing is not None:
            return existing
        item = AssistantMessage(message_id)
        item.retryRequested.connect(self.retryRequested.emit)
        self._assistant[message_id] = item
        self._add(item)
        self._current_assistant = item
        return item

    def current_assistant(self, message_id: str = "") -> AssistantMessage:
        if message_id and message_id in self._assistant:
            return self._assistant[message_id]
        if self._current_assistant is not None:
            return self._current_assistant
        return self.assistant_for(message_id or f"local-{int(time.time() * 1000)}")

    def add_tool(self, tool_use_id: str, name: str, tool_input: Dict[str, Any],
                 parent_tool_use_id: str = "") -> ToolCard:
        existing = self._tools.get(tool_use_id)
        if existing is not None:
            return existing
        card = ToolCard(tool_use_id, name, tool_input, parent_tool_use_id)
        card.rawRequested.connect(self.rawRequested.emit)
        card.expandToggled.connect(self._on_tool_toggled)
        self._tools[tool_use_id] = card
        self._add(card)
        if name.lower() in ("bash", "write", "edit", "multiedit", "task", "agent"):
            card.toggle(True)
        return card

    def _on_tool_toggled(self, card: ToolCard, expanded: bool) -> None:
        if expanded:
            for other in self._tools.values():
                if other is not card and other.is_expanded():
                    other.toggle(False)

    def add_permission(self, ask: PermissionAsk) -> PermissionCard:
        card = PermissionCard(ask)
        card.decided.connect(self.permissionDecided.emit)
        self._permissions[ask.id] = card
        self._add(card)
        card.toggle = None  # type: ignore[assignment]
        return card

    def permission_card(self, ask_id: str) -> Optional[PermissionCard]:
        return self._permissions.get(ask_id)

    def add_todos(self, items: List[Dict[str, Any]]) -> None:
        card = self.add_tool(f"todos-{int(time.time() * 1000)}", "TodoWrite", {"todos": items})
        card.set_input({"todos": items})
        card.set_result([{"type": "text", "text": ""}], {"newTodos": items}, False)
        card.toggle(False)

    # ------------------------------------------------------------------ #
    # protocol plumbing
    # ------------------------------------------------------------------ #
    def handle(self, event: protocol.UiEvent) -> None:
        kind = event.kind
        payload = event.payload
        if kind == protocol.TEXT_DELTA:
            item = self.assistant_for(payload.get("message_id", ""))
            item.append_text(payload.get("text", ""))
        elif kind == protocol.THINKING_DELTA:
            item = self.assistant_for(payload.get("message_id", ""))
            item.append_thinking(payload.get("text", ""))
        elif kind == protocol.MESSAGE_FINAL:
            item = self.assistant_for(payload.get("message_id", ""))
            item.set_text(payload.get("text", ""), final=not payload.get("is_error", False))
            if payload.get("thinking"):
                item.append_thinking("")
            if payload.get("model"):
                item.model = payload["model"]
            if payload.get("is_error"):
                item.set_error(payload.get("error_code") or "error")
        elif kind == protocol.MESSAGE_END and payload.get("phase") == "stop":
            item = self._assistant.get(payload.get("message_id", ""))
            if item is not None:
                item.finish(item.model)
        elif kind == protocol.TOOL_START:
            card = self.add_tool(payload.get("tool_use_id", ""), payload.get("name", ""),
                                 payload.get("input") or {}, payload.get("parent_tool_use_id", ""))
            if not payload.get("partial"):
                card.set_input(payload.get("input") or {})
            self._collapse_assistant_stream(payload.get("message_id", ""))
        elif kind == protocol.TOOL_INPUT_DELTA:
            card = self._tools.get(payload.get("tool_use_id", ""))
            if card is not None:
                card.append_input_json(payload.get("partial_json", ""))
        elif kind == protocol.TOOL_RESULT:
            card = self._tools.get(payload.get("tool_use_id", ""))
            if card is None:
                card = self.add_tool(payload.get("tool_use_id", ""), payload.get("name", ""),
                                     payload.get("input") or {}, payload.get("parent_tool_use_id", ""))
            card.set_result(payload.get("content"), payload.get("structured"),
                            bool(payload.get("is_error")), str(payload.get("permission_decision") or ""))
            card.add_raw({"result": str(payload.get("content"))[:2000],
                          "decision": payload.get("permission_decision", "")})
            card.toggle(False)
        elif kind == protocol.PERMISSION_DENIED:
            self.add_notice(tr("perm.decided_deny"), payload.get("message", ""), "warn", "shield_alert")
            card = self._tools.get(payload.get("tool_use_id", ""))
            if card is not None:
                card.set_state("denied")
        elif kind == protocol.TODOS:
            self.add_todos(payload.get("items") or [])
        elif kind == protocol.PLAN:
            self.add_notice(tr("tool.plan"), payload.get("plan", ""), "info", "compass")
        elif kind == protocol.NOTICE:
            level = {"error": "error", "warn": "warn"}.get(str(payload.get("level", "info")), "info")
            if payload.get("notice") == "permission_ask":
                return
            self.add_notice(str(payload.get("title", "")), str(payload.get("message", "")), level)
        elif kind == protocol.USER_ECHO:
            text = str(payload.get("text", "")).strip()
            if text:
                self.add_user(text)
        elif kind == protocol.TURN_DONE:
            self._finish_turn(payload)
        elif kind == protocol.ERROR:
            code = payload.get("code", "error")
            self.add_notice(tr("error.generic_title"), str(payload.get("message", "")),
                            "error" if code != "warn" else "warn", "warning")
        elif kind == protocol.SESSION_INIT:
            self.add_notice(tr("cli.found"),
                            f"{payload.get('model', '')} · {len(payload.get('tools') or [])} tools · "
                            f"v{payload.get('cli_version', '')}", "success", "check_circle")

    def _collapse_assistant_stream(self, message_id: str) -> None:
        item = self._assistant.get(message_id)
        if item is not None and not item.is_empty():
            item.finish(item.model)

    def _finish_turn(self, payload: Dict[str, Any]) -> None:
        summary = protocol.summarize_result(payload)
        item = self._current_assistant
        if item is not None:
            item.finish()
            item.set_stats(
                f"{protocol.format_tokens(summary['tokens_in'])} in · "
                f"{protocol.format_tokens(summary['tokens_out'])} out · "
                f"{protocol.format_duration(summary['duration_ms'])} · "
                f"{protocol.format_cost(summary['cost_usd'])}"
            )
        text = (
            f"{summary['num_turns']} steps · {protocol.format_duration(summary['duration_ms'])} · "
            f"{protocol.format_cost(summary['cost_usd'])}"
        )
        if payload.get("is_error"):
            self.add_notice(tr("status.error"), str(payload.get("result_text") or "")[:400], "error", "warning")
        self.add_separator(text)
        self._current_assistant = None

    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        for widget in self.items:
            self.layout_box.removeWidget(widget)
            widget.deleteLater()
        self.items.clear()
        self._assistant.clear()
        self._tools.clear()
        self._permissions.clear()
        self._current_assistant = None
        self._empty.setVisible(True)

    def replay(self, events: List[protocol.UiEvent]) -> None:
        for event in events:
            self.handle(event)
        self.scroll_to_bottom()

    def set_palette(self, palette, font_size: int = 14) -> None:
        self._palette = palette
        self._empty.set_palette(palette)
        self.setStyleSheet(f"QScrollArea {{ background: {palette.bg}; border: none; }}")
        for widget in self.items:
            if hasattr(widget, "set_palette"):
                try:
                    widget.set_palette(palette, font_size)
                except TypeError:
                    widget.set_palette(palette)
        self.jump_button.setIcon(icons.icon("chevron_down", palette.text, 14))
        self.jump_button.setStyleSheet(
            f"background-color: {palette.surface}; border: 1px solid {palette.border_strong};"
            f" color: {palette.text}; border-radius: 14px; padding: 6px 14px;"
        )

    def export_markdown(self, title: str = "") -> str:
        from fcc import markdown as md

        out: List[str] = [f"# {title or tr('app.name')}", ""]
        for widget in self.items:
            if isinstance(widget, UserMessage):
                out.append(f"## {tr('chat.you')}\n\n{widget.text()}\n")
            elif isinstance(widget, AssistantMessage):
                if widget.text().strip():
                    out.append(f"## {tr('chat.claude')}\n\n{widget.text()}\n")
            elif isinstance(widget, ToolCard):
                out.append(f"> 🔧 {widget.as_text()}\n")
            elif isinstance(widget, NoticeItem):
                continue
            elif isinstance(widget, TurnSeparator):
                out.append("---\n")
        return "\n".join(out)
