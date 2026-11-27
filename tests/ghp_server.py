"""A small local web server that behaves like GitHub Pages for the tests:
serves the repo folder, answers any missing path with /404.html and status 404, and serves
.webmanifest / .json / .woff2 with the right types. Bind to "localhost" so the service worker can register.

Run by hand:  python3 tests/ghp_server.py [port]
"""
import functools, http.server, os, pathlib, socketserver, sys, threading

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".webmanifest": "application/manifest+json", ".json": "application/json",
                      ".woff": "font/woff", ".woff2": "font/woff2", ".js": "text/javascript", ".txt": "text/plain"}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (ROOT / "404.html").exists():
            body = (ROOT / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start(port=0):
    """Start in a background thread; returns (server, base_url)."""
    srv = Server(("localhost", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://localhost:%d/" % srv.server_address[1]


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv, url = start(port)
    print("serving", ROOT, "at", url, flush=True)
    threading.Event().wait()
