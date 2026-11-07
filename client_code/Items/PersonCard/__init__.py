from anvil import *

from ._anvil_designer import PersonCardTemplate
from ... import router, sr, state


class PersonCard(PersonCardTemplate):
    """The poster's (or your helper's) record next to a bounty. item = {p: person, role: poster | helper, title}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p, role = self.item["p"], self.item["role"]
        r = p.get("record") or {}
        d = self.dom_nodes
        e = sr.esc
        d["title"].textContent = self.item["title"]
        d["who"].setAttribute("href", router.href("neighbour", p["id"]))
        d["av"].textContent = state.initials(p["name"])
        d["name"].textContent = p["name"]
        d["sub"].textContent = (p.get("area") or "Neighbour") + ((" · since " + sr.fmt_date(p["joined"], {"month": "short", "year": "numeric"})) if p.get("joined") else "")
        sr.rich(d["l1"], "Rated " + sr.rating_html(r) + (" by helpers" if role == "poster" else " by posters"))
        if role == "poster":
            d["l2"].textContent = sr.pay_record(r)
            late = r.get("late_cancels") or 0
            sr.rich(d["l3"], "<b>%s</b> bounties completed%s" % (e(r.get("completed") or 0), (" · %d late cancel%s" % (late, "s" if late > 1 else "")) if late else ""))
        else:
            d["l2box"].hidden = True
            drops = r.get("dropouts") or 0
            sr.rich(d["l3"], "<b>%s</b> jobs done · <b>%s</b> quality bonuses%s" % (e(r.get("jobs") or 0), e(r.get("bonus_won") or 0),
                                                                                 (" · %d drop-out%s" % (drops, "s" if drops > 1 else "")) if drops else ""))
        d["warn"].hidden = r.get("standing") != "warned"
