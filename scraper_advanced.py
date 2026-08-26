"""Advanced match stats from footywire, the real Score Involvements source.

    python scraper_advanced.py 2026
    python scraper_advanced.py 2015 2025      # inclusive range

Writes one CSV per season to data_advanced/advanced_<season>.csv.

Why this exists. `features.add_row_stats()` computes a column called
`Score_Involvements` as Goals + Goal.Assists + Marks.Inside.50 + Inside.50s.
That is a model feature, and it is a perfectly good one, but it is NOT the
AFL's Score Involvements stat and it never was. It double counts (a mark inside
50 converted to a goal scores twice for one act) and it omits the largest real
component (any possession in a scoring chain). The two land in the same 6 to 9
per game range for a midfielder, which is exactly why the collision survived:
the wrong number looks right. `round_bests.py` already refuses to rank the
column for this reason. The dashboard, until this file existed, did not.

The engineered column keeps its name and its definition, because it is one of
the 93 entries in `predictions/features.pkl` and renaming it breaks
`predict_2026.py` against the trained model. The real stat arrives beside it
under `Score_Involvements_Actual` and the user-facing label belongs to the real
one.

Coverage floor is 2015, measured rather than assumed: footywire's advanced
table carries no SI column for 2003, 2010, 2011, 2012, 2013 or 2014, and does
carry it for 2015 onward. A season before the floor is refused rather than
written empty, because a file of nulls is indistinguishable from a failed run.

Round numbering. footywire calls Opening Round "Round 0", so its round number
runs one BEHIND the AFLTables raw Round_num that the rest of this repo uses
from 2024 on. The label is recorded verbatim as `Round_fw` and no offset is
applied here; build_score_involvements.py maps each season's rounds positionally
onto the game_level file's own, which needs no per-season constant.
"""

import os
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

from club_aliases import canonical_club

BASE = "https://www.footywire.com/afl/footy"
OUT_DIR = "data_advanced"
SI_FLOOR = 2015
DELAY = 0.4
TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; brownlow-engine/1.0)"}

# The advanced table's own column codes, kept as scraped so a reader can check
# them against the page. SI is the one this module exists for; the rest are
# free once the page is open and the repo holds none of them.
WANTED = ('CP', 'UP', 'ED', 'DE%', 'CM', 'GA', 'MI5', '1%', 'BO', 'CCL',
          'SCL', 'SI', 'MG', 'TO', 'ITC', 'T5', 'TOG%')

RENAME = {
    'SI': 'Score_Involvements_Actual',
    'MG': 'Metres_Gained',
    'ITC': 'Intercepts',
    'CCL': 'Centre_Clearances',
    'SCL': 'Stoppage_Clearances',
    'ED': 'Effective_Disposals',
    'DE%': 'Disposal_Efficiency_Pct',
    'CM': 'Contested_Marks_fw',
    'GA': 'Goal_Assists_fw',
    'MI5': 'Marks_Inside_50_fw',
    'CP': 'Contested_Possessions_fw',
    'UP': 'Uncontested_Possessions_fw',
    '1%': 'One_Percenters_fw',
    'BO': 'Bounces_fw',
    'TO': 'Turnovers',
    'T5': 'Tackles_Inside_50',
    'TOG%': 'Time_On_Ground_Pct',
}

KNOWN_CLUBS = {
    'Adelaide', 'Brisbane Lions', 'Carlton', 'Collingwood', 'Essendon',
    'Fremantle', 'Geelong', 'Gold Coast', 'Greater Western Sydney',
    'Hawthorn', 'Melbourne', 'North Melbourne', 'Port Adelaide', 'Richmond',
    'St Kilda', 'Sydney', 'West Coast', 'Western Bulldogs',
}

_MONTHS = {m: i for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    time.sleep(DELAY)
    return r.text


def _heading_to_club(heading):
    """'Greater Western Sydney Match Statistics' club name to the archive's."""
    name = heading.strip().title()
    # canonical_club knows the nicknamed forms; the few it does not are the
    # clubs whose slug carries a nickname the archive never uses.
    fixed = {
        'West Coast Eagles': 'West Coast', 'Hawthorn Hawks': 'Hawthorn',
        'Sydney Swans': 'Sydney', 'Adelaide Crows': 'Adelaide',
        'Brisbane Lions': 'Brisbane Lions', 'Carlton Blues': 'Carlton',
        'Collingwood Magpies': 'Collingwood', 'Essendon Bombers': 'Essendon',
        'Fremantle Dockers': 'Fremantle', 'Geelong Cats': 'Geelong',
        'Gold Coast Suns': 'Gold Coast', 'Gws Giants': 'Greater Western Sydney',
        'Greater Western Sydney Giants': 'Greater Western Sydney',
        # Heading forms, measured across 2015-2026 by sampling 9 matches a
        # season: footywire's table headings use short club names, and exactly
        # two of the eighteen differ from what the archive stores.
        'Gws': 'Greater Western Sydney', 'Brisbane': 'Brisbane Lions',
        'Kangaroos': 'North Melbourne', 'Sydney Swans Swans': 'Sydney',
        'Melbourne Demons': 'Melbourne', 'North Melbourne Kangaroos': 'North Melbourne',
        'Port Adelaide Power': 'Port Adelaide', 'Richmond Tigers': 'Richmond',
        'St Kilda Saints': 'St Kilda', 'Western Bulldogs': 'Western Bulldogs',
    }.get(name, name)
    club = canonical_club(fixed)
    if club not in KNOWN_CLUBS:
        raise ValueError(
            f"heading {heading!r} maps to {club!r}, which the archive does not "
            f"use. Add it to the map above. Raised here rather than at the end "
            f"of the season build, because that check costs 206 requests to "
            f"report the same thing.")
    return club


def fixture(season):
    """Every match of a season as (mid, round_label, date), home-and-away and
    finals alike. Finals are kept and labelled; the consumer filters."""
    html = _get(f"{BASE}/ft_match_list?year={season}")
    soup = BeautifulSoup(html, 'html.parser')
    out, rnd = [], None
    for tr in soup.find_all('tr'):
        a = tr.find('a', href=re.compile(r'ft_match_statistics\?mid=\d+'))
        if a is None:
            txt = tr.get_text(' ', strip=True)
            m = re.match(r'^(Round \d+|Opening Round|Wildcard \w+|'
                         r'Finals? Week \d+|\w+ Final)\b', txt)
            # A nav block repeats every round name on one line; a real heading
            # row is short. Length is the only thing that separates them.
            if m and len(txt) < 40:
                rnd = m.group(1)
            continue
        cells = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
        if not cells:
            continue
        mid = int(re.search(r'mid=(\d+)', a['href']).group(1))
        date = _parse_date(cells[0], season)
        # The page's nav block is itself a table row and it carries the first
        # match link, so it reaches here before any round heading has been
        # seen. A real fixture row always leads with a parseable date; the nav
        # row never does, and that is the only thing that separates the two.
        if date is None:
            continue
        out.append({'mid': mid, 'Round_fw': rnd, 'Date': date})
    seen, uniq = set(), []
    for r in out:
        if r['mid'] not in seen:
            seen.add(r['mid'])
            uniq.append(r)
    return uniq


def _parse_date(cell, season):
    """'Thu 5 Mar 7:30pm' to an ISO date. Returns None when the cell is not a
    date, which happens on the odd fixture row carrying a placeholder."""
    m = re.search(r'(\d{1,2})\s+([A-Z][a-z]{2})', cell)
    if not m:
        return None
    day, mon = int(m.group(1)), _MONTHS.get(m.group(2))
    if mon is None:
        return None
    return f"{season:04d}-{mon:02d}-{day:02d}"


_HEADING_RE = re.compile(r'([A-Z][A-Za-z \.]+?) Match Statistics \(Sorted')


def match_rows(mid):
    """Every player's advanced line from one match.

    The team comes from the table's own heading, never from the player's
    profile link. footywire's `pp-<club>--<name>` href names the club the
    player is at NOW, not the club he played this match for, so reading the
    team from it silently reassigns every player who later changed clubs. On
    the 2015 opening round that put Dangerfield, Jeremy Cameron and Isaac Smith
    in Geelong's table and left the season joining at 62%.
    """
    html = _get(f"{BASE}/ft_match_statistics?mid={mid}&advv=Y")
    soup = BeautifulSoup(html, 'html.parser')
    headings = _HEADING_RE.findall(html)
    rows, tables_seen = [], []
    for tb in soup.find_all('table'):
        # footywire nests the stats table inside two layout tables, and
        # find_all('tr') on a wrapper returns the inner rows too, so every
        # player would be counted once per level. Three levels, three copies:
        # the first run of this scraper wrote exactly 3x the expected rows.
        # Only the innermost table, the one holding no table of its own, is
        # the real one.
        if tb.find('table') is not None:
            continue
        trs = tb.find_all('tr')
        head = None
        for tr in trs:
            txts = [td.get_text(strip=True) for td in tr.find_all('td')]
            if txts[:1] == ['Player'] and 'SI' in txts:
                head = txts
                break
        if head is None:
            continue
        # Nth stats table belongs to the Nth heading, home side first.
        idx = len([t for t in tables_seen])
        tables_seen.append(tb)
        if idx >= len(headings):
            raise ValueError(
                f"mid {mid}: stats table {idx + 1} has no matching "
                f"'<club> Match Statistics' heading; headings found: {headings}")
        team = _heading_to_club(headings[idx])
        for tr in trs:
            tds = tr.find_all('td')
            txts = [td.get_text(strip=True) for td in tds]
            if len(txts) != len(head) or txts[0] == 'Player':
                continue
            a = tds[0].find('a', href=True)
            if not a or 'pp-' not in a['href']:
                continue
            _, _, name_slug = a['href'].split('pp-')[1].partition('--')
            rec = {'Team': team,
                   'Player_fw': name_slug.replace('-', ' ').title()}
            for code in WANTED:
                if code in head:
                    rec[RENAME[code]] = txts[head.index(code)]
            rows.append(rec)
    return rows


def build(season, out_dir=OUT_DIR):
    if season < SI_FLOOR:
        raise ValueError(
            f"{season} is before the measured Score Involvements floor of "
            f"{SI_FLOOR}; footywire's advanced table carries no SI column for "
            f"it, and writing a file of nulls would look like a failed run")
    fx = fixture(season)
    print(f"{season}: {len(fx)} matches in the fixture", flush=True)
    frames = []
    for i, m in enumerate(fx, 1):
        try:
            rows = match_rows(m['mid'])
        except Exception as exc:
            print(f"   mid {m['mid']} FAILED: {exc}", flush=True)
            continue
        if not rows:
            print(f"   mid {m['mid']} returned no rows", flush=True)
            continue
        d = pd.DataFrame(rows)
        d['Season'] = season
        d['Round_fw'] = m['Round_fw']
        d['Date'] = m['Date']
        d['mid'] = m['mid']
        frames.append(d)
        if i % 25 == 0:
            print(f"   {i}/{len(fx)}", flush=True)
    if not frames:
        raise RuntimeError(f"{season}: no rows scraped at all")
    out = pd.concat(frames, ignore_index=True)
    for c in out.columns:
        if c in ('Team', 'Player_fw', 'Round_fw', 'Date'):
            continue
        out[c] = pd.to_numeric(out[c], errors='coerce')
    # A club slug this module does not know title-cases to something the
    # archive has never heard of and then silently drops every one of that
    # club's rows at join time. GWS did exactly that on the first run: 529
    # rows, one whole club, gone with no error anywhere.
    unknown = sorted(set(out['Team']) - set(KNOWN_CLUBS))
    if unknown:
        raise ValueError(
            f"{season}: club name(s) the archive does not use: {unknown}. "
            f"Add them to _slug_to_club's map before trusting this file")

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"advanced_{season}.csv")
    out.to_csv(path, index=False)
    miss = int(out['Score_Involvements_Actual'].isna().sum())
    print(f"{season}: wrote {path}, {len(out):,} player-games, "
          f"{out['mid'].nunique()} matches, {miss} null SI", flush=True)
    return path


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    lo = int(argv[0])
    hi = int(argv[1]) if len(argv) > 1 else lo
    for season in range(lo, hi + 1):
        build(season)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
