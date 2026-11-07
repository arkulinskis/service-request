from anvil import *
import anvil.server

from ._anvil_designer import NeighbourTemplate
from ... import router, sr, state


class Neighbour(NeighbourTemplate):
    """A neighbour's public page (#neighbour/<id>): first name + initial, area, record as a helper and as a poster
    (pays within 2 days, bonus paid), badges, skills, open bounties and reviews (once no longer blind).
    Never an email or an address."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        sr.catalog()
        r = anvil.server.call("get_neighbour", args[0] if args else "")
        if r.get("ok") is False:
            self.body.visible = False
            self.dom_nodes["missing_p"].textContent = r.get("error") or ""
            return
        self.missing_box.visible = False
        self._draw(r["person"])

    def _draw(self, p):
        self.p = p
        router.set_title(p["name"])
        n = self.dom_nodes
        h, po = p["as_helper"], p["as_poster"]
        n["av"].textContent = state.initials(p["name"])
        n["name"].textContent = p["name"]
        n["area_box"].hidden = not p.get("area")
        n["area"].textContent = p.get("area") or ""
        n["since"].textContent = "Neighbour since " + sr.fmt_date(p.get("joined"), {"month": "long", "year": "numeric"})
        n["good"].hidden = not (h.get("standing") == "good" and (h.get("jobs") or po.get("completed")))
        n["warned"].hidden = h.get("standing") != "warned"
        self.edit_link.visible = bool(p.get("me"))
        self.report_button.visible = not p.get("me")
        helps = (h.get("jobs") or 0) > 0 or bool(p.get("skills"))
        posts = (po.get("posted") or 0) > 0
        stats = []
        if helps:
            stats += [{"num": str(h.get("jobs") or 0), "label": "jobs done"},
                      {"num": ("★ %.1f" % float(h["rating"])) if h.get("rating") else "–", "label": "as a helper (%s)" % (h.get("reviews") or 0)},
                      {"num": str(h.get("bonus_won") or 0), "label": "quality bonuses won"}]
        if posts:
            stats += [{"num": str(po.get("completed") or 0), "label": "bounties completed"},
                      {"num": ("%s/%s" % (po.get("paid_fast") or 0, po["paid"])) if po.get("paid") else "–", "label": "paid within 2 days"}]
            if po.get("bonus_jobs"):
                stats.append({"num": "%s/%s" % (po.get("bonus_paid") or 0, po["bonus_jobs"]), "label": "bonuses paid"})
        if not helps and not posts:
            stats.append({"num": "New", "label": "no jobs yet"})
        self.stats_panel.items = stats
        self.bio_box.visible = bool(p.get("bio"))
        n["bio"].textContent = p.get("bio") or ""
        self.skills_panel.items = [{"text": s, "cls": "brand"} for s in p.get("skills") or []]
        self.badges_box.visible = bool(p.get("badges"))
        self.badges_panel.items = p.get("badges") or []
        revs = p.get("reviews") or []
        n["rev_count"].textContent = str(len(revs))
        self.reviews_panel.items = revs
        n["no_reviews"].hidden = bool(revs)
        self.open_box.visible = bool(p.get("open"))
        self.open_panel.items = p.get("open") or []

    @handle("report_button", "click")
    def report_button_click(self, **event_args):
        sr.report(self.p["name"], user=self.p["id"])
