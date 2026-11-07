from fcc.claude import capabilities

HELP = """Usage: claude [options] [command] [prompt]

Options:
  --add-dir <directories...>            Additional directories to allow tool
                                        access to
  --include-partial-messages            Include partial message chunks as they
                                        arrive (only works with --print and
                                        --output-format=stream-json)
  --input-format <format>               Input format (only works with --print):
                                        "text" (default), or "stream-json"
                                        (choices: "text", "stream-json")
  --output-format <format>              Output format (only works with --print):
                                        "text" "json", or "stream-json"
                                        (choices: "text", "json", "stream-json")
  --permission-mode <mode>              Permission mode to use for the session
                                        (choices: "acceptEdits", "auto",
                                        "bypassPermissions", "manual",
                                        "dontAsk", "plan")
  --permission-prompts <target>         Who answers permission prompts
                                        (choices: "host", "none", default:
                                        "host")
  --permission-prompt-tool <tool>       MCP tool that answers prompts
  -p, --print                           Print response and exit
  -r, --resume [value]                  Resume a conversation by session ID
  --session-id <uuid>                   Use a specific session ID
  -n, --name <name>                     Set a display name for the session
  --allowedTools, --allowed-tools <tools...>
      Comma or space-separated list of tool names to allow
  --model <model>                       Model for the current session
  --effort <level>                      Effort level (low, medium, high, xhigh,
                                        max)
  --verbose                             Override verbose mode setting
"""


def test_parse_help_detects_flags():
    caps = capabilities.parse_help(HELP)
    assert caps.print_mode
    assert caps.stream_json_input and caps.stream_json_output
    assert caps.partial_messages
    assert caps.resume
    assert caps.session_id
    assert caps.permission_mode
    assert "acceptEdits" in caps.permission_modes
    assert "bypassPermissions" in caps.permission_modes
    assert caps.permission_prompts
    assert caps.permission_prompt_tool
    assert caps.allowed_tools
    assert caps.model
    assert caps.effort
    assert caps.verbose


def test_build_command_full():
    caps = capabilities.parse_help(HELP)
    options = capabilities.LaunchOptions(
        project_path="/tmp/proj",
        model="sonnet",
        permission_mode="acceptEdits",
        allowed_tools=["Bash(git *)"],
        add_dirs=["/tmp/extra"],
        streaming=True,
        host_permissions=True,
        session_name="my session",
    )
    argv = capabilities.build_command("/usr/bin/claude", caps, options)
    assert argv[0] == "/usr/bin/claude"
    assert "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--input-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert "--include-partial-messages" in argv
    assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    assert argv[argv.index("--permission-prompt-tool") + 1] == \
        f"mcp__{capabilities.PERMISSION_SERVER_NAME}__can_use_tool"
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert "Bash(git *)" in argv
    assert "--add-dir" in argv
    assert argv[argv.index("--name") + 1] == "my session"


def test_build_command_disables_flags():
    caps = capabilities.parse_help(HELP)
    options = capabilities.LaunchOptions(
        project_path="/tmp/proj",
        permission_mode="default",
        host_permissions=False,
        disabled_flags=["--include-partial-messages", "--permission-prompt-tool"],
    )
    argv = capabilities.build_command("claude", caps, options)
    assert "--include-partial-messages" not in argv
    assert "--permission-prompt-tool" not in argv


def test_bypass_mode_adds_danger_flags():
    caps = capabilities.parse_help(HELP + "  --allow-dangerously-skip-permissions  Enable bypassing\n"
                                            "  --dangerously-skip-permissions  Bypass all checks\n")
    options = capabilities.LaunchOptions(project_path="/tmp/proj",
                                         permission_mode="bypassPermissions")
    argv = capabilities.build_command("claude", caps, options)
    assert "--allow-dangerously-skip-permissions" in argv
    assert "--dangerously-skip-permissions" in argv


def test_flags_rejected_by_cli():
    stderr = "error: unknown option '--include-partial-messages'\n(Did you mean --print?)\n"
    stderr += "warning: unknown flag --frobnicate\n"
    flags = capabilities.flags_rejected_by_cli(stderr)
    assert "--include-partial-messages" in flags
    assert "--frobnicate" in flags


def test_unknown_help_is_tolerant():
    caps = capabilities.parse_help("")
    assert caps.unknown
    assert caps.print_mode is True  # defaults keep the app functional


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(capabilities, "cache_file", lambda: tmp_path / "caps.json")
    caps = capabilities.parse_help(HELP)
    import time

    caps.cli_path = "/tmp/claude"
    caps.cli_version = "9.9.9"
    caps.probed_at = time.time()
    capabilities.cache_store(caps)
    loaded = capabilities.cache_load("/tmp/claude", "9.9.9")
    assert loaded is not None
    assert loaded.permission_modes == caps.permission_modes
