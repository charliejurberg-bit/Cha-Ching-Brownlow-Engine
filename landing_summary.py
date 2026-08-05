"""Landing summary artifact for the public front door.

Reads what predict_2026.py wrote and emits site/landing.json, the one file the
Next.js landing page parses for every live value it shows. That front end is a
separate repo (cha-ching-brownlow), where this file is committed as
data/landing.json and imported at build time.

There is no model here, no LLM call and no network access. Every field is a
number or a string formatted straight out of predictions/game_level_2026.csv,
predictions/season_2026.csv and data_2026/best_odds.csv.

RETROSPECTIVE, NOT FORWARD
Every number in the artifact describes rounds that have already been played.
The model scores completed games, so `Exp_Votes` is the vote total those
performances earned, not a call on games still to come. Field names and comments
here stay retrospective for that reason: no "predicted", no "forecast", no
"projected".

WHERE THE ARTIFACT GOES
site/landing.json is git tracked, which drafts/ is not, so it can be read from
outside this machine at all. This repo is public and raw reads answer 200,
verified 4 August 2026, so once pushed the artifact sits at
raw.githubusercontent.com/charliejurberg-bit/Cha-Ching-Brownlow-Engine/master/site/landing.json

Running this script changes nothing that is live, and committing it is necessary
rather than sufficient. The front end imports its own copy at data/landing.json
(app/page.tsx, a static import, no fetch of any kind), so the pushed file still
has to get across to that repo before a build will show these numbers.

SCHEMA
Fixed by components/landing/landing-data.ts in the front end repo, which
validates the file at module scope during the static prerender, so a missing or
wrong-typed field fails `next build` rather than shipping a broken page. This
writer matches that validator field for field:

    round            number   display round, never the raw AFLTables number
    brownlowNight    string   ISO date of the count
    leader.name      string   non-empty
    leader.votes     number   season Exp_Total_Votes, 1dp
    leader.clear     number   margin over second, 1dp
    leader.bestOdds  string   non-empty, so a missing price is EM_DASH
    chips[]          rank, name, team, votes
    ticker[]         match, and votes[] as [slot, SURNAME] pairs

`chips[].rank` is not optional. The validator calls asNumber on it, so omitting
it fails the build.

EXIT CODE
Non-zero on any failure, by one of two paths. A missing input file prints a `!`
line and returns 1. Every other fault, an empty round, a club with no
DISPLAY_CODES entry, a blank surname, raises and propagates as a traceback,
which also exits non-zero and says more than a swallowed message would. Nothing
is written in either case, so a failed run leaves the last good artifact in
place.
update.py logs a warning and carries on regardless of what it gets back, so this
exit code is the only honest signal the step emits.

Run standalone, or as step 10 of update.py:
    python landing_summary.py
"""

import json
import os
import sys

import pandas as pd

# Imported, never re-copied. _display_round already exists in three places
# (dashboard.py, draft_posts.py, streaks.py), each with its own copy of the
# season constant, and a fourth copy is a defect not a convenience.
from draft_posts import (
    GAME_LEVEL,
    SEASON,
    TOP_N_PER_GAME,
    _display_round,
    load_latest_round,
)

BEST_ODDS = "data_2026/best_odds.csv"

OUT_DIR = "site"
OUT_PATH = os.path.join(OUT_DIR, "landing.json")

# Count night, fixed. Not derived from anything in the data.
BROWNLOW_NIGHT = "2026-09-21"

# Hero chips: the round's three highest by Exp_Votes.
CHIPS_N = 3

# The one em dash this repo emits on purpose. It is a missing-value glyph, not
# prose, so the standing no-em-dash copy rule does not reach it. The front end
# validator rejects both an empty string and null for bestOdds and would fail
# the build, and the landing spec already renders an absent price as an em dash.
EM_DASH = "—"


# Club to display code. This is a DISPLAY map owned by the artifact, and it is
# deliberately not TEAM_ABBREV from brownlow_model.py.
#
# TEAM_ABBREV is a modelling map. It exists to parse the club names out of the
# coaches votes file so they can be merged onto the stats frame, and its codes
# are whatever that source happens to use. Reading it here coupled a rendered
# string on the public landing page to a merge key, so a future change to the
# feature pipeline could silently repaint the page, and it emitted the wrong
# codes anyway: MELB, BL, COLL, CARL and GEEL where the front end has always
# rendered MEL, BRI, COL, CAR and GEE, and eleven of its eighteen keys are not
# three letters at all, which breaches the format landing_spec.md states.
#
# Keys are the canonical club names, the same strings TEAM_ABBREV maps to and
# the same ones the CSVs carry, so the merge and the display still agree about
# what a club is called. Values are the codes the front end already ships.
#
# Ten codes are inherited from the committed data/landing.json and cannot be
# changed without repainting the page: BRI, CAR, COL, ESS, GEE, GWS, MEL, STK,
# WB, WCE. The other eight clubs never appear in that file, so they take the
# standard AFL code: ADE, FRE, GCS, HAW, NTH, PTA, RIC, SYD.
#
# WB is the one code that is not three letters. It is what data/landing.json
# ships for Western Bulldogs and changing it would repaint the page, so the
# shipped value wins over the stated format here.
DISPLAY_CODES = {
    'Adelaide': 'ADE',
    'Brisbane Lions': 'BRI',
    'Carlton': 'CAR',
    'Collingwood': 'COL',
    'Essendon': 'ESS',
    'Fremantle': 'FRE',
    'Geelong': 'GEE',
    'Gold Coast': 'GCS',
    'Greater Western Sydney': 'GWS',
    'Hawthorn': 'HAW',
    'Melbourne': 'MEL',
    'North Melbourne': 'NTH',
    'Port Adelaide': 'PTA',
    'Richmond': 'RIC',
    'St Kilda': 'STK',
    'Sydney': 'SYD',
    'West Coast': 'WCE',
    'Western Bulldogs': 'WB',
}


def _team_code(team):
    """Display code for a club name, or a hard failure.

    An unmapped club would otherwise reach the artifact as a blank or as a raw
    club name in a field the front end renders as a code, so it stops the run
    instead. The AFL adding a nineteenth club is exactly the case this is here
    to catch.
    """
    code = DISPLAY_CODES.get(str(team).strip())
    if code is None:
        raise ValueError(f"no DISPLAY_CODES entry for club {team!r}")
    return code


def _by_votes(frame):
    """Highest Exp_Votes first, ties broken on Player_Name.

    Same ordering as the draft 3/2/1, so the artifact and the draft post never
    disagree about who took a game.
    """
    return frame.sort_values(['Exp_Votes', 'Player_Name'], ascending=[False, True])


def _surname(value):
    """The stored surname, validated.

    Read from the Surname column and never split out of Player_Name. Players
    sharing a name are stored disambiguated, so 2026 holds both "Bailey Williams
    (Western Bulldogs)" and "Bailey Williams (West Coast)", and splitting on
    whitespace would hand back "(Western" and "Coast)".

    Blank or NaN raises rather than passing through. Left alone it would reach
    the ticker as an empty string or as the literal "NAN", which reads like a
    player rather than like a fault.
    """
    last = str(value).strip()
    if not last or last.lower() == 'nan':
        raise ValueError(f"blank Surname {value!r}")
    return last


def _chip_name(player_name, surname):
    """Chip form the front end renders: an initial, then the surname.

    "Marcus Bontempelli" becomes "M. Bontempelli". The initial is the first
    character of Player_Name, which is the first letter of the first name
    whatever the disambiguating suffix does at the other end of the string.
    """
    name = str(player_name).strip()
    if not name:
        raise ValueError(f"blank Player_Name beside surname {surname!r}")
    return f"{name[0].upper()}. {_surname(surname)}"


def build_chips(rnd):
    """The round's top CHIPS_N by Exp_Votes, ranked 1 upward."""
    top = _by_votes(rnd).head(CHIPS_N)
    if top.empty:
        raise ValueError("no player games in the latest round")
    return [
        {
            'rank': rank,
            'name': _chip_name(r['Player_Name'], r['Surname']),
            'team': _team_code(r['Playing.for']),
            'votes': round(float(r['Exp_Votes']), 1),
        }
        for rank, (_, r) in enumerate(top.iterrows(), start=1)
    ]


def build_ticker(rnd):
    """Every fixture in the round, each with its 3/2/1 by Exp_Votes.

    The numbers in the pairs are the 3/2/1 slots, not vote values: the ticker
    reads "3 ASHCROFT  2 NEALE  1 ANDREWS". Surnames are uppercased here rather
    than left to CSS, matching the file the front end already ships.
    """
    items = []
    for _gid, g in rnd.groupby('Game_ID', sort=True):
        home = _team_code(g['Home.team'].iloc[0])
        away = _team_code(g['Away.team'].iloc[0])
        top = _by_votes(g).head(TOP_N_PER_GAME)
        votes = [
            [slot, _surname(r['Surname']).upper()]
            for slot, (_, r) in zip(range(TOP_N_PER_GAME, 0, -1), top.iterrows())
        ]
        items.append({'match': f"{home} V {away}", 'votes': votes})
    if not items:
        raise ValueError("no fixtures in the latest round")
    return items


def leader_odds(player_name, path=BEST_ODDS):
    """Best price for the leader, formatted "$1.20", or EM_DASH.

    Matched on the name exactly, allowing only for surrounding whitespace. No
    fuzzy fallback: quoting one player's price against another player's name is
    worse than quoting no price, and the em dash is what the landing page shows
    for an absent value anyway.

    A missing best_odds.csv is treated as the degenerate case of no match rather
    than as a fatal fault. The odds scraper is the most fragile step in the
    chain, this is the only market value on the page, and the schema already has
    a representation for not having it. Losing the price should not cost the
    site every other field in the artifact.
    """
    if not os.path.exists(path):
        # Worded rather than shown, because this line is read in a Windows
        # console and the glyph itself does not survive cp1252.
        print(f"! {path} not found, writing an em dash for bestOdds")
        return EM_DASH
    odds = pd.read_csv(path, usecols=lambda c: c in ('player', 'best_odds'))
    hit = odds[odds['player'].astype(str).str.strip() == str(player_name).strip()]
    if hit.empty:
        return EM_DASH
    price = pd.to_numeric(hit['best_odds'].iloc[0], errors='coerce')
    if pd.isna(price):
        return EM_DASH
    return f"${float(price):.2f}"


def build_leader(season_now, odds_path=BEST_ODDS):
    """Season leader by Exp_Total_Votes, their total, and the margin to second.

    Both numbers are rounded for display only at the last step, so `clear` is
    the difference of the two full values rather than the difference of two
    already-rounded ones.
    """
    ranked = season_now.sort_values(
        ['Exp_Total_Votes', 'Player_Name'], ascending=[False, True]
    )
    if ranked.empty:
        raise ValueError(f"{SEASON} holds no players")
    top = float(ranked['Exp_Total_Votes'].iloc[0])
    # A one-row season table has no second place to measure against. It cannot
    # happen mid-season and null would fail the front end validator, so the
    # honest number for a gap over nobody is zero.
    second = float(ranked['Exp_Total_Votes'].iloc[1]) if len(ranked) > 1 else top
    name = str(ranked['Player_Name'].iloc[0]).strip()
    return {
        'name': name,
        'votes': round(top, 1),
        'clear': round(top - second, 1),
        'bestOdds': leader_odds(name, odds_path),
    }


def build_summary():
    """The artifact as a dict, with the raw AFLTables round it was built from.

    The raw round comes back alongside it because nothing in the artifact
    carries it: `round` is the display number, and the console line prints both
    so a reader can see the conversion that was applied.
    """
    rnd, latest_raw, season = load_latest_round()
    season_now = pd.read_csv(SEASON, usecols=['Player_Name', 'Exp_Total_Votes'])
    return {
        'round': _display_round(latest_raw, season),
        'brownlowNight': BROWNLOW_NIGHT,
        'leader': build_leader(season_now),
        'chips': build_chips(rnd),
        'ticker': build_ticker(rnd),
    }, latest_raw


def main():
    for path in (GAME_LEVEL, SEASON):
        if not os.path.exists(path):
            print(f"! {path} not found. Run predict_2026.py first.")
            return 1
    summary, latest_raw = build_summary()

    # allow_nan=False so a NaN vote raises here rather than being written as a
    # bare NaN token. Python emits that happily, it is not valid JSON, and the
    # run would otherwise exit 0 having published a file the front end cannot
    # parse. Serialised before the directory is touched, so a fault leaves the
    # last good artifact in place.
    body = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(body)

    # The artifact itself can carry an em dash; this line is read in a Windows
    # console, so it stays ASCII.
    print(f"OK wrote {OUT_PATH}")
    print(
        f"OK AFLTables Round_num {latest_raw}, written as round {summary['round']}, "
        f"{len(summary['chips'])} chips, {len(summary['ticker'])} fixtures"
    )
    print("OK nothing is live until this is committed, pushed, and carried to the front end repo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
