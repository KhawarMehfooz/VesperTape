import asyncio
import json
import unittest

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from api.contracts import CreateJobRequest, PreviewRequest
from api.errors import install_error_handlers
from api.settings import AppSettings


async def call(app, path, method="GET", body=b""):
    messages = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1234), "server": ("test", 80),
    }
    try:
        await app(scope, receive, send)
    except RuntimeError:
        # ServerErrorMiddleware re-raises unexpected errors after sending 500.
        if not messages or messages[0]["status"] != 500:
            raise
    payload = b"".join(message.get("body", b"") for message in messages)
    return messages[0], json.loads(payload)


class ErrorTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        install_error_handlers(self.app)

        @self.app.post("/validate")
        def validate(request: CreateJobRequest):
            AppSettings(allowed_modes=("audio",)).validate_download_settings(request.settings)
            return request

        @self.app.get("/failure")
        def failure():
            raise RuntimeError("secret-password")

        @self.app.get("/http")
        def http():
            raise HTTPException(401, "secret-password", headers={"WWW-Authenticate": "Bearer"})

    def test_routing_errors_and_headers(self):
        for path, method, status, code in (
            ("/missing", "GET", 404, "not_found"),
            ("/validate", "GET", 405, "method_not_allowed"),
            ("/http", "GET", 401, "http_error"),
        ):
            with self.subTest(path=path):
                start, payload = asyncio.run(call(self.app, path, method))
                self.assertEqual(start["status"], status)
                self.assertEqual(payload["error"]["code"], code)
                self.assertNotIn("secret-password", json.dumps(payload))
                if status == 401:
                    self.assertIn((b"www-authenticate", b"Bearer"), start["headers"])

    def test_validation_and_malformed_json_do_not_echo_input(self):
        for body in (b'{"url":"secret-password"}', b'{"secret-password":', b'{}'):
            start, payload = asyncio.run(call(self.app, "/validate", "POST", body))
            self.assertEqual(start["status"], 422)
            self.assertEqual(payload["error"]["code"], "validation_error")
            self.assertTrue(payload["error"]["details"])
            self.assertNotIn("secret-password", json.dumps(payload))

    def test_disabled_options_use_same_envelope(self):
        start, payload = asyncio.run(call(self.app, "/validate", "POST", b'{"url":"https://example.com"}'))
        self.assertEqual(start["status"], 422)
        self.assertEqual(payload["error"]["details"][0]["location"], ["body", "settings", "mode"])

    def test_internal_errors_hide_exception_text(self):
        start, payload = asyncio.run(call(self.app, "/failure"))
        self.assertEqual(start["status"], 500)
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertNotIn("secret-password", json.dumps(payload))

    def test_request_constraints(self):
        for payload in (
            {"selection": {"item_indices": [0]}},
            {"selection": {"item_indices": [True]}},
            {"selection": {"item_indices": [1, 1]}},
            {"settings": {"filename": "../escape"}},
            {"settings": {"filename": "%(title)s"}},
            {"settings": {"destination": "/tmp"}},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CreateJobRequest.model_validate({"url": "https://example.com", **payload})
        for url in ("file:///tmp/video", "https://user:secret@example.com", "https://example.com:bad", "https://exa mple.com"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                PreviewRequest(url=url)
        self.assertEqual(PreviewRequest(url=" https://example.com ").url, "https://example.com")

    def test_production_routes_and_documented_errors(self):
        from api.main import app

        start, payload = asyncio.run(call(app, "/api/missing"))
        self.assertEqual(start["status"], 404)
        self.assertEqual(payload["error"]["code"], "not_found")
        start, payload = asyncio.run(call(app, "/api/health"))
        self.assertEqual(start["status"], 200)
        self.assertEqual(payload, {"status": "ok"})
        schema = app.openapi()
        self.assertEqual(
            schema["paths"]["/api/settings"]["get"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/ErrorResponse",
        )
