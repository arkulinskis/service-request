"""Trust & safety: the rules that keep a cash bounty board honest.

How the app is protected (also explained to members on the #rules page):
  - Text scan (scan): scam words (gift cards, crypto, wire transfers, cheques, overpayment, upfront fees,
    unknown packages) and unsafe or licensed work (roofs, electrical, gas, childcare, rides, hazardous waste)
    send a new bounty to the moderators' review queue instead of the board. "Another task" always goes there.
  - Contact details (redact): phone numbers, emails and links are hidden in public text, so first contact
    happens inside the app (where reports work) and nobody harvests numbers from the board.
  - Limits: new accounts may have 2 live bounties and 2 active jobs; established ones 6 and 4. A poster with
    a payment overdue (72 h after validating) can't post or hire until they settle it.
  - Strikes: an upheld report or a lost dispute is a strike; 3 strikes pause the account (no posting, no offers).
  - Reports: 3 open reports from different people on an open bounty take it off the board for review.
  - Stats on every profile (stats column): how fast a poster pays, how often they pay the quality bonus,
    late cancellations, a helper's jobs, bonuses won and drop-outs. Reputation is earned, not claimed.
"""
import datetime as dt
import re

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C

NEW_LIVE, LIVE = 2, 6            # live bounties a poster may have (new account, established)
NEW_ACTIVE, ACTIVE = 2, 4        # jobs a helper may have on the go
STRIKES_PAUSE = 3
PAY_GRACE_HOURS = 72
LIVE_STATUSES = ("review", "open", "assigned", "submitted", "validated", "paid", "disputed")

SCAM = [
    (r"gift\s*-?\s*cards?", "Mentions gift cards"),
    (r"bitcoin|\bcrypto|\busdt\b|ethereum", "Mentions crypto"),
    (r"western\s*union|moneygram|wire\s*transfer|money\s*order", "Mentions money transfers"),
    (r"\bcheques?\b|\bchecks? (deposit|to deposit)|deposit (a|the|my|this) (cheque|check)", "Mentions cheques"),
    (r"overpa(y|id|yment)|send (the |me )?(rest|difference|change|extra) back|refund the (difference|extra)", "Overpayment pattern"),
    (r"(pay|paid|money|cash)\s*(me\s*)?up\s*-?\s*front|(pay|paid|payment|money) in advance|deposit fee|registration fee|pay (a|the) fee|pay to (apply|start)", "Asks for money upfront"),
    (r"\bpackages?\b[^.]{0,40}\b(deliver|carry|bring|drop)|\b(deliver|carry|bring)\b[^.]{0,40}\bpackages?\b", "Carrying packages"),
    (r"bank (login|password|card|account (details|number))|\bpin code\b|social insurance|\bSIN\b", "Asks for banking or ID details"),
]
UNSAFE = [
    (r"\broofs?\b|rooftop|\bshingles?\b", "Roof work"),
    (r"electrical (work|panel)|\bwiring\b|breaker (box|panel)|electrician", "Electrical work"),
    (r"\bgas (line|leak|pipe|hookup)|furnace|propane", "Gas work"),
    (r"plumb(ing|er)|sewer line|water heater", "Plumbing"),
    (r"asbestos|vermiculite|solvents?|syringes?|needles|biohazard|mou?ld removal", "Hazardous material"),
    (r"babysit|child\s*care|nanny|look after (my|the|our) (kids?|child|children|son|daughter)", "Childcare"),
    (r"drive me|give (me|us) a ride|ride to|chauffeur|pick (me|us) up", "Rides"),
    (r"prescriptions?|medication|\bpills\b", "Medicine"),
    (r"(cut|chop|fell(ing)?|take) down (a|the|my|our) tree|chainsaw", "Tree felling"),
    (r"\bguns?\b|firearms?|weapons?|\bammo\b", "Weapons"),
]
PHONE = re.compile(r"(?<!\d)(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LINK = re.compile(r"https?://\S+|www\.\S+", re.I)
HIDDEN = "[contact hidden: chat in the app once you're matched]"

REPORT_KINDS = {"not_paid": "Didn't pay", "no_show": "Didn't show up", "scam": "Looks like a scam", "unsafe": "Unsafe or not allowed",
                "rude": "Rude or harassing", "fake": "Fake bounty or profile", "other": "Something else"}


# ---------------------------------------------------------------------------------- text
def scan(text):
    """The reasons this text needs a moderator (empty list = fine)."""
    t = text or ""
    out = []
    for pattern, why in SCAM + UNSAFE:
        if re.search(pattern, t, re.I) and why not in out:
            out.append(why)
    return out


def redact(text):
    """Hide phone numbers, emails and links. Returns (clean text, True if anything was hidden)."""
    t = text or ""
    clean = LINK.sub(HIDDEN, EMAIL.sub(HIDDEN, PHONE.sub(HIDDEN, t)))
    return clean, clean != t


def valid_email(s):
    return bool(re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,190}\.[a-zA-Z]{2,24}", s or ""))


# ---------------------------------------------------------------------------------- stats + standing
def stats(user):
    return dict((user["stats"] if user is not None else None) or {})


def bump(user, **inc):
    """Add to a person's counters, e.g. bump(u, jobs=1)."""
    if user is None:
        return
    s = stats(user)
    for k, v in inc.items():
        s[k] = (s.get(k) or 0) + v
    user["stats"] = s


def bump_cat(user, cat):
    s = stats(user)
    by = dict(s.get("by_cat") or {})
    by[cat] = (by.get(cat) or 0) + 1
    s["by_cat"] = by
    user["stats"] = s


def paused(user):
    return bool(user is not None and (user["paused"] or (user["strikes"] or 0) >= STRIKES_PAUSE))


def strike(user, why):
    if user is None:
        return
    user["strikes"] = (user["strikes"] or 0) + 1
    s = stats(user)
    s["last_strike"] = C.text(why, 120)
    user["stats"] = s


def overdue(user):
    """This person's validated bounties that are still unpaid after the grace period."""
    limit = C.now() - dt.timedelta(hours=PAY_GRACE_HOURS)
    return [b for b in app_tables.bounties.search(poster=user, status="validated")
            if b["validated_at"] is not None and b["validated_at"] < limit]


def is_new(user, role):
    s = stats(user)
    return (s.get("completed") or 0) == 0 if role == "poster" else (s.get("jobs") or 0) == 0


def can_post(user):
    """None if this person may post (or hire) now, else the reason why not."""
    if paused(user):
        return "Your account is paused after reports, so you can't post or hire right now. Write to us through Submit feedback."
    if overdue(user):
        return "You have a bounty to pay first: it was validated more than 3 days ago. Settle it in My jobs, then post again."
    live = len([b for b in app_tables.bounties.search(poster=user) if b["status"] in LIVE_STATUSES])
    cap = NEW_LIVE if is_new(user, "poster") else LIVE
    if live >= cap:
        return ("New accounts can have %d live bounties at a time. Finish one first (it unlocks %d)." % (NEW_LIVE, LIVE)
                if cap == NEW_LIVE else "You already have %d live bounties. Finish or cancel one first." % LIVE)
    return None


def active_jobs(user):
    return [b for b in app_tables.bounties.search(helper=user) if b["status"] in ("assigned", "submitted")]


def can_help(user):
    """None if this person may take on another job, else the reason why not."""
    if paused(user):
        return "Your account is paused after reports, so you can't make offers right now. Write to us through Submit feedback."
    cap = NEW_ACTIVE if is_new(user, "helper") else ACTIVE
    if len(active_jobs(user)) >= cap:
        return ("New helpers can have %d jobs on the go. Finish one first." % NEW_ACTIVE if cap == NEW_ACTIVE
                else "You already have %d jobs on the go. Finish one first." % ACTIVE)
    return None


def record(user, role):
    """The public track record shown on bounties and profiles."""
    s = stats(user)
    if role == "poster":
        paid, fast = s.get("paid") or 0, s.get("paid_fast") or 0
        bj, bp = s.get("bonus_jobs") or 0, s.get("bonus_paid") or 0
        return {"posted": s.get("posted") or 0, "completed": s.get("completed") or 0, "paid": paid, "paid_fast": fast,
                "bonus_jobs": bj, "bonus_paid": bp, "late_cancels": s.get("late_cancels") or 0,
                "rating": s.get("poster_rating"), "reviews": s.get("poster_reviews") or 0,
                "standing": "paused" if paused(user) else ("good" if not (user["strikes"] or 0) else "warned")}
    return {"jobs": s.get("jobs") or 0, "bonus_won": s.get("bonus_won") or 0, "dropouts": s.get("dropouts") or 0,
            "rating": s.get("helper_rating"), "reviews": s.get("helper_reviews") or 0, "by_cat": s.get("by_cat") or {},
            "standing": "paused" if paused(user) else ("good" if not (user["strikes"] or 0) else "warned")}


# ---------------------------------------------------------------------------------- reports
@anvil.server.callable(require_user=True)
def report(kind, text, bounty_id=None, user_id=None):
    """Anyone signed in can report a bounty or a person. Moderators see it in Admin -> Trust & safety."""
    me = C.require_user()
    if kind not in REPORT_KINDS:
        return C.fail("Pick what's wrong.")
    text = C.text(text, 1000, multiline=True)
    if len(text) < 10:
        return C.fail("Tell us a little more (at least 10 characters), so a moderator can act on it.")
    if C.rate_limited("report", 10, 3600):
        return C.fail("That's a lot of reports in one hour. A moderator will look at the ones you sent.")
    b = C.row_by_id(app_tables.bounties, bounty_id) if bounty_id else None
    subject = C.row_by_id(app_tables.users, user_id) if user_id else None
    if b is None and subject is None:
        return C.fail("We couldn't find what you're reporting.")
    if b is not None and subject is None:
        subject = b["helper"] if b["poster"] == me else b["poster"]
    if subject == me:
        return C.fail("You can't report yourself.")
    if app_tables.reports.get(reporter=me, bounty=b, subject=subject, status="open") is not None:
        return C.fail("You already reported this. A moderator will look at it soon.")
    app_tables.reports.add_row(reporter=me, bounty=b, subject=subject, kind=kind, text=text, status="open",
                               note="", created=C.now(), is_demo=False)
    hidden = False
    if b is not None and b["status"] == "open":
        reporters = {r["reporter"].get_id() for r in app_tables.reports.search(bounty=b, status="open") if r["reporter"] is not None}
        if len(reporters) >= 3:
            b["status"] = "review"
            b["flags"] = list(b["flags"] or []) + ["Reported by %d neighbours" % len(reporters)]
            hidden = True
    return C.ok(hidden=hidden)


# ---------------------------------------------------------------------------------- admin: review queue
def _admin_bounty(b):
    p = b["poster"]
    return {"id": b.get_id(), "title": b["title"], "details": b["details"] or "", "task": b["task"], "area": b["area"] or "",
            "base": b["base"], "bonus": b["bonus"] or 0, "status": b["status"], "flags": list(b["flags"] or []),
            "created": C.iso(b["created"]), "poster": C.name_of(p), "poster_email": p["email"] if p else "",
            "poster_strikes": (p["strikes"] or 0) if p else 0, "helper": C.name_of(b["helper"]) if b["helper"] else None,
            "demo": bool(b["is_demo"]), "dispute": b["dispute_reason"] or "", "dispute_by": b["dispute_by"] or "",
            "quality": b["quality"], "amount_due": b["amount_due"]}


@anvil.server.callable(require_user=True)
def admin_queue():
    C.require_admin()
    rows = app_tables.bounties.search(tables.order_by("created", ascending=True), status="review")
    return {"items": [_admin_bounty(b) for b in rows]}


@anvil.server.callable(require_user=True)
def admin_approve(bounty_id):
    C.require_admin()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["status"] != "review":
        return C.fail("That bounty isn't waiting for review any more.")
    b.update(status="open", updated=C.now())
    from . import Bounties
    Bounties.log(b, "admin", "Approved by a moderator: it's on the board.")
    return C.ok()


@anvil.server.callable(require_user=True)
def admin_reject(bounty_id, note):
    C.require_admin()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["status"] not in ("review", "open"):
        return C.fail("That bounty can't be rejected now.")
    note = C.text(note, 300) or "It doesn't follow the rules for bounties."
    b.update(status="rejected", updated=C.now(), cancel_reason=note)
    from . import Bounties
    Bounties.log(b, "admin", "Not approved: " + note)
    return C.ok()


# ---------------------------------------------------------------------------------- admin: trust & safety
def _person(u):
    if u is None:
        return None
    return {"id": u.get_id(), "name": C.name_of(u), "email": u["email"], "strikes": u["strikes"] or 0, "paused": paused(u),
            "last_strike": stats(u).get("last_strike") or ""}


@anvil.server.callable(require_user=True)
def admin_safety():
    C.require_admin()
    disputes = [_admin_bounty(b) for b in app_tables.bounties.search(tables.order_by("updated", ascending=False), status="disputed")]
    reps = []
    for r in app_tables.reports.search(tables.order_by("created", ascending=False))[:150]:
        reps.append({"id": r.get_id(), "kind": r["kind"], "kind_label": REPORT_KINDS.get(r["kind"], r["kind"]), "text": r["text"],
                     "status": r["status"], "note": r["note"] or "", "created": C.iso(r["created"]),
                     "reporter": C.name_of(r["reporter"]), "subject": _person(r["subject"]),
                     "bounty": {"id": r["bounty"].get_id(), "title": r["bounty"]["title"]} if r["bounty"] is not None else None})
    people = [_person(u) for u in app_tables.users.search() if (u["strikes"] or 0) > 0 or u["paused"]]
    return {"disputes": disputes, "reports": reps, "people": people,
            "counts": {"disputes": len(disputes), "reports": len([r for r in reps if r["status"] == "open"]), "people": len(people)}}


@anvil.server.callable(require_user=True)
def admin_resolve_report(report_id, action, note=""):
    C.require_admin()
    r = C.row_by_id(app_tables.reports, report_id)
    if r is None:
        return C.fail("That report no longer exists.")
    if action not in ("uphold", "dismiss"):
        return C.fail("Uphold or dismiss?")
    if r["status"] != "open":
        return C.fail("That report was already handled.")
    r.update(status="upheld" if action == "uphold" else "dismissed", note=C.text(note, 300), resolved_at=C.now())
    if action == "uphold":
        strike(r["subject"], REPORT_KINDS.get(r["kind"], "Report") + " (upheld)")
    return C.ok()


@anvil.server.callable(require_user=True)
def admin_resolve_dispute(bounty_id, outcome, strike_who=None, note=""):
    """outcome: full (base + bonus owed), base (base only), done (payment confirmed, close it), cancel (nothing owed)."""
    C.require_admin()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["status"] != "disputed":
        return C.fail("That bounty isn't in dispute.")
    if outcome not in ("full", "base", "done", "cancel"):
        return C.fail("Pick an outcome.")
    if strike_who not in (None, "", "poster", "helper"):
        return C.fail("Strike the poster, the helper, or nobody.")
    note = C.text(note, 300)
    from . import Bounties, Work
    now = C.now()
    if outcome in ("full", "base"):
        earned = outcome == "full" and (b["bonus"] or 0) > 0
        b.update(status="validated", bonus_earned=earned, amount_due=b["base"] + ((b["bonus"] or 0) if earned else 0),
                 validated_at=now, paid_at=None, updated=now)
        text = "A moderator settled the dispute: %s is owed." % C.money(b["amount_due"])
    elif outcome == "done":
        Work.finish(b)
        text = "A moderator settled the dispute: payment confirmed, the job is closed."
    else:
        b.update(status="cancelled", amount_due=0, updated=now, cancel_reason="Closed by a moderator after a dispute.")
        text = "A moderator closed the bounty after the dispute: nothing is owed."
    if note:
        text += " Note: " + note
    if strike_who:
        strike(b[strike_who], "Dispute on \"%s\"" % b["title"])
    Bounties.log(b, "admin", text)
    Bounties.ping(b, "poster")
    Bounties.ping(b, "helper")
    return C.ok()


@anvil.server.callable(require_user=True)
def admin_set_standing(user_id, strikes, paused_flag):
    me = C.require_admin()
    u = C.row_by_id(app_tables.users, user_id)
    if u is None:
        return C.fail("That account no longer exists.")
    if u == me and paused_flag:
        return C.fail("You can't pause yourself.")
    n = int(C.number(strikes, 0) or 0)
    u.update(strikes=max(0, min(9, n)), paused=bool(paused_flag))
    return C.ok(person=_person(u))


@anvil.server.callable(require_user=True)
def admin_bounties(status=None):
    C.require_admin()
    rows = app_tables.bounties.search(tables.order_by("created", ascending=False))
    items = [_admin_bounty(b) for b in rows if not status or status == "all" or b["status"] == status]
    return {"items": items[:300], "total": len(items)}


@anvil.server.callable(require_user=True)
def admin_remove_bounty(bounty_id, note=""):
    C.require_admin()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None:
        return C.fail("That bounty no longer exists.")
    b.update(status="removed", updated=C.now(), cancel_reason=C.text(note, 300) or "Removed by a moderator.")
    from . import Bounties
    Bounties.log(b, "admin", "Removed by a moderator.")
    return C.ok()
