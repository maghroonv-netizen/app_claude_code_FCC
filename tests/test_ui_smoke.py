"""Offscreen Qt smoke tests: widgets build, events render, dialogs construct."""

import pytest

from fcc.claude import protocol
from fcc.claude.permissions import PermissionAsk
from fcc.theme import palette_for
from fcc.ui.common import set_palette
from fcc.ui.widgets.chat_view import ChatView
from fcc.ui.widgets.composer import Composer
from fcc.ui.widgets.markdown_view import MarkdownView
from fcc.ui.widgets.sidebar import Sidebar
from fcc.ui.widgets.tool_card import PermissionCard
from fcc.ui.dialogs.settings import SettingsDialog
from fcc.ui.dialogs.system import DiagnosticsDialog


@pytest.fixture()
def palette():
    return palette_for("light")


def test_chat_stream_renders(qtbot, palette):
    view = ChatView()
    set_palette(view, palette)
    qtbot.addWidget(view)

    view.handle(protocol.UiEvent(protocol.SESSION_INIT, {
        "session_id": "s1", "model": "claude-opus-5-5", "cli_version": "2.1.318",
        "cwd": "/tmp", "tools": ["Bash"], "permission_mode": "default",
        "slash_commands": ["help"], "agents": [], "skills": [], "api_key_source": "env"}))
    view.handle(protocol.UiEvent(protocol.TEXT_DELTA, {"message_id": "m1", "text": "Hello "}))
    view.handle(protocol.UiEvent(protocol.TEXT_DELTA, {"message_id": "m1", "text": "**world**"}))
    view.handle(protocol.UiEvent(protocol.TOOL_START, {
        "message_id": "m1", "tool_use_id": "t1", "name": "Bash", "input": {"command": "ls"}}))
    view.handle(protocol.UiEvent(protocol.TOOL_RESULT, {
        "tool_use_id": "t1", "name": "Bash", "is_error": False,
        "content": "a.txt", "structured": {"stdout": "a.txt"}, "permission_decision": "accept"}))
    view.handle(protocol.UiEvent(protocol.MESSAGE_FINAL, {"message_id": "m1", "text": "Hello **world**"}))
    view.handle(protocol.UiEvent(protocol.TURN_DONE, {
        "duration_ms": 100, "duration_api_ms": 90, "cost_usd": 0.01, "tokens_in": 10,
        "tokens_out": 5, "num_turns": 1, "is_error": False, "context_window": 200000}))

    exported = view.export_markdown("Smoke test")
    assert "Hello" in exported
    assert "world" in exported
    assert "ls" in exported
    assert "a.txt" in exported

    ask = PermissionAsk(id="a1", tool_name="Write", title="Write file",
                        tool_input={"file_path": "/x/y.py"}, description="Writes y.py",
                        subject="/x/y.py")
    card = view.add_permission(ask)
    assert view.permission_card("a1") is card
    card.decide("allow", "")


def test_permission_card_flow(qtbot, palette):
    ask = PermissionAsk(id="a2", tool_name="Bash", title="Run command",
                        tool_input={"command": "git status"}, description="Runs git status",
                        subject="git status")
    card = PermissionCard(ask)
    set_palette(card, palette)
    qtbot.addWidget(card)
    decisions = []
    card.decided.connect(lambda who, behavior, scope, message:
                         decisions.append((behavior, scope, message)))
    card.decide("allow", "")
    assert decisions and decisions[0][0] == "allow"


def test_composer_send_and_context(qtbot, palette, tmp_path):
    composer = Composer()
    set_palette(composer, palette)
    qtbot.addWidget(composer)
    file_path = tmp_path / "notes.md"
    file_path.write_text("context", encoding="utf-8")
    composer.set_project(str(tmp_path))
    assert composer.attach_paths([str(file_path)]) == 1
    assert composer.attachments and composer.attachments[0]["name"] == "notes.md"
    composer.set_text("hello there")
    with qtbot.waitSignal(composer.sendRequested, timeout=2000) as blocker:
        composer.submit()
    text, payloads = blocker.args
    assert text == "hello there"
    assert payloads and payloads[0]["name"] == "notes.md"
    assert composer.attachments == []


def test_sidebar_renders_records(qtbot, palette, tmp_config):
    record = tmp_config.upsert_project("/tmp/demo")
    session = tmp_config.create_session("/tmp/demo", "Chat one")
    sidebar = Sidebar()
    set_palette(sidebar, palette)
    qtbot.addWidget(sidebar)
    sidebar.refresh_projects([record], record.path)
    sidebar.refresh_sessions([session], session.id)
    sidebar.set_status("ready", "idle")


def test_markdown_view_stream(qtbot):
    widget = MarkdownView()
    qtbot.addWidget(widget)
    widget.set_markdown("# Heading\n\n- item", streaming=True)
    widget.set_markdown("# Heading\n\n- item\n- two", streaming=False)
    assert "Heading" in widget.plain()


def test_settings_dialog_constructs(qtbot, tmp_config):
    dialog = SettingsDialog(tmp_config)
    qtbot.addWidget(dialog)
    assert dialog.tabs.count() >= 4


def test_diagnostics_dialog_constructs(qtbot, tmp_config):
    dialog = DiagnosticsDialog(tmp_config, None)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle()


def test_main_window_smoke(qtbot, tmp_config):
    from fcc.ui.main_window import MainWindow

    window = MainWindow(tmp_config)
    qtbot.addWidget(window)
    # Let the deferred startup probe fire and run to completion inside the
    # test, so no thread can leak past teardown (a hard-crash risk on Windows).
    qtbot.wait(200)
    if window._probe is not None:
        assert window._probe.wait(20000)
    window.toggle_theme()
    assert tmp_config.theme in ("light", "dark")
    window.toggle_language()
    assert tmp_config.language in ("en", "fa")
    window.toggle_theme()
    window.toggle_language()
    window.close()


def test_trust_permission_build_dialogs(qtbot, tmp_config):
    from fcc.claude.permissions import PermissionAsk, rule_options
    from fcc.ui.dialogs.permission import PermissionDialog
    from fcc.ui.dialogs.system import BuildDialog
    from fcc.ui.dialogs.trust import TrustDialog

    trust = TrustDialog("/tmp/some project", tmp_config)
    set_palette(trust, palette_for("light"))
    qtbot.addWidget(trust)

    ask = PermissionAsk(id="x1", tool_name="Bash", tool_input={"command": "git push"},
                        subject="git push", title="Run command", description="push")
    dialog = PermissionDialog(ask, rule_options(ask, "/tmp/some project"))
    set_palette(dialog, palette_for("light"))
    qtbot.addWidget(dialog)

    build = BuildDialog(tmp_config)
    set_palette(build, palette_for("light"))
    qtbot.addWidget(build)


def test_toast_stack_keeps_both_toasts_visible(qtbot):
    from PySide6.QtWidgets import QWidget

    from fcc.ui.widgets.panels import ToastStack

    host = QWidget()
    host.resize(900, 700)
    qtbot.addWidget(host)
    stack = ToastStack(host)
    stack.show()
    host.show()
    first = stack.show_toast("first notification", "success", timeout=0)
    second = stack.show_toast("second notification", "error", timeout=0)
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    stack._relayout()
    QApplication.processEvents()
    assert first in stack._toasts and second in stack._toasts
    geo1, geo2 = first.geometry(), second.geometry()
    # no overlap and both inside the stack rectangle
    assert geo1.bottom() < geo2.top() or geo2.bottom() < geo1.top()
    for geo in (geo1, geo2):
        assert geo.top() >= 0 and geo.bottom() <= stack.height()
        assert geo.left() >= 0 and geo.right() <= stack.width()
    assert stack.height() >= geo1.height() + geo2.height()


def test_trust_dialog_cycles_all_modes(qtbot):
    from fcc.config import PERMISSION_MODES
    from fcc.ui.dialogs.trust import TrustDialog

    for mode in PERMISSION_MODES:
        dialog = TrustDialog("/tmp/some project", mode)
        set_palette(dialog, palette_for("light"))
        qtbot.addWidget(dialog)
        assert dialog.mode == mode
        dialog._mode_changed()
        dialog._allow()
        assert dialog.granted is True
        assert dialog.mode in PERMISSION_MODES


def test_session_row_looks_professional(qtbot, tmp_config):
    from fcc.ui.widgets.sidebar import SessionRow

    record = tmp_config.create_session("/tmp/demo", "Refactor payments")
    record.model = "claude-opus-5-5"
    row = SessionRow(record, active=True)
    set_palette(row, palette_for("dark"))
    qtbot.addWidget(row)
    assert row.property("active") == "true"
    assert row.objectName() == "SessionItem"
    assert row.chip.text() == "claude-opus-5-5"
