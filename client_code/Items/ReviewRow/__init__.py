from anvil import *

from ._anvil_designer import ReviewRowTemplate
from ... import sr


class ReviewRow(ReviewRowTemplate):
    """A review on a neighbour's page. item = {stars, author, role, bounty, at, text, tags}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        sr.fill_stars(d["stars"], r["stars"])
        d["author"].textContent = r.get("author") or ""
        d["role"].textContent = "as a helper" if r.get("role") == "helper" else "as a poster"
        d["meta"].textContent = (r.get("bounty") or "") + " · " + sr.ago(r.get("at"))
        d["text"].hidden = not r.get("text")
        d["text"].textContent = r.get("text") or ""
        self.tags_panel.items = [{"text": t} for t in r.get("tags") or []]
        self.tags_panel.visible = bool(r.get("tags"))
