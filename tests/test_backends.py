"""Demo backend behaviour and the transcript replay helper."""

from fcc.claude import transcript
from fcc.claude import demo_script  # noqa: F401  (import sanity)
from fcc.claude.session import DemoBackend as Demo


def test_demo_backend_turn(qtbot, tmp_config):
    backend = Demo()
    states, events, turns = [], [], []
    backend.state_changed.connect(states.append)
    backend.event.connect(events.append)
    backend.turn_finished.connect(turns.append)
    backend.start("/tmp/demo-project")
    qtbot.waitUntil(lambda: backend.is_running(), timeout=5000)
    assert backend.send("hello demo")
    qtbot.waitUntil(lambda: len(turns) >= 1, timeout=15000)
    kinds = {event.kind for event in events}
    from fcc.claude import protocol

    assert protocol.SESSION_INIT in kinds
    assert protocol.MESSAGE_FINAL in kinds
    assert protocol.TURN_DONE in kinds
    backend.stop()
    qtbot.waitUntil(lambda: not backend.is_running(), timeout=5000)


def test_transcript_replay_events(tmp_path):
    from fcc.claude import protocol

    path = tmp_path / "t.jsonl"
    lines = [
        {"type": "system", "subtype": "init", "session_id": "s1", "cwd": "/x", "model": "m",
         "tools": [], "claude_code_version": "2.1.318"},
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "hello"}], "usage": {}}, "uuid": "u1"},
        {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.0,
         "usage": {}, "duration_ms": 1, "result": "hello"},
    ]
    records = [{"direction": "out", "payload": {"type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}}]
    records += [{"direction": "in", "line": __import__("json").dumps(item)} for item in lines]
    path.write_text("\n".join(__import__("json").dumps(item) for item in records),
                    encoding="utf-8")
    events = transcript.replay(path)
    assert len(events) >= 4
    kinds = [event.kind for event in events]
    assert protocol.USER_ECHO in kinds
    assert protocol.MESSAGE_FINAL in kinds
    assert protocol.TURN_DONE in kinds
