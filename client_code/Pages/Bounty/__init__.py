from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import BountyTemplate
from ... import router, sr, state
from ...Dialogs.Ask import Ask

CLOSED = ("cancelled", "rejected", "expired", "removed")
CHAT_STATES = ("assigned", "submitted", "validated", "paid", "done", "disputed")


class Bounty(BountyTemplate):
    """One bounty (#bounty/<id>). What you see depends on who you are and the stage (role from get_bounty):
    visitors: details, the approximate area, the poster's record, the offer form.
    poster: offers (pick a helper), chat, the proof check with the live quality meter, the payment step (the helper's
    e-Transfer email appears only now), reviews. helper: the exact address, chat, the proof form, payment confirmation,
    reviews. Every money figure comes from the server (base, bonus, bar, amount_due); the live meter uses the server's
    own scoring rule (sr.quality)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.id = args[0] if args else ""
        self.b: dict = {}
        self._vchecks: list = []
        self._pchecks: list = []
        self._stars = 0
        self._tags: list = []
        self._link = ""
        self._pm = "etransfer"
        self._review_tags: list = []
        self.offers_panel.add_event_handler("x-accept", self._accept)
        self.offers_panel.add_event_handler("x-decline", self._decline)
        self.validate_checks.add_event_handler("x-check", self._vcheck)
        self.proof_checks.add_event_handler("x-check", self._pcheck)
        self.tags_panel.add_event_handler("x-chip", self._tag)
        for node in (self.dom_nodes["pm_et"], self.dom_nodes["pm_cash"]):
            node.addEventListener("change", self._pm_change)
        state.set_control_attr(self.chat_text, "aria-label", "Message")
        state.set_control_attr(self.chat_text, "maxlength", 1000)
        state.set_control_attr(self.offer_msg, "maxlength", 500)
        state.set_control_attr(self.offer_when, "maxlength", 80)
        state.set_control_attr(self.pay_ref, "maxlength", 40)
        state.set_control_attr(self.review_text, "maxlength", 600)
        state.set_control_attr(self.review_text, "aria-label", "Your review")
        state.set_control_attr(self.validate_note, "maxlength", 600)
        state.set_control_attr(self.proof_note_box, "maxlength", 800)
        state.set_control_attr(self.proof_email, "maxlength", 200)
        sr.catalog()
        self._load()

    # ------------------------------------------------------------------ data
    def _load(self):
        res = anvil.server.call("get_bounty", self.id)
        if res.get("ok") is False:
            return self._gone("Bounty not found", res.get("error") or "")
        if res.get("gone"):
            status = sr.STATUS.get(res.get("status"), res.get("status") or "")
            return self._gone(res.get("title") or "Bounty", "This bounty is no longer open (%s)." % status.lower())
        self.b = res["bounty"]
        router.set_title(self.b["title"])
        self._draw()

    def _gone(self, title, text):
        self.grid.visible = False
        self.gone_box.visible = True
        self.dom_nodes["back"].hidden = True
        self.dom_nodes["gone_h"].textContent = title
        self.dom_nodes["gone_p"].textContent = text

    def _reload(self):
        y = window.scrollY
        self._load()
        window.scrollTo(0, y)

    def _act(self, msg, fn, *args):
        """A server call for an action button: expected problems are a toast; success = toast + fresh page."""
        r = state.call(fn, *args)
        if r is None:
            return None
        if msg:
            state.toast(msg, "ok")
        self._reload()
        return r

    # ------------------------------------------------------------------ drawing
    def _draw(self):
        b = self.b
        r, s = b["role"], b["status"]
        t = sr.task(b["task"])
        c = sr.cat(t["cat"])
        n = self.dom_nodes
        party = r in ("poster", "helper")
        self.gone_box.visible = False
        self.grid.visible = True
        n["back"].hidden = False
        n["back"].setAttribute("href", "#jobs" if party else "#board")
        n["back_text"].textContent = "My jobs" if party else "Bounty board"
        # head
        sr.fill_ti(n["ti"], b["task"], "lg")
        n["catname"].textContent = c["name"] + " · " + t["name"]
        sr.fill_stamp(n["stamp"], s)
        n["demo"].hidden = not b.get("demo")
        n["yours"].hidden = not party
        n["yours"].textContent = "Your bounty" if r == "poster" else "Your job"
        n["title"].textContent = b["title"]
        n["area"].textContent = b.get("area") or ""
        n["away"].textContent = (" · " + sr.dist(b["dist"]) + " away") if (b.get("dist") is not None and r == "visitor") else ""
        n["when"].textContent = sr.when(b)
        size = b.get("size") or "medium"
        n["size"].textContent = size[:1].upper() + size[1:] + " job"
        n["vehicle"].hidden = not b.get("vehicle")
        n["posted"].textContent = "Posted " + sr.ago(b.get("created"))
        # the tag and the money rule
        sr.fill_tag(n["tag"], b["base"], b.get("bonus") or 0, b.get("bar") or 80, "big")
        sr.rich(n["payline"], sr.icon(sr.PAY_ICON.get(b.get("pay"), "wallet")) + " " + sr.esc(sr.PAY.get(b.get("pay"), "")) +
                (("<br>" + sr.esc(sr.plural(b.get("offers") or 0, "offer"))) if s == "open" else ""))
        checklist = b.get("checklist") or []
        if b.get("bonus"):
            n["bonus_line"].className = "small bt-bonusline"
            sr.rich(n["bonus_line"], "<b>Quality bonus:</b> %s is paid once the work is validated, plus <b>%s</b> if the checklist "
                    "score reaches <b>%s%%</b> (%d of %d items)." % (sr.esc(sr.money(b["base"])), sr.esc(sr.money(b["bonus"])), b["bar"],
                                                                    sr.need(len(checklist), b["bar"]), len(checklist)))
        else:
            n["bonus_line"].className = "small muted bt-bonusline"
            n["bonus_line"].textContent = "Paid once the work is validated. No quality bonus on this one."
        n["agreed"].hidden = not (b["base"] > (b.get("posted_base") or b["base"]))
        sr.rich(n["agreed"], sr.icon("arrow") + " Agreed at %s (posted at %s)." % (sr.esc(sr.money(b["base"])), sr.esc(sr.money(b.get("posted_base") or b["base"]))))
        self._action(r, s)
        people = []
        if r != "poster" and b.get("poster"):
            people.append({"p": b["poster"], "role": "poster", "title": "Posted by"})
        if r == "poster" and b.get("helper"):
            people.append({"p": b["helper"], "role": "helper", "title": "Your helper"})
        self.people_panel.items = people
        self.report_link.visible = r != "poster"
        self._main(r, s)
        if r == "helper" and b.get("validation") and b["validation"].get("bonus_earned") and not sr.stored("cheer." + str(b["id"])):
            sr.store("cheer." + str(b["id"]), 1)
            sr.confetti()

    # ------------------------------------------------------------------ the side panel: what to do now
    def _reset_action(self):
        n = self.dom_nodes
        for node in (n["act_h"], n["act_p"], n["act_p2"], n["act_meter"], n["act_badge"], n["act_addr"], n["act_row"],
                     n["act_link"], n["signin_line"]):
            node.hidden = True
        self.act_list.visible = False
        self.act_note.visible = False
        for comp in (self.offer_form, self.withdraw_button, self.raise_button, self.received_button, self.pay_box,
                     self.cancel_link, self.backout_link, self.dispute_link):
            comp.visible = False
        self._link = ""

    def _h(self, text, icon=None):
        node = self.dom_nodes["act_h"]
        node.hidden = False
        sr.rich(node, (sr.icon(icon) + " " if icon else "") + sr.esc(text))

    def _p(self, html, muted=False, node_name="act_p"):
        node = self.dom_nodes["act_p"] if node_name == "act_p" else self.dom_nodes["act_p2"]
        node.hidden = False
        node.className = "small" + (" muted" if muted else "")
        sr.rich(node, html)

    def _a(self, text, href, primary=False, icon=None, mode=""):
        node = self.dom_nodes["act_link"]
        node.hidden = False
        node.className = "ui-btn block" + (" primary" if primary else "")
        node.setAttribute("href", href)
        sr.rich(node, (sr.icon(icon) if icon else "") + sr.esc(text))
        self._link = mode

    def _dispute(self, text="Something's wrong"):
        self.dispute_link.text = text
        self.dispute_link.visible = True

    def _action(self, r, s):
        self._reset_action()
        b = self.b
        e = sr.esc
        P = sr.first((b.get("poster") or {}).get("name"))
        H = sr.first((b.get("helper") or {}).get("name"))
        v = b.get("validation") or {}
        if s in CLOSED:
            self._h(sr.STATUS.get(s, s))
            self._p(e(b.get("cancel_reason") or "This bounty is closed."), muted=True)
            return
        if s == "disputed":
            self._h("A moderator is on it", "shield")
            d = b.get("dispute")
            if d:
                who = "You" if d["by"] == r else (P if d["by"] == "poster" else H)
                self._p(e('%s opened a dispute: "%s"' % (who, d["reason"])), muted=True, node_name="act_p2")
            self._p("Nothing to do for now. The moderator reads both sides, the chat and the photos, then decides what is owed.")
            return
        if r in ("visitor", "admin"):
            if r == "admin" and s != "open":
                self._p("You're seeing this as a moderator.", muted=True)
                self._a("Open admin", "#admin/bounties")
                return
            if not state.me():
                self._h("Want this job?")
                self._p("Join free to send %s an offer. You'll see the exact address once you're picked." % e(P), muted=True)
                self._a("Join to make an offer", "#auth/signup", primary=True, icon="hand", mode="signup")
                self.dom_nodes["signin_line"].hidden = False
                return
            mo = b.get("my_offer")
            if mo and mo["status"] == "pending":
                self._h("Offer sent", "send")
                self._p("You offered <b>%s</b>%s. %s will pick a helper soon; you'll see it in My jobs." % (
                    e(sr.money(mo["ask"])), (" · " + e(mo["when"])) if mo.get("when") else "", e(P)))
                self._p(e('"%s"' % mo["message"]), muted=True, node_name="act_p2")
                self.withdraw_button.visible = True
                return
            if mo and mo["status"] == "declined":
                self._h("Not this time")
                self._p("%s went with someone else. Plenty more on the board!" % e(P), muted=True)
                self._a("Back to the board", "#board")
                return
            self._h("Make an offer")
            if b.get("can_help"):
                self.act_note.text = b["can_help"]
                self.act_note.visible = True
                return
            n = self.dom_nodes
            n["offer_msg_cap"].textContent = "Message to " + P
            self.offer_msg.placeholder = "Hi %s! I can do this. I have…" % P
            n["offer_ask_cap"].innerHTML = "Your price <em>(the bounty is %s)</em>" % e(sr.money(b["base"]))
            self.offer_ask.text = b["base"]
            state.set_control_attr(self.offer_ask, "min", b["base"])
            state.set_control_attr(self.offer_ask, "max", min(b["base"] * 2, 500))
            state.set_control_attr(self.offer_ask, "step", 1)
            self.offer_form.visible = True
            return
        if r == "poster":
            if s == "review":
                self._h("Waiting for a moderator", "shield")
                self._p("Your bounty isn't on the board yet because:")
                self.act_list.items = [{"text": f, "cls": "bt-flag"} for f in (b.get("flags") or [])]
                self.act_list.visible = True
                self._p("Most checks take a few hours. If it breaks the rules it won't be approved.", muted=True, node_name="act_p2")
                self.cancel_link.visible = True
            elif s == "open":
                self._h("Pick your helper" if b.get("offers") else "Waiting for offers")
                self._p("Compare the offers below: track record, reviews and what they say. Only the one you pick sees your address."
                        if b.get("offers") else "Neighbours nearby can see it now. Sweeten the deal to get offers faster.", muted=True)
                self.raise_button.visible = True
                self.cancel_link.visible = True
            elif s == "assigned":
                self._h("%s is booked" % H, "check")
                self._p("They now see your address and can chat with you below. When the job is done they send photos and their "
                        "checklist, and you validate it here.")
                self.cancel_link.visible = True
                self._dispute()
            elif s == "submitted":
                self._h("Proof is in!", "camera")
                self._p("%s says the job is done. Check the photos and tick the checklist below." % e(H))
                self.dom_nodes["act_badge"].hidden = False
                self.dom_nodes["act_badge_text"].textContent = "%s h left, then it's validated with %s's own checklist" % (
                    sr.hours_left((b.get("proof") or {}).get("at"), 48), H)
                self._dispute()
            elif s == "validated":
                self._pay_panel()
                self._dispute()
            elif s == "paid":
                pm = b.get("payment") or {}
                self._h("Marked as paid", "check")
                self._p("You paid <b>%s</b> by %s%s. Waiting for %s to confirm. It closes by itself after 7 days." % (
                    e(sr.money(v.get("amount_due"))), e(sr.PAY.get(pm.get("method"), pm.get("method") or "")),
                    (" (ref. %s)" % e(pm["ref"])) if pm.get("ref") else "", e(H)))
                self._dispute()
            elif s == "done":
                rv = b.get("reviews")
                self._h("All done", "star")
                self._p("Paid and confirmed. " + ("Leave %s a review below: it helps the next neighbour." % e(H)
                                                  if rv and not rv.get("mine") else "Thanks for using the board!"))
                self._a("Post a similar bounty", router.href("post", b["task"]), primary=True, icon="plus")
            return
        if r == "helper":
            ex = b.get("exact") or {}
            po = b.get("payout") or {}
            pm = b.get("payment") or {}
            if s == "assigned":
                self._h("You're booked!", "check")
                self._p("The address (only you see it):", muted=True)
                n = self.dom_nodes
                n["act_addr"].hidden = False
                n["act_addr"].textContent = ex.get("address") or ""
                n["act_row"].hidden = False
                n["directions"].setAttribute("href", "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (ex.get("lat"), ex.get("lng")))
                self.backout_link.visible = True
                self._dispute()
            elif s == "submitted":
                self._h("Proof sent", "clock")
                self._p("%s has <b>%s h</b> to check it. If they don't, it's validated automatically with your checklist." % (
                    e(P), sr.hours_left((b.get("proof") or {}).get("at"), 48)))
                self._dispute()
            elif s == "validated":
                self._h("%s is owed to you" % sr.money(v.get("amount_due")), "wallet")
                m = self.dom_nodes["act_meter"]
                m.hidden = False
                sr.fill_meter(m, v.get("quality") or 0, b.get("bar") or 80, b.get("bonus"))
                bonus = ""
                if b.get("bonus"):
                    bonus = "<b>Bonus earned!</b> " if v.get("bonus_earned") else "Bonus not reached this time. "
                self._p(bonus + "%s pays by %s%s." % (e(P), e(sr.PAY.get(po.get("method"), "")),
                                                      (" to <b>%s</b>" % e(po.get("email") or "")) if po.get("method") == "etransfer" else ""))
                self.received_button.text = "I got paid"
                self.received_button.visible = True
                self._dispute("Not paid, or the score is unfair")
            elif s == "paid":
                self._h("%s says they paid" % P, "bank")
                self._p("<b>%s</b> by %s%s. Check your bank app (not an email link), then confirm." % (
                    e(sr.money(v.get("amount_due"))), e(sr.PAY.get(pm.get("method"), pm.get("method") or "")),
                    (", reference <b>%s</b>" % e(pm["ref"])) if pm.get("ref") else ""))
                self.received_button.text = "Yes, I got it"
                self.received_button.visible = True
                self._dispute("I didn't get it")
            elif s == "done":
                rv = b.get("reviews")
                self._h("Job done!", "star")
                self._p("You earned <b>%s</b>%s. %s" % (e(sr.money(v.get("amount_due") if v else b["base"])),
                                                        " including the quality bonus" if v.get("bonus_earned") else "",
                                                        ("Review %s below." % e(P)) if rv and not rv.get("mine") else ""))
                self._a("Find the next bounty", "#board")

    def _pay_panel(self):
        b = self.b
        v = b.get("validation") or {}
        po = b.get("payout") or {}
        H = sr.first((b.get("helper") or {}).get("name"))
        n = self.dom_nodes
        due = sr.money(v.get("amount_due"))
        et = po.get("method") == "etransfer"
        self.pay_box.visible = True
        n["pay_h"].textContent = "Time to pay " + H
        n["pay_big"].textContent = due
        n["pay_base"].textContent = sr.money(b["base"])
        n["pay_bonus_row"].hidden = not b.get("bonus")
        n["pay_bonus_row"].className = "" if v.get("bonus_earned") else "no"
        n["pay_bonus_label"].textContent = "Quality bonus (%s%% of %s%%)" % (v.get("quality"), b.get("bar"))
        n["pay_bonus"].textContent = sr.money(b.get("bonus"))
        n["pay_total"].textContent = due
        self.pay_et.visible = et
        n["pay_email"].textContent = po.get("email") or ""
        n["pay_cash"].hidden = et
        sr.rich(n["pay_cash"], "%s asked for <b>cash</b>. Hand it over in person, then mark it paid." % sr.esc(H))
        self.paid_button.text = "I've paid " + due
        n["pay_exact"].textContent = "Send exactly %s. No fees: the app never asks you for money." % due

    # ------------------------------------------------------------------ the main column
    def _main(self, r, s):
        b = self.b
        n = self.dom_nodes
        P = sr.first((b.get("poster") or {}).get("name"))
        H = sr.first((b.get("helper") or {}).get("name"))
        checklist = b.get("checklist") or []
        # photos
        photos = b.get("photos") or []
        self.photos_sec.visible = bool(photos)
        self.photos_panel.items = [{"key": k, "alt": "Photo of the job"} for k in photos]
        # offers (poster, open or in review)
        show_offers = r == "poster" and s in ("open", "review")
        self.offers_sec.visible = show_offers
        if show_offers:
            offers = b.get("offers_list") or []
            n["offer_count"].textContent = str(len([o for o in offers if o["status"] == "pending"]))
            self.offers_panel.items = [{"o": o, "base": b["base"], "open": s == "open"} for o in offers]
            self.offers_empty.visible = not offers
        # proof (shown above the check while the poster validates)
        proof = b.get("proof")
        self.proof_view_sec.visible = bool(proof)
        if proof:
            n["proof_h"].textContent = "Proof from " + H
            self.proof_photos.items = [{"key": k, "alt": "Proof photo"} for k in proof.get("photos") or []]
            n["proof_note"].hidden = not proof.get("note")
            n["proof_note"].textContent = '"%s"' % (proof.get("note") or "")
            sc = proof.get("self_checks") or []
            n["proof_meta"].textContent = "Sent %s · %d of %d items ticked by the helper" % (sr.ago(proof.get("at")), len([x for x in sc if x]), len(sc))
        # the poster checks the work
        validating = r == "poster" and s == "submitted" and bool(proof)
        self.validate_sec.visible = validating
        if validating:
            sc = (proof or {}).get("self_checks") or []
            self._vchecks = [bool(sc[i]) if i < len(sc) else False for i in range(len(checklist))]
            self.validate_checks.items = [{"i": i, "text": c, "checked": self._vchecks[i], "self": bool(sc[i]) if i < len(sc) else False}
                                          for i, c in enumerate(checklist)]
            sr.rich(n["validate_p"], "Tick every item that was done. %sIf you untick something, say why: %s reads it." % (
                ("The bonus is paid from %s%%. " % b["bar"]) if b.get("bonus") else "", sr.esc(H)))
            n["validate_note_cap"].innerHTML = "Note for %s <em>(needed if you untick something)</em>" % sr.esc(H)
            self._verdict()
        # the helper sends proof
        proving = r == "helper" and s == "assigned"
        self.proof_form_sec.visible = proving
        if proving:
            self._pchecks = [True for c in checklist]
            self.proof_checks.items = [{"i": i, "text": c, "checked": True, "self": None} for i, c in enumerate(checklist)]
            n["proof_form_p"].textContent = ("Tick what you did, add photos of the finished job, and say how you want to be paid. "
                                             "%s then validates it." % P)
            n["proof_note_cap"].innerHTML = "Note for %s <em>(optional)</em>" % sr.esc(P)
            either = b.get("pay") == "either"
            n["pm_box"].hidden = not either
            pm = "etransfer" if either else b.get("pay")
            n["pm_et"].checked = pm == "etransfer"
            n["pm_cash"].checked = pm == "cash"
            self._pm = pm
            self.email_box.visible = pm != "cash"
            self.proof_email.text = (state.me() or {}).get("payout_email") or ""
            n["email_hint"].textContent = "Only %s sees it, and only after validating your work." % P
            self.uploader.setup(6, "Add photo")
        # the result
        v = b.get("validation")
        self.result_sec.visible = bool(v)
        if v:
            n["result_h"].textContent = "Quality %s%%" % v.get("quality")
            n["result_auto"].hidden = not v.get("auto")
            sr.fill_meter(n["result_meter"], v.get("quality") or 0, b.get("bar") or 80, b.get("bonus"))
            checks = v.get("checks") or []
            self.result_list.items = [{"text": c, "icon": "check" if (i < len(checks) and checks[i]) else "x",
                                       "cls": "y" if (i < len(checks) and checks[i]) else "n"} for i, c in enumerate(checklist)]
            n["result_note"].hidden = not v.get("note")
            sr.rich(n["result_note"], sr.icon("chat") + ' "%s"' % sr.esc(v.get("note") or ""))
            n["result_auto_p"].hidden = not v.get("auto")
        self._reviews(r)
        # chat
        msgs = b.get("messages")
        chat = msgs is not None and s in CHAT_STATES
        self.chat_sec.visible = chat
        if chat:
            other = H if r == "poster" else P
            n["chat_h"].textContent = "Chat with " + other
            self._chat_draw()
            self.chat_form.visible = s != "done"
        # about, checklist, where, timeline
        n["details"].textContent = b.get("details") or ""
        n["tools"].hidden = not b.get("tools")
        n["tools_text"].textContent = b.get("tools") or ""
        k = max(1, len(checklist))
        sr.rich(n["checklist_p"], "The poster ticks this checklist when the job is done. Each item is worth %d%%.%s" % (
            sr.js_round(100.0 / k), (" The %s bonus is paid from %s%%." % (sr.esc(sr.money(b["bonus"])), b["bar"])) if b.get("bonus") else ""))
        self.checklist_panel.items = [{"text": c, "cls": "bt-cl-item", "right": "%d%%" % sr.js_round(100.0 / k)} for c in checklist]
        ex = b.get("exact")
        if ex:
            n["where_p"].textContent = (ex.get("address") or "") + " · " + (b.get("area") or "")
            self.map.point(ex["lat"], ex["lng"], True, "Job")
        else:
            n["where_p"].textContent = ("Around %s. The circle is approximate: the exact address goes only to the helper the "
                                        "poster picks." % (b.get("area") or ""))
            self.map.point(b["lat"], b["lng"], False)
        log = list(b.get("log") or [])
        log.reverse()
        self.log_sec.visible = bool(log)
        self.log_panel.items = log

    def _reviews(self, r):
        b = self.b
        rv = b.get("reviews")
        self.reviews_sec.visible = bool(rv)
        if not rv:
            return
        n = self.dom_nodes
        other = sr.first((b.get("helper") or {}).get("name")) if r == "poster" else sr.first((b.get("poster") or {}).get("name"))
        mine = rv.get("mine")
        self.mine_box.visible = bool(mine)
        self.review_form.visible = not mine
        if mine:
            n["mine_h"].textContent = "Your review of " + other
            sr.fill_stars(n["mine_stars"], mine["stars"])
            n["mine_text"].textContent = mine.get("text") or ""
            n["mine_text"].hidden = not mine.get("text")
            self.mine_tags.items = [{"text": x} for x in mine.get("tags") or []]
        else:
            n["review_p"].textContent = "Reviews are blind: you'll see %s's once you leave yours%s." % (
                other, " (theirs is waiting!)" if rv.get("theirs_waiting") else "")
            self._review_tags = rv.get("tags") or []
            self._draw_tags()
            self._draw_stars()
        theirs = rv.get("theirs")
        self.theirs_box.visible = bool(theirs)
        if theirs:
            n["theirs_h"].textContent = "%s's review of you" % theirs.get("author")
            sr.fill_stars(n["theirs_stars"], theirs["stars"])
            n["theirs_text"].textContent = theirs.get("text") or ""
            n["theirs_text"].hidden = not theirs.get("text")
            self.theirs_tags.items = [{"text": x} for x in theirs.get("tags") or []]

    def _chat_draw(self):
        msgs = self.b.get("messages") or []
        self.chat_panel.items = msgs
        self.dom_nodes["chat_empty"].hidden = bool(msgs)
        box = self.dom_nodes["chat_box"]
        box.scrollTop = box.scrollHeight

    # ------------------------------------------------------------------ the live quality meter (poster)
    def _vcheck(self, **event_args):
        self._vchecks[event_args["i"]] = bool(event_args["checked"])
        self._verdict()

    def _verdict(self):
        b = self.b
        total = len(self._vchecks)
        ticked = len([x for x in self._vchecks if x])
        q = sr.quality(ticked, total)
        bonus = b.get("bonus") or 0
        earned = bool(bonus) and q >= (b.get("bar") or 80)
        sr.fill_meter(self.dom_nodes["live_meter"], q, b.get("bar") or 80, bonus)
        sr.rich(self.dom_nodes["verdict"], "Quality %s%% → you'll owe <b>%s</b>%s" % (
            q, sr.esc(sr.money(b["base"] + (bonus if earned else 0))),
            ((" (bounty + bonus)" if earned else " (bonus not reached)") if bonus else "")))

    def _pcheck(self, **event_args):
        self._pchecks[event_args["i"]] = bool(event_args["checked"])

    def _pm_change(self, event):
        self._pm = "cash" if self.dom_nodes["pm_cash"].checked else "etransfer"
        self.email_box.visible = self._pm != "cash"

    # ------------------------------------------------------------------ actions
    def act_link_click(self, event):
        if self._link == "signup":
            event.preventDefault()
            router.remember_after(router.href("bounty", self.id))
            router.go("auth", "signup")

    def signin_click(self, event):
        event.preventDefault()
        router.remember_after(router.href("bounty", self.id))
        router.go("auth")

    def jump_click(self, event):
        event.preventDefault()
        anvil.js.get_dom_node(self.proof_form_sec).scrollIntoView(sr.js({"behavior": "smooth"}))

    @handle("offer_button", "click")
    def offer_button_click(self, **event_args):
        msg = (self.offer_msg.text or "").strip()
        if len(msg) < 10:
            state.toast("Say a little more in your message (at least 10 characters).", "error")
            return
        ask = self.offer_ask.text
        self._act("Offer sent!", "make_offer", self.id, msg, self.offer_when.text or "", int(float(ask)) if ask not in (None, "") else None)

    @handle("withdraw_button", "click")
    def withdraw_button_click(self, **event_args):
        self._act("Offer withdrawn", "withdraw_offer", self.b["my_offer"]["id"])

    def _accept(self, **event_args):
        o = event_args["offer"]
        name = sr.first(o["helper"]["name"])
        if confirm("They'll see your address and can chat with you. The other offers are declined.",
                   title="Pick %s for %s?" % (name, sr.money(o["ask"])), buttons=[("Back", False), ("Pick " + name, True)]):
            if self._act(name + " is booked!", "accept_offer", o["id"]):
                sr.confetti()

    def _decline(self, **event_args):
        self._act("Offer declined", "decline_offer", event_args["offer"]["id"])

    @handle("raise_button", "click")
    def raise_button_click(self, **event_args):
        b = self.b
        bid = self.id

        def run(v):
            return anvil.server.call("raise_bounty", bid, v["n1"], v["n2"])
        ok = alert(Ask(title="Raise the bounty", text="More money gets more offers. You can raise it, not lower it.", ok="Raise it", run=run,
                       numbers=[{"label": "Bounty ($)", "min": b["base"], "max": 500, "value": b["base"] + 5},
                                {"label": "Quality bonus ($)", "min": b.get("bonus") or 0, "max": 200, "value": b.get("bonus") or 0}]),
                   buttons=[], role="app-dialog", dismissible=True)
        if ok:
            state.toast("Bounty raised", "ok")
            self._reload()

    @handle("cancel_link", "click")
    def cancel_link_click(self, **event_args):
        booked = self.b["status"] == "assigned"
        bid = self.id

        def run(v):
            return anvil.server.call("cancel_bounty", bid, v["text"])
        ok = alert(Ask(title="Cancel this bounty?", ok="Cancel bounty", danger=True, run=run,
                       text="Your helper is told why. A late cancel shows on your record." if booked else "It comes off the board. Offers are declined.",
                       text_field={"label": "Why?", "optional": not booked, "min": 10 if booked else 0, "max": 300}),
                   buttons=[], role="app-dialog", dismissible=True)
        if ok:
            state.toast("Cancelled")
            self._reload()

    @handle("backout_link", "click")
    def backout_link_click(self, **event_args):
        P = sr.first((self.b.get("poster") or {}).get("name"))
        bid = self.id

        def run(v):
            return anvil.server.call("back_out", bid, v["text"])
        ok = alert(Ask(title="Back out of this job?", ok="Back out", danger=True, run=run,
                       text="The bounty goes back on the board and the others who offered are asked again. It shows as a drop-out on your record.",
                       text_field={"label": "Tell %s why" % P, "min": 10, "max": 300}),
                   buttons=[], role="app-dialog", dismissible=True)
        if ok:
            state.toast("You backed out")
            self._reload()

    @handle("dispute_link", "click")
    def dispute_link_click(self, **event_args):
        bid = self.id

        def run(v):
            return anvil.server.call("open_dispute", bid, v["text"])
        ok = alert(Ask(title="Ask a moderator", ok="Open a dispute", danger=True, run=run,
                       text="Use this when you can't sort it out in the chat: not paid, no-show, an unfair score, poor work. The job is frozen until a moderator decides.",
                       text_field={"label": "What went wrong?", "min": 20, "max": 800, "placeholder": "Facts help: dates, what was agreed, what happened."}),
                   buttons=[], role="app-dialog", dismissible=True)
        if ok:
            state.toast("A moderator will look at it.", "ok")
            self._reload()

    @handle("report_link", "click")
    def report_link_click(self, **event_args):
        sr.report("this bounty", bounty=self.id)

    @handle("received_button", "click")
    def received_button_click(self, **event_args):
        due = sr.money((self.b.get("validation") or {}).get("amount_due"))
        if confirm("Check your bank app or your wallet first. This closes the job.", title="Did you get %s?" % due,
                   buttons=[("Back", False), ("Yes, I got it", True)]):
            if self._act("Job closed. Nice work!", "confirm_received", self.id):
                sr.confetti()

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        sr.copy((self.b.get("payout") or {}).get("email") or "", "Email")

    @handle("paid_button", "click")
    def paid_button_click(self, **event_args):
        et = (self.b.get("payout") or {}).get("method") == "etransfer"
        ref = (self.pay_ref.text or "").strip()
        if et and len(ref) < 4:
            state.toast("Add the reference number from your bank (at least 4 characters).", "error")
            return
        self._act("Marked as paid. Thank you!", "mark_paid", self.id, "etransfer" if et else "cash", ref)

    @handle("proof_button", "click")
    def proof_button_click(self, **event_args):
        if self.uploader.busy():
            state.toast("Wait for the photos to finish uploading.")
            return
        P = sr.first((self.b.get("poster") or {}).get("name"))
        self._act("Proof sent to %s!" % P, "submit_proof", self.id, list(self._pchecks), self.proof_note_box.text or "",
                  self.uploader.keys(), self._pm, (self.proof_email.text or "") if self._pm != "cash" else "",
                  bool(self.remember_box.checked))

    @handle("validate_button", "click")
    def validate_button_click(self, **event_args):
        H = sr.first((self.b.get("helper") or {}).get("name"))
        r = self._act("Validated. Now pay %s." % H, "validate_work", self.id, list(self._vchecks), self.validate_note.text or "")
        if r and r.get("bonus_earned"):
            sr.confetti()

    # ---- reviews
    def _draw_stars(self):
        for i, node in enumerate([self.dom_nodes["s1"], self.dom_nodes["s2"], self.dom_nodes["s3"], self.dom_nodes["s4"], self.dom_nodes["s5"]]):
            on = i < self._stars
            node.classList.toggle("on", on)
            node.setAttribute("aria-pressed", "true" if (i + 1) == self._stars else "false")

    def star_click(self, event):
        self._stars = int(event.currentTarget.getAttribute("data-star"))
        self._draw_stars()

    def _draw_tags(self):
        self.tags_panel.items = [{"key": t, "label": t, "on": t in self._tags} for t in self._review_tags]

    def _tag(self, **event_args):
        key = event_args["key"]
        focus = state.focus_key()
        if key in self._tags:
            self._tags.remove(key)
        else:
            self._tags.append(key)
        self._draw_tags()
        state.refocus(self.tags_panel, focus)

    @handle("review_button", "click")
    def review_button_click(self, **event_args):
        if not self._stars:
            state.toast("Pick 1 to 5 stars.", "error")
            return
        self._act("Thanks for the review!", "leave_review", self.id, self._stars, list(self._tags), self.review_text.text or "")

    # ---- chat
    @handle("chat_button", "click")
    def chat_button_click(self, **event_args):
        text = self.chat_text.text or ""
        if not text.strip():
            return
        self.chat_button.enabled = False
        try:
            r = anvil.server.call_s("send_message", self.id, text)
        finally:
            self.chat_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            state.toast(r.get("error") or "That message didn't send.", "error")
            return
        self.b.setdefault("messages", []).append(r["message"])
        self.chat_text.text = ""
        self._chat_draw()
