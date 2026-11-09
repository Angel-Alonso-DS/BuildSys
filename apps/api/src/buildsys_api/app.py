"""Dependency-free HTTP API for the BuildSys demo."""
from __future__ import annotations
import json
import re
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import environ
from .service import BuildSysService

class ApiHandler(BaseHTTPRequestHandler):
    service = None
    def allowed_origin(self):
        origin = self.headers.get("Origin")
        configured = {item.strip() for item in environ.get("BUILDSYS_ALLOWED_ORIGINS", "").split(",") if item.strip()}
        return origin if origin and origin in configured else None
    def _service(self):
        if self.service is None: raise RuntimeError("API service has not been configured")
        return self.service
    def _json(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        origin = self.allowed_origin()
        if origin: self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(encoded)
    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000: raise ValueError("request body is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict): raise ValueError("request body must be a JSON object")
        return value
    @staticmethod
    def required(value, name):
        if not isinstance(value, str) or not value.strip(): raise ValueError(f"{name} must be a non-empty string")
        return value.strip()
    def do_OPTIONS(self):
        origin = self.allowed_origin()
        if not origin: self._json(HTTPStatus.FORBIDDEN, {"error":"origin_not_allowed"}); return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_GET(self):
        if self.path == "/health": self._json(HTTPStatus.OK, {"status":"ok"})
        elif self.path == "/knowledge": self._json(HTTPStatus.OK, {"items":self._service().knowledge()})
        else: self._json(HTTPStatus.NOT_FOUND, {"error":"not_found"})
    def do_POST(self):
        try:
            body = self._body()
            if self.path == "/learning/duplicate-event":
                learned = self._service().learn_from_duplicate(self.required(body.get("source_system","orders"), "source_system"))
                self._json(HTTPStatus.CREATED, asdict(learned)); return
            match = re.fullmatch(r"/systems/([A-Za-z0-9_-]+)/(build|events)", self.path)
            if not match: self._json(HTTPStatus.NOT_FOUND, {"error":"not_found"}); return
            system_name, action = match.groups()
            if action == "build": self._json(HTTPStatus.CREATED, self._service().build_system(system_name)); return
            result, created = self._service().receive_event(system_name, self.required(body.get("request_id"),"request_id"), json.dumps(body.get("payload",{})))
            self._json(HTTPStatus.CREATED if created else HTTPStatus.OK, result)
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
    def log_message(self, *_): return

def main():
    port = int(environ.get("PORT","8000"))
    ApiHandler.service = BuildSysService(environ.get("BUILDSYS_DATABASE","buildsys.db"))
    print(f"BuildSys API listening on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("0.0.0.0",port),ApiHandler).serve_forever()
if __name__ == "__main__": main()
