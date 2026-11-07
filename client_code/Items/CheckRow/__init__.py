from anvil import *

from ._anvil_designer import CheckRowTemplate


class CheckRow(CheckRowTemplate):
    """A checklist item to tick (the proof form and the poster's check). item = {i, text, checked, self: None | bool}.
    Ticking raises x-check (i, checked)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        d = self.dom_nodes
        d["box"].checked = bool(it.get("checked"))
        d["text"].textContent = it["text"]
        if it.get("self") is None:
            d["self_note"].remove()
        else:
            d["self_note"].textContent = "Helper: done" if it["self"] else "Helper: not done"
        d["box"].addEventListener("change", self._change)

    def _change(self, event):
        if self.parent:
            self.parent.raise_event("x-check", i=self.item["i"], checked=bool(self.dom_nodes["box"].checked))
