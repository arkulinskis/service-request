import datetime

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import PostTemplate
from ... import router, sr, state

SIZE_INDEX = {"small": 0, "medium": 1, "large": 2}


class Post(PostTemplate):
    """Post a bounty (#post, #post/<task>) in 5 steps: the task (40 kinds), the details and photos, where (map pin +
    a private street address), the bounty + quality bonus + checklist + payment method, then review against the rules.
    The server checks everything again (Bounties.post_bounty: $20-$500, bonus $5 up to the bounty, bar 50-100%) and may
    send it to the moderators first."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.C = sr.catalog()
        self.step = 0
        self.seen = 0
        self.cat_filter = "season"
        self.query = ""
        self.use_bonus = True
        self.P: dict = {"task": None, "title": "", "details": "", "size": "medium", "when_date": "", "when_note": "", "lat": None,
                        "lng": None, "area": "", "address": "", "base": 20, "bonus": 10, "bar": 80, "checklist": [],
                        "pay_method": "either", "photo_keys": []}
        try:
            jobs = anvil.server.call_s("get_jobs")
            self.limit = (jobs.get("limits") or {}).get("post")
        except Exception:
            self.limit = None
        n = self.dom_nodes
        date_input = state.control(self.date_box)
        date_input.setAttribute("type", "date")
        today = datetime.date.today().isoformat()
        date_input.setAttribute("min", today)
        state.set_control_attr(self.q_box, "aria-label", "Search tasks")
        state.set_control_attr(self.base_box, "aria-label", "Bounty in dollars")
        state.set_control_attr(self.base_box, "min", self.C["min_base"])
        state.set_control_attr(self.base_box, "max", self.C["max_base"])
        state.set_control_attr(self.base_box, "step", 1)
        state.set_control_attr(self.minus_button, "aria-label", "Minus 5 dollars")
        state.set_control_attr(self.plus_button, "aria-label", "Plus 5 dollars")
        state.set_control_attr(self.title_box, "maxlength", 90)
        state.set_control_attr(self.details_box, "maxlength", 1500)
        state.set_control_attr(self.when_box, "maxlength", 80)
        state.set_control_attr(self.address_box, "maxlength", 160)
        state.control(self.q_box).addEventListener("input", self._q_input)
        state.control(self.base_box).addEventListener("input", self._base_input)
        for node in (n["size_small"], n["size_medium"], n["size_large"]):
            node.addEventListener("change", self._size_change)
        for node in (n["pay_cash"], n["pay_etransfer"], n["pay_either"]):
            node.addEventListener("change", self._pay_change)
        n["use_bonus"].addEventListener("change", self._bonus_toggle)
        self.cats_panel.add_event_handler("x-chip", self._cat_chip)
        self.tasks_panel.add_event_handler("x-task", self._task_pick)
        self.presets_panel.add_event_handler("x-chip", self._preset)
        self.bonus_panel.add_event_handler("x-chip", self._bonus_chip)
        self.bar_panel.add_event_handler("x-chip", self._bar_chip)
        self.checklist_panel.add_event_handler("x-ci", self._ci)
        self.checklist_panel.add_event_handler("x-crm", self._crm)
        self.not_allowed_panel.items = [{"text": x, "cls": "ps-no"} for x in self.C["not_allowed"][:4]]
        if args and args[0] in self.C["by_key"]:
            self._choose(args[0])
            self.step = self.seen = 1
        self._frame()

    def task(self):
        return self.C["by_key"].get(self.P["task"])

    def _choose(self, key):
        t = self.C["by_key"].get(key)
        if not t:
            return
        changed = self.P["task"] != key
        self.P["task"] = key
        if changed:
            P = self.P
            P["title"] = "" if t["key"] == "other" else t["name"]
            P["checklist"] = list(t["checklist"])
            P["base"] = t["prices"][SIZE_INDEX[P["size"]]]
            P["bonus"] = max(5, min(P["base"], (sr.js_round(P["base"] / 4.0 / 5) * 5) or 5)) if self.use_bonus else 0

    # ------------------------------------------------------------------ drawing the current step
    def _frame(self):
        n = self.dom_nodes
        for i, (btn, num) in enumerate([(n["st0"], n["sb0"]), (n["st1"], n["sb1"]), (n["st2"], n["sb2"]), (n["st3"], n["sb3"]), (n["st4"], n["sb4"])]):
            btn.className = "on" if i == self.step else ("done" if (i < self.seen or i < self.step) else "")
            btn.disabled = i > self.seen
            if i == self.step:
                btn.setAttribute("aria-current", "step")
            else:
                btn.removeAttribute("aria-current")
            num.textContent = "✓" if i < self.step else str(i + 1)
        self.limit_box.visible = bool(self.limit)
        n["limit_text"].textContent = self.limit or ""
        steps = [self.step_task, self.step_details, self.step_where, self.step_bounty, self.step_review]
        for i, part in enumerate(steps):
            part.visible = i == self.step
        self.prev_button.visible = self.step > 0
        self.next_button.visible = self.step < 4
        self.next_button.enabled = not (self.step == 0 and not self.P["task"])
        self.post_button.visible = self.step == 4
        self.post_button.enabled = not self.limit
        [self._step_task, self._step_details, self._step_where, self._step_bounty, self._step_review][self.step]()
        self._aside()
        window.scrollTo(0, 0)

    def _step_task(self):
        C = self.C
        cats = [("season", "In season", "sparkle"), ("all", "All 40", "grid")] + [(c["key"], c["name"], c["icon"]) for c in C["categories"]]
        self.cats_panel.items = [{"key": k, "label": label, "icon": icon, "on": self.cat_filter == k and not self.query} for k, label, icon in cats]
        q = self.query.lower()
        out = []
        for t in C["tasks"]:
            if q:
                if q in (t["name"] + " " + t["blurb"] + " " + C["cat_by_key"][t["cat"]]["name"]).lower():
                    out.append(t)
            elif self.cat_filter == "season":
                if sr.in_season(t) or t["key"] == "other":
                    out.append(t)
            elif self.cat_filter == "all" or t["cat"] == self.cat_filter:
                out.append(t)
        self.tasks_panel.items = [{"t": t, "on": self.P["task"] == t["key"]} for t in out]
        self.dom_nodes["no_task"].hidden = bool(out)

    def _step_details(self):
        P, t, n = self.P, self.task(), self.dom_nodes
        n["task_name"].textContent = t["name"]
        self.title_box.text = P["title"]
        self.details_box.text = P["details"]
        self.details_box.placeholder = t["blurb"] + " Where are the tools? Anything to know (dog, gate code, parking)?"
        for key, node, price in (("small", n["size_small"], n["price_small"]), ("medium", n["size_medium"], n["price_medium"]),
                                 ("large", n["size_large"], n["price_large"])):
            node.checked = P["size"] == key
            price.textContent = "~" + sr.money(t["prices"][SIZE_INDEX[key]])
        self.date_box.text = P["when_date"]
        self.when_box.text = P["when_note"]
        k = len(P["photo_keys"])
        n["photo_count"].hidden = not k
        n["photo_count"].textContent = "%s added. Add more below or keep these." % sr.plural(k, "photo")
        self.uploader.setup(max(0, 4 - k), "Add a photo")

    def _step_where(self):
        P, n = self.P, self.dom_nodes
        spot = (state.me() or {}).get("spot")
        if P["lat"] is None:
            self.spot_map.message("No spot yet: pick it on the map.")
        else:
            self.spot_map.point(P["lat"], P["lng"], True, "Job", zoom_control=False)
        self.pick_button.text = "Pick the spot on the map" if P["lat"] is None else "Move the pin"
        self.myarea_button.visible = bool(spot) and P["lat"] is None
        if spot:
            self.myarea_button.text = "Use my area (%s)" % spot.get("label")
        n["area_line"].hidden = not P["area"]
        sr.rich(n["area_line"], "<b>Area shown:</b> " + sr.esc(P["area"]))
        self.address_box.text = P["address"]

    def _step_bounty(self):
        P, t, C = self.P, self.task(), self.C
        self.dom_nodes["bounty_lead"].textContent = "The minimum is %s. Fair bounties get done first." % sr.money(C["min_base"])
        self.base_box.text = P["base"]
        self.presets_panel.items = [{"key": t["prices"][i], "label": "%s ~%s" % (s["name"], sr.money(t["prices"][i]))} for i, s in enumerate(C["sizes"])]
        self.dom_nodes["use_bonus"].checked = self.use_bonus
        self.bonus_box.visible = self.use_bonus
        self._money_chips()
        self._checklist()
        for key, node in (("cash", self.dom_nodes["pay_cash"]), ("etransfer", self.dom_nodes["pay_etransfer"]), ("either", self.dom_nodes["pay_either"])):
            node.checked = P["pay_method"] == key
        self._explain()

    def _money_chips(self):
        P = self.P
        self.bonus_panel.items = [{"key": v, "label": "+" + sr.money(v), "on": P["bonus"] == v} for v in (5, 10, 15, 20, 30)]
        self.bar_panel.items = [{"key": v, "label": "%d%%" % v, "on": P["bar"] == v} for v in (60, 70, 80, 90, 100)]

    def _checklist(self):
        items = self.P["checklist"]
        self.checklist_panel.items = [{"i": i, "text": c} for i, c in enumerate(items)]
        self.add_item_button.visible = len(items) < 8

    def _step_review(self):
        P, t, n = self.P, self.task(), self.dom_nodes
        n["sum_task"].textContent = t["name"]
        n["sum_title"].textContent = P["title"]
        n["sum_details"].textContent = P["details"]
        n["sum_when"].textContent = sr.when(P)
        n["sum_size"].textContent = P["size"]
        n["sum_where"].textContent = P["area"] + " · " + P["address"]
        sr.rich(n["sum_bounty"], "<b>%s</b>%s" % (sr.esc(sr.money(P["base"])), (" + %s bonus at %s%%" % (sr.esc(sr.money(P["bonus"])), P["bar"])) if self.use_bonus else ""))
        n["sum_pay"].textContent = [m["name"] for m in self.C["pay_methods"] if m["key"] == P["pay_method"]][0]
        n["sum_checklist"].textContent = " · ".join(P["checklist"])
        n["sum_photos"].textContent = str(len(P["photo_keys"]))
        for node in (n["rule0"], n["rule1"], n["rule2"]):
            node.checked = False
        self.error_label.visible = False

    def _aside(self):
        P = self.P
        has = bool(P["task"])
        self.how_box.visible = not has
        self.preview_box.visible = has
        self.rules_box.visible = has
        if not has:
            return
        t = self.task()
        me = state.me() or {}
        self.preview_panel.items = [{"id": "preview", "title": P["title"] or t["name"], "task": P["task"], "area": P["area"] or "Your area",
                                     "dist": None, "when_date": P["when_date"], "when_note": P["when_note"], "pay": P["pay_method"],
                                     "vehicle": t.get("vehicle"), "base": P["base"], "bonus": P["bonus"] if self.use_bonus else 0,
                                     "bar": P["bar"], "offers": 0, "poster": {"name": me.get("short") or me.get("name"), "record": {}}}]

    def _explain(self):
        P = self.P
        k = len([c for c in P["checklist"] if c.strip()]) or 1
        need = sr.need(k, P["bar"])
        each = sr.js_round(100.0 / k)
        if self.use_bonus:
            html = (sr.icon("ruler") + " With %d items, each is worth %d%%. Tick <b>%d of %d</b> (%d%%) and you pay <b>%s</b>; below that you pay <b>%s</b>." % (
                k, each, need, k, P["bar"], sr.esc(sr.money(P["base"] + P["bonus"])), sr.esc(sr.money(P["base"]))))
        else:
            html = sr.icon("ruler") + " With %d items, each is worth %d%% of the score. You pay <b>%s</b> once you validate." % (k, each, sr.esc(sr.money(P["base"])))
        sr.rich(self.dom_nodes["explain"], html)
        self._aside()

    # ------------------------------------------------------------------ reading + checking each step
    def _collect(self):
        P, n = self.P, self.dom_nodes
        if self.step == 1:
            P["title"] = (self.title_box.text or "").strip()
            P["details"] = (self.details_box.text or "").strip()
            P["when_date"] = state.control(self.date_box).value or ""
            P["when_note"] = (self.when_box.text or "").strip()
            for k in self.uploader.keys():
                if k not in P["photo_keys"]:
                    P["photo_keys"].append(k)
        if self.step == 2:
            P["address"] = (self.address_box.text or "").strip()
        if self.step == 3:
            P["base"] = self._base_value()
            P["checklist"] = [c.strip() for c in P["checklist"]]

    def _base_value(self):
        try:
            return int(round(float(self.base_box.text or 0)))
        except Exception:
            return 0

    def _check(self):
        P, C = self.P, self.C
        if self.step == 0 and not P["task"]:
            return "Pick a task first."
        if self.step == 1:
            if self.uploader.busy():
                return "Wait for the photos to finish uploading."
            if len(P["title"]) < 6:
                return "Give it a title (at least 6 characters)."
            if len(P["details"]) < 15:
                return "Describe the job in a sentence or two."
        if self.step == 2:
            if P["lat"] is None:
                return "Pick the spot on the map."
            if len(P["address"]) < 5:
                return "Add the street address (only your helper sees it)."
        if self.step == 3:
            if P["base"] < C["min_base"]:
                return "The minimum bounty is %s." % sr.money(C["min_base"])
            if P["base"] > C["max_base"]:
                return "Bounties go up to %s." % sr.money(C["max_base"])
            if self.use_bonus and P["bonus"] > P["base"]:
                return "The bonus can't be more than the bounty."
            if len([c for c in P["checklist"] if c]) < 2:
                return "Keep at least 2 checklist items."
        return None

    def _go(self, to):
        self._collect()
        if to > self.step:
            err = self._check()
            if err:
                state.toast(err, "error")
                return
        self.step = to
        self.seen = max(self.seen, to)
        self._frame()

    def step_click(self, event):
        btn = event.currentTarget
        if not btn.disabled:
            self._go(int(btn.getAttribute("data-step")))

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self._go(self.step + 1)

    @handle("prev_button", "click")
    def prev_button_click(self, **event_args):
        self._go(self.step - 1)

    # ---- step 1
    def _q_input(self, event):
        self.query = self.q_box.text or ""
        self._step_task()

    def _cat_chip(self, **event_args):
        focus = state.focus_key()
        self.cat_filter = event_args["key"]
        self.query = ""
        self.q_box.text = ""
        self._step_task()
        state.refocus(self.cats_panel, focus)

    def _task_pick(self, **event_args):
        self._choose(event_args["key"])
        self.seen = max(self.seen, 1)
        self.step = 1
        self._frame()

    # ---- step 2
    def _size_change(self, event):
        value = event.currentTarget.value
        self.P["size"] = value
        if self.P["task"]:
            self.P["base"] = self.task()["prices"][SIZE_INDEX[value]]

    # ---- step 3
    @handle("pick_button", "click")
    def pick_button_click(self, **event_args):
        self._collect()
        P = self.P
        p = sr.pick_spot(title="Where is the job?", ok="Use this spot", pin_label="Job", label_title="Area shown on the board",
                         lat=P["lat"], lng=P["lng"], label=P["area"],
                         text="Put the pin on the house. The board only shows the area name and a circle about 500 m wide.")
        if not p:
            return
        P["lat"], P["lng"], P["area"] = p["lat"], p["lng"], p["label"]
        if p.get("street") and not P["address"]:
            P["address"] = p["street"]
        self._frame()

    @handle("myarea_button", "click")
    def myarea_button_click(self, **event_args):
        self._collect()
        s = (state.me() or {}).get("spot") or {}
        self.P["lat"], self.P["lng"], self.P["area"] = s.get("lat"), s.get("lng"), s.get("label") or ""
        self._frame()

    # ---- step 4
    def _set_base(self, value):
        C = self.C
        self.P["base"] = max(C["min_base"], min(C["max_base"], value))
        self.base_box.text = self.P["base"]
        self._explain()

    @handle("minus_button", "click")
    def minus_button_click(self, **event_args):
        self._set_base(self._base_value() - 5)

    @handle("plus_button", "click")
    def plus_button_click(self, **event_args):
        self._set_base(self._base_value() + 5)

    def _base_input(self, event):
        self.P["base"] = self._base_value()
        self._explain()

    def _preset(self, **event_args):
        self.P["base"] = event_args["key"]
        self.base_box.text = self.P["base"]
        self._explain()

    def _bonus_toggle(self, event):
        self.use_bonus = bool(self.dom_nodes["use_bonus"].checked)
        self.bonus_box.visible = self.use_bonus
        self._explain()

    def _bonus_chip(self, **event_args):
        focus = state.focus_key()
        self.P["bonus"] = event_args["key"]
        self._money_chips()
        self._explain()
        state.refocus(self.bonus_panel, focus)

    def _bar_chip(self, **event_args):
        focus = state.focus_key()
        self.P["bar"] = event_args["key"]
        self._money_chips()
        self._explain()
        state.refocus(self.bar_panel, focus)

    def _ci(self, **event_args):
        self.P["checklist"][event_args["i"]] = event_args["text"]
        self._explain()

    def _crm(self, **event_args):
        del self.P["checklist"][event_args["i"]]
        self._checklist()
        self._explain()

    @handle("add_item_button", "click")
    def add_item_button_click(self, **event_args):
        self.P["checklist"].append("")
        self._checklist()
        self._explain()
        inputs = anvil.js.get_dom_node(self.checklist_panel).querySelectorAll("input")
        if inputs.length:
            getattr(getattr(inputs, "item")(inputs.length - 1), "focus")()

    def _pay_change(self, event):
        self.P["pay_method"] = event.currentTarget.value
        self._aside()

    # ---- step 5: post it
    @handle("post_button", "click")
    def post_button_click(self, **event_args):
        n = self.dom_nodes
        if not (n["rule0"].checked and n["rule1"].checked and n["rule2"].checked):
            self._fail("Tick the three promises first.")
            return
        data = dict(self.P)
        data["bonus"] = self.P["bonus"] if self.use_bonus else 0
        data["checklist"] = [c for c in self.P["checklist"] if c]
        self.post_button.enabled = False
        try:
            r = anvil.server.call("post_bounty", data)
        finally:
            self.post_button.enabled = not self.limit
        if r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return
        if r.get("status") == "review":
            alert("Your bounty goes to a moderator first, because: %s. Most checks take a few hours. You'll see it in My jobs." % "; ".join(r.get("flags") or []),
                  title="Almost there", role="app-dialog")
        else:
            sr.confetti()
            state.toast("Posted! (We hid contact details: chat in the app.)" if r.get("hidden_contact") else "Your bounty is on the board!", "ok")
        router.go("bounty", r["id"])

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True

    def leave(self):
        pass
