"""Tests for automatic retirement of IPOs dropped by their registrar.

The rule under test: any IPO currently offered as checkable (validated=True +
Allotment Announced) must stop being checkable once its registrar removes it
from that dropdown — but only when the dropdown was *conclusively read*, and
only after repeated confirmation, so that one broken scrape can never empty
the client-facing list.

`plan_retirement` is pure, so the whole rule is testable without a database. The
one test that exercises the DB apply layer skips itself unless
``TEST_DATABASE_URL`` is set, matching the rest of the suite.
"""

import pytest

from ipo_sync.retire import (
    ABSENT,
    INCONCLUSIVE,
    RETIRED,
    RETIRE_AFTER_SCANS,
    STILL_LIVE,
    RetireCandidate,
    plan_retirement,
)

PORTAL = "KFin Technologies"


def _verdict(name, registrar, absent_scan_count, live_names, conclusive, **kwargs):
    verdicts = plan_retirement(
        [RetireCandidate(name=name, registrar_name=registrar, absent_scan_count=absent_scan_count)],
        {PORTAL: live_names},
        conclusive,
        **kwargs,
    )
    assert len(verdicts) == 1
    return verdicts[0]


# ---------------------------------------------------------------------------
# Still listed -> stays checkable
# ---------------------------------------------------------------------------

def test_still_listed_is_not_retired_and_counter_resets():
    verdict = _verdict("Acme Ltd", PORTAL, 1, ["Acme Limited"], {PORTAL})
    assert verdict.outcome == STILL_LIVE
    assert verdict.absent_scan_count == 0


def test_name_matching_ignores_legal_suffixes_and_casing():
    # The exact spelling drift the promotion path already tolerates must not
    # make the retirement path think a live IPO vanished.
    verdict = _verdict(
        "Fly-Hi Maritime Travels Limited - SME",
        "Bigshare Services",
        0,
        ["FLY HI MARITIME TRAVELS"],
        {"Bigshare Services"},
    )
    assert verdict.outcome == STILL_LIVE


def test_listed_on_another_registrar_portal_stays_checkable():
    # A wrong registrar_id is a routing problem, not evidence the IPO is gone.
    verdict = _verdict("Acme Ltd", "Bigshare Services", 5, ["Acme Ltd"], {PORTAL})
    assert verdict.outcome == STILL_LIVE
    assert verdict.absent_scan_count == 0


# ---------------------------------------------------------------------------
# Absent -> two strikes, never one
# ---------------------------------------------------------------------------

def test_first_absence_records_a_strike_without_retiring():
    verdict = _verdict("Gone Ltd", PORTAL, 0, ["Other Ltd"], {PORTAL})
    assert verdict.outcome == ABSENT
    assert verdict.absent_scan_count == 1


def test_second_consecutive_absence_retires():
    verdict = _verdict("Gone Ltd", PORTAL, 1, ["Other Ltd"], {PORTAL})
    assert verdict.outcome == RETIRED
    assert verdict.absent_scan_count == RETIRE_AFTER_SCANS


def test_retirement_threshold_is_configurable():
    verdict = _verdict("Gone Ltd", PORTAL, 0, ["Other Ltd"], {PORTAL}, retire_after=1)
    assert verdict.outcome == RETIRED


def test_a_single_bad_scan_cannot_retire_anything():
    # The whole live list came back empty for this registrar, so nothing was
    # conclusively read: no candidate may be retired, however high its counter.
    verdicts = plan_retirement(
        [
            RetireCandidate("A Ltd", PORTAL, 9),
            RetireCandidate("B Ltd", PORTAL, 9),
        ],
        {},
        set(),
    )
    assert [v.outcome for v in verdicts] == [INCONCLUSIVE, INCONCLUSIVE]
    assert [v.absent_scan_count for v in verdicts] == [9, 9]  # not even a strike


def test_unread_registrar_leaves_counter_untouched():
    verdict = _verdict("Gone Ltd", PORTAL, 1, ["Other Ltd"], set())
    assert verdict.outcome == INCONCLUSIVE
    assert verdict.absent_scan_count == 1


def test_ipo_with_no_registrar_is_never_retired():
    verdict = _verdict("Gone Ltd", None, 0, ["Other Ltd"], {PORTAL})
    assert verdict.outcome == INCONCLUSIVE


def test_unusable_name_is_inconclusive():
    verdict = _verdict("   ", PORTAL, 0, ["Other Ltd"], {PORTAL})
    assert verdict.outcome == INCONCLUSIVE


# ---------------------------------------------------------------------------
# Contract with the caller
# ---------------------------------------------------------------------------

def test_one_verdict_per_candidate_in_original_order():
    candidates = [
        RetireCandidate("A Ltd", PORTAL, 0),
        RetireCandidate("B Ltd", PORTAL, 1),
        RetireCandidate("C Ltd", None, 0),
        RetireCandidate("Z Ltd", PORTAL, 4),
    ]
    verdicts = plan_retirement(candidates, {PORTAL: ["Z Ltd"]}, {PORTAL})
    assert len(verdicts) == len(candidates)
    assert [v.outcome for v in verdicts] == [ABSENT, RETIRED, INCONCLUSIVE, STILL_LIVE]


def test_no_candidates_is_a_no_op():
    assert plan_retirement([], {PORTAL: ["Acme Ltd"]}, {PORTAL}) == []


# ---------------------------------------------------------------------------
# DB apply layer (needs a real MySQL; skipped without TEST_DATABASE_URL)
# ---------------------------------------------------------------------------

def test_retire_hides_the_row_without_deleting_it(db_session):
    from db.models import EndpointType, IPO, IPOStatus, Registrar
    from ipo_sync.auto_detect import _retire_stale_dropdown_ipos

    registrar = Registrar(
        name=PORTAL,
        priority=1,
        endpoint_type=EndpointType.browser_automation,
        active=True,
    )
    db_session.add(registrar)
    db_session.flush()

    ipo = IPO(
        external_id="drop-1",
        name="Gone Ltd",
        status=IPOStatus.Allotment_Announced,
        source="NSE+registrar-dropdown",
        auto_detected=True,
        validated=True,
        registrar_id=registrar.id,
        absent_scan_count=RETIRE_AFTER_SCANS - 1,
    )
    db_session.add(ipo)
    db_session.commit()
    ipo_id = ipo.id

    summary = _retire_stale_dropdown_ipos(
        db_session, {PORTAL: ["Still Here Ltd"]}, {PORTAL}
    )
    db_session.commit()

    assert summary["retired"] == 1
    refreshed = db_session.query(IPO).filter(IPO.id == ipo_id).one()
    assert refreshed is not None, "the row must survive retirement"
    assert refreshed.validated is False
    assert refreshed.status == IPOStatus.Closed


def test_manual_upload_is_retired_when_its_registrar_drops_it(db_session):
    from db.models import EndpointType, IPO, IPOStatus, Registrar
    from ipo_sync.auto_detect import _retire_stale_dropdown_ipos

    registrar = Registrar(
        name=PORTAL,
        priority=1,
        endpoint_type=EndpointType.browser_automation,
        active=True,
    )
    db_session.add(registrar)
    db_session.flush()

    manual = IPO(
        external_id="manual-1",
        name="Curated Ltd",
        status=IPOStatus.Allotment_Announced,
        source="manual-upload",
        auto_detected=False,
        validated=True,
        registrar_id=registrar.id,
        absent_scan_count=RETIRE_AFTER_SCANS - 1,
    )
    db_session.add(manual)
    db_session.commit()

    summary = _retire_stale_dropdown_ipos(db_session, {PORTAL: ["Other Ltd"]}, {PORTAL})
    db_session.commit()

    assert summary["retired"] == 1
    refreshed = db_session.query(IPO).filter(IPO.id == manual.id).one()
    assert refreshed.validated is False
    assert refreshed.status == IPOStatus.Closed
