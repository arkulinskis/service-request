# Service Request

A neighbourhood bounty board. People post small paid jobs that need no degree (raking leaves, shovelling snow, hauling junk,
moving furniture, walking a dog: 40 kinds), from $20. Neighbours nearby send offers; the poster picks one, the helper does the
job and sends photo proof, the poster ticks a quality checklist, and pays the helper directly in **cash or by Interac
e-Transfer** (no money moves through the app: that's regulated in Canada). An optional **quality bonus** is paid when the
checklist score reaches the bar the poster set (e.g. $20 + $10 at 80%). Built on [Anvil](https://anvil.works), Montréal first.

- **App repo:** github.com/arkulinskis/service-request (branch `master`). Anvil pulls `master`.
- **Live:** https://service-request.anvil.app
- **Design:** "hi-vis bounty board": safety-vest yellow `#ffd400` on near-black, warm paper `#f4f2ec`, Archivo Black + Archivo,
  thick outlines, hard offset shadows, hazard stripes, tear-off price tags, rubber-stamp statuses. Light and dark.

## What it does

**For everyone (no account needed):**
- **Landing** (`#landing`): the promise, how it works for posters and for helpers, the quality bonus explained, "built against
  scams", all 40 tasks, FAQ.
- **Bounty board** (`#board`, the home page): open bounties as TaskRabbit-style cards + a map of price-tag pins; search, category
  chips (incl. "In season"), sort (newest, highest, closest, soonest), distance, payment method, "quality bonus only".
  Sorted from your saved area, your location, or Montréal.
- **Bounty page** (`#bounty/<id>`): details, photos, the checklist with each item's weight, an approximate circle on the map,
  the poster's record (rating, "pays within 2 days: 8/8", bonuses paid), safety tips, report.
- **Neighbour pages** (`#neighbour/<id>`): first name + initial, area, record as helper and poster, badges, skills, reviews.
- **Rules & safety** (`#rules`): paying, quality & bonus, six scams, what's not allowed, privacy, disputes & strikes, all 40
  tasks with suggested prices.

**For members:**
- **Post a bounty** (`#post`, `#post/<task>`): 5 steps: task (40, searchable) → details, size, date, photos → map pin + private
  street address → bounty (min $20, suggested by task and size), optional quality bonus and bar, editable checklist, cash /
  e-Transfer / either → review with three promises. Live preview of the board card.
- **Offers:** message, when, and an optional counter-offer (up to double). The poster compares offers (rating, jobs, bonuses
  won, drop-outs, skills) and picks one; the others are declined. Raise the bounty while open. Cancel (a reason is needed once
  booked; it counts as a late cancel).
- **Booked:** the helper sees the street address + directions; private chat; the helper can back out (counts as a drop-out; the
  bounty goes back on the board and the other offers come back).
- **Proof:** the helper ticks the checklist, adds 1-6 photos (shrunk on the phone), a note, and how to be paid (cash, or
  e-Transfer to their email, remembered in their profile).
- **Validation:** the poster ticks the checklist with a live quality meter ("80% → you'll owe $30"); unticked items need a
  reason. Not checked in 48 h → validated with the helper's own checklist.
- **Payment:** the poster sees the amount, the breakdown and (only now) the helper's e-Transfer email with a copy button,
  then marks it paid with the bank reference. The helper confirms; unquestioned for 7 days → closed.
- **Disputes:** either side can freeze the job for a moderator (not paid, no-show, unfair score, poor work).
- **Blind reviews** (stars + tags + text) once done. **Badges** (Leaf legend, Snow warrior, Prompt payer, Fair grader…).
- **My jobs** (`#jobs`): To do / Posted / Doing / Offers sent, with what needs you ("Check the work", "Pay $30").
- **Ledger** (`#ledger`): earned, coming to you, paid, owed; every amount with method and reference; CSV export.
- **Profile:** helper bio, skills, e-Transfer email, open to jobs, your area.

**Abuse protections** (server_code/Trust.py): scam / unsafe-work text scanner → moderator review queue; phone numbers, emails
and links hidden in public text; fuzzed public location (200-450 m) and address only for the matched helper; e-Transfer email
only after validation; new-account limits (2 live bounties, 2 active jobs); pay within 3 days or posting is blocked; strikes
(3 = paused); 3 reports pull a bounty; blind reviews, each neighbour counted once in a rating; amounts $20-$500, bonus ≤ bounty.

**For admins** (`#admin`; arkulinskis@gmail.com becomes an admin on first sign-in):
- **Overview:** queue, disputes, reports, open / under way / payment pending / done, $ settled.
- **Review queue:** flagged bounties with the reasons; approve or reject (with a note to the poster).
- **Trust & safety:** settle disputes (owed full / base only / payment confirmed / nothing owed, optional strike, note), uphold
  or dismiss reports, edit strikes and pause accounts.
- **Bounties:** every bounty by status; remove.
- **Feedback inbox, Users, Demo data** (15 Montréal neighbours, 18 open bounties with offers, finished jobs with reviews, 2
  flagged posts, a report, a dispute).

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/service-request`.
2. **Users** service: email + password and "Continue with Google", sign-up allowed (already set in `anvil.yaml`; check it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **arkulinskis@gmail.com** straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

<!-- libraries:start -->
## Libraries and outside services

What this project uses besides its own code. Generated by `APP_MAKER/tools/libraries.py`; to change it, edit `APP_MAKER/libraries/catalog.py` and re-run the script.

| Name | How it gets in | Used here for |
|---|---|---|
| [Leaflet](https://leafletjs.com) 1.9.4 | Loaded from a CDN | jobs posted near you |
| [Nominatim](https://nominatim.org) | Outside web service | OpenStreetMap's address search: turns an address into a map position, and back. |
| [OpenStreetMap tiles](https://operations.osmfoundation.org/policies/tiles/) | Outside web service | The free map pictures behind the Leaflet maps. |
| [YouTube embeds](https://developers.google.com/youtube/player_parameters) | Outside web service | Plays a YouTube video inside the page (the privacy-friendlier youtube-nocookie address). |
| [Google Fonts](https://fonts.google.com) | Loaded from a CDN | Archivo, Archivo Black |

**Built into the browser:** Canvas 2D, Geolocation, localStorage, Clipboard, File downloads (Blob).

**Anvil platform:** Anvil, Anvil Data Tables, Anvil Google service, Anvil JS bridge (anvil.js), Anvil Users.

**Build and test tools (not shipped):** Node.js, PyYAML, Headless Chrome (DevTools Protocol).

<!-- libraries:end -->

## Working on it

Native Anvil Forms since November 2026 (branch `forms`): this folder *is* the Anvil app. `APP_MAP.md` is the code map.

```
python tools/check.py                            # Anvil's validator, JS syntax, asset hashes, server tests -> ALL CHECKS PASSED
python -I tools/ui_test.py                       # the real app in the Anvil App Server (Docker) + headless Chrome: tools/ui/smoke.js
python tools/assets.py                           # after changing anything in theme/assets (cache-busting hashes, icons.css)
git push origin forms                            # deploy (Anvil pulls the branch it runs)
```

## Project layout

```
client_code/    startup.py (who is signed in, Privacy & Terms, router), router.py (#page/arg addresses), state.py, auth.py,
                sr.py (catalogue, money, the quality rule, tags/stamps/stars, spot picker, report), legal.py
                Layouts/Shell (header, menus, footer, phone tab bar), Pages/ (Landing, Board, Bounty, Post, Jobs, Ledger,
                Neighbour, Rules, Profile, Auth, Admin), Items/ (list rows), Dialogs/ (Ask, Report, SpotPicker, Zoom),
                Components/ (Map = Leaflet, Uploader = photo shrink + upload)
server_code/    Catalog (40 tasks), Bounties (board, posting, timers), Work (offers → payment, chat, reviews, jobs, ledger),
                Trust (scanner, limits, strikes, reports, moderation), People (profiles, badges), Photos, DemoData, DemoArt,
                common, Accounts, Feedback, Admin, legal_server
theme/assets/   app.css (tokens + brand + pages + Anvil roles), sr-engine.js (maps, place search, photo shrinking, confetti,
                the landing map), app-kit.js (theme, storage, icon table), icons.css (generated), legal-kit.js, icons
tools/          check.py, assets.py, build_icons.py, make_icons.py, ui_test.py + ui/smoke.js, live/drive.mjs, testing/
```

## Later: real payments

`Work.mark_paid` / `Work.confirm_received` are the only places money changes state, and every amount owed is in the
`bounties` table (`amount_due`, `paid_method`, `paid_ref`, dates). A licensed payment partner (a payment processor offering
Interac Request Money, or a marketplace service like Stripe Connect) can plug in there as a third `paid_method`.
