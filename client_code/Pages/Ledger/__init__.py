from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import LedgerTemplate
from ... import sr


class Ledger(LedgerTemplate):
    """The ledger (#ledger): every amount owed, sent and settled, both ways (earned as a helper, paid as a poster), with
    totals and a CSV export. Money never moves through the app: this is the paper trail for cash and e-Transfers."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("get_ledger")
        self._filter = "all"
        T = self.data["totals"]
        n = self.dom_nodes
        n["earned"].textContent = sr.money(T["earned"])
        n["earned_sub"].textContent = "earned" + ((" (%s in bonuses)" % sr.money(T["bonus"])) if T.get("bonus") else "")
        n["coming"].textContent = sr.money(T["coming"])
        n["spent"].textContent = sr.money(T["spent"])
        n["owe"].textContent = sr.money(T["owe"])
        n["owe"].classList.toggle("lg-bad", bool(T["owe"]))
        self.csv_button.visible = bool(self.data["rows"])
        self._draw()

    def _draw(self):
        rows = [r for r in self.data["rows"] if self._filter == "all" or r["dir"] == self._filter]
        for key, b in (("all", self.f_all), ("in", self.f_in), ("out", self.f_out)):
            b.classes["on"] = key == self._filter
        self.rows_panel.items = rows
        self.table_box.visible = bool(rows)
        self.empty_box.visible = not rows

    def filter_click(self, event):
        self._filter = event.currentTarget.getAttribute("data-f")
        self._draw()

    @handle("csv_button", "click")
    def csv_button_click(self, **event_args):
        def q(v):
            return '"' + str("" if v is None else v).replace('"', '""') + '"'
        lines = [["date", "bounty", "direction", "with", "method", "reference", "state", "quality", "bonus", "amount"]]
        for r in self.data["rows"]:
            lines.append([(r.get("at") or "")[:10], r["title"], "earned" if r["dir"] == "in" else "paid", r.get("other"),
                          r.get("method"), r.get("ref"), r.get("state"), r.get("quality"), r.get("bonus"), r.get("amount")])
        window.SR.download("service-request-ledger.csv", "\n".join(",".join(q(v) for v in line) for line in lines))
