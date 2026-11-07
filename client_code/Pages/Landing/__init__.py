import json

from anvil import *
from anvil.js import window

from ._anvil_designer import LandingTemplate
from ... import sr, state

YT_VIDEO = "_Qj7nniw9cw"


class Landing(LandingTemplate):
    """What visitors see first (also #landing = "About" for members): the promise on a drawn neighbourhood map with
    bounty pins, the video, both sides, the quality bonus, the anti-scam measures, the 40 tasks, FAQ."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = state.me()
        self.guest_cta.visible = not me
        self.member_cta.visible = bool(me)
        state.set_attr(self.band_link, "href", "#post" if me else "#auth/signup")
        self.dom_nodes["band_text"].textContent = "Post a bounty" if me else "Join free"
        cat = sr.catalog()
        pins, seen = [], set()
        for t in cat["tasks"]:
            if t["cat"] not in seen and len(pins) < 7:
                seen.add(t["cat"])
                pins.append({"cat": t["cat"], "icon": sr.cat(t["cat"])["icon"], "name": t["name"], "price": (t.get("prices") or [20])[0]})
        window.SR.heroArt(self.dom_nodes["art"], json.dumps(pins))
        self.wall_panel.items = [{"t": t, "member": bool(me)} for t in cat["tasks"]]
        self.dom_nodes["yt_cover"].addEventListener("click", self._play)

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="Service Request video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
