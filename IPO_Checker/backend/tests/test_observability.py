"""Tests for request-id middleware and the Website_Error spike monitor."""

import logging

from registrar_services.website_error_monitor import WebsiteErrorMonitor


def test_request_id_is_generated_and_echoed(app_client):
    res = app_client.get("/health")

    assert res.status_code == 200
    assert res.headers.get("x-request-id")


def test_incoming_request_id_is_preserved(app_client):
    res = app_client.get("/health", headers={"X-Request-ID": "req-123"})

    assert res.headers.get("x-request-id") == "req-123"


def test_scrapers_health_reports_monitor_snapshot(app_client):
    res = app_client.get("/health/scrapers")

    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"window_seconds", "error_count", "threshold"}


def _make_monitor(threshold=3, window=60, cooldown=0):
    monitor = WebsiteErrorMonitor()
    monitor._threshold = threshold
    monitor._window_seconds = window
    monitor._alert_cooldown = cooldown
    monitor._webhook_url = None
    return monitor


def test_monitor_counts_errors_in_window():
    monitor = _make_monitor()
    monitor.record(2)
    monitor.record(2)

    assert monitor.snapshot()["error_count"] == 2


def test_monitor_threshold_emits_critical_log(caplog):
    monitor = _make_monitor(threshold=2)

    with caplog.at_level(logging.CRITICAL, logger="registrar_services.website_error_monitor"):
        monitor.record(2)
        monitor.record(3)

    criticals = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(criticals) == 1
    assert "Website_Error spike" in criticals[0].message


def test_monitor_alert_respects_cooldown(caplog):
    monitor = _make_monitor(threshold=2, cooldown=3600)

    with caplog.at_level(logging.CRITICAL, logger="registrar_services.website_error_monitor"):
        monitor.record(2)  # crosses threshold -> alert
        monitor.record(3)  # still within cooldown -> no second alert

    criticals = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(criticals) == 1
