from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import RulesTemplate
from ... import router, sr

SECTIONS = ("pay", "quality", "scams", "allowed", "privacy", "disputes", "tasks")


class Rules(RulesTemplate):
    """Rules & safety (#rules, #rules/<section>), public: paying (cash / e-Transfer, no fees), quality and the bonus, the
    scams to watch for, what's not allowed, privacy, disputes and strikes, and every task with its suggested prices."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self._section = args[0] if args and args[0] in SECTIONS else None
        C = sr.catalog()
        n = self.dom_nodes
        n["min_tag"].textContent = "$%s+" % C["min_base"]
        n["pay_amount"].textContent = ("The amount is set before the job: the bounty (at least $%s), plus the quality bonus if the "
                                       "checklist score reaches the bar." % C["min_base"])
        n["allowed_p"].textContent = ("Neighbourly jobs that need no degree and no licence: yard, snow, junk, lifting, outdoor cleaning, "
                                      "errands, pets and plants, seasonal help. Bounties from $%s to $%s." % (C["min_base"], C["max_base"]))
        self.not_allowed_panel.items = [{"text": x, "icon": "x", "cls": "rl-no-li"} for x in C["not_allowed"]]
        rows = []
        for c in C["categories"]:
            rows.append({"cat": c})
            rows += [{"t": t} for t in C["tasks"] if t["cat"] == c["key"]]
        self.tasks_panel.items = rows

    def _scroll(self, section):
        el = anvil.js.get_dom_node(self).querySelector("#rl-" + section)
        if el:
            el.scrollIntoView(sr.js({"behavior": "smooth"}))

    def after_open(self):
        if self._section:
            sr.later(lambda: self._scroll(self._section), 80)

    def jump_click(self, event):
        event.preventDefault()
        section = event.currentTarget.getAttribute("data-jump")
        router.replace("rules", section)
        self._scroll(section)
