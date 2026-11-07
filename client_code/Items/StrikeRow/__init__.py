from anvil import *

from ._anvil_designer import StrikeRowTemplate
from ... import state


class StrikeRow(StrikeRowTemplate):
    """Someone with strikes (Admin → Trust & safety): set the strikes and the pause by hand."""

    def __init__(self, **properties):
        super().__init__(**properties)
        u = self.item
        d = self.dom_nodes
        d["name"].textContent = u.get("name") or ""
        d["last"].textContent = u.get("last_strike") or ""
        d["email"].textContent = u.get("email") or ""
        self.strikes_box.text = str(u.get("strikes") or 0)
        self.paused_box.checked = bool(u.get("paused"))
        state.set_control_attr(self.strikes_box, "min", 0)
        state.set_control_attr(self.strikes_box, "max", 9)
        state.set_control_attr(self.strikes_box, "aria-label", "Strikes")

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        try:
            strikes = int(float(self.strikes_box.text or 0))
        except Exception:
            strikes = 0
        if state.call("admin_set_standing", self.item["id"], strikes, bool(self.paused_box.checked)):
            state.toast("Saved", "ok")
            if self.parent:
                self.parent.raise_event("x-changed")
