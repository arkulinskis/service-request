from anvil import *
import anvil.js

from ._anvil_designer import AdminTemplate
from ... import sr, state

TABS = ["overview", "queue", "safety", "bounties", "feedback", "users", "demo"]
STATUSES = ["all", "review", "open", "assigned", "submitted", "validated", "paid", "done", "disputed", "cancelled", "rejected", "removed"]


class Admin(AdminTemplate):
    """#admin/<tab> (admins only): overview counts, the review queue (flagged bounties: approve / reject), trust & safety
    (disputes, reports, strikes), every bounty, the old feedback inbox, users (admin / active switches), demo data.
    Each tab is its own address, so the browser's back button works."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "overview"
        self._filter = "new"
        self._status = "all"
        parts = {"overview": self.overview_part, "queue": self.queue_part, "safety": self.safety_part, "bounties": self.bounties_part,
                 "feedback": self.feedback_part, "users": self.users_part, "demo": self.demo_part}
        tabs = {"overview": self.tab_overview, "queue": self.tab_queue, "safety": self.tab_safety, "bounties": self.tab_bounties,
                "feedback": self.tab_feedback, "users": self.tab_users, "demo": self.tab_demo}
        for name in TABS:
            parts[name].visible = name == self.tab
            tabs[name].classes["on"] = name == self.tab
            state.set_attr(tabs[name], "aria-current", "page" if name == self.tab else None)
        for panel in (self.queue_panel, self.disputes_panel, self.bounties_panel, self.reports_panel, self.handled_panel, self.people_panel):
            panel.add_event_handler("x-changed", self._changed)
        self.feedback_panel.add_event_handler("x-changed", self._feedback_changed)
        self.status_box.items = [("All statuses" if s == "all" else sr.STATUS.get(s, s), s) for s in STATUSES]
        state.set_control_attr(self.status_box, "aria-label", "Status")
        state.set_control_attr(self.search_box, "aria-label", "Search by name or email")
        sr.catalog()
        self._show()

    def _show(self):
        if self.tab == "overview":
            self._overview()
        elif self.tab == "queue":
            self._queue()
        elif self.tab == "safety":
            self._safety()
        elif self.tab == "bounties":
            self._bounties()
        elif self.tab == "feedback":
            self._feedback()
        elif self.tab == "users":
            self._users()
        else:
            self._demo()

    def _changed(self, **event_args):
        self._show()

    # ---- overview
    def _overview(self):
        d = state.call("admin_overview")
        if not d:
            return
        bs = d["bounties"]
        n = self.dom_nodes
        n["s_review"].textContent = str(bs.get("review", 0))
        n["s_disputes"].textContent = "%s · %s" % (bs.get("disputed", 0), d.get("reports_open", 0))
        n["s_open"].textContent = str(bs.get("open", 0))
        n["s_way"].textContent = str(bs.get("assigned", 0) + bs.get("submitted", 0))
        n["s_pay"].textContent = str(bs.get("validated", 0) + bs.get("paid", 0))
        n["s_done"].textContent = str(bs.get("done", 0))
        n["s_settled"].textContent = sr.money(d.get("settled") or 0)
        n["s_users"].textContent = str(d.get("users", 0))
        n["s_feedback"].textContent = str(d.get("feedback_new", 0))
        sr.rich(n["demo_line"], "Demo data is <b>%s</b> (%s demo people). Manage it in the Demo data tab." % (
            sr.esc(d["demo"]["state"]), d["demo"]["counts"].get("users", 0)))

    # ---- review queue
    def _queue(self):
        d = state.call("admin_queue")
        items = (d or {}).get("items") or []
        self.queue_panel.items = [{"b": b, "mode": "queue"} for b in items]
        self.queue_empty.visible = not items

    # ---- trust & safety
    def _safety(self):
        d = state.call("admin_safety") or {"disputes": [], "reports": [], "people": []}
        n = self.dom_nodes
        disputes = d.get("disputes") or []
        reports = d.get("reports") or []
        people = d.get("people") or []
        open_r = [r for r in reports if r["status"] == "open"]
        done_r = [r for r in reports if r["status"] != "open"][:20]
        n["h_disputes"].textContent = "Disputes (%d)" % len(disputes)
        self.disputes_panel.items = [{"b": b, "mode": "dispute"} for b in disputes]
        n["no_disputes"].hidden = bool(disputes)
        n["h_reports"].textContent = "Open reports (%d)" % len(open_r)
        self.reports_panel.items = open_r
        n["no_reports"].hidden = bool(open_r)
        n["h_people"].textContent = "People with strikes (%d)" % len(people)
        self.strikes_head.visible = bool(people)
        self.people_panel.items = people
        n["no_people"].hidden = bool(people)
        n["h_handled"].hidden = not done_r
        self.handled_panel.items = done_r

    # ---- every bounty
    def _bounties(self):
        self.status_box.selected_value = self._status
        d: dict = state.call("admin_bounties", self._status) or {"items": [], "total": 0}
        self.dom_nodes["bounties_count"].textContent = sr.plural(d.get("total") or 0, "bounty", "bounties")
        self.bounties_panel.items = [{"b": b, "mode": "all"} for b in d["items"]]
        self.bounties_empty.visible = not d["items"]

    @handle("status_box", "change")
    def status_box_change(self, **event_args):
        self._status = self.status_box.selected_value
        self._bounties()

    # ---- feedback
    def _feedback(self):
        d = state.call("list_feedback", None)
        if not d:
            return
        items = [i for i in d["items"] if self._filter == "all" or i["status"] == self._filter]
        self.feedback_panel.items = items
        self.no_feedback.visible = not items
        labels = {"new": "New", "read": "Read", "done": "Done", "all": "All"}
        for key, el in (("new", self.f_new), ("read", self.f_read), ("done", self.f_done), ("all", self.f_all)):
            count = len(d["items"]) if key == "all" else d["counts"].get(key, 0)
            el.classes["on"] = key == self._filter
            anvil.js.get_dom_node(el).textContent = "%s (%d)" % (labels[key], count)

    def fb_filter_click(self, event):
        self._filter = event.currentTarget.getAttribute("data-f")
        self._feedback()

    def _feedback_changed(self, **event_args):
        self._feedback()

    # ---- users
    def _users(self, query=None):
        d = state.call("list_users", query or None)
        if not d:
            return
        self.users_panel.items = d["users"]
        self.users_count.text = state.plural(d["total"], "person", "people")

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._users(self.search_box.text)

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self._users(self.search_box.text)

    # ---- demo data
    def _demo(self):
        d: dict = (state.call("admin_overview") or {}).get("demo") or {"state": "?", "counts": {}}
        counts = ", ".join("%s %s" % (v, k) for k, v in d["counts"].items())
        self.demo_status.text = "Status: %s · %s" % (d["state"], counts)
        self.demo_load_button.text = "Reload demo data" if d["state"] == "loaded" else "Load demo data"

    @handle("demo_load_button", "click")
    def demo_load_button_click(self, **event_args):
        if confirm("Demo people and content are added (any old demo rows are replaced).", title="Load the demo data?",
                   buttons=[("Cancel", False), ("Load", True)], role="app-dialog"):
            if state.call("demo_load"):
                state.toast("Done", "ok")
                self._demo()

    @handle("demo_remove_button", "click")
    def demo_remove_button_click(self, **event_args):
        if confirm("Every demo row is deleted. Real data stays.", title="Remove the demo data?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("demo_remove"):
                state.toast("Done", "ok")
                self._demo()
