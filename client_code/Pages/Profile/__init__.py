from anvil import *
import anvil.server

from ._anvil_designer import ProfileTemplate
from ... import auth, router, sr, state

THEMES = ["auto", "light", "dark"]


class Profile(ProfileTemplate):
    """Your account (#profile): name, helper profile (bio, skills, e-Transfer email, open to jobs), the area you work
    around, appearance, password reset, privacy, sign out."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.C = sr.catalog()
        state.set_control_attr(self.name_box, "autocomplete", "name")
        state.set_control_attr(self.name_box, "maxlength", 60)
        state.set_control_attr(self.bio_box, "maxlength", 400)
        state.set_control_attr(self.payout_box, "maxlength", 200)
        state.set_control_attr(self.payout_box, "autocomplete", "email")
        self.skills_panel.add_event_handler("x-chip", self._skill)
        self._draw()

    def _draw(self):
        me = state.me() or {}
        n = self.dom_nodes
        n["av"].textContent = state.initials(me.get("name"))
        n["name"].textContent = me.get("name") or ""
        n["email"].textContent = (me.get("email") or "") + ((" · member since " + sr.fmt_date(me["joined"], {"month": "long", "year": "numeric"})) if me.get("joined") else "")
        sr.rich(n["seen_as"], "Neighbours see you as <b>%s</b>.%s" % (sr.esc(me.get("short") or ""),
                (' <span class="ui-badge warn">%s</span>' % sr.esc(sr.plural(me["strikes"], "strike"))) if me.get("strikes") else ""))
        n["public_link"].setAttribute("href", router.href("neighbour", me.get("id")))
        self.helper_on.checked = bool(me.get("helper_on"))
        self.bio_box.text = me.get("bio") or ""
        self._skills = list(me.get("skills") or [])
        self._draw_skills()
        self.payout_box.text = me.get("payout_email") or ""
        spot = me.get("spot")
        n["area"].textContent = spot["label"] if spot else "Not set"
        n["area_sub"].textContent = "Bounties are sorted by distance from here." if spot else "Set it to see bounties by distance."
        self.area_button.text = "Change" if spot else "Set my area"
        n["name_cap"].textContent = 'Your full name (others see "%s")' % (me.get("short") or "")
        self.name_box.text = me.get("name") or ""
        self.admin_link.visible = bool(me.get("is_admin"))
        self._show_theme()

    def _draw_skills(self):
        self.skills_panel.items = [{"key": s, "label": s, "on": s in self._skills} for s in self.C["skills"]]

    def _skill(self, **event_args):
        key = event_args["key"]
        focus = state.focus_key()
        if key in self._skills:
            self._skills.remove(key)
        else:
            self._skills.append(key)
        self._draw_skills()
        state.refocus(self.skills_panel, focus)

    @handle("helper_button", "click")
    def helper_button_click(self, **event_args):
        skills = [s for s in self.C["skills"] if s in self._skills]
        r = state.call("update_helper_profile", self.bio_box.text or "", skills, self.payout_box.text or "", bool(self.helper_on.checked))
        if r:
            state.set_me(r["me"])
            state.toast("Helper profile saved", "ok")
            self._draw()

    @handle("name_button", "click")
    def name_button_click(self, **event_args):
        r = state.call("update_profile", self.name_box.text or "")
        if r:
            state.set_me(r["me"])
            state.toast("Saved", "ok")
            self._draw()
            if self.layout is not None and hasattr(self.layout, "refresh"):
                self.layout.refresh("profile")

    @handle("area_button", "click")
    def area_button_click(self, **event_args):
        if sr.edit_area():
            self._draw()

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        r = auth.reset((state.me() or {}).get("email") or "")
        state.toast(r.get("message") or "Sent.", "ok")

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()
        if self.layout is not None and hasattr(self.layout, "refresh"):
            self.layout.refresh("profile")

    def _show_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark]):
            el.classes["on"] = name == t

    def feedback_click(self, event):
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.toast("Signed out. See you soon!")
        router.go("landing")
