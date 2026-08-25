"""MUFG Intime live IPO allotment integration.

MUFG Intime India Pvt Ltd is the renamed Link Intime India Pvt Ltd — the same
registrar and the same public allotment portal at ``in.mpms.mufg.com``. This
class reuses the Link Intime live implementation under the MUFG registrar ID
(4), so IPOs mapped to either name resolve to the one real portal.
"""

from .link_intime import LinkIntimeLiveRegistrar


class MufgIntimeLiveRegistrar(LinkIntimeLiveRegistrar):
    label = "MUFG Intime"

    @property
    def name(self) -> str:
        return "MUFG Intime (live)"

    @property
    def registrar_id(self) -> int:
        return 4
