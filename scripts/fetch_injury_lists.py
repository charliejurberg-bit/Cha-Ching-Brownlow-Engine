"""Fetch the AFL's weekly published injury list for a whole home and away season.

    python scripts/fetch_injury_lists.py            # 2026
    python scripts/fetch_injury_lists.py --season 2026 --refetch

Writes the tracked `data_injury/injury_list_<season>.csv`, one row per player
per round listed, exactly as the AFL published it. Raw HTML is cached under the
gitignored `data_injury/raw/<season>/` and is a pure fetch cache.

THIS IS THE ONLY SOURCE IN THE REPO THAT SEPARATES INJURY FROM OMISSION
Every other file records who played. None of them records WHY a player did not,
so a count of players used, or of changes week to week, cannot tell a hamstring
from a form drop. Measured on 2026: Hawthorn used 40 players, equal third most
in the league, and lost only 126 games to injury, third fewest. That gap is
rotation. Sydney went the other way, 36 players used and 231 games lost. Any
claim about a club's injury toll needs this file, not a selection count.

THE SITE RESOLVES /news/<id>/<slug> BY ID AND IGNORES THE SLUG
A wrong ID does not 404. It serves the AFL home page with HTTP 200, and a bad
slug against a real ID serves that ID's article under the wrong name: asking
for .../1550784/...-r12 returns the R17 article with a 200. So the round number
in the URL proves nothing, article IDs are NOT interpolatable from the round
(the 2026 gaps run 3,215 to 5,557), and every page is verified against its own
<title> before it is parsed. A mismatch aborts the run.

ARTICLE IDS ARE PER SEASON AND MUST BE FOUND BY SEARCH
There is no working news search API on afl.com.au: /content/afl/news returns an
empty body, the /api/news/search path 404s, and the Internet Archive was
offline when this was built. The 2026 ids below were each found by searching
the exact headline "Medical room: The full AFL injury list, R<n>". A new season
means adding a new block to ARTICLE_IDS the same way. That is tedious once a
year and is the honest cost of the source having no index.

CLUB COMES FROM THE STRAP IMAGE, NEVER FROM TABLE ORDER
The club name appears in no heading next to its table. The only marker is the
strap image that precedes it, and the AFL changed the naming three times across
2026: `carlton.jpeg` early, `..._Straps-Badge-Refresh_CARL_FA-1x.jpg` later,
and the clubs' Indigenous names in Sir Doug Nicholls Round (`kuwarna`,
`walyalup`, `narrm`, `yartapuulti`, `euro-yroke`, `waalitj`). Two failures came
out of this and both were silent:

  - A first pass matched only `.jpg|.png`, so Carlton's `.jpeg` did not match
    and the "last image before this table" rule handed Carlton's AND
    Collingwood's tables to Brisbane.
  - Round 10's `kuwarna_2026.jpg` was unknown, and falling through to the
    previous club would have filed Adelaide's list under Brisbane.

So an unresolved filename RAISES. It never falls through to a neighbour. And
because a club mapping that is merely plausible is not good enough, the
resolved 18-club sequence is asserted against the AFL's alphabetical order on
every page. Table order is checked, not trusted.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'data_injury'

BASE = 'https://www.afl.com.au/news/{aid}/medical-room-the-full-afl-injury-list-{slug}'

# Round label -> article id. Labels are the AFL's own: 'OR' is Opening Round,
# then R1..R24. Add a season by searching each headline; see the docstring.
ARTICLE_IDS: dict[int, dict[str, int]] = {
    2026: {
        'OR': 1471556, 'R1': 1474771, 'R2': 1479593, 'R3': 1484108,
        'R4': 1487738, 'R5': 1491910, 'R6': 1497939, 'R7': 1502723,
        'R8': 1508056, 'R9': 1513224, 'R10': 1518239, 'R11': 1522891,
        'R12': 1528180, 'R13': 1532695, 'R14': 1537730, 'R15': 1542194,
        'R16': 1546646, 'R17': 1550784, 'R18': 1555832, 'R19': 1561100,
        'R20': 1566100, 'R21': 1571336, 'R22': 1576893, 'R23': 1582439,
        'R24': 1589445,
    },
}

# Newer straps carry an explicit club code.
BADGE_CODES = {
    'ADEL': 'Adelaide', 'BRIS': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FREM': 'Fremantle',
    'GEEL': 'Geelong', 'GCS': 'Gold Coast', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NM': 'North Melbourne',
    'PA': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WCE': 'West Coast', 'WB': 'Western Bulldogs',
}

# Older and Indigenous-round straps carry a name. MOST SPECIFIC FIRST:
# 'north-melbourne' must beat 'melbourne', 'port-adelaide' must beat
# 'adelaide', and 'western-bulldogs' must beat 'west-coast'.
STRAP_TOKENS: list[tuple[str, str]] = [
    ('kuwarna', 'Adelaide'), ('walyalup', 'Fremantle'), ('narrm', 'Melbourne'),
    ('yartapuulti', 'Port Adelaide'), ('euro-yroke', 'St Kilda'),
    ('euro_yroke', 'St Kilda'), ('waalitj', 'West Coast'),
    ('north-melbourne', 'North Melbourne'), ('port-adelaide', 'Port Adelaide'),
    ('western-bulldogs', 'Western Bulldogs'), ('west-coast', 'West Coast'),
    ('gws-giants', 'Greater Western Sydney'), ('gws', 'Greater Western Sydney'),
    ('gc-strap', 'Gold Coast'), ('gold-coast', 'Gold Coast'),
    ('stk-strap', 'St Kilda'), ('st-kilda', 'St Kilda'),
    ('adelaide', 'Adelaide'), ('brisbane', 'Brisbane Lions'),
    ('carlton', 'Carlton'), ('collingwood', 'Collingwood'),
    ('essendon', 'Essendon'), ('fremantle', 'Fremantle'),
    ('geelong', 'Geelong'), ('hawthorn', 'Hawthorn'),
    ('melbourne', 'Melbourne'), ('richmond', 'Richmond'), ('sydney', 'Sydney'),
]

ALPHABETICAL = [
    'Adelaide', 'Brisbane Lions', 'Carlton', 'Collingwood', 'Essendon',
    'Fremantle', 'Geelong', 'Gold Coast', 'Greater Western Sydney', 'Hawthorn',
    'Melbourne', 'North Melbourne', 'Port Adelaide', 'Richmond', 'St Kilda',
    'Sydney', 'West Coast', 'Western Bulldogs',
]

# .jpeg is in this list because leaving it out is exactly how Carlton and
# Collingwood were once filed under Brisbane.
IMG_RE = re.compile(
    r'photo-resources/[^"\']*?/([A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif))', re.I)
BADGE_RE = re.compile(r'Straps-Badge-Refresh_([A-Z]+)_FA')
TABLE_RE = re.compile(r'<table')


class ParseError(RuntimeError):
    """Raised rather than guessing. Every case here has produced wrong data."""


def resolve_club(filename: str) -> str:
    """Club from a strap image filename, or raise.

    Never falls back to the previous club: an unknown strap is a new naming
    scheme, and silently attributing its table to a neighbour is the failure
    this function exists to prevent.
    """
    badge = BADGE_RE.search(filename)
    if badge:
        code = badge.group(1)
        if code not in BADGE_CODES:
            raise ParseError(f'unknown club badge code {code!r} in {filename!r}')
        return BADGE_CODES[code]
    low = filename.lower()
    for token, club in STRAP_TOKENS:
        if token in low:
            return club
    raise ParseError(f'unresolved strap image {filename!r}: new naming scheme?')


def label_to_round(label: str) -> int:
    """AFL round label to the raw AFLTables Round_num.

    AFLTables numbers Opening Round as round 1 from 2024, so the AFL's R1 is
    raw 2 and its R24 is raw 25. This is the same offset CLAUDE.md records,
    applied in the direction that turns a label into the archive's key.
    """
    if label == 'OR':
        return 1
    return int(label[1:]) + 1


def parse_page(html: str, label: str) -> list[dict]:
    """Every injury row on one weekly page, with its club resolved and checked."""
    title_m = re.search(r'<title>([^<]*)</title>', html)
    title = title_m.group(1) if title_m else ''
    if f', {label}' not in title:
        raise ParseError(
            f'{label}: page title is {title!r}. The site resolves by id and '
            f'ignores the slug, so this is the wrong article or the home page.')

    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    if len(tables) != 18:
        raise ParseError(f'{label}: found {len(tables)} tables, expected 18')

    positions = [m.start() for m in TABLE_RE.finditer(html)]
    images = [(m.start(), m.group(1)) for m in IMG_RE.finditer(html)]

    rows: list[dict] = []
    sequence: list[str] = []
    for table, pos in zip(tables, positions):
        prior = [name for at, name in images if at < pos]
        if not prior:
            raise ParseError(f'{label}: a table has no strap image before it')
        club = resolve_club(prior[-1])
        sequence.append(club)
        for tr in table.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'])]
            if len(cells) < 3 or not cells[0] or cells[0].upper() == 'PLAYER':
                continue
            rows.append({
                'AFL_round': label,
                'Round_num': label_to_round(label),
                'Club': club,
                'Player_as_published': cells[0],
                'Injury': cells[1],
                'Estimated_return': cells[2],
            })

    if sequence != ALPHABETICAL:
        raise ParseError(
            f'{label}: club sequence is not the AFL\'s alphabetical order.\n'
            f'  got {sequence}')
    return rows


def fetch(season: int, refetch: bool = False, pause: float = 1.2) -> pd.DataFrame:
    ids = ARTICLE_IDS.get(season)
    if not ids:
        raise SystemExit(
            f'No article ids for {season}. They cannot be interpolated from the '
            f'round number and there is no news search API; search the headline '
            f'"Medical room: The full AFL injury list, R<n>" for each round and '
            f'add a {season} block to ARTICLE_IDS.')

    cache_dir = OUT_DIR / 'raw' / str(season)
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'

    rows: list[dict] = []
    for label, aid in ids.items():
        cached = cache_dir / f'{label}.html'
        if cached.exists() and not refetch:
            html = cached.read_text(encoding='utf-8', errors='ignore')
        else:
            slug = label.lower()
            response = session.get(BASE.format(aid=aid, slug=slug), timeout=30)
            response.raise_for_status()
            html = response.text
            cached.write_text(html, encoding='utf-8', errors='ignore')
            time.sleep(pause)
        page_rows = parse_page(html, label)
        rows.extend(page_rows)
        print(f'  {label:4s} ok  18 clubs in order, {len(page_rows):3d} listed')

    frame = pd.DataFrame(rows)
    if frame['Club'].nunique() != 18:
        raise ParseError(f'{frame["Club"].nunique()} clubs across the season')
    return frame


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--refetch', action='store_true',
                    help='ignore the HTML cache and pull every round again')
    args = ap.parse_args()

    print(f'AFL weekly injury lists, {args.season}')
    frame = fetch(args.season, refetch=args.refetch)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'injury_list_{args.season}.csv'
    frame.to_csv(out, index=False)
    print(f'\n{len(frame):,} entries over {frame["Round_num"].nunique()} rounds '
          f'-> {out.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
