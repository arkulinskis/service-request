from anvil import *

from ._anvil_designer import LogRowTemplate
from ... import sr


class LogRow(LogRowTemplate):
    """A timeline entry. item = {at, who: poster | helper | system | admin, text}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        d = self.dom_nodes
        d["li"].className = "bt-log-li " + (it.get("who") or "")
        d["at"].textContent = sr.fmt_datetime(it.get("at"))
        d["text"].textContent = it.get("text") or ""
