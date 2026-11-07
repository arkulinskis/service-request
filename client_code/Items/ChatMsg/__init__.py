from anvil import *

from ._anvil_designer import ChatMsgTemplate
from ... import sr


class ChatMsg(ChatMsgTemplate):
    """A chat message. item = {mine, who, text, at}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m = self.item
        d = self.dom_nodes
        d["msg"].classList.toggle("mine", bool(m.get("mine")))
        d["text"].textContent = m["text"]
        d["meta"].textContent = ("You" if m.get("mine") else m.get("who") or "") + " · " + sr.fmt_datetime(m.get("at"))
