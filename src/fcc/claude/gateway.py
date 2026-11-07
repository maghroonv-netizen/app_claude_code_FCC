"""Free Claude Code (FCC) gateway detection and environment bridging.

The user may run the FCC server (`fcc-server` / `fcc server` from
github.com/Alishahryar1/free-claude-code) which exposes an Anthropic-compatible
proxy plus an admin dashboard (default http://127.0.0.1:8082/admin) where API
keys for dozens of providers are configured.  Their terminal Claude Code works
because FCC launches it with a specific environment (ANTHROPIC_BASE_URL pointing
at the proxy, ANTHROPIC_AUTH_TOKEN, …).  A desktop app that spawns `claude`
without that environment cannot see the gateway and fails with auth errors —
this module closes that gap:

* reads FCC's own config (`~/.fcc/.env`: PORT / HOST / ANTHROPIC_AUTH_TOKEN),
* falls back to the ports people actually run it on (8082, 8000, 5000),
* falls back to whatever `~/.claude/settings.json` env already contains,
* probes the proxy with a fast HTTP request,
* reproduces FCC's exact Claude environment policy so the GUI session behaves
  exactly like a terminal session started through FCC.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_PORT = 8082
FALLBACK_PORTS = (8082, 8000, 5000)
DEFAULT_TOKEN = "freecc"
CACHE_SECONDS = 30.0

_cache: Dict[str, object] = {"at": 0.0, "info": None}


@dataclass
class GatewayInfo:
    detected: bool = False
    base_url: str = ""
    admin_url: str = ""
    port: int = 0
    token: str = ""
    token_source: str = ""          # env-file | settings | config | default
    source: str = ""                # env-file | probe | settings | config
    detail: str = ""
    models: List[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.detected:
            return self.detail or "not detected"
        return f"{self.base_url} (port {self.port})"


# --------------------------------------------------------------------------- #
# config sources
# --------------------------------------------------------------------------- #
def fcc_env_path() -> Path:
    return Path.home() / ".fcc" / ".env"


def read_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def read_claude_settings_env() -> Dict[str, str]:
    """Env entries FCC (or the user) stored in Claude Code's own settings."""
    candidates = [Path.home() / ".claude" / "settings.json"]
    xdg = os.environ.get("CLAUDE_CONFIG_DIR")
    if xdg:
        candidates.insert(0, Path(xdg) / "settings.json")
    for path in candidates:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        env = document.get("env") if isinstance(document, dict) else None
        if isinstance(env, dict):
            return {str(k): str(v) for k, v in env.items() if isinstance(v, str)}
    return {}


def _loopback_host(host: str) -> str:
    host = (host or "").strip()
    if not host or host in {"0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return host


# --------------------------------------------------------------------------- #
# probing
# --------------------------------------------------------------------------- #
def _http_probe(url: str, token: str, timeout: float = 1.2) -> Tuple[int, str]:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(20000).decode("utf-8", "replace")
            return int(response.status), body
    except urllib.error.HTTPError as exc:          # server answered → alive
        return int(exc.code), ""
    except (urllib.error.URLError, socket.timeout, OSError, ValueError):
        return 0, ""


def probe(base_url: str, token: str, timeout: float = 1.2) -> Tuple[bool, str, List[str]]:
    status, body = _http_probe(base_url.rstrip("/") + "/v1/models", token, timeout)
    if status in (200, 401, 403):
        pass
    elif status == 0:
        status, _ = _http_probe(base_url.rstrip("/") + "/admin", token, timeout)
        if status != 200:
            return False, ("no response" if status == 0 else f"http {status}"), []
        return True, f"admin ui answered http {status}", []
    else:
        return False, f"http {status}", []
    models: List[str] = []
    try:
        payload = json.loads(body or "{}")
        for item in (payload.get("data") or [])[:40]:
            if isinstance(item, dict) and item.get("id"):
                models.append(str(item["id"]))
    except (json.JSONDecodeError, AttributeError):
        pass
    return True, f"http {status}", models


def detect(config=None, use_cache: bool = True, timeout: float = 1.2) -> GatewayInfo:
    """Locate a running FCC gateway. Never raises."""
    if use_cache:
        now = time.time()
        if now - float(_cache.get("at", 0.0)) < CACHE_SECONDS and _cache.get("info"):
            return _cache["info"]  # type: ignore[return-value]

    mode = getattr(config, "gateway_mode", "auto") or "auto"
    explicit_url = (getattr(config, "gateway_url", "") or "").strip()
    explicit_token = (getattr(config, "gateway_token", "") or "").strip()
    if mode == "off" and not explicit_url:
        info = GatewayInfo(detail="disabled in settings")
        _cache.update(at=time.time(), info=info)
        return info

    env_values = read_dotenv(fcc_env_path())
    settings_env = read_claude_settings_env()

    token = explicit_token
    token_source = "config" if token else ""
    if not token:
        token = env_values.get("ANTHROPIC_AUTH_TOKEN", "")
        token_source = "env-file" if token else ""
    if not token:
        token = settings_env.get("ANTHROPIC_AUTH_TOKEN", "")
        token_source = "settings" if token else ""
    if not token:
        token = DEFAULT_TOKEN
        token_source = "default"

    ports: List[int] = []
    for raw in (explicit_url, env_values.get("PORT", ""), settings_env.get("ANTHROPIC_BASE_URL", "")):
        if not raw:
            continue
        try:
            port = int(str(raw).rstrip("/").split(":")[-1])
            if 0 < port < 65536 and port not in ports:
                ports.append(port)
        except (ValueError, TypeError):
            pass
    for port in (DEFAULT_PORT, *FALLBACK_PORTS):
        if port not in ports:
            ports.append(port)

    if explicit_url:
        base = explicit_url.rstrip("/")
        alive, detail, models = probe(base, token, timeout)
        info = GatewayInfo(detected=alive, base_url=base, admin_url=base + "/admin",
                           port=int(base.split(":")[-1]) if ":" in base.split("//")[-1] else 0,
                           token=token, token_source=token_source,
                           source="config", detail=detail, models=models)
        _cache.update(at=time.time(), info=info)
        return info

    host = _loopback_host(env_values.get("HOST", ""))
    best = GatewayInfo(detail="no FCC server responded")
    for port in ports[:6]:
        base = f"http://{host}:{port}"
        alive, detail, models = probe(base, token, timeout)
        if alive:
            best = GatewayInfo(detected=True, base_url=base, admin_url=base + "/admin",
                               port=port, token=token, token_source=token_source,
                               source="env-file" if port == int(env_values.get("PORT") or -1)
                               else ("settings" if port in ports[2:3] else "probe"),
                               detail=detail, models=models)
            break
        best.detail = detail or best.detail
    if not best.detected and settings_env.get("ANTHROPIC_BASE_URL"):
        base = settings_env["ANTHROPIC_BASE_URL"].rstrip("/")
        alive, detail, models = probe(base, settings_env.get("ANTHROPIC_AUTH_TOKEN", token), timeout)
        if alive:
            best = GatewayInfo(detected=True, base_url=base, admin_url=base + "/admin",
                               port=int(base.split(":")[-1]) if base.split(":")[-1].isdigit() else 0,
                               token=settings_env.get("ANTHROPIC_AUTH_TOKEN", token),
                               token_source="settings", source="settings",
                               detail=detail, models=models)
    _cache.update(at=time.time(), info=best)
    return best


def invalidate_cache() -> None:
    _cache.update(at=0.0, info=None)


# --------------------------------------------------------------------------- #
# environment policy (mirrors FCC's harnesses/claude.py exactly)
# --------------------------------------------------------------------------- #
CLAUDE_CODE_AUTO_COMPACT_WINDOW = "190000"


def proxy_values(info: GatewayInfo) -> Dict[str, str]:
    return {
        "ANTHROPIC_BASE_URL": info.base_url,
        "ANTHROPIC_AUTH_TOKEN": info.token,
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
        "CLAUDE_CODE_AUTO_MODE_SERVER": "0",
        "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": CLAUDE_CODE_AUTO_COMPACT_WINDOW,
        "CLAUDE_ENABLE_STREAM_WATCHDOG": "0",
        "CLAUDE_ENABLE_BYTE_WATCHDOG": "0",
        "API_FORCE_IDLE_TIMEOUT": "0",
        "API_TIMEOUT_MS": "2147483647",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_FEEDBACK_COMMAND": "1",
        "DISABLE_ERROR_REPORTING": "1",
    }


def apply_to_env(env: Dict[str, str], info: GatewayInfo) -> Dict[str, str]:
    """Merge FCC's Claude policy into `env` the same way FCC's launcher does."""
    for key in [k for k in env if k.startswith("ANTHROPIC_")]:
        env.pop(key, None)
    env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    env.update(proxy_values(info))
    return env
