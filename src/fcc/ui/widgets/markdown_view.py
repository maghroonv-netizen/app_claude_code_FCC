"""Auto-sizing markdown view used for chat messages and tool output."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QTextOption
from PySide6.QtWidgets import QSizePolicy, QTextBrowser

from fcc import markdown
from fcc.ui.common import open_url


class MarkdownView(QTextBrowser):
    """Renders markdown, grows to fit its content, opens links in the browser."""

    linkActivated = Signal(str)

    def __init__(self, parent=None, streaming: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("Markdown")
        self._streaming = streaming
        self._pending = ""
        self._dirty = False
        self._font_size = 14
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setFrameShape(QTextBrowser.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextBrowser.WidgetWidth)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.document().setDocumentMargin(0)
        self.document().setDefaultStyleSheet(markdown.markdown_css(default_palette(), self._font_size))
        self.anchorClicked.connect(self._on_anchor)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._flush)
        self._html_cache = ""
        self._last_height = 0

    # ------------------------------------------------------------------ #
    def _on_anchor(self, url: QUrl) -> None:
        target = url.toString()
        if target.startswith("file://"):
            open_url(target)
        else:
            open_url(target)
        self.linkActivated.emit(target)

    def set_palette(self, palette, font_size: int = 14) -> None:
        self._font_size = font_size
        self.document().setDefaultStyleSheet(markdown.markdown_css(palette, font_size))
        self._render()

    def set_markdown(self, text: str, streaming: Optional[bool] = None) -> None:
        self._pending = text or ""
        live = self._streaming if streaming is None else streaming
        if not live:
            self._flush()
            return
        if not self._dirty:
            self._dirty = True
            self._timer.start()

    def flush_now(self) -> None:
        self._timer.stop()
        self._flush()

    def _flush(self) -> None:
        self._dirty = False
        self._render()

    def _render(self) -> None:
        html_text = markdown.to_html(self._pending, streaming=True)
        if html_text != self._html_cache:
            self.setHtml(html_text)
        self._sync_height()

    def setHtml(self, html_text: str) -> None:  # noqa: N802 - Qt API
        self._html_cache = html_text
        super().setHtml(html_text)
        self._sync_height()

    def _sync_height(self) -> None:
        width = max(80, self.viewport().width())
        self.document().setTextWidth(width)
        size = self.document().size()
        height = int(size.height()) + 2
        if height != self._last_height:
            self._last_height = height
            self.setFixedHeight(max(20, height))
            self.updateGeometry()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._sync_height()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self._sync_height()

    def plain(self) -> str:
        return self._pending

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(320, max(24, self._last_height))


def default_palette():
    """Neutral palette used before the theme is applied."""
    from fcc.theme import palette_for

    return palette_for("light")
