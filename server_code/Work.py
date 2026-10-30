"""The work itself: offers, picking a helper, proof, validation (quality % and the bonus), payment,
disputes, the chat, reviews, and the "My jobs" and "Ledger" pages.

Money never moves through the app: the poster pays cash or an Interac e-Transfer themselves, then both
sides confirm. The app keeps the record (amount owed, method, reference, dates), so a real payment
service can later plug in where mark_paid / confirm_received are.

The quality score is the share of the checklist the poster ticks (4 of 5 = 80%). The base bounty is owed
once the work is validated; the bonus only when the score reaches the bar the poster set. Any unticked
item needs a reason the helper can read, and how often a poster pays bonuses shows on their profile.
"""
import datetime as dt

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Bounties, Catalog, Trust
from .Bounties import log, ping

HELPER_TAGS = ["On time", "Great work", "Friendly", "Went the extra mile", "Tidy", "Good communication"]
POSTER_TAGS = ["Paid promptly", "Clear instructions", "Fair grader", "Friendly", "Tools ready", "Good communication"]
BLIND_DAYS = 7


def _bounty_for(me, bounty_id, need_role, statuses):
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None:
        return None, C.fail("That bounty doesn't exist any more.")
    if Bounties.role(b, me) != need_role:
        return None, C.fail("Only the %s can do that." % ("person who posted it" if need_role == "poster" else "helper on this job"))
    if b["status"] not in statuses:
        return None, C.fail("That can't be done at this stage (the bounty is %s)." % b["status"])
    return b, None


# ---------------------------------------------------------------------------------- offers
@anvil.server.callable(require_user=True)
def make_offer(bounty_id, message, when_text="", ask=None):
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    if b is None or b["status"] != "open":
        return C.fail("This bounty isn't taking offers any more.")
    if b["poster"] == me:
        return C.fail("You can't make an offer on your own bounty.")
    why = Trust.can_help(me)
    if why:
        return C.fail(why)
    message = C.text(message, 500, multiline=True)
    if len(message) < 10:
        return C.fail("Say hello and why you're a good fit (at least 10 characters).")
    ask = b["base"] if ask in (None, "") else C.number(ask)
    if ask is None or ask != int(ask) or ask < b["base"]:
        return C.fail("Your price can't be below the posted bounty (%s)." % C.money(b["base"]))
    if ask > min(b["base"] * 2, Catalog.MAX_BASE):
        return C.fail("Counter-offers go up to double the bounty (%s)." % C.money(min(b["base"] * 2, Catalog.MAX_BASE)))
    if C.rate_limited("offer", 20, 3600):
        return C.fail("That's a lot of offers in one hour. Wait for answers first.")
    pending = len(app_tables.offers.search(helper=me, status="pending"))
    if pending >= 10:
        return C.fail("You have 10 offers waiting for answers. Withdraw some first.")
    message, hidden = Trust.redact(message)
    o = app_tables.offers.get(bounty=b, helper=me)
    if o is not None and o["status"] in ("pending", "declined"):
        return C.fail("You already made an offer on this bounty." if o["status"] == "pending" else "The poster went with someone else.")
    fields = dict(message=message, when_text=C.text(when_text, 80), ask=int(ask), status="pending", created=C.now())
    if o is None:
        app_tables.offers.add_row(bounty=b, helper=me, is_demo=False, **fields)
    else:
        o.update(**fields)
    b["offer_count"] = len([x for x in app_tables.offers.search(bounty=b) if x["status"] == "pending"])
    ping(b, "poster")
    return C.ok(hidden_contact=hidden)


@anvil.server.callable(require_user=True)
def withdraw_offer(offer_id):
    me = C.require_user()
    o = C.row_by_id(app_tables.offers, offer_id)
    if o is None or o["helper"] != me:
        return C.fail("That offer isn't yours.")
    if o["status"] != "pending":
        return C.fail("Only a waiting offer can be withdrawn.")
    o["status"] = "withdrawn"
    b = o["bounty"]
    b["offer_count"] = max(0, (b["offer_count"] or 1) - 1)
    return C.ok()


@anvil.server.callable(require_user=True)
def decline_offer(offer_id):
    me = C.require_user()
    o = C.row_by_id(app_tables.offers, offer_id)
    if o is None or o["bounty"]["poster"] != me:
        return C.fail("Only the poster can answer offers.")
    if o["status"] != "pending":
        return C.fail("That offer was already answered.")
    o["status"] = "declined"
    o["bounty"]["offer_count"] = max(0, (o["bounty"]["offer_count"] or 1) - 1)
    return C.ok()


@anvil.server.callable(require_user=True)
def accept_offer(offer_id):
    me = C.require_user()
    o = C.row_by_id(app_tables.offers, offer_id)
    if o is None or o["bounty"]["poster"] != me:
        return C.fail("Only the poster can pick a helper.")
    b = o["bounty"]
    if b["status"] != "open" or o["status"] != "pending":
        return C.fail("That offer can't be accepted any more.")
    why = Trust.can_post(me) if Trust.overdue(me) or Trust.paused(me) else None
    if why:
        return C.fail(why)
    why = Trust.can_help(o["helper"])
    if why:
        return C.fail("%s can't take on another job right now. Pick someone else, or wait a little." % C.public_name(o["helper"]))
    now = C.now()
    raised = o["ask"] > b["base"]
    b.update(helper=o["helper"], status="assigned", assigned_at=now, updated=now, base=o["ask"], offer_count=0)
    o["status"] = "accepted"
    for other in app_tables.offers.search(bounty=b, status="pending"):
        other["status"] = "declined"
    log(b, "poster", "Picked %s%s. The address is now shared with them." % (C.public_name(o["helper"]),
                                                                            (" at their price of %s" % C.money(o["ask"])) if raised else ""))
    ping(b, "helper")
    return C.ok()


@anvil.server.callable(require_user=True)
def back_out(bounty_id, reason):
    """The helper can't do it after all: the bounty goes back on the board (it counts as a drop-out)."""
    me = C.require_user()
    b, err = _bounty_for(me, bounty_id, "helper", ("assigned",))
    if err:
        return err
    reason = C.text(reason, 300)
    if len(reason) < 10:
        return C.fail("Tell the poster why (at least 10 characters).")
    b.update(helper=None, status="open", assigned_at=None, updated=C.now(), base=b["posted_base"] or b["base"])
    o = app_tables.offers.get(bounty=b, helper=me)
    if o is not None:
        o["status"] = "withdrawn"
    for other in app_tables.offers.search(bounty=b, status="declined"):
        other["status"] = "pending"
    b["offer_count"] = len(app_tables.offers.search(bounty=b, status="pending"))
    log(b, "helper", "%s backed out: %s The bounty is back on the board." % (C.public_name(me), reason))
    ping(b, "poster")
    Trust.bump(me, dropouts=1)
    return C.ok()


# ---------------------------------------------------------------------------------- proof + validation
def _checks(values, n):
    if not isinstance(values, list) or len(values) != n:
        return None
    return [bool(v) for v in values]


@anvil.server.callable(require_user=True)
def submit_proof(bounty_id, self_checks, note, photo_keys, payout_method, payout_email="", remember=False):
    me = C.require_user()
    b, err = _bounty_for(me, bounty_id, "helper", ("assigned",))
    if err:
        return err
    checks = _checks(self_checks, len(b["checklist"] or []))
    if checks is None:
        return C.fail("Go through the checklist first.")
    if not any(checks):
        return C.fail("Tick what you did. If you couldn't do the job, back out instead.")
    allowed = {"cash": ["cash"], "etransfer": ["etransfer"], "either": ["cash", "etransfer"]}[b["pay_method"]]
    if payout_method not in allowed:
        return C.fail("This bounty pays by %s." % ("cash" if allowed == ["cash"] else "e-Transfer" if allowed == ["etransfer"] else "cash or e-Transfer"))
    email = C.text(payout_email, 200).lower()
    if payout_method == "etransfer":
        if not Trust.valid_email(email):
            return C.fail("Add the email your bank uses for Interac e-Transfers.")
    else:
        email = ""
    from . import Photos
    photos, problem = Photos.claim(me, photo_keys or [], 6, bounty=b)
    if problem:
        return C.fail(problem)
    if not photos:
        return C.fail("Add at least one photo of the finished job: it's your proof.")
    for p in photos:
        p["bounty"] = b
    now = C.now()
    b.update(status="submitted", submitted_at=now, updated=now, self_checks=checks, proof_note=C.text(note, 800, multiline=True),
             proof_photos=[p["key"] for p in photos], payout_method=payout_method, payout_email=email)
    if remember and email:
        me["payout_email"] = email
    log(b, "helper", "Sent proof: %d of %d checklist items done. Waiting for the poster to check (48 h, then it's validated automatically)."
        % (sum(checks), len(checks)))
    ping(b, "poster")
    return C.ok()


def apply_validation(b, checks, note, auto=False):
    n = max(1, len(checks))
    quality = int(round(100.0 * sum(1 for c in checks if c) / n))
    bonus = b["bonus"] or 0
    earned = bonus > 0 and quality >= (b["bar"] or 80)
    now = C.now()
    b.update(status="validated", checks=checks, quality=quality, bonus_earned=earned, amount_due=b["base"] + (bonus if earned else 0),
             validate_note=note, validated_at=now, updated=now, auto_validated=auto)
    if bonus:
        Trust.bump(b["poster"], bonus_jobs=1, bonus_paid=1 if earned else 0)
        if earned:
            Trust.bump(b["helper"], bonus_won=1)
    who = "system" if auto else "poster"
    text = ("Validated automatically after 48 h with the helper's checklist: " if auto else "Validated: ") + \
        "quality %d%%%s. %s is owed." % (quality, (" (bonus earned!)" if earned else " (bonus not reached)") if bonus else "", C.money(b["amount_due"]))
    log(b, who, text)
    ping(b, "helper")
    if auto:
        ping(b, "poster")


@anvil.server.callable(require_user=True)
def validate_work(bounty_id, checks, note=""):
    me = C.require_user()
    b, err = _bounty_for(me, bounty_id, "poster", ("submitted",))
    if err:
        return err
    checks = _checks(checks, len(b["checklist"] or []))
    if checks is None:
        return C.fail("Go through the checklist first.")
    note = C.text(note, 600, multiline=True)
    if not all(checks) and len(note) < 10:
        return C.fail("Some items aren't ticked: tell the helper what was missing (at least 10 characters). It's only fair.")
    apply_validation(b, checks, note)
    return C.ok(quality=b["quality"], bonus_earned=bool(b["bonus_earned"]), amount_due=b["amount_due"],
                payout={"method": b["payout_method"], "email": b["payout_email"] or ""})


# ---------------------------------------------------------------------------------- payment
def finish(b):
    """Close a job as done and count it on both records."""
    now = C.now()
    if b["paid_at"] is None:
        _count_payment(b, now)
        b["paid_at"] = now
    b.update(status="done", done_at=now, updated=now)
    Trust.bump(b["poster"], completed=1)
    Trust.bump(b["helper"], jobs=1)
    t = Catalog.task(b["task"]) or Catalog.TASK_BY_KEY["other"]
    Trust.bump_cat(b["helper"], t["cat"])


def _count_payment(b, when):
    fast = b["validated_at"] is not None and (when - b["validated_at"]).total_seconds() <= 48 * 3600
    Trust.bump(b["poster"], paid=1, paid_fast=1 if fast else 0)


@anvil.server.callable(require_user=True)
def mark_paid(bounty_id, method, ref=""):
    me = C.require_user()
    b, err = _bounty_for(me, bounty_id, "poster", ("validated",))
    if err:
        return err
    if method not in ("cash", "etransfer"):
        return C.fail("Cash or e-Transfer?")
    if method != b["payout_method"] and b["payout_method"]:
        return C.fail("The helper asked to be paid by %s." % ("cash" if b["payout_method"] == "cash" else "e-Transfer"))
    ref = C.text(ref, 40)
    if method == "etransfer" and len(ref) < 4:
        return C.fail("Add the e-Transfer reference number from your bank (it helps if anything goes wrong).")
    now = C.now()
    _count_payment(b, now)
    b.update(status="paid", paid_method=method, paid_ref=ref, paid_at=now, updated=now)
    log(b, "poster", "Paid %s by %s%s. Waiting for the helper to confirm." % (C.money(b["amount_due"]),
                                                                             "cash" if method == "cash" else "e-Transfer",
                                                                             (" (ref. %s)" % ref) if ref else ""))
    ping(b, "helper")
    return C.ok()


@anvil.server.callable(require_user=True)
def confirm_received(bounty_id):
    me = C.require_user()
    b, err = _bounty_for(me, bounty_id, "helper", ("validated", "paid"))
    if err:
        return err
    finish(b)
    log(b, "helper", "Got the %s. Job done!" % C.money(b["amount_due"]))
    ping(b, "poster")
    return C.ok()


@anvil.server.callable(require_user=True)
def open_dispute(bounty_id, reason):
    """Either side asks a moderator: unfair score, not paid, poor work, no-show..."""
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    r = Bounties.role(b, me) if b is not None else None
    if r not in ("poster", "helper"):
        return C.fail("Only the poster and the helper can open a dispute.")
    if b["status"] not in ("assigned", "submitted", "validated", "paid"):
        return C.fail("A dispute can be opened while the job is under way, until it's closed.")
    reason = C.text(reason, 800, multiline=True)
    if len(reason) < 20:
        return C.fail("Explain what went wrong (at least 20 characters). A moderator will read both sides.")
    b.update(status="disputed", dispute_by=r, dispute_reason=reason, dispute_from=b["status"], updated=C.now())
    log(b, r, "Opened a dispute: " + reason)
    ping(b, "helper" if r == "poster" else "poster")
    return C.ok()


# ---------------------------------------------------------------------------------- chat
@anvil.server.callable(require_user=True)
def send_message(bounty_id, text):
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    r = Bounties.role(b, me) if b is not None else None
    if r not in ("poster", "helper"):
        return C.fail("Only the poster and the matched helper can chat here.")
    if b["status"] in Bounties.CLOSED or b["status"] == "open":
        return C.fail("The chat opens when a helper is picked, and closes with the bounty.")
    text = C.text(text, 1000, multiline=True)
    if not text:
        return C.fail("Type a message first.")
    if C.rate_limited("message", 60, 3600):
        return C.fail("That's a lot of messages. Take a short break.")
    m = app_tables.messages.add_row(bounty=b, sender=me, text=text, created=C.now(), is_demo=False)
    ping(b, "helper" if r == "poster" else "poster")
    return C.ok(message={"mine": True, "who": C.public_name(me), "text": m["text"], "at": C.iso(m["created"])})


# ---------------------------------------------------------------------------------- reviews (blind)
def _review(rv):
    return {"stars": rv["stars"], "tags": list(rv["tags"] or []), "text": rv["text"] or "", "author": C.public_name(rv["author"]),
            "author_id": rv["author"].get_id() if rv["author"] else None, "role": rv["subject_role"], "at": C.iso(rv["created"]),
            "bounty": rv["bounty"]["title"] if rv["bounty"] is not None else "", "task": rv["bounty"]["task"] if rv["bounty"] is not None else ""}


def visible(rv):
    """Blind reviews: shown once both sides reviewed, or BLIND_DAYS after the job closed."""
    b = rv["bounty"]
    if b is None:
        return True
    both = len(app_tables.reviews.search(bounty=b)) >= 2
    return both or (b["done_at"] is not None and b["done_at"] < C.now() - dt.timedelta(days=BLIND_DAYS))


def reviews_for(b, me):
    mine = app_tables.reviews.get(bounty=b, author=me) if me is not None else None
    theirs = [rv for rv in app_tables.reviews.search(bounty=b) if rv["author"] != me]
    other = theirs[0] if theirs else None
    return {"mine": _review(mine) if mine else None, "theirs": _review(other) if other and (mine or visible(other)) else None,
            "theirs_waiting": bool(other) and not mine, "tags": HELPER_TAGS if Bounties.role(b, me) == "poster" else POSTER_TAGS}


def _rerate(subject, subject_role):
    """Average stars, counting each neighbour once (their latest review), so friends can't farm a rating."""
    latest = {}
    for rv in app_tables.reviews.search(tables.order_by("created"), subject=subject, subject_role=subject_role):
        latest[rv["author"].get_id() if rv["author"] else rv.get_id()] = rv["stars"]
    s = Trust.stats(subject)
    s[subject_role + "_rating"] = round(sum(latest.values()) / len(latest), 2) if latest else None
    s[subject_role + "_reviews"] = len(latest)
    subject["stats"] = s


@anvil.server.callable(require_user=True)
def leave_review(bounty_id, stars, tags, text=""):
    me = C.require_user()
    b = C.row_by_id(app_tables.bounties, bounty_id)
    r = Bounties.role(b, me) if b is not None else None
    if r not in ("poster", "helper") or b["status"] != "done":
        return C.fail("You can review once the job is done, if you took part in it.")
    if app_tables.reviews.get(bounty=b, author=me) is not None:
        return C.fail("You already reviewed this job.")
    stars = C.number(stars)
    if stars not in (1, 2, 3, 4, 5):
        return C.fail("Pick 1 to 5 stars.")
    allowed = HELPER_TAGS if r == "poster" else POSTER_TAGS
    tags = [t for t in (tags or []) if t in allowed][:4] if isinstance(tags, list) else []
    subject = b["helper"] if r == "poster" else b["poster"]
    subject_role = "helper" if r == "poster" else "poster"
    text, _ = Trust.redact(C.text(text, 600, multiline=True))
    app_tables.reviews.add_row(bounty=b, author=me, subject=subject, subject_role=subject_role, stars=int(stars), tags=tags,
                               text=text, created=C.now(), is_demo=False)
    _rerate(subject, subject_role)
    ping(b, subject_role)
    return C.ok()


# ---------------------------------------------------------------------------------- My jobs + Ledger
def _needs(b, r, me):
    s = b["status"]
    if r == "poster":
        if s == "open" and (b["offer_count"] or 0):
            return "Pick a helper (%s)" % _plural(b["offer_count"], "offer")
        if s == "submitted":
            return "Check the work"
        if s == "validated":
            return "Pay %s" % C.money(b["amount_due"])
    else:
        if s == "assigned":
            return "Do the job, then send proof"
        if s in ("validated", "paid"):
            return "Confirm you got paid" if s == "paid" else "Waiting for %s" % C.money(b["amount_due"])
    if s == "done" and app_tables.reviews.get(bounty=b, author=me) is None:
        return "Leave a review"
    return ""


def _plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _job(b, r, me):
    other = b["helper"] if r == "poster" else b["poster"]
    needs = _needs(b, r, me)
    return {"id": b.get_id(), "title": b["title"], "task": b["task"], "status": b["status"], "area": b["area"] or "",
            "base": b["base"], "bonus": b["bonus"] or 0, "bar": b["bar"] or 80, "amount_due": b["amount_due"],
            "quality": b["quality"], "bonus_earned": bool(b["bonus_earned"]), "updated": C.iso(b["updated"]),
            "when_date": C.iso(b["when_date"]), "when_note": b["when_note"] or "", "offers": b["offer_count"] or 0,
            "other": C.public_name(other) if other is not None else None, "unread": b[r + "_unread"] or 0,
            "needs": needs, "urgent": bool(needs) and not needs.startswith("Waiting"), "pay": b["pay_method"]}


@anvil.server.callable(require_user=True)
def get_jobs():
    me = C.require_user()
    Bounties.sweep()
    posted = [_job(b, "poster", me) for b in app_tables.bounties.search(tables.order_by("updated", ascending=False), poster=me)
              if b["status"] != "removed"]
    doing = [_job(b, "helper", me) for b in app_tables.bounties.search(tables.order_by("updated", ascending=False), helper=me)]
    offers = []
    for o in app_tables.offers.search(tables.order_by("created", ascending=False), helper=me):
        if o["status"] in ("pending", "declined") and o["bounty"] is not None and o["bounty"]["helper"] != me:
            b = o["bounty"]
            offers.append({"id": o.get_id(), "bounty": b.get_id(), "title": b["title"], "task": b["task"], "ask": o["ask"],
                           "status": o["status"] if b["status"] == "open" or o["status"] == "declined" else "closed",
                           "created": C.iso(o["created"]), "area": b["area"] or ""})
    todo = len([j for j in posted + doing if j["urgent"]])
    return {"posted": posted, "doing": doing, "offers": offers[:40], "todo": todo,
            "limits": {"post": Trust.can_post(me), "help": Trust.can_help(me)}}


@anvil.server.callable(require_user=True)
def get_ledger():
    """Every amount owed, sent and settled, both ways. A record only: the money moves outside the app."""
    me = C.require_user()
    rows = []
    for r, col in (("poster", "poster"), ("helper", "helper")):
        q = {col: me}
        for b in app_tables.bounties.search(**q):
            if b["status"] not in ("validated", "paid", "done", "disputed") or b["amount_due"] is None:
                continue
            other = b["helper"] if r == "poster" else b["poster"]
            state = {"validated": "owed", "paid": "sent", "done": "settled", "disputed": "disputed"}[b["status"]]
            when = b["done_at"] or b["paid_at"] or b["validated_at"]
            rows.append({"id": b.get_id(), "title": b["title"], "task": b["task"], "dir": "out" if r == "poster" else "in",
                         "amount": b["amount_due"], "base": b["base"], "bonus": b["bonus"] if b["bonus_earned"] else 0,
                         "quality": b["quality"], "method": b["paid_method"] or b["payout_method"] or "", "ref": b["paid_ref"] or "",
                         "state": state, "at": C.iso(when), "other": C.public_name(other) if other is not None else ""})
    rows.sort(key=lambda x: x["at"] or "", reverse=True)

    def total(d, states):
        return sum(x["amount"] for x in rows if x["dir"] == d and x["state"] in states)
    return {"rows": rows, "totals": {"earned": total("in", ("settled",)), "coming": total("in", ("owed", "sent")),
                                     "spent": total("out", ("settled",)), "owe": total("out", ("owed",)),
                                     "bonus": sum(x["bonus"] for x in rows if x["dir"] == "in" and x["state"] == "settled")}}
