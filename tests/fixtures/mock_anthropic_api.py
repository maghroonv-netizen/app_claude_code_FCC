"""A tiny stand-in for the Anthropic Messages API, used by the end-to-end test.

It streams one tool call (Write) on the first turn and plain text afterwards,
which is exactly what the GUI needs in order to exercise the permission
handshake, tool cards and the final result event against the real CLI.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVER_CODE = r'''
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
TARGET = os.environ.get("FCC_MOCK_WRITE_PATH", "/tmp/fcc-e2e/note.txt")
CONTENT = os.environ.get("FCC_MOCK_WRITE_CONTENT", "hello from the e2e test")
state = {"calls": 0}


def emit(w, event, data):
    w.write(("event: %s\ndata: %s\n\n" % (event, json.dumps(data))).encode())


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"data": []}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        if "/v1/messages" not in self.path:
            payload = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        state["calls"] += 1
        has_result = "tool_result" in body
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        import io
        buffer = io.BytesIO()

        def ev(event, data):
            buffer.write(("event: %s\ndata: %s\n\n" % (event, json.dumps(data))).encode())

        call = state["calls"]
        ev("message_start", {"type": "message_start", "message": {
            "id": "msg_%d" % call, "type": "message", "role": "assistant",
            "model": "claude-sonnet-4-5", "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 1}}})
        ev("ping", {"type": "ping"})
        if not has_result:
            ev("content_block_start", {"type": "content_block_start", "index": 0,
               "content_block": {"type": "tool_use", "id": "toolu_e2e_%d" % call,
                                 "name": "Write", "input": {}}})
            pieces = ['{"file_path":"%s"' % TARGET.replace("\\", "/"),
                      ',"content":"%s"}' % CONTENT]
            for piece in pieces:
                ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                   "delta": {"type": "input_json_delta", "partial_json": piece}})
            stop_reason = "tool_use"
        else:
            ev("content_block_start", {"type": "content_block_start", "index": 0,
               "content_block": {"type": "text", "text": ""}})
            for piece in ["The file ", "is written. ", "Done."]:
                ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                   "delta": {"type": "text_delta", "text": piece}})
            stop_reason = "end_turn"
        ev("content_block_stop", {"type": "content_block_stop", "index": 0})
        ev("message_delta", {"type": "message_delta",
           "delta": {"stop_reason": stop_reason, "stop_sequence": None},
           "usage": {"output_tokens": 30}})
        ev("message_stop", {"type": "message_stop"})
        data = buffer.getvalue()
        self.wfile.write(("%X\r\n" % len(data)).encode() + data + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
'''


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(write_path: str, content: str = "hello from the e2e test"):
    """Start the mock API; returns (process, base_url)."""
    port = free_port()
    env = dict(os.environ)
    env["FCC_MOCK_WRITE_PATH"] = write_path
    env["FCC_MOCK_WRITE_CONTENT"] = content
    process = subprocess.Popen(
        [sys.executable, "-c", SERVER_CODE, str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                break
        except OSError:
            import time

            time.sleep(0.2)
    return process, f"http://127.0.0.1:{port}"


def stop_server(process) -> None:
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
