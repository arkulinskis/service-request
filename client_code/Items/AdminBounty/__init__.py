from anvil import *
import anvil.server

from ._anvil_designer import AdminBountyTemplate
from ... import router, sr, state
from ...Dialogs.Ask import Ask

OUTCOMES = [("Owed: bounty + bonus", "full"), ("Owed: bounty only", "base"), ("Payment confirmed: close", "done"), ("Nothing owed: cancel", "cancel")]
STRIKES = [("No strike", ""), ("Strike the poster", "poster"), ("Strike the helper", "helper")]


class AdminBounty(AdminBountyTemplate):
    """A bounty in Admin (review queue, disputes, every bounty). item = {b, mode: queue | dispute | all}.
    After an action it raises x-changed so the Admin page reloads the tab."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b, mode = self.item["b"], self.item["mode"]
        d = self.dom_nodes
        d["title"].textContent = b["title"]
        sr.fill_stamp(d["stamp"], b["status"])
        d["demo"].hidden = not b.get("demo")
        sr.fill_tag(d["tag"], b["base"], size="sm", sub=("+" + sr.money(b["bonus"])) if b.get("bonus") else "")
        flags = b.get("flags") or []
        self.flags_panel.items = [{"text": f, "cls": "warn"} for f in flags]
        self.flags_panel.visible = bool(flags)
        d["details"].hidden = not b.get("details")
        d["details"].textContent = b.get("details") or ""
        d["dispute"].hidden = not b.get("dispute")
        d["dispute_by"].textContent = "%s says:" % (b.get("dispute_by") or "")
        d["dispute_text"].textContent = b.get("dispute") or ""
        d["poster"].textContent = "%s <%s>%s" % (b.get("poster") or "", b.get("poster_email") or "",
                                                 (" · " + sr.plural(b["poster_strikes"], "strike")) if b.get("poster_strikes") else "")
        d["helper"].hidden = not b.get("helper")
        d["helper"].textContent = "Helper: " + (b.get("helper") or "")
        d["quality"].hidden = b.get("quality") is None
        d["quality"].textContent = "Quality %s%%" % b.get("quality")
        d["owed"].hidden = b.get("amount_due") is None
        d["owed"].textContent = "Owed " + sr.money(b.get("amount_due"))
        d["where"].textContent = (b.get("area") or "") + " · " + sr.ago(b.get("created"))
        d["open"].setAttribute("href", router.href("bounty", b["id"]))
        self.queue_acts.visible = mode == "queue"
        self.dispute_acts.visible = mode == "dispute"
        self.all_acts.visible = mode == "all" and b["status"] != "removed"
        if mode == "dispute":
            self.outcome_box.items = OUTCOMES
            self.strike_box.items = STRIKES
            state.set_control_attr(self.outcome_box, "aria-label", "What is owed")
            state.set_control_attr(self.strike_box, "aria-label", "Strike")
            state.set_control_attr(self.note_box, "aria-label", "Note for both sides")
            state.set_control_attr(self.note_box, "maxlength", 300)

    def _done(self, msg):
        state.toast(msg, "ok")
        if self.parent:
            self.parent.raise_event("x-changed")

    @handle("approve_button", "click")
    def approve_button_click(self, **event_args):
        if state.call("admin_approve", self.item["b"]["id"]):
            self._done("Approved: it's on the board")

    @handle("reject_button", "click")
    def reject_button_click(self, **event_args):
        bid = self.item["b"]["id"]

        def run(v):
            return anvil.server.call("admin_reject", bid, v["text"])
        if alert(Ask(title="Reject this bounty?", ok="Reject", danger=True, run=run,
                     text_field={"label": "Why? (the poster sees this)", "value": "It breaks the rules for bounties.", "max": 300}),
                 buttons=[], role="app-dialog", dismissible=True):
            self._done("Rejected")

    @handle("settle_button", "click")
    def settle_button_click(self, **event_args):
        if state.call("admin_resolve_dispute", self.item["b"]["id"], self.outcome_box.selected_value,
                      self.strike_box.selected_value or None, self.note_box.text or ""):
            self._done("Dispute settled")

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        if confirm("It disappears for everyone. The poster sees it was removed by a moderator.", title="Remove this bounty?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("admin_remove_bounty", self.item["b"]["id"], ""):
                self._done("Removed")
