# server.py
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from scrapers.auchan import scrape_auchan
#from scrapers.froiz import scrape_froiz...


class ScrapeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data):
        """Send a JSON response with given status code."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # CORS básico para poderes chamar isto do Next.js
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        # Healthcheck simples
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        # Endpoint principal: /scrape?store=auchan&query=leite
        if parsed.path == "/scrape":
            params = parse_qs(parsed.query)
            store = params.get("store", [""])[0].strip().lower()
            query = params.get("query", [""])[0].strip()

            if not store or not query:
                self._send_json(
                    400, {"error": "Missing 'store' or 'query' in query parameters."}
                )
                return

            try:
                if store == "auchan":
                    items = scrape_auchan(query)
                # elif store == "froiz":
                #     items = scrape_froiz(query)
                # elif store == "pingo_doce":
                #     items = scrape_pingo_doce(query)
                else:
                    self._send_json(400, {"error": f"Unsupported store '{store}'."})
                    return

                self._send_json(
                    200,
                    {
                        "store": store,
                        "query": query,
                        "count": len(items),
                        "items": items,
                    },
                )

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

        # Qualquer outra rota -> 404
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
