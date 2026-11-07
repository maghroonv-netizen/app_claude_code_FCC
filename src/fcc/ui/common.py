"""Shared UI helpers: dynamic properties, buttons, layout sugar, animations."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt,
                            QTimer, QUrl, Signal)
from PySide6.QtGui import (QDesktopServices, QFont, QIcon, QKeySequence, QPainter,
                           QPaintEvent, QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
                               QWidget)

from fcc import icons


def props(widget: QWidget, **values: Any) -> QWidget:
    """Set Qt dynamic properties and force a style re-evaluation."""
    for key, value in values.items():
        widget.setProperty(key, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def object_name(widget: QWidget, name: str) -> QWidget:
    widget.setObjectName(name)
    return widget


def hline(palette=None) -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def spacer(size: int = 8) -> QWidget:
    widget = QWidget()
    widget.setFixedSize(size, size)
    return widget


def stretch() -> QWidget:
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return widget


def label(text: str = "", *, muted: bool = False, faint: bool = False, accent: bool = False,
          size: int = 0, bold: bool = False, wrap: bool = False, align=None) -> QLabel:
    widget = QLabel(text)
    if muted:
        widget.setProperty("muted", True)
    if faint:
        widget.setProperty("faint", True)
    if accent:
        widget.setProperty("accent", True)
    font = widget.font()
    if size:
        font.setPointSize(size)
    if bold:
        font.setWeight(QFont.DemiBold)
    widget.setFont(font)
    if wrap:
        widget.setWordWrap(True)
    if align is not None:
        widget.setAlignment(align)
    return widget


def button(text: str = "", icon_name: str = "", *, primary: bool = False, ghost: bool = False,
           danger: bool = False, icon_only: bool = False, size: int = 18,
           tooltip: str = "", clicked: Optional[Callable] = None,
           color: str = "#6E6C65") -> QPushButton:
    widget = QPushButton(text)
    if icon_name:
        widget.setIcon(icons.icon(icon_name, color if not primary else "#FFFFFF", size))
        widget.setIconSize(QSize(size, size))
    if icon_only:
        widget.setObjectName("Icon")
        widget.setFixedSize(size + 16, size + 16)
        widget.setCursor(Qt.PointingHandCursor)
    elif primary:
        widget.setObjectName("Primary")
        widget.setCursor(Qt.PointingHandCursor)
    elif ghost:
        widget.setObjectName("Ghost")
        widget.setCursor(Qt.PointingHandCursor)
    elif danger:
        widget.setObjectName("Danger")
        widget.setCursor(Qt.PointingHandCursor)
    else:
        widget.setCursor(Qt.PointingHandCursor)
    if tooltip:
        widget.setToolTip(tooltip)
    if clicked is not None:
        widget.clicked.connect(clicked)
    return widget


def tool_button(icon_name: str, *, size: int = 18, tooltip: str = "", color: str = "#6E6C65",
                checkable: bool = False, clicked: Optional[Callable] = None) -> QToolButton:
    widget = QToolButton()
    widget.setObjectName("Icon")
    widget.setIcon(icons.icon(icon_name, color, size))
    widget.setIconSize(QSize(size, size))
    widget.setFixedSize(size + 16, size + 16)
    widget.setCursor(Qt.PointingHandCursor)
    widget.setCheckable(checkable)
    widget.setAutoRaise(True)
    if tooltip:
        widget.setToolTip(tooltip)
    if clicked is not None:
        widget.clicked.connect(clicked)
    return widget


def recolor_icon(button_widget, icon_name: str, color: str, size: int = 18) -> None:
    button_widget.setIcon(icons.icon(icon_name, color, size))


def layout(*widgets, margin: int = 0, spacing: int = 8, vertical: bool = False,
           align=None) -> Any:
    box = QVBoxLayout() if vertical else QHBoxLayout()
    box.setContentsMargins(margin, margin, margin, margin)
    box.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            continue
        if isinstance(widget, QWidget):
            box.addWidget(widget)
        else:
            box.addLayout(widget)
    if align is not None:
        box.setAlignment(align)
    return box


def card(object_id: str = "Card", margin: int = 14, spacing: int = 10) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(object_id)
    box = QVBoxLayout(frame)
    box.setContentsMargins(margin, margin, margin, margin)
    box.setSpacing(spacing)
    return frame, box


def open_url(url: str) -> None:
    if not url:
        return
    try:
        QDesktopServices.openUrl(QUrl(url))
    except Exception:
        pass


def open_path(path: str) -> None:
    if not path:
        return
    try:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    except Exception:
        pass


def fade_in(widget: QWidget, duration: int = 220) -> None:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    animation.start(QPropertyAnimation.DeleteWhenStopped)


def slide_in(widget: QWidget, distance: int = 18, duration: int = 240) -> None:
    fade_in(widget, duration)
    target = widget.pos()
    start = QPoint(target.x(), target.y() + distance)
    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(target)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start(QPropertyAnimation.DeleteWhenStopped)


def shortcut(key: str, widget: QWidget, callback: Callable) -> QShortcut:
    item = QShortcut(QKeySequence(key), widget)
    item.setContext(Qt.WindowShortcut)
    item.activated.connect(callback)
    return item


def elide(text: str, limit: int = 60) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def copy_to_clipboard(text: str) -> None:
    QApplication.clipboard().setText(text or "")


def set_font_size(widget: QWidget, size: int) -> None:
    font = widget.font()
    font.setPointSize(size)
    widget.setFont(font)


class Spinner(QWidget):
    """A small coral arc spinner used while Claude Code works."""

    def __init__(self, size: int = 18, color: str = "#D97757", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size = size
        self._color = color
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._tick)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        self.setVisible(True)

    def stop(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def _tick(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPen

        pen = QPen()
        pen.setWidth(max(2, self._size // 8))
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(Qt.transparent)
        painter.setPen(pen)
        rect = QRectF(1, 1, self._size - 2, self._size - 2)
        from PySide6.QtGui import QColor

        pen.setColor(QColor(self._color))
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 280 * 16)
        painter.end()


class Pill(QFrame):
    """A rounded status chip with an optional leading dot/icon."""

    def __init__(self, text: str = "", icon_name: str = "", color: str = "#D97757",
                 size: int = 13, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        props(self, badge=True)
        box = QHBoxLayout(self)
        box.setContentsMargins(9, 3, 9, 3)
        box.setSpacing(5)
        self._icon_label: Optional[QLabel] = None
        if icon_name:
            self._icon_label = QLabel()
            self._icon_label.setPixmap(icons.pixmap(icon_name, color, size))
            box.addWidget(self._icon_label)
        self._text = label(text, size=0)
        props(self._text, badgeText=True)
        font = self._text.font()
        font.setPointSize(max(7, size - 4))
        self._text.setFont(font)
        box.addWidget(self._text)
        self._color = color
        self._icon_name = icon_name
        self._size = size

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def text(self) -> str:
        return self._text.text()

    def set_color(self, color: str, icon_name: Optional[str] = None) -> None:
        self._color = color
        if icon_name:
            self._icon_name = icon_name
        if self._icon_label is not None and self._icon_name:
            self._icon_label.setPixmap(icons.pixmap(self._icon_name, color, self._size))


def set_palette(widget, palette, *args, **kwargs):
    """Apply `palette` to any widget that implements `set_palette`."""
    setter = getattr(widget, "set_palette", None)
    if callable(setter):
        setter(palette, *args, **kwargs)
    return widget
