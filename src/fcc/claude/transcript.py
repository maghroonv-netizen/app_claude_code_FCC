"""Read and export the JSONL transcripts the app records for each session."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fcc.claude import protocol


def read_raw(path: Path, limit: int = 20000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def replay(path: Path) -> List[protocol.UiEvent]:
    """Rebuild UI events from a stored transcript (used to reopen a session)."""
    interpreter = protocol.StreamInterpreter()
    events: List[protocol.UiEvent] = []
    for record in read_raw(path):
        direction = record.get("direction")
        if direction == "in":
            raw = protocol.parse_line(record.get("line", ""))
            if raw is None:
                continue
            events.extend(interpreter.feed(raw))
        elif direction == "out":
            payload = record.get("payload") or {}
            if payload.get("type") == "user":
                message = payload.get("message") or {}
                content = message.get("content")
                text_parts = []
                attachments = []
                if isinstance(content, str):
                    text_parts.append(content)
                else:
                    for block in content or []:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            text_parts.append(str(block.get("text") or ""))
                        elif block.get("type") == "image":
                            attachments.append({"type": "image", "name": "image"})
                text = "\n".join(part for part in text_parts if part).strip()
                if text or attachments:
                    events.append(protocol.UiEvent(protocol.USER_ECHO, {"text": text}))
    return events


def to_markdown(path: Path, title: str = "", project: str = "") -> str:
    lines: List[str] = []
    lines.append(f"# {title or 'Claude Code session'}")
    if project:
        lines.append(f"\n_Project: `{project}`_")
    lines.append(f"\n_Exported {time.strftime('%Y-%m-%d %H:%M')}_\n")
    from fcc.claude import toolmeta

    for event in replay(path):
        kind = event.kind
        payload = event.payload
        if kind == protocol.USER_ECHO:
            text = str(payload.get("text", "")).strip()
            if text:
                lines.append(f"\n## You\n\n{text}\n")
        elif kind == protocol.MESSAGE_FINAL:
            text = str(payload.get("text", "")).strip()
            if text:
                lines.append(f"\n## Claude\n\n{text}\n")
        elif kind == protocol.TOOL_START and not payload.get("partial"):
            name = payload.get("name", "tool")
            lines.append(f"\n> 🔧 **{name}** — {toolmeta.title_for(name, payload.get('input') or {})}")
        elif kind == protocol.TOOL_RESULT:
            detail = toolmeta.describe_output(
                payload.get("name", ""), payload.get("input") or {},
                payload.get("content"), payload.get("structured"))
            if detail.body:
                fence = "```" + (detail.language or "")
                body = detail.body if len(detail.body) < 4000 else detail.body[:4000] + "\n…"
                lines.append(f"> {fence}\n> " + body.replace("\n", "\n> ") + f"\n> ```")
        elif kind == protocol.TURN_DONE:
            summary = protocol.summarize_result(payload)
            lines.append(
                f"\n---\n\n_Turn: {summary['num_turns']} steps · "
                f"{protocol.format_duration(summary['duration_ms'])} · "
                f"{protocol.format_cost(summary['cost_usd'])} · "
                f"{protocol.format_tokens(summary['tokens_in'])} in / "
                f"{protocol.format_tokens(summary['tokens_out'])} out_\n")
    return "\n".join(lines)


def to_json(path: Path) -> List[Dict[str, Any]]:
    return read_raw(path)
