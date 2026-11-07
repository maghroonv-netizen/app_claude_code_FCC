"""Turns Claude Code's stream-json output into small UI-friendly events.

Verified against Claude Code 2.1.x: `system/init`, `system/status`,
`stream_event` partials, `assistant`, `user` (tool results), `result`,
`system/permission_denied`, `control_request`/`control_response`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# event kinds --------------------------------------------------------------- #
SESSION_INIT = "session_init"
STATUS = "status"
TEXT_DELTA = "text_delta"
THINKING_DELTA = "thinking_delta"
MESSAGE_FINAL = "message_final"
MESSAGE_END = "message_end"
TOOL_START = "tool_start"
TOOL_INPUT_DELTA = "tool_input_delta"
TOOL_RESULT = "tool_result"
PERMISSION_DENIED = "permission_denied"
TODOS = "todos"
PLAN = "plan"
TURN_DONE = "turn_done"
ERROR = "error"
NOTICE = "notice"
SUGGESTION = "suggestion"
USER_ECHO = "user_echo"
CONTROL = "control"
RAW = "raw"

ALL_KINDS = [
    SESSION_INIT, STATUS, TEXT_DELTA, THINKING_DELTA, MESSAGE_FINAL, MESSAGE_END,
    TOOL_START, TOOL_INPUT_DELTA, TOOL_RESULT, PERMISSION_DENIED, TODOS, PLAN,
    TURN_DONE, ERROR, NOTICE, SUGGESTION, USER_ECHO, CONTROL, RAW,
]

AUTH_ERROR_CODES = {
    "authentication_failed": "auth",
    "invalid_api_key": "auth",
    "unauthorized": "auth",
}


@dataclass
class UiEvent:
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None
    ts: float = field(default_factory=time.time)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


def parse_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


class StreamInterpreter:
    """Stateful normaliser: feed raw dicts, get a list of :class:`UiEvent`."""

    def __init__(self) -> None:
        self.session_id: str = ""
        self.cwd: str = ""
        self.model: str = ""
        self.cli_version: str = ""
        self.permission_mode: str = ""
        self.api_key_source: str = ""
        self.tools: List[str] = []
        self.slash_commands: List[str] = []
        self.capabilities: List[str] = []
        self._message_text: Dict[str, str] = {}
        self._message_thinking: Dict[str, str] = {}
        self._tool_inputs: Dict[str, str] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._block_tools: Dict[str, str] = {}
        self.turn_count = 0

    # ------------------------------------------------------------------ #
    def feed(self, event: Dict[str, Any]) -> List[UiEvent]:
        if not isinstance(event, dict):
            return []
        kind = event.get("type")
        handler = {
            "system": self._system,
            "stream_event": self._stream_event,
            "assistant": self._assistant,
            "user": self._user,
            "result": self._result,
            "control_request": self._control,
            "control_response": self._control,
            "control_error": self._control,
            "prompt_suggestion": self._suggestion,
        }.get(kind)
        if handler is None:
            return [UiEvent(RAW, {"raw_type": kind}, event)]
        try:
            return handler(event) or []
        except Exception as exc:  # never let one odd frame kill the session
            return [UiEvent(ERROR, {"code": "parse", "message": f"{type(exc).__name__}: {exc}"}, event)]

    def feed_many(self, events: List[Dict[str, Any]]) -> List[UiEvent]:
        out: List[UiEvent] = []
        for event in events:
            out.extend(self.feed(event))
        return out

    # ------------------------------------------------------------------ #
    def _system(self, event: Dict[str, Any]) -> List[UiEvent]:
        subtype = event.get("subtype", "")
        if subtype == "init":
            self.session_id = str(event.get("session_id") or self.session_id)
            self.cwd = str(event.get("cwd") or self.cwd)
            self.model = str(event.get("model") or self.model)
            self.cli_version = str(event.get("claude_code_version") or "")
            self.permission_mode = str(event.get("permissionMode") or "")
            self.api_key_source = str(event.get("apiKeySource") or "")
            self.tools = list(event.get("tools") or [])
            self.slash_commands = list(event.get("slash_commands") or [])
            self.capabilities = list(event.get("capabilities") or [])
            return [UiEvent(SESSION_INIT, {
                "session_id": self.session_id,
                "cwd": self.cwd,
                "model": self.model,
                "cli_version": self.cli_version,
                "permission_mode": self.permission_mode,
                "api_key_source": self.api_key_source,
                "tools": self.tools,
                "mcp_servers": list(event.get("mcp_servers") or []),
                "slash_commands": self.slash_commands,
                "agents": list(event.get("agents") or []),
                "skills": list(event.get("skills") or []),
                "capabilities": self.capabilities,
                "output_style": event.get("output_style", ""),
            }, event)]
        if subtype == "status":
            return [UiEvent(STATUS, {"status": event.get("status", ""), "detail": event.get("detail", "")}, event)]
        if subtype == "permission_denied":
            return [UiEvent(PERMISSION_DENIED, {
                "tool_name": event.get("tool_name", ""),
                "tool_use_id": event.get("tool_use_id", ""),
                "message": event.get("message", ""),
            }, event)]
        if subtype == "compact_boundary":
            meta = event.get("compact_metadata") or {}
            return [UiEvent(NOTICE, {
                "notice": "compact",
                "title": "Conversation compacted",
                "message": f"Context reduced to {meta.get('post_tokens', '?')} tokens "
                           f"from {meta.get('pre_tokens', '?')}.",
            }, event)]
        if subtype in ("informational", "notification"):
            return [UiEvent(NOTICE, {
                "notice": subtype,
                "title": event.get("key") or subtype,
                "message": str(event.get("text") or event.get("content") or ""),
                "level": event.get("level") or event.get("color") or "info",
            }, event)]
        return [UiEvent(NOTICE, {"notice": subtype or "system", "title": subtype or "system",
                                 "message": json.dumps({k: v for k, v in event.items() if k != "type"})[:400]}, event)]

    def _stream_event(self, event: Dict[str, Any]) -> List[UiEvent]:
        inner = event.get("event") or {}
        inner_type = inner.get("type")
        message_id = str(event.get("api_message_id") or inner.get("message", {}).get("id") or "")
        parent = event.get("parent_tool_use_id")
        out: List[UiEvent] = []

        if inner_type == "message_start":
            message = inner.get("message") or {}
            message_id = str(message.get("id") or message_id)
            self._message_text[message_id] = ""
            self._message_thinking[message_id] = ""
            usage = message.get("usage") or {}
            out.append(UiEvent(MESSAGE_END, {"message_id": message_id, "phase": "start",
                                             "model": message.get("model", ""),
                                             "ttft_ms": event.get("ttft_ms"),
                                             "usage": usage, "parent_tool_use_id": parent}, event))
        elif inner_type == "content_block_start":
            block = inner.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_id = str(block.get("id") or "")
                self._tool_inputs[tool_id] = ""
                self._tools[tool_id] = {"name": block.get("name", ""), "input": {}}
                self._block_tools[f"{message_id}:{inner.get('index', 0)}"] = tool_id
                out.append(UiEvent(TOOL_START, {
                    "tool_use_id": tool_id,
                    "name": block.get("name", ""),
                    "input": {},
                    "partial": True,
                    "parent_tool_use_id": parent,
                    "message_id": message_id,
                }, event))
        elif inner_type == "content_block_delta":
            delta = inner.get("delta") or {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                text = delta.get("text") or ""
                self._message_text[message_id] = self._message_text.get(message_id, "") + text
                out.append(UiEvent(TEXT_DELTA, {"message_id": message_id, "text": text,
                                                "parent_tool_use_id": parent}, event))
            elif delta_type in ("thinking_delta", "signature_delta"):
                text = delta.get("thinking") or delta.get("signature") or ""
                if delta_type == "thinking_delta":
                    self._message_thinking[message_id] = self._message_thinking.get(message_id, "") + text
                    out.append(UiEvent(THINKING_DELTA, {"message_id": message_id, "text": text,
                                                        "parent_tool_use_id": parent}, event))
            elif delta_type == "input_json_delta":
                partial = delta.get("partial_json") or ""
                index = inner.get("index", 0)
                tool_id = self._current_tool_id(message_id, index)
                if tool_id:
                    self._tool_inputs[tool_id] = self._tool_inputs.get(tool_id, "") + partial
                    out.append(UiEvent(TOOL_INPUT_DELTA, {"tool_use_id": tool_id, "partial_json": partial,
                                                          "parent_tool_use_id": parent}, event))
        elif inner_type == "message_delta":
            usage = inner.get("usage") or {}
            out.append(UiEvent(MESSAGE_END, {"message_id": message_id, "phase": "delta",
                                             "stop_reason": (inner.get("delta") or {}).get("stop_reason"),
                                             "usage": usage, "parent_tool_use_id": parent}, event))
        elif inner_type == "message_stop":
            out.append(UiEvent(MESSAGE_END, {"message_id": message_id, "phase": "stop",
                                             "text": self._message_text.get(message_id, ""),
                                             "thinking": self._message_thinking.get(message_id, ""),
                                             "parent_tool_use_id": parent}, event))
        return out

    def _current_tool_id(self, message_id: str, index: int) -> str:
        """Map a streaming content block back to the tool_use id it belongs to."""
        key = f"{message_id}:{index}"
        if key in self._block_tools:
            return self._block_tools[key]
        for candidate in (f":{index}", key):
            if candidate in self._block_tools:
                return self._block_tools[candidate]
        if len(self._tool_inputs) == 1:
            return next(iter(self._tool_inputs))
        return ""

    def _assistant(self, event: Dict[str, Any]) -> List[UiEvent]:
        message = event.get("message") or {}
        message_id = str(message.get("id") or event.get("uuid") or "")
        parent = event.get("parent_tool_use_id")
        out: List[UiEvent] = []
        blocks = message.get("content")
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        text_parts: List[str] = []
        thinking_parts: List[str] = []
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(str(block.get("text") or ""))
            elif block_type == "thinking":
                thinking_parts.append(str(block.get("thinking") or block.get("text") or ""))
            elif block_type == "tool_use":
                tool_id = str(block.get("id") or "")
                tool_input = block.get("input") or {}
                self._tools[tool_id] = {"name": block.get("name", ""), "input": tool_input}
                out.append(UiEvent(TOOL_START, {
                    "tool_use_id": tool_id,
                    "name": block.get("name", ""),
                    "input": tool_input,
                    "partial": False,
                    "parent_tool_use_id": parent,
                    "message_id": message_id,
                }, event))
                if str(block.get("name", "")).lower() == "todowrite":
                    out.append(UiEvent(TODOS, {"items": list((tool_input or {}).get("todos") or []),
                                               "tool_use_id": tool_id}, event))
                if str(block.get("name", "")).lower() == "exitplanmode":
                    out.append(UiEvent(PLAN, {"plan": str((tool_input or {}).get("plan") or ""),
                                              "tool_use_id": tool_id}, event))

        full_text = "\n".join(part for part in text_parts if part)
        if full_text:
            out.append(UiEvent(MESSAGE_FINAL, {
                "message_id": message_id,
                "text": full_text,
                "thinking": "\n".join(part for part in thinking_parts if part),
                "model": message.get("model", ""),
                "usage": message.get("usage") or {},
                "parent_tool_use_id": parent,
                "uuid": event.get("uuid", ""),
                "timestamp": event.get("timestamp", ""),
                "is_error": bool(event.get("is_api_error_message")),
                "error_code": str(event.get("error") or ""),
            }, event))
        elif thinking_parts:
            out.append(UiEvent(MESSAGE_FINAL, {"message_id": message_id, "text": "",
                                               "thinking": "\n".join(thinking_parts),
                                               "parent_tool_use_id": parent}, event))
        if event.get("is_api_error_message"):
            code = str(event.get("error") or "")
            out.append(UiEvent(ERROR, {
                "code": AUTH_ERROR_CODES.get(code, code or "api_error"),
                "message": full_text or "Claude Code reported an API error.",
                "recoverable": code not in AUTH_ERROR_CODES,
            }, event))
        return out

    def _user(self, event: Dict[str, Any]) -> List[UiEvent]:
        message = event.get("message") or {}
        content = message.get("content")
        parent = event.get("parent_tool_use_id")
        structured = event.get("tool_use_result")
        meta = event.get("tool_result_meta") or []
        meta_by_id = {}
        if isinstance(meta, list):
            for item in meta:
                if isinstance(item, dict) and item.get("id"):
                    meta_by_id[item["id"]] = item
        out: List[UiEvent] = []

        if isinstance(content, str):
            if event.get("is_meta") or event.get("isCompactSummary"):
                return [UiEvent(NOTICE, {"notice": "summary", "title": "Context summary", "message": content[:500]}, event)]
            return [UiEvent(USER_ECHO, {"text": content}, event)]
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                tool_id = str(block.get("tool_use_id") or "")
                info = self._tools.get(tool_id, {})
                item_meta = meta_by_id.get(tool_id) or {}
                decision = (item_meta.get("permission_decision") or {}) if isinstance(item_meta, dict) else {}
                out.append(UiEvent(TOOL_RESULT, {
                    "tool_use_id": tool_id,
                    "name": info.get("name", ""),
                    "input": info.get("input", {}),
                    "content": block.get("content"),
                    "is_error": bool(block.get("is_error")),
                    "structured": structured,
                    "meta": item_meta,
                    "permission_decision": decision.get("decision", ""),
                    "permission_source": decision.get("source", ""),
                    "permission_reason": decision.get("reason_type", ""),
                    "non_execution_kind": item_meta.get("non_execution_kind", "") if isinstance(item_meta, dict) else "",
                    "parent_tool_use_id": parent,
                }, event))
            elif block.get("type") == "text":
                out.append(UiEvent(USER_ECHO, {"text": str(block.get("text") or "")}, event))
        return out

    def _result(self, event: Dict[str, Any]) -> List[UiEvent]:
        self.turn_count += 1
        usage = event.get("usage") or {}
        model_usage = event.get("modelUsage") or {}
        context_window = 0
        for entry in model_usage.values() if isinstance(model_usage, dict) else []:
            if isinstance(entry, dict) and entry.get("contextWindow"):
                context_window = int(entry["contextWindow"])
                break
        payload = {
            "subtype": event.get("subtype", ""),
            "is_error": bool(event.get("is_error")),
            "result_text": str(event.get("result") or ""),
            "duration_ms": int(event.get("duration_ms") or 0),
            "duration_api_ms": int(event.get("duration_api_ms") or 0),
            "num_turns": int(event.get("num_turns") or 0),
            "total_cost_usd": float(event.get("total_cost_usd") or 0.0),
            "usage": usage,
            "model_usage": model_usage,
            "context_window": context_window,
            "permission_denials": event.get("permission_denials") or [],
            "terminal_reason": event.get("terminal_reason", ""),
            "session_id": event.get("session_id") or self.session_id,
            "error_code": str(event.get("api_error_status") or ""),
        }
        out = [UiEvent(TURN_DONE, payload, event)]
        text = payload["result_text"]
        if payload["is_error"] and text:
            lowered = text.lower()
            code = "auth" if ("not logged in" in lowered or "invalid api key" in lowered or "unauthorized" in lowered) else "api_error"
            out.append(UiEvent(ERROR, {"code": code, "message": text, "recoverable": code != "auth"}, event))
        return out

    def _control(self, event: Dict[str, Any]) -> List[UiEvent]:
        request = event.get("request") or {}
        response = event.get("response") or {}
        return [UiEvent(CONTROL, {
            "direction": "in" if event.get("type") == "control_request" else "out",
            "subtype": request.get("subtype") or response.get("subtype") or "",
            "request_id": event.get("request_id") or response.get("request_id") or "",
            "error": event.get("error") or response.get("error") or "",
        }, event)]

    def _suggestion(self, event: Dict[str, Any]) -> List[UiEvent]:
        return [UiEvent(SUGGESTION, {"suggestion": event.get("suggestion") or event.get("prompt") or ""}, event)]


def summarize_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compact numbers for the status bar / session header."""
    usage = payload.get("usage") or {}
    tokens_in = int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0) \
        + int(usage.get("cache_creation_input_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or 0)
    cost = float(payload.get("total_cost_usd") or 0.0)
    duration = int(payload.get("duration_ms") or 0)
    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost,
        "duration_ms": duration,
        "num_turns": int(payload.get("num_turns") or 0),
        "context_window": int(payload.get("context_window") or 0),
    }


def format_duration(ms: int) -> str:
    if ms <= 0:
        return "-"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    return f"{minutes}m {int(seconds % 60)}s"


def format_cost(cost: float) -> str:
    if not cost:
        return "$0.00"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f}M"
    if count >= 1_000:
        return f"{count / 1000:.1f}k"
    return str(count)
