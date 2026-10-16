"""Local stand-in for a Slack incoming webhook: prints each POSTed alert. For offline demos only."""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        print("=== ALERT RECEIVED ===", flush=True)
        print(json.loads(body)["text"], flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    print(f"slack sink on http://127.0.0.1:{port}/alert", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
