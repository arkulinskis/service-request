from anvil import *
import anvil.js

from ._anvil_designer import BountyCardTemplate
from ... import router, sr, state


class BountyCard(BountyCardTemplate):
    """A bounty on the board (TaskRabbit-like row): category tile, title, area, when, payment, the poster's record,
    the tear-off tag, a photo, the number of offers. item = a board card from get_board (or the post wizard's preview).
    Hovering raises x-hover (bounty_id, on) so the page lights up the map pin."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        d = self.dom_nodes
        p = b.get("poster") or {}
        rec = p.get("record") or {}
        card = d["card"]
        card.setAttribute("href", router.href("bounty", b["id"]))
        card.setAttribute("data-card", str(b["id"]))
        sr.fill_ti(d["ti"], b["task"])
        d["title"].textContent = b["title"]
        d["area"].textContent = (b.get("area") or "") + ((" · " + sr.dist(b["dist"])) if b.get("dist") is not None else "")
        d["when"].textContent = sr.when(b)
        d["pay_ic"].className = "ic ic-" + sr.PAY_ICON.get(b.get("pay"), "wallet")
        d["pay"].textContent = sr.PAY.get(b.get("pay"), "")
        d["vehicle"].hidden = not b.get("vehicle")
        d["mini"].textContent = state.initials(p.get("name"))
        d["who"].textContent = p.get("name") or ""
        sr.fill_rating(d["rating"], rec)
        d["fast"].hidden = not (rec.get("paid", 0) >= 3 and rec.get("paid_fast") == rec.get("paid"))
        d["demo"].hidden = not b.get("demo")
        d["mine"].hidden = not b.get("mine")
        sr.fill_tag(d["tag"], b["base"], b.get("bonus") or 0, b.get("bar") or 80)
        if b.get("cover"):
            d["ph"].src = sr.photo(b["cover"], True)
        else:
            d["ph"].remove()
        d["offers"].textContent = sr.plural(b["offers"], "offer") if b.get("offers") else "No offers yet"
        card.addEventListener("mouseenter", self._enter)
        card.addEventListener("mouseleave", self._leave)

    def _enter(self, event):
        if self.parent:
            self.parent.raise_event("x-hover", bounty_id=self.item["id"], on=True)

    def _leave(self, event):
        if self.parent:
            self.parent.raise_event("x-hover", bounty_id=self.item["id"], on=False)
