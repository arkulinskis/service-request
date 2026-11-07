from anvil import *

from ._anvil_designer import StatCardTemplate


class StatCard(StatCardTemplate):
    """A number with a label (a neighbour's record). item = {num, label}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["num"].textContent = self.item["num"]
        self.dom_nodes["label"].textContent = self.item["label"]
