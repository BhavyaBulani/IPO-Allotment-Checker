"""
Backfill and de-duplicate ``ipos.name_key``.

Needed because the column arrives *after* the rows do: production already holds
IPO rows created before ``name_key`` existed, including at least one genuine
duplicate pair. A unique index cannot be created while those duplicates share a
key, so they have to be resolved first.

Two callers, one implementation:

  * alembic/versions/d7f3a1c8b04e_add_name_key_to_ipos.py — the migration path
  * main.py ``_ensure_ipo_name_key_column()`` — services deployed with a bare
    ``uvicorn`` start command that never run migrations

Keeping the repair in one place is deliberate. The alternative (inlining the
logic in the migration, as migrations normally should) would mean two copies of
a de-duplication rule that must agree exactly, and a mismatch between them is
precisely the kind of silent divergence that produced the duplicates.

The plan/apply split mirrors ``ipo_sync/retire.py`` so the interesting part —
which row survives a collision — is a pure function testable without a database.

Rows are never deleted. ``allotment_results.ipo_id`` references ``ipos.id``, so
deleting a duplicate would destroy real check history. The losing row is instead
hidden (``validated=False``, status ``Closed``) and given a synthetic
non-colliding key, so it disappears from the checkable dropdown while both its
history and the fact that it existed remain visible in ``/api/ipos/admin``.
"""

import logging

logger = logging.getLogger(__name__)

# Separator for a losing duplicate's synthetic key. Deliberately contains
# characters normalize_ipo_name() can never emit (it lowercases, collapses runs
# of whitespace, and never produces "~"), so a synthetic key cannot collide with
# a real one.
DUP_KEY_MARKER = "~dup~"


def _keep_rank(row: dict) -> tuple:
    """Sort key picking the duplicate worth keeping. Highest wins.

    1. A row that is currently checkable (validated + Allotment Announced) —
       it is the one the registrar's portal actually lists today.
    2. More saved allotment_results — keeps the row the most history hangs off,
       so the fewest foreign keys end up pointing at a hidden row.
    3. Lowest id — the older row, as a deterministic final tie-break.
    """
    return (
        bool(row.get("validated")),
        int(row.get("result_count") or 0),
        -int(row["id"]),
    )


def plan_name_key_backfill(rows: list[dict]) -> tuple[dict[int, str | None], list[dict]]:
    """Return ``({ipo_id: name_key}, duplicates)`` — pure, no I/O.

    Every input row gets an entry: its true key, a synthetic
    ``<key>~dup~<id>`` key when it lost a collision, or ``None`` when its name
    yields no usable key at all (both MySQL and SQLite allow repeated NULLs in a
    unique index, so several unusable names coexist safely).

    Each row dict needs: ``id``, ``name``, ``validated`` (bool-ish),
    ``status`` (str) and ``result_count`` (int).
    """
    from ipo_sync.name_key import normalize_ipo_name

    grouped: dict[str, list[dict]] = {}
    assignments: dict[int, str | None] = {}
    for row in rows:
        key = normalize_ipo_name(row.get("name"))
        if not key:
            assignments[row["id"]] = None
            continue
        grouped.setdefault(key, []).append(row)

    duplicates: list[dict] = []
    for key, group in grouped.items():
        if len(group) == 1:
            assignments[group[0]["id"]] = key
            continue

        keeper = max(group, key=_keep_rank)
        assignments[keeper["id"]] = key
        for row in group:
            if row["id"] == keeper["id"]:
                continue
            assignments[row["id"]] = f"{key}{DUP_KEY_MARKER}{row['id']}"
            duplicates.append({
                "id": row["id"],
                "name": row.get("name"),
                "key": key,
                "kept_id": keeper["id"],
                "kept_name": keeper.get("name"),
            })

    return assignments, duplicates


def _backfill_on_connection(conn) -> dict:
    from sqlalchemy import text

    rows = conn.execute(
        text("SELECT id, name, validated, status FROM ipos")
    ).mappings().all()

    # result_count drives which duplicate is kept; the table may legitimately
    # not exist yet on a very fresh database.
    counts: dict[int, int] = {}
    try:
        for ipo_id, total in conn.execute(
            text("SELECT ipo_id, COUNT(*) FROM allotment_results GROUP BY ipo_id")
        ).all():
            counts[int(ipo_id)] = int(total)
    except Exception:  # noqa: BLE001 - no results table yet is fine
        counts = {}

    prepared = [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "validated": bool(r["validated"]),
            "status": r["status"],
            "result_count": counts.get(int(r["id"]), 0),
        }
        for r in rows
    ]
    assignments, duplicates = plan_name_key_backfill(prepared)

    updated = 0
    for ipo_id, key in assignments.items():
        result = conn.execute(
            text(
                "UPDATE ipos SET name_key = :key WHERE id = :id "
                "AND (name_key IS NULL OR name_key <> :key)"
            ),
            {"key": key, "id": ipo_id},
        )
        updated += result.rowcount or 0

    for duplicate in duplicates:
        conn.execute(
            text("UPDATE ipos SET validated = 0, status = 'Closed' WHERE id = :id"),
            {"id": duplicate["id"]},
        )

    return {"updated": updated, "duplicates": duplicates}


def apply_name_key_backfill(bind) -> dict:
    """Backfill ``ipos.name_key`` in place and hide losing duplicates.

    ``bind`` may be an Alembic ``Connection`` (the migration path, so the work
    joins the migration's own transaction) or an ``Engine`` (the startup
    self-heal path, where this owns the transaction).

    Idempotent, and never raises: rows already carrying the right key are
    skipped, and a failure here must not stop the app from booting.
    """
    from sqlalchemy import inspect
    from sqlalchemy.engine import Engine

    try:
        if not inspect(bind).has_table("ipos"):
            return {"skipped": "no ipos table"}

        if isinstance(bind, Engine):
            with bind.begin() as conn:
                summary = _backfill_on_connection(conn)
        else:
            summary = _backfill_on_connection(bind)
    except Exception as exc:  # noqa: BLE001 - startup must survive this
        logger.error("ipo name_key backfill failed: %s", exc, exc_info=True)
        return {"error": str(exc)}

    duplicates = summary.get("duplicates") or []
    if duplicates:
        logger.warning(
            "De-duplicated %d IPO row(s) sharing a name key. The duplicate is "
            "hidden (validated=False) but never deleted, so saved check history "
            "survives: %s",
            len(duplicates),
            "; ".join(
                f"kept #{d['kept_id']} '{d['kept_name']}' over #{d['id']} '{d['name']}'"
                for d in duplicates[:10]
            ),
        )
    return summary
