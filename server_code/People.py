"""People: a neighbour's public profile (record, badges, reviews), and your own helper settings:
bio, skills, the area you work around, and the email your bank uses for Interac e-Transfers.

Public profiles show a first name + last initial, the area name, the record and the reviews that are no
longer blind. Never an email, never the payout email, never an address.
"""
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Catalog, Trust, Work

SKILLS = Catalog.SKILLS


def badges(u):
    s = Trust.stats(u)
    by = s.get("by_cat") or {}
    out = []

    def add(key, name, why):
        out.append({"key": key, "name": name, "why": why})
    jobs = s.get("jobs") or 0
    if jobs >= 1:
        add("first", "First job", "Finished a first bounty")
    if jobs >= 10:
        add("trusted", "Trusted neighbour", "10 bounties finished")
    if (by.get("yard") or 0) >= 3:
        add("leaf", "Leaf legend", "3+ yard jobs")
    if (by.get("snow") or 0) >= 3:
        add("snow", "Snow warrior", "3+ snow jobs")
    if (by.get("moving") or 0) >= 3:
        add("lift", "Heavy lifter", "3+ moving jobs")
    if (by.get("junk") or 0) >= 3:
        add("junk", "Junk buster", "3+ junk jobs")
    if (s.get("bonus_won") or 0) >= 3:
        add("bonus", "Bonus hunter", "Earned the quality bonus 3+ times")
    if (s.get("helper_reviews") or 0) >= 3 and (s.get("helper_rating") or 0) >= 4.8:
        add("five", "Five-star", "4.8+ stars from 3+ neighbours")
    if (s.get("paid") or 0) >= 3 and s.get("paid_fast") == s.get("paid"):
        add("prompt", "Prompt payer", "Always paid within 2 days")
    if (s.get("bonus_jobs") or 0) >= 3 and (s.get("bonus_paid") or 0) * 10 >= (s.get("bonus_jobs") or 1) * 8:
        add("fair", "Fair grader", "Pays the bonus 80%+ of the time")
    return out


@anvil.server.callable
def get_neighbour(user_id):
    u = C.row_by_id(app_tables.users, user_id)
    if u is None or u["enabled"] is False and not u["is_demo"]:
        return C.fail("We couldn't find that neighbour.")
    me = C.me()
    reviews = []
    for rv in app_tables.reviews.search(tables.order_by("created", ascending=False), subject=u):
        if Work.visible(rv):
            reviews.append(Work._review(rv))
    open_rows = app_tables.bounties.search(tables.order_by("created", ascending=False), poster=u, status="open")
    return C.ok(person={
        "id": u.get_id(), "name": C.public_name(u), "area": u["spot_label"] or "", "joined": C.iso(u["signed_up"]),
        "bio": u["bio"] or "", "skills": list(u["skills"] or []), "helper_on": u["helper_on"] is not False,
        "as_helper": Trust.record(u, "helper"), "as_poster": Trust.record(u, "poster"), "badges": badges(u),
        "reviews": reviews[:40], "me": me is not None and me == u,
        "open": [{"id": b.get_id(), "title": b["title"], "task": b["task"], "base": b["base"], "bonus": b["bonus"] or 0,
                  "area": b["area"] or ""} for b in open_rows[:6]]})


@anvil.server.callable(require_user=True)
def update_helper_profile(bio, skills, payout_email, helper_on=True):
    me = C.require_user()
    bio, _ = Trust.redact(C.text(bio, 400, multiline=True))
    skills = [s for s in (skills or []) if s in SKILLS][:8] if isinstance(skills, list) else []
    email = C.text(payout_email, 200).lower()
    if email and not Trust.valid_email(email):
        return C.fail("That e-Transfer email doesn't look right.")
    me.update(bio=bio, skills=skills, payout_email=email, helper_on=bool(helper_on))
    from . import Accounts
    return C.ok(me=Accounts.me_dict(me))


@anvil.server.callable(require_user=True)
def set_spot(lat, lng, label):
    """Where you are (to sort bounties by distance). Others only ever see the area name."""
    me = C.require_user()
    lat, lng = C.number(lat), C.number(lng)
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return C.fail("Put a pin on the map first.")
    label = C.text(label, 60)
    if len(label) < 2:
        return C.fail("Give the area a name, like a neighbourhood.")
    me.update(spot_lat=round(lat, 4), spot_lng=round(lng, 4), spot_label=label)
    from . import Accounts
    return C.ok(me=Accounts.me_dict(me))
