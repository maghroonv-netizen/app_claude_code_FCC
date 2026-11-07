"""End-to-end: the real `claude` CLI driven by our backend, with a local mock
Anthropic API. Skipped automatically when the CLI or the mock harness is
unavailable; enable with FCC_E2E=1 (the CI/dev default where the CLI exists).
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))

from fcc.claude import protocol  # noqa: E402
from fcc.claude import discovery  # noqa: E402
from fcc.claude.permissions import PermissionAnswer, PermissionBroker  # noqa: E402
from fcc.claude.session import ClaudeBackend  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("FCC_E2E", "0") != "1" or discovery.find_claude() is None,
    reason="set FCC_E2E=1 and install the Claude Code CLI to run this",
)


def test_full_turn_with_permission_handshake(qtbot, tmp_config, tmp_path):
    from mock_anthropic_api import start_server, stop_server

    project = tmp_path / "project"
    project.mkdir()
    target = project / "note.txt"

    process, base_url = start_server(str(target))
    try:
        tmp_config.env = {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_API_KEY": "test-key",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
        }
        tmp_config.permission_timeout_sec = 60
        tmp_config.startup_timeout_sec = 60

        broker = PermissionBroker(lambda: tmp_config, lambda: str(project))
        asks = []
        broker.ask_user.connect(lambda ask: (
            asks.append(ask),
            broker.resolve(ask.id, PermissionAnswer(behavior="allow",
                                                     updated_input=ask.tool_input)),
        ))

        backend = ClaudeBackend(lambda: tmp_config, broker)
        events, turns, errors, states = [], [], [], []
        backend.event.connect(events.append)
        backend.turn_finished.connect(turns.append)
        backend.error_occurred.connect(lambda code, msg: errors.append((code, msg)))
        backend.state_changed.connect(states.append)

        backend.start(str(project))
        qtbot.waitUntil(lambda: backend.is_running(), timeout=60000)
        assert backend.send("write the note file")
        qtbot.waitUntil(lambda: len(turns) >= 1, timeout=120000)

        kinds = {event.kind for event in events}
        assert protocol.SESSION_INIT in kinds
        assert asks, "the CLI must ask the host before writing outside its sandbox"
        assert protocol.TOOL_START in kinds
        assert protocol.TOOL_RESULT in kinds
        assert protocol.MESSAGE_FINAL in kinds
        assert protocol.TURN_DONE in kinds
        assert asks and asks[0].tool_name == "Write"
        assert not errors, errors
        assert target.exists(), "the mock API's Write call should have created the file"
        assert target.read_text(encoding="utf-8").strip() == "hello from the e2e test"

        summary = turns[0]
        assert summary.get("is_error") is False
        backend.stop()
        qtbot.waitUntil(lambda: not backend.is_running(), timeout=30000)
    finally:
        stop_server(process)


def test_permission_deny_reaches_cli(qtbot, tmp_config, tmp_path):
    from mock_anthropic_api import start_server, stop_server

    project = tmp_path / "project2"
    project.mkdir()
    target = project / "blocked.txt"

    process, base_url = start_server(str(target))
    try:
        tmp_config.env = {"ANTHROPIC_BASE_URL": base_url, "ANTHROPIC_API_KEY": "test-key",
                          "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                          "DISABLE_TELEMETRY": "1"}
        tmp_config.permission_timeout_sec = 60
        broker = PermissionBroker(lambda: tmp_config, lambda: str(project))
        broker.ask_user.connect(lambda ask: broker.resolve(
            ask.id, PermissionAnswer(behavior="deny", message="Denied by the test")))

        backend = ClaudeBackend(lambda: tmp_config, broker)
        events, turns = [], []
        backend.event.connect(events.append)
        backend.turn_finished.connect(turns.append)
        backend.start(str(project))
        qtbot.waitUntil(lambda: backend.is_running(), timeout=60000)
        backend.send("try to write")
        qtbot.waitUntil(lambda: len(turns) >= 1, timeout=120000)

        denied_results = [event for event in events
                          if event.kind == protocol.TOOL_RESULT and event.payload.get("is_error")]
        assert denied_results, "a denied Write must surface as an error tool_result"
        assert not target.exists()
        backend.stop()
        qtbot.waitUntil(lambda: not backend.is_running(), timeout=30000)
    finally:
        stop_server(process)
