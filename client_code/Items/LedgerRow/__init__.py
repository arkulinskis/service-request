from anvil import *

from ._anvil_designer import LedgerRowTemplate
from ... import router, sr

STATES = {"owed": "Owed", "sent": "Sent", "settled": "Settled", "disputed": "Disputed"}


class LedgerRow(LedgerRowTemplate):
    """One amount in the ledger. item = a row from get_ledger."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        d["a"].setAttribute("href", router.href("bounty", r["id"]))
        d["a"].textContent = r["title"]
        sub = sr.fmt_date(r.get("at"))
        if r.get("quality") is not None:
            sub += " · quality %s%%" % r["quality"]
        if r.get("bonus"):
            sub += " · +%s bonus" % sr.money(r["bonus"])
        d["sub"].textContent = sub
        d["who"].textContent = ("From " if r["dir"] == "in" else "To ") + (r.get("other") or "")
        d["how"].textContent = sr.PAY.get(r.get("method"), "") + ((" · " + r["ref"]) if r.get("ref") else "")
        d["st"].className = "st " + r["state"]
        d["st"].textContent = STATES.get(r["state"], r["state"])
        d["amt"].className = "amt " + r["dir"]
        d["amt"].textContent = ("+" if r["dir"] == "in" else "−") + sr.money(r["amount"])
