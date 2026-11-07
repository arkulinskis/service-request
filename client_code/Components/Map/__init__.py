import json

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import MapTemplate


class Map(MapTemplate):
    """The Leaflet map engine (window.SR.mapBoard / SR.mapPoint) on a page.

        m.board(center, on_open, on_hover)  the board map; then m.pins(items, spot) and m.hot(id, on)
        m.point(lat, lng, exact, label, zoom_control=True)
        m.message(text)                      no map, just a line of text (e.g. "No spot yet")
    It draws once it is on the page (show) and destroys the Leaflet map when hidden, so maps never pile up."""

    def __init__(self, **properties):
        self._height = ""
        self._spec: dict = {}
        self._ctl = None
        self._shown = False
        self._pins = None
        super().__init__(**properties)

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value or ""  # applied when the map is drawn (the template may not exist yet here)

    # ---- what to draw
    def board(self, center, on_open, on_hover):
        self._spec = {"kind": "board", "center": center, "open": on_open, "hover": on_hover}
        self._mount()

    def pins(self, items, spot=None):
        small = [{"id": b["id"], "lat": b.get("lat"), "lng": b.get("lng"), "base": b["base"], "bonus": b.get("bonus") or 0}
                 for b in items]
        self._pins = (json.dumps(small), json.dumps(spot) if spot else None)
        if self._ctl is not None and self._spec.get("kind") == "board":
            self._ctl.pins(self._pins[0], self._pins[1])

    def hot(self, bounty_id, on):
        if self._ctl is not None and self._spec.get("kind") == "board":
            self._ctl.hot(bounty_id, bool(on))

    def point(self, lat, lng, exact=False, label="Job", zoom_control=True):
        self._spec = {"kind": "point", "lat": lat, "lng": lng, "exact": exact, "label": label, "zoom": zoom_control}
        self._mount()

    def message(self, text):
        self._unmount()
        self._spec = {}
        box = self.dom_nodes["box"]
        msg = window.document.createElement("div")
        msg.className = "sr-map-msg"
        msg.textContent = text
        box.innerHTML = ""
        box.appendChild(msg)

    def resize(self):
        if self._ctl is not None:
            self._ctl.resize()

    # ---- the engine
    def _mount(self):
        if not self._shown or not self._spec:
            return
        self._unmount()
        box = self.dom_nodes["box"]
        if self._height:
            box.style.height = self._height
        s = self._spec
        if s["kind"] == "board":
            hooks = window.JSON.parse("{}")
            hooks.open = s["open"]
            hooks.hover = s["hover"]
            self._ctl = window.SR.mapBoard(box, window.JSON.parse(json.dumps(s["center"])), hooks)
            if self._pins is not None:
                self._ctl.pins(self._pins[0], self._pins[1])
        else:
            self._ctl = window.SR.mapPoint(box, s["lat"], s["lng"], bool(s["exact"]), s["label"], bool(s["zoom"]))

    def _unmount(self):
        if self._ctl is not None:
            self._ctl.destroy()
            self._ctl = None

    @handle("", "show")
    def form_show(self, **event_args):
        self._shown = True
        self._mount()

    @handle("", "hide")
    def form_hide(self, **event_args):
        self._shown = False
        self._unmount()
