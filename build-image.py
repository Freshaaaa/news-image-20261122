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
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
    """Small pictogram centred at (cx, cy), size s."""
    if kind == "blast":
        # building + explosion star
        draw.rectangle([cx - s * 0.32, cy - s * 0.1, cx + s * 0.1, cy + s * 0.42], fill=col)
        draw.rectangle([cx + s * 0.14, cy + s * 0.05, cx + s * 0.4, cy + s * 0.42], fill=(70, 70, 70))
        for dx, dy in [(-0.5, -0.45), (-0.1, -0.5), (0.35, -0.48), (0.55, -0.3),
                       (-0.55, -0.25), (0.1, -0.35)]:
            draw.line([(cx, cy - s * 0.2), (cx + dx * s, cy + dy * s)], fill=RED, width=3)
        draw.ellipse([cx - s * 0.14, cy - s * 0.42, cx + s * 0.14, cy - s * 0.14],
                     fill=(240, 180, 40), outline=RED)
    elif kind == "ship":
        draw.polygon([(cx - s * 0.45, cy + s * 0.25), (cx + s * 0.45, cy + s * 0.25),
                      (cx + s * 0.3, cy + s * 0.42), (cx - s * 0.3, cy + s * 0.42)], fill=col)
        draw.rectangle([cx - s * 0.2, cy - s * 0.05, cx + s * 0.2, cy + s * 0.25], fill=(60, 60, 60))
        draw.line([(cx, cy - s * 0.45), (cx, cy - s * 0.05)], fill=col, width=3)
        draw.polygon([(cx, cy - s * 0.45), (cx + s * 0.3, cy - s * 0.32),
                      (cx, cy - s * 0.2)], fill=RED)
        draw.line([(cx - s * 0.45, cy + s * 0.5), (cx + s * 0.45, cy + s * 0.5)],
                  fill=BLUE2, width=3)
    elif kind == "missile":
        draw.polygon([(cx, cy - s * 0.5), (cx + s * 0.14, cy - s * 0.2),
                      (cx + s * 0.14, cy + s * 0.25), (cx - s * 0.14, cy + s * 0.25),
                      (cx - s * 0.14, cy - s * 0.2)], fill=col)
        draw.polygon([(cx - s * 0.14, cy + s * 0.25), (cx - s * 0.3, cy + s * 0.45),
                      (cx, cy + s * 0.3)], fill=RED)
        draw.polygon([(cx + s * 0.14, cy + s * 0.25), (cx + s * 0.3, cy + s * 0.45),
                      (cx, cy + s * 0.3)], fill=RED)
    elif kind == "chart":
        pts = [(cx - s * 0.45, cy + s * 0.1), (cx - s * 0.2, cy - s * 0.15),
               (cx, cy + s * 0.05), (cx + s * 0.2, cy - s * 0.2),
               (cx + s * 0.45, cy + s * 0.35)]
        draw.line(pts, fill=RED, width=4, joint="curve")
        draw.polygon([(cx + s * 0.45, cy + s * 0.35), (cx + s * 0.45, cy + s * 0.2),
                      (cx + s * 0.3, cy + s * 0.35)], fill=RED)
        draw.line([(cx - s * 0.5, cy + s * 0.45), (cx + s * 0.5, cy + s * 0.45)],
                  fill=GREY, width=2)
    elif kind == "flag":
        draw.line([(cx - s * 0.3, cy - s * 0.45), (cx - s * 0.3, cy + s * 0.45)],
                  fill=col, width=3)
        for i, c in enumerate([INK, (255, 255, 255), INK, (255, 255, 255)]):
            draw.rectangle([cx - s * 0.3, cy - s * 0.45 + i * s * 0.18,
                            cx + s * 0.4, cy - s * 0.45 + (i + 1) * s * 0.18], fill=c)
        draw.rectangle([cx - s * 0.3, cy - s * 0.45, cx + s * 0.4, cy + s * 0.27],
                       outline=INK)
    elif kind == "quake":
        pts = [(cx - s * 0.5, cy), (cx - s * 0.3, cy - s * 0.3), (cx - s * 0.12, cy + s * 0.25),
               (cx + s * 0.05, cy - s * 0.35), (cx + s * 0.22, cy + s * 0.2),
               (cx + s * 0.4, cy - s * 0.1), (cx + s * 0.5, cy)]
        draw.line(pts, fill=RED, width=3, joint="curve")
        draw.line([(cx - s * 0.5, cy + s * 0.4), (cx + s * 0.5, cy + s * 0.4)],
                  fill=GREY, width=2)
    elif kind == "storm":
        draw.ellipse([cx - s * 0.4, cy - s * 0.3, cx + s * 0.1, cy + s * 0.1], fill=GREY)
        draw.ellipse([cx - s * 0.1, cy - s * 0.4, cx + s * 0.4, cy + s * 0.05], fill=INK)
        draw.polygon([(cx + s * 0.05, cy + s * 0.05), (cx - s * 0.1, cy + s * 0.35),
                      (cx + s * 0.05, cy + s * 0.35), (cx - s * 0.05, cy + s * 0.55)],
                     fill=(240, 180, 40))
    elif kind == "fire":
        draw.rectangle([cx - s * 0.35, cy + s * 0.1, cx + s * 0.35, cy + s * 0.45], fill=GREY)
        draw.polygon([(cx, cy - s * 0.45), (cx + s * 0.2, cy - s * 0.05),
                      (cx + s * 0.08, cy + s * 0.1), (cx - s * 0.12, cy + s * 0.1),
                      (cx - s * 0.2, cy - s * 0.05)], fill=RED)
        draw.ellipse([cx - s * 0.08, cy - s * 0.05, cx + s * 0.08, cy + s * 0.1],
                     fill=(240, 180, 40))
    elif kind == "virus":
        draw.ellipse([cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25], fill=RED)
        for a in range(0, 360, 45):
            import math
            r = math.radians(a)
            x1, y1 = cx + 0.25 * s * math.cos(r), cy + 0.25 * s * math.sin(r)
            x2, y2 = cx + 0.42 * s * math.cos(r), cy + 0.42 * s * math.sin(r)
            draw.line([(x1, y1), (x2, y2)], fill=RED, width=3)
    elif kind == "planet":
        draw.ellipse([cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3],
                     fill=(200, 170, 120), outline=INK)
        draw.ellipse([cx - s * 0.5, cy - s * 0.12, cx + s * 0.5, cy + s * 0.12],
                     outline=BLUE2, width=2)


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


def draw_world_map(draw, x0, y0, w, h):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=SEA, outline=INK, width=1)
    for poly in WORLD_POLYS:
        pts = [world_xy(lat, lon, x0, y0, w, h) for lon, lat in poly]
        # darker land + darker coastline so continents pop off the sea
        draw.polygon(pts, fill=(212, 196, 152), outline=(105, 95, 68))
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
    poly = [(0.03, 0.36), (0.04, 0.31), (0.05, 0.26), (0.08, 0.19), (0.15, 0.16),
            (0.25, 0.15), (0.30, 0.19), (0.35, 0.17), (0.45, 0.15), (0.55, 0.17),
            (0.60, 0.20), (0.65, 0.15), (0.75, 0.17), (0.85, 0.19), (0.89, 0.22),
            (0.93, 0.23), (0.96, 0.29), (0.95, 0.36), (0.90, 0.44), (0.86, 0.47),
            (0.82, 0.50), (0.74, 0.54), (0.66, 0.58), (0.58, 0.54), (0.50, 0.50),
            (0.42, 0.48), (0.34, 0.46), (0.26, 0.44), (0.18, 0.42),
            (0.10, 0.40), (0.06, 0.38), (0.08, 0.34), (0.04, 0.32)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    # v5: soft shadow under the map (drawn first, land covers the
    # overlap, only the fringe shows on the sea) + subtle vertical
    # gradient on the land (brighter at the top, a touch darker below)
    # + very subtle dot texture — warmer, darker land so the map reads
    # as a shape, not a pale silhouette
    _soft_shadow(img, pts, offset=(3, 5), blur=5, alpha=55)
    _poly_gradient(img, pts, (212, 184, 136), (198, 166, 112))
    draw.polygon(pts, fill=None, outline=INK)
    _stipple(draw, pts, (186, 156, 106), step=9)
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
    two-thirds, a BIG burning warship (120px hull) sits low in the sea
    with a two-tier orange fire and five smoke puffs billowing up and
    to the right, waves under the hull, a smaller ship in the distance,
    a burning port facility on the coast near Benghazi, and a thick red
    SEA DRONE arrow. At 300px the first thing seen is the burning ship.
    Everything stays inside the box (x0, y0, w, h)."""
    # v5: subtle vertical gradient on the sea (lighter at the top,
    # deeper below) instead of a flat fill
    _rect_gradient(img, x0, y0, w, h, (230, 236, 241), (198, 212, 226))
    draw.rectangle([x0, y0, x0 + w, y0 + h], outline=INK, width=1)
    # land: north coast lower than v3 (more sea room for the ship +
    # smoke), with the Sidra gulf dip; extends past the bottom
    poly = [(0.02, 0.62), (0.10, 0.58), (0.20, 0.56), (0.25, 0.60),
            (0.30, 0.58), (0.40, 0.64), (0.44, 0.66), (0.48, 0.68),
            (0.55, 0.64), (0.62, 0.59), (0.70, 0.56), (0.78, 0.54),
            (0.86, 0.56), (0.90, 0.60), (0.94, 0.58),
            (0.98, 0.68), (0.98, 1.0), (0.0, 1.0), (0.0, 0.66)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    draw.polygon(pts, fill=LAND2, outline=INK)
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
    # second ship, small, in the distance (lower left of the sea)
    sx2, sy2 = x0 + 0.13 * w, y0 + 0.24 * h
    draw.polygon([(sx2 - 13, sy2), (sx2 + 13, sy2), (sx2 + 9, sy2 + 5),
                  (sx2 - 9, sy2 + 5)], fill=(70, 70, 70))
    draw.rectangle([sx2 - 7, sy2 - 6, sx2 + 7, sy2], fill=GREY)
    draw.ellipse([sx2 - 2, sy2 - 12, sx2 + 2, sy2 - 7], fill=(150, 145, 135))
    draw.line([(sx2 - 15, sy2 + 7), (sx2 + 15, sy2 + 7)], fill=BLUE2, width=1)
    # BIG burning warship, low in the sea (waterline just above the coast)
    sx, sy = x0 + 0.40 * w, y0 + 0.52 * h
    # smoke: 5 puffs billowing up and to the right (wind), above the
    # fire — v5: clean gradient, darkest at the base, lightest at the
    # top, plus a pale highlight on the topmost puff
    draw.ellipse([sx - 20, sy - 62, sx - 2, sy - 46], fill=(98, 93, 83))
    draw.ellipse([sx - 6, sy - 64, sx + 12, sy - 48], fill=(118, 113, 103))
    draw.ellipse([sx + 6, sy - 66, sx + 24, sy - 50], fill=(138, 133, 123))
    draw.ellipse([sx + 16, sy - 64, sx + 34, sy - 50], fill=(158, 153, 143))
    draw.ellipse([sx + 26, sy - 60, sx + 42, sy - 48], fill=(172, 167, 157))
    draw.ellipse([sx + 28, sy - 58, sx + 38, sy - 52], fill=(205, 200, 190))
    # fire: two-tier orange glow + bright core + tall red flame tongues
    draw.ellipse([sx - 44, sy - 54, sx + 44, sy - 16], fill=(250, 195, 95))
    draw.ellipse([sx - 38, sy - 50, sx + 38, sy - 18], fill=(248, 160, 55))
    draw.ellipse([sx - 32, sy - 48, sx + 32, sy - 20], fill=(240, 180, 40), outline=RED)
    draw.ellipse([sx - 15, sy - 40, sx + 15, sy - 22], fill=(255, 215, 90))
    for dx, dy in [(-26, -52), (0, -56), (26, -50)]:
        draw.line([(sx, sy - 24), (sx + dx, sy + dy)], fill=RED, width=4)
    # superstructure + funnel + mast — v5: light strip on top of the
    # superstructure so the firelight reads as shading, not flat grey
    draw.rectangle([sx - 28, sy - 20, sx + 28, sy - 6], fill=GREY)
    draw.rectangle([sx - 28, sy - 20, sx + 28, sy - 16], fill=(140, 140, 140))
    draw.rectangle([sx - 42, sy - 16, sx - 30, sy - 6], fill=(60, 60, 60))
    draw.line([(sx + 22, sy - 20), (sx + 22, sy - 36)], fill=INK, width=2)
    # hull: dark, 120px wide — v5: thin grey highlight just under the
    # white waterline so the hull has a lit edge
    draw.polygon([(sx - 60, sy - 6), (sx + 60, sy - 6), (sx + 48, sy + 10),
                  (sx - 48, sy + 10)], fill=INK)
    draw.line([(sx - 60, sy - 6), (sx + 60, sy - 6)], fill=(255, 255, 255), width=1)
    draw.line([(sx - 56, sy - 3), (sx + 56, sy - 3)], fill=(110, 110, 110), width=2)
    # waves under the hull (in the sea, just above the coast)
    for wy in (sy + 12, sy + 14):
        draw.line([(sx - 62, wy), (sx - 30, wy - 2), (sx, wy), (sx + 30, wy - 2),
                   (sx + 62, wy)], fill=BLUE2, width=1)
    # thick red arrow: drone path to the ship, from the upper left
    draw.line([(x0 + 30, y0 + 10), (sx - 62, sy - 8)], fill=RED, width=4)
    draw.polygon([(sx - 62, sy - 8), (sx - 74, sy - 14), (sx - 70, sy)], fill=RED)


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
    # Capitol dome, BIG and detailed, top right. base_top = y0+66;
    # the bar sits at y0+84, so the base (ends y0+76) just clears it.
    cx = x0 + w - 46
    base_top = y0 + 66
    # dome: smooth half-ellipse polygon (offsets from cx, base_top) —
    # v5: subtle left-to-right gradient (bright white on the lit side,
    # faintly shaded on the right) instead of a flat fill
    dome = [(-30, -10), (-29, -18), (-24, -25), (-16, -30), (-9, -32),
            (0, -32), (9, -32), (16, -30), (24, -25), (29, -18), (30, -10)]
    dome_pts = [(cx + dx, base_top + dy) for dx, dy in dome]
    _poly_gradient(img, dome_pts, (255, 255, 255), (224, 229, 237), horizontal=True)
    draw.polygon(dome_pts, fill=None, outline=INK)
    # ribs on the dome
    for dx, top in [(-20, -28), (-10, -31), (0, -32), (10, -31), (20, -28)]:
        draw.line([(cx + dx, base_top + top), (cx + dx, base_top - 11)],
                  fill=GREY, width=1)
    # lantern + finial
    draw.rectangle([cx - 6, base_top - 40, cx + 6, base_top - 32],
                   fill=(255, 255, 255), outline=INK)
    draw.ellipse([cx - 2, base_top - 42, cx + 2, base_top - 40], fill=INK)
    # drum
    draw.rectangle([cx - 22, base_top - 10, cx + 22, base_top],
                   fill=(255, 255, 255), outline=INK)
    # v5: soft shadow under the base (drawn first so the opaque base
    # covers the overlap — only the fringe below shows)
    _soft_shadow(img, [(cx - 42, base_top), (cx + 42, base_top),
                       (cx + 42, base_top + 10), (cx - 42, base_top + 10)],
                 offset=(2, 3), blur=3, alpha=45)
    # base with columns
    draw.rectangle([cx - 42, base_top, cx + 42, base_top + 10],
                   fill=(255, 255, 255), outline=INK)
    for dx in (-32, -24, -16, -8, 0, 8, 16, 24, 32):
        draw.line([(cx + dx, base_top + 1), (cx + dx, base_top + 9)],
                  fill=GREY, width=1)
    # two small gold stars flanking the dome
    for sx, sy in [(cx - 62, base_top - 38), (cx + 44, base_top - 52)]:
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
    draw_world_map(d, MX, y + 15, RX - MX, 160)

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
