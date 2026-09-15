"""
Retirement of registrar-sourced IPOs that have dropped off their registrar portal.

WHY THIS EXISTS
---------------
``auto_detect._merge_checkable`` and ``_dropdown_only_records`` are purely
additive: a name listed on a registrar's allotment portal is promoted to
``Allotment Announced`` and published to the client-facing dropdown, and nothing
ever takes it back out. A registrar, however, does not keep every issue in its
dropdown forever — once the allotment window passes, the name is removed. Left
alone, the dropdown keeps offering an IPO the registrar no longer knows about,
and a check against it comes back as a fabricated "Not Allotted" (the registrar
simply has no record), which is the single worst outcome this project recognises.

So the same portal signal that publishes a name must also be able to unpublish
it. That is this module.

THE SAFETY RULE (why absence is not immediately fatal)
-----------------------------------------------------
"The name is not in the list I just read" only means "removed" if the list was
actually read. Every other reason for it being missing — a selector that drifted
after a site redesign, a portal that timed out, a dropdown that paginates and we
only saw page one — would otherwise look identical, and acting on it would empty
the dropdown. Two independent guards prevent that:

1. **Conclusive reads only.** The caller passes ``conclusive_registrars``: the
   portals scraped without error *and* with at least one option returned. A row
   whose own registrar is not in that set is left alone, whatever it looks like.
2. **Two strikes.** A name must be absent from a conclusively-read portal on
   ``RETIRE_AFTER_SCANS`` consecutive scans before it is retired. One bad scan
   is therefore a no-op, and the counter resets the moment the name reappears.

Retirement is deliberately reversible and non-destructive: it flips
``validated``/``status``, it does not delete the row. Saved ``allotment_results``
reference ``ipos.id``, so deleting would destroy check history; and because the
promotion path runs on every scan, a name that reappears on the portal
republishes the very same row with no admin action.
"""

from dataclasses import dataclass

# The canonical name matcher, shared with the promotion path in auto_detect.py
# and with reconcile.py, so "Foo Ltd" retired as stale can never be a different
# key from the "Foo Limited" the portal publishes.
from ipo_sync.reconcile import _normalize_name_for_match as normalize_name_key

# Outcome labels (also used as counter keys by the caller's summary).
STILL_LIVE = "still_live"
ABSENT = "absent"
RETIRED = "retired"
INCONCLUSIVE = "inconclusive"

# Consecutive conclusively-observed absences required before a row is hidden.
# 2 means one unexpected scan can never remove an IPO from the dropdown, so a
# portal hiccup costs a day of staleness rather than the whole list.
RETIRE_AFTER_SCANS = 2


@dataclass(frozen=True)
class RetireCandidate:
    """A currently-published registrar-sourced IPO, as stored in the DB."""

    name: str
    registrar_name: str | None
    absent_scan_count: int = 0


@dataclass(frozen=True)
class RetireVerdict:
    """What should happen to one candidate this scan."""

    outcome: str
    absent_scan_count: int  # the value to persist now
    reason: str


def plan_retirement(
    candidates: list[RetireCandidate],
    live_names_by_registrar: dict[str, list[str]] | None,
    conclusive_registrars: set[str] | list[str] | None,
    retire_after: int = RETIRE_AFTER_SCANS,
) -> list[RetireVerdict]:
    """Decide, for each candidate, whether it is still live, newly absent, or stale.

    ``live_names_by_registrar`` maps registrar name -> the names that registrar's
    portal listed in this scan. ``conclusive_registrars`` names the portals those
    lists can be trusted to be complete for.

    Returns exactly one verdict per candidate, **in the same order**, so the
    caller can apply them positionally against its query results. Pure: no DB, no
    I/O, no global state, so the rule above can be unit-tested directly.
    """
    live_keys: dict[str, set[str]] = {}
    for registrar, names in (live_names_by_registrar or {}).items():
        keys = {key for key in (normalize_name_key(n) for n in names or []) if key}
        live_keys[registrar] = keys

    # A name live on ANY conclusively-read portal is checkable, regardless of
    # which registrar our row happens to point at — a slightly-off registrar
    # mapping is a routing problem, not evidence that the IPO is gone.
    any_live: set[str] = set()
    for keys in live_keys.values():
        any_live |= keys

    conclusive = set(conclusive_registrars or ())
    threshold = max(1, retire_after)

    verdicts: list[RetireVerdict] = []
    for candidate in candidates:
        key = normalize_name_key(candidate.name)
        previous = max(0, int(candidate.absent_scan_count or 0))

        if not key:
            verdicts.append(RetireVerdict(INCONCLUSIVE, previous, "unusable IPO name"))
            continue

        if key in any_live:
            verdicts.append(RetireVerdict(
                STILL_LIVE, 0, "still listed on a registrar allotment portal",
            ))
            continue

        if candidate.registrar_name not in conclusive:
            verdicts.append(RetireVerdict(
                INCONCLUSIVE,
                previous,
                f"registrar '{candidate.registrar_name}' was not read conclusively this scan",
            ))
            continue

        count = previous + 1
        if count >= threshold:
            verdicts.append(RetireVerdict(
                RETIRED,
                count,
                f"absent from the '{candidate.registrar_name}' portal for {count} "
                f"consecutive scans",
            ))
        else:
            verdicts.append(RetireVerdict(
                ABSENT,
                count,
                f"absent from the '{candidate.registrar_name}' portal "
                f"({count}/{threshold} scans; not yet retired)",
            ))

    return verdicts
