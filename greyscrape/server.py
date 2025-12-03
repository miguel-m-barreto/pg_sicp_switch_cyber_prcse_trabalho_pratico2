# greyscrape/server.py
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from scrapers import run_scraper

class ScrapeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        # Healthcheck
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        # /scrape?store=auchan&query=...
        if parsed.path == "/scrape":
            params = parse_qs(parsed.query)
            store = params.get("store", [""])[0].strip().lower()
            # query pode ser vazia -> landing page
            query = params.get("query", [""])[0]

            if not store:
                self._send_json(
                    400, {"error": "Missing 'store' in query parameters."}
                )
                return

            try:
                items = run_scraper(store, query)

                self._send_json(
                    200,
                    {
                        "store": store,
                        "query": query,
                        "count": len(items),
                        "items": items,
                    },
                )

            except ValueError as exc:
                # store não suportada
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:
                traceback.print_exc()
                self._send_json(
                    500,
                    {
                        "error": "Scrape failed.",
                        "details": str(exc),
                    },
                )
            return

        # 404 para o resto
        self._send_json(404, {"error": "Not found"})


def run(host: str = "0.0.0.0", port: int = 8000):
    server = ThreadingHTTPServer((host, port), ScrapeHandler)
    print(f"[*] HTTP server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down server...")
        server.server_close()


if __name__ == "__main__":
    run()
