from anvil import *

from ._anvil_designer import TaskButtonTemplate
from ... import sr


class TaskButton(TaskButtonTemplate):
    """A task to pick in the post wizard. item = {t: task, on: bool}; a click raises x-task (key)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t = self.item["t"]
        d = self.dom_nodes
        d["btn"].classList.toggle("on", bool(self.item.get("on")))
        d["btn"].setAttribute("aria-pressed", "true" if self.item.get("on") else "false")
        sr.fill_ti(d["ti"], t["key"], "sm")
        d["name"].textContent = t["name"]
        d["blurb"].textContent = t["blurb"]
        d["from"].textContent = "From " + sr.money(t["prices"][0])
        d["season"].hidden = not sr.in_season(t)
        d["vehicle"].hidden = not t.get("vehicle")

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-task", key=self.item["t"]["key"])
