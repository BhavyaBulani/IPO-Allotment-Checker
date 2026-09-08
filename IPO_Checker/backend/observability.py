"""Structured JSON logging and a request-ID access-log middleware.

Two goals, both aimed at Render's log stream:

- Every application log line is a single JSON object, so it can be searched and
  filtered by field (``level``, ``request_id``, ``path``, ``alert``, ...).
- Every HTTP request gets a stable ``request_id`` — reused from the incoming
  ``X-Request-ID`` header or generated — that is echoed back to the client and
  attached to every log line emitted while that request is being handled. That
  makes a slow or failing request traceable from the browser console straight
  to the backend log line.
"""

import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone

request_id_var = contextvars.ContextVar("request_id", default=None)

# Structured fields we deliberately surface when present on a LogRecord.
_EXTRA_KEYS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "alert",
    "error_count",
    "registrar_id",
)


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON line with a fixed, predictable shape."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        # Fall back to the context-local request id when the record did not
        # pass one explicitly via ``extra``.
        request_id = request_id_var.get()
        if request_id and "request_id" not in payload:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Route all application logging through the JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


class RequestContextMiddleware:
    """Pure-ASGI middleware: request id, structured access log, timing.

    Implemented directly against the ASGI interface (rather than
    ``BaseHTTPMiddleware``) so it plays safely with the app's streaming
    responses (the xlsx export) and background tasks.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header_value(scope, b"x-request-id") or uuid.uuid4().hex[:16]
        method = scope.get("method")
        path = scope.get("path")
        status_code = 500
        start = time.perf_counter()
        token = request_id_var.set(request_id)

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        access_logger = logging.getLogger("access")

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            access_logger.error(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
                exc_info=True,
            )
            raise
        finally:
            request_id_var.reset(token)

        access_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )


def _header_value(scope, target: bytes):
    for name, value in scope.get("headers", []):
        if name == target:
            return value.decode("latin-1")
    return None
