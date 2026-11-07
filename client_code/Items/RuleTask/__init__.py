from anvil import *

from ._anvil_designer import RuleTaskTemplate
from ... import router, sr


class RuleTask(RuleTaskTemplate):
    """A row of the rules page's task table: a category heading (item = {cat}) or a task (item = {t})."""

    def __init__(self, **properties):
        super().__init__(**properties)
        d = self.dom_nodes
        if self.item.get("cat"):
            c = self.item["cat"]
            d["row"].className = "rl-trow cat"
            d["name"].innerHTML = sr.icon(c["icon"]) + " " + sr.esc(c["name"])
            d["blurb"].remove()
            d["prices"].remove()
            return
        t = self.item["t"]
        d["name"].innerHTML = '<a href="%s">%s</a>%s' % (router.href("post", t["key"]), sr.esc(t["name"]),
                                                           ' <span class="ui-badge">Vehicle</span>' if t.get("vehicle") else "")
        d["blurb"].textContent = t["blurb"]
        d["prices"].textContent = " · ".join(sr.money(p) for p in t["prices"])
