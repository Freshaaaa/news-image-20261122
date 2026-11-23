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
    (-35, -8), (-37, -11), (-39, -15), (-40, -20), (-42, -23), (-46, -25),
    (-48, -27), (-52, -32), (-57, -35), (-58, -38), (-62, -41), (-65, -45),
    (-67, -49), (-69, -52), (-68, -55), (-66, -55), (-68, -52), (-70, -48),
    (-72, -42), (-73, -37), (-72, -30), (-70, -23), (-70, -18), (-75, -15),
    (-77, -12), (-80, -6), (-81, -1), (-80, 3), (-77, 5),
]
EUROPE = [
    (18, 70), (25, 71), (30, 70), (28, 66), (24, 62), (21, 59), (19, 55),
    (15, 54), (11, 57), (8, 57), (8, 54), (5, 53), (3, 51), (0, 50),
    (-2, 49), (-2, 47), (-4, 43), (-9, 43), (-9, 38), (-8, 37), (-6, 36),
    (-2, 36), (0, 39), (3, 42), (6, 43), (9, 44), (12, 42), (14, 40),
    (16, 38), (18, 40), (16, 42), (14, 45), (16, 44), (18, 42), (19, 41),
    (21, 40), (23, 39), (23, 37), (25, 38), (26, 40), (28, 41), (30, 42),
    (33, 44), (36, 45), (39, 46), (41, 46), (43, 45), (45, 44), (47, 45),
    (49, 46), (48, 48), (46, 51), (42, 54), (38, 57), (34, 59), (30, 61),
    (27, 63), (24, 66), (21, 68),
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
    (121, 28), (119, 24), (117, 22), (113, 22), (109, 19), (106, 12),
    (104, 9), (101, 6), (100, 2), (103, 1), (101, 5), (99, 9), (97, 13),
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
        draw.polygon(pts, fill=LAND, outline=(150, 140, 115))
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


def draw_turkiye(draw, x0, y0, w, h):
    """Türkiye with a readable coastline: Black Sea north, Mediterranean
    south with the Antalya bay, Aegean notches west. The draft-text box is
    a single line at the bottom so the map (and the Antalya pin) stay
    visible. Everything stays inside (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    poly = [(0.03, 0.36), (0.05, 0.26), (0.08, 0.19), (0.15, 0.16),
            (0.25, 0.15), (0.35, 0.17), (0.45, 0.15), (0.55, 0.17),
            (0.65, 0.15), (0.75, 0.17), (0.85, 0.19), (0.93, 0.23),
            (0.96, 0.29), (0.95, 0.36), (0.90, 0.44), (0.82, 0.50),
            (0.74, 0.54), (0.66, 0.58), (0.58, 0.54), (0.50, 0.50),
            (0.42, 0.48), (0.34, 0.46), (0.26, 0.44), (0.18, 0.42),
            (0.10, 0.40), (0.06, 0.38), (0.08, 0.34), (0.04, 0.32)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    draw.polygon(pts, fill=LAND2, outline=INK)
    draw.text((x0 + 6, y0 + 1), "TÜRKIYE", font=font(SANSB, 9), fill=INK)
    draw.text((x0 + 118, y0 + 1), "BLACK SEA", font=font(SANS, 7), fill=BLUE2)
    # Antalya pin on the south coast, at the bay dip
    ax, ay = x0 + 0.66 * w, y0 + 0.58 * h
    draw.ellipse([ax - 5, ay - 5, ax + 5, ay + 5], fill=RED, outline=(255, 255, 255), width=1)
    draw.text((ax + 8, y0 + 38), "ANTALYA", font=font(SANSB, 8), fill=RED)
    draw.text((x0 + 6, y0 + 39), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    # draft-text box: one line, bottom
    bx, by = x0 + 6, y0 + h - 14
    draw.rectangle([bx, by, x0 + w - 6, y0 + h - 3], fill=(255, 255, 255), outline=RED, width=1)
    draw.text((bx + 5, by + 2), "DRAFT TEXT: ", font=font(SANSB, 8), fill=RED)
    tx = bx + 5 + draw.textlength("DRAFT TEXT: ", font=font(SANSB, 8))
    draw.text((tx, by + 2), "fossil fuels NOT MENTIONED  →  NO DEAL",
              font=font(SANSB, 8), fill=INK)


def draw_libya(draw, x0, y0, w, h):
    """Libya / Mediterranean: sea on top, land below with the Gulf of
    Sidra dip, a BIG burning warship offshore in the sea, red SEA DRONE
    arrow, Benghazi pin on the north-east coast. Everything stays inside
    the box (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    # land: north coast with the Sidra gulf dip, extends past the bottom
    poly = [(0.02, 0.48), (0.10, 0.44), (0.20, 0.42), (0.30, 0.44),
            (0.40, 0.50), (0.48, 0.54), (0.55, 0.50), (0.62, 0.45),
            (0.70, 0.42), (0.78, 0.40), (0.86, 0.42), (0.94, 0.44),
            (0.98, 0.55), (0.98, 1.0), (0.0, 1.0), (0.0, 0.52)]
    pts = [(x0 + px * w, y0 + py * h) for px, py in poly]
    draw.polygon(pts, fill=LAND2, outline=INK)
    draw.text((x0 + 6, y0 + 2), "SEA DRONE", font=font(SANSB, 7), fill=RED)
    draw.text((x0 + w - 100, y0 + 2), "MEDITERRANEAN SEA", font=font(SANS, 7), fill=BLUE2)
    draw.text((x0 + 8, y0 + 44), "LIBYA", font=font(SANSB, 9), fill=INK)
    # Benghazi pin on the north-east coast
    bx, by = x0 + 0.70 * w, y0 + 0.42 * h
    draw.ellipse([bx - 5, by - 5, bx + 5, by + 5], fill=RED, outline=(255, 255, 255), width=1)
    draw.text((bx + 8, y0 + 20), "BENGHAZI", font=font(SANSB, 7), fill=RED)
    # BIG burning warship offshore, in the sea above the coast
    sx, sy = x0 + 0.45 * w, y0 + 20
    # smoke puffs above the fire
    draw.ellipse([sx - 5, sy - 19, sx + 1, sy - 14], fill=(120, 115, 105))
    draw.ellipse([sx + 1, sy - 18, sx + 7, sy - 13], fill=(140, 135, 125))
    # fire: orange core + red flame lines
    draw.ellipse([sx - 5, sy - 15, sx + 5, sy - 7], fill=(240, 180, 40), outline=RED)
    for dx, dy in [(-6, -17), (0, -18), (6, -16)]:
        draw.line([(sx, sy - 9), (sx + dx, sy + dy)], fill=RED, width=2)
    # superstructure + funnel + mast
    draw.rectangle([sx - 9, sy - 9, sx + 9, sy - 3], fill=GREY)
    draw.rectangle([sx - 13, sy - 7, sx - 7, sy - 3], fill=(60, 60, 60))
    draw.line([(sx + 5, sy - 9), (sx + 5, sy - 15)], fill=INK, width=2)
    # hull: dark, wider than tall
    draw.polygon([(sx - 17, sy - 3), (sx + 17, sy - 3), (sx + 12, sy + 6),
                  (sx - 12, sy + 6)], fill=INK)
    draw.line([(sx - 17, sy - 3), (sx + 17, sy - 3)], fill=(255, 255, 255), width=1)
    # waves under the hull
    for wy in (sy + 8, sy + 11):
        draw.line([(sx - 20, wy), (sx - 10, wy - 2), (sx, wy), (sx + 10, wy - 2),
                   (sx + 20, wy)], fill=BLUE2, width=1)
    # red arrow: drone path to the ship, from the upper left
    draw.line([(x0 + 30, y0 + 10), (sx - 19, sy - 7)], fill=RED, width=2)
    draw.polygon([(sx - 19, sy - 7), (sx - 27, sy - 11), (sx - 24, sy - 2)], fill=RED)


def draw_house_chart(draw, x0, y0, w, h):
    """US House seats: 258 Dem (blue) vs 177 Rep (red), stacked bar + Capitol.
    Everything stays inside the box (x0, y0, w, h)."""
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(226, 232, 238), outline=INK, width=1)
    draw.text((x0 + 6, y0 + 3), "US HOUSE  ·  435 SEATS", font=font(SANSB, 9), fill=INK)
    # Capitol dome, BIG and detailed, top right: columned base, drum,
    # ribbed dome, lantern + finial. Base sits just above the bar
    # (bar top = y0+32).
    cx = x0 + w - 32
    base_top = y0 + 24
    # dome: smooth half-ellipse polygon (offsets from cx, base_top)
    dome = [(-17, -6), (-16, -10), (-13, -14), (-9, -16), (-5, -18),
            (0, -18), (5, -18), (9, -16), (13, -14), (16, -10), (17, -6)]
    draw.polygon([(cx + dx, base_top + dy) for dx, dy in dome],
                 fill=(255, 255, 255), outline=INK)
    # ribs on the dome
    for dx, top in [(-11, -15), (-6, -17), (0, -18), (6, -17), (11, -15)]:
        draw.line([(cx + dx, base_top + top), (cx + dx, base_top - 7)],
                  fill=GREY, width=1)
    # lantern + finial
    draw.rectangle([cx - 4, base_top - 22, cx + 4, base_top - 18],
                   fill=(255, 255, 255), outline=INK)
    draw.ellipse([cx - 2, base_top - 24, cx + 2, base_top - 22], fill=INK)
    # drum
    draw.rectangle([cx - 13, base_top - 6, cx + 13, base_top],
                   fill=(255, 255, 255), outline=INK)
    # base with columns
    draw.rectangle([cx - 24, base_top, cx + 24, base_top + 8],
                   fill=(255, 255, 255), outline=INK)
    for dx in (-18, -12, -6, 0, 6, 12, 18):
        draw.line([(cx + dx, base_top + 1), (cx + dx, base_top + 7)],
                  fill=GREY, width=1)
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
