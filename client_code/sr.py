"""Service Request's shared client helpers (the Python side of the old window.SR).

    sr.catalog()               the task catalogue (get_catalog, fetched once): tasks, categories, sizes, pay methods,
                               not_allowed, skills, min_base / max_base / max_bonus; by_key and cat_by_key added here
    sr.task(key) / sr.cat(key) one task / category (a safe stand-in when unknown)
    sr.money(n)                "$20", "$12.50", "$1,250"
    sr.quality(k, n)           the checklist score exactly as the server works it out (Work.apply_validation)
    sr.need(n, bar)            how many of n items must be ticked to reach the bonus bar (same rule)
    sr.when(b), sr.dist(km), sr.fmt_date(iso, ...), sr.fmt_datetime(iso), sr.rating_text(rec), sr.pay_record(rec)
    sr.fill_tag / fill_ti / fill_stamp / fill_stars / fill_meter   draw the brand's small pieces into a template node
    sr.photo(key, thumb)       the URL of a bounty photo (server_code/Photos.py: /photo)
    sr.edit_area()             the "where do you help out?" spot picker + set_spot
    sr.report(what, ...)       the Report dialog (sign-in first)
The maps, photo shrinking, place search and confetti stay JavaScript (theme/assets/sr-engine.js).
"""
import datetime
import json
import math

import anvil.js
import anvil.server
from anvil import alert
from anvil.js import window

from . import state

_c: dict = {"cat": None, "api": None}

STATUS = {"review": "In review", "open": "Open", "assigned": "Booked", "submitted": "Proof sent", "validated": "Payment due",
          "paid": "Paid", "done": "Done", "disputed": "Dispute", "cancelled": "Cancelled", "rejected": "Not approved",
          "expired": "Expired", "removed": "Removed"}
PAY = {"cash": "Cash", "etransfer": "e-Transfer", "either": "Cash or e-Transfer"}
PAY_ICON = {"cash": "cash", "etransfer": "bank"}
LIVE = ("open", "review", "assigned", "submitted", "validated", "paid", "disputed")


def esc(s):
    return window.UI.esc(s)


def js(value):
    """A Python dict/list as a real JavaScript object."""
    return window.JSON.parse(json.dumps(value))


def plain(text_or_obj):
    """JSON text (or a JS object) from the engine as Python values."""
    if text_or_obj is None:
        return None
    if isinstance(text_or_obj, str):
        return json.loads(text_or_obj)
    return json.loads(window.JSON.stringify(text_or_obj))


# ---------------------------------------------------------------- the catalogue
def catalog():
    if _c["cat"] is None:
        c = anvil.server.call("get_catalog")
        c["by_key"] = {t["key"]: t for t in c["tasks"]}
        c["cat_by_key"] = {x["key"]: x for x in c["categories"]}
        _c["cat"] = c
    return _c["cat"]


def task(key):
    c = _c["cat"] or catalog()
    return c["by_key"].get(key) or {"key": key, "name": "Neighbourly task", "cat": "other", "checklist": [],
                                    "prices": [20, 40, 70], "months": list(range(1, 13)), "blurb": "", "vehicle": False}


def cat(key):
    c = _c["cat"] or catalog()
    return c["cat_by_key"].get(key) or {"key": "other", "name": "Something else", "icon": "sparkle"}


def in_season(t):
    return datetime.date.today().month in t["months"] and len(t["months"]) < 12


# ---------------------------------------------------------------- money and the quality rule
def money(n):
    n = float(n or 0)
    if n == math.floor(n):
        return "$" + "{:,}".format(int(n))
    return "$" + "{:,.2f}".format(n)


def quality(k, n):
    """The score: the share of ticked items, rounded the way the server rounds it (Work.apply_validation)."""
    return int(round(100.0 * k / max(1, n)))


def need(n, bar):
    """The fewest ticked items (of n) whose score reaches the bar (the server's rule: quality >= bar)."""
    n = max(1, n)
    for k in range(n + 1):
        if quality(k, n) >= bar:
            return k
    return n


def js_round(x):
    """JavaScript's Math.round (half up), for the post wizard's suggested numbers (same as the JS version)."""
    return int(math.floor(x + 0.5))


def first(name):
    return str(name or "").split(" ")[0]


def plural(n, one, many=None):
    return state.plural(n, one, many)


# ---------------------------------------------------------------- dates and places
def _date(iso):
    if not iso:
        return None
    return window.Date(iso + "T12:00:00") if len(iso) <= 10 else window.Date(iso)


def fmt_date(iso, opts=None):
    d = _date(iso)
    if d is None:
        return ""
    return d.toLocaleDateString([], js(opts or {"day": "numeric", "month": "short", "year": "numeric"}))


def fmt_datetime(iso):
    d = _date(iso)
    if d is None:
        return ""
    return d.toLocaleString([], js({"day": "numeric", "month": "short", "hour": "2-digit", "minute": "2-digit"}))


def ago(iso):
    return state.ago(iso)


def hours_left(iso, hours):
    if not iso:
        return hours
    gone = (window.Date.now() - window.Date.parse(iso)) / 3600000.0
    return max(0, js_round(hours - gone))


def when(b):
    parts = []
    if b.get("when_date"):
        parts.append(fmt_date(b["when_date"], {"weekday": "short", "day": "numeric", "month": "short"}))
    if b.get("when_note"):
        parts.append(b["when_note"])
    return " · ".join(parts) or "Flexible"


def dist(km):
    if km is None:
        return ""
    if km < 1:
        return "%d m" % max(100, js_round(km * 10) * 100)
    return ("%.1f" % km if km < 10 else str(js_round(km))) + " km"


def rating_text(rec):
    if rec and rec.get("rating"):
        return "★ %.1f (%s)" % (float(rec["rating"]), rec.get("reviews") or 0)
    return "New"


def pay_record(rec):
    if not rec:
        return ""
    if not rec.get("paid"):
        return "No payments yet"
    out = "Pays within 2 days: %s/%s" % (rec.get("paid_fast") or 0, rec["paid"])
    if rec.get("bonus_jobs"):
        out += " · Bonus paid %s/%s" % (rec.get("bonus_paid") or 0, rec["bonus_jobs"])
    return out


def photo(key, thumb=False):
    if not key:
        return ""
    if _c["api"] is None:
        _c["api"] = str(anvil.server.get_api_origin()).rstrip("/")
    return _c["api"] + "/photo?k=" + window.encodeURIComponent(key) + ("&s=t" if thumb else "")


# ---------------------------------------------------------------- the brand's small pieces, drawn into template nodes
def icon(name, cls=""):
    return '<i class="ic ic-%s%s" aria-hidden="true"></i>' % (name, (" " + cls) if cls else "")


def fill_tag(node, base, bonus=0, bar=80, size="", sub=None):
    """The tear-off price tag: the amount, then "+$10 at 80%" (or "bounty")."""
    node.className = "sr-tag" + ((" " + size) if size else "")
    if sub is None:
        sub = ("+%s at %s%%" % (money(bonus), bar or 80)) if bonus else "bounty"
    node.innerHTML = "<b>%s</b>%s" % (esc(money(base)), ("<i>%s</i>" % esc(sub)) if sub else "")


def fill_ti(node, task_key, size=""):
    """The task's category tile (a coloured square with the category icon)."""
    c = cat(task(task_key)["cat"])
    node.className = "sr-ti c-%s%s" % (c["key"], (" " + size) if size else "")
    node.setAttribute("title", c["name"])
    node.innerHTML = icon(c["icon"])


def fill_stamp(node, status):
    node.className = "sr-stamp " + status
    node.textContent = STATUS.get(status, status)


def fill_stars(node, n, total=5):
    node.className = "sr-stars"
    node.setAttribute("role", "img")
    node.setAttribute("aria-label", "%s out of 5 stars" % (n or 0))
    on = js_round(n or 0)
    node.innerHTML = "".join('<span class="%s">%s</span>' % ("" if i <= on else "off", icon("starf")) for i in range(1, total + 1))


def fill_meter(node, q, bar, bonus):
    """The quality meter: a striped fill to q%, the bonus bar as a dashed line."""
    node.className = "bt-meter"
    node.setAttribute("role", "img")
    node.setAttribute("aria-label", "Quality %s%%" % q)
    node.innerHTML = ('<div class="fill%s" style="width:%s%%"></div>' % (" full" if q >= 100 else "", q) +
                      ('<div class="bar" style="left:%s%%"><span>Bonus at %s%%</span></div>' % (bar, bar) if bonus else "") +
                      '<span class="val">%s%%</span>' % q)


def rating_html(rec):
    """"★ 4.8 (12)" with the star in gold, or "New"."""
    if rec and rec.get("rating"):
        return '<span class="sr-star">★ %.1f</span> <span class="faint">(%s)</span>' % (float(rec["rating"]), esc(rec.get("reviews") or 0))
    return '<span class="faint">New</span>'


def fill_rating(node, rec):
    node.innerHTML = rating_html(rec)


def stored(key, default=None):
    """This browser's saved value (same keys as the JavaScript version: 'servicerequest.<key>'), as Python values."""
    try:
        v = window.localStorage.getItem(window.UI.config.key + "." + key)
        return default if v is None else json.loads(v)
    except Exception:
        return default


def store(key, value):
    try:
        window.localStorage.setItem(window.UI.config.key + "." + key, json.dumps(value))
    except Exception:
        pass


def later(fn, ms=50):
    window.setTimeout(fn, ms)


def rich(node, html):
    """A sentence with bold parts (values already escaped with esc())."""
    node.innerHTML = html


def confetti():
    window.SR.confetti()


def copy(text, what="Copied"):
    try:
        window.navigator.clipboard.writeText(text)
        state.toast("%s copied" % what, "ok")
    except Exception:
        state.toast("Select it and copy by hand.")


# ---------------------------------------------------------------- dialogs shared by several pages
def pick_spot(**opts):
    """The spot picker dialog. Returns {lat, lng, label, street} or None."""
    from .Dialogs.SpotPicker import SpotPicker
    return alert(SpotPicker(**opts), buttons=[], large=True, role="app-dialog", dismissible=True)


def edit_area():
    """Where do you help out? Saves the area (set_spot) and returns the new me, or None."""
    me = state.me() or {}
    s = me.get("spot") or {}
    p = pick_spot(title="Where do you help out?", ok="Save my area", pin_label="You",
                  text="Bounties are sorted by distance from here. Others only see the area name, never your address.",
                  label=s.get("label") or "", lat=s.get("lat"), lng=s.get("lng"))
    if not p:
        return None
    r = state.call("set_spot", p["lat"], p["lng"], p["label"])
    if not r:
        return None
    state.set_me(r["me"])
    state.toast("Area saved: " + p["label"], "ok")
    return r["me"]


def report(what, bounty=None, user=None):
    from . import router
    if not state.me():
        router.go("auth")
        return
    from .Dialogs.Report import Report
    def send(kind, text):
        return anvil.server.call("report", kind, text, bounty, user)
    res = alert(Report(what=what, send=send), buttons=[], role="app-dialog", dismissible=True)
    if res:
        state.toast("Thanks. It's off the board until a moderator checks it." if res.get("hidden") else
                    "Thanks. A moderator will look at it.", "ok")


def zoom(key):
    from .Dialogs.Zoom import Zoom
    alert(Zoom(key=key), buttons=[], large=True, role="app-dialog", dismissible=True)
