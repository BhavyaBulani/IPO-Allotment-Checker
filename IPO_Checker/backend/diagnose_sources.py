"""
Run this once from wherever the app will actually be deployed (e.g. a
Render shell, not your laptop) BEFORE trusting the sync pipeline.

It hits NSE, BSE, and (if UPSTOX_ACCESS_TOKEN is set) Upstox directly and
prints what came back — raw row count, a sample row, and whether the
expected fields were found. If NSE/BSE 403 or return junk from this host
but not from your laptop, that confirms IP-based blocking, not a bug.

Usage:
    cd IPO_Checker/backend
    python diagnose_sources.py
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def check(source_name, fetch_fn):
    print(f"\n=== {source_name} ===")
    try:
        rows = fetch_fn()
    except Exception as exc:
        print(f"  RAISED (should not happen — fetch_fn should catch internally): {exc}")
        return
    print(f"  Rows returned: {len(rows)}")
    if rows:
        sample = rows[0]
        print(f"  Sample row: {sample}")
        missing = [k for k in ("name", "status") if not sample.get(k)]
        if missing:
            print(f"  WARNING: sample row missing required field(s): {missing}")
        else:
            print("  Looks parseable.")
    else:
        print("  No rows — check the WARNING log above for the reason (403, bad JSON, etc.)")


if __name__ == "__main__":
    from ipo_sync.sources.nse_source import fetch_nse_ipos
    from ipo_sync.sources.bse_source import fetch_bse_ipos
    from ipo_sync.sources.upstox_source import fetch_upstox_ipos
    from ipo_sync.sources.ipotracker_source import fetch_ipotracker_ipos
    from ipo_sync.sources.finapi_source import fetch_finapi_ipos

    check("NSE", fetch_nse_ipos)
    check("BSE", fetch_bse_ipos)
    check("Upstox", fetch_upstox_ipos)
    check("ipotracker", fetch_ipotracker_ipos)
    check("FinAPI", fetch_finapi_ipos)

    print(
        "\nIf NSE/BSE show 0 rows here but work fine from your laptop, "
        "that's IP-based blocking on this host — see README for fallback options "
        "(Playwright-based fetch, or a paid aggregator like ipoalerts.in)."
    )
