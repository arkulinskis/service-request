from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import BoardTemplate
from ... import router, sr, state

DEFAULT: dict = {"q": "", "cat": "all", "sort": "new", "dist": "any", "pay": "any", "bonus": False}
SORTS = [("Newest", "new"), ("Highest bounty", "money"), ("Closest", "near"), ("Soonest", "soon")]
DISTS = [("Any distance", "any"), ("Within 2 km", "2"), ("Within 5 km", "5"), ("Within 10 km", "10"), ("Within 25 km", "25")]
PAYS = [("Any payment", "any"), ("Cash", "cash"), ("e-Transfer", "etransfer")]


class Board(BoardTemplate):
    """The bounty board (#board, the home page). Open bounties near you (your saved area, your location, or Montréal),
    searchable, with category chips, filters (kept in this browser as 'board.f') and a map of price-tag pins.
    Anyone can browse."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.F: dict = dict(DEFAULT)
        saved = sr.stored("board.f", {}) or {}
        for k in ("cat", "sort", "dist", "pay", "bonus"):
            if k in saved:
                self.F[k] = saved[k]
        self.guest_spot: dict = {}
        self.cat = sr.catalog()
        self.sort_box.items = SORTS
        self.dist_box.items = DISTS
        self.pay_box.items = PAYS
        for box, label in ((self.sort_box, "Sort"), (self.dist_box, "Distance"), (self.pay_box, "Payment")):
            state.set_control_attr(box, "aria-label", label)
        state.set_control_attr(self.search_box, "aria-label", "Search bounties")
        state.control(self.search_box).addEventListener("input", self._typed)
        self.cards_panel.add_event_handler("x-hover", self._card_hover)
        self.chips_panel.add_event_handler("x-chip", self._chip)
        me = state.me()
        self.guest_band.visible = not me
        self.area_button.text = "Change area" if me else "Use my location"
        self._load()

    # ---- data
    def _load(self):
        gs = self.guest_spot
        self.data = anvil.server.call("get_board", gs.get("lat"), gs.get("lng"))
        me = state.me() or {}
        spot = me.get("spot") or {}
        self.dom_nodes["area_name"].textContent = spot.get("label") or ("you" if gs else "Montréal")
        self.map.board(self.data["center"], self._pin_open, self._pin_hover)
        self._controls()
        self._draw()

    def _controls(self):
        F = self.F
        self.sort_box.selected_value = F["sort"]
        self.dist_box.selected_value = str(F["dist"])
        self.pay_box.selected_value = F["pay"]
        self.bonus_box.checked = bool(F["bonus"])
        self.search_box.text = str(F["q"] or "")
        self._chips()

    def _chips(self):
        cats = [("all", "All", "grid"), ("season", "In season", "sparkle")] + [
            (c["key"], c["name"], c["icon"]) for c in self.cat["categories"] if c["key"] != "other"]
        self.chips_panel.items = [{"key": k, "label": label, "icon": icon, "on": self.F["cat"] == k} for k, label, icon in cats]

    def _filtered(self):
        F = self.F
        q = str(F["q"] or "").strip().lower()
        top = None if F["dist"] == "any" else float(F["dist"])
        out = []
        for b in self.data["items"]:
            t = sr.task(b["task"])
            if F["cat"] == "season" and not sr.in_season(t):
                continue
            if F["cat"] not in ("all", "season") and b["cat"] != F["cat"]:
                continue
            if top is not None and b.get("dist") is not None and b["dist"] > top:
                continue
            if F["pay"] != "any" and b["pay"] != F["pay"] and b["pay"] != "either":
                continue
            if F["bonus"] and not b.get("bonus"):
                continue
            if q and q not in (" ".join([b["title"], b.get("details") or "", b["area"], t["name"], sr.cat(b["cat"])["name"]])).lower():
                continue
            out.append(b)
        if F["sort"] == "new":
            out.sort(key=lambda b: b["created"] or "", reverse=True)
        elif F["sort"] == "money":
            out.sort(key=lambda b: b["base"] + (b.get("bonus") or 0), reverse=True)
        elif F["sort"] == "near":
            out.sort(key=lambda b: 1e9 if b.get("dist") is None else b["dist"])
        elif F["sort"] == "soon":
            out.sort(key=lambda b: b.get("when_date") or "9999")
        return out

    def _draw(self):
        d = self.data
        items = self._filtered()
        sr.rich(self.dom_nodes["summary"], "<b>%s</b> · <b>%s</b> waiting to be earned" % (
            sr.esc(sr.plural(d["total"], "open bounty", "open bounties")), sr.esc(sr.money(d["money"]))))
        n, total = len(items), len(d["items"])
        self.dom_nodes["count"].textContent = ("Showing all %d" % n) if n == total else ("%d of %d match" % (n, total))
        self.cards_panel.items = items
        self.empty_box.visible = not items
        self.map.pins(items, self.guest_spot or d.get("spot"))
        F = self.F
        sr.store("board.f", {"cat": F["cat"], "sort": F["sort"], "dist": F["dist"], "pay": F["pay"], "bonus": F["bonus"]})

    # ---- map <-> cards
    def _pin_open(self, bounty_id):
        router.go("bounty", bounty_id)

    def _pin_hover(self, bounty_id, on):
        node = anvil.js.get_dom_node(self.cards_panel).querySelector('[data-card="%s"]' % window.CSS.escape(str(bounty_id)))
        if node:
            node.classList.toggle("hot", bool(on))

    def _card_hover(self, **event_args):
        self.map.hot(event_args["bounty_id"], event_args["on"])

    # ---- filters
    def _chip(self, **event_args):
        focus = state.focus_key()
        self.F["cat"] = event_args["key"]
        self._chips()
        self._draw()
        state.refocus(self.chips_panel, focus)

    @handle("sort_box", "change")
    def sort_box_change(self, **event_args):
        self.F["sort"] = self.sort_box.selected_value
        self._draw()

    @handle("dist_box", "change")
    def dist_box_change(self, **event_args):
        self.F["dist"] = self.dist_box.selected_value
        self._draw()

    @handle("pay_box", "change")
    def pay_box_change(self, **event_args):
        self.F["pay"] = self.pay_box.selected_value
        self._draw()

    @handle("bonus_box", "change")
    def bonus_box_change(self, **event_args):
        self.F["bonus"] = bool(self.bonus_box.checked)
        self._draw()

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self.search_button_click()

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self.F["q"] = self.search_box.text or ""
        self._draw()

    def _typed(self, event):
        if not self.search_box.text and self.F["q"]:
            self.F["q"] = ""
            self._draw()

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        self.F = dict(DEFAULT)
        self._controls()
        self._draw()

    # ---- list / map on phones
    def _show(self, which):
        self.dom_nodes["split"].setAttribute("data-show", which)
        self.show_list.classes["on"] = which == "list"
        self.show_map.classes["on"] = which == "map"
        sr.later(self.map.resize, 60)

    def show_list_click(self, event):
        self._show("list")

    def show_map_click(self, event):
        self._show("map")

    # ---- area
    def area_click(self, event):
        self.area_button_click()

    @handle("area_button", "click")
    def area_button_click(self, **event_args):
        if state.me():
            if sr.edit_area():
                self._load()
            return
        r = sr.plain(window.SR.locate(False))
        if r.get("error"):
            state.toast("We couldn't get your location. Showing Montréal.", "error")
            return
        self.guest_spot = {"lat": r["lat"], "lng": r["lng"]}
        self._load()
