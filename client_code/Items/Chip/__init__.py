from anvil import *

from ._anvil_designer import ChipTemplate


class Chip(ChipTemplate):
    """A pill button (category chips, filters, money presets). item = {key, label, icon?, on}; a click raises x-chip."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        d = self.dom_nodes
        d["label"].textContent = it["label"]
        if it.get("icon"):
            d["ic"].className = "ic ic-" + it["icon"]
        else:
            d["ic"].remove()
        d["btn"].classList.toggle("on", bool(it.get("on")))
        d["btn"].setAttribute("aria-pressed", "true" if it.get("on") else "false")
        d["btn"].setAttribute("data-key", str(it["key"]))

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-chip", key=self.item["key"])
