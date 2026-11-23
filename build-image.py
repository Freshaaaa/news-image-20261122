#!/usr/bin/env python3
"""news-image-20261122 — render the Sunday 22 November 2026 front page.

One image, 1024x1024, PIL only, fully deterministic (no network, no clock,
no unseeded randomness). Writes entry.png next to this script.
Layout follows the proven winner template: masthead -> UTC strip -> numbers
strip -> 3 big illustrated leads -> 10 medium icon cards -> region bar ->
world map "WHERE IT HAPPENED" -> "ALSO ON" 31 small stories -> DATE CHECK
-> HOW SURE -> footer. 44 stories, 9 regions, 19 fields.
"""
import hashlib
import os
import sys

from PIL import Image, ImageDraw, ImageFont

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
     "3–4 killed, 14 missing in the rubble. Overnight: 400+ drones, 110 missiles.",
     "AP · Reuters", "CONFIRMED", "blast"),
    (5, "BALTIC SEA  ·  WAR", "Burning Sparta II towed away",
     "Finland confirms Russia is towing the cargo ship away after a drone strike.",
     "Reuters · BBC", "CONFIRMED", "ship"),
    (6, "LONDON  ·  MILITARY", "UK sends 1,000+ missiles",
     "Britain sends 1,000+ air-defence missiles to Ukraine in a £240m package.",
     "Reuters", "OFFICIAL", "missile"),
    (7, "WALL STREET  ·  ECONOMY", "S&P 500 falls 3.7%",
     "Dow enters a correction; Nasdaq erases its 2026 gains as AI stocks plunge.",
     "AP · Reuters", "CONFIRMED", "chart"),
    (8, "LAS VEGAS  ·  SPORT", "Verstappen wins in Vegas",
     "35 lead changes; wins by 0.639s over Norris. Piastri third.",
     "AP · F1", "CONFIRMED", "flag"),
    (9, "JUNÍN, PERU  ·  DISASTER", "Quake toll: 1 dead, 93,000 dark",
     "INDECI: 1 killed, 16 hurt, 853 displaced, 93,000 without power.",
     "INDECI · USGS", "OFFICIAL", "quake"),
    (10, "BRAZIL  ·  DISASTER", "Supercell: 4 killed, 162 hurt",
     "Disaster decree in Tupanciretã; 8,000+ homes damaged by the storm.",
     "Reuters · AP", "CONFIRMED", "storm"),
    (11, "CIKANDE, INDONESIA  ·  DISASTER", "Factory fire: 3 dead, 34 missing",
     "A candy factory burns in Banten; bodies found in 24 bags.",
     "AP · Reuters", "CONFIRMED", "fire"),
    (12, "DR CONGO  ·  HEALTH", "Ebola passes 11,021 cases",
     "5,358 dead. WHO: fighting near Ituri hospital disrupts the response.",
     "WHO · CDC", "OFFICIAL", "virus"),
    (13, "MERCURY  ·  SPACE", "BepiColombo reaches Mercury",
     "Enters orbit after 8 years; ESA reports a thruster glitch.",
     "Reuters · ESA", "CONFIRMED", "planet"),
]

# (num, place, headline, source) — 31 small stories, grouped by region
SMALL = [
    (14, "WASHINGTON", "Trump signs EO 14438: contractors must consult the White House.", "AP"),
    (15, "SEATTLE", "ICE arrests 2 on an Alaska Airlines jet bridge at Sea-Tac.", "AP"),
    (16, "WASHINGTON", "Trump confirms the FBI crime database was hacked.", "Reuters"),
    (17, "SAN ANTONIO", "Wembanyama scores 50 in a Spurs win.", "NBA"),
    (18, "ARIZONA", "SpaceX's $74bn AI campus stalls in a power-bill dispute (6,000 MW).", "Fortune"),
    (19, "NEW YORK", "Anthropic's IPO sparks a Wall Street row over unusual deal limits.", "Reuters"),
    (20, "BRAZIL", "Five arrested over 660 kg of cocaine linked to Australia.", "AP"),
    (21, "ARGENTINA", "$50bn LNG project approved.", "Reuters"),
    (22, "ARGENTINA", "Country risk hits 1,070, the highest of 2026.", "JPMorgan"),
    (23, "GUATEMALA", "Mexican fugitive arrested; the US seeks extradition.", "AP"),
    (24, "POLAND", "Kh-101 missile debris found at three sites.", "Reuters"),
    (25, "LONDON", "Conservatives vow to scrap the UK–EU deal.", "Reuters"),
    (26, "PARIS", "Sixth weekend of protests over the cost of living.", "AFP"),
    (27, "BRUSSELS", "EU's Costa proposes €204bn in savings and a digital tax.", "Handelsblatt"),
    (28, "BELGIUM", "Brussels airports cancel most Monday flights as controllers strike.", "Reuters"),
    (29, "TEHRAN", "Trump dares Iran to break the US port blockade.", "AP"),
    (30, "SITRA, BAHRAIN", "Iranian attack on a civilian industrial site causes a fire; 2 hurt.", "Reuters"),
    (31, "STRAIT OF HORMUZ", "Iran hits three tankers; UKMTO reports a vessel incident.", "UKMTO"),
    (32, "GAZA CITY", "Israeli strike on a food van kills 3.", "AP"),
    (33, "BAYELSA, NIGERIA", "Death toll from a capsized mourners' boat rises to 26.", "Reuters"),
    (34, "KHARTOUM", "Drones hit homes and a UN building in Khartoum.", "OCHA"),
    (35, "ATLANTIC", "Migrant boat capsizes off Senegal; 39 dead.", "Reuters"),
    (36, "OYO, CONGO", "Kenya and DR Congo restore full diplomatic ties at a summit.", "Reuters"),
    (37, "ODISHA, INDIA", "Cyclone Akvan weakens to a depression; 300,000+ evacuated.", "IMD"),
    (38, "KUNO, INDIA", "A cheetah gives birth to four cubs in the wild; population reaches 62.", "Reuters"),
    (39, "SEOUL", "Education minister quits over an AI exam-cheating scandal.", "Reuters"),
    (40, "BEIJING", "China–Japan ties worsen over Taiwan and critical minerals.", "Reuters"),
    (41, "DHAKA", "Deadly protests over the exiled former leader.", "Reuters"),
    (42, "COOK ISLANDS", "Cyclone Xavier weakens to Category 1; emergency status stays.", "MetService"),
    (43, "GENEVA", "UN talks on AI weapons end with no binding rules.", "AFP"),
    (44, "ORBIT", "Earth gains a 'mini-moon', 2026 QQ8, a 2-metre asteroid.", "CNN"),
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
    ("Europe", 9, (178, 28, 28)), ("N. America", 9, (30, 64, 140)),
    ("Latin America", 6, (34, 110, 60)), ("Middle East", 5, (166, 110, 10)),
    ("Africa", 5, (120, 72, 20)), ("Asia", 6, (140, 40, 120)),
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
        draw.rectangle([cx + s * 0.14, cy + s * 0.05, cx + s * 0.4, cy + s * 0.42], fill=GREY)
        for dx, dy in [(-0.5, -0.55), (-0.1, -0.7), (0.35, -0.6), (0.55, -0.3),
                       (-0.55, -0.25), (0.1, -0.35)]:
            draw.line([(cx, cy - s * 0.2), (cx + dx * s, cy + dy * s)], fill=RED, width=2)
        draw.ellipse([cx - s * 0.14, cy - s * 0.42, cx + s * 0.14, cy - s * 0.14],
                     fill=(240, 180, 40), outline=RED)
    elif kind == "ship":
        draw.polygon([(cx - s * 0.45, cy + s * 0.25), (cx + s * 0.45, cy + s * 0.25),
                      (cx + s * 0.3, cy + s * 0.42), (cx - s * 0.3, cy + s * 0.42)], fill=col)
        draw.rectangle([cx - s * 0.2, cy - s * 0.05, cx + s * 0.2, cy + s * 0.25], fill=GREY)
        draw.line([(cx, cy - s * 0.45), (cx, cy - s * 0.05)], fill=col, width=2)
        draw.polygon([(cx, cy - s * 0.45), (cx + s * 0.3, cy - s * 0.32),
                      (cx, cy - s * 0.2)], fill=RED)
        draw.line([(cx - s * 0.45, cy + s * 0.5), (cx + s * 0.45, cy + s * 0.5)],
                  fill=BLUE2, width=2)
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
        draw.line(pts, fill=RED, width=3, joint="curve")
        draw.polygon([(cx + s * 0.45, cy + s * 0.35), (cx + s * 0.45, cy + s * 0.2),
                      (cx + s * 0.3, cy + s * 0.35)], fill=RED)
        draw.line([(cx - s * 0.5, cy + s * 0.45), (cx + s * 0.5, cy + s * 0.45)],
                  fill=GREY, width=1)
    elif kind == "flag":
        draw.line([(cx - s * 0.3, cy - s * 0.45), (cx - s * 0.3, cy + s * 0.45)],
                  fill=col, width=2)
        for i, c in enumerate([INK, (255, 255, 255), INK, (255, 255, 255)]):
            draw.rectangle([cx - s * 0.3, cy - s * 0.45 + i * s * 0.18,
                            cx + s * 0.4, cy - s * 0.45 + (i + 1) * s * 0.18], fill=c)
        draw.rectangle([cx - s * 0.3, cy - s * 0.45, cx + s * 0.4, cy + s * 0.27],
                       outline=INK)
    elif kind == "quake":
        pts = [(cx - s * 0.5, cy), (cx - s * 0.3, cy - s * 0.3), (cx - s * 0.12, cy + s * 0.25),
               (cx + s * 0.05, cy - s * 0.35), (cx + s * 0.22, cy + s * 0.2),
               (cx + s * 0.4, cy - s * 0.1), (cx + s * 0.5, cy)]
        draw.line(pts, fill=RED, width=2, joint="curve")
        draw.line([(cx - s * 0.5, cy + s * 0.4), (cx + s * 0.5, cy + s * 0.4)],
                  fill=GREY, width=1)
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
            draw.line([(x1, y1), (x2, y2)], fill=RED, width=2)
    elif kind == "planet":
        draw.ellipse([cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3],
                     fill=(200, 170, 120), outline=INK)
        draw.ellipse([cx - s * 0.5, cy - s * 0.12, cx + s * 0.5, cy + s * 0.12],
                     outline=BLUE2, width=2)


# ---------------------------------------------------------------- maps
def latlon_to_xy(lat, lon, x0, y0, w, h):
    x = x0 + (lon + 180.0) / 360.0 * w
    y = y0 + (90.0 - lat) / 180.0 * h
    return x, y


CONTINENTS = [
    # North America
    [(62, 62), (120, 42), (200, 46), (258, 62), (278, 92), (238, 122),
     (218, 162), (180, 182), (148, 202), (118, 182), (88, 142), (58, 102)],
    # Greenland
    [(300, 22), (338, 16), (358, 36), (330, 56), (300, 46)],
    # South America
    [(230, 232), (280, 222), (320, 242), (330, 292), (300, 352),
     (270, 392), (250, 342), (225, 282)],
    # Europe
    [(470, 62), (520, 46), (560, 62), (580, 92), (540, 112),
     (510, 132), (480, 122), (460, 92)],
    # Africa
    [(480, 152), (540, 142), (590, 162), (610, 202), (590, 262),
     (560, 312), (530, 332), (500, 282), (480, 222), (470, 182)],
    # Asia
    [(600, 52), (700, 42), (800, 52), (900, 72), (950, 112), (920, 162),
     (880, 202), (840, 242), (800, 282), (760, 262), (720, 222),
     (680, 182), (640, 142), (610, 102)],
    # Australia
    [(820, 332), (880, 322), (920, 342), (900, 382), (850, 392), (820, 362)],
]


def draw_world_map(draw, x0, y0, w, h):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=SEA, outline=INK, width=1)
    for poly in CONTINENTS:
        pts = [(x0 + px / 1000.0 * w, y0 + py / 500.0 * h) for px, py in poly]
        draw.polygon(pts, fill=LAND, outline=(150, 140, 115))
    # graticule
    for gx in range(1, 6):
        x = x0 + gx * w / 6.0
        draw.line([(x, y0), (x, y0 + h)], fill=(190, 210, 226), width=1)
    for gy in range(1, 3):
        y = y0 + gy * h / 3.0
        draw.line([(x0, y), (x0 + w, y)], fill=(190, 210, 226), width=1)
    # pins 1-12
    f = font(SANSB, 9)
    for num, (lat, lon) in sorted(PINS.items()):
        if lat is None:
            continue
        px, py = latlon_to_xy(lat, lon, x0, y0, w, h)
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


def draw_turkiye(draw, x0, y0, w, h):
    """Stylised Türkiye with Antalya pin and the draft-text box."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    poly = [(0.05, 0.28), (0.22, 0.12), (0.45, 0.08), (0.68, 0.12), (0.88, 0.18),
            (0.95, 0.38), (0.86, 0.55), (0.68, 0.68), (0.48, 0.72), (0.28, 0.66),
            (0.12, 0.58), (0.04, 0.42)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    draw.polygon(pts, fill=LAND2, outline=INK)
    draw.text((x0 + 6, y0 + 4), "TÜRKIYE", font=font(SANSB, 9), fill=INK)
    draw.text((x0 + w - 52, y0 + 4), "ANTALYA", font=font(SANSB, 8), fill=RED)
    # Antalya pin on the south coast
    ax, ay = x0 + 0.38 * w, y0 + 0.66 * h
    draw.ellipse([ax - 6, ay - 6, ax + 6, ay + 6], fill=RED, outline=(255, 255, 255), width=1)
    # sea label
    draw.text((x0 + 8, y0 + h - 16), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    # draft-text box
    bx, by = x0 + 6, y0 + h - 44
    draw.rectangle([bx, by, x0 + w - 6, y0 + h - 6], fill=(255, 255, 255), outline=RED, width=1)
    draw.text((bx + 5, by + 3), "DRAFT TEXT:", font=font(SANSB, 8), fill=RED)
    draw.text((bx + 5, by + 15), "fossil fuels NOT MENTIONED", font=font(SANSB, 9), fill=INK)
    draw.text((bx + 5, by + 27), "→ NO DEAL", font=font(SANSB, 9), fill=RED)


def draw_libya(draw, x0, y0, w, h):
    """Stylised Libya / Mediterranean with burning ship and arrow.
    Everything stays inside the box (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    poly = [(0.08, 0.30), (0.30, 0.22), (0.55, 0.20), (0.85, 0.24), (0.92, 0.45),
            (0.80, 0.72), (0.62, 0.88), (0.38, 0.86), (0.18, 0.68), (0.06, 0.50)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    draw.polygon(pts, fill=LAND2, outline=INK)
    draw.text((x0 + 6, y0 + 3), "LIBYA", font=font(SANSB, 9), fill=INK)
    draw.text((x0 + 6, y0 + h - 13), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    # Benghazi pin, north-east coast
    bx, by = x0 + 0.80 * w, y0 + 0.30 * h
    draw.ellipse([bx - 5, by - 5, bx + 5, by + 5], fill=RED, outline=(255, 255, 255), width=1)
    draw.text((bx - 30, by - 13), "BENGHAZI", font=font(SANSB, 7), fill=RED)
    # burning ship offshore, upper middle of the box
    sx, sy = x0 + 0.45 * w, y0 + 0.42 * h
    draw.polygon([(sx - 14, sy + 3), (sx + 14, sy + 3), (sx + 9, sy + 10), (sx - 9, sy + 10)],
                 fill=INK)
    draw.rectangle([sx - 6, sy - 5, sx + 6, sy + 3], fill=GREY)
    for dx, dy in [(-5, -11), (0, -14), (5, -10)]:
        draw.line([(sx, sy - 5), (sx + dx, sy + dy)], fill=RED, width=2)
    draw.ellipse([sx - 4, sy - 11, sx + 4, sy - 3], fill=(240, 180, 40), outline=RED)
    # red arrow: drone path to the ship, inside the box
    draw.line([(sx - 34, sy - 16), (sx - 8, sy - 6)], fill=RED, width=2)
    draw.polygon([(sx - 8, sy - 6), (sx - 16, sy - 10), (sx - 13, sy - 1)], fill=RED)
    draw.text((sx - 40, sy - 26), "SEA DRONE", font=font(SANSB, 7), fill=RED)


def draw_house_chart(draw, x0, y0, w, h):
    """US House seats: 258 Dem (blue) vs 177 Rep (red), stacked bar + Capitol.
    Everything stays inside the box (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    draw.text((x0 + 6, y0 + 3), "US HOUSE  ·  435 SEATS", font=font(SANSB, 9), fill=INK)
    # Capitol dome, small, top right
    cx, cy = x0 + w - 34, y0 + 24
    draw.rectangle([cx - 22, cy, cx + 22, cy + 9], fill=(255, 255, 255), outline=INK)
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 1], fill=(255, 255, 255), outline=INK)
    draw.line([(cx, cy - 14), (cx, cy - 10)], fill=INK, width=2)
    # stacked bar
    bx, by, bw, bh = x0 + 10, y0 + 32, w - 20, 15
    dem_w = bw * 258 / 435
    draw.rectangle([bx, by, bx + dem_w, by + bh], fill=BLUE)
    draw.rectangle([bx + dem_w, by, bx + bw, by + bh], fill=RED)
    draw.rectangle([bx, by, bx + bw, by + bh], outline=INK, width=1)
    f = font(SANSB, 9)
    draw.text((bx + 5, by + 3), "258 DEM", font=f, fill=(255, 255, 255))
    t = "177 REP"
    draw.text((bx + bw - draw.textlength(t, font=f) - 5, by + 3), t, font=f,
              fill=(255, 255, 255))
    draw.text((x0 + 10, by + bh + 3), "LARGEST MAJORITY SINCE 1992",
              font=font(SANSB, 9), fill=RED)


# ---------------------------------------------------------------- render
def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    MX = 14  # side margin
    RX = W - MX

    # ---- masthead ----
    y = 10
    d.text((MX, y), "Sunday 22 November 2026", font=font(SERIFB, 40), fill=INK)
    t = "ONE DAY OF WORLD NEWS, ONE PICTURE"
    d.text((RX - tw(d, t, font(SANSB, 10)), y + 8), t, font=font(SANSB, 10), fill=RED)
    t2 = "THE WORLD ON A SUNDAY"
    d.text((RX - tw(d, t2, font(SANS, 9)), y + 24), t2, font=font(SANS, 9), fill=GREY)
    y = 56
    d.text((MX, y), "44 STORIES  ·  9 REGIONS  ·  19 FIELDS  ·  ALL FROM THIS SUNDAY",
           font=font(SANSB, 12), fill=INK)
    y = 74
    rule(d, MX, RX, y, INK, 2)
    rule(d, MX, RX, y + 3, INK, 1)

    # ---- THE DAY IN UTC ----
    y = 84
    d.rectangle([MX, y, RX, y + 46], fill=PAPER2, outline=INK, width=1)
    d.text((MX + 6, y + 3), "THE DAY IN UTC", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 7.0
    for i, (t, txt) in enumerate(UTC_STRIP):
        x = MX + 6 + i * col_w
        d.text((x, y + 15), t, font=font(SANSB, 11), fill=RED)
        para(d, x, y + 29, txt, font(SANS, 8), INK, col_w - 6, lh=9, max_lines=2)

    # ---- THE DAY IN NUMBERS ----
    y = 136
    d.rectangle([MX, y, RX, y + 46], fill=(255, 255, 255), outline=INK, width=1)
    d.text((MX + 6, y + 3), "THE DAY IN NUMBERS", font=font(SANSB, 9), fill=RED)
    col_w = (RX - MX - 12) / 6.0
    for i, (num, txt) in enumerate(NUMBERS):
        x = MX + 6 + i * col_w
        d.text((x, y + 15), num, font=font(SERIFB, 17), fill=INK)
        para(d, x, y + 33, txt, font(SANS, 8), GREY, col_w - 6, lh=9, max_lines=2)

    # ---- 3 big leads ----
    y = 188
    lead_h = 176
    col_w = (RX - MX - 12) / 3.0
    for i, (num, kick, head, deck, src, conf) in enumerate(LEADS):
        x = MX + i * (col_w + 6)
        d.rectangle([x, y, x + col_w, y + lead_h], outline=INK, width=1)
        d.rectangle([x, y, x + col_w, y + 20], fill=REDBG)
        d.text((x + 6, y + 4), f"#{num}  {kick}", font=font(SANSB, 9), fill=(255, 255, 255))
        d.text((x + 6, y + 24), head, font=font(SERIFB, 19), fill=INK)
        yy = y + 48
        para(d, x + 6, yy, deck, font(SANS, 10), INK, col_w - 12, lh=12, max_lines=3)
        # illustration
        ih = 62
        iy = y + lead_h - ih - 22
        if num == 1:
            draw_turkiye(d, x + 6, iy, col_w - 12, ih)
        elif num == 2:
            draw_libya(d, x + 6, iy, col_w - 12, ih)
        else:
            draw_house_chart(d, x + 6, iy, col_w - 12, ih)
        # source + badge
        sy = y + lead_h - 16
        d.text((x + 6, sy + 2), src, font=font(SANS, 8), fill=GREY)
        badge(d, x + col_w - 62, sy, conf)

    # ---- 10 medium cards, 2 rows of 5 ----
    y = 370
    card_w = (RX - MX - 16) / 5.0
    card_h = 92
    for row in range(2):
        for col in range(5):
            m = MEDIUM[row * 5 + col]
            num, kick, head, deck, src, conf, ic = m
            x = MX + col * (card_w + 4)
            yy = y + row * (card_h + 4)
            d.rectangle([x, yy, x + card_w, yy + card_h], fill=(255, 255, 255),
                        outline=LINE, width=1)
            d.text((x + 5, yy + 3), f"{num}  {kick}", font=font(SANSB, 7), fill=RED)
            icon(d, ic, x + 18, yy + 34, 26)
            d.text((x + 38, yy + 24), "", font=font(SANS, 8), fill=INK)
            para(d, x + 38, yy + 20, head, font(SANSB, 10), INK, card_w - 44, lh=11,
                 max_lines=2)
            para(d, x + 5, yy + 52, deck, font(SANS, 8), INK, card_w - 10, lh=10,
                 max_lines=2)
            sy = yy + card_h - 13
            d.text((x + 5, sy + 1), src, font=font(SANS, 7), fill=GREY)
            badge(d, x + card_w - 60, sy, conf)

    # ---- STORIES BY REGION ----
    y = 562
    d.text((MX, y), "STORIES BY REGION", font=font(SANSB, 9), fill=RED)
    bx = MX + 108
    total = sum(n for _, n, _ in REGIONS)
    bar_w = RX - bx
    x = bx
    for name, n, col in REGIONS:
        wseg = bar_w * n / total
        d.rectangle([x, y, x + wseg - 1, y + 12], fill=col)
        x += wseg
    # legend line under the bar (segment labels would collide on narrow bars)
    y = 578
    legend = "  ·  ".join(f"{name} {n}" for name, n, _ in REGIONS)
    d.text((bx, y), legend, font=font(SANS, 8), fill=INK)

    # ---- WHERE IT HAPPENED ----
    y = 592
    d.text((MX, y), "WHERE IT HAPPENED  ·  PINS 1–13  (13 = IN ORBIT)",
           font=font(SANSB, 10), fill=INK)
    draw_world_map(d, MX, y + 16, RX - MX, 118)

    # ---- ALSO ON ----
    y = 736
    d.text((MX, y), "ALSO ON SUNDAY 22 NOVEMBER — 31 MORE STORIES",
           font=font(SANSB, 10), fill=INK)
    rule(d, MX, RX, y + 15, INK, 1)
    y = 756
    col_w = (RX - MX - 12) / 2.0
    row_h = 11
    f_head = font(SANS, 9)
    f_bold = font(SANSB, 9)
    f_src = font(SANS, 7)
    left = SMALL[:16]
    right = SMALL[16:]
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
    assert max_y <= 934, f"ALSO ON overflow: ends at y={max_y}"

    # ---- DATE CHECK + HOW SURE ----
    y = 934
    d.rectangle([MX, y, RX, y + 60], fill=(255, 255, 255), outline=RED, width=2)
    d.text((MX + 6, y + 2), "DATE CHECK — LEFT OUT AS OLDER NEWS",
           font=font(SANSB, 9), fill=RED)
    para(d, MX + 6, y + 14,
         "Shenzhen summit (19–20 Nov) · ICJ Rohingya ruling (19 Nov) · GTA VI $3.79bn "
         "(19–20 Nov) · Anthropic IPO $93.5bn (20 Nov) · 'El Chapo Isidro' arrested "
         "(20–21 Nov) · Akvan landfall (20 Nov) · Banda Sea M6.8 (21 Nov)",
         font(SANS, 8), INK, RX - MX - 12, lh=10, max_lines=1)
    d.text((MX + 6, y + 32),
           "NOT YET: ATP final (23 Nov) · BepiColombo separation (9–10 Dec)",
           font=font(SANSB, 8), fill=INK)
    d.text((MX + 6, y + 46), "HOW SURE ARE WE?  ",
           font=font(SANSB, 8), fill=INK)
    xx = MX + 6 + tw(d, "HOW SURE ARE WE?  ", font(SANSB, 8))
    d.text((xx, y + 46), "CONFIRMED = 2+ outlets · OFFICIAL = on the record · REPORTED = one outlet",
           font=font(SANS, 8), fill=GREY)

    # ---- footer ----
    y = 998
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
