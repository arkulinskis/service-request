"""Bounties: the board, one bounty's page, posting, raising the amount, cancelling, and the timers.

A bounty's life (status):
  review     a moderator checks it first (flagged words, "another task", or reported 3 times)
  open       on the board, neighbours send offers
  assigned   the poster picked a helper: the helper now sees the exact address and can chat
  submitted  the helper sent proof (photos, the checklist they did, how they want to be paid)
  validated  the poster ticked the checklist: quality % decides the bonus; the amount is now owed,
             and the poster sees the helper's e-Transfer email (never before)
  paid       the poster says they paid (cash or e-Transfer, with the reference)
  done       the helper confirmed they got it (or 7 days passed without a word)
  disputed   either side asked a moderator; cancelled / rejected / expired / removed: closed
Timers (sweep, run lazily by the main calls): proof not validated in 48 h -> validated with the helper's
own checklist; "paid" not confirmed in 7 days -> done; open bounties 14 days past their date -> expired.

Privacy: the board shows a pin moved 200-450 m from the real spot (pub_lat/pub_lng) and the area name.
The exact spot and the street address go only to the poster and the matched helper.
"""
import datetime as dt
import math
import random

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Catalog, DemoData, Trust

MONTREAL = (45.5088, -73.5878)
CLOSED = ("cancelled", "rejected", "expired", "removed")
SWEEP_EVERY = 120  # seconds


# ---------------------------------------------------------------------------------- small helpers
def log(b, who, text):
    entries = list(b["log"] or [])
    entries.append({"at": C.iso(C.now()), "who": who, "text": C.text(text, 300)})
    b["log"] = entries[-60:]


def ping(b, who):
    """Something happened that `who` ("poster" / "helper") should look at: a dot on My jobs."""
    col = who + "_unread"
    b[col] = (b[col] or 0) + 1


def role(b, me):
    if me is None:
        return "visitor"
    if b["poster"] == me:
        return "poster"
    if b["helper"] is not None and b["helper"] == me:
        return "helper"
    if C.is_admin(me):
        return "admin"
    return "visitor"


def fuzz(lat, lng):
    """A point 200-450 m away in a random direction: close enough to judge the trip, not a doorstep."""
    d = random.uniform(200, 450)
    a = random.uniform(0, 2 * math.pi)
    return lat + d * math.cos(a) / 111320.0, lng + d * math.sin(a) / (111320.0 * max(0.2, math.cos(math.radians(lat))))


def person(u, role_name):
    if u is None:
        return None
    return {"id": u.get_id(), "name": C.public_name(u),
            "area": u["spot_label"] or "", "joined": C.iso(u["signed_up"]), "record": Trust.record(u, role_name)}


def cover(b):
    keys = list(b["photos"] or [])
    return keys[0] if keys else None


def card(b, me, center):
    """What the board shows for one bounty."""
    t = Catalog.task(b["task"]) or Catalog.TASK_BY_KEY["other"]
    dist = C.km(center[0], center[1], b["pub_lat"], b["pub_lng"]) if center else None
    return {"id": b.get_id(), "title": b["title"], "task": b["task"], "cat": t["cat"], "area": b["area"] or "",
            "lat": b["pub_lat"], "lng": b["pub_lng"], "base": b["base"], "bonus": b["bonus"] or 0, "bar": b["bar"] or 80,
            "pay": b["pay_method"], "size": b["size"], "when_date": C.iso(b["when_date"]), "when_note": b["when_note"] or "",
            "created": C.iso(b["created"]), "offers": b["offer_count"] or 0, "status": b["status"], "vehicle": t["vehicle"],
            "dist": round(dist, 2) if dist is not None else None, "cover": cover(b), "mine": me is not None and b["poster"] == me,
            "demo": bool(b["is_demo"]), "poster": person(b["poster"], "poster"), "details": (b["details"] or "")[:160]}


def center_for(me, lat=None, lng=None):
    lat, lng = C.number(lat), C.number(lng)
    if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
        return (lat, lng)
    if me is not None and me["spot_lat"] is not None:
        return (me["spot_lat"], me["spot_lng"])
    return MONTREAL


# ---------------------------------------------------------------------------------- timers
def sweep(force=False):
    last = C.get_setting("swept_at")
    now = C.now()
    if not force and last and (now - dt.datetime.fromisoformat(last)).total_seconds() < SWEEP_EVERY:
        return
    C.set_setting("swept_at", now.isoformat())
    from . import Work
    for b in app_tables.bounties.search(status="submitted"):
        if b["submitted_at"] is not None and b["submitted_at"] < now - dt.timedelta(hours=48):
            Work.apply_validation(b, list(b["self_checks"] or []), "", auto=True)
    for b in app_tables.bounties.search(status="paid"):
        if b["paid_at"] is not None and b["paid_at"] < now - dt.timedelta(days=7):
            Work.finish(b)
            log(b, "system", "Closed automatically: the payment wasn't questioned within 7 days.")
    today = now.date()
    for b in app_tables.bounties.search(status="open"):
        if b["when_date"] is not None and b["when_date"] < today - dt.timedelta(days=14):
            b.update(status="expired", updated=now)
            log(b, "system", "Expired: the date passed two weeks ago with nobody picked.")


# ---------------------------------------------------------------------------------- the board
@anvil.server.callable
def get_board(lat=None, lng=None):
    """Open bounties around a point (or the viewer's area, or Montréal). Filtering happens in the page."""
    DemoData.ensure_loaded()
    sweep()
    me = C.me()
    center = center_for(me, lat, lng)
    rows = app_tables.bounties.search(tables.order_by("created", ascending=False), status="open")
    items = [card(b, me, center) for b in rows[:300]]
    return {"items": items, "center": {"lat": center[0], "lng": center[1]},
            "spot": ({"lat": me["spot_lat"], "lng": me["spot_lng"], "label": me["spot_label"] or ""}
                     if me is not None and me["spot_lat"] is not None else None),
            "total": len(items), "money": sum(i["base"] + i["bonus"] for i in items)}


# ---------------------------------------------------------------------------------- one bounty
def _offer(o, viewer_role):
    h = o["helper"]
    return {"id": o.get_id(), "message": o["message"] or "", "when": o["when_text"] or "", "ask": o["ask"], "status": o["status"],
            "created": C.iso(o["created"]), "helper": person(h, "helper"),
            "skills": list((h["skills"] or [])[:6]) if h else [], "bio": (h["bio"] or "")[:200] if h else ""}


@anvil.server.callable
def get_bounty(bounty_id):
    DemoData.ensure_loaded()
    sweep()
    me = C.me()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or (b["status"] == "removed" and not C.is_admin(me)):
        return C.fail("This bounty doesn't exist any more.")
    r = role(b, me)
    party = r in ("poster", "helper", "admin")
    if b["status"] != "open" and not party:
        return C.ok(gone=True, title=b["title"], status=b["status"])
    t = Catalog.task(b["task"]) or Catalog.TASK_BY_KEY["other"]
    out = card(b, me, center_for(me))
    out.update({"role": r, "details": b["details"] or "", "checklist": list(b["checklist"] or []), "photos": list(b["photos"] or []),
                "task_name": t["name"], "tools": t["tools"], "posted_base": b["posted_base"] or b["base"],
                "flags": list(b["flags"] or []) if r in ("poster", "admin") else [], "status": b["status"],
                "updated": C.iso(b["updated"]), "helper": person(b["helper"], "helper") if b["helper"] is not None else None,
                "cancel_reason": b["cancel_reason"] or "", "log": list(b["log"] or []) if party else []})
    if party:
        out.update({"exact": {"lat": b["lat"], "lng": b["lng"], "address": b["address"] or ""},
                    "proof": {"photos": list(b["proof_photos"] or []), "note": b["proof_note"] or "", "self_checks": list(b["self_checks"] or []),
                              "at": C.iso(b["submitted_at"])} if b["submitted_at"] is not None else None,
                    "validation": {"checks": list(b["checks"] or []), "quality": b["quality"], "bonus_earned": bool(b["bonus_earned"]),
                                   "amount_due": b["amount_due"], "note": b["validate_note"] or "", "auto": bool(b["auto_validated"]),
                                   "at": C.iso(b["validated_at"])} if b["validated_at"] is not None else None,
                    "payment": {"method": b["paid_method"] or "", "ref": b["paid_ref"] or "", "at": C.iso(b["paid_at"])} if b["paid_at"] is not None else None,
                    "payout": None, "dispute": {"by": b["dispute_by"] or "", "reason": b["dispute_reason"] or ""} if b["dispute_reason"] else None,
                    "messages": [{"mine": m["sender"] == me, "who": C.public_name(m["sender"]), "text": m["text"], "at": C.iso(m["created"])}
                                 for m in app_tables.messages.search(tables.order_by("created"), bounty=b)]})
        if b["validated_at"] is not None or r == "helper":
            # The e-Transfer email: the helper's own, or the poster's once the work is validated. Never anyone else.
            out["payout"] = {"method": b["payout_method"] or "", "email": b["payout_email"] or ""}
        if b["status"] == "done":
            from . import Work
            out["reviews"] = Work.reviews_for(b, me)
    if r == "poster" or r == "admin":
        offers = app_tables.offers.search(tables.order_by("created", ascending=False), bounty=b)
        out["offers_list"] = [_offer(o, r) for o in offers if o["status"] != "withdrawn"]
    elif me is not None:
        mine = app_tables.offers.get(bounty=b, helper=me)
        out["my_offer"] = _offer(mine, r) if mine is not None and mine["status"] != "withdrawn" else None
        out["can_help"] = Trust.can_help(me)
    if r in ("poster", "helper") and (b[r + "_unread"] or 0):
        b[r + "_unread"] = 0
    return C.ok(bounty=out)


# ---------------------------------------------------------------------------------- posting
def _amounts(base, bonus, bar):
    base, bonus, bar = C.number(base), C.number(bonus, 0) or 0, C.number(bar, 80) or 80
    if base is None or base != int(base):
        return None, "The bounty is a whole number of dollars."
    if base < Catalog.MIN_BASE:
        return None, "The minimum bounty is $%d." % Catalog.MIN_BASE
    if base > Catalog.MAX_BASE:
        return None, "Bounties go up to $%d. Bigger jobs are for licensed pros." % Catalog.MAX_BASE
    if bonus != int(bonus) or bonus < 0:
        return None, "The quality bonus is a whole number of dollars."
    if 0 < bonus < 5:
        return None, "A quality bonus starts at $5 (or leave it at $0)."
    if bonus > min(base, Catalog.MAX_BONUS):
        return None, "The quality bonus can't be more than the bounty itself (and at most $%d)." % Catalog.MAX_BONUS
    if bar not in range(50, 101, 5):
        return None, "The quality bar is between 50% and 100%, in steps of 5."
    return (int(base), int(bonus), int(bar)), None


@anvil.server.callable(require_user=True)
def post_bounty(data):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    why = Trust.can_post(me)
    if why:
        return C.fail(why)
    t = Catalog.task(data.get("task"))
    if t is None:
        return C.fail("Pick a task from the list.")
    title = C.text(data.get("title"), 90)
    details = C.text(data.get("details"), 1500, multiline=True)
    if len(title) < 6:
        return C.fail("Give the bounty a title (at least 6 characters).")
    if len(details) < 15:
        return C.fail("Describe the job in a sentence or two (at least 15 characters): what, where, anything to know.")
    size = data.get("size") if data.get("size") in Catalog.SIZE_INDEX else "medium"
    amounts, problem = _amounts(data.get("base"), data.get("bonus"), data.get("bar"))
    if problem:
        return C.fail(problem)
    base, bonus, bar = amounts
    pay = data.get("pay_method")
    if pay not in ("cash", "etransfer", "either"):
        return C.fail("Say how you'll pay: cash, e-Transfer, or either.")
    lat, lng = C.number(data.get("lat")), C.number(data.get("lng"))
    if lat is None or lng is None or not (41 <= lat <= 84 and -142 <= lng <= -52):
        return C.fail("Put a pin on the map where the job is (Canada only for now).")
    area = C.text(data.get("area"), 60)
    address = C.text(data.get("address"), 160)
    if len(area) < 2:
        return C.fail("Give the area a name, like a neighbourhood.")
    if len(address) < 5:
        return C.fail("Add the street address. Only the helper you pick will see it.")
    when = data.get("when_date")
    when_date = None
    if when:
        try:
            when_date = dt.date.fromisoformat(str(when)[:10])
        except ValueError:
            return C.fail("That date doesn't look right.")
        today = C.now().date()
        if when_date < today - dt.timedelta(days=1) or when_date > today + dt.timedelta(days=90):
            return C.fail("Pick a date between today and 90 days from now.")
    checklist = [C.text(x, 90) for x in (data.get("checklist") or []) if C.text(x, 90)][:8]
    if len(checklist) < 2:
        return C.fail("Keep at least 2 checklist items: they are how the quality is measured.")
    if C.rate_limited("post_bounty", 6, 3600):
        return C.fail("That's a lot of bounties in one hour. Please try again a bit later.")
    from . import Photos
    photos, problem = Photos.claim(me, data.get("photo_keys") or [], 4)
    if problem:
        return C.fail(problem)
    title, hid1 = Trust.redact(title)
    details, hid2 = Trust.redact(details)
    flags = Trust.scan(" ".join([title, details, address] + checklist))
    if t["key"] == "other":
        flags.append("\"Another task\": a moderator checks these")
    if Trust.is_new(me, "poster") and base + bonus > 150:
        flags.append("High amount from a new account")
    now = C.now()
    plat, plng = fuzz(lat, lng)
    b = app_tables.bounties.add_row(
        poster=me, helper=None, task=t["key"], title=title, details=details, size=size, when_date=when_date,
        when_note=C.text(data.get("when_note"), 80), lat=lat, lng=lng, pub_lat=plat, pub_lng=plng, area=area, address=address,
        base=base, posted_base=base, bonus=bonus, bar=bar, checklist=checklist, pay_method=pay,
        status="review" if flags else "open", flags=flags, photos=[p["key"] for p in photos], proof_photos=[],
        created=now, updated=now, offer_count=0, poster_unread=0, helper_unread=0, log=[], is_demo=False)
    for p in photos:
        p["bounty"] = b
    log(b, "poster", "Posted for %s%s." % (C.money(base), (" + %s quality bonus at %d%%" % (C.money(bonus), bar)) if bonus else ""))
    if flags:
        log(b, "system", "Waiting for a moderator: " + "; ".join(flags) + ".")
    Trust.bump(me, posted=1)
    return C.ok(id=b.get_id(), status=b["status"], flags=flags, hidden_contact=hid1 or hid2)


@anvil.server.callable(require_user=True)
def raise_bounty(bounty_id, base, bonus):
    """Sweeten the deal: raise the bounty or the bonus while it's still open."""
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["poster"] != me:
        return C.fail("Only the person who posted it can change the amount.")
    if b["status"] not in ("open", "review"):
        return C.fail("The amount is fixed once a helper is picked.")
    amounts, problem = _amounts(base, bonus, b["bar"] or 80)
    if problem:
        return C.fail(problem)
    nb, nbo, _ = amounts
    if nb < b["base"] or nbo < (b["bonus"] or 0):
        return C.fail("You can raise the amounts, not lower them (helpers may already have offered).")
    if nb == b["base"] and nbo == (b["bonus"] or 0):
        return C.fail("That's the same amount as now.")
    b.update(base=nb, bonus=nbo, updated=C.now())
    log(b, "poster", "Raised to %s%s." % (C.money(nb), (" + %s bonus" % C.money(nbo)) if nbo else ""))
    for o in app_tables.offers.search(bounty=b, status="pending"):
        if (o["ask"] or 0) < nb:
            o["ask"] = nb
    return C.ok()


@anvil.server.callable(require_user=True)
def cancel_bounty(bounty_id, reason=""):
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["poster"] != me:
        return C.fail("Only the person who posted it can cancel it.")
    reason = C.text(reason, 300)
    if b["status"] in ("open", "review"):
        b.update(status="cancelled", updated=C.now(), cancel_reason=reason or "Cancelled by the poster.")
        log(b, "poster", "Cancelled." + ((" " + reason) if reason else ""))
    elif b["status"] == "assigned":
        if len(reason) < 10:
            return C.fail("A helper is already booked: tell them why you're cancelling (at least 10 characters).")
        b.update(status="cancelled", updated=C.now(), cancel_reason=reason)
        log(b, "poster", "Cancelled after a helper was booked: " + reason)
        ping(b, "helper")
        Trust.bump(me, late_cancels=1)
    else:
        return C.fail("The work is already done: validate it, or open a dispute if something's wrong.")
    for o in app_tables.offers.search(bounty=b, status="pending"):
        o["status"] = "declined"
    return C.ok()
