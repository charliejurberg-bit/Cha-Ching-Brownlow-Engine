"""Every player's advanced stats for every AFL match the AFL's own feed holds.

    python desk/fetch_feed_history.py            # all seasons, resumes
    python desk/fetch_feed_history.py 2027       # one season (weekly, in season)

Writes data_feed/afl_player_stats.csv.gz, one row per player per match, from
`playerStats/match/<id>`: the same Champion Data figures the desk reads live,
so a live line and the history it is held against are the same quantity.
That matters most for score involvements: the AFLTables-derived column of that
name in features.py is a different, made-up quantity (CLAUDE.md, "Score
involvements"). This file is the real one, from 2012 rather than footywire's
2015.

Finals included. Matches already in the file are skipped, so a rerun only
fetches what is new; delete the file to refetch everything.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import fetch_match_chains as fmc  # noqa: E402

OUT = ROOT / 'data_feed' / 'afl_player_stats.csv.gz'
FIRST = 2012

MAIN = {
    'scoreInvolvements': 'Score Involvements', 'metresGained': 'Metres Gained',
    'intercepts': 'Intercepts', 'contestedPossessions': 'Contested Possessions',
    'uncontestedPossessions': 'Uncontested Possessions', 'inside50s': 'Inside 50s',
    'rebound50s': 'Rebound 50s', 'contestedMarks': 'Contested Marks',
    'marksInside50': 'Marks Inside 50', 'tacklesInside50': 'Tackles Inside 50',
    'goalAssists': 'Goal Assists', 'onePercenters': 'One Percenters', 'bounces': 'Bounces',
    'disposals': 'Disposals', 'goals': 'Goals', 'tackles': 'Tackles', 'marks': 'Marks',
}
EXTENDED = {
    'interceptMarks': 'Intercept Marks', 'groundBallGets': 'Ground Ball Gets',
    'pressureActs': 'Pressure Acts', 'spoils': 'Spoils', 'hitoutsToAdvantage': 'Hitouts To Advantage',
    'effectiveDisposals': 'Effective Disposals', 'scoreLaunches': 'Score Launches',
    'marksOnLead': 'Marks On Lead', 'f50GroundBallGets': 'F50 Ground Ball Gets',
}


def rows_for(match: dict, j: dict) -> list[dict]:
    out = []
    for side in ('homeTeamPlayerStats', 'awayTeamPlayerStats'):
        for row in j.get(side, []):
            p = row['player']['player']['player']
            n = p['playerName']
            s = row['playerStats']['stats']
            e = s.get('extendedStats') or {}
            r = {'Season': match['Season'], 'MatchId': match['MatchId'], 'RoundNumber': match['RoundNumber'],
                 'RoundName': match['RoundName'], 'utc': match['utc'], 'Home': match['Home'], 'Away': match['Away'],
                 'Club': fmc.CD_TEAM.get(row.get('teamId'), row.get('teamId')), 'FeedId': p['playerId'],
                 'Name': f"{n.get('givenName', '')} {n.get('surname', '')}".strip(), 'Surname': n.get('surname', '')}
            for k, c in MAIN.items():
                r[c] = s.get(k)
            cl = s.get('clearances') or {}
            r['Centre Clearances'] = cl.get('centreClearances')
            for k, c in EXTENDED.items():
                r[c] = e.get(k)
            out.append(r)
    return out


def main(argv: list[str]) -> None:
    sess = fmc._session()
    token, minted = fmc._token(sess), time.time()
    seasons = sorted(fmc._compseasons(sess).items())
    if argv:
        want = {int(a) for a in argv}
        seasons = [(y, c) for y, c in seasons if y in want]
    else:
        seasons = [(y, c) for y, c in seasons if y >= FIRST]
    done = set()
    old = None
    if OUT.exists():
        old = pd.read_csv(OUT, low_memory=False)
        done = set(old.MatchId)
    new = []
    for year, cs in seasons:
        fixture = fmc._fixture(sess, cs, year)
        todo = [m for m in fixture if m['status'] in fmc.FINISHED_STATUS and m['MatchId'] not in done]
        print(f'{year}: {len(fixture)} matches, {len(todo)} to fetch', flush=True)
        for i, m in enumerate(todo):
            if time.time() - minted > 1500:
                token, minted = fmc._token(sess), time.time()
            r = sess.get(f'{fmc.CFS}/playerStats/match/{m["MatchId"]}',
                         headers={'x-media-mis-token': token}, timeout=30)
            if r.status_code == 401:
                token, minted = fmc._token(sess), time.time()
                r = sess.get(f'{fmc.CFS}/playerStats/match/{m["MatchId"]}',
                             headers={'x-media-mis-token': token}, timeout=30)
            r.raise_for_status()
            rows = rows_for(m, r.json())
            if not rows:
                print(f'  {m["MatchId"]}: no player stats', flush=True)
            new += rows
            time.sleep(fmc.DELAY)
            if (i + 1) % 50 == 0:
                print(f'  {i + 1}/{len(todo)}', flush=True)
        # Write after every season so an interrupted run keeps what it fetched.
        if new:
            frame = pd.DataFrame(new) if old is None else pd.concat([old, pd.DataFrame(new)], ignore_index=True)
            OUT.parent.mkdir(exist_ok=True)
            frame.to_csv(OUT, index=False)
            old, new = frame, []
            done = set(old.MatchId)
    print(f'{OUT.relative_to(ROOT)}: {0 if old is None else len(old)} rows')


if __name__ == '__main__':
    main(sys.argv[1:])
