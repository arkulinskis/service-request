from anvil import *

from ._anvil_designer import BadgeTemplate


class Badge(BadgeTemplate):
    """A small badge: item = {text, cls?} (skills, review tags)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        d = self.dom_nodes["b"]
        d.textContent = self.item["text"]
        if self.item.get("cls"):
            d.className = "ui-badge " + self.item["cls"]
