"""Demo content, so the board is alive for the first visitors: neighbours around Montréal, open bounties with
offers, finished jobs with reviews, and a few cases for the moderators (flagged posts, a report, a dispute).
Loaded automatically the first time anyone opens the app (ensure_loaded), removed or reloaded from
Admin -> Demo data. Removing it is remembered: it doesn't come back.

Demo people have is_demo=True and @example.com emails; they can't sign in (no password). Every demo row
is flagged is_demo=True, so remove() deletes exactly what load() added (plus real rows that point at demo
rows, like an offer on a demo bounty, so nothing dangles). All names are made up.
"""
import datetime as dt
import random

from anvil.tables import app_tables

from . import common as C

# name, email, area, (lat, lng), bio, skills, preset stats (their history before the demo starts)
DEMO_USERS = [
    ("Maya Chen", "maya.demo@example.com", "Plateau-Mont-Royal", (45.5236, -73.5810),
     "Concordia student, early riser, I own two good shovels and a leaf blower. I bag neatly and send photos.",
     ["Strong back", "Own snow shovel", "Early bird", "Bilingual (EN/FR)"], {"jobs": 14, "bonus_won": 9, "by_cat": {"yard": 6, "snow": 5, "moving": 3}}),
    ("Théo Martin", "theo.demo@example.com", "Rosemont", (45.5435, -73.5850),
     "Handy, patient, and I have a hatchback. Flat-pack furniture is my happy place.",
     ["Own car", "Own tools", "Evenings", "Weekends"], {"jobs": 8, "bonus_won": 5, "by_cat": {"moving": 5, "handy": 3}}),
    ("Samir Haddad", "samir.demo@example.com", "Villeray", (45.5450, -73.6200),
     "I have a pickup truck and I know every eco-centre on the island. Junk gone in one trip.",
     ["Own truck or van", "Strong back", "Weekends"], {"jobs": 21, "bonus_won": 12, "by_cat": {"junk": 13, "moving": 8}}),
    ("Owen Gallagher", "owen.demo@example.com", "Ahuntsic", (45.5590, -73.6520),
     "17, saving up for a bike. I rake, I shovel, I walk dogs. My mom says I'm very polite.",
     ["Pet lover", "Weekends", "Own snow shovel"], {"jobs": 5, "bonus_won": 3, "by_cat": {"yard": 2, "snow": 2, "pets": 1}}),
    ("Dmitri Volkov", "dmitri.demo@example.com", "Saint-Henri", (45.4770, -73.5850),
     "Retired carpenter. Shelves, pictures, BBQs and car shelters, done right the first time.",
     ["Own tools", "Own car", "Evenings"], {"jobs": 11, "bonus_won": 6, "by_cat": {"handy": 7, "errands": 4}}),
    ("Gloria Fernandes", "gloria.demo@example.com", "Notre-Dame-de-Grâce", (45.4720, -73.6150),
     "Two maples, one beagle (Biscuit), zero patience for raking. I pay the same day.",
     [], {"posted": 9, "completed": 8, "paid": 8, "paid_fast": 8, "bonus_jobs": 6, "bonus_paid": 6}),
    ("Jean-Philippe Roy", "jp.demo@example.com", "Outremont", (45.5190, -73.6080),
     "Busy dad of three. If it involves snow, I'd rather pay you.",
     [], {"posted": 12, "completed": 11, "paid": 11, "paid_fast": 10, "bonus_jobs": 7, "bonus_paid": 6}),
    ("Priya Nair", "priya.demo@example.com", "Mile End", (45.5245, -73.6000),
     "New to Montréal, lots of flat-pack and a window AC that needs to go.",
     [], {"posted": 3, "completed": 2, "paid": 2, "paid_fast": 2, "bonus_jobs": 1, "bonus_paid": 1}),
    ("Lucie Tremblay", "lucie.demo@example.com", "Hochelaga", (45.5440, -73.5450),
     "Spring-cleaning all year round. The garage is my nemesis.",
     [], {"posted": 6, "completed": 5, "paid": 5, "paid_fast": 4, "bonus_jobs": 3, "bonus_paid": 2}),
    ("Inès Ozola", "ines.demo@example.com", "Verdun", (45.4590, -73.5700),
     "I post and I help: I'll walk your dog if you put up my Tempo.",
     ["Pet lover", "Weekends"], {"posted": 4, "completed": 4, "paid": 4, "paid_fast": 4, "jobs": 3, "by_cat": {"pets": 3}}),
    ("Kwame Asante", "kwame.demo@example.com", "Griffintown", (45.4920, -73.5600),
     "Moving every two years like a true Montrealer.",
     [], {"posted": 5, "completed": 4, "paid": 4, "paid_fast": 3, "bonus_jobs": 2, "bonus_paid": 1, "late_cancels": 1}),
    ("Hélène Gagnon", "helene.demo@example.com", "Rosemont", (45.5400, -73.5900),
     "Snowbird from December to March. My bins and driveway need a friend.",
     [], {"posted": 7, "completed": 7, "paid": 7, "paid_fast": 7, "bonus_jobs": 4, "bonus_paid": 4}),
    ("Bernard Lefebvre", "bernard.demo@example.com", "Ahuntsic", (45.5560, -73.6600),
     "82 and still gardening. Technology, however, is a mystery.",
     [], {"posted": 2, "completed": 2, "paid": 2, "paid_fast": 2}),
    ("Sofia Russo", "sofia.demo@example.com", "Plateau-Mont-Royal", (45.5270, -73.5760),
     "Two cats (Pesto and Gnocchi), frequent work trips.",
     [], {"posted": 3, "completed": 3, "paid": 3, "paid_fast": 3, "bonus_jobs": 3, "bonus_paid": 3}),
    ("Kevin Brooks", "kevin.demo@example.com", "Laval", (45.5380, -73.7400), "", [], {}),
]

# poster, task, title, details, size, days ahead, when note, base, bonus, bar, pay, photo scene, offers [(helper, message, when, ask)]
OPEN = [
    (5, "leaves", "Rake & bag the front and back yard",
     "Two big maples dropped everything this week. Paper yard bags and two rakes are in the shed by the gate. "
     "Collection is Wednesday, so bags at the curb Tuesday night please.", "medium", 2, "Saturday morning is ideal", 35, 10, 80,
     "either", "leaves", [(0, "Hi Gloria! I did your neighbour's yard last week. I can come Saturday 9 am.", "Saturday 9 am", 35),
                          (3, "I'm Owen, 17. I rake fast and I'll bag everything neatly.", "Saturday afternoon", 35)]),
    (7, "ac", "Take my window AC out before the cold",
     "Second-floor window, standard 10,000 BTU unit. I'll need two people (or one very strong one). It goes to the basement storage.",
     "small", 3, "Any evening after 6", 45, 0, 80, "cash", None, [(1, "Théo here, I can bring a friend and a dolly. Tuesday works.", "Tuesday 6:30 pm", 45)]),
    (8, "ecocentre", "Haul an old couch and 8 boxes to the eco-centre",
     "Old sofa (no bugs, just old), 8 boxes of papers and an old printer. Everything is in the back alley shed. "
     "Needs a truck or a big van.", "medium", 4, "Weekend", 70, 15, 90, "etransfer", "junk",
     [(2, "Pickup truck, one trip, I'll send you the eco-centre receipt.", "Saturday 10 am", 80)]),
    (9, "tempo", "Put up our Tempo car shelter",
     "Single-car Tempo, all the pieces are labelled from last spring. Ground is soft enough for the anchors.",
     "medium", 5, "Before Nov 15", 60, 0, 80, "either", None, []),
    (5, "dogwalk", "Walk Biscuit (beagle) three lunchtimes this week",
     "Friendly beagle, pulls a bit at first. 45 minutes around the park, Monday, Wednesday, Friday around noon. Poop bags by the door.",
     "medium", 1, "Mon / Wed / Fri at noon", 60, 10, 90, "etransfer", None, [(3, "I love beagles! I'm free at lunch on those days.", "Mon/Wed/Fri", 60)]),
    (6, "windows", "Wash the ground-floor windows before winter",
     "Six windows at the front, four at the back. Bucket, squeegee and a step stool (no ladder needed).", "medium", 6, "Any weekday", 40, 0, 80, "cash", None, []),
    (7, "flatpack", "Assemble a big wardrobe (two frames + doors)",
     "Flat-pack wardrobe, 2 m tall, two frames, sliding doors. It must be anchored to the wall (kit included).", "large", 3, "Sunday",
     80, 20, 90, "etransfer", "boxes", [(1, "Built three of these. Two hours, anchored properly.", "Sunday 1 pm", 80),
                                        (4, "Carpenter, 40 years. I'll bring my own drill and level.", "Sunday morning", 90)]),
    (8, "firewood", "Stack a cord of firewood",
     "Delivery is dumped on the driveway. It needs to go to the rack along the fence (about 15 m away). Gloves provided.", "medium", 2,
     "Before Friday", 45, 0, 80, "cash", None, []),
    (6, "lights", "Holiday lights on the hedge and the porch",
     "Three strands for the hedge, one for the porch railing. All reachable from the ground. Lights tested and in a box.", "small", 20,
     "Late November", 45, 10, 80, "either", None, []),
    (11, "curb", "Bins to the curb every Monday in November",
     "I'm away for the month. Garbage Monday night, recycling every Monday, bring them back Tuesday. Four weeks.", "medium", 3,
     "Mondays in November", 40, 10, 100, "etransfer", None, [(0, "I live 5 minutes away, happy to do all four weeks.", "Every Monday", 40)]),
    (10, "truck", "Help load a moving truck on Saturday",
     "One-bedroom apartment, third floor, no elevator (sorry). Truck rented for 9 am. Pizza included.", "large", 8, "Saturday 9 am",
     120, 30, 90, "etransfer", "boxes", [(2, "I can come with a friend, we've done lots of third floors.", "Saturday 9 am", 140)]),
    (11, "driveway", "First-snowfall standby: shovel my driveway",
     "When the first real snow comes (5 cm+), shovel the driveway and the plow ridge before 8 am. Shovel is in the garage.", "medium", 25,
     "First snowfall", 35, 10, 80, "either", "snow", []),
    (12, "techhelp", "Set up my new tablet for video calls with my grandkids",
     "I bought a tablet. I'd like video calls to work, and the font bigger. Patience appreciated!", "small", 2, "Afternoon", 30, 10, 80,
     "cash", None, [(4, "Happy to help, Bernard. I'll write the steps on a card for you.", "Thursday 2 pm", 30)]),
    (10, "garage", "Clean out the garage before winter",
     "Sort into keep / donate / toss, sweep, put the bikes on the wall hooks. Donation drop-off is a bonus if you have a car.",
     "large", 7, "Next weekend", 90, 20, 80, "either", None, []),
    (7, "weeds", "Weed the garden and put it to bed",
     "Small front garden. Pull the weeds, cut back the dead stems, cover the roses with the burlap I have.", "small", 4,
     "Any morning", 35, 0, 80, "cash", None, []),
    (13, "petvisit", "Feed Pesto and Gnocchi (4 visits)",
     "Two indoor cats. Food, fresh water, litter, 10 minutes of play. Keys handed over in person first.", "medium", 9,
     "Thu to Sun", 60, 10, 100, "etransfer", None, [(9, "Cat person here! Happy to meet first for the keys.", "Thu-Sun", 60)]),
    (10, "boxes", "Break down 30 moving boxes",
     "All the boxes from my move. Flatten, tie them up and put them in the recycling area.", "small", 1, "Tomorrow", 25, 0, 80,
     "cash", "boxes", []),
    (12, "springclean", "Rake out the flower beds for the winter",
     "Leaves and dead stems out of the beds along the fence, bag it all. I'll make coffee.", "medium", 5, "Weekday morning", 40, 10, 80,
     "cash", "leaves", []),
]

# Finished jobs (history + reviews): poster, helper, task, title, base, bonus, bar, quality %, days ago,
# poster's review of the helper (stars, tags, text), helper's review of the poster
DONE = [
    (5, 0, "leaves", "Rake leaves (front lawn)", 30, 10, 80, 100, 8,
     (5, ["On time", "Great work", "Tidy"], "Maya was fantastic: every leaf bagged and the walk swept."),
     (5, ["Paid promptly", "Clear instructions"], "Gloria had bags and rakes ready, paid the same day.")),
    (8, 2, "ecocentre", "Old mattress and shelves to the eco-centre", 60, 10, 90, 100, 20,
     (5, ["On time", "Went the extra mile"], "Samir took it all in one trip and sent me the receipt."),
     (5, ["Paid promptly", "Friendly"], "Easy job, everything ready in the alley.")),
    (6, 3, "driveway", "Shovel the driveway after the storm", 35, 10, 80, 75, 260,
     (4, ["On time"], "Good job, missed a bit by the garage."), (5, ["Fair grader", "Paid promptly"], "Fair, and he explained what I missed.")),
    (6, 0, "sidewalk", "Clear the walk and front steps", 25, 5, 80, 100, 240,
     (5, ["Great work", "On time"], "Before 7 am, perfect."), (5, ["Paid promptly"], "")),
    (7, 1, "flatpack", "Assemble a bed frame", 45, 10, 90, 100, 30,
     (5, ["Great work", "Good communication"], "Sturdy and fast. Théo even took the boxes."),
     (4, ["Clear instructions"], "Nice, though a screw was missing from the kit.")),
    (13, 9, "petvisit", "Cat visits for a long weekend", 45, 10, 100, 100, 45,
     (5, ["Went the extra mile"], "Sent photos every visit, the cats were happy."), (5, ["Clear instructions", "Paid promptly"], "")),
    (11, 4, "pictures", "Hang six frames and a mirror", 40, 10, 90, 75, 60,
     (4, ["Tidy"], "Great work, one frame a bit off."), (4, ["Paid promptly"], "Fine, but a 90% bonus bar is steep.")),
    (10, 2, "truck", "Unload a moving truck", 100, 20, 80, 100, 400,
     (5, ["Great work", "On time"], ""), (5, ["Friendly"], "The pizza was great.")),
]

# For the moderators: posts the scanner sent to the review queue
FLAGGED = [
    (14, "pickup", "Pick up a package at the post office for my cousin",
     "Pick up a package at the post office with my card and deliver it to my cousin downtown. I'll send the card by email.",
     ["Carrying packages"], 40),
    (14, "other", "Buy gift cards for my office party",
     "I need someone to buy 4 gift cards (I'll pay back double by e-transfer afterwards) and send me the codes. Easy money!",
     ["Mentions gift cards", "\"Another task\": a moderator checks these"], 60),
]
DEMO_TABLES = ["reports", "reviews", "messages", "offers", "photos", "bounties"]
LINKS = {"offers": ("bounty", "helper"), "messages": ("bounty", "sender"), "reviews": ("bounty", "author", "subject"),
         "reports": ("bounty", "reporter", "subject"), "photos": ("bounty", "owner"), "bounties": ("poster", "helper")}


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    if state() == "never":
        load()


def _photo(owner, bounty, scene):
    from . import DemoArt
    m = DemoArt.media(scene)
    p = app_tables.photos.add_row(owner=owner, bounty=bounty, key=C.token(24), image=m, thumb=m, created=C.now(), is_demo=True)
    return p["key"]


def load():
    from . import Bounties, Catalog, Work
    remove(remember=False)
    rnd = random.Random(42)
    now = C.now()
    today = now.date()
    users = []
    for name, email, area, spot, bio, skills, stats in DEMO_USERS:
        u = app_tables.users.get(email=email) or app_tables.users.add_row(email=email, enabled=False)
        u.update(display_name=name, is_demo=True, signed_up=now - dt.timedelta(days=rnd.randint(40, 500)), spot_label=area,
                 spot_lat=spot[0], spot_lng=spot[1], bio=bio, skills=skills, stats=dict(stats), helper_on=bool(skills), strikes=0)
        users.append(u)

    def bounty(poster, task_key, title, details, size, base, bonus, bar, pay, status, created, **extra):
        t = Catalog.task(task_key)
        lat = poster["spot_lat"] + rnd.uniform(-0.008, 0.008)
        lng = poster["spot_lng"] + rnd.uniform(-0.008, 0.008)
        plat, plng = Bounties.fuzz(lat, lng)
        row: dict = dict(poster=poster, task=task_key, title=title, details=details, size=size, lat=lat, lng=lng, pub_lat=plat, pub_lng=plng,
                   area=poster["spot_label"], address="%d rue de l'Exemple (demo)" % rnd.randint(100, 9999), base=base, posted_base=base,
                   bonus=bonus, bar=bar, checklist=list(t["checklist"]), pay_method=pay, status=status, flags=[], photos=[],
                   proof_photos=[], created=created, updated=created, offer_count=0, poster_unread=0, helper_unread=0,
                   log=[{"at": C.iso(created), "who": "poster", "text": "Posted for %s%s." % (
                       C.money(base), (" + %s quality bonus at %d%%" % (C.money(bonus), bar)) if bonus else "")}],
                   is_demo=True)
        row.update(extra)
        return app_tables.bounties.add_row(**row)

    for i, (pi, task_key, title, details, size, ahead, note, base, bonus, bar, pay, scene, offers) in enumerate(OPEN):
        created = now - dt.timedelta(hours=3 + i * 5 + rnd.randint(0, 4))
        b = bounty(users[pi], task_key, title, details, size, base, bonus, bar, pay, "open", created,
                   when_date=today + dt.timedelta(days=ahead), when_note=note)
        if scene:
            b["photos"] = [_photo(users[pi], b, scene)]
        for hi, msg, when, ask in offers:
            app_tables.offers.add_row(bounty=b, helper=users[hi], message=msg, when_text=when, ask=ask, status="pending",
                                      created=created + dt.timedelta(minutes=30 + rnd.randint(0, 200)), is_demo=True)
        b["offer_count"] = len(offers)

    for pi, hi, task_key, title, base, bonus, bar, quality, ago, rv_helper, rv_poster in DONE:
        t = Catalog.task(task_key)
        done = now - dt.timedelta(days=ago)
        n = len(t["checklist"])
        ticks = int(round(n * quality / 100.0))
        q = int(round(100.0 * ticks / n))
        earned = bonus > 0 and q >= bar
        b = bounty(users[pi], task_key, title, t["blurb"], "medium", base, bonus, bar, "either", "done", done - dt.timedelta(days=3),
                   helper=users[hi], assigned_at=done - dt.timedelta(days=2), submitted_at=done - dt.timedelta(days=1),
                   self_checks=[True] * n, checks=[k < ticks for k in range(n)], quality=q, bonus_earned=earned,
                   amount_due=base + (bonus if earned else 0), validated_at=done - dt.timedelta(hours=20),
                   paid_at=done - dt.timedelta(hours=10), paid_method="etransfer", paid_ref="DEMO", payout_method="etransfer",
                   done_at=done, updated=done)
        for author, subject, role, rv in ((users[pi], users[hi], "helper", rv_helper), (users[hi], users[pi], "poster", rv_poster)):
            app_tables.reviews.add_row(bounty=b, author=author, subject=subject, subject_role=role, stars=rv[0], tags=rv[1], text=rv[2],
                                       created=done + dt.timedelta(hours=rnd.randint(1, 30)), is_demo=True)
    for u in users:
        Work._rerate(u, "helper")
        Work._rerate(u, "poster")

    for pi, task_key, title, details, flags, base in FLAGGED:
        b = bounty(users[pi], task_key, title, details, "small", base, 0, 80, "etransfer", "review", now - dt.timedelta(hours=2),
                   flags=flags, when_date=today + dt.timedelta(days=2))
        b["log"] = list(b["log"]) + [{"at": C.iso(now), "who": "system", "text": "Waiting for a moderator: " + "; ".join(flags) + "."}]
    app_tables.reports.add_row(reporter=users[5], bounty=None, subject=users[14], kind="scam",
                               text="This person asked me to buy gift cards for them and send the codes. Looks like a scam.",
                               status="open", note="", created=now - dt.timedelta(hours=1), is_demo=True)

    # A dispute for the moderators: the helper thinks the score was unfair.
    b = bounty(users[10], "garage", "Sort and sweep the storage locker", Catalog.task("garage")["blurb"], "medium", 60, 20, 80,
               "etransfer", "disputed", now - dt.timedelta(days=4), helper=users[4], assigned_at=now - dt.timedelta(days=3),
               submitted_at=now - dt.timedelta(days=2), self_checks=[True, True, True, True], checks=[True, False, False, True],
               quality=50, bonus_earned=False, amount_due=60, validate_note="The shelves aren't organised the way I wanted.",
               validated_at=now - dt.timedelta(days=1), payout_method="etransfer", payout_email="dmitri.payouts@example.com",
               dispute_by="helper", dispute_from="validated",
               dispute_reason="I sorted everything into keep / donate / toss with Kwame on the phone, and he only asked for "
                              "'organised shelves' afterwards. I think 2 of the 4 unticked items are unfair and the bonus should be paid.")
    b["log"] = list(b["log"]) + [{"at": C.iso(now - dt.timedelta(hours=20)), "who": "helper", "text": "Opened a dispute about the score."}]
    C.set_setting("demo", "loaded")
    return counts()


def remove(remember=True):
    demo_users = list(app_tables.users.search(is_demo=True))
    demo_bounties = list(app_tables.bounties.search(is_demo=True))
    for name in DEMO_TABLES:
        for r in list(getattr(app_tables, name).search()):
            if r["is_demo"] or any(r[c] is not None and (r[c] in demo_users or r[c] in demo_bounties) for c in LINKS[name]):
                r.delete()
    for u in demo_users:
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"people": len(app_tables.users.search(is_demo=True))}
    for name in ("bounties", "offers", "reviews"):
        out[name] = len(getattr(app_tables, name).search(is_demo=True))
    return out
