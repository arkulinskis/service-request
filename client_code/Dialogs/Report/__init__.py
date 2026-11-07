from anvil import *
import anvil.js

from ._anvil_designer import ReportTemplate
from ... import state


class Report(ReportTemplate):
    """Report a bounty or a person: a kind and what happened. send(kind, text) makes the server call (report);
    problems show in the dialog. Closes with the reply, or None."""

    def __init__(self, what="this", send=None, **properties):
        super().__init__(**properties)
        self._send = send
        self.dom_nodes["title"].textContent = "Report " + (what or "this")
        state.set_control_attr(self.text_box, "maxlength", 1000)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        picked = self.dom_nodes["kinds"].querySelector("input:checked")
        kind = getattr(picked, "value") if picked else "other"
        text = (self.text_box.text or "").strip()
        if len(text) < 10:
            self._fail("Tell us a little more (at least 10 characters), so a moderator can act on it.")
            return
        self.send_button.enabled = False
        try:
            r = self._send(kind, text) if self._send else {"ok": True}
        finally:
            self.send_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return
        self.raise_event("x-close-alert", value=r)

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True
