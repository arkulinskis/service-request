"""Photos: the poster's "before" pictures and the helper's proof. The phone shrinks each one (a full JPEG and a
thumbnail) and uploads it straight away (upload_photo); posting or sending proof then attaches it (claim).

Served at <app>/_/api/photo?k=<key>[&s=t] under 24 random characters, only once attached to a bounty. The
keys only reach people who may see the bounty (proof photos: the poster, the helper and moderators).
Unattached uploads are cleaned up after a day.
"""
import base64
import datetime as dt

import anvil
import anvil.server
from anvil.tables import app_tables

from . import common as C

MAX_PENDING = 12
FULL_LIMIT = 900 * 1024
THUMB_LIMIT = 200 * 1024


def _image(data_url, limit):
    """data:image/...;base64,... -> BlobMedia, only real JPEG / PNG / WebP pictures."""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/") or ";base64," not in data_url:
        return None
    if len(data_url) > limit * 4 // 3 + 200:
        return None
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=False)
    except Exception:
        return None
    if raw[:3] == b"\xff\xd8\xff":
        kind = "image/jpeg"
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "image/png"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        kind = "image/webp"
    else:
        return None
    if len(raw) > limit:
        return None
    return anvil.BlobMedia(kind, raw, name="photo." + kind.split("/")[1])


@anvil.server.callable(require_user=True)
def upload_photo(full, thumb):
    me = C.require_user()
    if C.rate_limited("photo", 60, 3600):
        return C.fail("That's a lot of photos in one hour. Please take a short break.")
    img, th = _image(full, FULL_LIMIT), _image(thumb, THUMB_LIMIT)
    if img is None or th is None:
        return C.fail("That picture didn't work. Try another photo (JPEG or PNG).")
    old = C.now() - dt.timedelta(days=1)
    pending = []
    for p in app_tables.photos.search(owner=me, bounty=None):
        if p["created"] < old:
            p.delete()
        else:
            pending.append(p)
    if len(pending) >= MAX_PENDING:
        return C.fail("Finish the bounty or proof you're working on first, then add more photos.")
    p = app_tables.photos.add_row(owner=me, bounty=None, key=C.token(24), image=img, thumb=th, created=C.now(), is_demo=False)
    return C.ok(key=p["key"])


def claim(me, keys, limit, bounty=None):
    """The photo rows for these keys, in order: the caller's own and not used elsewhere. (rows, problem)"""
    if not isinstance(keys, list):
        return [], "Those photos didn't come through. Add them again?"
    if len(keys) > limit:
        return [], "Up to %d photos here." % limit
    rows = []
    for k in keys:
        p = app_tables.photos.get(key=k) if isinstance(k, str) and k else None
        if p is None or p["owner"] != me or (p["bounty"] is not None and p["bounty"] != bounty):
            return [], "One of the photos is missing. Take it again?"
        rows.append(p)
    return rows, None


@anvil.server.http_endpoint("/photo")
def photo(k=None, s=None, **kw):
    p = app_tables.photos.get(key=k) if isinstance(k, str) and 10 <= len(k) <= 40 else None
    if p is None or p["bounty"] is None:
        return anvil.server.HttpResponse(404, "Not found")
    media = p["thumb"] if s == "t" and p["thumb"] is not None else p["image"]
    return anvil.server.HttpResponse(200, media, headers={"Cache-Control": "public, max-age=31536000, immutable",
                                                         "Content-Type": media.content_type})
