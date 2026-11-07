from anvil import *

from ._anvil_designer import PhotoThumbTemplate
from ... import sr


class PhotoThumb(PhotoThumbTemplate):
    """A photo thumbnail; a click shows it big. item = {key, alt}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        d = self.dom_nodes
        d["img"].src = sr.photo(self.item["key"], True)
        d["img"].alt = self.item.get("alt") or "Photo"
        d["btn"].setAttribute("aria-label", "Show the photo bigger")

    def btn_click(self, event):
        sr.zoom(self.item["key"])
