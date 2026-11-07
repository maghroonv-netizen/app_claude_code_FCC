"""Chat rows: user bubbles, assistant answers, thinking blocks and notices."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QSizePolicy, QVBoxLayout, QWidget)

from fcc import icons, markdown
from fcc.i18n import tr
from fcc.ui.common import (Pill, Spinner, button, copy_to_clipboard, hline, label, props,
                           spacer, stretch, tool_button)
from fcc.ui.widgets.markdown_view import MarkdownView

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


def _clock(timestamp: Optional[float] = None) -> str:
    return time.strftime("%H:%M", time.localtime(timestamp or time.time()))


class Avatar(QLabel):
    """Rounded Claude spark badge."""

    def __init__(self, size: int = 30, color: str = "#D97757", bg: str = "#F7E7DF",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self._color = color
        self._bg = bg
        self._repaint_avatar()

    def set_colors(self, color: str, bg: str) -> None:
        self._color, self._bg = color, bg
        self._repaint_avatar()

    def _repaint_avatar(self) -> None:
        from PySide6.QtGui import QColor, QPainter, QPixmap

        scale = 2
        pixmap = QPixmap(self._size * scale, self._size * scale)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor(self._bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, pixmap.width(), pixmap.height(), self._size * 0.34 * scale,
                                self._size * 0.34 * scale)
        painter.end()

        mark = icons.pixmap("spark", self._color, int(self._size * 0.66 * scale), stroke_width=2.1)
        painter = QPainter(pixmap)
        painter.drawPixmap(int((pixmap.width() - mark.width()) / 2),
                           int((pixmap.height() - mark.height()) / 2), mark)
        painter.end()
        self.setPixmap(pixmap.scaled(self._size, self._size, Qt.KeepAspectRatio,
                                     Qt.SmoothTransformation))


class ThinkingBlock(QFrame):
    """Collapsible extended-thinking stream."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SystemNote")
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(6)
        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(7)
        self.spinner = Spinner(13)
        head_box.addWidget(self.spinner)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap("brain", "#9C9A91", 14))
        head_box.addWidget(self.icon_label)
        self.title = label(tr("chat.thinking"), faint=True)
        head_box.addWidget(self.title)
        head_box.addStretch(1)
        self.chevron = tool_button("chevron_down", size=13, color="#9C9A91")
        self.chevron.clicked.connect(self.toggle)
        head_box.addWidget(self.chevron)
        box.addWidget(head)
        self.body = MarkdownView(streaming=True)
        self.body.setVisible(False)
        box.addWidget(self.body)
        self._text = ""
        self._open = False
        self.spinner.start()

    def append(self, text: str) -> None:
        self._text += text
        if self._open:
            self.body.set_markdown(self._text)

    def finish(self) -> None:
        self.spinner.stop()
        self.spinner.setVisible(False)
        self.icon_label.setPixmap(icons.pixmap("brain", "#9C9A91", 14))
        self.title.setText(f"{tr('chat.thinking')} · {len(self._text):,} chars")
        if not self._text:
            self.setVisible(False)

    def toggle(self) -> None:
        self._open = not self._open
        self.body.setVisible(self._open)
        self.chevron.setIcon(icons.icon("chevron_up" if self._open else "chevron_down", "#9C9A91", 13))
        if self._open:
            self.body.set_markdown(self._text)

    def set_palette(self, palette) -> None:
        self.body.set_palette(palette, 13)
        self.spinner.set_color(palette.accent)
        self.icon_label.setPixmap(icons.pixmap("brain", palette.text_faint, 14))
        self.chevron.setIcon(icons.icon("chevron_up" if self._open else "chevron_down", palette.text_faint, 13))


class AssistantMessage(QFrame):
    """One Claude answer: avatar, streaming markdown, thinking and actions."""

    retryRequested = Signal()
    rawRequested = Signal(object)

    def __init__(self, message_id: str = "", model: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.message_id = message_id
        self.model = model
        self.role = ROLE_ASSISTANT
        self.created_at = time.time()
        self._text = ""
        self._final = False
        self.setObjectName("ClaudeRow")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 10, 26, 10)
        outer.setSpacing(11)
        self.avatar = Avatar(30)
        outer.addWidget(self.avatar, 0, Qt.AlignTop)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        outer.addLayout(column, 1)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(8)
        self.name_label = label(tr("chat.claude"))
        font = self.name_label.font()
        font.setWeight(QFont.DemiBold)
        self.name_label.setFont(font)
        head_box.addWidget(self.name_label)
        self.model_pill = Pill("", "cpu", "#9C9A91", size=12)
        head_box.addWidget(self.model_pill)
        self.time_label = label(_clock(self.created_at), faint=True)
        head_box.addWidget(self.time_label)
        head_box.addStretch(1)
        self.spinner = Spinner(14)
        head_box.addWidget(self.spinner)
        self.copy_button = tool_button("copy", size=14, tooltip=tr("common.copy"))
        self.copy_button.clicked.connect(self.copy_text)
        self.retry_button = tool_button("refresh", size=14, tooltip=tr("chat.retry_last"))
        self.retry_button.clicked.connect(self.retryRequested.emit)
        head_box.addWidget(self.copy_button)
        head_box.addWidget(self.retry_button)
        column.addWidget(head)

        self.thinking = ThinkingBlock()
        self.thinking.setVisible(False)
        column.addWidget(self.thinking)

        self.view = MarkdownView(streaming=True)
        column.addWidget(self.view)

        self.error_row = QWidget()
        error_box = QHBoxLayout(self.error_row)
        error_box.setContentsMargins(0, 0, 0, 0)
        error_box.setSpacing(7)
        self.error_icon = QLabel()
        self.error_icon.setPixmap(icons.pixmap("warning", "#B3453B", 15))
        error_box.addWidget(self.error_icon)
        self.error_label = label("", wrap=True)
        error_box.addWidget(self.error_label, 1)
        self.error_row.setVisible(False)
        column.addWidget(self.error_row)

        self.stats_label = label("", faint=True)
        self.stats_label.setVisible(False)
        column.addWidget(self.stats_label)

        self.spinner.start()

    # ------------------------------------------------------------------ #
    def append_text(self, text: str) -> None:
        self._text += text
        self.view.set_markdown(self._text, streaming=True)

    def set_text(self, text: str, final: bool = True) -> None:
        self._text = text or ""
        self._final = final
        self.view.set_markdown(self._text, streaming=not final)
        if final:
            self.view.flush_now()
            self.spinner.stop()
            self.spinner.setVisible(False)

    def append_thinking(self, text: str) -> None:
        if not self.thinking.isVisible():
            self.thinking.setVisible(True)
        self.thinking.append(text)

    def finish(self, model: str = "") -> None:
        self.spinner.stop()
        self.spinner.setVisible(False)
        self.thinking.finish()
        self.view.flush_now()
        self._final = True
        if model:
            self.model = model
        self.model_pill.set_text(self.model or "")
        self.model_pill.setVisible(bool(self.model))

    def set_stats(self, text: str) -> None:
        if text:
            self.stats_label.setText(text)
            self.stats_label.setVisible(True)

    def set_error(self, message: str, level: str = "error") -> None:
        color = {"error": "#B3453B", "warn": "#B4801F", "auth": "#B3453B"}.get(level, "#6E6C65")
        self.error_icon.setPixmap(icons.pixmap("warning", color, 15))
        self.error_label.setText(message)
        self.error_label.setStyleSheet(f"color: {color};")
        self.error_row.setVisible(True)

    def copy_text(self) -> None:
        copy_to_clipboard(self.text())

    def text(self) -> str:
        return self._text

    def is_empty(self) -> bool:
        return not self._text.strip()

    def set_palette(self, palette) -> None:
        self.avatar.set_colors(palette.accent, palette.accent_soft)
        self.view.set_palette(palette, palette_font_size(palette))
        self.thinking.set_palette(palette)
        self.model_pill.set_color(palette.text_faint, "cpu")
        self.spinner.set_color(palette.accent)
        self.copy_button.setIcon(icons.icon("copy", palette.text_muted, 14))
        self.retry_button.setIcon(icons.icon("refresh", palette.text_muted, 14))
        self.name_label.setStyleSheet(f"color: {palette.text};")
        self.time_label.setStyleSheet(f"color: {palette.text_faint};")
        self.stats_label.setStyleSheet(f"color: {palette.text_faint};")


def palette_font_size(palette) -> int:
    return int(getattr(palette, "font_size", 0) or 14)


class UserMessage(QFrame):
    """A prompt you sent, right-aligned like a normal chat app."""

    editRequested = Signal(str)
    copyRequested = Signal(str)

    def __init__(self, text: str = "", attachments: Optional[List[Dict[str, Any]]] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.role = ROLE_USER
        self.created_at = time.time()
        self._text = text
        outer = QHBoxLayout(self)
        outer.setContentsMargins(60, 8, 18, 8)
        outer.setSpacing(0)
        outer.addStretch(1)

        self.bubble = QFrame()
        self.bubble.setObjectName("UserBubble")
        self.bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        self.bubble.setMaximumWidth(900)
        box = QVBoxLayout(self.bubble)
        box.setContentsMargins(14, 10, 14, 10)
        box.setSpacing(6)

        self.view = MarkdownView(streaming=False)
        self.view.set_markdown(text, streaming=False)
        box.addWidget(self.view)

        if attachments:
            self.attach_row = QWidget()
            attach_box = QHBoxLayout(self.attach_row)
            attach_box.setContentsMargins(0, 0, 0, 0)
            attach_box.setSpacing(6)
            for item in attachments:
                chip = Pill(item.get("name", "file"), "clip", "#6E6C65", size=12)
                attach_box.addWidget(chip)
            attach_box.addStretch(1)
            box.addWidget(self.attach_row)

        foot = QWidget()
        foot_box = QHBoxLayout(foot)
        foot_box.setContentsMargins(0, 0, 0, 0)
        foot_box.setSpacing(6)
        foot_box.addStretch(1)
        self.time_label = label(_clock(self.created_at), faint=True)
        foot_box.addWidget(self.time_label)
        self.copy_button = tool_button("copy", size=13, tooltip=tr("common.copy"),
                                       clicked=lambda: copy_to_clipboard(self._text))
        self.edit_button = tool_button("pencil", size=13, tooltip=tr("chat.retry_last"),
                                       clicked=lambda: self.editRequested.emit(self._text))
        foot_box.addWidget(self.copy_button)
        foot_box.addWidget(self.edit_button)
        box.addWidget(foot)

        outer.addWidget(self.bubble, 0)

    def text(self) -> str:
        return self._text

    def set_palette(self, palette) -> None:
        self.view.set_palette(palette, palette_font_size(palette))
        self.time_label.setStyleSheet(f"color: {palette.text_faint};")
        self.copy_button.setIcon(icons.icon("copy", palette.text_muted, 13))
        self.edit_button.setIcon(icons.icon("pencil", palette.text_muted, 13))


class NoticeItem(QFrame):
    """System notes: session start, compaction, denials, warnings, errors."""

    LEVELS = {"info": ("info", "#3E6E8E"), "warn": ("warning", "#B4801F"),
              "error": ("warning", "#B3453B"), "success": ("check_circle", "#4C8C4A")}

    def __init__(self, title: str = "", message: str = "", level: str = "info",
                 icon_name: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SystemNote")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.level = level
        outer = QHBoxLayout(self)
        outer.setContentsMargins(58, 4, 26, 4)
        outer.setSpacing(9)
        name, color = self.LEVELS.get(level, self.LEVELS["info"])
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap(icon_name or name, color, 15))
        outer.addWidget(self.icon_label, 0, Qt.AlignTop)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        if title:
            column.addWidget(label(title, bold=True))
        if message:
            body = label(message, wrap=True, muted=True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            column.addWidget(body)
        outer.addLayout(column, 1)
        self._color = color

    def set_palette(self, palette) -> None:
        color = {"info": palette.info, "warn": palette.warn, "error": palette.danger,
                 "success": palette.success}.get(self.level, palette.text_muted)
        name = self.LEVELS.get(self.level, self.LEVELS["info"])[0]
        self.icon_label.setPixmap(icons.pixmap(name, color, 15))


class TurnSeparator(QFrame):
    """Thin rule with the turn's stats in the middle."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(58, 6, 26, 6)
        outer.setSpacing(10)
        self.left = hline()
        self.right = hline()
        outer.addWidget(self.left, 1)
        self.pill = Pill(text or tr("tool.finished"), "check_circle", "#4C8C4A", size=12)
        outer.addWidget(self.pill)
        outer.addWidget(self.right, 1)

    def set_text(self, text: str) -> None:
        self.pill.set_text(text)

    def set_palette(self, palette) -> None:
        self.pill.set_color(palette.success, "check_circle")
        for line in (self.left, self.right):
            line.setStyleSheet(f"background-color: {palette.border};")
