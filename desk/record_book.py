"""The Game Day Desk's record book: every record a live stat line can be held
up against, worked out once before the game so the live panel only compares.

    python desk/record_book.py            # writes desk/data/record_book.json
    python desk/record_book.py --show Disposals

What it holds, per stat, single game, finals included (AFLTables' convention,
and the one every published record list uses):

  all_time   the top 10 (ties kept, so the list can run past 10)
  club       each club's record, FOR that club, and its top 10 cutoff
  opponent   the record AGAINST each club
  venue      the record at each ground
  season     each season's highest single game

and per active player (played in the last three seasons): career games, career totals,
date of birth and their career-best game in each stat.

Two brackets for the age and early-career alerts:

  early            per stat, per career game n (1 to 100): the most of it a
                   player had through his first n games (n = 1 is debut).
                   Only careers that began inside the stat's coverage count.
  milestone_ages   per milestone, the age every player reached it, sorted

Ages come from a date of birth worked out per player from AFLTables' Age
column (decimal years on the day; 0 there means unknown), so a game with a
blank Age still gets one. Game numbers are counted from the archive itself,
which is complete from 1897, and include finals, as AFLTables does.

Scope is ALL TIME by default (CLAUDE.md, "Historical claims"). Each stat
carries `from`, the first season it is recorded in enough games to stand
behind (measured below, not assumed), and every claim off it must name that
year when it is after 1897. Goals and games reach 1897 through
data_history/goals_1897_1964.csv.gz (scripts/fetch_goals_1897_1964.R); every
other stat starts where AFLTables starts recording it.

Clubs are counted by lineage, as the clubs count their own records: South
Melbourne is Sydney, Footscray is the Western Bulldogs, Kangaroos is North
Melbourne, the Brisbane Bears are the Brisbane Lions. Fitzroy and the other
defunct clubs stay themselves.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / 'data' / 'record_book.json'

FILES = [
    ROOT / 'data_history' / 'fitzroy_stats_1965_2006.csv.gz',
    ROOT / 'fitzroy_stats_all.csv',
]
PRE_1965 = ROOT / 'data_history' / 'goals_1897_1964.csv.gz'

# Stat key on the desk -> archive column. The order is the desk's order.
STATS = {
    'Disposals': 'Disposals',
    'Kicks': 'Kicks',
    'Handballs': 'Handballs',
    'Marks': 'Marks',
    'Goals': 'Goals',
    'Tackles': 'Tackles',
    'Clearances': 'Clearances',
    'Hitouts': 'Hit.Outs',
    # Advanced, from AFLTables, which carries these from 1998-2003: longer
    # than the AFL's feed, and the same Champion Data figures.
    'Contested Possessions': 'Contested.Possessions',
    'Inside 50s': 'Inside.50s',
    'Rebound 50s': 'Rebounds',
    'Contested Marks': 'Contested.Marks',
    'Marks Inside 50': 'Marks.Inside.50',
    'One Percenters': 'One.Percenters',
    'Goal Assists': 'Goal.Assists',
    'Bounces': 'Bounces',
}
BASIC = ['Disposals', 'Kicks', 'Handballs', 'Marks', 'Goals', 'Tackles', 'Clearances', 'Hitouts']

# Only in the AFL's own feed (desk/fetch_feed_history.py), 2012 on. Joined
# onto the archive rows by season, club, name and date.
FEED = ROOT / 'data_feed' / 'afl_player_stats.csv.gz'
FEED_ONLY = ['Score Involvements', 'Metres Gained', 'Intercepts', 'Intercept Marks',
             'Ground Ball Gets', 'Pressure Acts', 'Spoils', 'Hitouts To Advantage',
             'Effective Disposals', 'Centre Clearances', 'Tackles Inside 50', 'Score Launches']
MIN_JOIN = 0.98
AFL_PLAYERS = ROOT / 'data_feed' / 'afl_players.csv'
STATS.update({k: k for k in FEED_ONLY})

LINEAGE = {
    'South Melbourne': 'Sydney',
    'Footscray': 'Western Bulldogs',
    'Kangaroos': 'North Melbourne',
    'Brisbane Bears': 'Brisbane Lions',
}

# Career milestones worth a post, per career total.
# Only the big round numbers: 100 games or 500 tackles is club trivia (the
# floor of what gets read, measured on @sirswampthing, memory swamp-tweet-format).
MILESTONES = {
    'Games': [200, 250, 300, 350, 400],
    'Goals': [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
    'Disposals': [5000, 6000, 7000, 8000],
    'Tackles': [1000, 1250, 1500],
    'Clearances': [1000, 1250, 1500],
    'Marks': [2000, 2500],
    'Hitouts': [5000, 6000, 7000, 8000, 9000, 10000],
}

# Players the desk knows: anyone who played in the book's last three seasons.
# One season was not enough: a player who missed a whole year injured (Logan
# McDonald and Phoenix Gothard, 2025) came back unknown, with no career.
ACTIVE_SEASONS = 3
EARLY_GAMES = 100
EARLY_TOP = 5
# Share of a season's team-games with a non-zero total. 0.8, not 0.9: 2020's
# shortened quarters left 15% of team-games without a bounce, which a 0.9 cut
# read as bounces starting in 2021 when they are recorded from 1999. Hitouts
# still start in 1976 (1975: 42%, genuinely half recorded).
COVERAGE = 0.8


def live_season_files() -> list[Path]:
    """data_<season>/afltables_<season>.csv for every season after 2025."""
    return sorted(p for p in ROOT.glob('data_20*/afltables_20*.csv')
                  if int(p.stem.rsplit('_', 1)[1]) > 2025)


def load() -> pd.DataFrame:
    cols = ['Season', 'Round', 'Date', 'Venue', 'ID', 'Player', 'First.name', 'Surname', 'Playing.for',
            'Home.team', 'Away.team', 'Age', *STATS.values()]
    cols = [c for c in cols if c not in FEED_ONLY]
    parts = [pd.read_csv(f, usecols=cols, low_memory=False)
             for f in [*FILES, *live_season_files()]]
    if PRE_1965.exists():
        old = pd.read_csv(PRE_1965, low_memory=False)
        old = old[[c for c in cols if c in old.columns]]
        parts.insert(0, old)
    else:
        print(f'warning: {PRE_1965.name} missing; goals and games start in 1965', file=sys.stderr)
    d = pd.concat(parts, ignore_index=True)
    d = fill_identity(d)
    d = d.drop_duplicates(['Season', 'Date', 'ID', 'Playing.for'])
    for c in ('Playing.for', 'Home.team', 'Away.team'):
        d[c] = d[c].replace(LINEAGE)
    d['Opponent'] = d['Away.team'].where(d['Playing.for'] == d['Home.team'], d['Home.team'])
    d['Round'] = d['Round'].astype(str)
    d = add_age_and_game_number(d)
    d = d.reset_index(drop=True)
    return join_feed(d)


def fill_identity(d: pd.DataFrame) -> pd.DataFrame:
    """AFLTables leaves Player and ID blank on some rows (92 in 2026: Charlie
    Cameron, Jack Ross, Jack Graham...). Left blank, those games vanish from a
    career total and a blank name reaches the page as NaN. The name comes back
    from First.name + Surname; the ID from the same name at the same club in
    another row, then the same name anywhere if unique. A true debutant with no
    ID anywhere gets a stable negative one."""
    blank = d['Player'].isna()
    d.loc[blank, 'Player'] = (d.loc[blank, 'First.name'].fillna('') + ' ' + d.loc[blank, 'Surname'].fillna('')).str.strip()
    known = d[d.ID.notna()]
    by_club = known.groupby(['Player', 'Playing.for']).ID.agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    by_name = known.groupby('Player').ID.agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    miss = d.ID.isna()
    keys = list(zip(d.loc[miss, 'Player'], d.loc[miss, 'Playing.for']))
    d.loc[miss, 'ID'] = pd.to_numeric(pd.Series([by_club.get(k) for k in keys], dtype=object), errors='coerce').to_numpy()
    miss = d.ID.isna()
    d.loc[miss, 'ID'] = pd.to_numeric(d.loc[miss, 'Player'].map(by_name), errors='coerce')
    miss = d.ID.isna()
    if miss.any():
        new = {k: -(i + 1) for i, k in enumerate(sorted(set(zip(d.loc[miss, 'Player'], d.loc[miss, 'Playing.for']))))}
        d.loc[miss, 'ID'] = [new[k] for k in zip(d.loc[miss, 'Player'], d.loc[miss, 'Playing.for'])]
        print(f'{len(new)} players with no ID anywhere (debutants), given stable stand-ins')
    return d


def add_age_and_game_number(d: pd.DataFrame) -> pd.DataFrame:
    """DOB per player (the most common date implied by his Age column), every
    game's age from it, and his career game number on the day."""
    if 'Age' not in d.columns:
        raise SystemExit('no Age column: rerun scripts/fetch_goals_1897_1964.R (it now keeps Age)')
    dt = pd.to_datetime(d['Date'])
    ok = d['Age'].fillna(0) >= 14
    implied = dt[ok] - pd.to_timedelta((d.loc[ok, 'Age'] * 365.25).round(), unit='D')
    dob = implied.groupby(d.loc[ok, 'ID']).agg(lambda s: s.mode().iloc[0])
    dob = afl_dob_fix(d, dob)
    d['DOB'] = d['ID'].map(dob)
    d['Age'] = (dt - d['DOB']).dt.days / 365.25
    print(f'ages: {d.DOB.notna().mean():.2%} of games, {d.loc[d.DOB.isna(), "ID"].nunique()} players without one')
    d = d.assign(_dt=dt).sort_values(['ID', '_dt', 'Season']).drop(columns='_dt')
    d['GameNo'] = d.groupby('ID').cumcount() + 1
    return d


def afl_dob_fix(d: pd.DataFrame, dob: pd.Series) -> pd.Series:
    """Age is published to a few decimals, so the implied date can land a day
    out (30 of 611 active players against the AFL's own list). Where the AFL's
    player list (desk/feed.py caches it) has the same name and debut year,
    uniquely, and its date is within two days, take the AFL's. A bigger gap is
    a real conflict between the sources (one has day and month swapped) and is
    left alone rather than guessed."""
    if not AFL_PLAYERS.exists():
        return dob
    sys.path.insert(0, str(ROOT))
    from features import normalise_name
    a = pd.read_csv(AFL_PLAYERS, dtype=str).dropna(subset=['dateOfBirth', 'debutYear'])
    a['key'] = (a.firstName.fillna('') + ' ' + a.surname.fillna('')).map(normalise_name) + '|' + a.debutYear
    a = a.drop_duplicates('key', keep=False).set_index('key')['dateOfBirth']
    first = d.sort_values('Season').drop_duplicates('ID')
    key = first.Player.map(normalise_name) + '|' + first.Season.astype(str)
    afl = pd.to_datetime(pd.Series(key.map(a).to_numpy(), index=first.ID.to_numpy()), errors='coerce')
    afl = afl[afl.index.isin(dob.index)].dropna()
    gap = (afl - dob.reindex(afl.index)).abs()
    fix = afl[gap.between(pd.Timedelta(days=1), pd.Timedelta(days=2))]
    print(f'dob: {len(afl)} players checked against the AFL list, {len(fix)} moved a day or two')
    out = dob.copy()
    out.loc[fix.index] = fix
    return out


def age_text(dob: pd.Timestamp, on: pd.Timestamp) -> str:
    """'19y 120d': whole years, then days since the last birthday."""
    y = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
    try:
        last = dob.replace(year=dob.year + y)
    except ValueError:          # born 29 February
        last = dob.replace(year=dob.year + y, day=28)
    return f'{y}y {(on - last).days}d'


def early_career(d: pd.DataFrame, debut: pd.Series) -> dict:
    """Per stat with long coverage, per career game n, the top EARLY_TOP
    running totals through game n."""
    out = {}
    e = d[d.GameNo <= EARLY_GAMES].sort_values(['ID', 'GameNo'])
    for key, col in STATS.items():
        if key in FEED_ONLY:
            continue
        start = coverage_from(d, col)
        f = e[e.ID.map(debut) >= start][['ID', 'Player', 'Season', 'Playing.for', 'GameNo', col]].rename(columns={'Playing.for': 'Club'})
        f['cum'] = f[col].fillna(0).groupby(f.ID).cumsum()
        f = f[f.cum > 0]
        by_n = {}
        for n, g in f.groupby('GameNo'):
            g = g.sort_values(['cum', 'Season'], ascending=[False, True])
            cut = g.cum.iloc[min(EARLY_TOP, len(g)) - 1]
            by_n[str(int(n))] = [{'v': int(r.cum), 'player': r.Player, 'club': r.Club, 'season': int(r.Season)}
                                 for r in g[g.cum >= cut].itertuples()]
        out[key] = {'from': start, 'by_n': by_n}
    return out


def milestone_ages(d: pd.DataFrame, debut: pd.Series, frm: dict) -> dict:
    """Per milestone, the age each player reached it: youngest and oldest five
    named, every age kept (sorted) to rank a new one against."""
    out = {}
    s = d[d.DOB.notna()].sort_values(['ID', 'GameNo'])
    for stat, marks in MILESTONES.items():
        out[stat] = {}
        if stat == 'Games':
            run = s.GameNo
            f = s
        else:
            col = STATS[stat]
            f = s[s.ID.map(debut) >= frm[stat]]
            run = f[col].fillna(0).groupby(f.ID).cumsum()
        for m in marks:
            hit = f[run >= m].drop_duplicates('ID')
            if hit.empty:
                continue
            hit = hit.sort_values('Age')
            pick = lambda h: [{'player': r.Player, 'season': int(r.Season), 'age': age_text(r.DOB, pd.Timestamp(r.Date))}
                              for r in h.itertuples()]
            out[stat][str(m)] = {'ages': [round(float(a), 4) for a in hit.Age],
                                 'young': pick(hit.head(5)), 'old': pick(hit.tail(5).iloc[::-1])}
    return out


def join_feed(d: pd.DataFrame) -> pd.DataFrame:
    """Put the feed-only stats onto archive rows: season, club and name, then
    surname, each within a day of the archive's date. Refuses below MIN_JOIN."""
    for c in FEED_ONLY:
        d[c] = float('nan')
    if not FEED.exists():
        print(f'warning: {FEED.name} missing; run desk/fetch_feed_history.py', file=sys.stderr)
        return d
    sys.path.insert(0, str(ROOT))
    from features import normalise_name

    f = pd.read_csv(FEED, low_memory=False)
    f['Club'] = f['Club'].replace(LINEAGE)
    f['date'] = pd.to_datetime(f['utc'], utc=True).dt.tz_convert('Australia/Melbourne').dt.tz_localize(None).dt.normalize()
    f['norm'] = f['Name'].map(normalise_name)
    f['sur'] = f['Surname'].map(normalise_name)
    f['fi'] = range(len(f))
    a = d.loc[d.Season >= f.Season.min(), ['Season', 'Date', 'Playing.for', 'Player']].copy()
    a['ai'] = a.index
    a['date'] = pd.to_datetime(a['Date']).dt.normalize()
    a['norm'] = a['Player'].map(normalise_name)
    a['sur'] = a['Player'].str.split(' ', n=1).str[-1].map(normalise_name)
    a = a.rename(columns={'Playing.for': 'Club'})

    def pair(keys, fl, al):
        m = fl.merge(al, on=['Season', 'Club', *keys], suffixes=('', '_a'))
        m = m[(m['date'] - m['date_a']).abs() <= pd.Timedelta(days=1)]
        # Unique both ways, so two Bailey Williamses never cross.
        m = m[~m.fi.duplicated(keep=False) & ~m.ai.duplicated(keep=False)]
        return m[['fi', 'ai']]

    m1 = pair(['norm'], f, a)
    left_f, left_a = f[~f.fi.isin(m1.fi)], a[~a.ai.isin(m1.ai)]
    m2 = pair(['sur'], left_f, left_a)
    m = pd.concat([m1, m2])
    rate = len(m) / len(f)
    print(f'feed join: {len(m1)} by name, {len(m2)} by surname, {len(f) - len(m)} unmatched ({rate:.2%})')
    if rate < MIN_JOIN:
        raise SystemExit(f'feed join {rate:.2%} is under {MIN_JOIN:.0%}; refusing to build on it')
    vals = f.set_index('fi').loc[m.fi.to_numpy(), FEED_ONLY].to_numpy()
    d.loc[m.ai.to_numpy(), FEED_ONLY] = vals
    return d


def shown_round(season: int, rnd: str) -> str:
    """AFLTables numbers Opening Round as Round 1 from 2024 (CLAUDE.md)."""
    if not rnd.isdigit():
        return rnd
    n = int(rnd) - 1 if season >= 2024 else int(rnd)
    return 'OR' if n == 0 else f'R{n}'


def coverage_from(d: pd.DataFrame, col: str) -> int:
    """First season from which at least COVERAGE of team-games record the stat."""
    tg = d.groupby(['Season', 'Date', 'Playing.for'])[col].sum(min_count=1)
    share = (tg.fillna(0) > 0).groupby(level='Season').mean()
    ok = share[share >= COVERAGE].index
    # The first season of an unbroken run to the present, so a stray early
    # season does not open a gap.
    seasons = sorted(share.index)
    start = seasons[-1]
    for s in reversed(seasons):
        if s in ok:
            start = s
        else:
            break
    return int(start)


def game_row(r) -> dict:
    s = int(r.Season)
    return {'player': r.Player, 'id': r.ID, 'club': r['Playing.for'], 'opp': r.Opponent,
            'venue': r.Venue, 'season': s, 'round': shown_round(s, r.Round), 'date': str(r.Date)[:10]}


def top(frame: pd.DataFrame, col: str, n: int = 10) -> tuple[list[dict], int | None]:
    """Top n with ties kept, and the value needed to enter it."""
    f = frame[frame[col].notna()].sort_values([col, 'Season'], ascending=[False, True])
    if f.empty:
        return [], None
    cut = int(f[col].iloc[min(n, len(f)) - 1])
    rows = f[f[col] >= cut]
    return [{'v': int(r[col]), **game_row(r)} for _, r in rows.iterrows()], cut


def record(frame: pd.DataFrame, col: str) -> dict:
    """The record value and everyone who holds it."""
    f = frame[frame[col].notna()]
    if f.empty:
        return {}
    v = int(f[col].max())
    held = f[f[col] == v].sort_values('Season')
    return {'v': v, 'by': [game_row(r) for _, r in held.iterrows()]}


def build(before: str | None = None) -> dict:
    d = load()
    if before:
        # The book as it stood on the morning of `before`, so a replayed round
        # is judged against records it had not yet set.
        d = d[pd.to_datetime(d.Date).dt.strftime('%Y-%m-%d') < before]
    book: dict = {
        'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'through': int(d.Season.max()),
        'lineage': LINEAGE,
        'stats': {},
        'players': {},
    }
    for key, col in STATS.items():
        start = coverage_from(d, col)
        f = d[d.Season >= start]
        vals = f[col].dropna()
        entry = {'col': col, 'from': start, 'basic': key in BASIC,
                 # How big a game is: the desk's floors for "worth a look".
                 'p99': float(vals.quantile(0.99)), 'p97': float(vals.quantile(0.97))}
        entry['all_time'], entry['top10_cut'] = top(f, col)
        entry['club'] = {}
        for club, g in f.groupby('Playing.for'):
            rec = record(g, col)
            lst, cut = top(g, col)
            entry['club'][club] = {**rec, 'top10_cut': cut,
                                   'top': [{k: r[k] for k in ('v', 'player', 'season')} for r in lst[:6]]}
        entry['opponent'] = {opp: record(g, col) for opp, g in f.groupby('Opponent')}
        entry['venue'] = {v: record(g, col) for v, g in f.groupby('Venue')}
        entry['season'] = {int(s): record(g, col) for s, g in f.groupby('Season')}
        book['stats'][key] = entry
        print(f'{key:11s} from {start}  record {entry["all_time"][0]["v"]} '
              f'({entry["all_time"][0]["player"]}, {entry["all_time"][0]["season"]})  '
              f'top-10 cutoff {entry["top10_cut"]}')

    active = d.loc[d.Season > d.Season.max() - ACTIVE_SEASONS, 'ID'].unique()
    for pid, g in d[d.ID.isin(active)].groupby('ID'):
        g = g.sort_values(['Season', 'Date'])
        last = g.iloc[-1]
        p = {'name': last.Player, 'club': last['Playing.for'], 'games': int(len(g)),
             'debut': int(g.Season.min()), 'dob': str(last.DOB)[:10] if pd.notna(last.DOB) else None,
             'totals': {}, 'best': {}}
        for key, col in STATS.items():
            p['totals'][key] = int(g[col].fillna(0).sum())
            if g[col].notna().any() and g[col].max() > 0:
                b = g.loc[g[col].idxmax()]
                p['best'][key] = {'v': int(b[col]), 'season': int(b.Season),
                                  'round': shown_round(int(b.Season), b.Round), 'opp': b.Opponent}
        book['players'][str(int(pid))] = p
    book['milestones'] = MILESTONES
    # How many players have ever reached each milestone: the rarity a
    # milestone alert is ranked by. A stat's totals only count from its
    # coverage year, so a pre-coverage career undercounts (never overcounts).
    career = d.groupby('ID').agg(Games=('Season', 'size'),
                                 **{k: (c, 'sum') for k, c in STATS.items()})
    book['milestone_counts'] = {k: {str(m): int((career[k] >= m).sum()) for m in ms}
                                for k, ms in MILESTONES.items()}
    debut = d.groupby('ID').Season.min()
    book['early'] = early_career(d, debut)
    book['milestone_ages'] = milestone_ages(d, debut, {k: book['stats'][k]['from'] for k in STATS})
    print(f'{len(book["players"])} active players')
    # Every game, for the desk's rarity counts, stat combinations and ages.
    games = d[['Season', 'Date', 'Round', 'ID', 'Player', 'Playing.for', 'Opponent', 'DOB', 'Age', 'GameNo',
               *STATS.values()]].rename(
        columns={c: k for k, c in STATS.items()})
    games.to_pickle(OUT.with_name(OUT.stem.replace('record_book', 'games') + '.pkl'))
    return book


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', help='print one stat from the written book')
    ap.add_argument('--before', help='YYYY-MM-DD: only games before this date (for replay tests)')
    ap.add_argument('--out', help='write here instead of desk/data/record_book.json')
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = Path(a.out).resolve()
    if a.show:
        s = json.loads(OUT.read_text())['stats'][a.show]
        print(f'{a.show}, from {s["from"]}, top 10 cutoff {s["top10_cut"]}')
        for r in s['all_time']:
            print(f'  {r["v"]:3d}  {r["player"]:24s} {r["club"]:18s} v {r["opp"]:18s} {r["season"]} {r["round"]}')
        return
    book = build(a.before)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(book, separators=(',', ':'), allow_nan=False))
    print(f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
