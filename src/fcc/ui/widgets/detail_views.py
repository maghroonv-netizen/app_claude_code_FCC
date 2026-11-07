"""Rich viewers for tool output: diffs, code, file lists and task lists."""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from fcc import markdown
from fcc.claude.toolmeta import DiffLine, ToolDetail
from fcc.ui.common import button, copy_to_clipboard, label, props
from fcc.ui.widgets.markdown_view import MarkdownView, default_palette

DIFF_LIMIT = 300


class DiffView(MarkdownView):
    """Unified diff with line numbers, rendered as selectable HTML."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, streaming=False)
        self._lines: List[DiffLine] = []
        self._expanded = False
        self._palette = default_palette()

    def set_palette(self, palette, font_size: int = 14) -> None:  # type: ignore[override]
        self._palette = palette
        self._font_size = font_size
        self._render_diff()

    def set_diff(self, lines: List[DiffLine]) -> None:
        self._lines = lines or []
        self._render_diff()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._render_diff()

    def text_payload(self) -> str:
        out = []
        for line in self._lines:
            prefix = {"add": "+", "del": "-", "hunk": "", "ctx": " "}.get(line.kind, " ")
            out.append(f"{prefix}{line.text}")
        return "\n".join(out)

    def _render_diff(self) -> None:
        p = self._palette
        small = max(9, self._font_size - 3)
        rows = self._lines if self._expanded else self._lines[:DIFF_LIMIT]
        parts = [
            f'<table class="diff" cellspacing="0" cellpadding="0" '
            f'style="border-collapse:collapse;font-family:Consolas,monospace;font-size:{small}px;">'
        ]
        for line in rows:
            if line.kind == "hunk":
                parts.append(
                    f'<tr><td colspan="3" style="background:{p.surface_sunken};color:{p.text_faint};'
                    f'padding:2px 8px;border-top:1px solid {p.border};border-bottom:1px solid {p.border};">'
                    f"{html.escape(line.text)}</td></tr>"
                )
                continue
            if line.kind == "add":
                bg, fg, sign = p.success_soft, p.success, "+"
            elif line.kind == "del":
                bg, fg, sign = p.danger_soft, p.danger, "−"
            else:
                bg, fg, sign = "transparent", p.text_muted, " "
            old_no = "" if line.old_no is None else str(line.old_no)
            new_no = "" if line.new_no is None else str(line.new_no)
            gutter = (
                f'color:{p.text_faint};background:{p.surface_alt};'
                f'padding:1px 6px;text-align:right;border-right:1px solid {p.border};'
                f'white-space:nowrap;user-select:none;'
            )
            parts.append(
                f'<tr><td style="{gutter}">{old_no}</td><td style="{gutter}">{new_no}</td>'
                f'<td width="100%" style="background:{bg};color:{fg};padding:1px 8px;'
                f'white-space:pre-wrap;word-break:break-word;">'
                f'<span style="user-select:none;">{sign}</span> {html.escape(line.text or " ")}</td></tr>'
            )
        parts.append("</table>")
        if not self._expanded and len(self._lines) > DIFF_LIMIT:
            parts.append(
                f'<p style="color:{p.text_faint};font-size:{small}px;margin:6px 0 0 0;">'
                f"{len(self._lines) - DIFF_LIMIT} more lines hidden</p>"
            )
        self.setHtml("".join(parts))


class CodeBlock(MarkdownView):
    """Syntax-highlighted code / command output."""

    def __init__(self, language: str = "", parent: Optional[QWidget] = None, max_lines: int = 400) -> None:
        super().__init__(parent, streaming=False)
        self._language = language
        self._code = ""
        self._max_lines = max_lines
        self._expanded = False
        self._palette = default_palette()

    def set_palette(self, palette, font_size: int = 14) -> None:  # type: ignore[override]
        self._palette = palette
        self._font_size = font_size
        self._render_code()

    def set_code(self, code: str, language: str = "") -> None:
        self._code = code or ""
        if language:
            self._language = language
        self._render_code()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._render_code()

    def line_count(self) -> int:
        return self._code.count("\n") + 1 if self._code else 0

    def _render_code(self) -> None:
        code = self._code
        clipped = False
        if not self._expanded and self.line_count() > self._max_lines:
            code = "\n".join(self._code.splitlines()[: self._max_lines])
            clipped = True
        body = markdown._highlight(code, self._language)
        if clipped:
            body = body.replace(
                "</code></pre>",
                f'<span style="opacity:.6">… {self.line_count() - self._max_lines} more lines</span></code></pre>',
            )
        self.setHtml(body)


class TodoView(QFrame):
    """Claude's task list rendered as a checklist."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 2, 0, 2)
        self._box.setSpacing(4)
        self._items: List[Dict[str, Any]] = []
        self._palette = default_palette()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.set_items(self._items)

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self._items = items or []
        while self._box.count():
            child = self._box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        done = sum(1 for item in self._items if item.get("status") == "completed")
        if self._items:
            head = label(f"{done}/{len(self._items)} complete", faint=True)
            self._box.addWidget(head)
        for item in self._items:
            status = str(item.get("status", "pending"))
            text = str(item.get("content") or item.get("activeForm") or "")
            if status == "in_progress":
                text = str(item.get("activeForm") or text)
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 0, 0, 0)
            row_box.setSpacing(8)
            mark = {"completed": "✓", "in_progress": "▶", "pending": "○"}.get(status, "○")
            color = {"completed": self._palette.success, "in_progress": self._palette.accent,
                     "pending": self._palette.text_faint}.get(status, self._palette.text_faint)
            tick = QLabel(mark)
            tick.setStyleSheet(f"color: {color}; font-weight: 700;")
            tick.setFixedWidth(14)
            row_box.addWidget(tick)
            text_label = label(text)
            if status == "completed":
                text_label.setStyleSheet(f"color: {self._palette.text_faint}; text-decoration: line-through;")
            elif status == "in_progress":
                text_label.setStyleSheet(f"color: {self._palette.text}; font-weight: 600;")
            else:
                text_label.setStyleSheet(f"color: {self._palette.text_muted};")
            text_label.setWordWrap(True)
            row_box.addWidget(text_label, 1)
            self._box.addWidget(row)

    def as_text(self) -> str:
        lines = []
        for item in self._items:
            mark = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}.get(item.get("status"), "[ ]")
            lines.append(f"{mark} {item.get('content', '')}")
        return "\n".join(lines)


class FileListView(QFrame):
    """Compact list of file paths or search hits."""

    def __init__(self, parent: Optional[QWidget] = None, max_items: int = 60) -> None:
        super().__init__(parent)
        self._max_items = max_items
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 2, 0, 2)
        self._box.setSpacing(2)
        self._items: List[Dict[str, Any]] = []
        self._palette = default_palette()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.set_items(self._items)

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self._items = items or []
        while self._box.count():
            child = self._box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        from fcc import icons

        for item in self._items[: self._max_items]:
            text = str(item.get("text", ""))
            sub = str(item.get("sub", ""))
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 0, 0, 0)
            row_box.setSpacing(7)
            icon_label = QLabel()
            icon_label.setPixmap(icons.pixmap("file", self._palette.text_faint, 14))
            row_box.addWidget(icon_label)
            name = label(text)
            name.setStyleSheet(f"font-family: Consolas, monospace; font-size: {max(10, self._font_size() - 2)}px;")
            row_box.addWidget(name, 1)
            if sub:
                sub_label = label(sub, faint=True)
                row_box.addWidget(sub_label)
            self._box.addWidget(row)
        if len(self._items) > self._max_items:
            self._box.addWidget(label(f"… {len(self._items) - self._max_items} more", faint=True))

    def _font_size(self) -> int:
        return getattr(self._palette, "font_size", 14) or 14

    def as_text(self) -> str:
        return "\n".join(str(item.get("text", "")) for item in self._items)


class KeyValueView(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 2, 0, 2)
        self._box.setSpacing(3)
        self._rows: List[Any] = []
        self._palette = default_palette()

    def set_palette(self, palette) -> None:
        self._palette = palette
        self.set_rows(self._rows)

    def set_rows(self, rows) -> None:
        self._rows = list(rows or [])
        while self._box.count():
            child = self._box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for key, value in self._rows:
            if not value:
                continue
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 0, 0, 0)
            row_box.setSpacing(8)
            key_label = label(f"{key}")
            key_label.setStyleSheet(f"color: {self._palette.text_faint}; min-width: 84px;")
            row_box.addWidget(key_label)
            value_label = label(str(value), wrap=True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setStyleSheet(f"color: {self._palette.text}; font-family: Consolas, monospace;")
            row_box.addWidget(value_label, 1)
            self._box.addWidget(row)

    def as_text(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in self._rows)


class DetailBody(QFrame):
    """Chooses the right viewer for a :class:`ToolDetail`."""

    copyRequested = Signal(str)
    expandRequested = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(8)
        self._palette = default_palette()
        self._detail: Optional[ToolDetail] = None
        self._expanded = False
        self._viewer: Optional[QWidget] = None
        self._kv: Optional[KeyValueView] = None
        self._more: Optional[QWidget] = None

    def set_palette(self, palette, font_size: int = 14) -> None:
        self._palette = palette
        if isinstance(self._viewer, (DiffView, CodeBlock)):
            self._viewer.set_palette(palette, font_size)
        elif isinstance(self._viewer, (TodoView, FileListView, KeyValueView)):
            self._viewer.set_palette(palette)

    def set_detail(self, detail: Optional[ToolDetail]) -> None:
        self._detail = detail
        self._rebuild()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        if isinstance(self._viewer, (DiffView, CodeBlock)):
            self._viewer.set_expanded(expanded)

    def as_text(self) -> str:
        if self._viewer is not None and hasattr(self._viewer, "as_text"):
            return self._viewer.as_text()
        if self._viewer is not None and hasattr(self._viewer, "text_payload"):
            return self._viewer.text_payload()
        if self._detail is not None:
            return self._detail.body
        return ""

    # ------------------------------------------------------------------ #
    def _clear(self) -> None:
        while self._box.count():
            child = self._box.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self._viewer = None
        self._kv = None
        self._more = None

    def _rebuild(self) -> None:
        self._clear()
        detail = self._detail
        if detail is None or detail.is_empty:
            empty = label("No output", faint=True)
            self._box.addWidget(empty)
            return

        if detail.rows:
            self._kv = KeyValueView()
            self._kv.set_palette(self._palette)
            self._kv.set_rows(detail.rows)
            self._box.addWidget(self._kv)

        if detail.kind == "diff" and detail.diff:
            view = DiffView()
            view.set_palette(self._palette, self._font_size())
            view.set_diff(detail.diff)
            view.set_expanded(self._expanded)
            self._viewer = view
            self._box.addWidget(view)
        elif detail.kind == "todos" and detail.items:
            view = TodoView()
            view.set_palette(self._palette)
            view.set_items(detail.items)
            self._viewer = view
            self._box.addWidget(view)
        elif detail.kind == "files" and detail.items:
            view = FileListView()
            view.set_palette(self._palette)
            view.set_items(detail.items)
            self._viewer = view
            self._box.addWidget(view)
        elif detail.kind == "kv":
            rows = [(k, v) for k, v in detail.rows if k not in [r[0] for r in (detail.rows[:0])]]
            view = KeyValueView()
            view.set_palette(self._palette)
            view.set_rows(detail.rows)
            self._viewer = view
            self._box.addWidget(view)
        elif detail.body:
            view = CodeBlock(detail.language or "")
            view.set_palette(self._palette, self._font_size())
            view.set_code(detail.body, detail.language or "")
            view.set_expanded(self._expanded)
            self._viewer = view
            self._box.addWidget(view)

        if detail.truncated or (isinstance(self._viewer, CodeBlock) and self._viewer.line_count() > 400):
            self._more = button("Show everything", "expand", ghost=True, size=14,
                                clicked=lambda: self.expandRequested.emit(not self._expanded))
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(self._more)
            row.addStretch(1)
            self._box.addLayout(row)

    def _font_size(self) -> int:
        return 14
