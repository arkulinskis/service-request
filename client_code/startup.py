"""The app starts here (anvil.yaml: startup module). One server call to learn who is signed in (Anvil's loading
spinner shows meanwhile), the Privacy & Terms kit, then the page for the address in the browser bar."""
import json

import anvil.server
from anvil.js import window

from . import legal, router, state


def _test_call(name, args_json):
    """window.srCall(name, argsJson): the same server calls the pages make (still signed-in and permission-checked),
    so tools/ui/smoke.js can create a bounty in one line and open the poster's view of it."""
    return json.dumps(anvil.server.call(name, *json.loads(args_json or "[]")))


window.srCall = _test_call

LEGAL_THEME = {"accent": "#111111"}  # colours for the Privacy & Terms page (near-black, --c-brand in app.css)

legal.setup(LEGAL_THEME)
state.set_me(anvil.server.call("get_me"))
if state.me():
    legal.refresh_soon()
router.start()
