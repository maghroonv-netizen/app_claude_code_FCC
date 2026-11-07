"""A believable offline Claude Code session for demo mode and UI tests."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, List, Tuple

from fcc.claude import protocol
from fcc.claude.control import PermissionAsk

Step = Tuple[str, dict, int]


def _words(text: str, message_id: str, per: int = 6, delay: int = 34) -> List[Step]:
    out: List[Step] = []
    chunks = text.split(" ")
    for index in range(0, len(chunks), per):
        piece = " ".join(chunks[index:index + per])
        if index + per < len(chunks):
            piece += " "
        out.append((protocol.TEXT_DELTA, {"message_id": message_id, "text": piece, "parent_tool_use_id": None}, delay))
    return out


def build_script(prompt: str, project_path: str = "") -> List[Any]:
    """Return the ordered demo events for one conversational turn."""
    folder = Path(project_path or ".").name or "your-project"
    message_id = f"msg_{uuid.uuid4().hex[:6]}"
    tool_read = f"toolu_{uuid.uuid4().hex[:8]}"
    tool_bash = f"toolu_{uuid.uuid4().hex[:8]}"
    tool_write = f"toolu_{uuid.uuid4().hex[:8]}"
    file_path = str(Path(project_path or ".") / "src" / "main.py")
    script: List[Any] = []

    script.append((protocol.STATUS, {"status": "requesting"}, 160))
    script.append((protocol.MESSAGE_END, {"message_id": message_id, "phase": "start", "model": "claude-sonnet-4-5",
                                          "ttft_ms": 420, "usage": {"input_tokens": 1204, "output_tokens": 1}}, 220))
    script.append((protocol.THINKING_DELTA, {
        "message_id": message_id,
        "text": f"The user asked about “{prompt.strip()[:80]}”. Let me look at the project structure first, "
                "then read the entry point and check whether the tests pass.",
    }, 420))

    intro = f"Looking into **{folder}** now — reading the entry point and checking the layout."
    script.extend(_words(intro, message_id))

    # Read tool ----------------------------------------------------------- #
    script.append((protocol.TOOL_START, {
        "tool_use_id": tool_read, "name": "Read", "partial": False,
        "input": {"file_path": file_path, "limit": 120}, "message_id": message_id,
    }, 260))
    script.append((protocol.TOOL_RESULT, {
        "tool_use_id": tool_read, "name": "Read", "input": {"file_path": file_path},
        "content": [{"type": "text", "text": (
            '"""Application entry point."""\n\nfrom .app import create_app\n\n\n'
            'def main() -> int:\n    app = create_app()\n    return app.run()\n\n\n'
            'if __name__ == "__main__":\n    raise SystemExit(main())\n')}],
        "is_error": False,
        "structured": {"file": {"filePath": file_path, "content": "def main() -> int:\n    ...",
                                "numLines": 12, "startLine": 1, "totalLines": 12}},
        "meta": {}, "permission_decision": "accept", "permission_source": "config",
    }, 320))

    # Bash tool ----------------------------------------------------------- #
    script.append((protocol.TOOL_START, {
        "tool_use_id": tool_bash, "name": "Bash", "partial": False,
        "input": {"command": "pytest -q --maxfail=1", "description": "Run the test suite"},
        "message_id": message_id,
    }, 280))
    script.append((protocol.TOOL_RESULT, {
        "tool_use_id": tool_bash, "name": "Bash",
        "input": {"command": "pytest -q --maxfail=1"},
        "content": [{"type": "text", "text": "..........F....\n1 failed, 14 passed in 3.42s"}],
        "is_error": True,
        "structured": {"stdout": "..........F....", "stderr": "1 failed, 14 passed in 3.42s",
                       "interrupted": False},
        "meta": {}, "permission_decision": "accept", "permission_source": "config",
    }, 420))

    # Todo list ----------------------------------------------------------- #
    script.append((protocol.TOOL_START, {
        "tool_use_id": f"toolu_{uuid.uuid4().hex[:8]}", "name": "TodoWrite", "partial": False,
        "input": {"todos": [
            {"content": "Read the entry point", "status": "completed", "activeForm": "Reading the entry point"},
            {"content": "Run the test suite", "status": "completed", "activeForm": "Running the test suite"},
            {"content": "Fix the failing assertion", "status": "in_progress", "activeForm": "Fixing the failing assertion"},
            {"content": "Re-run tests and summarise", "status": "pending", "activeForm": "Re-running tests"},
        ]},
        "message_id": message_id,
    }, 200))
    script.append((protocol.TODOS, {"items": [
        {"content": "Read the entry point", "status": "completed", "activeForm": "Reading the entry point"},
        {"content": "Run the test suite", "status": "completed", "activeForm": "Running the test suite"},
        {"content": "Fix the failing assertion", "status": "in_progress", "activeForm": "Fixing the failing assertion"},
        {"content": "Re-run tests and summarise", "status": "pending", "activeForm": "Re-running tests"},
    ]}, 220))

    # A real permission prompt (blocking, handled by the UI) -------------- #
    def ask_permission(backend) -> int:
        ask = PermissionAsk(
            id=uuid.uuid4().hex[:10],
            tool_name="Edit",
            tool_input={"file_path": file_path,
                        "old_string": "    return app.run()",
                        "new_string": "    return app.run(debug=True)"},
            tool_use_id=tool_write,
            subject=file_path,
            title=f"Edit {Path(file_path).name}",
            source="demo",
            asked_at=time.time(),
        )
        backend.ask_demo_permission(ask)
        return 300

    script.append(ask_permission)

    script.append((protocol.TOOL_START, {
        "tool_use_id": tool_write, "name": "Edit", "partial": False,
        "input": {"file_path": file_path, "old_string": "    return app.run()",
                  "new_string": "    return app.run(debug=True)"},
        "message_id": message_id,
    }, 240))
    script.append((protocol.TOOL_RESULT, {
        "tool_use_id": tool_write, "name": "Edit",
        "input": {"file_path": file_path},
        "content": [{"type": "text", "text": f"Updated {file_path}"}],
        "is_error": False,
        "structured": {"filePath": file_path, "oldString": "    return app.run()",
                       "newString": "    return app.run(debug=True)",
                       "structuredPatch": [{"oldStart": 6, "oldLines": 2, "newStart": 6, "newLines": 2,
                                            "lines": ["-    return app.run()", "+    return app.run(debug=True)"]}],
                       "gitDiff": {"filename": "src/main.py", "status": "modified",
                                   "additions": 1, "deletions": 1, "changes": 2}},
        "meta": {}, "permission_decision": "accept", "permission_source": "user",
    }, 340))

    final_id = f"msg_{uuid.uuid4().hex[:6]}"
    script.append((protocol.MESSAGE_END, {"message_id": final_id, "phase": "start", "model": "claude-sonnet-4-5",
                                          "usage": {"input_tokens": 3120, "output_tokens": 1}}, 200))
    answer = (
        "Done. Here is what I found and changed:\n\n"
        "1. **`src/main.py`** starts the app through `create_app()`.\n"
        "2. The suite had **one failing test** — `test_debug_flag`.\n"
        "3. I enabled `debug=True` when running the app, which is what that test expects.\n\n"
        "```python\n"
        "def main() -> int:\n"
        "    app = create_app()\n"
        "    return app.run(debug=True)\n"
        "```\n\n"
        "Re-run `pytest -q` and all 15 tests should pass. Want me to add a regression test for the flag?"
    )
    script.extend(_words(answer, final_id, per=5, delay=30))
    script.append((protocol.MESSAGE_FINAL, {"message_id": final_id, "text": answer, "thinking": "",
                                            "model": "claude-sonnet-4-5",
                                            "usage": {"input_tokens": 3120, "output_tokens": 168}}, 120))
    script.append((protocol.TURN_DONE, {
        "subtype": "success", "is_error": False, "result_text": "", "duration_ms": 8421,
        "duration_api_ms": 6120, "num_turns": 4, "total_cost_usd": 0.0183,
        "usage": {"input_tokens": 4324, "output_tokens": 578, "cache_read_input_tokens": 2048},
        "model_usage": {"claude-sonnet-4-5": {"inputTokens": 4324, "outputTokens": 578, "contextWindow": 200000}},
        "context_window": 200000, "permission_denials": [], "terminal_reason": "",
        "session_id": "", "error_code": "",
    }, 160))
    return script
