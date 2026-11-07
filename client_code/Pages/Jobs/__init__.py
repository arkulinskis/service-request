from anvil import *
import anvil.server

from ._anvil_designer import JobsTemplate
from ... import sr, state

TABS = ["todo", "posted", "doing", "offers"]
EMPTY = {
    "todo": ("check", "All caught up", "Nothing needs you right now. Post a bounty, or find one to do.",
             [("#post", "Post a bounty"), ("#board", "Browse bounties")]),
    "posted": ("tag", "No bounties yet", "Leaves, snow, a couch to haul? Post it from $20.", [("#post", "Post a bounty")]),
    "doing": ("hand", "No jobs yet", "Find a bounty near you and send an offer.", [("#board", "Browse bounties")]),
    "offers": ("send", "No offers sent", "Offers you make on bounties show up here.", [("#board", "Browse bounties")]),
}


class Jobs(JobsTemplate):
    """My jobs (#jobs/<todo|posted|doing|offers>): everything you posted and everything you're doing, with what needs
    your attention first (pick a helper, check the work, pay, confirm you got paid, review). Plus the offers you sent."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        tab = args[0] if args and args[0] in TABS else "todo"
        sr.catalog()
        d = anvil.server.call("get_jobs")
        self._draw(d, tab)

    def _draw(self, d, tab):
        todo = [{"j": j, "role": "poster"} for j in d["posted"] if j.get("urgent")] + \
               [{"j": j, "role": "helper"} for j in d["doing"] if j.get("urgent")]

        def live(j):
            return j["status"] in sr.LIVE
        counts = {"todo": len(todo), "posted": len([j for j in d["posted"] if live(j)]),
                  "doing": len([j for j in d["doing"] if live(j)]),
                  "offers": len([o for o in d["offers"] if o["status"] == "pending"])}
        n = self.dom_nodes
        for k, node in (("todo", n["c_todo"]), ("posted", n["c_posted"]), ("doing", n["c_doing"]), ("offers", n["c_offers"])):
            node.textContent = str(counts[k]) if counts[k] else ""
            node.hidden = not counts[k]
        n["n_todo"].textContent = str(counts["todo"])
        n["n_posted"].textContent = str(counts["posted"])
        n["n_doing"].textContent = str(counts["doing"])
        owe = sum(j.get("amount_due") or 0 for j in d["posted"] if j["status"] == "validated")
        owed = sum(j.get("amount_due") or 0 for j in d["doing"] if j["status"] in ("validated", "paid"))
        n["owed"].textContent = sr.money(owed)
        n["owed_sub"].textContent = "coming to you" + ((" · you owe " + sr.money(owe)) if owe else "")
        limit = (d.get("limits") or {}).get("post")
        self.limit_note.text = limit or ""
        self.limit_note.visible = bool(limit)
        for k, link in (("todo", self.tab_todo), ("posted", self.tab_posted), ("doing", self.tab_doing), ("offers", self.tab_offers)):
            link.classes["on"] = k == tab
            state.set_attr(link, "aria-current", "page" if k == tab else None)

        first, second, t1, t2 = [], [], "", ""
        if tab == "todo":
            first = todo
        elif tab in ("posted", "doing"):
            jobs = d["posted"] if tab == "posted" else d["doing"]
            role = "poster" if tab == "posted" else "helper"
            first = [{"j": j, "role": role} for j in jobs if live(j)]
            second = [{"j": j, "role": role} for j in jobs if not live(j)]
            t1, t2 = "In progress", "Finished and closed"
        else:
            first = [{"j": o, "role": "offer"} for o in d["offers"]]
        self.list1.items = first
        self.list2.items = second
        self.list1.visible = bool(first)
        self.list2.visible = bool(second)
        n["group1"].textContent = t1
        n["group1"].hidden = not (t1 and first)
        n["group2"].textContent = t2
        n["group2"].hidden = not (t2 and second)
        empty = not first and not second
        self.empty_box.visible = empty
        if empty:
            ic, h, p, links = EMPTY[tab]
            n["empty_ic"].className = "ic ic-" + ic
            n["empty_h"].textContent = h
            n["empty_p"].textContent = p
            for i, a in enumerate([n["empty_a1"], n["empty_a2"]]):
                a.hidden = i >= len(links)
                if i < len(links):
                    a.setAttribute("href", links[i][0])
                    a.textContent = links[i][1]
