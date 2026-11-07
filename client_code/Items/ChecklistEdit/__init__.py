from anvil import *

from ._anvil_designer import ChecklistEditTemplate
from ... import state


class ChecklistEdit(ChecklistEditTemplate):
    """One editable checklist item in the post wizard. item = {i, text}. Typing raises x-ci (i, text); the x raises x-crm (i)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["num"].textContent = str(self.item["i"] + 1)
        self.box.text = self.item["text"]
        state.set_control_attr(self.box, "maxlength", 90)
        state.set_control_attr(self.box, "aria-label", "Checklist item %d" % (self.item["i"] + 1))
        state.control(self.box).addEventListener("input", self._typed)

    def _typed(self, event):
        if self.parent:
            self.parent.raise_event("x-ci", i=self.item["i"], text=self.box.text or "")

    @handle("rm_button", "click")
    def rm_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-crm", i=self.item["i"])
