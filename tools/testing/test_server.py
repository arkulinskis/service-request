"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python -I tools/testing/test_server.py          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

# ================================================================================== Service Request
import base64 as _b64
import datetime as _dt

D = M["DemoData"]
B = M["Bounties"]
TR = M["Trust"]
JPEG = "data:image/jpeg;base64," + _b64.b64encode(b"\xff\xd8\xff" + b"0" * 200).decode()
LEAF_CHECKS = ["Lawn raked clear of leaves", "Garden beds cleared", "Leaves bagged in paper yard bags", "Bags placed at the curb",
               "Walkway and steps swept"]


def bdata(**kw):
    d = dict(task="leaves", title="Rake and bag my leaves", details="Front lawn and the beds. Bags are in the shed, curb on Tuesday.",
             size="medium", when_date=(now.date() + _dt.timedelta(days=2)).isoformat(), when_note="Saturday morning",
             lat=45.5236, lng=-73.5810, area="Plateau", address="1234 rue Testing", base=20, bonus=10, bar=80,
             checklist=list(LEAF_CHECKS), pay_method="etransfer", photo_keys=[])
    d.update(kw)
    return d


def photo():
    return ok(call("upload_photo", JPEG, JPEG))["key"]


def bounty(bid):
    return ok(call("get_bounty", bid))["bounty"]


def row(bid):
    return T.bounties.get_by_id(bid)


# ---------------------------------------------------------------------------------- catalogue + demo board
as_user(None)
cat = call("get_catalog")
assert len(cat["tasks"]) >= 30 and cat["min_base"] == 20, "at least 30 neighbourly tasks, $20 minimum"
assert all(min(t["prices"]) >= 20 for t in cat["tasks"]), "suggested prices respect the minimum"
assert all(len(t["checklist"]) >= 4 for t in cat["tasks"])
board = call("get_board")
assert D.state() == "loaded" and board["total"] == len(D.OPEN), "demo loads on first visit"
blob = str(board)
assert "rue de l'Exemple" not in blob and "@example.com" not in blob, "no addresses or emails on the public board"
first = board["items"][0]
assert first["poster"]["name"].endswith(".") and first["dist"] is not None
assert all(i["status"] == "open" for i in board["items"])
flagged = [b for b in T.bounties.search(status="review")]
assert len(flagged) == 2, "demo has flagged posts for the moderators"
g = call("get_bounty", flagged[0].get_id())
assert g.get("gone") is True, "a bounty under review isn't shown to the public"
bad(call("get_bounty", "nope"))
pub = bounty(first["id"])
assert pub["role"] == "visitor" and "exact" not in pub and "messages" not in pub and "offers_list" not in pub

# ---------------------------------------------------------------------------------- people for the bounty tests
carl = person("carl@example.com", "Carl Duval")
dee = person("dee@example.com", "Dee Okafor")
gina = person("gina@example.com", "Gina Rossi")

# ---------------------------------------------------------------------------------- posting
as_user(None)
assert denied("post_bounty", bdata())
assert denied("upload_photo", JPEG, JPEG)
as_user(ana)
bad(call("post_bounty", "nonsense"))
bad(call("post_bounty", bdata(base=19)), "minimum $20")
bad(call("post_bounty", bdata(base=20.5)), "whole dollars")
bad(call("post_bounty", bdata(base=501)), "maximum")
bad(call("post_bounty", bdata(bonus=25)), "bonus can't be more than the bounty")
bad(call("post_bounty", bdata(bonus=3)), "bonus starts at $5")
bad(call("post_bounty", bdata(bar=83)), "bar in steps of 5")
bad(call("post_bounty", bdata(task="burglary")), "only catalogue tasks")
bad(call("post_bounty", bdata(lat=None)), "needs a pin")
bad(call("post_bounty", bdata(lat=48.85, lng=2.35)), "Canada only")
bad(call("post_bounty", bdata(address="")), "needs an address")
bad(call("post_bounty", bdata(title="Hey")), "title too short")
bad(call("post_bounty", bdata(checklist=["Only one"])), "checklist needs 2 items")
bad(call("post_bounty", bdata(pay_method="paypal")), "cash or e-Transfer only")
bad(call("post_bounty", bdata(when_date="2001-01-01")), "date in range")
bad(call("post_bounty", bdata(photo_keys=["not-a-photo"])), "unknown photo")
k = photo()
r = ok(call("post_bounty", bdata(photo_keys=[k], details="Front lawn and beds. Call me at 514-555-0199 or ana.lima@gmail.com")))
LEAVES = r["id"]
assert r["status"] == "open" and r["hidden_contact"], "contact details are hidden"
b = row(LEAVES)
assert "555" not in b["details"] and "gmail" not in b["details"] and b["photos"] == [k]
assert abs(b["pub_lat"] - b["lat"]) > 0.0005 or abs(b["pub_lng"] - b["lng"]) > 0.0005, "the public pin is moved"
km = M["common"].km(b["lat"], b["lng"], b["pub_lat"], b["pub_lng"])
assert 0.15 < km < 0.5, km
assert T.photos.get(key=k)["bounty"] == b
as_user(bob)
bad(call("post_bounty", bdata(photo_keys=[k])), "can't reuse someone else's photo")
as_user(ana)
r = ok(call("post_bounty", bdata(task="pickup", title="Pick up a parcel", details="Buy 2 gift cards for me and deliver the package downtown.")))
SCAM = r["id"]
assert r["status"] == "review" and "Mentions gift cards" in r["flags"] and "Carrying packages" in r["flags"]
bad(call("post_bounty", bdata()), "new accounts: 2 live bounties")
as_user(None)
assert call("get_bounty", SCAM).get("gone"), "flagged posts stay off the board"
assert LEAVES in [i["id"] for i in call("get_board")["items"]]
for txt, flag in [("Clean my roof gutters from the roof", "Roof work"), ("Babysit my kids while you rake", "Childcare"),
                  ("Send me the rest back by western union", "Mentions money transfers"), ("Pay me upfront for the bags", "Asks for money upfront")]:
    assert flag in TR.scan(txt), (txt, TR.scan(txt))
assert TR.scan("Rake the leaves and weed the garden beds, check the walk") == [], "ordinary jobs aren't flagged"
assert TR.redact("call 438 555 0101 or see www.x.com")[1] and TR.redact("rake 40 bags")[1] is False

# ---------------------------------------------------------------------------------- raising the bounty
as_user(bob)
bad(call("raise_bounty", LEAVES, 30, 10), "only the poster")
as_user(ana)
bad(call("raise_bounty", LEAVES, 19, 10))
bad(call("raise_bounty", LEAVES, 20, 5), "can't lower")
bad(call("raise_bounty", LEAVES, 20, 10), "same amount")
ok(call("raise_bounty", LEAVES, 22, 10))
row(LEAVES)["base"] = 20  # back to the user's example: $20 + $10 at 80%
row(LEAVES)["posted_base"] = 20

# ---------------------------------------------------------------------------------- offers
as_user(None)
assert denied("make_offer", LEAVES, "Hello there, I can help")
as_user(ana)
bad(call("make_offer", LEAVES, "I'll do my own job"), "no offers on your own bounty")
as_user(bob)
bad(call("make_offer", LEAVES, "hi"), "message too short")
bad(call("make_offer", LEAVES, "Happy to help this weekend", "Sat", 15), "below the bounty")
bad(call("make_offer", LEAVES, "Happy to help this weekend", "Sat", 41), "more than double")
ok(call("make_offer", LEAVES, "Happy to help! Text me at 514 555 0123", "Saturday 9 am"))
o_bob = T.offers.get(helper=bob)
assert "555" not in o_bob["message"] and o_bob["ask"] == 20
bad(call("make_offer", LEAVES, "Another offer from me"), "one offer each")
as_user(carl)
ok(call("make_offer", LEAVES, "I can come Sunday with my own rake", "Sunday", 25))
o_carl = T.offers.get(helper=carl)
as_user(dee)
ok(call("make_offer", LEAVES, "I'm nearby, any time Saturday", "Saturday"))
o_dee = T.offers.get(helper=dee)
ok(call("withdraw_offer", o_dee.get_id()))
bad(call("withdraw_offer", o_dee.get_id()), "already withdrawn")
as_user(bob)
bad(call("withdraw_offer", o_carl.get_id()), "not your offer")
as_user(ana)
vb = bounty(LEAVES)
assert vb["role"] == "poster" and len(vb["offers_list"]) == 2 and row(LEAVES)["offer_count"] == 2
assert "carl@example.com" not in str(vb), "offers never show emails"
as_user(carl)
assert bounty(LEAVES)["my_offer"]["ask"] == 25 and "offers_list" not in bounty(LEAVES)
bad(call("accept_offer", o_bob.get_id()), "only the poster picks")
as_user(ana)
ok(call("decline_offer", o_carl.get_id()))
bad(call("decline_offer", o_carl.get_id()))
ok(call("accept_offer", o_bob.get_id()))
b = row(LEAVES)
assert b["status"] == "assigned" and b["helper"] == bob and b["base"] == 20
bad(call("accept_offer", o_carl.get_id()), "already assigned")

# ---------------------------------------------------------------------------------- who sees what once assigned
as_user(carl)
assert call("get_bounty", LEAVES).get("gone"), "others no longer see an assigned bounty"
as_user(bob)
hb = bounty(LEAVES)
assert hb["role"] == "helper" and hb["exact"]["address"] == "1234 rue Testing", "the matched helper sees the address"
as_user(None)
assert "1234 rue Testing" not in str(call("get_board"))

# ---------------------------------------------------------------------------------- chat
as_user(carl)
bad(call("send_message", LEAVES, "hello"))
as_user(bob)
bad(call("send_message", LEAVES, "   "))
ok(call("send_message", LEAVES, "On my way at 9! I'm at 514-555-0123 if needed."))
assert row(LEAVES)["poster_unread"] >= 1
as_user(ana)
msgs = bounty(LEAVES)["messages"]
assert len(msgs) == 1 and not msgs[0]["mine"] and "555" in msgs[0]["text"], "contact is fine in a private chat once matched"
assert row(LEAVES)["poster_unread"] == 0, "opening the bounty marks it read"
ok(call("send_message", LEAVES, "Great, the bags are in the shed."))

# ---------------------------------------------------------------------------------- proof
as_user(ana)
bad(call("submit_proof", LEAVES, [True] * 5, "", [], "etransfer", "bob@bank.ca"), "only the helper")
as_user(bob)
bad(call("submit_proof", LEAVES, [True] * 4, "", [], "etransfer", "bob@bank.ca"), "checklist length")
bad(call("submit_proof", LEAVES, [False] * 5, "", [], "etransfer", "bob@bank.ca"), "nothing done")
bad(call("submit_proof", LEAVES, [True] * 5, "", [], "cash"), "this bounty pays by e-Transfer")
bad(call("submit_proof", LEAVES, [True] * 5, "", [], "etransfer", "not-an-email"))
bad(call("submit_proof", LEAVES, [True] * 5, "", [], "etransfer", "bob@bank.ca"), "needs a photo")
pk = photo()
ok(call("submit_proof", LEAVES, [True, True, True, True, False], "All bagged, didn't get to the walkway (it rained).", [pk],
        "etransfer", "bob.payouts@bank.ca", True))
b = row(LEAVES)
assert b["status"] == "submitted" and b["payout_email"] == "bob.payouts@bank.ca" and bob["payout_email"] == "bob.payouts@bank.ca"
as_user(ana)
pb = bounty(LEAVES)
assert pb["payout"] is None and "bob.payouts" not in str(pb), "the payout email stays hidden until the work is validated"
assert pb["proof"]["photos"] == [pk]
r_ok = M["Photos"].photo(k=pk)
assert r_ok.status == 200
assert M["Photos"].photo(k=photo()).status == 404, "photos not attached to a bounty aren't served"

# ---------------------------------------------------------------------------------- validation: the user's example
as_user(bob)
bad(call("validate_work", LEAVES, [True] * 5), "only the poster validates")
as_user(ana)
bad(call("validate_work", LEAVES, [True] * 3), "checklist length")
bad(call("validate_work", LEAVES, [True, True, True, True, False]), "a reason for unticked items")
v = ok(call("validate_work", LEAVES, [True, True, True, True, False], "Walkway wasn't swept, everything else perfect."))
assert v["quality"] == 80 and v["bonus_earned"] and v["amount_due"] == 30, "80% reaches the 80% bar: $20 + $10 bonus"
assert v["payout"]["email"] == "bob.payouts@bank.ca", "now the poster sees where to send the e-Transfer"
assert bounty(LEAVES)["payout"]["email"] == "bob.payouts@bank.ca"
as_user(carl)
assert call("get_bounty", LEAVES).get("gone") and "bob.payouts" not in str(call("get_bounty", LEAVES))

# ---------------------------------------------------------------------------------- payment
as_user(bob)
bad(call("mark_paid", LEAVES, "etransfer", "CA12345"), "only the poster marks it paid")
as_user(ana)
bad(call("mark_paid", LEAVES, "cash"), "the helper asked for e-Transfer")
bad(call("mark_paid", LEAVES, "etransfer", ""), "needs the reference")
ok(call("mark_paid", LEAVES, "etransfer", "CAa1B2c3"))
bad(call("confirm_received", LEAVES), "only the helper confirms")
as_user(bob)
ok(call("confirm_received", LEAVES))
b = row(LEAVES)
assert b["status"] == "done"
sa, sb = TR.stats(ana), TR.stats(bob)
assert sa["completed"] == 1 and sa["paid"] == 1 and sa["paid_fast"] == 1 and sa["bonus_jobs"] == 1 and sa["bonus_paid"] == 1
assert sb["jobs"] == 1 and sb["bonus_won"] == 1 and sb["by_cat"]["yard"] == 1

# ---------------------------------------------------------------------------------- blind reviews
as_user(carl)
bad(call("leave_review", LEAVES, 5, []), "only the two sides review")
as_user(bob)
bad(call("leave_review", LEAVES, 6, []))
ok(call("leave_review", LEAVES, 5, ["Paid promptly", "Not a real tag"], "Paid the same evening, thanks Ana! 514 555 0000"))
bad(call("leave_review", LEAVES, 4, []), "one review each")
rv = T.reviews.get(author=bob)
assert rv["tags"] == ["Paid promptly"] and "555" not in rv["text"]
as_user(ana)
rs = bounty(LEAVES)["reviews"]
assert rs["theirs"] is None and rs["theirs_waiting"], "blind until you review too"
ok(call("leave_review", LEAVES, 4, ["Great work"], "Good job, missed the walkway."))
assert bounty(LEAVES)["reviews"]["theirs"]["stars"] == 5
assert TR.stats(bob)["helper_rating"] == 4 and TR.stats(ana)["poster_rating"] == 5
nb = ok(call("get_neighbour", bob.get_id()))["person"]
assert nb["as_helper"]["jobs"] == 1 and nb["badges"][0]["key"] == "first" and len(nb["reviews"]) == 1
assert "bob@example.com" not in str(nb) and "bob.payouts" not in str(nb), "public profiles never show emails"
bad(call("get_neighbour", "nope"))

# ---------------------------------------------------------------------------------- jobs + ledger
as_user(ana)
jobs = call("get_jobs")
assert any(j["id"] == LEAVES for j in jobs["posted"])
led = call("get_ledger")
assert led["totals"]["spent"] == 30 and led["rows"][0]["dir"] == "out"
as_user(bob)
led = call("get_ledger")
assert led["totals"]["earned"] == 30 and led["totals"]["bonus"] == 10
assert any(j["id"] == LEAVES for j in call("get_jobs")["doing"])
as_user(None)
assert denied("get_jobs") and denied("get_ledger")


# ---------------------------------------------------------------------------------- a second job: overdue payment, dispute, moderator
def quick_job(poster, helper, **kw):
    as_user(poster)
    bid = ok(call("post_bounty", bdata(**kw)))["id"]
    as_user(helper)
    ok(call("make_offer", bid, "I can do it this week"))
    as_user(poster)
    ok(call("accept_offer", T.offers.get(bounty=row(bid), helper=helper).get_id()))
    as_user(helper)
    ok(call("submit_proof", bid, [True] * len(row(bid)["checklist"]), "Done", [photo()], "etransfer", "pay.me@bank.ca"))
    return bid


as_user(gina)
JOB2 = quick_job(gina, carl)
as_user(gina)
ok(call("validate_work", JOB2, [True] * 5))
row(JOB2)["validated_at"] = now - _dt.timedelta(days=4)
bad(call("post_bounty", bdata()), "an overdue payment blocks new posts")
bad(call("open_dispute", JOB2, "too short"))
as_user(dee)
bad(call("open_dispute", JOB2, "I wasn't even part of this one, but I'm complaining"))
as_user(carl)
ok(call("open_dispute", JOB2, "Validated four days ago and still no e-Transfer. I asked twice in the chat."))
assert row(JOB2)["status"] == "disputed" and row(JOB2)["dispute_by"] == "helper"
as_user(gina)
bad(call("mark_paid", JOB2, "etransfer", "REF123"), "frozen while disputed")
as_user(ana)
assert denied("admin_resolve_dispute", JOB2, "full")
as_user(admin)
saf = call("admin_safety")
assert any(d["id"] == JOB2 for d in saf["disputes"])
bad(call("admin_resolve_dispute", JOB2, "weird"))
ok(call("admin_resolve_dispute", JOB2, "full", "poster", "Poster reminded to pay."))
b = row(JOB2)
assert b["status"] == "validated" and b["amount_due"] == 30 and gina["strikes"] == 1
as_user(gina)
ok(call("mark_paid", JOB2, "etransfer", "REF999"))

# ---------------------------------------------------------------------------------- timers (sweep)
as_user(dee)
JOB3 = quick_job(dee, carl, base=40, bonus=0, pay_method="either")
row(JOB3)["submitted_at"] = now - _dt.timedelta(hours=49)
row(JOB2)["paid_at"] = now - _dt.timedelta(days=8)
B.sweep(force=True)
b3 = row(JOB3)
assert b3["status"] == "validated" and b3["auto_validated"] and b3["quality"] == 100 and b3["amount_due"] == 40, "proof auto-validates after 48 h"
assert row(JOB2)["status"] == "done", "an unquestioned payment closes after 7 days"

# ---------------------------------------------------------------------------------- backing out + late cancel
as_user(bob)
JOB4 = ok(call("post_bounty", bdata(task="driveway", title="Shovel my driveway", details="After the next snowfall please, before 8 am.",
                                    checklist=["Driveway cleared", "Plow ridge cleared"], base=30, bonus=0)))["id"]
as_user(carl)
ok(call("make_offer", JOB4, "I'll be there at 7 am"))
as_user(dee)
ok(call("make_offer", JOB4, "Me too, I live next door"))
as_user(bob)
ok(call("accept_offer", T.offers.get(bounty=row(JOB4), helper=carl).get_id()))
as_user(carl)
bad(call("back_out", JOB4, "sick"), "needs a reason")
ok(call("back_out", JOB4, "Sorry, I hurt my back this morning."))
b4 = row(JOB4)
assert b4["status"] == "open" and b4["helper"] is None and TR.stats(carl)["dropouts"] == 1
assert T.offers.get(bounty=b4, helper=dee)["status"] == "pending", "other offers come back"
as_user(bob)
ok(call("accept_offer", T.offers.get(bounty=b4, helper=dee).get_id()))
bad(call("cancel_bounty", JOB4, "nah"), "a booked helper deserves a reason")
ok(call("cancel_bounty", JOB4, "The snow melted overnight, sorry Dee!"))
assert row(JOB4)["status"] == "cancelled" and TR.stats(bob)["late_cancels"] == 1
as_user(dee)
bad(call("cancel_bounty", JOB4), "only the poster cancels")

# ---------------------------------------------------------------------------------- reports
as_user(dee)
OPEN1 = call("get_board")["items"][0]["id"]
bad(call("report", "weird", "This is not a real kind", OPEN1))
bad(call("report", "scam", "short", OPEN1))
ok(call("report", "scam", "Asked me to pay a deposit first.", OPEN1))
bad(call("report", "scam", "Reporting it a second time.", OPEN1), "one open report each")
bad(call("report", "rude", "I'm reporting myself for fun", None, dee.get_id()), "can't report yourself")
for who in (carl, bob):
    as_user(who)
    ok(call("report", "scam", "Same here, wanted money upfront.", OPEN1))
assert row(OPEN1)["status"] == "review", "3 reports take a bounty off the board"
as_user(ana)
assert denied("admin_queue") and denied("admin_safety") and denied("admin_approve", OPEN1)
as_user(admin)
q = call("admin_queue")["items"]
assert any(i["id"] == OPEN1 for i in q) and any(i["id"] == SCAM for i in q)
ok(call("admin_approve", OPEN1))
assert row(OPEN1)["status"] == "open"
ok(call("admin_reject", SCAM, "Gift cards and packages aren't allowed."))
assert row(SCAM)["status"] == "rejected"
bad(call("admin_approve", SCAM))
reps = call("admin_safety")["reports"]
rid = [r for r in reps if r["status"] == "open" and r["subject"] and r["subject"]["email"] == "kevin.demo@example.com"][0]["id"]
ok(call("admin_resolve_report", rid, "uphold", "Scam attempt."))
bad(call("admin_resolve_report", rid, "dismiss"), "already handled")
kevin = T.users.get(email="kevin.demo@example.com")
assert kevin["strikes"] == 1
ok(call("admin_set_standing", gina.get_id(), 3, False))
assert TR.paused(gina)
as_user(gina)
assert "paused" in bad(call("post_bounty", bdata()))["error"]
assert "paused" in bad(call("make_offer", OPEN1, "Can I help with this one?"))["error"]
as_user(admin)
ok(call("admin_set_standing", gina.get_id(), 0, False))
bad(call("admin_set_standing", admin.get_id(), 0, True), "can't pause yourself")
assert call("admin_bounties", "done")["total"] >= 2
ok(call("admin_remove_bounty", OPEN1, "Test removal"))
as_user(None)
bad(call("get_bounty", OPEN1), "removed bounties are gone")
as_user(admin)
ov = call("admin_overview")
assert ov["bounties"]["done"] >= 1 and ov["settled"] >= 60

# ---------------------------------------------------------------------------------- limits for helpers
as_user(ana)
ok(call("set_spot", 45.53, -73.6, "Mile End"))
bad(call("set_spot", None, 3, "x"))
assert call("get_board")["spot"]["label"] == "Mile End"
bad(call("update_helper_profile", "Hi", ["Own car"], "nope"))
me2 = ok(call("update_helper_profile", "I rake. Call 514 555 0101", ["Own car", "Flying"], "ana.pay@bank.ca"))["me"]
assert me2["skills"] == ["Own car"] and "555" not in me2["bio"] and me2["payout_email"] == "ana.pay@bank.ca"
as_user(None)
assert denied("set_spot", 1, 1, "x") and denied("update_helper_profile", "", [], "")

# ---------------------------------------------------------------------------------- demo data
as_user(admin)
real_before = len([b for b in T.bounties.search() if not b["is_demo"]])
ok(call("demo_remove"))
assert D.state() == "removed" and not T.users.search(is_demo=True) and not T.bounties.search(is_demo=True)
assert len(T.bounties.search()) == real_before, "removing demo data keeps real bounties"
as_user(None)
call("get_board")
assert D.state() == "removed", "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert len(T.bounties.search(is_demo=True)) == len(D.OPEN) + len(D.DONE) + len(D.FLAGGED) + 1, "reloading replaces the demo"
maya = T.users.get(email="maya.demo@example.com")
mp = ok(call("get_neighbour", maya.get_id()))["person"]
assert mp["as_helper"]["rating"] and len(mp["reviews"]) >= 2 and any(bd["key"] == "leaf" for bd in mp["badges"])

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "get_board", "get_bounty", "get_catalog", "get_neighbour", "legal_state", "legal_accept"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
