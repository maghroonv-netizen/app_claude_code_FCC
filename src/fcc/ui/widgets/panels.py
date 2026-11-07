"""Status bar, live activity log and toast notifications."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QSizePolicy,
                               QVBoxLayout, QWidget)

from fcc import icons
from fcc.i18n import tr
from fcc.ui.common import button, hline, label, props, tool_button

STATE_TEXT = {
    "idle": ("status.offline", "#9C9A91"),
    "starting": ("status.starting", "#B4801F"),
    "ready": ("status.ready", "#4C8C4A"),
    "busy": ("status.busy", "#D97757"),
    "waiting_permission": ("status.waiting", "#B4801F"),
    "stopping": ("status.stopped", "#9C9A91"),
    "ended": ("status.stopped", "#9C9A91"),
    "error": ("status.error", "#B3453B"),
    "demo": ("status.demo", "#7A8450"),
}


class StatusBar(QFrame):
    contextRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(38)
        self._palette = None
        box = QHBoxLayout(self)
        box.setContentsMargins(16, 0, 16, 0)
        box.setSpacing(10)

        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        box.addWidget(self.dot)
        self.state_label = label(tr("status.offline"), muted=True)
        box.addWidget(self.state_label)
        box.addWidget(_vsep())

        self.project_label = label("", faint=True)
        box.addWidget(self.project_label)
        box.addStretch(1)

        self.context_bar = QProgressBar()
        self.context_bar.setFixedWidth(110)
        self.context_bar.setTextVisible(False)
        self.context_bar.setRange(0, 100)
        self.context_bar.setValue(0)
        self.context_bar.setToolTip(tr("status.context"))
        box.addWidget(self.context_bar)
        self.context_label = label("", faint=True)
        box.addWidget(self.context_label)
        box.addWidget(_vsep())

        self.model_label = label("", faint=True)
        box.addWidget(self.model_label)
        box.addWidget(_vsep())
        self.mode_label = label("", faint=True)
        box.addWidget(self.mode_label)
        self.gateway_label = label("", faint=True)
        self.gateway_label.setVisible(False)
        box.addWidget(self.gateway_label)
        box.addWidget(_vsep())
        self.stats_label = label("", faint=True)
        box.addWidget(self.stats_label)

    def set_state(self, state: str, extra: str = "") -> None:
        key, color = STATE_TEXT.get(state, STATE_TEXT["idle"])
        text = tr(key) if not extra else extra
        self.state_label.setText(text)
        self.dot.setPixmap(_dot(9, color))
        self.state_label.setStyleSheet(f"color: {color};")

    def set_project(self, path: str) -> None:
        from pathlib import Path

        self.project_label.setText(str(Path(path)) if path else "")
        self.project_label.setToolTip(path)

    def set_model(self, model: str) -> None:
        self.model_label.setText(model or "")
        self.model_label.setVisible(bool(model))

    def set_mode(self, mode: str) -> None:
        self.mode_label.setText(tr(f"perm.mode.{mode}") if mode else "")
        self.mode_label.setVisible(bool(mode))

    def set_gateway(self, text: str, ok: bool = False) -> None:
        self.gateway_label.setText(text or "")
        self.gateway_label.setVisible(bool(text))
        color = "#4C8C4A" if ok else ""
        self.gateway_label.setStyleSheet(f"color: {color};" if color else "")

    def set_stats(self, stats) -> None:
        from fcc.claude.protocol import format_cost, format_duration, format_tokens

        self.stats_label.setText(
            f"{format_tokens(stats.tokens_in)}↓ {format_tokens(stats.tokens_out)}↑ · "
            f"{format_cost(stats.cost_usd)} · {format_duration(stats.duration_ms)}"
        )
        window = stats.context_window or 200000
        used = stats.tokens_in + stats.tokens_out
        percent = max(0, min(100, int(used * 100 / window))) if window else 0
        self.context_bar.setValue(percent)
        self.context_label.setText(f"{format_tokens(used)} / {format_tokens(window)}")
        busy = percent > 80
        props(self.context_bar, busy=busy)

    def set_palette(self, palette) -> None:
        self._palette = palette
        for widget in (self.project_label, self.context_label, self.model_label,
                       self.mode_label, self.stats_label):
            widget.setStyleSheet(f"color: {palette.text_faint};")


def _vsep() -> QWidget:
    widget = QFrame()
    widget.setFixedWidth(1)
    widget.setFixedHeight(16)
    widget.setProperty("vsep", True)
    return widget


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


class Toast(QFrame):
    dismissed = Signal(object)

    def __init__(self, message: str, level: str = "info", timeout: int = 4200,
                 action_text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.level = level
        self.message = message
        box = QHBoxLayout(self)
        box.setContentsMargins(14, 11, 12, 11)
        box.setSpacing(10)
        icon_name, color = {
            "info": ("info", "#3E6E8E"), "success": ("check_circle", "#4C8C4A"),
            "warn": ("warning", "#B4801F"), "error": ("x_circle", "#B3453B"),
        }.get(level, ("info", "#3E6E8E"))
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap(icon_name, color, 17))
        box.addWidget(self.icon_label, 0, Qt.AlignTop)
        self.text_label = label(message, wrap=True)
        self.text_label.setMaximumWidth(360)
        box.addWidget(self.text_label, 1)
        if action_text:
            self.action = button(action_text, ghost=True, size=13,
                                 clicked=lambda: self.dismissed.emit(self))
            box.addWidget(self.action)
        close = tool_button("x", size=12, clicked=lambda: self.dismissed.emit(self))
        box.addWidget(close, 0, Qt.AlignTop)
        self.setMaximumWidth(460)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._effect = effect
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.dismissed.emit(self))

    def animate_in(self) -> None:
        animation = QPropertyAnimation(self._effect, b"opacity", self)
        animation.setDuration(200)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start(QPropertyAnimation.DeleteWhenStopped)

    def animate_out(self, on_done) -> None:
        animation = QPropertyAnimation(self._effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(on_done)
        animation.start(QPropertyAnimation.DeleteWhenStopped)


class ToastStack(QWidget):
    """Floating notification stack; place over the window's bottom-right corner."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(8)
        self._box.addStretch(1)
        self._toasts: List[Toast] = []
        self.resize(460, 400)

    def show_toast(self, message: str, level: str = "info", timeout: int = 4200,
                   action_text: str = "") -> Toast:
        toast = Toast(message, level, timeout, action_text, self)
        toast.dismissed.connect(self.dismiss)
        self._box.insertWidget(self._box.count() - 1, toast)
        self._toasts.append(toast)
        toast.animate_in()
        self._relayout()
        QTimer.singleShot(0, self._relayout)   # after label wrapping settles
        while len(self._toasts) > 4:
            self.dismiss(self._toasts[0])
        return toast

    def dismiss(self, toast: Toast) -> None:
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)

        def finish() -> None:
            self._box.removeWidget(toast)
            toast.deleteLater()
            self._relayout()

        toast.animate_out(finish)

    def _relayout(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self._box.activate()
        width = 460
        needed = self._box.sizeHint().height()
        height = max(60, min(needed, max(60, parent.height() - 96)))
        x = max(8, parent.width() - width - 22)
        y = max(8, parent.height() - height - 56)
        self.setGeometry(x, y, width, height)
        self.raise_()

    def set_palette(self, palette) -> None:
        for toast in list(self._toasts):
            toast.setStyleSheet(
                f"QFrame#Card {{ background-color: {palette.surface}; border: 1px solid {palette.border_strong};"
                f" border-radius: 14px; }}"
            )
            toast.text_label.setStyleSheet(f"color: {palette.text};")


class ActivityPanel(QFrame):
    """Live view of everything Claude Code streams, for transparency and debugging."""

    closed = Signal()
    filterChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedWidth(392)
        self._palette = None
        self._lines: List[Dict[str, Any]] = []
        self._filter = "all"

        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(9)

        head = QWidget()
        head_box = QHBoxLayout(head)
        head_box.setContentsMargins(0, 0, 0, 0)
        head_box.setSpacing(8)
        title = label(tr("chat.raw_events"), bold=True)
        head_box.addWidget(title)
        self.count_label = label("0", faint=True)
        head_box.addWidget(self.count_label)
        head_box.addStretch(1)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["all", "tools", "permissions", "errors", "text"])
        self.filter_combo.currentTextChanged.connect(self._on_filter)
        head_box.addWidget(self.filter_combo)
        self.copy_button = tool_button("copy", size=14, tooltip=tr("common.copy"), clicked=self.copy_all)
        self.clear_button = tool_button("trash", size=14, clicked=self.clear)
        self.close_button = tool_button("x", size=14, clicked=self.closed.emit)
        head_box.addWidget(self.copy_button)
        head_box.addWidget(self.clear_button)
        head_box.addWidget(self.close_button)
        box.addWidget(head)

        self.stats = QLabel("")
        self.stats.setWordWrap(True)
        self.stats.setProperty("faint", True)
        box.addWidget(self.stats)

        self.view = QPlainTextEdit()
        self.view.setObjectName("RawLog")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(4000)
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        box.addWidget(self.view, 1)

    def _on_filter(self, value: str) -> None:
        self._filter = value
        self.filterChanged.emit(value)
        self._render()

    def add(self, kind: str, text: str, channel: str = "event") -> None:
        self._lines.append({"kind": kind, "text": text, "channel": channel, "at": time.time()})
        if len(self._lines) > 2000:
            self._lines = self._lines[-2000:]
        if self._matches(self._lines[-1]):
            self.view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {text}")
            self.view.moveCursor(QTextCursor.End)
        self.count_label.setText(str(len(self._lines)))

    def _matches(self, item: Dict[str, Any]) -> bool:
        if self._filter == "all":
            return True
        if self._filter == "tools":
            return item["kind"].startswith("tool")
        if self._filter == "permissions":
            return "permission" in item["kind"]
        if self._filter == "errors":
            return item["kind"] in ("error", "stderr")
        if self._filter == "text":
            return item["kind"] in ("text", "message_final")
        return True

    def _render(self) -> None:
        self.view.clear()
        for item in self._lines:
            if self._matches(item):
                self.view.appendPlainText(f"{time.strftime('%H:%M:%S', time.localtime(item['at']))}  {item['text']}")

    def set_stats(self, stats: Dict[str, Any]) -> None:
        parts = [
            f"session {str(stats.get('session_id', '-'))[:8]}",
            f"pid {stats.get('pid', '-')}",
            f"asks {stats.get('control', {}).get('asks', 0)}",
            f"allow {stats.get('control', {}).get('allowed', 0)}",
            f"deny {stats.get('control', {}).get('denied', 0)}",
        ]
        self.stats.setText("  ·  ".join(parts))

    def copy_all(self) -> None:
        QApplication.clipboard().setText(self.view.toPlainText())

    def clear(self) -> None:
        self._lines.clear()
        self.view.clear()
        self.count_label.setText("0")

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.stats.setStyleSheet(f"color: {palette.text_faint};")
        self.view.setStyleSheet(
            f"QPlainTextEdit#RawLog {{ background-color: {palette.code_bg}; color: {palette.code_text};"
            f" border: 1px solid {palette.code_border}; border-radius: 10px; }}"
        )
        for widget, name in ((self.copy_button, "copy"), (self.clear_button, "trash"),
                             (self.close_button, "x")):
            widget.setIcon(icons.icon(name, palette.text_muted, 14))
