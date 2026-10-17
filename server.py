from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parent


class SiteHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        return super().do_GET()


handler = partial(SiteHandler, directory=str(ROOT / "public"))
port = int(os.environ.get("PORT", "10000"))
server = ThreadingHTTPServer(("0.0.0.0", port), handler)
print(f"Telegram Team Finder site listening on port {port}", flush=True)
server.serve_forever()
