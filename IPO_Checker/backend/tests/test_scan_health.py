"""Tests for per-registrar scan health.

The gap this closes: the registrar dropdown scan only acts on portals it read
*conclusively*, so a portal whose DOM has changed stops publishing and stops
retiring — silently. No exception reaches the logs, ``/health`` stays green, and
the dropdown freezes with dead IPOs in it.

``plan_scan_health`` is pure, so the decision is testable without a database or
a browser. The DB writer and ``snapshot()`` are thin wrappers over it.
"""

import pytest

from ipo_sync.scan_health import (
    SCAN_FAILURE_ALERT_THRESHOLD,
    ScanHealthUpdate,
    plan_scan_health,
)

# Two registrars, so a healthy one can be checked not to mask a failing one.
SCAN_OK = {
    "rows": [{"name": "Alpha Ltd"}],
    "live_names": {"KFin Technologies": ["Alpha Ltd", "Beta Ltd"]},
    "conclusive": ["KFin Technologies"],
    "failed": {},
}

SCAN_KFIN_BROKEN = {
    "rows": [],
    "live_names": {},
    "conclusive": [],
    "failed": {"KFin Technologies": "Timeout 30000ms exceeded"},
}


def _by_name(updates):
    return {u.registrar_name: u for u in updates}


def test_conclusive_read_is_healthy_and_reports_its_name_count():
    updates = plan_scan_health(SCAN_OK)

    assert len(updates) == 1
    assert updates[0] == ScanHealthUpdate(
        registrar_name="KFin Technologies",
        conclusive=True,
        live_name_count=2,
        error=None,
        consecutive_failures=0,
        alerting=False,
    )


def test_first_failure_counts_as_one():
    updates = plan_scan_health(SCAN_KFIN_BROKEN)

    assert updates[0].conclusive is False
    assert updates[0].consecutive_failures == 1
    assert updates[0].error == "Timeout 30000ms exceeded"
    assert updates[0].alerting is False


def test_failures_accumulate_across_scans():
    previous = {"KFin Technologies": 1}

    updates = plan_scan_health(SCAN_KFIN_BROKEN, previous)

    assert updates[0].consecutive_failures == 2


def test_alert_fires_at_the_threshold_not_before():
    previous = {"KFin Technologies": SCAN_FAILURE_ALERT_THRESHOLD - 1}

    updates = plan_scan_health(SCAN_KFIN_BROKEN, previous)

    assert updates[0].consecutive_failures == SCAN_FAILURE_ALERT_THRESHOLD
    assert updates[0].alerting is True


def test_a_successful_scan_resets_the_counter():
    """Otherwise one bad night would contribute to an alert months later."""
    previous = {"KFin Technologies": 99}

    updates = plan_scan_health(SCAN_OK, previous)

    assert updates[0].consecutive_failures == 0
    assert updates[0].alerting is False
    assert updates[0].error is None


def test_registrar_absent_from_the_scan_is_left_untouched():
    """A portal the run never reached was not attempted — not a failure."""
    scan = {
        "live_names": {"KFin Technologies": ["Alpha Ltd"]},
        "conclusive": ["KFin Technologies"],
        "failed": {},
    }

    updates = plan_scan_health(scan, {"Bigshare Services": 2})

    assert list(_by_name(updates)) == ["KFin Technologies"]


def test_a_failing_portal_is_not_masked_by_a_healthy_one():
    scan = {
        "live_names": {"KFin Technologies": ["Alpha Ltd"]},
        "conclusive": ["KFin Technologies"],
        "failed": {"Bigshare Services": "no options returned"},
    }

    updates = _by_name(plan_scan_health(scan))

    assert updates["KFin Technologies"].conclusive is True
    assert updates["Bigshare Services"].conclusive is False
    assert updates["Bigshare Services"].error == "no options returned"


def test_updates_come_back_in_a_stable_order():
    scan = {
        "live_names": {"Zeta Registrar": ["Alpha Ltd"]},
        "conclusive": ["Zeta Registrar"],
        "failed": {"Alpha Registrar": "boom"},
    }

    names = [u.registrar_name for u in plan_scan_health(scan)]

    assert names == sorted(names)


@pytest.mark.parametrize("scan", [None, {}, {"conclusive": [], "failed": {}}])
def test_an_empty_or_missing_scan_produces_no_updates(scan):
    assert plan_scan_health(scan) == []


def test_a_missing_failed_scan_error_string_is_tolerated():
    """A registrar can be listed as failed with no message; that must not raise."""
    updates = plan_scan_health({"conclusive": [], "failed": {"KFin Technologies": None}})

    assert updates[0].consecutive_failures == 1
    assert updates[0].error is None
