"""Which CLI flags this installation understands, and how to build a command line.

Claude Code evolves quickly, so instead of hard-coding flags we read
`claude --help` once, cache the result and degrade gracefully on older or newer
builds. Unknown-option failures are retried with the offending flag removed.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from fcc import paths
from fcc.logging_setup import get_logger

log = get_logger("cli.caps")

CACHE_VERSION = 4


@dataclass
class Capabilities:
    cli_path: str = ""
    cli_version: str = ""
    probed_at: float = 0.0
    # core
    print_mode: bool = True
    output_formats: List[str] = field(default_factory=lambda: ["text", "json", "stream-json"])
    input_formats: List[str] = field(default_factory=lambda: ["text", "stream-json"])
    stream_json_input: bool = True
    stream_json_output: bool = True
    verbose: bool = True
    partial_messages: bool = True
    replay_user_messages: bool = False
    include_hook_events: bool = False
    forward_subagent_text: bool = False
    # sessions
    resume: bool = True
    continue_: bool = True
    session_id: bool = True
    fork_session: bool = False
    no_session_persistence: bool = False
    name: bool = False
    # permissions
    permission_mode: bool = True
    permission_modes: List[str] = field(default_factory=lambda: ["default", "acceptEdits", "plan", "bypassPermissions"])
    permission_prompts: bool = False
    permission_prompt_choices: List[str] = field(default_factory=list)
    permission_prompt_tool: bool = True
    allowed_tools: bool = True
    allowed_tools_flag: str = "--allowedTools"
    disallowed_tools: bool = True
    disallowed_tools_flag: str = "--disallowedTools"
    add_dir: bool = True
    allow_dangerously_skip: bool = False
    dangerously_skip: bool = True
    restricted: bool = False
    safe_mode: bool = False
    # model / prompt
    model: bool = True
    fallback_model: bool = False
    effort: bool = False
    effort_levels: List[str] = field(default_factory=list)
    system_prompt: bool = True
    append_system_prompt: bool = True
    agents: bool = False
    agent: bool = False
    tools_flag: bool = False
    mcp_config: bool = True
    strict_mcp_config: bool = False
    settings_flag: bool = False
    setting_sources: bool = False
    json_schema: bool = False
    max_budget: bool = False
    prompt_suggestions: bool = False
    autocompact: bool = False
    worktree: bool = False
    debug: bool = True
    unknown: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @property
    def interactive_streaming(self) -> bool:
        return self.stream_json_input and self.stream_json_output

    @property
    def host_permission_prompts(self) -> bool:
        """Can the app answer permission prompts over the control channel?"""
        return self.permission_prompt_tool or self.permission_prompts

    def summary(self) -> Dict[str, str]:
        interesting = [
            "stream_json_input", "partial_messages", "resume", "session_id", "fork_session",
            "permission_mode", "permission_prompt_tool", "permission_prompts", "allowed_tools",
            "add_dir", "model", "effort", "append_system_prompt", "agents", "mcp_config",
            "settings_flag", "json_schema", "replay_user_messages", "include_hook_events",
            "no_session_persistence", "name", "dangerously_skip", "safe_mode", "restricted",
        ]
        out = {}
        for key in interesting:
            value = getattr(self, key, None)
            if isinstance(value, bool):
                out[key] = "yes" if value else "no"
            elif isinstance(value, list):
                out[key] = ", ".join(str(v) for v in value) or "-"
        out["permission_modes"] = ", ".join(self.permission_modes) or "-"
        return out


_FLAG_RE = re.compile(r"(--[a-z0-9\-]+)")


def _flatten(help_text: str) -> str:
    """Help output is wrapped; join it so regexes see one logical line per flag."""
    lines = [ln.rstrip() for ln in help_text.splitlines()]
    joined: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            joined.append("")
            continue
        if line.startswith("  ") and not line.startswith("    ") and joined and joined[-1]:
            # continuation of the previous option description
            joined[-1] = joined[-1] + " " + stripped
        elif joined and joined[-1].endswith(" ") is False and line.startswith("      "):
            joined[-1] = joined[-1] + " " + stripped
        else:
            joined.append(stripped)
    text = "\n".join(joined)
    return re.sub(r"[ \t]+", " ", text)


def _choices(text: str, flag: str) -> List[str]:
    pattern = re.compile(re.escape(flag) + r"[^\n]*?\(choices:\s*([^)]*)\)")
    match = pattern.search(text)
    if not match:
        return []
    return [part.strip().strip('"').strip("'") for part in match.group(1).split(",") if part.strip()]


def parse_help(help_text: str) -> Capabilities:
    caps = Capabilities()
    if not help_text.strip():
        caps.unknown.append("empty-help")
        return caps
    flat = _flatten(help_text)
    found = set(_FLAG_RE.findall(flat))

    def has(*names: str) -> bool:
        return any(name in found for name in names)

    caps.print_mode = has("-p", "--print")
    caps.output_formats = _choices(flat, "--output-format") or caps.output_formats
    caps.input_formats = _choices(flat, "--input-format") or caps.input_formats
    caps.stream_json_output = "stream-json" in caps.output_formats
    caps.stream_json_input = "stream-json" in caps.input_formats
    caps.verbose = has("--verbose")
    caps.partial_messages = has("--include-partial-messages")
    caps.replay_user_messages = has("--replay-user-messages")
    caps.include_hook_events = has("--include-hook-events")
    caps.forward_subagent_text = has("--forward-subagent-text")

    caps.resume = has("-r", "--resume")
    caps.continue_ = has("-c", "--continue")
    caps.session_id = has("--session-id")
    caps.fork_session = has("--fork-session")
    caps.no_session_persistence = has("--no-session-persistence")
    caps.name = has("-n", "--name")

    caps.permission_mode = has("--permission-mode")
    modes = _choices(flat, "--permission-mode")
    if modes:
        caps.permission_modes = modes
    caps.permission_prompts = has("--permission-prompts")
    caps.permission_prompt_choices = _choices(flat, "--permission-prompts")
    caps.permission_prompt_tool = has("--permission-prompt-tool")
    caps.allowed_tools = has("--allowedTools", "--allowed-tools")
    caps.allowed_tools_flag = "--allowedTools" if "--allowedTools" in found else "--allowed-tools"
    caps.disallowed_tools = has("--disallowedTools", "--disallowed-tools")
    caps.disallowed_tools_flag = "--disallowedTools" if "--disallowedTools" in found else "--disallowed-tools"
    caps.add_dir = has("--add-dir")
    caps.allow_dangerously_skip = has("--allow-dangerously-skip-permissions")
    caps.dangerously_skip = has("--dangerously-skip-permissions")
    caps.restricted = has("--restricted")
    caps.safe_mode = has("--safe-mode")

    caps.model = has("--model")
    caps.fallback_model = has("--fallback-model")
    caps.effort = has("--effort")
    caps.effort_levels = _choices(flat, "--effort")
    caps.system_prompt = has("--system-prompt")
    caps.append_system_prompt = has("--append-system-prompt")
    caps.agents = has("--agents")
    caps.agent = has("--agent")
    caps.tools_flag = has("--tools")
    caps.mcp_config = has("--mcp-config")
    caps.strict_mcp_config = has("--strict-mcp-config")
    caps.settings_flag = has("--settings")
    caps.setting_sources = has("--setting-sources")
    caps.json_schema = has("--json-schema")
    caps.max_budget = has("--max-budget-usd")
    caps.prompt_suggestions = has("--prompt-suggestions")
    caps.autocompact = has("--autocompact")
    caps.worktree = has("-w", "--worktree")
    caps.debug = has("-d", "--debug")
    return caps


def cache_file() -> Path:
    return paths.cache_dir() / "cli-capabilities.json"


def cache_load(cli_path: str, cli_version: str) -> Optional[Capabilities]:
    try:
        file = cache_file()
        if not file.exists():
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("cache_version") != CACHE_VERSION:
            return None
        if data.get("cli_path") != cli_path or data.get("cli_version") != cli_version:
            return None
        if time.time() - float(data.get("probed_at", 0)) > 60 * 60 * 24 * 14:
            return None
        caps = Capabilities(**{k: v for k, v in data.items() if k in Capabilities.__dataclass_fields__})
        log.info("Using cached CLI capabilities for %s", cli_version)
        return caps
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def cache_store(caps: Capabilities) -> None:
    try:
        data = asdict(caps)
        data["cache_version"] = CACHE_VERSION
        cache_file().parent.mkdir(parents=True, exist_ok=True)
        cache_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not cache CLI capabilities: %s", exc)


def detect(cli_path: str, cli_version: str, help_text: str, use_cache: bool = True) -> Capabilities:
    if use_cache:
        cached = cache_load(cli_path, cli_version)
        if cached is not None:
            return cached
    caps = parse_help(help_text)
    caps.cli_path = cli_path
    caps.cli_version = cli_version
    caps.probed_at = time.time()
    cache_store(caps)
    return caps


# --------------------------------------------------------------------------- #
# command line construction
# --------------------------------------------------------------------------- #

PERMISSION_SERVER_NAME = "fcc_studio"


@dataclass
class LaunchOptions:
    project_path: str
    resume_session_id: str = ""
    new_session_id: str = ""
    model: str = ""
    effort: str = ""
    permission_mode: str = "default"
    allowed_tools: List[str] = field(default_factory=list)
    disallowed_tools: List[str] = field(default_factory=list)
    add_dirs: List[str] = field(default_factory=list)
    append_system_prompt: str = ""
    session_name: str = ""
    streaming: bool = True
    host_permissions: bool = True
    persist_session: bool = True
    extra_args: List[str] = field(default_factory=list)
    safe_mode: bool = False
    max_budget_usd: float = 0.0
    disabled_flags: List[str] = field(default_factory=list)


def build_command(cli_path: str, caps: Capabilities, opts: LaunchOptions) -> List[str]:
    """Assemble the CLI invocation for a long-lived streaming session."""
    argv: List[str] = [cli_path]
    disabled = set(opts.disabled_flags)

    def add(flag: str, *values: str, supported: bool = True) -> None:
        if not supported or flag in disabled:
            return
        argv.append(flag)
        argv.extend(v for v in values if v not in (None, ""))

    add("-p", supported=caps.print_mode)
    if caps.stream_json_output and "--output-format" not in disabled:
        argv += ["--output-format", "stream-json"]
    if caps.stream_json_input and "--input-format" not in disabled:
        argv += ["--input-format", "stream-json"]
    add("--verbose", supported=caps.verbose)

    if opts.streaming and caps.partial_messages:
        add("--include-partial-messages")
    # --replay-user-messages is intentionally not used: the app records the
    # prompts it sends, so an echo would duplicate them in the transcript.

    # permissions -----------------------------------------------------------
    mode = (opts.permission_mode or "default").strip()
    if caps.permission_mode and mode and mode != "default" and mode in caps.permission_modes:
        add("--permission-mode", mode)
    if mode == "bypassPermissions":
        if caps.allow_dangerously_skip:
            add("--allow-dangerously-skip-permissions")
        if caps.dangerously_skip:
            add("--dangerously-skip-permissions")
    if opts.host_permissions and caps.permission_prompt_tool and "--permission-prompt-tool" not in disabled:
        argv += ["--permission-prompt-tool", f"mcp__{PERMISSION_SERVER_NAME}__can_use_tool"]
    if opts.host_permissions and caps.permission_prompts and "host" in (caps.permission_prompt_choices or ["host"]):
        add("--permission-prompts", "host")
    if opts.allowed_tools and caps.allowed_tools:
        argv += [caps.allowed_tools_flag, *opts.allowed_tools]
    if opts.disallowed_tools and caps.disallowed_tools:
        argv += [caps.disallowed_tools_flag, *opts.disallowed_tools]
    for directory in opts.add_dirs:
        if caps.add_dir and directory:
            argv += ["--add-dir", directory]

    # session ---------------------------------------------------------------
    if opts.resume_session_id and caps.resume:
        add("--resume", opts.resume_session_id)
    elif opts.new_session_id and caps.session_id:
        add("--session-id", opts.new_session_id)
    if opts.session_name and caps.name:
        add("--name", opts.session_name[:60])
    if not opts.persist_session and caps.no_session_persistence:
        add("--no-session-persistence")
    if opts.safe_mode and caps.safe_mode:
        add("--safe-mode")

    # model / prompt --------------------------------------------------------
    if opts.model and caps.model:
        add("--model", opts.model)
    if opts.effort and caps.effort and (not caps.effort_levels or opts.effort in caps.effort_levels):
        add("--effort", opts.effort)
    if opts.append_system_prompt and caps.append_system_prompt:
        add("--append-system-prompt", opts.append_system_prompt)
    if opts.max_budget_usd and caps.max_budget:
        add("--max-budget-usd", str(opts.max_budget_usd))

    for extra in opts.extra_args:
        if extra:
            argv.append(extra)
    return argv


_UNKNOWN_OPTION_RE = re.compile(r"unknown option '([^']+)'")
_UNKNOWN_FLAG_RE = re.compile(r"(?:unknown|unrecognized|invalid) (?:option|flag|argument)[:\s]+(-{1,2}[A-Za-z0-9\-]+)", re.I)


def flags_rejected_by_cli(stderr_text: str) -> List[str]:
    """Extract flag names the CLI refused, so we can retry without them."""
    out: List[str] = []
    for match in _UNKNOWN_OPTION_RE.finditer(stderr_text or ""):
        out.append(match.group(1))
    for match in _UNKNOWN_FLAG_RE.finditer(stderr_text or ""):
        out.append(match.group(1))
    cleaned = []
    for flag in out:
        flag = flag.strip().strip("'\"")
        if flag.startswith("-") and flag not in cleaned:
            cleaned.append(flag)
    return cleaned
