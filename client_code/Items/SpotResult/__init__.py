from anvil import *

from ._anvil_designer import SpotResultTemplate


class SpotResult(SpotResultTemplate):
    """A place found by the spot picker's search. item = {lat, lng, name, street, label}; a click raises x-pick."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["btn"].textContent = self.item["label"]

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-pick", place=self.item)
