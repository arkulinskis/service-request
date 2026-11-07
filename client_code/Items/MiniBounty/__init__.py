from anvil import *

from ._anvil_designer import MiniBountyTemplate
from ... import router, sr


class MiniBounty(MiniBountyTemplate):
    """One of a neighbour's open bounties. item = {id, task, title, area, base}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        d = self.dom_nodes
        d["a"].setAttribute("href", router.href("bounty", b["id"]))
        sr.fill_ti(d["ti"], b["task"], "sm")
        d["title"].textContent = b["title"]
        d["area"].textContent = b.get("area") or ""
        sr.fill_tag(d["tag"], b["base"], size="sm", sub="")
