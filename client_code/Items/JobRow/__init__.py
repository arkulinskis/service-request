from anvil import *

from ._anvil_designer import JobRowTemplate
from ... import router, sr


class JobRow(JobRowTemplate):
    """One job in My jobs. item = {j: job or offer, role: "poster" | "helper" | "offer"}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        j, role = self.item["j"], self.item["role"]
        d = self.dom_nodes
        sr.fill_ti(d["ti"], j["task"])
        d["title"].textContent = j["title"]
        d["area"].textContent = j.get("area") or ""
        if role == "offer":
            d["row"].setAttribute("href", router.href("bounty", j["bounty"]))
            st = j["status"]
            d["stamp"].className = "ui-badge" + (" warn" if st == "pending" else "")
            d["stamp"].textContent = "Waiting for an answer" if st == "pending" else ("Not picked" if st == "declined" else "Closed")
            d["needs"].hidden = True
            d["who"].hidden = True
            d["when"].textContent = "Sent " + sr.ago(j.get("created"))
            sr.fill_tag(d["tag"], j.get("ask") or 0, size="sm", sub="")
            d["dot"].hidden = True
            return
        d["row"].setAttribute("href", router.href("bounty", j["id"]))
        sr.fill_stamp(d["stamp"], j["status"])
        wait = not j.get("urgent")
        d["needs"].hidden = not j.get("needs")
        d["needs"].classList.toggle("wait", wait)
        d["needs_ic"].className = "ic ic-" + ("clock" if wait else "bell")
        d["needs_text"].textContent = j.get("needs") or ""
        if role == "poster":
            if j.get("other"):
                sr.rich(d["who"], "Helper: <b>%s</b>" % sr.esc(j["other"]))
            else:
                d["who"].textContent = sr.plural(j.get("offers") or 0, "offer")
        else:
            sr.rich(d["who"], "For <b>%s</b>" % sr.esc(j.get("other") or ""))
        d["when"].textContent = "Updated " + sr.ago(j.get("updated"))
        due = j.get("amount_due")
        sr.fill_tag(d["tag"], due if due is not None else j["base"], size="sm",
                    sub=("+" + sr.money(j["bonus"])) if (j.get("bonus") and due is None) else "")
        d["dot"].hidden = not j.get("unread")
        d["dot"].textContent = str(j.get("unread") or "")
