"""Rolling monitor for registrar ``Website_Error`` spikes.

Live registrar portals change their markup/APIs without notice. The one symptom
that is always safe to act on is a *sudden run of Website_Error results*: the
live parsers deliberately degrade every unexpected page shape to
``Website_Error`` (never to a fabricated "Allotted"/"Not Allotted"), so a spike
here means "a portal changed and checks are now silently failing".

The monitor keeps a sliding window of the last N seconds. When the error count
crosses the threshold it emits a CRITICAL log line and, if ``ALERT_WEBHOOK_URL``
is set, POSTs a one-line message to a Slack/Discord incoming-webhook URL. The
cooldown prevents one bad hour from spamming the channel.

Configure via env (all optional):

- ``WEBSITE_ERROR_WINDOW_SECONDS``        (default 300)
- ``WEBSITE_ERROR_THRESHOLD``             (default 10)
- ``WEBSITE_ERROR_ALERT_COOLDOWN_SECONDS`` (default 1800)
- ``ALERT_WEBHOOK_URL``                   (default: none — log-only)
"""

import json
import logging
import os
import threading
import time
import urllib.request
from collections import deque

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


class WebsiteErrorMonitor:
    def __init__(self):
        self._window_seconds = _env_int("WEBSITE_ERROR_WINDOW_SECONDS", 300)
        self._threshold = _env_int("WEBSITE_ERROR_THRESHOLD", 10)
        self._alert_cooldown = _env_int("WEBSITE_ERROR_ALERT_COOLDOWN_SECONDS", 1800)
        self._webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
        self._lock = threading.Lock()
        self._events = deque()  # (timestamp, registrar_id)
        self._last_alert_at = 0.0

    def record(self, registrar_id: int) -> None:
        now = time.time()
        with self._lock:
            self._events.append((now, registrar_id))
            self._prune(now)
            if len(self._events) >= self._threshold:
                self._trigger_alert(len(self._events), registrar_id)

    def snapshot(self) -> dict:
        with self._lock:
            self._prune(time.time())
            return {
                "window_seconds": self._window_seconds,
                "error_count": len(self._events),
                "threshold": self._threshold,
            }

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._events and self._events[0][0] <= cutoff:
            self._events.popleft()

    def _trigger_alert(self, count: int, registrar_id: int) -> None:
        now = time.time()
        if now - self._last_alert_at < self._alert_cooldown:
            return
        self._last_alert_at = now

        message = (
            f"Website_Error spike: {count} scraper errors in the last "
            f"{self._window_seconds}s (last registrar_id={registrar_id})."
        )
        logger.critical(
            message,
            extra={"alert": "website_error_spike", "error_count": count, "registrar_id": registrar_id},
        )

        if self._webhook_url:
            threading.Thread(target=self._post_webhook, args=(message,), daemon=True).start()

    def _post_webhook(self, message: str) -> None:
        payload = json.dumps({"text": message}).encode("utf-8")
        request = urllib.request.Request(
            self._webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
        except Exception as exc:  # noqa: BLE001 - alerting must never crash a check
            logger.warning("Failed to post alert webhook: %s", exc)


website_error_monitor = WebsiteErrorMonitor()
