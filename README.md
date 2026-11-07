# Claude Code Studio (FCC)

A native **Windows desktop application**, written in Python (PySide6 / Qt), that turns the
[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) into a polished chat
application — the same feel as the Claude app: coral-on-cream design, a conversation pane,
and a live view of *everything* Claude Code is doing (tool calls, file edits, diffs, shell
commands, thinking, costs) instead of a terminal.

> Not a web app. No browser, no server, no terminal window. One process talks to the
> `claude` executable over its streaming JSON protocol and renders the whole session natively.

![logo](assets/logo.png)

---

## شروع سریع (فارسی)

۱. پیش‌نیاز: ویندوز ۱۰/۱۱، پایتون ۳.۱۰ به بالا، و Claude Code نصب‌شده
(`npm install -g @anthropic-ai/claude-code` و سپس یک بار `claude` و `/login`).

۲. نصب وابستگی‌ها و اجرا:

```bat
pip install -r requirements.txt
python run.py
```

یا دوبار کلیک روی `fcc.bat`.

۳. اولین اجرا: پوشهٔ پروژه را انتخاب می‌کنید → مجوز دسترسی می‌دهید → چت باز می‌شود.
هر کاری که Claude انجام می‌دهد (خواندن فایل، ویرایش، دستور شل، جست‌وجو) به‌صورت کارت‌های
زنده نمایش داده می‌شود و برای اقدامات حساس، کارت تأیید/رد می‌آید.

حالت نمایشی بدون نیاز به CLI یا اینترنت: `python run.py --demo`

---

## What you get

| Requirement | Where it lives |
|---|---|
| Pick the working folder | `Welcome` screen + *Choose folder* (`ui/widgets/welcome.py`, `claude/projects.py`) |
| Approve / deny access to it | Trust dialog with permission mode + “remember” (`ui/dialogs/trust.py`, `config.py`) |
| Chat UI like the Claude app | Streaming markdown chat, composer with attachments, sessions sidebar (`ui/widgets/*`) |
| Drive the CLI and show the answers | `ClaudeBackend` spawns `claude -p --input-format stream-json …` and pipes NDJSON into the UI (`claude/session.py`, `claude/protocol.py`) |
| Show the entire process | Tool cards with live input streaming, diffs with syntax highlighting, bash output, todos, thinking (`ui/widgets/tool_card.py`, `claude/toolmeta.py`) |
| Claude branding | Coral/cream/dark palettes, sunburst mark, typography, animations (`theme.py`, `icons.py`, `assets/`) |
| No crash on launch | Layered fallbacks: capability probe with flag-degradation, retry with `--resume`, crash file, diagnostics dialog |
| `.exe` + installer | `tools/build_windows.py` → PyInstaller + Inno Setup; CI workflow publishes a release |

### Feature tour

- **Sessions**: multiple conversations per project, renamed/deleted from the sidebar,
  transcripts recorded to JSONL and replayed when reopened, exportable to Markdown.
- **Permissions, done properly**: the app hosts an in-process MCP server
  (`mcp__fcc_studio__can_use_tool`) so every `can_use_tool` request becomes a beautiful
  inline card (plus a modal dialog when the window is unfocused). Remember decisions per
  session / project / globally with patterns like `Bash(git *)` or `Write(src/**)`.
  A layered fallback covers CLI versions without the prompt tool
  (`system/permission_denied` card → `--allowedTools` → automatic `--resume` retry).
- **Permission modes**: default, acceptEdits, plan, bypassPermissions (with a loud warning),
  dontAsk, auto — switchable live via the control channel.
- **Live control**: interrupt a run, switch model or effort mid-session, watch context usage,
  cost and token counters in the status bar.
- **Themes**: light / dark / system, five accent palettes, font scaling, density, animations
  on/off, full RTL Persian localisation (`fa`) alongside English.
- **Demo mode** (`--demo`): a scripted offline session that exercises every widget,
  including a permission prompt — perfect for exploring the UI or UI tests.
- **Diagnostics & build dialogs**: environment report, `claude doctor` runner, copyable
  bug report, and a one-click packaging entry point.

---

## How it works (protocol notes)

```
┌────────────── Qt GUI (main thread) ──────────────┐
│  chat view · tool cards · permission cards · …   │
└──────────────▲───────────────────▲───────────────┘
        signals│                   │signals
┌──────────────┴─────┐   ┌─────────┴────────┐
│ StreamInterpreter  │   │ PermissionBroker │◄── rules (session/project/global)
└──────────────▲─────┘   └─────────▲────────┘
        NDJSON │                   │ blocking ask/answer
┌──────────────┴───────────────────┴───────────────┐
│ reader thread · control thread · MCP perm server │
└──────────────▲───────────────────────────────────┘
               │ stdout/stdin (stream-json + control protocol)
        ┌──────┴──────┐
        │ claude -p … │  (hidden process, CREATE_NO_WINDOW on Windows)
        └─────────────┘
```

Validated against Claude Code **2.1.x**:

```
claude -p --input-format stream-json --output-format stream-json --verbose \
       --include-partial-messages \
       --permission-prompts host \
       --permission-prompt-tool mcp__fcc_studio__can_use_tool \
       [--permission-mode …] [--model …] [--resume <id>]
```

- `initialize` control request is answered echoing the requested MCP `protocolVersion`,
  notifications are acked with an empty result, and `tools/call` replies with
  `{"behavior":"allow","updatedInput":{…}}` or `{"behavior":"deny","message":"…"}`.
- Stream order handled: `system/init` → `stream_event` SSE frames (text / thinking /
  `input_json_delta`) → aggregated `assistant` → `user` tool results with
  `structuredPatch` + `gitDiff` + `tool_result_meta.permission_decision` → `result`
  (cost, usage, `modelUsage`, `num_turns`).
- Capability probe (`claude --help`) is cached and **degrades gracefully**: if a future CLI
  rejects a flag, stderr is parsed and the session is relaunched without it, or resumed.

---

## Run from source

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Linux/macOS
.venv/bin/python run.py                                             # or: python run.py
```

Useful flags: `--demo`, `--project <dir>`, `--new-session`, `--theme light|dark|system`,
`--accent coral|clay|ember|olive|slate`, `--lang en|fa`, `--font-size 15`,
`--mode acceptEdits`, `--model <name>`, `--cli <path>`, `--console-log`,
`--diagnostics`, `--reset-config`, `--version`.

Runtime data (config, transcripts, logs) lives in
`%APPDATA%\ClaudeCodeStudio` on Windows (`~/.config/ClaudeCodeStudio` elsewhere);
override with `FCC_DATA_DIR`.

---

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                       # unit + widget tests (offscreen Qt)
FCC_E2E=1 python -m pytest             # + end-to-end against the REAL claude CLI
```

The end-to-end suite starts a local mock Anthropic API, launches the genuine CLI through
`ClaudeBackend`, answers a real permission ask over the MCP control channel, and asserts
the file the model “wrote” appears on disk — deny paths included.

On bare Linux CI containers without `libGL`/`libdbus` (Qt fails to import), generate
load-time stubs once — they are never called by the offscreen platform:

```bash
python tools/make_stublibs.py
LD_LIBRARY_PATH=~/.cache/fcc-stublibs python -m pytest
```

CI itself (`.github/workflows/tests.yml`, matrix ubuntu/windows × py3.10/3.12) writes
pytest output to `pytest_out.txt`, appends the real `PYTEST_EXIT_CODE=`, forces Qt
logging to stderr, and uploads both as an artifact on failure. The full story of the
two shutdown crashes this caught — and a step-by-step guide for debugging any future
red check — lives in [`docs/ci-debug-history.md`](docs/ci-debug-history.md) (فارسی).

---

## Packaging: `.exe` + installer

Packaging must run **on Windows** (or in the included GitHub Actions workflow) — the
sandbox/CI Linux box cannot produce PE binaries. Everything else is already wired:

```bat
pip install -r requirements-dev.txt
python tools\build_windows.py --output build\output --installer
```

That produces, in `build\output`:

1. `ClaudeCodeStudio\` — the app folder (fast startup), plus
   `ClaudeCodeStudio-<ver>-win64-portable.zip` (copy-anywhere build);
2. `ClaudeCodeStudio-Setup-<ver>-x64.exe` — an Inno Setup installer with per-user or
   per-machine install, Start Menu/desktop shortcuts, optional “install Claude Code CLI
   now” task (runs `npm install -g @anthropic-ai/claude-code`), uninstaller, and a
   post-install check that explains `/login` when the CLI is missing.

Options: `--onefile` (single self-contained exe), `--console` (debug console window),
`--clean`, `--skip-install`. Icons (`assets/icon.ico`, installer/tray variants) are
regenerated from vector maths with `python tools/make_icons.py`.

**Zero-touch releases:** push a tag (`git tag v1.0.1 && git push --tags`) or trigger the
`build-windows` workflow manually — GitHub’s Windows runner builds the exe + installer and
publishes them to a GitHub Release. The `tests` workflow runs the suite on Linux + Windows.

---

## Repository layout

```
src/fcc/            application package
  claude/           CLI discovery, capabilities, NDJSON protocol, control channel,
                    permission broker, backends (real + demo), transcripts, projects
  ui/               main window, chat widgets, composer, sidebar, dialogs
                    (trust / permission / settings / diagnostics / build)
  theme.py icons.py markdown.py i18n.py config.py paths.py logging_setup.py
assets/             generated icons (ico/png) + macOS iconset on demand
build/              fcc.spec (PyInstaller), version_info.txt, installer/ClaudeCodeStudio.iss
tools/              build_windows.py, make_icons.py, make_stublibs.py
tests/              unit, widget (offscreen Qt) and real-CLI end-to-end suites
docs/               intro site (index.html) + CI debug history (ci-debug-history.md, فارسی)
.github/workflows/  tests.yml, windows-build.yml
run.py, fcc.bat     launchers
```

---

## Troubleshooting

- **“Claude Code CLI not found”** — install Node.js 18+, then
  `npm install -g @anthropic-ai/claude-code`; or point Settings → CLI path at it.
- **Auth errors** — run `claude` once in a terminal and sign in with `/login`; the app
  shows the exact hint from `claude doctor` in the diagnostics dialog.
- **A session died unexpectedly** — the crash file and rotating logs are under
  `%APPDATA%\ClaudeCodeStudio\logs`; *Help → Diagnostics* copies a full report.
- **Everything looks fine but nothing streams** — older CLIs may lack
  `--include-partial-messages`; the app detects the rejection and relaunches without it
  (aggregated messages still render).
- **A GitHub Actions check is red** — open the run under the repo's *Actions* tab,
  read the *Run the test suite* step (full pytest output + real exit code) and
  download the `pytest-<os>-<python>` artifact. تاریخچه و راهنمای کامل فارسی:
  [`docs/ci-debug-history.md`](docs/ci-debug-history.md).

## License

MIT — see `LICENSE`. “Claude”, “Claude Code” and the sunburst mark are trademarks of
Anthropic, PBC; this is an independent community front-end, not affiliated with or
endorsed by Anthropic.
