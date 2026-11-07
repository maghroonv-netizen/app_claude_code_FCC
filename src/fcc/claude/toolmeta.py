"""Human-friendly rendering metadata for every Claude Code tool call."""

from __future__ import annotations

import difflib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_BODY = 24000
MAX_LINE = 2000


@dataclass
class DiffLine:
    kind: str  # add | del | ctx | hunk
    text: str
    old_no: Optional[int] = None
    new_no: Optional[int] = None


@dataclass
class ToolDetail:
    kind: str = "text"  # text | code | diff | todos | files | kv | json | image | none
    title: str = ""
    body: str = ""
    language: str = ""
    rows: List[Tuple[str, str]] = field(default_factory=list)
    diff: List[DiffLine] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.body or self.rows or self.diff or self.items)


CATEGORY_META: Dict[str, Dict[str, str]] = {
    "read": {"icon": "file_text", "accent": "info", "label": "Read"},
    "write": {"icon": "pencil", "accent": "accent", "label": "Write"},
    "edit": {"icon": "diff", "accent": "accent", "label": "Edit"},
    "shell": {"icon": "terminal", "accent": "warn", "label": "Shell"},
    "search": {"icon": "search", "accent": "info", "label": "Search"},
    "web": {"icon": "globe", "accent": "info", "label": "Web"},
    "agent": {"icon": "agent", "accent": "success", "label": "Agent"},
    "plan": {"icon": "list", "accent": "success", "label": "Plan"},
    "think": {"icon": "brain", "accent": "muted", "label": "Thinking"},
    "other": {"icon": "wrench", "accent": "muted", "label": "Tool"},
}

TOOL_CATEGORY: Dict[str, str] = {
    "bash": "shell", "shell": "shell", "powershell": "shell", "bashoutput": "shell",
    "killshell": "shell", "killbash": "shell",
    "read": "read", "view": "read", "fileread": "read", "listmcpresources": "read",
    "readmcpresource": "read", "readmcpresourcedir": "read", "notebookread": "read",
    "write": "write", "filewrite": "write", "create": "write",
    "edit": "edit", "fileedit": "edit", "multiedit": "edit", "notebookedit": "edit",
    "glob": "search", "grep": "search", "search": "search", "toolsearch": "search",
    "ls": "search", "listdir": "search",
    "webfetch": "web", "websearch": "web",
    "task": "agent", "agent": "agent", "sendmessage": "agent", "listagents": "agent",
    "taskcreate": "agent", "taskupdate": "agent", "taskget": "agent", "tasklist": "agent",
    "taskstop": "agent",
    "todowrite": "plan", "todoread": "plan", "exitplanmode": "plan", "enterplanmode": "plan",
    "reportfindings": "plan", "workflow": "plan", "skill": "think",
}

_CODE_LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript", ".tsx": "tsx",
    ".json": "json", ".md": "markdown", ".html": "html", ".css": "css", ".scss": "scss",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".sh": "bash", ".bash": "bash", ".ps1": "powershell", ".bat": "bat", ".sql": "sql",
    ".rs": "rust", ".go": "go", ".java": "java", ".kt": "kotlin", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".lua": "lua", ".r": "r", ".dart": "dart", ".vue": "html",
    ".xml": "xml", ".svg": "xml", ".txt": "text", ".env": "bash", ".dockerfile": "docker",
}


def category(tool_name: str) -> str:
    name = (tool_name or "").strip()
    key = name.lower()
    if key in TOOL_CATEGORY:
        return TOOL_CATEGORY[key]
    if key.startswith("mcp__"):
        return "other"
    return "other"


def meta(tool_name: str) -> Dict[str, str]:
    return CATEGORY_META.get(category(tool_name), CATEGORY_META["other"])


def icon_name(tool_name: str) -> str:
    from fcc.icons import tool_icon_name

    return tool_icon_name(tool_name)


def accent_key(tool_name: str) -> str:
    return meta(tool_name)["accent"]


def language_for_path(path: str) -> str:
    name = Path(path or "").name.lower()
    if name in ("dockerfile", "makefile", "justfile"):
        return "docker" if name == "dockerfile" else "make"
    return _CODE_LANG_BY_EXT.get(Path(name).suffix, "text")


# --------------------------------------------------------------------------- #
# subjects & titles
# --------------------------------------------------------------------------- #

def subject_for(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> str:
    """The single value a permission rule is matched against."""
    data = tool_input or {}
    name = (tool_name or "").lower()
    if name in ("bash", "shell", "powershell"):
        return str(data.get("command", ""))
    if name in ("read", "write", "edit", "multiedit", "view", "notebookedit", "fileread", "filewrite", "fileedit"):
        return str(data.get("file_path") or data.get("path") or data.get("notebook_path") or "")
    if name in ("glob", "grep"):
        return str(data.get("pattern", ""))
    if name in ("webfetch",):
        return str(data.get("url", ""))
    if name in ("websearch",):
        return str(data.get("query", ""))
    if name in ("task", "agent"):
        return str(data.get("subagent_type") or data.get("description") or "")
    if name.startswith("mcp__"):
        return name
    for key in ("file_path", "path", "command", "url", "query", "pattern", "name", "id", "description"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return name


def _short_path(path: str) -> str:
    if not path:
        return ""
    p = str(path).replace("\\", "/")
    parts = [part for part in p.split("/") if part]
    if len(parts) <= 3:
        return p
    return "…/" + "/".join(parts[-3:])


def title_for(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> str:
    data = tool_input or {}
    name = (tool_name or "").strip()
    lower = name.lower()

    if lower in ("bash", "shell", "powershell"):
        command = str(data.get("command", "")).strip()
        description = str(data.get("description") or "").strip()
        first = command.splitlines()[0] if command else ""
        if len(first) > 96:
            first = first[:93] + "…"
        return description or first or "Run a command"
    if lower in ("write", "filewrite"):
        return f"Write {_short_path(str(data.get('file_path', '')))}"
    if lower in ("edit", "fileedit", "multiedit"):
        return f"Edit {_short_path(str(data.get('file_path', '')))}"
    if lower in ("read", "view", "fileread"):
        return f"Read {_short_path(str(data.get('file_path', '')))}"
    if lower == "notebookedit":
        return f"Edit notebook {_short_path(str(data.get('notebook_path', '')))}"
    if lower == "glob":
        return f"Find files matching {data.get('pattern', '')}"
    if lower == "grep":
        return f"Search for “{data.get('pattern', '')}”"
    if lower == "webfetch":
        return f"Fetch {data.get('url', '')}"
    if lower == "websearch":
        return f"Web search: {data.get('query', '')}"
    if lower in ("task", "agent"):
        return f"{data.get('subagent_type') or 'Sub-agent'}: {data.get('description') or 'task'}"
    if lower == "todowrite":
        todos = data.get("todos") or []
        return f"Update task list ({len(todos)} items)"
    if lower == "exitplanmode":
        return "Present the plan"
    if lower == "askuserquestion":
        return "Ask you a question"
    if lower.startswith("mcp__"):
        parts = name.split("__")
        if len(parts) >= 3:
            return f"{parts[1]} · {parts[-1]}"
        return name
    return name or "Tool"


def subtitle_for(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> str:
    data = tool_input or {}
    lower = (tool_name or "").lower()
    if lower in ("bash", "shell"):
        command = str(data.get("command", "")).strip()
        if command and data.get("description"):
            first = command.splitlines()[0]
            return first if len(first) <= 120 else first[:117] + "…"
        return ""
    if lower == "read":
        bits = []
        if data.get("offset"):
            bits.append(f"from line {data['offset']}")
        if data.get("limit"):
            bits.append(f"{data['limit']} lines")
        return " · ".join(bits)
    if lower == "grep":
        bits = []
        if data.get("glob"):
            bits.append(str(data["glob"]))
        if data.get("output_mode"):
            bits.append(str(data["output_mode"]))
        return " · ".join(bits)
    if lower in ("task", "agent"):
        return str(data.get("prompt", ""))[:160]
    return ""


# --------------------------------------------------------------------------- #
# outputs
# --------------------------------------------------------------------------- #

def _clip(text: str, limit: int = MAX_BODY) -> Tuple[str, bool]:
    if text is None:
        return "", False
    text = str(text)
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n… ({len(text) - limit} more characters)", True


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif block.get("type") == "image":
                    parts.append("[image]")
                elif "text" in block:
                    parts.append(str(block["text"]))
                else:
                    parts.append(json.dumps(block, ensure_ascii=False, indent=2)[:2000])
        return "\n".join(parts)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        return json.dumps(content, ensure_ascii=False, indent=2)
    return str(content)


def diff_from_structured(patch: Any) -> List[DiffLine]:
    lines: List[DiffLine] = []
    if not isinstance(patch, list):
        return lines
    for hunk in patch:
        if not isinstance(hunk, dict):
            continue
        old_no = int(hunk.get("oldStart") or 1)
        new_no = int(hunk.get("newStart") or 1)
        lines.append(
            DiffLine(
                kind="hunk",
                text=f"@@ -{old_no},{hunk.get('oldLines', 0)} +{new_no},{hunk.get('newLines', 0)} @@",
            )
        )
        for raw in hunk.get("lines") or []:
            text = raw if isinstance(raw, str) else str(raw)
            if text.startswith("+"):
                lines.append(DiffLine("add", text[1:], None, new_no))
                new_no += 1
            elif text.startswith("-"):
                lines.append(DiffLine("del", text[1:], old_no, None))
                old_no += 1
            elif text.startswith("\\"):
                lines.append(DiffLine("ctx", text))
            else:
                lines.append(DiffLine("ctx", text[1:] if text.startswith(" ") else text, old_no, new_no))
                old_no += 1
                new_no += 1
    return lines


def diff_from_patch_text(patch: str) -> List[DiffLine]:
    lines: List[DiffLine] = []
    for raw in (patch or "").splitlines():
        if raw.startswith("@@"):
            lines.append(DiffLine("hunk", raw))
        elif raw.startswith("+") and not raw.startswith("+++"):
            lines.append(DiffLine("add", raw[1:]))
        elif raw.startswith("-") and not raw.startswith("---"):
            lines.append(DiffLine("del", raw[1:]))
        elif raw.startswith(("---", "+++", "diff ", "index ")):
            lines.append(DiffLine("hunk", raw))
        else:
            lines.append(DiffLine("ctx", raw[1:] if raw.startswith(" ") else raw))
    return lines


def diff_from_strings(old: str, new: str, limit: int = 400) -> List[DiffLine]:
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    out: List[DiffLine] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset, line in enumerate(old_lines[i1:i2]):
                out.append(DiffLine("ctx", line, i1 + offset + 1, j1 + offset + 1))
        else:
            for offset, line in enumerate(old_lines[i1:i2]):
                out.append(DiffLine("del", line, i1 + offset + 1, None))
            for offset, line in enumerate(new_lines[j1:j2]):
                out.append(DiffLine("add", line, None, j1 + offset + 1))
        if len(out) > limit:
            break
    return out


def describe_input(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> ToolDetail:
    """What Claude wants to do — shown *before* the call is approved."""
    data = tool_input or {}
    lower = (tool_name or "").lower()
    if lower in ("bash", "shell", "powershell"):
        command = str(data.get("command", ""))
        body, truncated = _clip(command, 8000)
        detail = ToolDetail(kind="code", title="Command", body=body, language="bash", truncated=truncated)
        if data.get("timeout"):
            detail.rows.append(("Timeout", f"{int(data['timeout']) // 1000}s"))
        return detail
    if lower in ("write", "filewrite"):
        content = str(data.get("content", ""))
        body, truncated = _clip(content, 8000)
        return ToolDetail(
            kind="code",
            title=str(data.get("file_path", "")),
            body=body,
            language=language_for_path(str(data.get("file_path", ""))),
            truncated=truncated,
            rows=[("File", str(data.get("file_path", ""))), ("Size", f"{len(content):,} chars")],
        )
    if lower in ("edit", "fileedit", "multiedit"):
        old = str(data.get("old_string") or data.get("old_str") or "")
        new = str(data.get("new_string") or data.get("new_str") or "")
        diff = diff_from_strings(old, new)
        return ToolDetail(
            kind="diff",
            title=str(data.get("file_path", "")),
            diff=diff,
            stats={"add": sum(1 for d in diff if d.kind == "add"), "del": sum(1 for d in diff if d.kind == "del")},
            rows=[("File", str(data.get("file_path", "")))],
        )
    if lower == "todowrite":
        return ToolDetail(kind="todos", title="Task list", items=list(data.get("todos") or []))
    if lower in ("task", "agent"):
        return ToolDetail(
            kind="kv",
            title=str(data.get("description") or "Sub-agent"),
            rows=[
                ("Agent", str(data.get("subagent_type") or "general-purpose")),
                ("Description", str(data.get("description") or "")),
                ("Prompt", _clip(str(data.get("prompt") or ""), 4000)[0]),
            ],
        )
    if lower in ("webfetch", "websearch"):
        rows = [(k.replace("_", " ").title(), str(v)) for k, v in data.items() if isinstance(v, (str, int, float))]
        return ToolDetail(kind="kv", title=title_for(tool_name, data), rows=rows)
    if not data:
        return ToolDetail(kind="none")
    try:
        body, truncated = _clip(json.dumps(data, ensure_ascii=False, indent=2), 8000)
    except (TypeError, ValueError):
        body, truncated = _clip(str(data), 8000)
    return ToolDetail(kind="json", title="Input", body=body, language="json", truncated=truncated)


def describe_output(tool_name: str, tool_input: Optional[Dict[str, Any]],
                    content: Any, structured: Any = None) -> ToolDetail:
    """What the tool returned — rendered as code, diff, file list or key/value rows."""
    data = tool_input or {}
    lower = (tool_name or "").lower()
    struct = structured if isinstance(structured, dict) else {}
    text = _content_to_text(content)

    if lower in ("bash", "shell", "powershell"):
        stdout = str(struct.get("stdout", "")) if struct else ""
        stderr = str(struct.get("stderr", "")) if struct else ""
        if not stdout and not stderr:
            stdout = text
        body, truncated = _clip(stdout, MAX_BODY)
        detail = ToolDetail(kind="code", title="Output", body=body, language="text", truncated=truncated)
        if stderr.strip():
            err, err_trunc = _clip(stderr, 6000)
            detail.rows.append(("stderr", err))
            detail.truncated = detail.truncated or err_trunc
        if struct.get("interrupted"):
            detail.rows.append(("Status", "interrupted"))
        if struct.get("backgroundTaskId"):
            detail.rows.append(("Background task", str(struct["backgroundTaskId"])))
        return detail

    if lower in ("edit", "fileedit", "multiedit", "write", "filewrite", "notebookedit"):
        patch = struct.get("structuredPatch")
        diff = diff_from_structured(patch)
        if not diff and struct.get("gitDiff", {}).get("patch"):
            diff = diff_from_patch_text(struct["gitDiff"]["patch"])
        if not diff:
            old = str(struct.get("oldString") or data.get("old_string") or "")
            new = str(struct.get("newString") or data.get("content") or data.get("new_string") or "")
            if old or new:
                diff = diff_from_strings(old, new)
        rows: List[Tuple[str, str]] = []
        file_path = str(struct.get("filePath") or data.get("file_path") or "")
        if file_path:
            rows.append(("File", file_path))
        git_diff = struct.get("gitDiff") or {}
        if git_diff:
            rows.append(("Git", f"+{git_diff.get('additions', 0)} / -{git_diff.get('deletions', 0)} ({git_diff.get('status', 'modified')})"))
        if struct.get("type"):
            rows.append(("Action", str(struct["type"])))
        detail = ToolDetail(
            kind="diff" if diff else "text",
            title="Changes" if diff else "Result",
            diff=diff,
            rows=rows,
            stats={"add": sum(1 for d in diff if d.kind == "add"), "del": sum(1 for d in diff if d.kind == "del")},
        )
        if not diff:
            detail.body, detail.truncated = _clip(text, 6000)
        return detail

    if lower in ("read", "view", "fileread"):
        file_info = struct.get("file") or {}
        body_text = str(file_info.get("content") or text)
        body, truncated = _clip(body_text, MAX_BODY)
        path = str(file_info.get("filePath") or data.get("file_path") or "")
        rows = []
        if path:
            rows.append(("File", path))
        if file_info.get("numLines") is not None:
            rows.append(("Lines", f"{file_info.get('startLine', 1)}–{int(file_info.get('startLine', 1)) + int(file_info.get('numLines', 0)) - 1} of {file_info.get('totalLines', '?')}"))
        return ToolDetail(kind="code", title="File", body=body, language=language_for_path(path),
                          rows=rows, truncated=truncated)

    if lower == "glob":
        files = struct.get("filenames") or []
        items = [{"text": str(f)} for f in files[:200]]
        return ToolDetail(kind="files", title="Matching files", items=items,
                          stats={"count": struct.get("numFiles", len(files)), "truncated": struct.get("truncated", False)})

    if lower == "grep":
        files = struct.get("filenames") or []
        content = struct.get("content") or ""
        if content:
            body, truncated = _clip(content, MAX_BODY)
            return ToolDetail(kind="code", title="Matches", body=body, language="text", truncated=truncated,
                              stats={"files": struct.get("numFiles", len(files))})
        return ToolDetail(kind="files", title="Files with matches", items=[{"text": str(f)} for f in files[:200]],
                          stats={"count": struct.get("numFiles", len(files))})

    if lower == "todowrite":
        todos = struct.get("newTodos") or data.get("todos") or []
        return ToolDetail(kind="todos", title="Task list", items=list(todos))

    if lower in ("webfetch",):
        rows = []
        if struct.get("code") is not None:
            rows.append(("HTTP", f"{struct.get('code')} {struct.get('codeText', '')}".strip()))
        if struct.get("bytes") is not None:
            rows.append(("Size", f"{int(struct['bytes']):,} bytes"))
        if struct.get("durationMs") is not None:
            rows.append(("Time", f"{int(struct['durationMs']) / 1000:.1f}s"))
        if struct.get("url"):
            rows.append(("URL", str(struct["url"])))
        body, truncated = _clip(str(struct.get("result") or text), MAX_BODY)
        return ToolDetail(kind="text", title="Fetched", body=body, rows=rows, truncated=truncated)

    if lower == "websearch":
        results = struct.get("results") or []
        if results:
            return ToolDetail(kind="files", title="Search results",
                              items=[{"text": str(r.get("title", "")), "sub": str(r.get("url", ""))} for r in results[:30]])
        body, truncated = _clip(text, MAX_BODY)
        return ToolDetail(kind="text", title="Search results", body=body, truncated=truncated)

    if lower in ("task", "agent"):
        body, truncated = _clip(text, MAX_BODY)
        return ToolDetail(kind="text", title="Sub-agent result", body=body, truncated=truncated)

    if lower == "exitplanmode":
        plan = str(data.get("plan") or text)
        body, truncated = _clip(plan, MAX_BODY)
        return ToolDetail(kind="text", title="Plan", body=body, truncated=truncated)

    if not text.strip() and not struct:
        return ToolDetail(kind="none", title="")

    body, truncated = _clip(text, MAX_BODY)
    looks_json = body.lstrip().startswith(("{", "["))
    return ToolDetail(kind="json" if looks_json else "text", title="Output", body=body,
                      language="json" if looks_json else "", truncated=truncated)


def file_stats(path: str) -> Dict[str, Any]:
    """Lightweight folder facts for the project header."""
    stats: Dict[str, Any] = {"files": 0, "size": 0, "git": False, "branch": ""}
    root = Path(path)
    try:
        stats["git"] = (root / ".git").exists()
        if stats["git"]:
            head = root / ".git" / "HEAD"
            if head.exists():
                text = head.read_text(encoding="utf-8", errors="replace").strip()
                if text.startswith("ref:"):
                    stats["branch"] = text.split("refs/heads/")[-1].strip()
    except OSError:
        pass
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".cache", "target"}
    count = 0
    size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            count += len(filenames)
            if count > 20000:
                break
    except OSError:
        pass
    stats["files"] = count
    stats["size"] = size
    return stats
