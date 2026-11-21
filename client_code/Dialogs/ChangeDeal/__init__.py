from anvil import *
import anvil.server

from ._anvil_designer import ChangeDealTemplate
from ... import sr, state


class ChangeDeal(ChangeDealTemplate):
    """Propose a new deal on a booked job (Work.propose_change): a new bounty and/or up to 3 extra checklist items,
    with what changed. The other side accepts or declines it on the bounty page. Server errors stay in the dialog.
    Closes with True when the proposal was sent, None on Back."""

    def __init__(self, bounty_id="", base=20, bonus=0, other="", items_left=3, **properties):
        super().__init__(**properties)
        self._id = bounty_id
        self._left = max(0, min(3, items_left))
        state.heading(self.title_label, 2)
        self.text_label.text = ("Job bigger (or smaller) than it looked? Agree it here, not in cash on the doorstep. "
                                "%s sees your proposal and accepts or declines it." % (other or "The other side"))
        self.base_box.text = base
        self.dom_nodes["base_cap"].innerHTML = "New bounty ($) <em>(now %s)</em>" % sr.esc(sr.money(base))
        state.set_control_attr(self.base_box, "min", max(20, bonus or 0))
        state.set_control_attr(self.base_box, "max", 500)
        state.set_control_attr(self.base_box, "step", 1)
        boxes = [self.item1_box, self.item2_box, self.item3_box]
        for i, box in enumerate(boxes):
            box.visible = i < self._left
            state.set_control_attr(box, "maxlength", 90)
            state.set_control_attr(box, "aria-label", "Extra checklist item %d" % (i + 1))
        state.set_control_attr(self.why_box, "maxlength", 300)
        self.dom_nodes["hint"].textContent = ("Accepted changes update the bounty and the checklist the work is scored on. "
                                              "Extra items count in the quality score like the others.")

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        v = self.base_box.text
        if v in (None, ""):
            return self._fail("Fill in the bounty (it can stay the same if you only add items).")
        try:
            base = float(v)
        except (TypeError, ValueError):
            return self._fail("The bounty is a whole number of dollars.")
        items = [(b.text or "").strip() for b in (self.item1_box, self.item2_box, self.item3_box)[:self._left]]
        items = [x for x in items if x]
        why = (self.why_box.text or "").strip()
        if len(why) < 10:
            return self._fail("Say what changed (at least 10 characters).")
        self.error_label.visible = False
        self.ok_button.enabled = False
        try:
            r = anvil.server.call("propose_change", self._id, int(base) if base == int(base) else base, items, why)
        finally:
            self.ok_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            return self._fail(r.get("error") or "That didn't work.")
        self.raise_event("x-close-alert", value=True)

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True
