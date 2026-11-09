"""Dependency-free HTTP API; deploy with python -m buildsys_api.app."""
from __future__ import annotations
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import environ
from .service import BuildSysService

class ApiHandler(BaseHTTPRequestHandler):
    service = BuildSysService(environ.get("BUILDSYS_DATABASE", "buildsys.db"))
    def _json(self, status: HTTPStatus, body: object) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
    def _body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")
    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
        elif self.path == "/knowledge":
            self._json(HTTPStatus.OK, {"items": self.service.knowledge()})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
    def do_POST(self) -> None:
        try:
            body = self._body()
            if self.path == "/learning/duplicate-event":
                learned = self.service.learn_from_duplicate(str(body.get("source_system", "orders")))
                self._json(HTTPStatus.CREATED, asdict(learned))
            elif self.path.startswith("/systems/") and self.path.endswith("/build"):
                self._json(HTTPStatus.CREATED, self.service.build_system(self.path.split("/")[2]))
            elif self.path.startswith("/systems/") and self.path.endswith("/events"):
                result, created = self.service.receive_event(
                    self.path.split("/")[2], str(body.get("request_id", "")), json.dumps(body.get("payload", {})))
                self._json(HTTPStatus.CREATED if created else HTTPStatus.OK, result)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
    def log_message(self, *_: object) -> None:
        return

def main() -> None:
    port = int(environ.get("PORT", "8000"))
    print(f"BuildSys API listening on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), ApiHandler).serve_forever()
if __name__ == "__main__":
    main()
