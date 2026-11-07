"""The MCP-over-control permission handshake, mirroring the live protocol."""

import json

from fcc.claude.capabilities import PERMISSION_SERVER_NAME
from fcc.claude.control import (ControlChannel, PermissionAnswer, PermissionAsk,
                                PERMISSION_TOOL)


class Recorder:
    def __init__(self):
        self.out = []

    def __call__(self, payload):
        self.out.append(payload)

    def mcp_results(self):
        results = []
        for item in self.out:
            if item.get("type") != "control_response":
                continue
            response = item.get("response", {})
            mcp = response.get("response", {}).get("mcp_response")
            if mcp:
                results.append(mcp)
        return results


def make_channel(answer=None):
    recorder = Recorder()
    channel = ControlChannel(recorder)
    channel.set_permission_callback(lambda ask: answer or PermissionAnswer(behavior="allow"))
    return channel, recorder


def request(payload):
    return {"type": "control_request", "request_id": "r1", "request": payload}


def test_initialize_handshake():
    channel, recorder = make_channel()
    channel.handle(request({"subtype": "mcp_message", "server_name": PERMISSION_SERVER_NAME,
                            "message": {"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                        "params": {"protocolVersion": "2025-11-25"}}}))
    results = recorder.mcp_results()
    assert results, "expected an MCP response"
    result = results[0]["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert result["serverInfo"]["name"] == PERMISSION_SERVER_NAME
    assert channel.connected_server


def test_notification_is_acked_with_empty_result():
    channel, recorder = make_channel()
    channel.handle(request({"subtype": "mcp_message", "server_name": PERMISSION_SERVER_NAME,
                            "message": {"jsonrpc": "2.0", "method": "notifications/initialized"}}))
    results = recorder.mcp_results()
    assert results and results[0]["result"] == {}
    assert results[0]["id"] is None


def test_tools_list_exposes_permission_tool():
    channel, recorder = make_channel()
    channel.handle(request({"subtype": "mcp_message", "server_name": PERMISSION_SERVER_NAME,
                            "message": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}}))
    tools = recorder.mcp_results()[0]["result"]["tools"]
    assert tools[0]["name"] == PERMISSION_TOOL
    assert "inputSchema" in tools[0]


def test_tools_call_allow_roundtrip():
    payload = {"behavior": None}

    def callback(ask: PermissionAsk) -> PermissionAnswer:
        payload["behavior"] = ask.tool_name
        return PermissionAnswer(behavior="allow", updated_input=ask.tool_input)

    channel, recorder = make_channel()
    channel.set_permission_callback(callback)
    channel.handle(request({
        "subtype": "mcp_message", "server_name": PERMISSION_SERVER_NAME,
        "message": {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": PERMISSION_TOOL,
                               "arguments": {"tool_name": "Write",
                                             "input": {"file_path": "/x/y.py", "content": "a"},
                                             "tool_use_id": "toolu_9"}}}}))
    assert payload["behavior"] == "Write"
    results = recorder.mcp_results()
    content = results[0]["result"]["content"][0]["text"]
    decision = json.loads(content)
    assert decision["behavior"] == "allow"
    assert decision["updatedInput"]["file_path"] == "/x/y.py"
    assert channel.stats()["allowed"] == 1


def test_tools_call_deny_message():
    channel, recorder = make_channel(PermissionAnswer(behavior="deny", message="Not today"))
    channel.handle(request({
        "subtype": "mcp_message", "server_name": PERMISSION_SERVER_NAME,
        "message": {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": PERMISSION_TOOL,
                               "arguments": {"tool_name": "Bash", "input": {"command": "rm -rf /"}}}}}))
    decision = json.loads(recorder.mcp_results()[0]["result"]["content"][0]["text"])
    assert decision["behavior"] == "deny"
    assert decision["message"] == "Not today"
    assert channel.stats()["denied"] == 1


def test_direct_control_permission_request():
    channel, recorder = make_channel(PermissionAnswer(behavior="allow"))
    channel.handle(request({"subtype": "can_use_tool", "tool_name": "Bash",
                            "input": {"command": "ls"}, "tool_use_id": "t1"}))
    responses = [r for r in recorder.out if r.get("type") == "control_response"]
    body = responses[0]["response"]["response"]
    assert body["behavior"] == "allow"


def test_interrupt_and_set_mode():
    channel, recorder = make_channel()
    channel.interrupt()
    channel.set_permission_mode("plan")
    kinds = [r["request"]["subtype"] for r in recorder.out if r.get("type") == "control_request"]
    assert kinds == ["interrupt", "set_permission_mode"]


def test_unknown_server_is_rejected():
    channel, recorder = make_channel()
    channel.handle(request({"subtype": "mcp_message", "server_name": "other",
                            "message": {"jsonrpc": "2.0", "id": 5, "method": "ping"}}))
    responses = [r for r in recorder.out if r.get("type") == "control_response"]
    assert responses[0]["response"]["subtype"] == "error"
