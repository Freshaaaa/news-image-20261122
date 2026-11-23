#!/usr/bin/env python3
"""news-image-20261122 — render the Sunday 22 November 2026 front page.

One image, 1024x1024, PIL only, fully deterministic (no network, no clock,
no unseeded randomness). Writes entry.png next to this script.
Layout follows the proven winner template: masthead -> UTC strip -> numbers
strip -> 3 big illustrated leads -> 10 medium icon cards -> region bar ->
world map "WHERE IT HAPPENED" -> "ALSO ON" 23 small stories -> DATE CHECK
-> HOW SURE -> footer. 36 stories, 9 regions, 19 fields.
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
def _poly_gradient(img, pts, c0, c1, horizontal=False):
    """Fill polygon `pts` (absolute image coords) with a subtle gradient
    c0 -> c1 (top->bottom, or left->right if horizontal)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)), int(min(ys))
    x1, y1 = int(max(xs)), int(max(ys))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    if horizontal:
        for j in range(w):
            t = j / max(1, w - 1)
            c = tuple(int(round(c0[i] + (c1[i] - c0[i]) * t)) for i in range(3))
            gd.line([(j, 0), (j, h - 1)], fill=c)
    else:
        for j in range(h):
            t = j / max(1, h - 1)
            c = tuple(int(round(c0[i] + (c1[i] - c0[i]) * t)) for i in range(3))
            gd.line([(0, j), (w - 1, j)], fill=c)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
    img.paste(grad, (x0, y0), mask)


def _rect_gradient(img, x0, y0, w, h, top, bottom):
    """Vertical gradient over a rectangle (top -> bottom)."""
    x0, y0, w, h = int(x0), int(y0), int(w), int(h)
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for j in range(h):
        t = j / max(1, h - 1)
        c = tuple(int(round(top[i] + (bottom[i] - top[i]) * t)) for i in range(3))
        gd.line([(0, j), (w - 1, j)], fill=c)
    img.paste(grad, (x0, y0))


def _soft_shadow(img, pts, offset=(3, 5), blur=5, alpha=55):
    """Soft drop shadow of a polygon: black shape offset down-right,
    blurred, composited at low alpha. Draw BEFORE the shape itself so
    the shape covers the shadow where they overlap."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.polygon([(x + offset[0], y + offset[1]) for x, y in pts],
               fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base = img.convert("RGBA")
    out = Image.alpha_composite(base, layer)
    img.paste(out.convert("RGB"), (0, 0))


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


def _flame(draw, cx, base_y, tip_y, half_w, color, seed):
    """One flame tongue: a wavy teardrop from base_y up to tip_y,
    centred at cx, half-width half_w at the base. Edge points are
    jittered (seeded) so the tongue reads as a flame, not a smooth
    blob. Layered tongues (red -> orange -> yellow) replace the flat
    yellow ellipse of v6."""
    rng = random.Random(seed)
    h = base_y - tip_y
    pts = [
        (cx - half_w, base_y),
        (cx - half_w - 2, base_y - 0.35 * h),
        (cx - half_w * 0.55, base_y - 0.65 * h),
        (cx - 2, base_y - 0.85 * h),
        (cx, tip_y),
        (cx + 2, base_y - 0.85 * h),
        (cx + half_w * 0.55, base_y - 0.65 * h),
        (cx + half_w + 2, base_y - 0.35 * h),
        (cx + half_w, base_y),
    ]
    pts = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
           for x, y in pts]
    draw.polygon(pts, fill=color)


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
    ("−3.7%", "S&P 500 in one day"),
    ("M6.7", "Peru earthquake"),
    ("26", "killed as a boat capsizes in Nigeria"),
    ("93,000", "without power after the Peru quake"),
    ("50", "points for Wembanyama"),
]

REGIONS = [
    ("Europe", 7, (178, 28, 28)), ("N. America", 7, (30, 64, 140)),
    ("Latin America", 4, (34, 110, 60)), ("Middle East", 5, (166, 110, 10)),
    ("Africa", 5, (120, 72, 20)), ("Asia", 4, (140, 40, 120)),
    ("Oceania", 1, (20, 120, 130)), ("Global", 3, (90, 86, 76)),
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
def icon(draw, kind, cx, cy, s, col=INK):
    """Mini-scene (v9): a small detailed illustration centred at
    (cx, cy), size s (~40px) — a few BIG, THICK elements, because
    small details do not read at 300px. Everything stays inside
    cx-19..cx+19, cy-21..cy+24 so it never touches the kicker above,
    the headline/deck to the right, or the source line below."""
    if kind == "blast":
        # --- damaged apartment block: two towers, broken roof,
        # cracked windows, smoke, a small drone overhead
        # left tower (taller, broken jagged top)
        draw.polygon([(cx - 18, cy - 2), (cx - 14, cy - 9), (cx - 10, cy - 4),
                      (cx - 6, cy - 11), (cx - 2, cy - 3), (cx - 2, cy + 20),
                      (cx - 18, cy + 20)], fill=(70, 70, 70), outline=INK)
        # right tower (shorter, flat roof)
        draw.rectangle([cx + 2, cy + 6, cx + 18, cy + 20], fill=(110, 110, 110),
                       outline=INK)
        # windows: lit (yellow) and broken (black)
        for wx, wy, lit in [(-15, 0, True), (-8, 0, False), (-15, 8, False),
                            (-8, 8, True), (-15, 15, True), (-8, 15, False),
                            (5, 10, True), (12, 10, False), (5, 16, False),
                            (12, 16, True)]:
            c = (240, 180, 40) if lit else (20, 20, 20)
            draw.rectangle([cx + wx, cy + wy, cx + wx + 4, cy + wy + 5], fill=c)
        # crack down the left tower face
        draw.line([(cx - 12, cy - 4), (cx - 9, cy + 4), (cx - 13, cy + 10),
                   (cx - 10, cy + 18)], fill=RED, width=2)
        # smoke puffs from the broken roof
        draw.ellipse([cx - 14, cy - 18, cx - 4, cy - 10], fill=(150, 145, 135))
        draw.ellipse([cx - 8, cy - 20, cx + 1, cy - 13], fill=(172, 167, 157))
        # drone overhead, top right
        draw.rectangle([cx + 11, cy - 17, cx + 17, cy - 14], fill=INK)
        draw.line([(cx + 8, cy - 18), (cx + 20, cy - 18)], fill=INK, width=2)
        draw.line([(cx + 8, cy - 13), (cx + 20, cy - 13)], fill=INK, width=2)
        draw.line([(cx + 14, cy - 13), (cx + 14, cy - 10)], fill=RED, width=2)
        # ground line
        draw.line([(cx - 19, cy + 20), (cx + 19, cy + 20)], fill=INK, width=2)
    elif kind == "ship":
        # --- burning ship towed by a tug: hull with pointed bow,
        # superstructure, layered fire + smoke, tow line to a tug
        # sea
        for wy in (cy + 17, cy + 20):
            draw.line([(cx - 19, wy), (cx - 8, wy - 2), (cx + 2, wy),
                       (cx + 12, wy - 2), (cx + 19, wy)], fill=BLUE2, width=1)
        # smoke above the fire
        draw.ellipse([cx - 12, cy - 20, cx - 2, cy - 12], fill=(150, 145, 135))
        draw.ellipse([cx - 4, cy - 20, cx + 6, cy - 13], fill=(172, 167, 157))
        # superstructure + funnel (drawn first; flames sit on top)
        draw.rectangle([cx - 8, cy - 2, cx + 2, cy + 6], fill=(90, 90, 90),
                       outline=INK, width=1)
        draw.rectangle([cx - 6, cy - 6, cx - 2, cy - 2], fill=(60, 60, 60))
        # hull: pointed bow right, flat stern left
        draw.polygon([(cx - 18, cy + 6), (cx + 8, cy + 6), (cx + 14, cy + 10),
                      (cx + 8, cy + 14), (cx - 16, cy + 14)], fill=INK)
        draw.line([(cx - 18, cy + 6), (cx + 8, cy + 6)], fill=(255, 255, 255),
                  width=2)
        # portholes
        for px in (-12, -4, 4):
            draw.ellipse([cx + px - 2, cy + 9, cx + px + 2, cy + 13],
                         fill=(235, 235, 228))
        # layered fire over the superstructure
        _flame(draw, cx - 4, cy - 2, cy - 16, 6, (215, 50, 25), 601)
        _flame(draw, cx - 2, cy - 2, cy - 13, 5, (248, 140, 40), 602)
        _flame(draw, cx - 1, cy - 2, cy - 10, 3, (255, 210, 80), 603)
        # tow line from the stern down to the tug
        draw.line([(cx - 17, cy + 8), (cx - 13, cy + 16)], fill=(90, 90, 90),
                  width=2)
        # tug, bottom left
        draw.polygon([(cx - 19, cy + 18), (cx - 8, cy + 18), (cx - 10, cy + 22),
                      (cx - 17, cy + 22)], fill=(70, 70, 70))
        draw.rectangle([cx - 16, cy + 14, cx - 11, cy + 18], fill=(110, 110, 110),
                       outline=INK)
    elif kind == "missile":
        # --- missile battery: launcher truck + 3 missiles climbing
        # away on smoke trails
        # launcher truck, bottom left
        draw.rectangle([cx - 18, cy + 13, cx - 2, cy + 19], fill=(70, 70, 70),
                       outline=INK)
        draw.ellipse([cx - 15, cy + 19, cx - 11, cy + 23], fill=INK)
        draw.ellipse([cx - 7, cy + 19, cx - 3, cy + 23], fill=INK)
        # angled launch rail
        draw.line([(cx - 14, cy + 13), (cx - 6, cy - 2)], fill=INK, width=3)
        # 3 missiles climbing at different heights, each on a trail
        for ox, oy in [(-8, -8), (2, -12), (11, -5)]:
            mx, my = cx + ox, cy + oy
            # smoke trail curving down from the tail
            draw.line([(mx - 2, my + 8), (mx - 4, my + 14), (mx - 2, my + 20)],
                      fill=(190, 185, 175), width=3)
            # flame at the tail
            draw.polygon([(mx - 3, my + 7), (mx + 3, my + 7), (mx, my + 12)],
                         fill=(248, 140, 40))
            # body + nose + fins
            draw.polygon([(mx - 2, my + 7), (mx + 2, my + 7), (mx + 2, my - 4),
                          (mx, my - 8), (mx - 2, my - 4)], fill=INK)
            draw.polygon([(mx - 2, my + 5), (mx - 5, my + 9), (mx - 2, my + 7)],
                         fill=RED)
            draw.polygon([(mx + 2, my + 5), (mx + 5, my + 9), (mx + 2, my + 7)],
                         fill=RED)
    elif kind == "chart":
        # --- falling market: descending red candlesticks under a
        # thick red down-trend line with a big arrowhead
        # axes
        draw.line([(cx - 18, cy - 14), (cx - 18, cy + 18)], fill=GREY, width=2)
        draw.line([(cx - 18, cy + 18), (cx + 18, cy + 18)], fill=GREY, width=2)
        # 4 descending candlesticks (red bodies + wicks)
        for bx, top, bot in [(-14, -8, 0), (-6, -4, 4), (2, 0, 8), (10, 4, 12)]:
            draw.line([(cx + bx + 2, cy + top - 3), (cx + bx + 2, cy + bot + 3)],
                      fill=INK, width=1)
            draw.rectangle([cx + bx, cy + top, cx + bx + 5, cy + bot],
                           fill=RED, outline=INK)
        # thick red trend line over the candle tops
        pts = [(cx - 16, cy - 10), (cx - 8, cy - 6), (cx, cy - 1),
               (cx + 8, cy + 4), (cx + 15, cy + 10)]
        pts = _jitter_pts(pts, 1.0, 601)
        draw.line(pts, fill=RED, width=3, joint="curve")
        # big down arrowhead at the end of the trend line
        draw.polygon([(cx + 17, cy + 13), (cx + 9, cy + 7), (cx + 12, cy + 16)],
                     fill=RED)
    elif kind == "flag":
        # --- F1 car at speed under a checkered flag
        # checkered flag, top right: pole + 3x2 checker panel
        draw.line([(cx + 16, cy - 20), (cx + 16, cy - 2)], fill=INK, width=2)
        for r in range(2):
            for c in range(3):
                colr = INK if (r + c) % 2 == 0 else (255, 255, 255)
                draw.rectangle([cx + 4 + c * 4, cy - 20 + r * 4,
                                cx + 8 + c * 4, cy - 16 + r * 4], fill=colr)
        draw.rectangle([cx + 4, cy - 20, cx + 16, cy - 12], outline=INK)
        # track
        draw.line([(cx - 19, cy + 19), (cx + 19, cy + 19)], fill=GREY, width=2)
        # F1 car, side profile facing right: low red body, big rear
        # wing, nose + front wing, two fat wheels, driver helmet
        draw.polygon([(cx - 18, cy + 8), (cx - 10, cy + 6), (cx + 2, cy + 6),
                      (cx + 10, cy + 9), (cx + 14, cy + 12), (cx + 14, cy + 14),
                      (cx - 18, cy + 14)], fill=RED, outline=INK)
        # rear wing
        draw.rectangle([cx - 18, cy - 1, cx - 15, cy + 8], fill=INK)
        draw.rectangle([cx - 19, cy - 1, cx - 13, cy + 1], fill=INK)
        # front wing
        draw.rectangle([cx + 12, cy + 12, cx + 18, cy + 15], fill=INK)
        # driver helmet
        draw.ellipse([cx - 4, cy + 1, cx + 1, cy + 6], fill=(255, 255, 255),
                     outline=INK)
        # wheels: fat black tyres with grey hubs
        for wx in (-10, 8):
            draw.ellipse([cx + wx - 5, cy + 11, cx + wx + 5, cy + 21],
                         fill=INK)
            draw.ellipse([cx + wx - 2, cy + 14, cx + wx + 2, cy + 18],
                         fill=(180, 180, 180))
    elif kind == "quake":
        # --- cracked earth: a leaning tower over a split in the
        # ground, a smaller cracked building, dust at the base
        # leaning tower (leans right): parallelogram
        draw.polygon([(cx - 16, cy + 18), (cx - 12, cy - 8), (cx + 0, cy - 6),
                      (cx - 4, cy + 18)], fill=(90, 90, 90), outline=INK)
        # windows on the tower
        for wx, wy in [(-13, -4), (-12, 3), (-11, 10)]:
            draw.rectangle([cx + wx, cy + wy, cx + wx + 3, cy + wy + 3],
                           fill=(240, 180, 40))
        # crack down the tower face
        draw.line([(cx - 9, cy - 7), (cx - 11, cy + 2), (cx - 8, cy + 9),
                   (cx - 10, cy + 17)], fill=RED, width=2)
        # smaller building, right, cracked
        draw.rectangle([cx + 2, cy + 2, cx + 18, cy + 18], fill=(130, 130, 130),
                       outline=INK)
        draw.line([(cx + 8, cy + 2), (cx + 6, cy + 9), (cx + 10, cy + 14),
                   (cx + 8, cy + 18)], fill=INK, width=2)
        for wx, wy in [(5, 6), (12, 6), (5, 12), (12, 12)]:
            draw.rectangle([cx + wx, cy + wy, cx + wx + 3, cy + wy + 3],
                           fill=(20, 20, 20))
        # ground split: the ground line breaks open in the middle
        draw.line([(cx - 19, cy + 18), (cx - 8, cy + 18)], fill=INK, width=2)
        draw.line([(cx + 8, cy + 18), (cx + 19, cy + 18)], fill=INK, width=2)
        draw.polygon([(cx - 8, cy + 18), (cx - 2, cy + 24), (cx + 8, cy + 18)],
                     fill=(60, 60, 60))
        # dust puffs at the tower base
        draw.ellipse([cx - 18, cy + 14, cx - 10, cy + 19], fill=(172, 167, 157))
        draw.ellipse([cx + 2, cy + 15, cx + 9, cy + 19], fill=(150, 145, 135))
    elif kind == "storm":
        # --- big dark supercell: two overlapping storm clouds, a
        # bold lightning bolt, rain slanting below
        draw.ellipse([cx - 19, cy - 18, cx + 1, cy - 2], fill=(90, 90, 90))
        draw.ellipse([cx - 5, cy - 20, cx + 19, cy - 4], fill=INK)
        draw.ellipse([cx - 14, cy - 8, cx + 6, cy - 2], fill=(130, 130, 130))
        # lightning bolt, bold yellow zigzag from the cloud base
        draw.polygon([(cx + 6, cy - 4), (cx + 0, cy + 6), (cx + 4, cy + 6),
                      (cx - 2, cy + 18), (cx + 2, cy + 18), (cx + 6, cy + 8),
                      (cx + 2, cy + 8), (cx + 10, cy - 4)], fill=(240, 180, 40))
        # rain, slanting under the cloud's left half
        for rx in (-16, -10, -4):
            draw.line([(cx + rx, cy + 2), (cx + rx - 3, cy + 12)], fill=BLUE2,
                      width=2)
            draw.line([(cx + rx, cy + 12), (cx + rx - 3, cy + 20)], fill=BLUE2,
                      width=2)
    elif kind == "fire":
        # --- candy factory on fire: hall with a sawtooth roof, a tall
        # chimney, flames from the roof and a window, smoke overhead
        # chimney, right
        draw.rectangle([cx + 10, cy - 12, cx + 16, cy + 20], fill=(70, 70, 70),
                       outline=INK)
        draw.rectangle([cx + 10, cy - 12, cx + 16, cy - 9], fill=(150, 150, 150))
        # smoke from the chimney
        draw.ellipse([cx + 8, cy - 20, cx + 18, cy - 13], fill=(150, 145, 135))
        draw.ellipse([cx + 12, cy - 20, cx + 19, cy - 13], fill=(172, 167, 157))
        # factory hall with sawtooth roof
        draw.polygon([(cx - 19, cy + 20), (cx - 19, cy + 2), (cx - 13, cy - 4),
                      (cx - 7, cy + 2), (cx - 1, cy - 4), (cx + 5, cy + 2),
                      (cx + 10, cy + 2), (cx + 10, cy + 20)], fill=(110, 110, 110),
                     outline=INK)
        # windows (the middle one burns)
        for wx in (-16, -8, 0):
            draw.rectangle([cx + wx, cy + 8, cx + wx + 4, cy + 13],
                           fill=(20, 20, 20))
        # flames: from the roof and from the middle window
        _flame(draw, cx - 10, cy + 2, cy - 12, 5, (215, 50, 25), 611)
        _flame(draw, cx - 10, cy + 2, cy - 9, 4, (248, 140, 40), 612)
        _flame(draw, cx - 6, cy + 13, cy + 2, 4, (248, 140, 40), 613)
        _flame(draw, cx - 6, cy + 13, cy + 5, 3, (255, 210, 80), 614)
        # ground line
        draw.line([(cx - 19, cy + 20), (cx + 19, cy + 20)], fill=INK, width=2)
    elif kind == "virus":
        # --- Ebola virus, detailed: spiked body with inner texture,
        # plus a small red-cross medical badge
        vx, vy, r = cx - 5, cy + 4, 10
        # spikes with knobs (8 directions)
        for a in range(0, 360, 45):
            rad = math.radians(a)
            x1 = vx + (r - 1) * math.cos(rad)
            y1 = vy + (r - 1) * math.sin(rad)
            x2 = vx + (r + 5) * math.cos(rad)
            y2 = vy + (r + 5) * math.sin(rad)
            draw.line([(x1, y1), (x2, y2)], fill=RED, width=3)
            draw.ellipse([x2 - 2, y2 - 2, x2 + 2, y2 + 2], fill=RED)
        draw.ellipse([vx - r, vy - r, vx + r, vy + r], fill=RED, outline=INK)
        # inner texture: darker dots + a lighter highlight
        for dx, dy in [(-4, -3), (3, -4), (0, 4), (4, 2)]:
            draw.ellipse([vx + dx - 2, vy + dy - 2, vx + dx + 2, vy + dy + 2],
                         fill=(140, 20, 20))
        draw.ellipse([vx - 6, vy - 7, vx - 2, vy - 3], fill=(255, 120, 120))
        # red-cross badge, top right
        draw.rectangle([cx + 11, cy - 20, cx + 20, cy - 11], fill=(255, 255, 255),
                       outline=INK)
        draw.rectangle([cx + 14, cy - 18, cx + 17, cy - 13], fill=RED)
        draw.rectangle([cx + 12, cy - 16, cx + 19, cy - 15], fill=RED)
    elif kind == "planet":
        # --- Mercury, cratered, with a small probe on solar panels
        # (no ring — Mercury has none) and two stars
        draw.ellipse([cx - 16, cy - 9, cx + 8, cy + 15], fill=(200, 170, 120),
                     outline=INK, width=2)
        # craters: darker rings with a lighter inner floor
        for kx, ky, kr in [(-9, -3, 3), (-1, 6, 3), (-7, 7, 2)]:
            draw.ellipse([cx + kx - kr, cy + ky - kr, cx + kx + kr, cy + ky + kr],
                         fill=(165, 135, 90), outline=(150, 120, 80))
            draw.ellipse([cx + kx - kr + 1, cy + ky - kr + 1,
                          cx + kx + kr - 1, cy + ky + kr - 1],
                         fill=(185, 155, 105))
        # highlight arc, upper left
        draw.arc([cx - 14, cy - 7, cx + 6, cy + 13], start=140, end=250,
                 fill=(235, 215, 175), width=2)
        # probe above the planet: body + two solar panels
        draw.rectangle([cx + 2, cy - 20, cx + 8, cy - 15], fill=(110, 110, 110),
                       outline=INK)
        draw.rectangle([cx - 8, cy - 19, cx + 1, cy - 16], fill=BLUE2,
                       outline=INK)
        draw.rectangle([cx + 9, cy - 19, cx + 18, cy - 16], fill=BLUE2,
                       outline=INK)
        draw.ellipse([cx + 4, cy - 21, cx + 6, cy - 19], fill=RED)
        # stars
        for sx, sy in [(-17, -16), (17, 10)]:
            draw.ellipse([cx + sx - 1, cy + sy - 1, cx + sx + 1, cy + sy + 1],
                         fill=GOLD)


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


def draw_turkiye(img, draw, x0, y0, w, h):
    """Türkiye scene (130px box): a bigger, warmer map with Istanbul +
    Ankara marked, an OVERTIME clock, the Antalya pin with its glow, and
    a big rotated red "NO DEAL" stamp across the map — the scene reads as
    "a conference that failed", not just a map. The draft-text box stays
    as a single line at the bottom. Everything stays inside (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    # v7: faint watercolor wash over the sea so the background is not a
    # flat screen fill (drawn before the land so the map covers it)
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (190, 205, 220), alpha=20, seed=216)
    poly = [(0.03, 0.36), (0.04, 0.31), (0.05, 0.26), (0.08, 0.19), (0.15, 0.16),
            (0.25, 0.15), (0.30, 0.19), (0.35, 0.17), (0.45, 0.15), (0.55, 0.17),
            (0.60, 0.20), (0.65, 0.15), (0.75, 0.17), (0.85, 0.19), (0.89, 0.22),
            (0.93, 0.23), (0.96, 0.29), (0.95, 0.36), (0.90, 0.44), (0.86, 0.47),
            (0.82, 0.50), (0.74, 0.54), (0.66, 0.58), (0.58, 0.54), (0.50, 0.50),
            (0.42, 0.48), (0.34, 0.46), (0.26, 0.44), (0.18, 0.42),
            (0.10, 0.40), (0.06, 0.38), (0.08, 0.34), (0.04, 0.32)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    # v7: wavier coastline (seeded jitter, 3.5px — up from 2.5), a
    # watercolor wash over the land, and a pen-stroke outline instead
    # of the ruler line
    pts = _jitter_pts(pts, 3.5, 201)
    # v5: soft shadow under the map (drawn first, land covers the
    # overlap, only the fringe shows on the sea) + subtle vertical
    # gradient on the land (brighter at the top, a touch darker below)
    # + very subtle dot texture — warmer, darker land so the map reads
    # as a shape, not a pale silhouette
    _soft_shadow(img, pts, offset=(3, 5), blur=5, alpha=55)
    _poly_gradient(img, pts, (212, 184, 136), (198, 166, 112))
    _watercolor(img, pts, (186, 156, 106), alpha=40, seed=211)
    _hand_outline(draw, pts, INK, seed=221)
    _stipple(draw, pts, (186, 156, 106), step=9)
    # v9: small wave marks in the seas so the water reads as water,
    # not a flat fill — kept clear of the labels and the clock
    for wx in (0.58, 0.70):
        x, y = x0 + wx * w, y0 + 9
        draw.line([(x, y), (x + 4, y - 2), (x + 8, y)], fill=BLUE2, width=1)
    for wx, wy in [(0.45, 0.79), (0.70, 0.83)]:
        x, y = x0 + wx * w, y0 + wy * h
        draw.line([(x, y), (x + 4, y - 2), (x + 8, y)], fill=BLUE2, width=1)
    draw.text((x0 + 6, y0 + 1), "TÜRKIYE", font=font(SANSB, 9), fill=INK)
    draw.text((x0 + 100, y0 + 1), "BLACK SEA", font=font(SANS, 7), fill=BLUE2)
    # OVERTIME clock, top right (in the Black Sea, clear of the land),
    # with a warm glow halo so it pops — bigger in the 130px box
    cx, cy = x0 + w - 18, y0 + 16
    draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(250, 200, 110))
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(255, 255, 255), outline=RED, width=2)
    draw.line([(cx, cy), (cx, cy - 6)], fill=RED, width=2)
    draw.line([(cx, cy), (cx + 4, cy + 2)], fill=RED, width=2)
    draw.text((cx - 62, cy - 4), "OVERTIME", font=font(SANSB, 7), fill=RED)
    # Istanbul (north-west) + Ankara (central) markers; Ankara's label
    # sits LEFT of its dot so the NO DEAL stamp (right of it) never
    # touches it
    ix, iy = x0 + 0.16 * w, y0 + 0.26 * h
    draw.ellipse([ix - 3, iy - 3, ix + 3, iy + 3], fill=INK, outline=(255, 255, 255), width=1)
    draw.text((ix + 5, iy - 4), "ISTANBUL", font=font(SANS, 7), fill=INK)
    kx, ky = x0 + 0.42 * w, y0 + 0.38 * h
    draw.ellipse([kx - 3, ky - 3, kx + 3, ky + 3], fill=INK, outline=(255, 255, 255), width=1)
    lab = "ANKARA"
    draw.text((kx - 5 - draw.textlength(lab, font=font(SANS, 7)), ky - 4), lab,
              font=font(SANS, 7), fill=INK)
    # Antalya pin on the south coast, at the bay dip — with a warm glow
    # halo so it pops off the land
    ax, ay = x0 + 0.66 * w, y0 + 0.60 * h
    draw.ellipse([ax - 11, ay - 11, ax + 11, ay + 11], fill=(250, 200, 110))
    draw.ellipse([ax - 8, ay - 8, ax + 8, ay + 8], fill=(248, 170, 70))
    draw.ellipse([ax - 5, ay - 5, ax + 5, ay + 5], fill=RED, outline=(255, 255, 255), width=1)
    draw.text((ax + 8, ay - 4), "ANTALYA", font=font(SANSB, 8), fill=RED)
    draw.text((x0 + 6, y0 + 0.72 * h), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    # NO DEAL stamp: bold red text on transparent, rotated, pasted over
    # the eastern half of the map (clear of the clock, Istanbul, Ankara
    # and the Antalya pin)
    stamp = Image.new("RGBA", (140, 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rectangle([2, 2, 137, 37], outline=RED, width=3)
    sd.text((12, 8), "NO DEAL", font=font(SANSB, 20), fill=RED)
    stamp = stamp.rotate(-13, expand=True, resample=Image.BICUBIC)
    scx, scy = x0 + 0.65 * w, y0 + 0.30 * h
    img.paste(stamp, (int(scx - stamp.width / 2), int(scy - stamp.height / 2)), stamp)
    # draft-text box: one line, bottom
    bx, by = x0 + 6, y0 + h - 14
    draw.rectangle([bx, by, x0 + w - 6, y0 + h - 3], fill=(255, 255, 255), outline=RED, width=1)
    draw.text((bx + 5, by + 2), "DRAFT TEXT: ", font=font(SANSB, 8), fill=RED)
    tx = bx + 5 + draw.textlength("DRAFT TEXT: ", font=font(SANSB, 8))
    draw.text((tx, by + 2), "fossil fuels NOT MENTIONED  →  NO DEAL",
              font=font(SANSB, 8), fill=INK)


def draw_libya(img, draw, x0, y0, w, h):
    """Libya / Mediterranean SCENE (130px box): the sea fills the top
    two-thirds, a BIG burning warship (150px hull) sits low in the sea
    with layered flames and five smoke puffs billowing up and to the
    right, waves under the hull, a smaller ship in the distance,
    a burning port facility on the coast near Benghazi, and a thick red
    SEA DRONE arrow. At 300px the first thing seen is the burning ship.
    Everything stays inside the box (x0, y0, w, h)."""
    # v5: subtle vertical gradient on the sea (lighter at the top,
    # deeper below) instead of a flat fill
    _rect_gradient(img, x0, y0, w, h, (230, 236, 241), (198, 212, 226))
    # v6: a faint watercolor wash over the sea (clipped to the box) so
    # the water has variation like a wash, not a flat screen fill.
    # v7: two more washes in slightly different blues so the sea has
    # real watercolor depth, not one flat tint
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (150, 180, 200), alpha=25, seed=212)
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (140, 172, 202), alpha=22, seed=214)
    _watercolor(img, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                (185, 208, 224), alpha=18, seed=215)
    draw.rectangle([x0, y0, x0 + w, y0 + h], outline=INK, width=1)
    # land: north coast lower than v3 (more sea room for the ship +
    # smoke), with the Sidra gulf dip; extends past the bottom
    poly = [(0.02, 0.62), (0.10, 0.58), (0.20, 0.56), (0.25, 0.60),
            (0.30, 0.58), (0.40, 0.64), (0.44, 0.66), (0.48, 0.68),
            (0.55, 0.64), (0.62, 0.59), (0.70, 0.56), (0.78, 0.54),
            (0.86, 0.56), (0.90, 0.60), (0.94, 0.58),
            (0.98, 0.68), (0.98, 1.0), (0.0, 1.0), (0.0, 0.66)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    # v7: wavier coastline (seeded jitter, 3.5px — up from 2.5) +
    # watercolor wash + pen-stroke coastline instead of the ruler line
    pts = _jitter_pts(pts, 3.5, 202)
    draw.polygon(pts, fill=LAND2)
    _watercolor(img, pts, (194, 182, 148), alpha=35, seed=213)
    _hand_outline(draw, pts, INK, seed=222)
    # v5: very subtle dot texture on the land
    _stipple(draw, pts, (194, 182, 148), step=9)
    draw.text((x0 + 6, y0 + 2), "SEA DRONE", font=font(SANSB, 7), fill=RED)
    draw.text((x0 + w - 100, y0 + 2), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    draw.text((x0 + 8, y0 + 0.76 * h), "LIBYA", font=font(SANSB, 9), fill=INK)
    # Benghazi pin on the north-east coast; label BELOW the pin, on the
    # land (the ship's hull covers the strip left of the pin)
    bx, by = x0 + 0.70 * w, y0 + 0.56 * h
    draw.ellipse([bx - 5, by - 5, bx + 5, by + 5], fill=RED, outline=(255, 255, 255), width=1)
    lab = "BENGHAZI"
    draw.text((bx - draw.textlength(lab, font=font(SANSB, 7)) / 2, by + 9), lab,
              font=font(SANSB, 7), fill=RED)
    # burning port facility on the coast, east of Benghazi
    fx, fy = x0 + 0.84 * w, y0 + 0.58 * h
    draw.ellipse([fx - 14, fy - 26, fx + 14, fy - 4], fill=(250, 195, 95))
    draw.ellipse([fx - 6, fy - 28, fx + 2, fy - 20], fill=(120, 115, 105))
    draw.ellipse([fx + 1, fy - 27, fx + 8, fy - 19], fill=(140, 135, 125))
    draw.ellipse([fx - 11, fy - 21, fx + 11, fy - 5], fill=(240, 180, 40), outline=RED)
    for dx, dy in [(-9, -25), (0, -27), (9, -24)]:
        draw.line([(fx, fy - 6), (fx + dx, fy + dy)], fill=RED, width=3)
    draw.rectangle([fx - 12, fy - 5, fx + 12, fy + 3], fill=(60, 60, 60))
    # v8: a pale wash behind the main ship so the black hull lifts off
    # the sea (drawn BEFORE the small ship so the small ship stays crisp)
    _watercolor(img, [(x0 + 40, y0 + 6), (x0 + 235, y0 + 6),
                      (x0 + 235, y0 + 72), (x0 + 40, y0 + 72)],
                (205, 222, 234), alpha=30, seed=216)
    # second ship, small, in the distance (lower left of the sea)
    sx2, sy2 = x0 + 0.13 * w, y0 + 0.24 * h
    draw.polygon([(sx2 - 13, sy2), (sx2 + 13, sy2), (sx2 + 9, sy2 + 5),
                  (sx2 - 9, sy2 + 5)], fill=(70, 70, 70))
    draw.rectangle([sx2 - 7, sy2 - 6, sx2 + 7, sy2], fill=GREY)
    draw.ellipse([sx2 - 2, sy2 - 12, sx2 + 2, sy2 - 7], fill=(150, 145, 135))
    draw.line([(sx2 - 15, sy2 + 7), (sx2 + 15, sy2 + 7)], fill=BLUE2, width=1)
    # BIG burning warship, low in the sea (waterline just above the coast)
    # v8: ZOOMED IN — hull 120px -> 150px wide and 16px -> 20px tall,
    # fewer but BIGGER details (6 large portholes, 2 big lit bridge
    # windows, chunky gun turret, thick mast), thicker white waterline
    # + wider grey stripe, lighter superstructure, pale wash behind the
    # ship — so the ship reads as a warship even at 300px. Same centre:
    # sx, sy unchanged; footprint grows left/right, not up/down.
    sx, sy = x0 + 0.40 * w, y0 + 0.52 * h
    # smoke: 5 puffs billowing up and to the right (wind) — v8: slightly
    # bigger puffs to match the bigger ship, seeded jitter as in v7
    _rng = random.Random(205)
    for dx, dy, rw, rh, col in [
            (-24, -64, 20, 18, (98, 93, 83)), (-8, -66, 20, 18, (118, 113, 103)),
            (8, -66, 20, 18, (138, 133, 123)), (20, -62, 18, 16, (158, 153, 143)),
            (32, -58, 18, 14, (172, 167, 157))]:
        jx, jy = _rng.uniform(-2, 2), _rng.uniform(-2, 2)
        draw.ellipse([sx + dx + jx, sy + dy + jy,
                      sx + dx + rw + jx, sy + dy + rh + jy], fill=col)
    draw.ellipse([sx + 34, sy - 56, sx + 44, sy - 50], fill=(205, 200, 190))
    # warm glow behind the flames (wider than v7 — the ship is wider)
    draw.ellipse([sx - 40, sy - 40, sx + 40, sy - 10], fill=(250, 195, 95))
    # hull: pointed bow right, slanted transom stern, ~150px wide,
    # 20px tall. Vertices jittered 1.5px (seeded) so the edge is rough,
    # not ruler-straight — kept from v7
    hull = [(sx - 68, sy - 8), (sx + 52, sy - 8), (sx + 82, sy - 2),
            (sx + 66, sy + 12), (sx - 56, sy + 12)]
    hull = _jitter_pts(hull, 1.5, 203)
    draw.polygon(hull, fill=INK)
    # white waterline (THICK, 3px) along the deck + wide light-grey
    # stripe just under it, so the hull has a bold lit edge
    draw.line([(sx - 68, sy - 8), (sx + 52, sy - 8), (sx + 82, sy - 2)],
              fill=(255, 255, 255), width=3)
    draw.line([(sx - 66, sy - 3), (sx + 52, sy - 3), (sx + 80, sy + 3)],
              fill=(170, 170, 170), width=3)
    # portholes: FEWER but BIGGER — 6 large pale dots along the hull
    for px in (-56, -36, -16, 4, 24, 44):
        draw.ellipse([sx + px - 3, sy + 2, sx + px + 3, sy + 8],
                     fill=(235, 235, 228))
    # bow gun turret: BIGGER trapezoid on the foredeck + thicker barrel
    # pointing forward-up
    draw.polygon([(sx + 38, sy - 8), (sx + 58, sy - 8), (sx + 54, sy - 17),
                  (sx + 42, sy - 17)], fill=(70, 70, 70))
    draw.line([(sx + 56, sy - 15), (sx + 72, sy - 20)], fill=INK, width=4)
    # bridge tower, right of centre so it stays readable beside the
    # fire: BIGGER blocks, LIGHTER grey (v8: superstructure lightened
    # for contrast against the black hull and the fire), dark outlines
    draw.rectangle([sx + 4, sy - 26, sx + 36, sy - 8], fill=(150, 150, 150),
                   outline=INK, width=2)
    draw.rectangle([sx + 4, sy - 26, sx + 36, sy - 22], fill=(195, 195, 195))
    draw.rectangle([sx + 10, sy - 38, sx + 32, sy - 26], fill=(115, 115, 115),
                   outline=INK, width=2)
    # 2 BIG lit windows on the upper bridge block
    for wx0 in (13, 22):
        draw.rectangle([sx + wx0, sy - 35, sx + wx0 + 7, sy - 28],
                       fill=(185, 220, 240), outline=INK, width=1)
    # funnel, slanted, left of the bridge — right where the fire is
    draw.polygon([(sx - 28, sy - 8), (sx - 17, sy - 8), (sx - 19, sy - 26),
                  (sx - 30, sy - 26)], fill=(70, 70, 70))
    draw.rectangle([sx - 30, sy - 28, sx - 19, sy - 26], fill=INK)
    # LAYERED flames over the funnel/deck: red outer tongues, orange
    # middle, yellow core — v8: one more red tongue, wider tongues,
    # base on the higher deck (sy-8)
    for cx, tip, hw, seed in [(-30, -54, 9, 231), (-12, -60, 11, 232),
                               (4, -48, 8, 233), (-44, -44, 8, 240)]:
        _flame(draw, sx + cx, sy - 8, sy + tip, hw, (215, 50, 25), seed)
    for cx, tip, hw, seed in [(-28, -46, 8, 234), (-12, -50, 9, 235),
                               (0, -40, 7, 236)]:
        _flame(draw, sx + cx, sy - 8, sy + tip, hw, (248, 140, 40), seed)
    for cx, tip, hw, seed in [(-24, -38, 6, 237), (-12, -42, 7, 238),
                               (-2, -34, 5, 239)]:
        _flame(draw, sx + cx, sy - 8, sy + tip, hw, (255, 210, 80), seed)
    # radar mast + antenna whip on the bridge top — drawn AFTER the
    # flames so the mast silhouette still reads against the fire/sky;
    # v8: thicker mast + bigger crossbar
    draw.line([(sx + 26, sy - 38), (sx + 26, sy - 52)], fill=INK, width=3)
    draw.line([(sx + 16, sy - 52), (sx + 36, sy - 52)], fill=INK, width=3)
    draw.line([(sx + 31, sy - 38), (sx + 31, sy - 48)], fill=INK, width=2)
    # waves under the hull (in the sea, just above the coast) — v8 ends
    # at sx+66 so the line stops 6px short of the BENGHAZI label
    for wy in (sy + 14, sy + 16):
        draw.line([(sx - 70, wy), (sx - 35, wy - 2), (sx, wy), (sx + 35, wy - 2),
                   (sx + 66, wy)], fill=BLUE2, width=1)
    # v9: firelight shimmer on the water under the hull (short orange
    # streaks between the wave lines) + white foam at the bow
    for fx in (-40, 0, 40):
        draw.line([(sx + fx, sy + 13), (sx + fx, sy + 17)], fill=(248, 160, 55),
                  width=2)
    for fx, fy in [(84, 0), (88, 4), (80, 6)]:
        draw.ellipse([sx + fx - 2, sy + fy - 1, sx + fx + 2, sy + fy + 1],
                     fill=(255, 255, 255))
    # thick red arrow: drone path to the ship, from the upper left
    draw.line([(x0 + 30, y0 + 10), (sx - 68, sy - 8)], fill=RED, width=4)
    draw.polygon([(sx - 68, sy - 8), (sx - 80, sy - 14), (sx - 76, sy)], fill=RED)


def draw_house_chart(img, draw, x0, y0, w, h):
    """US House seats (130px box): 258 Dem (blue) vs 177 Rep (red),
    stacked bar + a BIG detailed Capitol (ribbed dome, lantern, columned
    base) and a small US flag — plus victory confetti dots and two gold
    stars scattered in the empty space, so the scene reads as a win.
    Everything stays inside the box (x0, y0, w, h)."""
    # v5: subtle sky gradient (pale blue at the top fading to near-white)
    _rect_gradient(img, x0, y0, w, h, (214, 225, 238), (236, 239, 243))
    draw.rectangle([x0, y0, x0 + w, y0 + h], outline=INK, width=1)
    draw.text((x0 + 6, y0 + 3), "US HOUSE  ·  435 SEATS", font=font(SANSB, 9), fill=INK)
    # small US flag, top left under the title
    fx, fy = x0 + 12, y0 + 20
    draw.line([(fx, fy), (fx, fy + 26)], fill=INK, width=2)
    for i, c in enumerate([RED, (255, 255, 255), RED, (255, 255, 255)]):
        draw.rectangle([fx + 2, fy + i * 5, fx + 38, fy + (i + 1) * 5], fill=c)
    draw.rectangle([fx + 2, fy, fx + 17, fy + 10], fill=BLUE)
    draw.ellipse([fx + 5, fy + 3, fx + 7, fy + 5], fill=(255, 255, 255))
    draw.ellipse([fx + 11, fy + 3, fx + 13, fy + 5], fill=(255, 255, 255))
    draw.rectangle([fx + 2, fy, fx + 38, fy + 20], outline=INK)
    # Capitol, BIG and real — v7 REDRAW: a proper dome (not a flat
    # half-ellipse) with ribs, a wider colonnaded drum, a lantern with
    # the Statue of Freedom on top, and two WINGS (Senate + House)
    # stretching left and right with pediments, windows and a columned
    # terrace base. Centred in the box (cx = x0+170) so the building
    # reads as the Capitol, not a small dome in the corner. The bar
    # sits at y0+84, so the terrace step (ends y0+80) just clears it.
    cx = x0 + 170
    base_top = y0 + 66
    # dome: a real dome silhouette — wide at the base, curving in to a
    # small flat crown — v5 gradient (bright lit side, shaded right)
    dome = [(-36, 0), (-35, -10), (-31, -20), (-24, -28), (-14, -33),
            (-6, -35), (0, -35), (6, -35), (14, -33), (24, -28),
            (31, -20), (35, -10), (36, 0)]
    dome_pts = [(cx + dx, base_top + dy) for dx, dy in dome]
    # v6: the dome outline is jittered 1px (seeded) and drawn as a
    # pen stroke — the dome stops looking stamped and starts looking
    # drawn
    dome_pts = _jitter_pts(dome_pts, 1.0, 204)
    _poly_gradient(img, dome_pts, (255, 255, 255), (224, 229, 237), horizontal=True)
    _hand_outline(draw, dome_pts, INK, seed=224)
    # ribs on the dome, following the curve
    for dx, top in [(-24, -28), (-12, -33), (0, -35), (12, -33), (24, -28)]:
        draw.line([(cx + dx, base_top + top), (cx + dx, base_top - 1)],
                  fill=GREY, width=1)
    # drum: wider colonnade under the dome
    draw.rectangle([cx - 26, base_top - 6, cx + 26, base_top],
                   fill=(255, 255, 255), outline=INK)
    for dx in (-22, -16, -10, -4, 2, 8, 14, 20):
        draw.line([(cx + dx, base_top - 5), (cx + dx, base_top - 1)],
                  fill=GREY, width=1)
    # lantern + Statue of Freedom on top (a tiny figure: head + body,
    # standing on the lantern's little cap)
    draw.rectangle([cx - 5, base_top - 43, cx + 5, base_top - 35],
                   fill=(255, 255, 255), outline=INK)
    draw.ellipse([cx - 5, base_top - 47, cx + 5, base_top - 43],
                 fill=(255, 255, 255), outline=INK)
    draw.ellipse([cx - 2, base_top - 54, cx + 2, base_top - 50], fill=INK)
    draw.polygon([(cx - 3, base_top - 50), (cx + 3, base_top - 50),
                  (cx + 1, base_top - 46), (cx - 1, base_top - 46)], fill=INK)
    # wings (Senate left, House right): lower blocks with a triangular
    # pediment in the middle of each, windows along the front. They
    # start clear of the flag (flag ends x0+50, left wing starts
    # cx-118 = x0+52) and stay below the flag's pole (y0+46).
    for sgn in (-1, 1):
        wx0 = cx + sgn * 36
        wx1 = cx + sgn * 118
        x_lo, x_hi = min(wx0, wx1), max(wx0, wx1)
        draw.rectangle([x_lo, base_top - 6, x_hi, base_top],
                       fill=(255, 255, 255), outline=INK)
        # pediment triangle in the middle of the wing
        px = cx + sgn * 77
        draw.polygon([(px - 18, base_top - 6), (px + 18, base_top - 6),
                      (px, base_top - 12)], fill=(255, 255, 255), outline=INK)
        # windows along the wing front
        for wx in range(int(x_lo) + 6, int(x_hi) - 4, 10):
            draw.rectangle([wx, base_top - 4, wx + 4, base_top - 1],
                           fill=(90, 90, 90))
    # v5: soft shadow under the base (drawn first so the opaque base
    # covers the overlap — only the fringe below shows)
    _soft_shadow(img, [(cx - 124, base_top), (cx + 124, base_top),
                       (cx + 124, base_top + 10), (cx - 124, base_top + 10)],
                 offset=(2, 3), blur=3, alpha=45)
    # terrace base with columns + a step below it
    draw.rectangle([cx - 124, base_top, cx + 124, base_top + 10],
                   fill=(255, 255, 255), outline=INK)
    for dx in range(-116, 117, 8):
        draw.line([(cx + dx, base_top + 1), (cx + dx, base_top + 9)],
                  fill=GREY, width=1)
    draw.rectangle([cx - 130, base_top + 10, cx + 130, base_top + 14],
                   fill=(245, 245, 245), outline=INK)
    # v9: two small trees flanking the terrace base (a touch of green
    # in front of the building) — clear of the flag, wings and bar
    for tx in (cx - 140, cx + 140):
        draw.rectangle([tx - 1, base_top + 9, tx + 1, base_top + 17],
                       fill=(120, 90, 60))
        draw.ellipse([tx - 5, base_top + 1, tx + 5, base_top + 11],
                     fill=GREEN)
    # two small gold stars flanking the dome
    for sx, sy in [(cx - 58, base_top - 36), (cx + 52, base_top - 44)]:
        draw.polygon([(sx, sy - 5), (sx + 2, sy - 1), (sx + 5, sy - 1),
                      (sx + 2, sy + 2), (sx + 3, sy + 6), (sx, sy + 3),
                      (sx - 3, sy + 6), (sx - 2, sy + 2), (sx - 5, sy - 1),
                      (sx - 2, sy - 1)], fill=GOLD, outline=INK)
    # victory confetti: fixed dots (red/blue/gold) in the empty space —
    # left of the dome, below the flag, and under the bar. Hardcoded,
    # so the render stays deterministic.
    confetti = [
        (60, 58, RED), (76, 68, BLUE), (92, 55, GOLD), (56, 75, BLUE),
        (102, 78, RED), (72, 82, GOLD), (122, 62, BLUE), (142, 72, RED),
        (162, 58, GOLD), (182, 78, BLUE), (206, 60, RED), (222, 76, GOLD),
        (20, 122, BLUE), (60, 124, RED), (100, 122, GOLD), (150, 125, BLUE),
        (180, 123, RED), (230, 121, GOLD), (270, 125, BLUE), (296, 120, RED),
        (250, 124, GOLD), (120, 126, BLUE),
    ]
    for px, py, col in confetti:
        draw.ellipse([x0 + px - 2, y0 + py - 2, x0 + px + 2, y0 + py + 2], fill=col)
    # stacked bar
    bx, by, bw, bh = x0 + 10, y0 + 84, w - 20, 20
    dem_w = bw * 258 / 435
    draw.rectangle([bx, by, bx + dem_w, by + bh], fill=BLUE)
    draw.rectangle([bx + dem_w, by, bx + bw, by + bh], fill=RED)
    draw.rectangle([bx, by, bx + bw, by + bh], outline=INK, width=1)
    f = font(SANSB, 9)
    draw.text((bx + 5, by + 5), "258 DEM", font=f, fill=(255, 255, 255))
    t = "177 REP"
    draw.text((bx + bw - draw.textlength(t, font=f) - 5, by + 5), t, font=f,
              fill=(255, 255, 255))
    draw.text((x0 + 10, by + bh + 4), "LARGEST MAJORITY SINCE 1992",
              font=font(SANSB, 9), fill=RED)


# ---------------------------------------------------------------- render
def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    MX = 14  # side margin
    RX = W - MX

    # ---- masthead ----
    y = 8
    d.text((MX, y), "Sunday 22 November 2026", font=font(SERIFB, 40), fill=INK)
    t = "ONE DAY OF WORLD NEWS, ONE PICTURE"
    d.text((RX - tw(d, t, font(SANSB, 10)), y + 8), t, font=font(SANSB, 10), fill=RED)
    t2 = "THE WORLD ON A SUNDAY"
    d.text((RX - tw(d, t2, font(SANS, 9)), y + 22), t2, font=font(SANS, 9), fill=GREY)
    y = 54
    d.text((MX, y), "36 STORIES  ·  9 REGIONS  ·  19 FIELDS  ·  ALL FROM THIS SUNDAY",
           font=font(SANSB, 12), fill=INK)
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

    # ---- 3 big leads (illustration boxes now 130px tall) ----
    y = 177
    lead_h = 246
    col_w = (RX - MX - 12) / 3.0
    for i, (num, kick, head, deck, src, conf) in enumerate(LEADS):
        x = MX + i * (col_w + 6)
        # v5: soft drop shadow under the lead box (drawn first; the
        # opaque paper fill covers the overlap, only the fringe shows)
        _rect_shadow(img, x, y, x + col_w, y + lead_h)
        d.rectangle([x, y, x + col_w, y + lead_h], fill=PAPER, outline=INK, width=1)
        d.rectangle([x, y, x + col_w, y + 20], fill=REDBG)
        d.text((x + 6, y + 4), f"#{num}  {kick}", font=font(SANSB, 9), fill=(255, 255, 255))
        d.text((x + 6, y + 24), head, font=font(SERIFB, 19), fill=INK)
        yy = y + 48
        para(d, x + 6, yy, deck, font(SANS, 10), INK, col_w - 12, lh=12, max_lines=3)
        # illustration
        ih = 130
        iy = y + lead_h - ih - 22
        if num == 1:
            draw_turkiye(img, d, x + 6, iy, col_w - 12, ih)
        elif num == 2:
            draw_libya(img, d, x + 6, iy, col_w - 12, ih)
        else:
            draw_house_chart(img, d, x + 6, iy, col_w - 12, ih)
        # source + badge
        sy = y + lead_h - 16
        d.text((x + 6, sy + 2), src, font=font(SANS, 8), fill=GREY)
        badge(d, x + col_w - 62, sy, conf)

    # ---- 10 medium cards, 2 rows of 5 (74px; NOT compressed in v4 —
    # the ALSO ON cut alone pays for the bigger leads) ----
    y = 429
    card_w = (RX - MX - 16) / 5.0
    card_h = 74
    for row in range(2):
        for col in range(5):
            m = MEDIUM[row * 5 + col]
            num, kick, head, deck, src, conf, ic = m
            x = MX + col * (card_w + 4)
            yy = y + row * (card_h + 3)
            d.rectangle([x, yy, x + card_w, yy + card_h], fill=(255, 255, 255),
                        outline=LINE, width=1)
            d.text((x + 5, yy + 3), f"{num}  {kick}", font=font(SANSB, 7), fill=RED)
            # BIG icon (40px, thick lines) on the left; headline + deck
            # to its right so nothing overlaps
            icon(d, ic, x + 21, yy + 34, 40)
            para(d, x + 46, yy + 14, head, font(SANSB, 10), INK, card_w - 52, lh=11,
                 max_lines=2)
            para(d, x + 46, yy + 39, deck, font(SANS, 8), INK, card_w - 52, lh=9,
                 max_lines=2)
            sy = yy + card_h - 13
            d.text((x + 5, sy + 1), src, font=font(SANS, 7), fill=GREY)
            badge(d, x + card_w - 60, sy, conf)

    # ---- STORIES BY REGION (single 14px row: label + bar + legend) ----
    y = 586
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

    # ---- WHERE IT HAPPENED (taller strip: 160px, Europe breathes) ----
    y = 604
    d.text((MX, y), "WHERE IT HAPPENED  ·  PINS 1–13  (13 = IN ORBIT)",
           font=font(SANSB, 10), fill=INK)
    draw_world_map(img, d, MX, y + 15, RX - MX, 160)

    # ---- ALSO ON ----
    y = 785
    d.text((MX, y), "ALSO ON SUNDAY 22 NOVEMBER — 23 MORE STORIES",
           font=font(SANSB, 10), fill=INK)
    rule(d, MX, RX, y + 15, INK, 1)
    y = 805
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
    assert max_y <= 940, f"ALSO ON overflow: ends at y={max_y}"

    # ---- DATE CHECK + HOW SURE ----
    y = 943
    d.rectangle([MX, y, RX, y + 52], fill=(255, 255, 255), outline=RED, width=2)
    d.text((MX + 6, y + 2), "DATE CHECK — LEFT OUT AS OLDER NEWS",
           font=font(SANSB, 9), fill=RED)
    para(d, MX + 6, y + 12,
         "Shenzhen summit (19–20 Nov) · ICJ Rohingya ruling (19 Nov) · GTA VI $3.79bn "
         "(19–20 Nov) · Anthropic IPO $93.5bn (20 Nov) · 'El Chapo Isidro' arrested "
         "(20–21 Nov) · Akvan landfall (20 Nov) · Banda Sea M6.8 (21 Nov)",
         font(SANS, 8), INK, RX - MX - 12, lh=10, max_lines=1)
    d.text((MX + 6, y + 28),
           "NOT YET: ATP final (23 Nov) · BepiColombo separation (9–10 Dec)",
           font=font(SANSB, 8), fill=INK)
    d.text((MX + 6, y + 40), "HOW SURE ARE WE?  ",
           font=font(SANSB, 8), fill=INK)
    xx = MX + 6 + tw(d, "HOW SURE ARE WE?  ", font(SANSB, 8))
    d.text((xx, y + 40), "CONFIRMED = 2+ outlets · OFFICIAL = on the record · REPORTED = one outlet",
           font=font(SANS, 8), fill=GREY)

    # ---- footer ----
    y = 999
    rule(d, MX, RX, y, INK, 1)
    d.text((MX, y + 4),
           "Every story here happened, or was first reported, on Sunday 22 November 2026.",
           font=font(SANSB, 9), fill=INK)
    d.text((MX, y + 15),
           "Sources: AP, Reuters, AFP, BBC, USGS, ESA, IMD, UKMTO, NEMA, WHO. "
           "All maps and drawings are original vector work, no photographs.",
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
