"""The message composer: auto-growing input, @files, /commands, attachments."""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QSizePolicy,
                               QVBoxLayout, QWidget)

from fcc import icons
from fcc.claude import projects
from fcc.i18n import tr
from fcc.ui.common import Pill, button, label, props, tool_button

MAX_ATTACHMENT_CHARS = 60_000
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}


class ComposerEdit(QPlainTextEdit):
    """Input box with chat-app key handling and completion hooks."""

    submitRequested = Signal()
    cancelRequested = Signal()
    completionRequested = Signal(str, str)  # kind ("file"|"command"), query
    completionClosed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Composer")
        self.setPlaceholderText(tr("chat.placeholder"))
        self.setTabChangesFocus(True)
        self.setAcceptDrops(False)
        self.document().setDocumentMargin(2)
        self._min_height = 46
        self._max_height = 220
        self.setFixedHeight(self._min_height)
        self.textChanged.connect(self._auto_grow)
        self._completion_open = False

    def set_completion_open(self, open_: bool) -> None:
        self._completion_open = open_

    def _auto_grow(self) -> None:
        document_height = int(self.document().documentLayout().documentSize().height()) + 18
        height = max(self._min_height, min(self._max_height, document_height))
        if height != self.height():
            self.setFixedHeight(height)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        modifiers = event.modifiers()
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if modifiers & Qt.ShiftModifier:
                super().keyPressEvent(event)
                return
            if modifiers & Qt.ControlModifier or not self._completion_open:
                self.submitRequested.emit()
                return
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Escape:
            if self._completion_open:
                self.completionClosed.emit()
                return
            self.cancelRequested.emit()
            return
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Tab) and self._completion_open:
            super().keyPressEvent(event)
            return
        super().keyPressEvent(event)
        self._notify_completion()

    def _notify_completion(self) -> None:
        cursor = self.textCursor()
        cursor.select(QTextCursor.BlockUnderCursor)
        block_text = cursor.selectedText()
        column = self.textCursor().positionInBlock()
        prefix = block_text[:column]
        if prefix.startswith("/"):
            token = prefix.split(" ")[-1]
            if prefix.count(" ") == 0:
                self.completionRequested.emit("command", token)
                return
        index = prefix.rfind("@")
        if index >= 0 and (index == 0 or prefix[index - 1] in " \n([,"):
            token = prefix[index:]
            if " " not in token[1:]:
                self.completionRequested.emit("file", token)
                return
        self.completionClosed.emit()

    def apply_completion(self, text: str, kind: str) -> None:
        cursor = self.textCursor()
        block = cursor.block().text()
        column = cursor.positionInBlock()
        prefix = block[:column]
        if kind == "command":
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.insertText(text + " ")
        else:
            index = prefix.rfind("@")
            for _ in range(column - index):
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
            cursor.insertText(text + " ")
        self.setFocus()
        self.completionClosed.emit()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(420, self._min_height)


class CompletionPopup(QFrame):
    """Floating list for @file and /command suggestions."""

    picked = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("Card")
        box = QVBoxLayout(self)
        box.setContentsMargins(6, 6, 6, 6)
        box.setSpacing(4)
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._clicked)
        box.addWidget(self.list)
        self.hint = label("", faint=True)
        box.addWidget(self.hint)
        self._kind = "file"
        self._items: List[str] = []
        self.hide()

    def show_items(self, items: List[str], kind: str, anchor: QPoint, hint: str = "") -> None:
        self._kind = kind
        self._items = list(items)
        self.list.clear()
        for item in items:
            entry = QListWidgetItem(icons.icon("terminal" if kind == "command" else "file",
                                               "#6E6C65", 14), item)
            self.list.addItem(entry)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        self.adjustSize()
        width = max(280, min(520, self.sizeHint().width()))
        self.resize(width, min(300, max(80, 34 * max(1, self.list.count()) + 30)))
        position = QPoint(anchor.x(), anchor.y() - self.height() - 6)
        self.move(position)
        self.show()
        self.raise_()

    def _clicked(self, item: QListWidgetItem) -> None:
        self.picked.emit(item.text(), self._kind)
        self.hide()

    def move_selection(self, delta: int) -> None:
        row = self.list.currentRow() + delta
        if 0 <= row < self.list.count():
            self.list.setCurrentRow(row)

    def accept_current(self) -> bool:
        item = self.list.currentItem()
        if item is None:
            return False
        self.picked.emit(item.text(), self._kind)
        self.hide()
        return True

    def set_palette(self, palette) -> None:
        self.setStyleSheet(
            f"QFrame {{ background-color: {palette.surface}; border: 1px solid {palette.border_strong};"
            f" border-radius: 12px; }}"
        )
        self.hint.setStyleSheet(f"color: {palette.text_faint};")


class AttachmentChip(QFrame):
    removed = Signal(object)

    def __init__(self, payload: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.payload = payload
        props(self, badge=True)
        box = QHBoxLayout(self)
        box.setContentsMargins(9, 3, 5, 3)
        box.setSpacing(5)
        icon_name = "image" if payload.get("type") == "image" else "clip"
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap(icon_name, "#6E6C65", 13))
        box.addWidget(self.icon_label)
        self.name_label = label(payload.get("name", "file"))
        font = self.name_label.font()
        font.setPointSize(max(7, font.pointSize() - 1))
        self.name_label.setFont(font)
        box.addWidget(self.name_label)
        self.close_button = tool_button("x", size=11, clicked=lambda: self.removed.emit(self))
        self.close_button.setFixedSize(18, 18)
        box.addWidget(self.close_button)

    def set_palette(self, palette) -> None:
        icon_name = "image" if self.payload.get("type") == "image" else "clip"
        self.icon_label.setPixmap(icons.pixmap(icon_name, palette.text_muted, 13))
        self.name_label.setStyleSheet(f"color: {palette.text_muted};")
        self.close_button.setIcon(icons.icon("x", palette.text_muted, 11))


class Composer(QFrame):
    """Everything below the conversation."""

    sendRequested = Signal(str, list)
    stopRequested = Signal()
    modeChangeRequested = Signal(str)
    modelChangeRequested = Signal(str)
    attachRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ComposerBar")
        self.setAcceptDrops(True)
        self.attachments: List[Dict[str, Any]] = []
        self.project_path = ""
        self.slash_commands: List[str] = []
        self.running = False
        self._palette = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 10, 18, 12)
        outer.setSpacing(8)

        self.attach_row = QWidget()
        self.attach_box = QHBoxLayout(self.attach_row)
        self.attach_box.setContentsMargins(2, 0, 2, 0)
        self.attach_box.setSpacing(6)
        self.attach_box.addStretch(1)
        self.attach_row.setVisible(False)
        outer.addWidget(self.attach_row)

        self.frame = QFrame()
        self.frame.setObjectName("Card")
        frame_box = QVBoxLayout(self.frame)
        frame_box.setContentsMargins(12, 10, 10, 8)
        frame_box.setSpacing(8)

        self.edit = ComposerEdit()
        self.edit.submitRequested.connect(self.submit)
        self.edit.cancelRequested.connect(self.stopRequested.emit)
        self.edit.completionRequested.connect(self._show_completion)
        self.edit.completionClosed.connect(self._hide_completion)
        frame_box.addWidget(self.edit)

        controls = QWidget()
        control_box = QHBoxLayout(controls)
        control_box.setContentsMargins(0, 0, 0, 0)
        control_box.setSpacing(6)

        self.attach_button = tool_button("clip", size=15, tooltip=tr("common.browse"),
                                         clicked=self.attachRequested.emit)
        control_box.addWidget(self.attach_button)

        self.mode_pill = button(tr("perm.mode.default"), "shield", size=13)
        self.mode_pill.setObjectName("Chip")
        self.mode_pill.setCursor(Qt.PointingHandCursor)
        self.mode_pill.clicked.connect(self._mode_menu)
        control_box.addWidget(self.mode_pill)

        self.model_pill = button(tr("model.default"), "cpu", size=13)
        self.model_pill.setObjectName("Chip")
        self.model_pill.setCursor(Qt.PointingHandCursor)
        self.model_pill.clicked.connect(self._model_menu)
        control_box.addWidget(self.model_pill)

        control_box.addStretch(1)

        self.hint_label = label("Enter ↵", faint=True)
        control_box.addWidget(self.hint_label)

        self.stop_button = button(tr("chat.stop"), "stop", size=14, danger=True,
                                  tooltip=tr("chat.stop_hint"), clicked=self.stopRequested.emit)
        self.stop_button.setVisible(False)
        control_box.addWidget(self.stop_button)

        self.send_button = button("", "send", primary=True, size=15, tooltip=tr("chat.send"),
                                  clicked=self.submit)
        self.send_button.setFixedSize(38, 34)
        control_box.addWidget(self.send_button)
        frame_box.addWidget(controls)

        outer.addWidget(self.frame)

        self.popup = CompletionPopup(self.window() if self.window() else self)
        self.popup.picked.connect(self._picked)
        self.set_running(False)

    # ------------------------------------------------------------------ #
    def set_project(self, path: str) -> None:
        self.project_path = path or ""

    def set_slash_commands(self, commands: List[str]) -> None:
        self.slash_commands = [c.lstrip("/") for c in commands or []]

    def set_running(self, running: bool) -> None:
        self.running = running
        self.stop_button.setVisible(running)
        self.send_button.setVisible(not running)
        self.edit.setReadOnly(False)
        self.hint_label.setText(tr("chat.stop_hint") if running else "Enter ↵")

    def set_enabled_state(self, enabled: bool, placeholder: str = "") -> None:
        self.edit.setEnabled(enabled)
        self.edit.setPlaceholderText(placeholder or tr("chat.placeholder"))
        self.send_button.setEnabled(enabled)
        self.attach_button.setEnabled(enabled)

    def set_mode(self, mode: str) -> None:
        names = {
            "default": "perm.mode.default", "acceptEdits": "perm.mode.acceptEdits",
            "plan": "perm.mode.plan", "bypassPermissions": "perm.mode.bypassPermissions",
            "dontAsk": "perm.mode.dontAsk", "auto": "perm.mode.auto",
        }
        self.mode_pill.setText(tr(names.get(mode, "perm.mode.default")))
        icon_name = {"default": "shield", "acceptEdits": "check_circle", "plan": "compass",
                     "bypassPermissions": "zap", "dontAsk": "lock", "auto": "sparkles"}.get(mode, "shield")
        color = "#B3453B" if mode == "bypassPermissions" else ("#B4801F" if mode in ("acceptEdits", "dontAsk") else "#6E6C65")
        self.mode_pill.setIcon(icons.icon(icon_name, color, 13))
        self.mode_pill.setToolTip(tr(f"perm.mode.{mode}"))
        if mode == "bypassPermissions":
            self.mode_pill.setStyleSheet("color: #B3453B; border-color: #B3453B;")
        else:
            self.mode_pill.setStyleSheet("")

    def set_model(self, model: str) -> None:
        self.model_pill.setText(model or tr("model.default"))
        self.model_pill.setToolTip(f"{tr('model.label')}: {model or tr('model.default')}")

    # ------------------------------------------------------------------ #
    def submit(self) -> None:
        if self.popup.isVisible():
            if self.popup.accept_current():
                return
        text = self.edit.toPlainText().strip()
        if not text and not self.attachments:
            return
        self.sendRequested.emit(text, list(self.attachments))
        self.edit.clear()
        self.clear_attachments()

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text)
        self.edit.setFocus()

    def focus_input(self) -> None:
        self.edit.setFocus()

    def _mode_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        for mode in ("default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"):
            action = menu.addAction(tr(f"perm.mode.{mode}"))
            action.setData(mode)
        chosen = menu.exec(self.mode_pill.mapToGlobal(QPoint(0, self.mode_pill.height() + 4)))
        if chosen is not None:
            self.modeChangeRequested.emit(str(chosen.data()))

    def _model_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        for model in ("", "sonnet", "opus", "haiku", "claude-sonnet-4-5", "claude-opus-4-1"):
            action = menu.addAction(model or tr("model.default"))
            action.setData(model)
        menu.addSeparator()
        action = menu.addAction("Custom…")
        action.setData("__custom__")
        chosen = menu.exec(self.model_pill.mapToGlobal(QPoint(0, self.model_pill.height() + 4)))
        if chosen is None:
            return
        value = str(chosen.data())
        if value == "__custom__":
            from PySide6.QtWidgets import QInputDialog

            text, ok = QInputDialog.getText(self, tr("model.label"), "Model name:")
            if ok and text.strip():
                value = text.strip()
            else:
                return
        self.modelChangeRequested.emit(value)

    # ------------------------------------------------------------------ #
    # attachments
    # ------------------------------------------------------------------ #
    def add_attachment(self, payload: Dict[str, Any]) -> None:
        self.attachments.append(payload)
        chip = AttachmentChip(payload)
        chip.removed.connect(self.remove_attachment)
        if self._palette is not None:
            chip.set_palette(self._palette)
        self.attach_box.insertWidget(self.attach_box.count() - 1, chip)
        self.attach_row.setVisible(True)

    def remove_attachment(self, chip: AttachmentChip) -> None:
        if chip.payload in self.attachments:
            self.attachments.remove(chip.payload)
        self.attach_box.removeWidget(chip)
        chip.deleteLater()
        self.attach_row.setVisible(bool(self.attachments))

    def clear_attachments(self) -> None:
        for payload in list(self.attachments):
            for index in range(self.attach_box.count()):
                widget = self.attach_box.itemAt(index).widget()
                if isinstance(widget, AttachmentChip) and widget.payload == payload:
                    self.remove_attachment(widget)
                    break
        self.attachments.clear()
        self.attach_row.setVisible(False)

    def attach_paths(self, paths: List[str]) -> int:
        added = 0
        for raw in paths:
            path = Path(raw)
            try:
                if not path.exists():
                    continue
                suffix = path.suffix.lower()
                if suffix in IMAGE_TYPES:
                    data = base64.b64encode(path.read_bytes()).decode("ascii")
                    self.add_attachment({
                        "type": "image", "name": path.name, "path": str(path),
                        "source": {"type": "base64", "media_type": IMAGE_TYPES[suffix], "data": data},
                    })
                    added += 1
                    continue
                if path.is_dir():
                    continue
                size = path.stat().st_size
                text = path.read_text(encoding="utf-8", errors="replace")
                if len(text) > MAX_ATTACHMENT_CHARS:
                    text = text[:MAX_ATTACHMENT_CHARS] + "\n… truncated …"
                lang = suffix.lstrip(".")
                self.add_attachment({
                    "type": "text", "name": f"{path.name} ({size // 1024} KB)" if size > 1024 else path.name,
                    "path": str(path),
                    "text": f"Attached file `{path}`:\n\n```{lang}\n{text}\n```",
                })
                added += 1
            except OSError:
                continue
        return added

    def attach_clipboard_image(self) -> bool:
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            return False
        from PySide6.QtCore import QBuffer

        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        image.save(buffer, "PNG")
        data = bytes(buffer.data()).decode("latin1")
        buffer.close()
        self.add_attachment({
            "type": "image", "name": "clipboard.png", "path": "",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": base64.b64encode(data.encode("latin1")).decode("ascii")},
        })
        return True

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        if urls:
            self.attach_paths(urls)
            event.acceptProposedAction()

    # ------------------------------------------------------------------ #
    # completion
    # ------------------------------------------------------------------ #
    def _show_completion(self, kind: str, query: str) -> None:
        if kind == "command":
            items = projects.suggest_slash_commands(self.slash_commands, query)
            if not items:
                self._hide_completion()
                return
            self.popup.show_items(items, "command", self._anchor_point(), "Slash commands from Claude Code")
        else:
            if not self.project_path:
                self._hide_completion()
                return
            files = projects.suggest_files(self.project_path, query, limit=10)
            if not files:
                self._hide_completion()
                return
            self.popup.show_items(files, "file", self._anchor_point(), "Files in the project")
        self.edit.set_completion_open(True)

    def _hide_completion(self) -> None:
        self.popup.hide()
        self.edit.set_completion_open(False)

    def _anchor_point(self) -> QPoint:
        cursor_rect = self.edit.cursorRect()
        point = self.edit.mapToGlobal(cursor_rect.bottomLeft())
        return point

    def _picked(self, text: str, kind: str) -> None:
        self.edit.apply_completion(text, kind)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.popup.isVisible():
            if event.key() == Qt.Key_Down:
                self.popup.move_selection(1)
                return
            if event.key() == Qt.Key_Up:
                self.popup.move_selection(-1)
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                if self.popup.accept_current():
                    return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    def set_palette(self, palette) -> None:
        self._palette = palette
        self.frame.setStyleSheet(
            f"QFrame#Card {{ background-color: {palette.surface}; border: 1px solid {palette.border_strong};"
            f" border-radius: 16px; }}"
        )
        self.edit.setStyleSheet(
            f"QPlainTextEdit#Composer {{ background: transparent; border: none; color: {palette.text};"
            f" font-size: {palette.font_size if hasattr(palette, 'font_size') else 14}px; }}"
        )
        self.send_button.setIcon(icons.icon("send", palette.text_on_accent, 15))
        self.stop_button.setIcon(icons.icon("stop", palette.danger, 14))
        self.attach_button.setIcon(icons.icon("clip", palette.text_muted, 15))
        self.hint_label.setStyleSheet(f"color: {palette.text_faint};")
        self.popup.set_palette(palette)
        for index in range(self.attach_box.count()):
            widget = self.attach_box.itemAt(index).widget()
            if isinstance(widget, AttachmentChip):
                widget.set_palette(palette)
