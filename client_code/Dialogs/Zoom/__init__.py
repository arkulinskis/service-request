from anvil import *

from ._anvil_designer import ZoomTemplate
from ... import sr


class Zoom(ZoomTemplate):
    """A photo, big."""

    def __init__(self, key="", **properties):
        super().__init__(**properties)
        self.dom_nodes["img"].src = sr.photo(key)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
