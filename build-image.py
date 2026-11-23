#!/usr/bin/env python3
"""news-image-20261122 — render the Sunday 22 November 2026 front page.

One image, 1024x1024, PIL only, fully deterministic (no network, no clock,
no unseeded randomness). Writes entry.png next to this script.
Layout follows the proven winner template: masthead -> UTC strip -> numbers
strip -> 3 big photo leads -> 33 photo cards in ONE unified 6x6 grid
(v12: every story gets a clear visual tile) -> region bar -> realistic
world map (v13: NASA Blue Marble raster) "WHERE IT HAPPENED" -> DATE
CHECK -> HOW SURE -> footer. 36 stories, 6 regions.
v14 "visual diperjelas lagi": grid tiles 162x70, banners 40px, headlines
9pt, all photos sharpened + more saturated, map pins bigger (r 8).
"""
import hashlib
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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
# v12: one photo per ALSO ON story (14-36), same photorealistic style.
SMALL_PHOTOS = {14: "also14-trump-eo.jpg", 15: "also15-fbi-hack.jpg",
                16: "also16-spacex-campus.jpg", 17: "also17-anthropic-ipo.jpg",
                18: "also18-lng.jpg", 19: "also19-argentina-risk.jpg",
                20: "also20-missile-debris.jpg", 21: "also21-parliament.jpg",
                22: "also22-eu.jpg", 23: "also23-blockade.jpg",
                24: "also24-bahrain-fire.jpg", 25: "also25-hormuz.jpg",
                26: "also26-gaza.jpg", 27: "also27-boat.jpg",
                28: "also28-khartoum.jpg", 29: "also29-migrant-boat.jpg",
                30: "also30-summit.jpg", 31: "also31-cyclone.jpg",
                32: "also32-beijing.jpg", 33: "also33-dhaka.jpg",
                34: "also34-xavier.jpg", 35: "also35-un-ai.jpg",
                36: "also36-minimoon.jpg"}
SMALL_FOCUS = {}  # default (0.5, 0.5) for every small photo
# Focus point of the center crop (fraction of source size). Lead 3's dome
# sits at the top of its frame, so bias the crop upward; med 12's subject
# stands on the right; med 9's house is right of centre; med 4's building
# and med 8's car sit left of centre.
LEAD_FOCUS = {1: (0.5, 0.55), 2: (0.5, 0.5), 3: (0.5, 0.30)}
MED_FOCUS = {4: (0.45, 0.5), 5: (0.5, 0.5), 6: (0.5, 0.5), 7: (0.5, 0.5),
             8: (0.45, 0.5), 9: (0.6, 0.5), 10: (0.5, 0.5), 11: (0.5, 0.5),
             12: (0.75, 0.5), 13: (0.5, 0.5)}
_photo_cache = {}


def _cover(num, w, h, lead=True, small=False):
    """Load a photo, center-crop it to the target aspect ratio around its
    focus point, and LANCZOS-resize to (w, h). Results are cached so each
    file is read once per run."""
    key = (num, w, h, lead, small)
    if key in _photo_cache:
        return _photo_cache[key]
    if small:
        fname = SMALL_PHOTOS[num]
        focus = SMALL_FOCUS.get(num, (0.5, 0.5))
    else:
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
    # v14: make every photo read clearly at contact-sheet scale — a
    # mild saturation + contrast lift and a light unsharp mask. All PIL
    # ops, fully deterministic; applied here so leads, mediums and grid
    # tiles all get it. The NASA map raster is pasted separately and is
    # left untouched.
    out = ImageEnhance.Color(out).enhance(1.14)
    out = ImageEnhance.Contrast(out).enhance(1.07)
    out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=3))
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
# v12: headlines shortened to fit the 8x3 photo grid (2 lines at 8pt in
# ~111px, ~40 chars max) — same facts, front-page headline style.
SMALL = [
    (14, "WASHINGTON", "Trump signs EO 14438 on contractors", "AP"),
    (15, "WASHINGTON", "Trump: FBI crime database hacked", "Reuters"),
    (16, "ARIZONA", "SpaceX $74bn AI campus stalls", "Fortune"),
    (17, "NEW YORK", "Anthropic IPO sparks Wall St row", "Reuters"),
    (18, "ARGENTINA", "Argentina approves $50bn LNG plan", "Reuters"),
    (19, "ARGENTINA", "Argentina risk hits 1,070 in 2026", "JPMorgan"),
    (20, "POLAND", "Kh-101 debris found in Poland", "Reuters"),
    (21, "LONDON", "Tories vow to scrap UK–EU deal", "Reuters"),
    (22, "BRUSSELS", "EU proposes €204bn savings plan", "Handelsblatt"),
    (23, "TEHRAN", "Trump dares Iran over port blockade", "AP"),
    (24, "SITRA, BAHRAIN", "Iran attack on Bahrain site: 2 hurt", "Reuters"),
    (25, "STRAIT OF HORMUZ", "Iran hits three tankers in Hormuz", "UKMTO"),
    (26, "GAZA CITY", "Strike on Gaza food van kills 3", "AP"),
    (27, "BAYELSA, NIGERIA", "Boat capsize toll rises to 26", "Reuters"),
    (28, "KHARTOUM", "Drones hit UN site in Khartoum", "OCHA"),
    (29, "ATLANTIC", "Boat sinks off Senegal: 39 dead", "Reuters"),
    (30, "OYO, CONGO", "Kenya, DR Congo restore full ties", "Reuters"),
    (31, "ODISHA, INDIA", "Akvan weakens; 300,000 moved", "IMD"),
    (32, "BEIJING", "China–Japan ties worsen over Taiwan", "Reuters"),
    (33, "DHAKA", "Deadly Dhaka protests over ex-leader", "Reuters"),
    (34, "COOK ISLANDS", "Cyclone Xavier weakens to Cat 1", "MetService"),
    (35, "GENEVA", "UN AI-weapons talks: no rules", "AFP"),
    (36, "ORBIT", "Earth gains a 'mini-moon', 2026 QQ8", "CNN"),
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
# v13: offsets retuned for the lat 75..-45 band (pins spread further
# apart vertically now) — 3 vs 7 collide (8px apart) and 1 vs 4 (14px).
PIN_OFFSETS = {3: (-14, 12), 4: (16, -10), 7: (14, -10)}


# ---------------------------------------------------------------- icons


# ---------------------------------------------------------------- maps
# World map: NASA Blue Marble Next Generation (public domain) raster,
# cropped to lat 75..-45 and committed as photos/world-map.jpg (2x the
# strip size). Pins use the same equirectangular projection, so they
# land on the real continents. The coastline polygons below are kept
# for reference but no longer drawn (v13: raster map replaces the
# flat vector map).
LAT_TOP, LAT_BOT = 75.0, -45.0


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


# v13: realistic satellite map — the NASA Blue Marble raster is pasted
# (2x strip size, LANCZOS down) and the pins sit on top of it. Each pin
# gets a dark halo so it reads on bright land (Sahara, ice) as well as
# on the dark sea; the leader line + true-spot dot are white for the
# same reason. The "13" label is white with a dark stroke because the
# top-right of the raster is dark ocean now.
_MAP_FILE = os.path.join(_PHOTO_DIR, "world-map.jpg")


def draw_world_map(img, draw, x0, y0, w, h, pin_r=7, pin_font=8):
    base = Image.open(_MAP_FILE).convert("RGB").resize((w, h), Image.LANCZOS)
    img.paste(base, (x0, y0))
    draw.rectangle([x0, y0, x0 + w, y0 + h], outline=INK, width=1)
    # pins 1-12
    f = font(SANSB, pin_font)
    for num, (lat, lon) in sorted(PINS.items()):
        if lat is None:
            continue
        px, py = world_xy(lat, lon, x0, y0, w, h)
        dx, dy = PIN_OFFSETS.get(num, (0, 0))
        if (dx, dy) != (0, 0):
            draw.line([(px, py), (px + dx, py + dy)], fill=(255, 255, 255), width=1)
            draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(255, 255, 255))
            px, py = px + dx, py + dy
        r = pin_r
        draw.ellipse([px - r - 2, py - r - 2, px + r + 2, py + r + 2],
                     fill=(20, 20, 20))
        draw.ellipse([px - r, py - r, px + r, py + r], fill=RED,
                     outline=(255, 255, 255), width=1)
        t = str(num)
        twd = draw.textlength(t, font=f)
        draw.text((px - twd / 2, py - 5), t, font=f, fill=(255, 255, 255))
    # 13 = space star, top right
    sx, sy = x0 + w - 26, y0 + 16
    draw.polygon([(sx, sy - 9), (sx + 3, sy - 3), (sx + 9, sy - 3), (sx + 4, sy + 2),
                  (sx + 6, sy + 9), (sx, sy + 5), (sx - 6, sy + 9), (sx - 4, sy + 2),
                  (sx - 9, sy - 3), (sx - 3, sy - 3)], fill=GOLD, outline=INK)
    draw.text((sx + 12, sy - 6), "13", font=f, fill=(255, 255, 255),
              stroke_width=1, stroke_fill=(20, 20, 20))








# ---------------------------------------------------------------- render
def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    MX = 14  # side margin
    RX = W - MX

    # ---- masthead (v10: like the reference front page — red tagline on
    # top, big title, centered subtitle; v14: title 36pt + subtitle 11pt
    # to fund taller grid banners) ----
    y = 3
    t = "ONE DAY OF WORLD NEWS, ONE PICTURE"
    d.text(((W - tw(d, t, font(SANSB, 9))) / 2, y), t, font=font(SANSB, 9), fill=RED)
    y = 12
    t = "SUNDAY 22 NOVEMBER 2026"
    d.text(((W - tw(d, t, font(SERIFB, 36))) / 2, y), t, font=font(SERIFB, 36), fill=INK)
    y = 49
    t = "36 STORIES  ·  6 REGIONS  ·  EVERY ONE DATED SUNDAY 22 NOVEMBER 2026"
    d.text(((W - tw(d, t, font(SANSB, 11))) / 2, y), t, font=font(SANSB, 11), fill=INK)
    y = 63
    rule(d, MX, RX, y, INK, 2)
    rule(d, MX, RX, y + 3, INK, 1)

    # ---- THE DAY IN UTC (v14: 30px) ----
    y = 70
    d.rectangle([MX, y, RX, y + 30], fill=PAPER2, outline=INK, width=1)
    d.text((MX + 6, y + 1), "THE DAY IN UTC", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 7.0
    for i, (t, txt) in enumerate(UTC_STRIP):
        x = MX + 6 + i * col_w
        d.text((x, y + 10), t, font=font(SANSB, 11), fill=RED)
        para(d, x, y + 19, txt, font(SANS, 8), INK, col_w - 6, lh=9, max_lines=1)

    # ---- THE DAY IN NUMBERS (v14: 34px) ----
    y = 104
    d.rectangle([MX, y, RX, y + 34], fill=(255, 255, 255), outline=INK, width=1)
    d.text((MX + 6, y + 2), "THE DAY IN NUMBERS", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 6.0
    for i, (num, txt) in enumerate(NUMBERS):
        x = MX + 6 + i * col_w
        d.text((x, y + 12), num, font=font(SERIFB, 16), fill=INK)
        para(d, x, y + 24, txt, font(SANS, 8), GREY, col_w - 6, lh=9, max_lines=2)

    # ---- 3 big leads (v10: PHOTO on top, then kicker + headline + deck
    # below — like the reference front page; v14: 192px tall, photo still
    # 92px, deck line-height 11 to fund the taller grid banners; photos
    # get the v14 sharpen/saturation lift via _cover) ----
    y = 148
    lead_h = 192
    col_w = (RX - MX - 12) / 3.0
    for i, (num, kick, head, deck, src, conf) in enumerate(LEADS):
        x = MX + i * (col_w + 6)
        # v5: soft drop shadow under the lead box (drawn first; the
        # opaque paper fill covers the overlap, only the fringe shows)
        _rect_shadow(img, x, y, x + col_w, y + lead_h)
        d.rectangle([x, y, x + col_w, y + lead_h], fill=PAPER, outline=INK, width=1)
        # photo: full column width, 92px tall, on top
        ph = _cover(num, int(col_w) - 2, 92, lead=True)
        img.paste(ph, (int(x) + 1, y + 1))
        d.rectangle([x + 1, y + 1, x + col_w - 1, y + 93], outline=INK, width=1)
        # kicker (red) + confidence badge, below the photo
        ky = y + 99
        d.text((x + 6, ky), f"#{num}  {kick}", font=font(SANSB, 9), fill=RED)
        badge(d, x + col_w - 62, ky - 1, conf)
        # headline (18pt so the longest one fits the column)
        d.text((x + 6, y + 112), head, font=font(SERIFB, 18), fill=INK)
        # deck, 3 lines max
        para(d, x + 6, y + 136, deck, font(SANS, 10), INK, col_w - 12, lh=11,
             max_lines=3)
        # source
        sy = y + lead_h - 16
        d.text((x + 6, sy + 2), src, font=font(SANS, 8), fill=GREY)

    # ---- THE REST OF THE DAY (v12: ONE unified photo grid — stories
    # 4-36, 6 cols x 6 rows; every story gets a clear photo tile: banner
    # + kicker + 2-line headline. v14 "visual diperjelas lagi": tiles
    # 162x70 (was 162x62), banner 40px (was 35), headline 9pt (was 8),
    # number badge 8pt, photos sharpened + more saturated via _cover.
    # Funded by small trims everywhere else (masthead, strips, leads,
    # gaps, DATE CHECK) — map stays 120px, lead photos stay 92px) ----
    y = 346
    d.text((MX, y), "MORE STORIES — 33 MORE, EACH WITH A PHOTO",
           font=font(SANSB, 10), fill=INK)
    rule(d, MX, RX, y + 13, INK, 1)
    y = 364
    GRID = [(num, kick, head, False)
            for num, kick, head, _d, _s, _c, _i in MEDIUM] + \
           [(num, place, head, True) for num, place, head, _s in SMALL]
    card_w = (RX - MX - 5 * 4) / 6.0
    card_h = 70
    for idx, (num, kick, head, small) in enumerate(GRID):
        row, col = divmod(idx, 6)
        x = MX + col * (card_w + 4)
        yy = y + row * (card_h + 2)
        d.rectangle([x, yy, x + card_w, yy + card_h], fill=(255, 255, 255),
                    outline=LINE, width=1)
        # photo banner: full card width, 40px tall, on top
        ph = _cover(num, int(card_w) - 2, 40, lead=False, small=small)
        img.paste(ph, (int(x) + 1, yy + 1))
        d.rectangle([x + 1, yy + 1, x + card_w - 1, yy + 41], outline=LINE, width=1)
        # story number badge over the banner's top-left corner
        fnum = font(SANSB, 8)
        ntxt = str(num)
        nw = int(d.textlength(ntxt, font=fnum)) + 6
        d.rounded_rectangle([x + 2, yy + 2, x + 2 + nw, yy + 13], radius=2, fill=RED)
        d.text((x + 5, yy + 3), ntxt, font=fnum, fill=(255, 255, 255))
        # kicker + headline (2 lines); deck dropped in v12 for clarity
        d.text((x + 5, yy + 42), kick, font=font(SANSB, 7), fill=RED)
        para(d, x + 5, yy + 50, head, font(SANS, 9), INK, card_w - 10, lh=9,
             max_lines=2)
    assert y + 5 * (card_h + 2) + card_h <= 800, "grid overflow"

    # ---- STORIES BY REGION (single 16px row: label + bar + legend) ----
    y = 800
    d.text((MX, y + 2), "STORIES BY REGION", font=font(SANSB, 9), fill=RED)
    bx = MX + 118
    total = sum(n for _, n, _ in REGIONS)
    legend = "  ·  ".join(f"{name} {n}" for name, n, _ in REGIONS)
    legend_w = int(tw(d, legend, font(SANS, 8)))
    bar_w = RX - bx - legend_w - 8
    x = bx
    for name, n, col in REGIONS:
        wseg = bar_w * n / total
        d.rectangle([x, y + 1, x + wseg - 1, y + 15], fill=col)
        x += wseg
    d.text((bx + bar_w + 8, y + 2), legend, font=font(SANS, 8), fill=INK)

    # ---- WHERE IT HAPPENED (v13: 120px — the map is a real satellite
    # image now, NASA Blue Marble, so it gets its height back; pins sit
    # on the real continents with a dark halo. v14: pins bigger (r 8,
    # font 9) so they read clearer at a glance) ----
    y = 820
    d.text((MX, y), "WHERE IT HAPPENED  ·  PINS 1–13  (13 = IN ORBIT)",
           font=font(SANSB, 10), fill=INK)
    draw_world_map(img, d, MX, y + 13, RX - MX, 120, pin_r=8, pin_font=9)

    # ---- DATE CHECK + HOW SURE (v14: 36px — same content, tighter) ----
    y = 959
    d.rectangle([MX, y, RX, y + 36], fill=(255, 255, 255), outline=RED, width=2)
    d.text((MX + 6, y + 1), "DATE CHECK — LEFT OUT AS OLDER NEWS",
           font=font(SANSB, 9), fill=RED)
    para(d, MX + 6, y + 9,
         "Shenzhen summit (19–20 Nov) · ICJ Rohingya ruling (19 Nov) · GTA VI $3.79bn "
         "(19–20 Nov) · Anthropic IPO $93.5bn (20 Nov) · 'El Chapo Isidro' arrested "
         "(20–21 Nov) · Akvan landfall (20 Nov) · Banda Sea M6.8 (21 Nov)",
         font(SANS, 8), INK, RX - MX - 12, lh=9, max_lines=1)
    d.text((MX + 6, y + 18),
           "NOT YET: ATP final (23 Nov) · BepiColombo separation (9–10 Dec)",
           font=font(SANSB, 8), fill=INK)
    d.text((MX + 6, y + 26), "HOW SURE ARE WE?  ",
           font=font(SANSB, 8), fill=INK)
    xx = MX + 6 + tw(d, "HOW SURE ARE WE?  ", font(SANSB, 8))
    d.text((xx, y + 26), "CONFIRMED = 2+ outlets · OFFICIAL = on the record · REPORTED = one outlet",
           font=font(SANS, 8), fill=GREY)

    # ---- footer ----
    y = 999
    rule(d, MX, RX, y, INK, 1)
    d.text((MX, y + 4),
           "Every story here happened, or was first reported, on Sunday 22 November 2026.",
           font=font(SANSB, 9), fill=INK)
    d.text((MX, y + 15),
           "Sources: AP, Reuters, AFP, BBC, USGS, ESA, IMD, UKMTO, NEMA, WHO. "
           "All photographs are AI-generated; the world map is NASA Blue "
           "Marble Next Generation (public domain).",
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
