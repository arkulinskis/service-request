"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules.

Links in templates are plain <a href="#board">; code calls router.go("bounty", id). The addresses are the same as in
the JavaScript version (#bounty/<id>, #jobs/<tab>, #admin/<tab>, #post/<task>, #rules/<section> ...), so links people
shared keep working.

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only, "user", "admin"
    NAV = the main menu (header + phone tab bar, signed-in people): (page, label, icon). At most 4.
New page: add it to PAGES, to _form() and (if it belongs in the menu) to NAV.
"""
import anvil
import anvil.js
from anvil.js import window

from . import state

PAGES = {
    "landing": (None, "Neighbourhood bounties"),
    "auth": ("guest", "Sign in"),
    "board": (None, "Bounty board"),
    "bounty": (None, "Bounty"),
    "post": ("user", "Post a bounty"),
    "jobs": ("user", "My jobs"),
    "ledger": ("user", "Ledger"),
    "neighbour": (None, "Neighbour"),
    "rules": (None, "Rules & safety"),
    "profile": ("user", "Your profile"),
    "admin": ("admin", "Admin"),
}
NAV = [("board", "Bounties", "search"), ("post", "Post", "plus"), ("jobs", "My jobs", "clipboard"), ("ledger", "Ledger", "wallet")]
APP_NAME = "Service Request"
_r: dict = {"after": "", "listening": False, "page": None}


def _form(name):
    """The page's Form class (imported when first needed, so start-up stays quick)."""
    if name == "landing":
        from .Pages.Landing import Landing
        return Landing
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "board":
        from .Pages.Board import Board
        return Board
    if name == "bounty":
        from .Pages.Bounty import Bounty
        return Bounty
    if name == "post":
        from .Pages.Post import Post
        return Post
    if name == "jobs":
        from .Pages.Jobs import Jobs
        return Jobs
    if name == "ledger":
        from .Pages.Ledger import Ledger
        return Ledger
    if name == "neighbour":
        from .Pages.Neighbour import Neighbour
        return Neighbour
    if name == "rules":
        from .Pages.Rules import Rules
        return Rules
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    from .Pages.Admin import Admin
    return Admin


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids like [8,83] contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return "board" if state.me() else "landing"


def set_title(text):
    window.document.title = text + " · " + APP_NAME


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
        window.history.replaceState(None, "", href(name))
    who = PAGES[name][0]
    if who == "guest" and state.me():
        name, args = "board", []
        window.history.replaceState(None, "", href(name))
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = "board", []
        window.history.replaceState(None, "", href(name))
    set_title(PAGES[name][1])
    window.UI_READY = False
    old = _r["page"]
    if old is not None and hasattr(old, "leave"):
        old.leave()  # pages with maps or timers let go of them here
    page = _form(name)(args=args)
    _r["page"] = page
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    if hasattr(page, "after_open"):
        page.after_open()  # e.g. #rules/scams scrolls to that section
    window.UI_READY = True  # tests and screenshots wait for this


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or the board."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash:
        window.location.hash = target
    else:
        go("board")


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
