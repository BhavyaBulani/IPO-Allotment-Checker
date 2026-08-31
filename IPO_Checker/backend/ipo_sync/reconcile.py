"""
Reconciles raw IPO rows from one or more sources into publish-ready
records, matching the contract auto_detect.py already expects:

    reconcile(nse_rows, bse_rows) -> list[ReconciledIPO]

Publish rule: an IPO is validated=True only if
  (a) it appears in 2+ sources and they agree on name+status, OR
  (b) it appears in only one source but that source is authoritative
      (currently: Upstox, since it's official broker data, not scraped) AND
  (c) its registrar free-text maps cleanly via registrar_map.

Anything else is held (validated=False) with a reason attached for an
admin review queue, rather than silently guessed.
"""

from dataclasses import dataclass, field
import re

from ipo_sync.registrar_map import resolve_registrar_name

# Sources whose single-source presence is still trustworthy enough to
# auto-publish (no cross-check needed) because they're primary/official
# rather than scraped/aggregated. NSE qualifies because its per-IPO detail
# endpoint supplies the registrar straight from the exchange's own records.
# ipotracker is the user's own curated catalog (with registrar + dates), and
# FinAPI is a structured, API-key-authenticated catalog. Both are treated as
# primary, though FinAPI rows still need a registrar from another source to
# pass validation (its catalog endpoint doesn't expose one).
_AUTHORITATIVE_SOLO_SOURCES = {"NSE", "Upstox", "ipotracker", "FinAPI"}


@dataclass
class ReconciledIPO:
    name: str
    status: str  # "Open" | "Upcoming" | "Closed" | "Allotment Announced"
    open_date: object
    close_date: object
    registrar_name: str | None
    sources: list = field(default_factory=list)
    validated: bool = False
    reason: str = ""


def _normalize_name_for_match(value: str) -> str:
    value = re.sub(r"\s*&\s*", " and ", value or "")
    value = re.sub(r"\b(limited|ltd|private|pvt)\b\.?", "", value or "", flags=re.I)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def reconcile(*source_rowsets: list[dict], source_names: list[str] | None = None) -> list[ReconciledIPO]:
    """
    Accepts any number of row-lists (e.g. reconcile(nse_rows, bse_rows) or
    reconcile(nse_rows, bse_rows, upstox_rows)). Each row is a dict:
    {name, status, open_date, close_date, registrar_name}.

    source_names defaults to ["NSE", "BSE", "Upstox", ...][:n] matching
    positional order, for backward compatibility with the 2-arg call in
    auto_detect.py.
    """
    default_names = ["NSE", "BSE", "Upstox"]
    if source_names is None:
        source_names = default_names[: len(source_rowsets)]

    # Group rows by normalized name across all sources.
    grouped: dict[str, list[tuple[str, dict]]] = {}
    for src_name, rows in zip(source_names, source_rowsets):
        for row in rows or []:
            key = _normalize_name_for_match(row.get("name", ""))
            if not key:
                continue
            grouped.setdefault(key, []).append((src_name, row))

    reconciled: list[ReconciledIPO] = []
    for key, entries in grouped.items():
        sources_present = sorted({src for src, _ in entries})
        statuses = {row["status"] for _, row in entries}
        display_name = entries[0][1]["name"]

        # Prefer the row with a registrar_name populated, and the most
        # complete dates, when multiple sources report the same IPO.
        best_row = max(
            (row for _, row in entries),
            key=lambda r: (bool(r.get("registrar_name")), bool(r.get("open_date")), bool(r.get("close_date"))),
        )

        status_agrees = len(statuses) == 1
        multi_source = len(sources_present) >= 2
        solo_authoritative = (
            len(sources_present) == 1 and sources_present[0] in _AUTHORITATIVE_SOLO_SOURCES
        )

        registrar_canonical = resolve_registrar_name(best_row.get("registrar_name"))

        reasons = []
        if not (multi_source or solo_authoritative):
            reasons.append(f"only seen in single non-authoritative source ({sources_present[0]})")
        if multi_source and not status_agrees:
            reasons.append(f"sources disagree on status: {statuses}")
        if not registrar_canonical:
            reasons.append(f"registrar '{best_row.get('registrar_name')}' not mapped")

        validated = (multi_source and status_agrees or solo_authoritative) and bool(registrar_canonical)

        reconciled.append(ReconciledIPO(
            name=display_name,
            status=best_row["status"],
            open_date=best_row.get("open_date"),
            close_date=best_row.get("close_date"),
            registrar_name=registrar_canonical,
            sources=sources_present,
            validated=validated,
            reason="; ".join(reasons) if reasons else "cross-confirmed",
        ))

    return reconciled
