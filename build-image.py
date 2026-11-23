#!/usr/bin/env python3
"""news-image-20261122 — render the Sunday 22 November 2026 front page.

One image, 1024x1024, PIL only, fully deterministic (no network, no clock,
no unseeded randomness). Writes entry.png next to this script.
Layout follows the proven winner template: masthead -> UTC strip -> numbers
strip -> 3 big photo leads -> 10 medium photo cards (v11: full-width photo
banner on top, like the top entries) -> region bar -> world map
"WHERE IT HAPPENED" -> "ALSO ON" 23 small stories -> DATE CHECK -> HOW
SURE -> footer. 36 stories, 6 regions.
"""
import hashlib
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1024, 1024
PAPER = (245, 239, 224)      # cream paper
PAPER2 = (238, 231, 212)     # slightly darker cream
INK = (26, 26, 26)
GREY = (90, 86, 76)
RED = (178, 28, 28)
REDBG = (122, 20, 20)
BLUE = (30, 64, 140)
BLUE2 = (58, 110, 190)
GREEN = (34, 110, 60)
AMBER = (166, 110, 10)
GOLD = (176, 138, 30)
LINE = (120, 112, 94)
SEA = (168, 196, 214)
LAND = (232, 224, 198)
LAND2 = (214, 204, 172)

FDIR = "/usr/share/fonts/truetype/dejavu"
SERIF = os.path.join(FDIR, "DejaVuSerif.ttf")
SERIFB = os.path.join(FDIR, "DejaVuSerif-Bold.ttf")
SANS = os.path.join(FDIR, "DejaVuSans.ttf")
SANSB = os.path.join(FDIR, "DejaVuSans-Bold.ttf")

_fonts = {}


def font(path, size):
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def tw(draw, text, f):
    """Text width."""
    return draw.textlength(text, font=f)


def wrap(draw, text, f, width):
    """Word-wrap text to a max pixel width; returns list of lines."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def para(draw, x, y, text, f, fill, width, lh=None, max_lines=None):
    """Draw wrapped paragraph; returns y after last line."""
    if lh is None:
        lh = f.size + 2
    lines = wrap(draw, text, f, width)
    if max_lines:
        lines = lines[:max_lines]
    for ln in lines:
        draw.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


def badge(draw, x, y, level):
    """Confidence badge; returns width used."""
    conf = {"CONFIRMED": (GREEN, "CONFIRMED"), "OFFICIAL": (BLUE, "OFFICIAL"),
            "REPORTED": (AMBER, "REPORTED")}
    col, txt = conf[level]
    f = font(SANSB, 7)
    w = int(draw.textlength(txt, font=f)) + 8
    draw.rounded_rectangle([x, y, x + w, y + 10], radius=2, fill=col)
    draw.text((x + 4, y + 1), txt, font=f, fill=(255, 255, 255))
    return w


def rule(draw, x0, x1, y, fill=INK, width=1):
    draw.line([(x0, y), (x1, y)], fill=fill, width=width)


# ---------------------------------------------------------------- v5 finesse
# Subtle shading / gradient / texture helpers. All deterministic (no
# randomness, no clock): gradients are per-row lerps, stipple jitter is
# arithmetic on grid coords, GaussianBlur is deterministic in Pillow.






def _rect_shadow(img, x0, y0, x1, y1, offset=(3, 4), blur=4, alpha=50):
    """Soft drop shadow of a rectangle (for the lead boxes)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rectangle([x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]],
                 fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base = img.convert("RGBA")
    out = Image.alpha_composite(base, layer)
    img.paste(out.convert("RGB"), (0, 0))


def _inside(px, py, pts):
    """Point-in-polygon (ray casting), for stipple clipping."""
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _stipple(draw, pts, dot, step=9):
    """Very subtle 1px dot texture inside a polygon. Jitter is
    arithmetic on grid coords (deterministic); dots are only a shade
    darker than the land so they read as texture, not noise."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for gy in range(int(min(ys)) + 4, int(max(ys)), step):
        for gx in range(int(min(xs)) + 4, int(max(xs)), step):
            jx = ((gx * 7 + gy * 13) % 5) - 2
            jy = ((gx * 11 + gy * 3) % 5) - 2
            if _inside(gx + jx, gy + jy, pts):
                draw.point((gx + jx, gy + jy), fill=dot)


# ---------------------------------------------------------------- v6 organic
# Hand-drawn feel: seeded jitter on polygon points, pen-stroke outlines
# with varying width, watercolor washes, paper grain. All deterministic:
# every jitter/noise draw uses its own random.Random(seed) — never the
# global random module, never the clock — so two runs are byte-identical.
def _jitter_pts(pts, amp, seed):
    """Return polygon points shifted by a seeded uniform jitter in
    [-amp, amp] px. Same seed -> same output. Amplitude 2-4px is enough
    to kill the "ruler" look without the shape becoming unrecognisable."""
    rng = random.Random(seed)
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp))
            for x, y in pts]


def _hand_outline(draw, pts, col, seed, closed=True):
    """Pen-stroke outline: a continuous 1px base line (so there are no
    joint gaps), then ~35% of the segments redrawn at 2px for pen
    pressure variation. Reads as a hand-drawn stroke, not a ruler line."""
    rng = random.Random(seed)
    n = len(pts)
    if closed:
        pairs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    else:
        pairs = [(pts[i], pts[i + 1]) for i in range(n - 1)]
    for a, b in pairs:
        draw.line([a, b], fill=col, width=1)
    # v7: stronger pen pressure — half the segments redrawn at 2px, and
    # long segments sometimes at 3px, so the stroke visibly varies
    for a, b in pairs:
        r = rng.random()
        seg = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        if r < 0.12 and seg > 8:
            draw.line([a, b], fill=col, width=3)
        elif r < 0.5:
            draw.line([a, b], fill=col, width=2)




def _watercolor(img, pts, color, alpha=40, seed=7, layers=2):
    """Fill a polygon with 2 translucent washes, each shifted a few px
    (seeded) — like watercolor over the flat fill. The wash is clipped
    to the original polygon so nothing spills past the edge."""
    rng = random.Random(seed)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    base = img.convert("RGBA")
    for _ in range(layers):
        dx = rng.uniform(-2.5, 2.5)
        dy = rng.uniform(-2.5, 2.5)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.polygon([(x + dx, y + dy) for x, y in pts], fill=color + (alpha,))
        la = ImageChops.multiply(layer.split()[3], mask)
        layer.putalpha(la)
        base = Image.alpha_composite(base, layer)
    img.paste(base.convert("RGB"), (0, 0))


def _paper_grain(img, seed=42, dots=3500, alpha=10):
    """Very subtle deterministic grain over the whole page — a few
    thousand 1px dots at ~4% alpha. Gives a paper feel at full size;
    invisible at 300px, and far too faint to hurt text crispness."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(dots):
        x = rng.uniform(0, img.size[0] - 1)
        y = rng.uniform(0, img.size[1] - 1)
        v = (0, 0, 0) if rng.random() < 0.6 else (255, 255, 255)
        ld.point((x, y), fill=v + (alpha,))
    base = img.convert("RGBA")
    out = Image.alpha_composite(base, layer)
    img.paste(out.convert("RGB"), (0, 0))


# ---------------------------------------------------------------- v10 photos
# Photorealistic photos (fixed files in photos/, committed to the repo).
# The build only reads + center-crops + LANCZOS-resizes them — no network,
# no clock, no randomness, so two runs are byte-identical.
_PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
LEAD_PHOTOS = {1: "lead1-cop31.jpg", 2: "lead2-warship.jpg", 3: "lead3-capitol.jpg"}
MED_PHOTOS = {4: "med4-dymer.jpg", 5: "med5-sparta.jpg", 6: "med6-missiles.jpg",
              7: "med7-market.jpg", 8: "med8-f1.jpg", 9: "med9-quake.jpg",
              10: "med10-storm.jpg", 11: "med11-factory.jpg", 12: "med12-ebola.jpg",
              13: "med13-mercury.jpg"}
# Focus point of the center crop (fraction of source size). Lead 3's dome
# sits at the top of its frame, so bias the crop upward; med 12's subject
# stands on the right; med 9's house is right of centre; med 4's building
# and med 8's car sit left of centre.
LEAD_FOCUS = {1: (0.5, 0.55), 2: (0.5, 0.5), 3: (0.5, 0.30)}
MED_FOCUS = {4: (0.45, 0.5), 5: (0.5, 0.5), 6: (0.5, 0.5), 7: (0.5, 0.5),
             8: (0.45, 0.5), 9: (0.6, 0.5), 10: (0.5, 0.5), 11: (0.5, 0.5),
             12: (0.75, 0.5), 13: (0.5, 0.5)}
_photo_cache = {}


def _cover(num, w, h, lead=True):
    """Load a photo, center-crop it to the target aspect ratio around its
    focus point, and LANCZOS-resize to (w, h). Results are cached so each
    file is read once per run."""
    key = (num, w, h, lead)
    if key in _photo_cache:
        return _photo_cache[key]
    fname = (LEAD_PHOTOS if lead else MED_PHOTOS)[num]
    focus = (LEAD_FOCUS if lead else MED_FOCUS)[num]
    src = Image.open(os.path.join(_PHOTO_DIR, fname)).convert("RGB")
    sw, sh = src.size
    target = w / h
    if sw / sh > target:  # too wide: crop the sides
        cw = int(sh * target)
        cx = int(focus[0] * sw)
        x0 = max(0, min(sw - cw, cx - cw // 2))
        box = (x0, 0, x0 + cw, sh)
    else:  # too tall: crop top/bottom
        ch = int(sw / target)
        cy = int(focus[1] * sh)
        y0 = max(0, min(sh - ch, cy - ch // 2))
        box = (0, y0, sw, y0 + ch)
    out = src.crop(box).resize((w, h), Image.LANCZOS)
    _photo_cache[key] = out
    return out


# ---------------------------------------------------------------- data
# (num, kicker, headline, deck, source, confidence, region)
LEADS = [
    (1, "ANTALYA, TÜRKIYE  ·  CLIMATE",
     "COP31 COLLAPSES",
     "No deal on fossil fuels. After days of overtime, nearly 200 nations leave Antalya without a cover decision; the EU rejects a final draft that does not mention fossil fuels at all.",
     "Reuters · AP · AFP", "CONFIRMED"),
    (2, "BENGHAZI, LIBYA  ·  WAR",
     "RUSSIAN WARSHIP HIT",
     "A Ukrainian sea drone strikes the Russian corvette Merkury at the Benghazi naval base. The ship is badly damaged and a fire breaks out at the facility, Libyan officers say.",
     "Reuters · AP", "CONFIRMED"),
    (3, "WASHINGTON  ·  POLITICS",
     "DEMOCRATS TAKE 258 SEATS",
     "Democrats secure at least 258 of 435 House seats — their largest majority since 1992 — after Hubbard beats Foxx in North Carolina. The Senate stays Democratic too.",
     "AP · Reuters", "CONFIRMED"),
]

# (num, kicker, headline, deck, source, confidence, icon)
MEDIUM = [
    (4, "KYIV  ·  WAR", "Drones hit flats in Dymer",
     "3–4 killed, 14 missing. Overnight: 400+ drones, 110 missiles.",
     "AP · Reuters", "CONFIRMED", "blast"),
    (5, "BALTIC SEA  ·  WAR", "Burning Sparta II towed away",
     "Finland: Russia tows the ship away after a drone strike.",
     "Reuters · BBC", "CONFIRMED", "ship"),
    (6, "LONDON  ·  MILITARY", "UK sends 1,000+ missiles",
     "Britain sends 1,000+ missiles to Ukraine in a £240m package.",
     "Reuters", "OFFICIAL", "missile"),
    (7, "WALL STREET  ·  ECONOMY", "S&P 500 falls 3.7%",
     "Dow in correction; Nasdaq erases 2026 gains as AI stocks plunge.",
     "AP · Reuters", "CONFIRMED", "chart"),
    (8, "LAS VEGAS  ·  SPORT", "Verstappen wins in Vegas",
     "35 lead changes; wins by 0.639s over Norris. Piastri third.",
     "AP · F1", "CONFIRMED", "flag"),
    (9, "JUNÍN, PERU  ·  DISASTER", "Quake toll: 1 dead, 93,000 dark",
     "INDECI: 1 killed, 16 hurt, 853 displaced, 93,000 without power.",
     "INDECI · USGS", "OFFICIAL", "quake"),
    (10, "BRAZIL  ·  DISASTER", "Supercell: 4 killed, 162 hurt",
     "Disaster decree in Tupanciretã; 8,000+ homes damaged.",
     "Reuters · AP", "CONFIRMED", "storm"),
    (11, "CIKANDE, INDONESIA  ·  DISASTER", "Factory fire: 3 dead, 34 missing",
     "A candy factory burns in Banten; bodies found in 24 bags.",
     "AP · Reuters", "CONFIRMED", "fire"),
    (12, "DR CONGO  ·  HEALTH", "Ebola passes 11,021 cases",
     "5,358 dead. WHO: fighting near Ituri hospital disrupts aid.",
     "WHO · CDC", "OFFICIAL", "virus"),
    (13, "MERCURY  ·  SPACE", "BepiColombo reaches Mercury",
     "Enters orbit after 8 years; ESA reports a thruster glitch.",
     "Reuters · ESA", "CONFIRMED", "planet"),
]

# (num, place, headline, source) — 23 small stories, grouped by region.
# v4: cut 8 least-significant stories (minor sports score, minor arrests,
# small local protest, local transport disruption, animal birth, minor
# resignation) to free ~44px for bigger lead illustrations.
SMALL = [
    (14, "WASHINGTON", "Trump signs EO 14438: contractors must consult the White House.", "AP"),
    (15, "WASHINGTON", "Trump confirms the FBI crime database was hacked.", "Reuters"),
    (16, "ARIZONA", "SpaceX's $74bn AI campus stalls in a power-bill dispute (6,000 MW).", "Fortune"),
    (17, "NEW YORK", "Anthropic's IPO sparks a Wall Street row over unusual deal limits.", "Reuters"),
    (18, "ARGENTINA", "$50bn LNG project approved.", "Reuters"),
    (19, "ARGENTINA", "Country risk hits 1,070, the highest of 2026.", "JPMorgan"),
    (20, "POLAND", "Kh-101 missile debris found at three sites.", "Reuters"),
    (21, "LONDON", "Conservatives vow to scrap the UK–EU deal.", "Reuters"),
    (22, "BRUSSELS", "EU's Costa proposes €204bn in savings and a digital tax.", "Handelsblatt"),
    (23, "TEHRAN", "Trump dares Iran to break the US port blockade.", "AP"),
    (24, "SITRA, BAHRAIN", "Iranian attack on a civilian industrial site causes a fire; 2 hurt.", "Reuters"),
    (25, "STRAIT OF HORMUZ", "Iran hits three tankers; UKMTO reports a vessel incident.", "UKMTO"),
    (26, "GAZA CITY", "Israeli strike on a food van kills 3.", "AP"),
    (27, "BAYELSA, NIGERIA", "Death toll from a capsized mourners' boat rises to 26.", "Reuters"),
    (28, "KHARTOUM", "Drones hit homes and a UN building in Khartoum.", "OCHA"),
    (29, "ATLANTIC", "Migrant boat capsizes off Senegal; 39 dead.", "Reuters"),
    (30, "OYO, CONGO", "Kenya and DR Congo restore full diplomatic ties at a summit.", "Reuters"),
    (31, "ODISHA, INDIA", "Cyclone Akvan weakens to a depression; 300,000+ evacuated.", "IMD"),
    (32, "BEIJING", "China–Japan ties worsen over Taiwan and critical minerals.", "Reuters"),
    (33, "DHAKA", "Deadly protests over the exiled former leader.", "Reuters"),
    (34, "COOK ISLANDS", "Cyclone Xavier weakens to Category 1; emergency status stays.", "MetService"),
    (35, "GENEVA", "UN talks on AI weapons end with no binding rules.", "AFP"),
    (36, "ORBIT", "Earth gains a 'mini-moon', 2026 QQ8, a 2-metre asteroid.", "CNN"),
]

UTC_STRIP = [
    ("02:00", "Akvan weakens over India"),
    ("06:30", "Drones hit flats in Dymer"),
    ("11:00", "COP31 ends with no deal"),
    ("15:00", "Warship hit at Benghazi"),
    ("18:26", "Democrats reach 258 seats"),
    ("20:30", "BepiColombo reaches Mercury"),
    ("23:30", "Verstappen wins in Vegas"),
]

NUMBERS = [
    ("258", "Democratic seats in the US House"),
    ("186", "drones fired at Ukraine overnight"),
    ("M6.7", "Peru earthquake"),
    ("26", "killed as a boat capsizes in Nigeria"),
    ("93,000", "without power after the Peru quake"),
    ("50", "points for Wembanyama"),
]

REGIONS = [
    ("Europe", 7, (178, 28, 28)), ("Americas", 11, (30, 64, 140)),
    ("Middle East", 5, (166, 110, 10)), ("Africa", 5, (120, 72, 20)),
    ("Asia-Pacific", 5, (140, 40, 120)), ("World", 3, (90, 86, 76)),
]

# (lat, lon) for map pins 1-13
PINS = {
    1: (36.9, 30.7), 2: (32.1, 20.1), 3: (38.9, -77.0), 4: (50.5, 30.5),
    5: (59.0, 21.0), 6: (51.5, -0.1), 7: (40.7, -74.0), 8: (36.1, -115.1),
    9: (-11.0, -75.0), 10: (-29.0, -54.0), 11: (-6.3, 106.3),
    12: (1.0, 30.0), 13: (None, None),  # 13 = space: star marker
}
# Visual nudge (dx, dy) for pins whose true positions collide, with a leader
# line from the true spot to the drawn pin.
PIN_OFFSETS = {1: (16, 12), 2: (-18, 12), 3: (-13, 11), 4: (13, -13),
               5: (-15, -13), 7: (13, -11)}


# ---------------------------------------------------------------- icons


# ---------------------------------------------------------------- maps
# World map: continents as (lon, lat) coastlines, drawn with an
# equirectangular projection cropped to lat 84..-60 so the strip reads
# larger. Pins use the same projection, so they land on the land.
LAT_TOP, LAT_BOT = 84.0, -60.0


def world_xy(lat, lon, x0, y0, w, h):
    x = x0 + (lon + 180.0) / 360.0 * w
    y = y0 + (LAT_TOP - lat) / (LAT_TOP - LAT_BOT) * h
    return x, y


# (lon, lat) coastline points, clockwise. Simplified real coastlines —
# enough points to read as the actual continents at this scale.
NORTH_AMERICA = [
    (-168, 66), (-160, 71), (-150, 70), (-140, 70), (-130, 70), (-120, 69),
    (-110, 68), (-100, 68), (-95, 68), (-92, 66), (-88, 60), (-82, 56),
    (-78, 58), (-72, 62), (-66, 60), (-64, 58), (-60, 55), (-56, 52),
    (-60, 47), (-65, 44), (-70, 42), (-73, 40), (-75, 38), (-76, 35),
    (-80, 32), (-81, 28), (-80, 25), (-82, 28), (-85, 30), (-89, 29),
    (-93, 29), (-97, 26), (-97, 22), (-94, 18), (-91, 19), (-87, 21),
    (-88, 16), (-86, 15), (-84, 12), (-82, 9), (-80, 9), (-77, 9),
    (-77, 7), (-80, 7), (-83, 8), (-86, 12), (-90, 14), (-93, 15),
    (-96, 16), (-100, 17), (-105, 20), (-108, 23), (-110, 23), (-112, 28),
    (-114, 31), (-117, 33), (-120, 34), (-122, 37), (-124, 40), (-124, 46),
    (-127, 49), (-130, 54), (-135, 57), (-142, 60), (-148, 60), (-155, 58),
    (-160, 58), (-165, 60),
]
GREENLAND = [
    (-44, 60), (-40, 65), (-32, 68), (-22, 70), (-20, 74), (-25, 78),
    (-35, 80), (-50, 80), (-58, 77), (-56, 72), (-53, 68), (-50, 64),
]
SOUTH_AMERICA = [
    (-77, 7), (-75, 10), (-72, 12), (-68, 11), (-64, 10), (-61, 9),
    (-57, 6), (-53, 5), (-51, 4), (-50, 0), (-44, -3), (-38, -5),
    (-35, -8), (-36, -7), (-37, -11), (-39, -15), (-40, -20), (-42, -23),
    (-44, -24), (-46, -25), (-48, -27), (-52, -32), (-57, -35), (-58, -38),
    (-62, -41), (-65, -45), (-67, -49), (-69, -52), (-68, -55), (-66, -55),
    (-68, -52), (-70, -48), (-72, -42), (-73, -37), (-72, -30), (-71, -26),
    (-70, -23), (-70, -18), (-75, -15), (-77, -12), (-80, -6), (-81, -1),
    (-80, 3), (-77, 5),
]
EUROPE = [
    (18, 70), (25, 71), (30, 70), (29, 68), (28, 66), (24, 62), (21, 59), (19, 55),
    (15, 54), (11, 57), (8, 57), (8, 54), (5, 53), (3, 51), (0, 50),
    (-2, 49), (-2, 47), (-4, 43), (-9, 43), (-9, 41), (-9, 38), (-8, 37), (-6, 36),
    (-2, 36), (0, 39), (3, 42), (6, 43), (9, 44), (12, 42), (14, 40),
    (16, 38), (17, 39), (18, 40), (16, 42), (14, 45), (16, 44), (18, 42), (19, 41),
    (21, 40), (23, 39), (24, 38), (23, 37), (25, 38), (26, 40), (28, 41), (30, 42),
    (33, 44), (36, 45), (39, 46), (41, 46), (43, 45), (45, 44), (47, 45),
    (49, 46), (48, 48), (46, 51), (42, 54), (38, 57), (34, 59), (30, 61),
    (27, 63), (24, 66), (23, 67), (21, 68),
]
BRITAIN = [
    (-5, 50), (-3, 53), (-5, 56), (-4, 58), (-2, 58), (0, 57), (0, 53),
    (1, 51), (-2, 50),
]
AFRICA = [
    (-6, 35), (-9, 32), (-13, 28), (-15, 24), (-17, 21), (-17, 16),
    (-15, 11), (-13, 8), (-8, 5), (-4, 5), (0, 6), (5, 6), (8, 4),
    (9, 4), (12, 0), (13, -3), (12, -6), (13, -12), (12, -17), (14, -22),
    (16, -28), (18, -32), (20, -35), (25, -34), (28, -32), (32, -28),
    (35, -24), (36, -18), (40, -15), (40, -10), (41, -5), (42, -1),
    (46, 0), (51, 2), (51, 10), (48, 11), (44, 11), (42, 12), (40, 15),
    (38, 18), (36, 22), (35, 27), (34, 28), (32, 31), (30, 31), (25, 32),
    (20, 32), (15, 32), (11, 34), (10, 37), (5, 37), (0, 36), (-3, 35),
]
MADAGASCAR = [
    (44, -16), (47, -15), (50, -16), (50, -20), (47, -24), (44, -25),
    (43, -21),
]
ASIA = [
    (28, 41), (30, 41), (33, 42), (36, 42), (39, 41), (41, 41), (44, 39),
    (47, 38), (50, 39), (53, 41), (56, 43), (59, 45), (62, 47), (66, 49),
    (70, 51), (74, 53), (78, 55), (82, 57), (86, 59), (90, 61), (95, 63),
    (100, 65), (105, 67), (110, 69), (115, 71), (120, 72), (125, 71),
    (130, 71), (135, 71), (140, 72), (145, 71), (150, 70), (155, 69),
    (160, 69), (165, 68), (170, 67), (178, 65), (178, 62), (170, 60),
    (163, 59), (158, 55), (156, 51), (152, 48), (148, 45), (144, 42),
    (141, 40), (138, 37), (135, 34), (132, 33), (130, 32), (128, 35),
    (127, 37), (126, 38), (124, 40), (121, 38), (120, 35), (122, 31),
    (121, 28), (119, 24), (117, 22), (113, 22), (109, 19), (107, 15), (106, 12),
    (105, 10), (104, 9), (101, 6), (102, 4), (100, 2), (103, 1), (101, 5), (99, 9), (97, 13),
    (94, 16), (92, 21), (89, 22), (87, 21), (84, 19), (81, 16), (80, 13),
    (78, 9), (77, 8), (76, 10), (74, 14), (72, 19), (70, 22), (67, 24),
    (63, 25), (59, 25), (56, 26), (54, 27), (52, 28), (50, 29), (48, 30),
    (48, 29), (50, 27), (52, 25), (55, 24), (58, 23), (59, 22), (57, 19),
    (55, 17), (52, 15), (49, 14), (46, 13), (43, 12), (42, 14), (40, 19),
    (39, 23), (38, 27), (36, 29), (35, 31), (36, 34), (35, 36), (33, 36),
    (30, 36), (28, 37), (27, 38), (28, 40),
]
JAPAN = [
    (130, 31), (132, 33), (134, 34), (136, 34), (138, 35), (140, 37),
    (141, 39), (141, 41), (142, 43), (144, 44), (142, 42), (140, 39),
    (139, 37), (137, 35), (135, 34), (133, 34), (131, 33),
]
SUMATRA = [
    (95, 5), (98, 3), (100, 1), (102, -1), (104, -3), (106, -6),
    (104, -5), (102, -3), (100, 0), (98, 2),
]
JAVA = [
    (105, -6), (108, -7), (111, -7), (114, -8), (114, -9), (110, -8),
    (107, -7),
]
BORNEO = [
    (109, 1), (111, 3), (114, 5), (117, 6), (119, 3), (118, 0), (116, -2),
    (113, -3), (110, -2),
]
NEW_GUINEA = [
    (131, -1), (135, -2), (138, -3), (141, -3), (144, -5), (146, -6),
    (147, -8), (144, -8), (141, -8), (138, -7), (135, -5), (132, -3),
]
AUSTRALIA = [
    (114, -22), (114, -28), (115, -33), (118, -35), (122, -34), (126, -32),
    (129, -32), (132, -32), (135, -35), (138, -35), (140, -38), (143, -39),
    (146, -39), (149, -37), (150, -34), (153, -31), (153, -27), (151, -24),
    (148, -20), (146, -19), (143, -16), (142, -11), (141, -13), (138, -15),
    (136, -15), (135, -17), (133, -13), (131, -12), (128, -14), (125, -15),
    (122, -17), (119, -20), (116, -21),
]
NEW_ZEALAND = [
    (167, -45), (170, -43), (173, -41), (175, -39), (177, -38), (175, -40),
    (173, -42), (170, -44), (167, -46),
]
WORLD_POLYS = [
    NORTH_AMERICA, GREENLAND, SOUTH_AMERICA, EUROPE, BRITAIN, AFRICA,
    MADAGASCAR, ASIA, JAPAN, SUMATRA, JAVA, BORNEO, NEW_GUINEA, AUSTRALIA,
    NEW_ZEALAND,
]


def draw_world_map(img, draw, x0, y0, w, h):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=SEA, outline=INK, width=1)
    # v7: richer sea — two watercolor washes over the whole map rect
    # (drawn before the land so the continents cover them)
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (150, 185, 210), alpha=22, seed=99)
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (182, 206, 222), alpha=20, seed=98)
    for pi, poly in enumerate(WORLD_POLYS):
        pts = [world_xy(lat, lon, x0, y0, w, h) for lon, lat in poly]
        # v7: wavier coastline — seeded jitter 3.5px on big continents,
        # 2.0px on small islands (up from 2.5/1.5), watercolor wash, and
        # a pen-stroke outline instead of the ruler line
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        big = max(max(xs) - min(xs), max(ys) - min(ys)) > 60
        amp = 3.5 if big else 2.0
        pts = _jitter_pts(pts, amp, 100 + pi)
        # darker land + darker coastline so continents pop off the sea
        draw.polygon(pts, fill=(212, 196, 152))
        _watercolor(img, pts, (196, 178, 132), alpha=35, seed=300 + pi)
        _hand_outline(draw, pts, (105, 95, 68), seed=400 + pi)
        # v5: very subtle dot texture on the land (reads as paper grain,
        # not noise) — drawn before graticule/pins so they stay crisp
        _stipple(draw, pts, (192, 174, 128), step=9)
    # graticule: every 60 deg lon, lat 60/30/-30; equator slightly stronger
    for lon in (-120, -60, 0, 60, 120):
        x = x0 + (lon + 180.0) / 360.0 * w
        draw.line([(x, y0), (x, y0 + h)], fill=(190, 210, 226), width=1)
    for lat in (60, 30, -30):
        _, yy = world_xy(lat, 0, x0, y0, w, h)
        draw.line([(x0, yy), (x0 + w, yy)], fill=(190, 210, 226), width=1)
    _, eq = world_xy(0, 0, x0, y0, w, h)
    draw.line([(x0, eq), (x0 + w, eq)], fill=(175, 198, 218), width=1)
    # pins 1-12
    f = font(SANSB, 9)
    for num, (lat, lon) in sorted(PINS.items()):
        if lat is None:
            continue
        px, py = world_xy(lat, lon, x0, y0, w, h)
        dx, dy = PIN_OFFSETS.get(num, (0, 0))
        if (dx, dy) != (0, 0):
            draw.line([(px, py), (px + dx, py + dy)], fill=RED, width=1)
            draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=RED)
            px, py = px + dx, py + dy
        r = 8
        draw.ellipse([px - r, py - r, px + r, py + r], fill=RED, outline=(255, 255, 255), width=1)
        t = str(num)
        twd = draw.textlength(t, font=f)
        draw.text((px - twd / 2, py - 5), t, font=f, fill=(255, 255, 255))
    # 13 = space star, top right
    sx, sy = x0 + w - 26, y0 + 16
    draw.polygon([(sx, sy - 9), (sx + 3, sy - 3), (sx + 9, sy - 3), (sx + 4, sy + 2),
                  (sx + 6, sy + 9), (sx, sy + 5), (sx - 6, sy + 9), (sx - 4, sy + 2),
                  (sx - 9, sy - 3), (sx - 3, sy - 3)], fill=GOLD, outline=INK)
    draw.text((sx + 12, sy - 6), "13", font=f, fill=INK)








# ---------------------------------------------------------------- render
def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    MX = 14  # side margin
    RX = W - MX

    # ---- masthead (v10: like the reference front page — red tagline on
    # top, big title, centered subtitle) ----
    y = 4
    t = "ONE DAY OF WORLD NEWS, ONE PICTURE"
    d.text(((W - tw(d, t, font(SANSB, 9))) / 2, y), t, font=font(SANSB, 9), fill=RED)
    y = 15
    t = "SUNDAY 22 NOVEMBER 2026"
    d.text(((W - tw(d, t, font(SERIFB, 40))) / 2, y), t, font=font(SERIFB, 40), fill=INK)
    y = 56
    t = "36 STORIES  ·  6 REGIONS  ·  EVERY ONE DATED SUNDAY 22 NOVEMBER 2026"
    d.text(((W - tw(d, t, font(SANSB, 12))) / 2, y), t, font=font(SANSB, 12), fill=INK)
    y = 72
    rule(d, MX, RX, y, INK, 2)
    rule(d, MX, RX, y + 3, INK, 1)

    # ---- THE DAY IN UTC ----
    y = 81
    d.rectangle([MX, y, RX, y + 38], fill=PAPER2, outline=INK, width=1)
    d.text((MX + 6, y + 2), "THE DAY IN UTC", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 7.0
    for i, (t, txt) in enumerate(UTC_STRIP):
        x = MX + 6 + i * col_w
        d.text((x, y + 12), t, font=font(SANSB, 11), fill=RED)
        para(d, x, y + 26, txt, font(SANS, 8), INK, col_w - 6, lh=9, max_lines=1)

    # ---- THE DAY IN NUMBERS ----
    y = 125
    d.rectangle([MX, y, RX, y + 46], fill=(255, 255, 255), outline=INK, width=1)
    d.text((MX + 6, y + 3), "THE DAY IN NUMBERS", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 6.0
    for i, (num, txt) in enumerate(NUMBERS):
        x = MX + 6 + i * col_w
        d.text((x, y + 15), num, font=font(SERIFB, 17), fill=INK)
        para(d, x, y + 33, txt, font(SANS, 8), GREY, col_w - 6, lh=9, max_lines=2)

    # ---- 3 big leads (v10: PHOTO on top, then kicker + headline + deck
    # below — like the reference front page) ----
    y = 177
    lead_h = 236
    col_w = (RX - MX - 12) / 3.0
    for i, (num, kick, head, deck, src, conf) in enumerate(LEADS):
        x = MX + i * (col_w + 6)
        # v5: soft drop shadow under the lead box (drawn first; the
        # opaque paper fill covers the overlap, only the fringe shows)
        _rect_shadow(img, x, y, x + col_w, y + lead_h)
        d.rectangle([x, y, x + col_w, y + lead_h], fill=PAPER, outline=INK, width=1)
        # photo: full column width, 124px tall, on top
        ph = _cover(num, int(col_w) - 2, 124, lead=True)
        img.paste(ph, (int(x) + 1, y + 1))
        d.rectangle([x + 1, y + 1, x + col_w - 1, y + 125], outline=INK, width=1)
        # kicker (red) + confidence badge, below the photo
        ky = y + 131
        d.text((x + 6, ky), f"#{num}  {kick}", font=font(SANSB, 9), fill=RED)
        badge(d, x + col_w - 62, ky - 1, conf)
        # headline (18pt so the longest one fits the column)
        d.text((x + 6, y + 146), head, font=font(SERIFB, 18), fill=INK)
        # deck, 3 lines max
        para(d, x + 6, y + 170, deck, font(SANS, 10), INK, col_w - 12, lh=12,
             max_lines=3)
        # source
        sy = y + lead_h - 16
        d.text((x + 6, sy + 2), src, font=font(SANS, 8), fill=GREY)

    # ---- 10 medium cards, 2 rows of 5 (v11: PHOTO BANNER on top, like
    # the top entries — full-width banner, then kicker + headline + deck
    # below; the tiny left thumbnail is gone) ----
    y = 419
    card_w = (RX - MX - 16) / 5.0
    card_h = 106
    for row in range(2):
        for col in range(5):
            m = MEDIUM[row * 5 + col]
            num, kick, head, deck, src, conf, _ic = m
            x = MX + col * (card_w + 4)
            yy = y + row * (card_h + 3)
            d.rectangle([x, yy, x + card_w, yy + card_h], fill=(255, 255, 255),
                        outline=LINE, width=1)
            # photo banner: full card width, 50px tall, on top
            ph = _cover(num, int(card_w) - 2, 50, lead=False)
            img.paste(ph, (int(x) + 1, yy + 1))
            d.rectangle([x + 1, yy + 1, x + card_w - 1, yy + 51], outline=LINE, width=1)
            # confidence badge over the banner's top-right corner
            badge(d, x + card_w - 62, yy + 3, conf)
            # kicker, headline (2 lines), deck (2 lines); per-card source
            # dropped in v11 — outlets are credited in the footer
            d.text((x + 5, yy + 54), f"{num}  {kick}", font=font(SANSB, 7), fill=RED)
            para(d, x + 5, yy + 64, head, font(SANSB, 10), INK, card_w - 10, lh=11,
                 max_lines=2)
            para(d, x + 5, yy + 86, deck, font(SANS, 8), INK, card_w - 10, lh=9,
                 max_lines=2)

    # ---- STORIES BY REGION (single 14px row: label + bar + legend) ----
    y = 640
    d.text((MX, y + 3), "STORIES BY REGION", font=font(SANSB, 9), fill=RED)
    bx = MX + 118
    total = sum(n for _, n, _ in REGIONS)
    legend = "  ·  ".join(f"{name} {n}" for name, n, _ in REGIONS)
    legend_w = int(tw(d, legend, font(SANS, 8)))
    bar_w = RX - bx - legend_w - 8
    x = bx
    for name, n, col in REGIONS:
        wseg = bar_w * n / total
        d.rectangle([x, y + 2, x + wseg - 1, y + 16], fill=col)
        x += wseg
    d.text((bx + bar_w + 8, y + 3), legend, font=font(SANS, 8), fill=INK)

    # ---- WHERE IT HAPPENED (v11: 112px strip — funds the taller medium
    # cards; Europe still reads, pins unchanged) ----
    y = 660
    d.text((MX, y), "WHERE IT HAPPENED  ·  PINS 1–13  (13 = IN ORBIT)",
           font=font(SANSB, 10), fill=INK)
    draw_world_map(img, d, MX, y + 15, RX - MX, 112)

    # ---- ALSO ON ----
    y = 793
    d.text((MX, y), "ALSO ON SUNDAY 22 NOVEMBER — 23 MORE STORIES",
           font=font(SANSB, 10), fill=INK)
    rule(d, MX, RX, y + 15, INK, 1)
    y = 813
    col_w = (RX - MX - 12) / 2.0
    row_h = 11
    f_head = font(SANS, 9)
    f_bold = font(SANSB, 9)
    f_src = font(SANS, 7)
    left = SMALL[:12]
    right = SMALL[12:]
    max_y = y
    for ci, group in enumerate((left, right)):
        x = MX + ci * (col_w + 12)
        yy = y
        for num, place, head, src in group:
            d.text((x, yy), f"{num}.", font=f_bold, fill=RED)
            prefix = f"{place} — "
            d.text((x + 18, yy), prefix, font=f_bold, fill=INK)
            px = x + 18 + tw(d, prefix, f_bold)
            src_w = tw(d, src, f_src) + 4
            avail = x + col_w - src_w - px
            # single line, truncate with ellipsis if it ever runs long
            txt = head
            while tw(d, txt, f_head) > avail and len(txt) > 10:
                txt = txt[:-4] + "…"
            d.text((px, yy), txt, font=f_head, fill=INK)
            d.text((x + col_w - src_w, yy), src, font=f_src, fill=GREY)
            yy += row_h
        max_y = max(max_y, yy)
    assert max_y <= 950, f"ALSO ON overflow: ends at y={max_y}"

    # ---- DATE CHECK + HOW SURE ----
    y = 949
    d.rectangle([MX, y, RX, y + 46], fill=(255, 255, 255), outline=RED, width=2)
    d.text((MX + 6, y + 2), "DATE CHECK — LEFT OUT AS OLDER NEWS",
           font=font(SANSB, 9), fill=RED)
    para(d, MX + 6, y + 11,
         "Shenzhen summit (19–20 Nov) · ICJ Rohingya ruling (19 Nov) · GTA VI $3.79bn "
         "(19–20 Nov) · Anthropic IPO $93.5bn (20 Nov) · 'El Chapo Isidro' arrested "
         "(20–21 Nov) · Akvan landfall (20 Nov) · Banda Sea M6.8 (21 Nov)",
         font(SANS, 8), INK, RX - MX - 12, lh=10, max_lines=1)
    d.text((MX + 6, y + 23),
           "NOT YET: ATP final (23 Nov) · BepiColombo separation (9–10 Dec)",
           font=font(SANSB, 8), fill=INK)
    d.text((MX + 6, y + 34), "HOW SURE ARE WE?  ",
           font=font(SANSB, 8), fill=INK)
    xx = MX + 6 + tw(d, "HOW SURE ARE WE?  ", font(SANSB, 8))
    d.text((xx, y + 34), "CONFIRMED = 2+ outlets · OFFICIAL = on the record · REPORTED = one outlet",
           font=font(SANS, 8), fill=GREY)

    # ---- footer ----
    y = 999
    rule(d, MX, RX, y, INK, 1)
    d.text((MX, y + 4),
           "Every story here happened, or was first reported, on Sunday 22 November 2026.",
           font=font(SANSB, 9), fill=INK)
    d.text((MX, y + 15),
           "Sources: AP, Reuters, AFP, BBC, USGS, ESA, IMD, UKMTO, NEMA, WHO. "
           "All photographs are AI-generated; the world map is "
           "original vector work.",
           font=font(SANS, 8), fill=GREY)
    # v6: very subtle paper grain over the whole page (last step, so it
    # touches everything equally and stays faint)
    _paper_grain(img)
    return img


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "entry.png")
    img = render()
    img.save(out, format="PNG", optimize=True)
    data = open(out, "rb").read()
    print(f"entry.png: {len(data)} bytes, {img.size[0]}x{img.size[1]}, "
          f"sha256 {hashlib.sha256(data).hexdigest()}")
    assert len(data) <= 1048576, "over 1 MiB"
    assert img.size[0] <= 1024 and img.size[1] <= 1024, "over 1024 px"
    return 0


if __name__ == "__main__":
    sys.exit(main())
