from anvil import *

from ._anvil_designer import LineTemplate


class Line(LineTemplate):
    """A line of text in a list: item = {text, cls?, icon?, right?} (checklist items, results, flags)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        d = self.dom_nodes
        d["row"].className = "sr-line " + (it.get("cls") or "")
        d["text"].textContent = it["text"]
        if it.get("icon"):
            d["ic"].className = "ic ic-" + it["icon"]
            d["ic"].setAttribute("aria-label", "Done" if it["icon"] == "check" else ("Not done" if it["icon"] == "x" else ""))
            if it["icon"] not in ("check", "x"):
                d["ic"].removeAttribute("aria-label")
        else:
            d["ic"].remove()
        if it.get("right"):
            d["right"].textContent = it["right"]
        else:
            d["right"].remove()
