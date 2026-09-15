"""Tests for the shared IPO name key and the name_key de-duplication.

The bug these lock down: ``ipos.name`` had no uniqueness constraint, and the
name key existed as three separate implementations. The manual-upload copy did
not strip "SME", so "ASHUTOSH FIBRE LIMITED SME" keyed as "ashutosh fibre sme"
on that path and "ashutosh fibre" in the sync pipeline — two rows for one
company, both offered in the checkable dropdown.

DB-backed tests need ``TEST_DATABASE_URL``; the rest run everywhere.
"""

import pytest


# --------------------------------------------------------------------------
# The key itself
# --------------------------------------------------------------------------

def test_production_duplicate_pair_now_shares_one_key():
    """The exact pair observed in the live database must collapse to one key."""
    from ipo_sync.name_key import normalize_ipo_name

    assert normalize_ipo_name("Ashutosh Fibre") == normalize_ipo_name(
        "ASHUTOSH FIBRE LIMITED SME"
    )


@pytest.mark.parametrize("a,b", [
    ("Tempsens Instruments", "Tempsens Instruments (India) Limited"),
    ("Fly-Hi Maritime Travels", "FLY HI MARITIME TRAVELS"),
    ("Phychem Technologies", "Phychem Technologies Limited - SME"),
    ("Alpha & Beta Ltd", "Alpha and Beta Limited"),
    ("Acme Pvt. Ltd.", "ACME PRIVATE LIMITED"),
    ("  Spaced   Out  Ltd  ", "Spaced Out"),
])
def test_equivalent_spellings_share_a_key(a, b):
    from ipo_sync.name_key import normalize_ipo_name

    assert normalize_ipo_name(a) == normalize_ipo_name(b)


@pytest.mark.parametrize("a,b", [
    ("Bondada Engineering", "Bondada Engineering India"),
    ("Alpha Ltd", "Beta Ltd"),
    ("Ashutosh Fibre", "Ashutosh Fibres"),
])
def test_different_companies_keep_different_keys(a, b):
    """The normalizer must not over-fold — a false match hides a real IPO."""
    from ipo_sync.name_key import normalize_ipo_name

    assert normalize_ipo_name(a) != normalize_ipo_name(b)


@pytest.mark.parametrize("value", [None, "", "   ", "Ltd", "Limited", "Pvt Ltd"])
def test_unusable_names_yield_an_empty_key(value):
    from ipo_sync.name_key import normalize_ipo_name

    assert normalize_ipo_name(value) == ""


def test_key_never_exceeds_the_column_width():
    from ipo_sync.name_key import MAX_NAME_KEY_LENGTH, normalize_ipo_name

    assert len(normalize_ipo_name("A" * 5000)) == MAX_NAME_KEY_LENGTH


# --------------------------------------------------------------------------
# The three old copies must stay merged
# --------------------------------------------------------------------------

def test_all_call_sites_share_one_implementation():
    """Regression guard against a fourth normalizer being introduced.

    reconcile, auto_detect and the manual upload endpoint each used to carry
    their own copy; they had already diverged. Every call site must now agree.
    """
    from api.endpoints.ipos import _normalize_name as upload_key
    from ipo_sync.auto_detect import _normalize_name_for_match, _normalize_name_loose
    from ipo_sync.name_key import normalize_ipo_name
    from ipo_sync.reconcile import _normalize_name_for_match as reconcile_key

    for spelling in (
        "Ashutosh Fibre",
        "ASHUTOSH FIBRE LIMITED SME",
        "Tempsens Instruments (India) Limited",
        "Fly-Hi Maritime  Travels Ltd.",
    ):
        expected = normalize_ipo_name(spelling)
        assert upload_key(spelling) == expected
        assert reconcile_key(spelling) == expected
        assert _normalize_name_for_match(spelling) == expected
        assert _normalize_name_loose(spelling) == expected


# --------------------------------------------------------------------------
# Planning the backfill (pure)
# --------------------------------------------------------------------------

def _row(ipo_id, name, validated=False, result_count=0, status="Closed"):
    return {
        "id": ipo_id,
        "name": name,
        "validated": validated,
        "status": status,
        "result_count": result_count,
    }


def test_unique_rows_all_get_their_own_key():
    from ipo_sync.name_key_backfill import plan_name_key_backfill

    assignments, duplicates = plan_name_key_backfill([
        _row(1, "Alpha Ltd"), _row(2, "Beta Ltd"),
    ])

    assert duplicates == []
    assert assignments == {1: "alpha", 2: "beta"}


def test_colliding_rows_keep_one_and_rekey_the_other():
    from ipo_sync.name_key_backfill import DUP_KEY_MARKER, plan_name_key_backfill

    assignments, duplicates = plan_name_key_backfill([
        _row(14, "Ashutosh Fibre"),
        _row(98, "ASHUTOSH FIBRE LIMITED SME"),
    ])

    # Exactly one row keeps the real key, so the unique index can be created.
    assert sorted(k for k in assignments.values() if k == "ashutosh fibre") == ["ashutosh fibre"]
    assert len(duplicates) == 1
    loser = duplicates[0]
    assert DUP_KEY_MARKER in assignments[loser["id"]]
    assert assignments[loser["kept_id"]] == "ashutosh fibre"
    assert len(set(assignments.values())) == 2  # both keys distinct


def test_the_checkable_duplicate_is_the_one_kept():
    """A row the portal actually lists today outranks an older hidden one."""
    from ipo_sync.name_key_backfill import plan_name_key_backfill

    assignments, duplicates = plan_name_key_backfill([
        _row(14, "Ashutosh Fibre", validated=False),
        _row(98, "ASHUTOSH FIBRE LIMITED SME", validated=True),
    ])

    assert assignments[98] == "ashutosh fibre"
    assert duplicates[0]["id"] == 14


def test_row_with_most_saved_history_wins_a_tie():
    """Keeping it means the fewest foreign keys point at a hidden row."""
    from ipo_sync.name_key_backfill import plan_name_key_backfill

    assignments, duplicates = plan_name_key_backfill([
        _row(7, "Alpha Ltd", result_count=0),
        _row(9, "ALPHA LIMITED", result_count=12),
    ])

    assert assignments[9] == "alpha"
    assert duplicates[0]["id"] == 7


def test_lowest_id_wins_when_everything_else_ties():
    from ipo_sync.name_key_backfill import plan_name_key_backfill

    assignments, _ = plan_name_key_backfill([
        _row(5, "Alpha Ltd"), _row(8, "ALPHA LIMITED"),
    ])

    assert assignments[5] == "alpha"


def test_unusable_names_are_left_null_and_do_not_collide():
    from ipo_sync.name_key_backfill import plan_name_key_backfill

    assignments, duplicates = plan_name_key_backfill([
        _row(1, "Ltd"), _row(2, "   "), _row(3, "Alpha Ltd"),
    ])

    assert assignments == {1: None, 2: None, 3: "alpha"}
    assert duplicates == []


# --------------------------------------------------------------------------
# The database actually enforces it
# --------------------------------------------------------------------------

def _make_ipo(name, status=None, **kwargs):
    from db.models import IPO, IPOStatus

    return IPO(name=name, status=status or IPOStatus.Closed, **kwargs)


def test_database_rejects_two_rows_with_the_same_key(db_session):
    """The constraint, not a code path, is what makes duplicates impossible."""
    from sqlalchemy.exc import IntegrityError

    db_session.add(_make_ipo("Alpha Ltd", name_key="alpha"))
    db_session.commit()

    db_session.add(_make_ipo("ALPHA LIMITED - SME", name_key="alpha"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_rows_without_a_usable_key_may_repeat(db_session):
    """NULL keys coexist, so a few unnormalizable names never block each other."""
    db_session.add(_make_ipo("Ltd", name_key=None))
    db_session.add(_make_ipo("   ", name_key=None))
    db_session.commit()

    from db.models import IPO
    assert db_session.query(IPO).count() == 2


def test_backfill_repairs_an_existing_duplicate_pair(db_engine, db_session):
    """End-to-end on the real observed pair: one row survives, none are lost."""
    from db.models import IPO, IPOStatus
    from ipo_sync.name_key_backfill import apply_name_key_backfill, DUP_KEY_MARKER

    # Insert with NULL keys so the unique index does not reject the pair — this
    # reproduces the pre-migration state, where nothing enforced uniqueness.
    db_session.add_all([
        _make_ipo("Ashutosh Fibre", status=IPOStatus.Allotment_Announced,
                  validated=True, name_key=None),
        _make_ipo("ASHUTOSH FIBRE LIMITED SME", status=IPOStatus.Allotment_Announced,
                  validated=True, name_key=None),
    ])
    db_session.commit()

    summary = apply_name_key_backfill(db_engine)
    assert len(summary["duplicates"]) == 1

    db_session.expire_all()
    rows = db_session.query(IPO).order_by(IPO.id).all()
    assert len(rows) == 2, "backfill must never delete a row"

    published = [r for r in rows if r.validated]
    assert len(published) == 1, "exactly one row stays checkable"
    assert published[0].name_key == "ashutosh fibre"

    hidden = [r for r in rows if not r.validated]
    assert len(hidden) == 1
    assert DUP_KEY_MARKER in hidden[0].name_key
    assert hidden[0].status == IPOStatus.Closed
