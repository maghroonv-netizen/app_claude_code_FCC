"""FCC (free-claude-code) gateway detection + environment bridging."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from fcc.claude import gateway


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    token_expected = "freecc"

    def log_message(self, *args):
        pass

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if self.path == "/v1/models":
            if auth != f"Bearer {self.token_expected}":
                self.send_response(401)
                self.send_header("content-length", "0")
                self.end_headers()
                return
            body = json.dumps({"data": [{"id": "grok-2"}, {"id": "glm-4.5"}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/admin":
            body = b"<html>admin</html>"
            self.send_response(200)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("content-length", "0")
            self.end_headers()


@pytest.fixture()
def fcc_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def fresh_cache():
    gateway.invalidate_cache()
    yield
    gateway.invalidate_cache()


class Cfg:
    gateway_mode = "auto"
    gateway_url = ""
    gateway_token = ""


def test_probe_detects_server_and_models(fcc_server):
    alive, detail, models = gateway.probe(fcc_server, "freecc")
    assert alive and detail == "http 200"
    assert models == ["grok-2", "glm-4.5"]


def test_probe_wrong_token_still_alive(fcc_server):
    alive, _, _ = gateway.probe(fcc_server, "nope")
    assert alive  # 401 means the gateway exists, the token is just wrong


def test_probe_random_http_server_is_not_fcc():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        alive, _, _ = gateway.probe(f"http://127.0.0.1:{port}", "freecc")
        assert alive  # has /v1/models → treated as gateway
    finally:
        server.shutdown()
    # a server without /v1/models and without /admin must not count
    class Plain(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.send_header("content-length", "0")
            self.end_headers()

    plain = ThreadingHTTPServer(("127.0.0.1", 0), Plain)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    try:
        alive, _, _ = gateway.probe(f"http://127.0.0.1:{plain.server_address[1]}", "freecc")
        assert not alive
    finally:
        plain.shutdown()


def test_detect_with_explicit_url(fcc_server, monkeypatch):
    monkeypatch.setattr(gateway, "fcc_env_path", lambda: __import__("pathlib").Path("/nonexistent/.env"))
    config = Cfg()
    config.gateway_url = fcc_server
    info = gateway.detect(config, use_cache=False)
    assert info.detected
    assert info.base_url == fcc_server
    assert info.admin_url == fcc_server + "/admin"
    assert info.models


def test_detect_reads_fcc_env_file(fcc_server, tmp_path, monkeypatch):
    env_dir = tmp_path / ".fcc"
    env_dir.mkdir()
    (env_dir / ".env").write_text(
        f"PORT={fcc_server.rsplit(':', 1)[1]}\nHOST=0.0.0.0\nANTHROPIC_AUTH_TOKEN=freecc\n",
        encoding="utf-8")
    monkeypatch.setattr(gateway, "fcc_env_path", lambda: env_dir / ".env")
    monkeypatch.setattr(gateway, "read_claude_settings_env", lambda: {})
    info = gateway.detect(Cfg(), use_cache=False)
    assert info.detected
    assert info.token_source == "env-file"
    assert info.port == int(fcc_server.rsplit(":", 1)[1])


def test_detect_reads_claude_settings_env(fcc_server, tmp_path, monkeypatch):
    config_dir = tmp_path / "claudeconf"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps(
        {"env": {"ANTHROPIC_BASE_URL": fcc_server, "ANTHROPIC_AUTH_TOKEN": "freecc"}}),
        encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(gateway, "fcc_env_path", lambda: tmp_path / "nope" / ".env")
    info = gateway.detect(Cfg(), use_cache=False)
    assert info.detected
    assert info.source == "settings" or info.token_source == "settings"


def test_detect_off_mode(fcc_server):
    config = Cfg()
    config.gateway_mode = "off"
    info = gateway.detect(config, use_cache=False)
    assert not info.detected


def test_apply_to_env_matches_fcc_policy(fcc_server):
    info = gateway.GatewayInfo(detected=True, base_url=fcc_server, token="freecc")
    env = {"ANTHROPIC_API_KEY": "sk-old", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
           "PATH": "/bin"}
    gateway.apply_to_env(env, info)
    assert env["ANTHROPIC_BASE_URL"] == fcc_server
    assert env["ANTHROPIC_AUTH_TOKEN"] == "freecc"
    assert "ANTHROPIC_API_KEY" not in env
    assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" not in env
    assert env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"
    assert env["API_TIMEOUT_MS"] == "2147483647"
    assert env["PATH"] == "/bin"


def test_dotenv_parser(tmp_path):
    path = tmp_path / ".env"
    path.write_text('# comment\nPORT=8082\nHOST="0.0.0.0"\n\nBROKEN\nX = y \n', encoding="utf-8")
    values = gateway.read_dotenv(path)
    assert values == {"PORT": "8082", "HOST": "0.0.0.0", "X": "y"}
