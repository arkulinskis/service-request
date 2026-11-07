from anvil import *

from ._anvil_designer import WallLinkTemplate
from ... import router, sr


class WallLink(WallLinkTemplate):
    """One of the 40 tasks on the landing page's wall. item = {t: task, member: bool}: members go straight to the post
    wizard with that task, visitors to sign-up."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t = self.item["t"]
        d = self.dom_nodes
        d["a"].setAttribute("href", router.href("post", t["key"]) if self.item["member"] else "#auth/signup")
        sr.fill_ti(d["ti"], t["key"], "sm")
        d["name"].textContent = t["name"]
        d["price"].textContent = "from " + sr.money(t["prices"][0])
