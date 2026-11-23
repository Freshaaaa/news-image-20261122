# Sunday 22 November 2026: 36 stories, 9 regions, 19 fields — COP31 collapses, Russian warship hit off Libya, Democrats take 258 seats

[![news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/Freshaaaa/news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/Freshaaaa/news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

One front page that sums up Sunday 22 November 2026 in a single image:
**36 stories, 9 regions, 19 fields** — every one dated that Sunday.

- **#1 COP31 collapses** (Antalya, Türkiye) — no deal on fossil fuels, with a map of Türkiye and the draft-text box.
- **#2 Russian warship hit off Libya** — a Ukrainian sea drone strikes the corvette Merkury at Benghazi, with a map of Libya.
- **#3 Democrats take 258 House seats** — largest majority since 1992, with a seats chart.
- Plus a UTC timeline, a numbers strip, 10 illustrated mid stories, a region bar, a numbered world map, 23 more stories, a DATE CHECK box, and a confidence legend (CONFIRMED / OFFICIAL / REPORTED).

## How it is built

`build-image.py` draws the whole page with PIL (DejaVu fonts, original vector
maps and drawings, no photographs, no network). It is deterministic: run it
twice and the bytes are identical.

```sh
python3 build-image.py        # writes entry.png (1024x1024, < 1 MiB)
mkdir -p out && MAKEFUN_OUTPUT_DIR=out node main.ts   # copies it to out/entry.png
```

## Sources

AP, Reuters, AFP, BBC, USGS, ESA, IMD, UKMTO, NEMA, WHO. Every story is
named with its source on the page.
