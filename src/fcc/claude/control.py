"""The control channel: permission prompts, interrupts and SDK-hosted MCP tools.

Claude Code answers permission questions through a JSON-RPC conversation that
runs inside its control stream. The app hosts a tiny in-process MCP server
(`fcc_studio`) exposing one tool, `can_use_tool`; the CLI calls it whenever an
action needs approval, which is how the GUI can show Allow / Deny buttons
instead of a terminal prompt.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from fcc.claude import protocol
from fcc.claude.capabilities import PERMISSION_SERVER_NAME
from fcc.logging_setup import get_logger

log = get_logger("cli.control")

PERMISSION_TOOL = "can_use_tool"
MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_FALLBACK_VERSION = "2024-11-05"

PERMISSION_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string", "description": "Name of the tool Claude wants to use."},
        "input": {"type": "object", "description": "Input the tool would be called with."},
        "tool_use_id": {"type": "string"},
        "blocked_path": {"type": "string"},
        "permission_suggestions": {"type": "array"},
    },
    "required": ["tool_name", "input"],
}


@dataclass
class PermissionAsk:
    id: str
    tool_name: str
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_use_id: str = ""
    subject: str = ""
    blocked_path: str = ""
    suggestions: List[Any] = field(default_factory=list)
    decision_reason: str = ""
    title: str = ""
    display_name: str = ""
    description: str = ""
    mcp_server: Dict[str, Any] = field(default_factory=dict)
    source: str = "mcp"  # mcp | control
    asked_at: float = field(default_factory=time.time)


@dataclass
class PermissionAnswer:
    behavior: str = "allow"  # allow | deny
    updated_input: Optional[Dict[str, Any]] = None
    message: str = ""
    remember: str = ""  # "" | session | project | global
    remember_behavior: str = "allow"
    answered_at: float = field(default_factory=time.time)
    timed_out: bool = False


AskCallback = Callable[[PermissionAsk], PermissionAnswer]


class ControlChannel:
    """Serialises control traffic to/from the CLI process."""

    def __init__(self, writer: Callable[[Dict[str, Any]], None],
                 ask_permission: Optional[AskCallback] = None,
                 on_event: Optional[Callable[[protocol.UiEvent], None]] = None,
                 permission_timeout: float = 0.0) -> None:
        self._writer = writer
        self._ask = ask_permission
        self._on_event = on_event
        self.permission_timeout = permission_timeout
        self._lock = threading.RLock()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._in_flight_asks: Dict[str, PermissionAsk] = {}
        self.server_name = PERMISSION_SERVER_NAME
        self.connected_server = False
        self.ask_count = 0
        self.allow_count = 0
        self.deny_count = 0

    # ------------------------------------------------------------------ #
    def set_permission_callback(self, callback: Optional[AskCallback]) -> None:
        self._ask = callback

    def _emit(self, event: protocol.UiEvent) -> None:
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as exc:  # pragma: no cover
                log.warning("on_event failed: %s", exc)

    # ---- outbound ----------------------------------------------------- #
    def send_request(self, subtype: str, **fields: Any) -> str:
        request_id = f"fcc_{uuid.uuid4().hex[:10]}"
        request = {"subtype": subtype}
        request.update({k: v for k, v in fields.items() if v is not None})
        with self._lock:
            self._pending[request_id] = {"subtype": subtype, "sent_at": time.time()}
        self._writer({"type": "control_request", "request_id": request_id, "request": request})
        log.debug("control -> %s (%s)", subtype, request_id)
        return request_id

    def send_response(self, request_id: str, response: Any) -> None:
        self._writer({
            "type": "control_response",
            "response": {"subtype": "success", "request_id": request_id, "response": response or {}},
        })

    def send_error(self, request_id: str, message: str) -> None:
        self._writer({
            "type": "control_response",
            "response": {"subtype": "error", "request_id": request_id, "error": message},
        })

    def interrupt(self) -> str:
        return self.send_request("interrupt")

    def end_session(self) -> str:
        return self.send_request("end_session")

    def set_permission_mode(self, mode: str) -> str:
        return self.send_request("set_permission_mode", mode=mode)

    def set_model(self, model: str) -> str:
        return self.send_request("set_model", model=model)

    def cancel_pending_asks(self, reason: str = "cancelled") -> None:
        with self._lock:
            asks = list(self._in_flight_asks.items())
            self._in_flight_asks.clear()
        for ask_id, _ in asks:
            log.info("Cancelling permission ask %s: %s", ask_id, reason)

    # ---- inbound ------------------------------------------------------ #
    def handle(self, event: Dict[str, Any]) -> List[protocol.UiEvent]:
        kind = event.get("type")
        if kind == "control_request":
            return self._handle_request(event)
        if kind == "control_response":
            return self._handle_response(event)
        if kind == "control_error":
            log.warning("control_error: %s", event.get("error"))
            return [protocol.UiEvent(protocol.NOTICE, {"notice": "control_error",
                                                       "title": "Control channel error",
                                                       "message": str(event.get("error") or "")}, event)]
        if kind == "control_cancel_request":
            request_id = event.get("request_id")
            with self._lock:
                self._pending.pop(request_id, None)
            return []
        return []

    def _handle_response(self, event: Dict[str, Any]) -> List[protocol.UiEvent]:
        response = event.get("response") or {}
        request_id = response.get("request_id") or event.get("request_id")
        with self._lock:
            pending = self._pending.pop(request_id, None)
        if response.get("subtype") == "error":
            log.warning("control request %s failed: %s", request_id, response.get("error"))
            return [protocol.UiEvent(protocol.NOTICE, {
                "notice": "control_error",
                "title": f"{(pending or {}).get('subtype', 'control')} failed",
                "message": str(response.get("error") or ""),
            }, event)]
        log.debug("control <- response for %s (%s)", request_id, (pending or {}).get("subtype"))
        return []

    def _handle_request(self, event: Dict[str, Any]) -> List[protocol.UiEvent]:
        request = event.get("request") or {}
        subtype = request.get("subtype")
        request_id = event.get("request_id") or ""
        log.debug("control <- request %s (%s)", subtype, request_id)

        if subtype == "mcp_message":
            self._handle_mcp(request_id, request)
            return []
        if subtype == "can_use_tool":
            self._handle_direct_permission(request_id, request)
            return []
        if subtype == "control_cancel_request":
            return []
        if subtype in ("hook_callback", "elicitation", "request_user_dialog", "get_server_instructions"):
            # Nothing in the GUI needs these yet; acknowledge politely.
            self.send_response(request_id, {})
            return [protocol.UiEvent(protocol.NOTICE, {
                "notice": subtype, "title": subtype, "message": json.dumps(request)[:240]}, event)]
        self.send_error(request_id, f"unsupported control request: {subtype}")
        return [protocol.UiEvent(protocol.NOTICE, {
            "notice": "unsupported_control", "title": f"Unsupported control request: {subtype}",
            "message": "The app acknowledged it with an error so Claude Code can continue."}, event)]

    # ---- MCP (permission server) -------------------------------------- #
    def _handle_mcp(self, request_id: str, request: Dict[str, Any]) -> None:
        message = request.get("message") or {}
        server = request.get("server_name") or self.server_name
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if server != self.server_name:
            self.send_error(request_id, f"unknown sdk mcp server: {server}")
            return

        if method == "initialize":
            version = params.get("protocolVersion") or MCP_PROTOCOL_VERSION
            self.connected_server = True
            self._mcp_reply(request_id, msg_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.server_name, "title": "Claude Code Studio",
                               "version": "1.0.0"},
                "instructions": "Hosts the permission prompt tool for the desktop GUI.",
            })
            return

        if method is None or str(method).startswith("notifications/"):
            # Notifications still need an acknowledgement frame with an empty result.
            self._mcp_reply(request_id, msg_id if msg_id is not None else None, {})
            return

        if method == "ping":
            self._mcp_reply(request_id, msg_id, {})
            return

        if method == "tools/list":
            self._mcp_reply(request_id, msg_id, {"tools": [{
                "name": PERMISSION_TOOL,
                "title": "Ask the user for permission",
                "description": "Shows a permission prompt in the Claude Code Studio GUI and "
                               "returns {behavior: allow|deny}.",
                "inputSchema": PERMISSION_TOOL_SCHEMA,
            }]})
            return

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            if tool_name != PERMISSION_TOOL:
                self._mcp_error(request_id, msg_id, -32601, f"unknown tool: {tool_name}")
                return
            decision = self.ask_permission(arguments, source="mcp")
            payload = {"behavior": decision.behavior,
                       "updatedInput": decision.updated_input if decision.behavior == "allow" else None}
            if decision.behavior == "deny":
                payload = {"behavior": "deny",
                           "message": decision.message or "The user denied this action."}
            else:
                payload = {k: v for k, v in payload.items() if v is not None}
            self._mcp_reply(request_id, msg_id, {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "isError": False,
            })
            return

        if method == "tools/list_changed":
            self._mcp_reply(request_id, msg_id, {})
            return

        self._mcp_error(request_id, msg_id, -32601, f"method not found: {method}")

    def _mcp_reply(self, request_id: str, msg_id: Any, result: Dict[str, Any]) -> None:
        reply: Dict[str, Any] = {"jsonrpc": "2.0", "result": result}
        if msg_id is not None:
            reply["id"] = msg_id
        else:
            reply["id"] = None
        self.send_response(request_id, {"mcp_response": reply})

    def _mcp_error(self, request_id: str, msg_id: Any, code: int, message: str) -> None:
        self.send_response(request_id, {"mcp_response": {
            "jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}})

    # ---- permission asking -------------------------------------------- #
    def _handle_direct_permission(self, request_id: str, request: Dict[str, Any]) -> None:
        decision = self.ask_permission(request, source="control")
        if decision.behavior == "allow":
            response: Dict[str, Any] = {"behavior": "allow"}
            if decision.updated_input is not None:
                response["updatedInput"] = decision.updated_input
        else:
            response = {"behavior": "deny", "message": decision.message or "Denied by the user."}
        self.send_response(request_id, response)

    def ask_permission(self, request: Dict[str, Any], source: str = "mcp") -> PermissionAnswer:
        """Blocking: shows the prompt in the UI and waits for the user."""
        from fcc.claude.toolmeta import subject_for, title_for

        tool_name = str(request.get("tool_name") or "")
        tool_input = request.get("input") if isinstance(request.get("input"), dict) else {}
        ask = PermissionAsk(
            id=uuid.uuid4().hex[:10],
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=str(request.get("tool_use_id") or ""),
            subject=subject_for(tool_name, tool_input),
            blocked_path=str(request.get("blocked_path") or ""),
            suggestions=list(request.get("permission_suggestions") or []),
            decision_reason=str(request.get("decision_reason") or ""),
            title=str(request.get("title") or title_for(tool_name, tool_input)),
            display_name=str(request.get("display_name") or ""),
            description=str(request.get("description") or ""),
            mcp_server=request.get("mcp_server") or {},
            source=source,
        )
        with self._lock:
            self._in_flight_asks[ask.id] = ask
            self.ask_count += 1

        self._emit(protocol.UiEvent(protocol.NOTICE, {
            "notice": "permission_ask", "ask_id": ask.id, "tool_name": tool_name,
            "subject": ask.subject, "message": ask.title}, None))

        answer = PermissionAnswer(behavior="deny", message="No permission handler is available.", timed_out=True)
        if self._ask is not None:
            try:
                answer = self._ask(ask) or answer
            except Exception as exc:  # pragma: no cover
                log.exception("permission callback failed: %s", exc)
                answer = PermissionAnswer(behavior="deny", message=f"Permission handler error: {exc}")
        with self._lock:
            self._in_flight_asks.pop(ask.id, None)
            if answer.behavior == "allow":
                self.allow_count += 1
            else:
                self.deny_count += 1
        if answer.behavior == "allow" and answer.updated_input is None:
            answer.updated_input = tool_input
        log.info("permission %s -> %s (%s)", tool_name, answer.behavior, answer.remember or "once")
        return answer

    # ---- stats --------------------------------------------------------- #
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "server_connected": self.connected_server,
                "asks": self.ask_count,
                "allowed": self.allow_count,
                "denied": self.deny_count,
                "in_flight": list(self._in_flight_asks.keys()),
                "pending_requests": list(self._pending.keys()),
            }
