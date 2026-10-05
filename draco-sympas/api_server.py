#!/usr/bin/env python3
"""Small dependency-free HTTP API for demonstrating the slice adapter."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "adapter"))
from python_slice import slice_source, token_fallback  # noqa: E402
from review import review_source  # noqa: E402
from diff_review import review_diff  # noqa: E402

UI = Path(__file__).parent / "ui" / "index.html"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "draco-sympas"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/review-diff":
            try:
                size = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(size))
                self._send(200, review_diff(data["diff"]))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self._send(400, {"error": "expected JSON body with a string field: diff"})
            return
        if self.path == "/review":
            try:
                size = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(size))
                self._send(200, review_source(data["source"]))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self._send(400, {"error": "expected JSON body with a string field: source"})
            return
        if self.path != "/slice":
            self._send(404, {"error": "not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(size))
            source = data["source"]
            try:
                lines, frontier = slice_source(source)
                method = "ast"
            except (SyntaxError, AttributeError, ValueError, TypeError):
                lines, frontier = token_fallback(source)
                method = "token_fallback"
            self._send(200, {"method": method, "slice_lines": lines, "frontier": frontier})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._send(400, {"error": "expected JSON body with a string field: source"})

    def log_message(self, *_args):
        return


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"draco-sympas API listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
