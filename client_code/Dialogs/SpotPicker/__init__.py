import json

from anvil import *
from anvil.js import window

from ._anvil_designer import SpotPickerTemplate
from ... import sr, state


class SpotPicker(SpotPickerTemplate):
    """The spot picker: a map with a draggable pin, "use my location", a place search (Nominatim, only on a tap) and
    the area name. Closes with {lat, lng, label, street}, or None."""

    def __init__(self, title="Where are you?", text="", ok="Save", pin_label="Here", label="", label_title="Name of the area",
                 hint="Tap the map to move the pin.", lat=None, lng=None, **properties):
        super().__init__(**properties)
        self.title_label.text = title
        state.heading(self.title_label, 2)
        self.text_label.text = text
        self.text_label.visible = bool(text)
        self.ok_button.text = ok
        self.hint_label.text = hint
        self.dom_nodes["label_cap"].textContent = label_title
        self.label_box.text = label or ""
        state.set_control_attr(self.label_box, "maxlength", 60)
        state.set_control_attr(self.search_box, "aria-label", "Search a place")
        self._pin = pin_label
        self._pos: dict = {"lat": lat, "lng": lng} if lat is not None else {}
        self._auto = not label
        self._street = ""
        self._ctl = None
        self.results_box.visible = False
        self.results_panel.add_event_handler("x-pick", self._picked)

    @handle("", "show")
    def form_show(self, **event_args):
        p = self._pos
        self._ctl = window.SR.mapSpot(self.dom_nodes["map"], p["lat"] if p else None, p["lng"] if p else None,
                                      self._pin, self._map_pick)

    @handle("", "hide")
    def form_hide(self, **event_args):
        if self._ctl is not None:
            self._ctl.destroy()
            self._ctl = None

    def _set(self, lat, lng, zoom=None, look_up=False):
        self._pos = {"lat": float(lat), "lng": float(lng)}
        self.error_label.visible = False
        if self._ctl is not None:
            self._ctl.setPos(lat, lng, zoom)
        if look_up:
            r = sr.plain(window.SR.reverse(lat, lng))
            self._street = r.get("street") or ""
            if r.get("area") and self._auto:
                self.label_box.text = r["area"]

    def _map_pick(self, lat, lng):
        self._set(lat, lng, None, True)

    @handle("label_box", "change")
    def label_box_change(self, **event_args):
        self._auto = not (self.label_box.text or "").strip()

    @handle("locate_button", "click")
    def locate_button_click(self, **event_args):
        self.locate_button.enabled = False
        try:
            r = sr.plain(window.SR.locate(True))
        finally:
            self.locate_button.enabled = True
        if r.get("error"):
            self._fail(r["error"])
        else:
            self._set(r["lat"], r["lng"], 16, True)

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self.search_button_click()

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        text = (self.search_box.text or "").strip()
        if len(text) < 2:
            return
        self.search_button.enabled = False
        try:
            r = sr.plain(window.SR.search(text))
        finally:
            self.search_button.enabled = True
        self.results_box.visible = True
        if isinstance(r, dict):
            self.results_panel.items = []
            self.results_note.text = r.get("error") or ""
        else:
            self.results_panel.items = r
            self.results_note.text = "" if r else "No place found. Try another spelling, or tap the map."
        self.results_note.visible = bool(self.results_note.text)

    def _picked(self, **event_args):
        place: dict = event_args["place"]
        if self._auto or not (self.label_box.text or "").strip():
            self.label_box.text = place["name"]
            self._auto = True
        self._street = place.get("street") or ""
        self._set(place["lat"], place["lng"], 16, False)
        self.results_box.visible = False

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        label = (self.label_box.text or "").strip()
        if not self._pos:
            self._fail("Put a pin on the map first (tap the map, use your location, or search).")
            return
        if len(label) < 2:
            self._fail("Give the area a name, like a neighbourhood.")
            self.label_box.focus()
            return
        self.raise_event("x-close-alert", value={"lat": self._pos["lat"], "lng": self._pos["lng"], "label": label,
                                                 "street": self._street})

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True
