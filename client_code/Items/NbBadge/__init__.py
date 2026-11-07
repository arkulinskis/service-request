from anvil import *

from ._anvil_designer import NbBadgeTemplate
from ... import sr

BADGE_ICON = {"first": "check", "trusted": "shield", "leaf": "leaf", "snow": "snow", "lift": "box", "junk": "bin", "bonus": "gift",
              "five": "star", "prompt": "bolt", "fair": "ruler"}


class NbBadge(NbBadgeTemplate):
    """A badge a neighbour earned (Leaf legend, Snow warrior ...). item = {key, name, why}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        d = self.dom_nodes
        d["ic"].innerHTML = sr.icon(BADGE_ICON.get(b["key"], "star"))
        d["name"].textContent = b["name"]
        d["why"].textContent = b.get("why") or ""
