"""Little illustrated "photos" for the demo bounties (SVG, drawn here, served by Photos.photo like real ones).
Clearly drawings, so nobody mistakes the demo for real neighbours' yards."""
import random

import anvil

W, H = 800, 600


def _sky(top, bottom):
    return ('<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/>'
            '<stop offset="1" stop-color="%s"/></linearGradient></defs><rect width="800" height="600" fill="url(#s)"/>' % (top, bottom))


def _house(x=470, y=150, wall="#e9dcc6", roof="#5b3a2e", door="#2c5d8a"):
    return ('<rect x="%d" y="%d" width="260" height="190" fill="%s" stroke="#111" stroke-width="5"/>'
            '<path d="M%d %d L%d %d L%d %d Z" fill="%s" stroke="#111" stroke-width="5" stroke-linejoin="round"/>'
            '<rect x="%d" y="%d" width="56" height="96" fill="%s" stroke="#111" stroke-width="5"/>'
            '<rect x="%d" y="%d" width="70" height="56" fill="#bfe3f2" stroke="#111" stroke-width="5"/>'
            '<rect x="%d" y="%d" width="70" height="56" fill="#bfe3f2" stroke="#111" stroke-width="5"/>'
            % (x, y + 60, wall, x - 20, y + 64, x + 130, y - 30, x + 280, y + 64, roof, x + 102, y + 154, door,
               x + 20, y + 100, x + 170, y + 100))


def _tree(x, y, crown):
    return ('<rect x="%d" y="%d" width="22" height="120" fill="#6b4a33" stroke="#111" stroke-width="5"/>'
            '<circle cx="%d" cy="%d" r="78" fill="%s" stroke="#111" stroke-width="5"/>' % (x - 11, y, x, y - 30, crown))


def leaves(after=False):
    rnd = random.Random(11)
    out = [_sky("#bcdcf0", "#f3e9d2"), _tree(170, 250, "#e08a1e" if not after else "#c86b12"), _house()]
    out.append('<rect y="370" width="800" height="230" fill="#7fb24a" stroke="#111" stroke-width="5"/>')
    out.append('<rect x="560" y="370" width="60" height="230" fill="#cfc6b8" stroke="#111" stroke-width="4"/>')
    if not after:
        for _ in range(240):
            x, y = rnd.uniform(0, 800), rnd.uniform(380, 600)
            c = rnd.choice(["#e8590c", "#f59f00", "#d9480f", "#ffd43b", "#a0522d"])
            out.append('<ellipse cx="%.0f" cy="%.0f" rx="11" ry="6" fill="%s" transform="rotate(%d %.0f %.0f)"/>'
                       % (x, y, c, rnd.randint(0, 180), x, y))
    else:
        for i, x in enumerate((40, 120, 200, 280)):
            out.append('<path d="M%d 520 l10 -86 h62 l10 86 Z" fill="#c8a06a" stroke="#111" stroke-width="5" stroke-linejoin="round"/>'
                       '<path d="M%d 448 h62" stroke="#111" stroke-width="4"/>' % (x, x + 10))
        out.append('<text x="400" y="580" font-family="Arial" font-weight="900" font-size="34" fill="#111">AFTER</text>')
    return out


def snow():
    rnd = random.Random(5)
    out = [_sky("#9fb6c8", "#e7eef3"), _house(wall="#dfe7ee", roof="#38424c"),
           '<rect y="360" width="800" height="240" fill="#ffffff" stroke="#111" stroke-width="5"/>',
           '<path d="M360 600 L420 360 H540 L640 600 Z" fill="#eef3f7" stroke="#111" stroke-width="5"/>',
           '<rect x="380" y="430" width="200" height="90" rx="30" fill="#c92a2a" stroke="#111" stroke-width="5"/>',
           '<path d="M380 452 q100 -40 200 0" fill="#fff" stroke="#111" stroke-width="4"/>',
           '<circle cx="420" cy="525" r="22" fill="#222"/><circle cx="545" cy="525" r="22" fill="#222"/>']
    for _ in range(120):
        out.append('<circle cx="%.0f" cy="%.0f" r="%.1f" fill="#fff" opacity=".9"/>' % (rnd.uniform(0, 800), rnd.uniform(0, 360), rnd.uniform(2, 6)))
    return out


def junk():
    return [_sky("#cfd8dc", "#eceff1"), '<rect y="380" width="800" height="220" fill="#9e9e9e" stroke="#111" stroke-width="5"/>',
            '<rect x="90" y="300" width="330" height="120" rx="20" fill="#6d4c8d" stroke="#111" stroke-width="6"/>',
            '<rect x="70" y="350" width="60" height="110" rx="16" fill="#5a3d76" stroke="#111" stroke-width="6"/>',
            '<rect x="380" y="350" width="60" height="110" rx="16" fill="#5a3d76" stroke="#111" stroke-width="6"/>',
            '<rect x="110" y="390" width="310" height="70" rx="10" fill="#7e5ca3" stroke="#111" stroke-width="6"/>',
            '<rect x="500" y="320" width="120" height="110" fill="#c8a06a" stroke="#111" stroke-width="6"/>',
            '<rect x="560" y="230" width="110" height="90" fill="#d7b07a" stroke="#111" stroke-width="6"/>',
            '<rect x="640" y="340" width="100" height="120" fill="#c8a06a" stroke="#111" stroke-width="6"/>',
            '<path d="M500 375 h120 M560 275 h110 M640 400 h100" stroke="#111" stroke-width="4"/>']


def boxes():
    out = [_sky("#f1e7d6", "#f8f2e8"), '<rect y="420" width="800" height="180" fill="#b08968" stroke="#111" stroke-width="5"/>']
    for x, y, w, h in ((80, 300, 180, 140), (270, 330, 160, 110), (450, 280, 200, 160), (130, 180, 150, 120),
                       (480, 160, 140, 120), (660, 340, 110, 100)):
        out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#d4a373" stroke="#111" stroke-width="6"/>'
                   '<path d="M%d %d h%d" stroke="#111" stroke-width="4"/><rect x="%d" y="%d" width="%d" height="14" fill="#ffd400" stroke="#111" stroke-width="3"/>'
                   % (x, y, w, h, x, y + 30, w, x + w // 2 - 20, y + 10, 40))
    return out


SCENES = {"leaves": lambda: leaves(False), "lawn": lambda: leaves(True), "snow": snow, "junk": junk, "boxes": boxes}


def svg(scene):
    body = "".join(SCENES[scene]())
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">%s'
            '<rect x="16" y="16" width="118" height="40" rx="6" fill="#ffd400" stroke="#111" stroke-width="4"/>'
            '<text x="30" y="45" font-family="Arial" font-weight="900" font-size="24" fill="#111">DEMO</text></svg>'
            % (W, H, W, H, body))


def media(scene):
    return anvil.BlobMedia("image/svg+xml", svg(scene).encode("utf-8"), name=scene + ".svg")
