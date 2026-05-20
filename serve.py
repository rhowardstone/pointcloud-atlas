"""Dev server for pointcloud-atlas.

  GET /            -> engine/index.html
  GET /data/<f>    -> <example>/data/<f>   (query string ignored)

Usage: python3 serve.py [example_dir] [port]
  example_dir defaults to examples/singlecell
"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
INDEX = HERE / "engine" / "index.html"
EXAMPLE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "examples" / "singlecell"
DATA = EXAMPLE / "data"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8770
CT = {".json": "application/json", ".bin": "application/octet-stream",
      ".gz": "application/gzip", ".html": "text/html; charset=utf-8",
      ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._send(INDEX, CT[".html"])
        if p.startswith("/data/"):
            f = DATA / p[len("/data/"):]
            if f.is_file():
                return self._send(f, CT.get(f.suffix, "application/octet-stream"))
        self.send_error(404)

    def _send(self, f, ctype):
        b = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)


if __name__ == "__main__":
    print(f"serving http://127.0.0.1:{PORT}/  (data: {DATA})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
