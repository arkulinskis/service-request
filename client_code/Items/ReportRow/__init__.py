from anvil import *

from ._anvil_designer import ReportRowTemplate
from ... import router, sr, state


class ReportRow(ReportRowTemplate):
    """A report in Admin → Trust & safety. Uphold (a strike) or dismiss; then x-changed."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        is_open = r["status"] == "open"
        d["kind"].className = "ui-badge" + (" bad" if is_open else "")
        d["kind"].textContent = r.get("kind_label") or r.get("kind") or ""
        e = sr.esc
        html = "<b>%s</b> reported" % e(r.get("reporter") or "")
        s = r.get("subject")
        if s:
            html += " <b>%s</b> (%s, %s)" % (e(s.get("name")), e(s.get("email")), e(sr.plural(s.get("strikes") or 0, "strike")))
        bt = r.get("bounty")
        if bt:
            html += ' on <a href="%s">%s</a>' % (router.href("bounty", bt["id"]), e(bt.get("title")))
        sr.rich(d["who"], html)
        d["when"].textContent = sr.ago(r.get("created"))
        d["text"].textContent = r.get("text") or ""
        self.acts.visible = is_open
        d["handled"].hidden = is_open
        d["handled"].textContent = r["status"] + ((": " + r["note"]) if r.get("note") else "")
        state.set_control_attr(self.note_box, "aria-label", "Note")
        state.set_control_attr(self.note_box, "maxlength", 300)

    def _resolve(self, action):
        if state.call("admin_resolve_report", self.item["id"], action, self.note_box.text or ""):
            state.toast("Done", "ok")
            if self.parent:
                self.parent.raise_event("x-changed")

    @handle("uphold_button", "click")
    def uphold_button_click(self, **event_args):
        self._resolve("uphold")

    @handle("dismiss_button", "click")
    def dismiss_button_click(self, **event_args):
        self._resolve("dismiss")
