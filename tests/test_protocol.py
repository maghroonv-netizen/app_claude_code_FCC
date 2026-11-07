"""Event normalisation, verified against real Claude Code 2.1.x output."""

import json

from fcc.claude import protocol

INIT = json.loads('{"type":"system","subtype":"init","cwd":"/tmp/x","session_id":"s1","tools":["Bash","Read","Write"],"mcp_servers":[],"model":"claude-opus-5-5","permissionMode":"default","slash_commands":["help","model"],"claude_code_version":"2.1.318","apiKeySource":"ANTHROPIC_API_KEY","output_style":"default","capabilities":["msg_lifecycle_v1"]}')
STREAM_TEXT = json.loads('{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello "}},"session_id":"s1","parent_tool_use_id":null,"uuid":"u1","api_message_id":"m1"}')
TOOL_START = json.loads('{"type":"stream_event","event":{"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"Bash","input":{}}},"session_id":"s1","api_message_id":"m1"}')
TOOL_DELTA = json.loads('{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"command\\""}},"session_id":"s1","api_message_id":"m1"}')
ASSISTANT = json.loads('{"type":"assistant","message":{"id":"m1","type":"message","role":"assistant","model":"claude-opus-5-5","content":[{"type":"text","text":"Hello world"},{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls"}}],"stop_reason":null,"usage":{"input_tokens":10,"output_tokens":4}},"parent_tool_use_id":null,"session_id":"s1","uuid":"u2","timestamp":"2026-01-01T00:00:00Z"}')
USER_RESULT = json.loads('{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_1","type":"tool_result","content":"a.txt\\nb.txt","is_error":false}]},"parent_tool_use_id":null,"session_id":"s1","uuid":"u3","tool_use_result":{"stdout":"a.txt\\nb.txt","stderr":"","interrupted":false},"tool_result_meta":[{"id":"toolu_1","permission_decision":{"decision":"accept","source":"config"}}]}')
RESULT = json.loads('{"duration_api_ms":900,"stop_reason":"end_turn","session_id":"s1","total_cost_usd":0.0012,"usage":{"input_tokens":120,"output_tokens":40},"modelUsage":{"claude-opus-5-5":{"inputTokens":120,"outputTokens":40,"contextWindow":200000}},"permission_denials":[],"is_error":false,"num_turns":2,"subtype":"success","result":"Hello world","type":"result","duration_ms":1200}')
DENIED = json.loads('{"type":"system","subtype":"permission_denied","tool_name":"Write","tool_use_id":"toolu_2","message":"Claude requested permissions to write to /x, but you haven\'t granted it yet.","session_id":"s1"}')
AUTH_ERROR = json.loads('{"type":"assistant","message":{"id":"m2","role":"assistant","content":[{"type":"text","text":"Not logged in · Please run /login"}],"usage":{}},"session_id":"s1","error":"authentication_failed","is_api_error_message":true}')


def make() -> protocol.StreamInterpreter:
    return protocol.StreamInterpreter()


def test_session_init_fields():
    events = make().feed(INIT)
    assert events and events[0].kind == protocol.SESSION_INIT
    payload = events[0].payload
    assert payload["session_id"] == "s1"
    assert payload["model"] == "claude-opus-5-5"
    assert payload["cli_version"] == "2.1.318"
    assert payload["tools"] == ["Bash", "Read", "Write"]
    assert payload["api_key_source"] == "ANTHROPIC_API_KEY"


def test_text_delta_and_final():
    interpreter = make()
    events = interpreter.feed(STREAM_TEXT)
    assert [e.kind for e in events] == [protocol.TEXT_DELTA]
    assert events[0].payload["text"] == "Hello "
    events = interpreter.feed(ASSISTANT)
    kinds = [e.kind for e in events]
    assert protocol.MESSAGE_FINAL in kinds
    assert protocol.TOOL_START in kinds
    final = next(e for e in events if e.kind == protocol.MESSAGE_FINAL)
    assert final.payload["text"] == "Hello world"
    tool = next(e for e in events if e.kind == protocol.TOOL_START)
    assert tool.payload["name"] == "Bash"
    assert tool.payload["input"] == {"command": "ls"}


def test_tool_input_delta_routing():
    interpreter = make()
    interpreter.feed(TOOL_START)
    events = interpreter.feed(TOOL_DELTA)
    assert events and events[0].kind == protocol.TOOL_INPUT_DELTA
    assert events[0].payload["tool_use_id"] == "toolu_1"


def test_tool_result_and_decision():
    interpreter = make()
    interpreter.feed(TOOL_START)
    interpreter.feed(ASSISTANT)
    events = interpreter.feed(USER_RESULT)
    assert events and events[0].kind == protocol.TOOL_RESULT
    payload = events[0].payload
    assert payload["tool_use_id"] == "toolu_1"
    assert payload["permission_decision"] == "accept"
    assert payload["structured"]["stdout"] == "a.txt\nb.txt"


def test_turn_done_summary():
    events = make().feed(RESULT)
    assert events[0].kind == protocol.TURN_DONE
    summary = protocol.summarize_result(events[0].payload)
    assert summary["cost_usd"] == 0.0012
    assert summary["context_window"] == 200000
    assert summary["tokens_out"] == 40


def test_permission_denied_event():
    events = make().feed(DENIED)
    assert events[0].kind == protocol.PERMISSION_DENIED
    assert events[0].payload["tool_name"] == "Write"


def test_auth_error_detected():
    events = make().feed(AUTH_ERROR)
    errors = [e for e in events if e.kind == protocol.ERROR]
    assert errors and errors[0].payload["code"] == "auth"


def test_formatting_helpers():
    assert protocol.format_duration(1500) == "1.5s"
    assert protocol.format_duration(75000) == "1m 15s"
    assert protocol.format_cost(0.001234) == "$0.0012"
    assert protocol.format_cost(1.5) == "$1.50"
    assert protocol.format_tokens(1500) == "1.5k"
    assert protocol.format_tokens(2_500_000) == "2.50M"
