from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import FlyerTemplate
from ... import router, sr

TABS = 8
QR_SRC = "_/theme/qrcode.js"


class Flyer(FlyerTemplate):
    """A printable street flyer (#flyer/<bounty id> or #flyer), public. For an open bounty: the task, area, date, price
    tag, a QR code to the bounty and 8 tear-off tabs with the link. Without an id (or when the bounty isn't open): the
    general "post a job / earn nearby" flyer that links to the landing page. Only public card data is used (the area,
    never the address or a name). The QR code is drawn by theme/assets/qrcode.js (qrcode-generator, MIT), loaded
    the first time a flyer opens; print styles in app.css hide the app's header, footer and these tools."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.id = args[0] if args else ""
        self._link = ""
        sr.catalog()
        base = window.location.origin + window.location.pathname
        if self.id:
            res = anvil.server.call("get_bounty", self.id)
            b = (res or {}).get("bounty") if (res or {}).get("ok") is not False else None
            if b and b.get("status") == "open":
                return self._bounty(b, base + router.href("bounty", self.id))
            self.note_label.text = "That bounty isn't open any more, so here's the general flyer instead."
            self.note_label.visible = True
        self._general(base + "#landing")

    # ------------------------------------------------------------------ the two flyers
    def _bounty(self, b, link):
        n = self.dom_nodes
        router.set_title("Flyer: " + b["title"])
        n["back"].setAttribute("href", router.href("bounty", self.id))
        n["back_text"].textContent = "Back to the bounty"
        t = sr.task(b["task"])
        n["kicker"].textContent = "Help wanted nearby"
        n["title"].textContent = b["title"]
        sr.fill_ti(n["ti"], b["task"])
        n["task"].textContent = t["name"]
        facts = [("pin", "Around " + (b.get("area") or "the neighbourhood")), ("calendar", sr.when(b)),
                 ("wallet", sr.PAY.get(b.get("pay"), "Cash or e-Transfer"))]
        if b.get("vehicle"):
            facts.append(("route", "Needs a vehicle"))
        sr.rich(n["facts"], "".join("<li>%s<span>%s</span></li>" % (sr.icon(i), sr.esc(x)) for i, x in facts if x))
        sr.fill_tag(n["tag"], b["base"], b.get("bonus") or 0, b.get("bar") or 80, "big")
        n["line"].textContent = ("Plus a %s quality bonus when the checklist score reaches %s%%." % (sr.money(b["bonus"]), b.get("bar") or 80)
                                 if b.get("bonus") else "Paid when the job is done and checked.")
        n["qr_cap"].textContent = "Scan to send an offer"
        self._finish(link, (b["title"] or "")[:28], sr.money(b["base"]))

    def _general(self, link):
        n = self.dom_nodes
        router.set_title("Street flyer")
        n["other_link"].parentElement.hidden = True
        n["kicker"].textContent = "Neighbours helping neighbours"
        n["title"].textContent = "Need a hand? Want to earn?"
        sr.fill_ti(n["ti"], "leaves")
        n["task"].textContent = "Leaves, snow, junk, moving and 40 other small jobs"
        facts = [("plus", "Post a job from $20. A neighbour sends an offer, you pick."),
                 ("hand", "Students and neighbours: earn cash on your own street."),
                 ("check", "Photo proof and a checklist, with an optional quality bonus."),
                 ("wallet", "Paid directly in cash or Interac e-Transfer.")]
        sr.rich(n["facts"], "".join("<li>%s<span>%s</span></li>" % (sr.icon(i), sr.esc(x)) for i, x in facts))
        sr.fill_tag(n["tag"], 20, 0, 80, "big", sub="and up")
        n["line"].textContent = "Free to join. No fees for posting or helping."
        n["qr_cap"].textContent = "Scan to see the jobs near you"
        self._finish(link, "Service Request", "jobs from $20")

    def _finish(self, link, tab_title, tab_price):
        n = self.dom_nodes
        n["url"].textContent = link.replace("https://", "").replace("http://", "")
        host = window.location.host
        tab = '<div class="fl-tab"><b>%s</b><span>%s</span><span>%s</span></div>' % (sr.esc(tab_title), sr.esc(tab_price), sr.esc(host))
        sr.rich(n["tabs"], tab * TABS)
        self._link = link
        self._qr()

    # ------------------------------------------------------------------ the QR code
    def _qr(self):
        if getattr(window, "qrcode", None):
            return self._draw_qr()
        doc = window.document
        script = doc.createElement("script")
        script.src = QR_SRC
        script.onload = lambda e: self._draw_qr()
        script.onerror = lambda e: self._qr_failed()
        doc.head.appendChild(script)

    def _draw_qr(self):
        try:
            qr = window.qrcode(0, "M")
            qr.addData(self._link)
            qr.make()
            self.dom_nodes["qr"].innerHTML = qr.createSvgTag(sr.js({"cellSize": 4, "margin": 0, "scalable": True}))
        except Exception:
            self._qr_failed()

    def _qr_failed(self):
        self.dom_nodes["qr"].textContent = "The QR code didn't load. The link below works just as well."
        self.dom_nodes["qr"].classList.add("fl-qr-off")

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        window.print()
