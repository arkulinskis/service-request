from anvil import *

from ._anvil_designer import OfferCardTemplate
from ... import router, sr, state


class OfferCard(OfferCardTemplate):
    """An offer the poster can pick or decline. item = {o: offer, base: the bounty, open: bool}.
    Raises x-accept / x-decline (offer=...)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        o = self.item["o"]
        h = o["helper"]
        rec = h.get("record") or {}
        d = self.dom_nodes
        d["card"].className = "bt-offer " + o["status"]
        d["who"].setAttribute("href", router.href("neighbour", h["id"]))
        d["av"].textContent = state.initials(h["name"])
        d["name"].textContent = h["name"]
        sr.fill_rating(d["rec"], rec)
        extra = " · %s jobs · %s bonuses" % (rec.get("jobs") or 0, rec.get("bonus_won") or 0)
        if rec.get("dropouts"):
            extra += " · %s drop-outs" % rec["dropouts"]
        d["rec"].insertAdjacentText("beforeend", extra)
        sr.fill_tag(d["tag"], o["ask"], size="sm", sub="")
        over = o["ask"] - self.item["base"]
        d["counter"].hidden = over <= 0
        d["counter"].textContent = "Counter-offer: +" + sr.money(over)
        d["msg"].textContent = o.get("message") or ""
        d["when"].hidden = not o.get("when")
        d["when_t"].textContent = o.get("when") or ""
        self.skills_panel.items = [{"text": k} for k in o.get("skills") or []]
        self.skills_panel.visible = bool(o.get("skills"))
        can_pick = o["status"] == "pending" and self.item["open"]
        self.acts.visible = can_pick
        self.pick_button.text = "Pick " + sr.first(h["name"])
        d["status"].hidden = can_pick
        d["status"].textContent = o["status"]

    @handle("pick_button", "click")
    def pick_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-accept", offer=self.item["o"])

    @handle("decline_button", "click")
    def decline_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-decline", offer=self.item["o"])
