"""Integrity validation for the historical coaches vote archive.

Standalone CLI. Nothing imports this, it writes no files, it makes no network
calls and it never edits coaches_votes_all.csv. It reads and it reports.

    python scripts/validate_coaches.py
    python scripts/validate_coaches.py --season 2025
    python scripts/validate_coaches.py --season 2025 --detail 40

WHY THIS EXISTS, AND WHY THE FAILURE IS SILENT

brownlow_model.py and backtest.py are the only two code paths that read
coaches_votes_all.csv. Both do the same thing to it:

    coaches_agg = coaches.groupby(
        ['Season','Round','CV_Player','CV_Team'])['Coaches.Votes'].sum()
    df = stats.merge(coaches_agg, on=[...], how='left')
    df['Coaches_Votes'] = df['Coaches_Votes'].fillna(0)

That groupby is a sum, not a uniqueness assertion. If the archive holds two
rows for one player in one season-round, because an extra fixture has been
folded into a real round, the two values are added and the model trains on the
total as though it were a single game's coaches votes. Nothing errors, nothing
warns, and the inflated number is indistinguishable downstream from a genuine
one. The fillna(0) on the other side is the mirror defect: an unmatched row
becomes a zero, and zero is the modal value.

WHAT A REAL ROW CAN HOLD, measured rather than assumed

Both coaches in a game award 5-4-3-2-1, so a game carries exactly
2 * (5+4+3+2+1) = 30 votes and a single player's two-coach sum runs 1 to 10.
Ten is a hard ceiling. A value above it, or a value that is not a whole number,
did not come from two coaches awarding places.

THE FOUR CHECKS

  1 DUPLICATE   two or more rows sharing Season + Round + player + club. This
                is the one that reaches the model as inflation, so both source
                fixtures are named on every finding.
  2 FRACTIONAL  Coaches.Votes is not a whole number. Votes are integers, so a
                fraction is a different quantity written into the column.
  3 CEILING     a value above 10, reported twice: as the archive stores it, and
                as the model's groupby would leave it after summing. The second
                number is the one that matters, the first says whether the
                archive was already wrong before the merge touched it.
  4 ROUND TOTAL a round whose votes are not 30 * games. Both numbers print.

CHECK 4 NEEDS AN INDEPENDENT DENOMINATOR

Counting games from the coaches file's own Home.Team / Away.Team would be
circular: those columns are part of what is suspect. The game count comes from
fitzroy_stats_all.csv (2007 onward) and data_history/game_level_2006.csv for
the one season that predates it.

Finals have no denominator here. fitzroy_stats_all.csv carries string round
labels for them, which coerce to NaN and drop, while the coaches archive
numbers finals continuously (2025 runs to round 29). A round with no
denominator is reported UNAVAILABLE and is not counted as a failure. It is
printed rather than skipped, because a silently omitted round reads as a round
that passed.

EXIT CODE
Non-zero if any check fires on any season in scope, zero if all are clean. An
unavailable denominator is not a failure. A season with no rows at all is,
since that means the filter matched nothing and the run proved nothing.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

COACHES_CSV = ROOT / "coaches_votes_all.csv"
# 2007 onward. The archive opens in 2006, one season earlier, so that season
# takes its denominator from the converted history instead.
STATS_CSV = ROOT / "fitzroy_stats_all.csv"
STATS_2006_CSV = ROOT / "data_history" / "game_level_2006.csv"

VOTES_PER_COACH = 5 + 4 + 3 + 2 + 1
COACHES_PER_GAME = 2
EXPECTED_VOTES_PER_GAME = VOTES_PER_COACH * COACHES_PER_GAME  # 30
# One player, both coaches, top place from each.
VOTE_CEILING = COACHES_PER_GAME * 5  # 10

# Deliberately a copy of brownlow_model.py's TEAM_ABBREV rather than an import.
# The point of this validator is to reproduce what that merge sees, so it has to
# key players the same way. Importing brownlow_model.py to borrow the dict would
# execute a training script. If the two ever diverge, this file is wrong and the
# divergence is the finding.
TEAM_ABBREV = {
    'ADEL': 'Adelaide', 'BL': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FRE': 'Fremantle',
    'GCFC': 'Gold Coast', 'GEEL': 'Geelong', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WB': 'Western Bulldogs', 'WCE': 'West Coast',
}

GROUP_KEY = ['Season', 'Round', 'CV_Player', 'CV_Team']


def _fail(msg):
    print(f"! {msg}", file=sys.stderr)
    return 1


def load_coaches(path=COACHES_CSV):
    """The archive, keyed the way brownlow_model.py keys it.

    CV_Player and CV_Team are split out of Player.Name with the same two regexes
    the model uses. An abbreviation outside TEAM_ABBREV maps to NaN, which is
    kept rather than dropped: a club the model cannot resolve is a finding in
    its own right and is reported by _unmapped_clubs.
    """
    df = pd.read_csv(path, low_memory=False)
    df['Season'] = pd.to_numeric(df['Season'], errors='coerce')
    df['Round'] = pd.to_numeric(df['Round'], errors='coerce')
    df['Coaches.Votes'] = pd.to_numeric(df['Coaches.Votes'], errors='coerce')
    # itertuples() cannot expose a column whose name holds a dot: it renames it
    # positionally, and row._asdict() then has no 'Coaches.Votes' key. Every
    # per-row access below goes through this alias instead. The dotted name is
    # kept because that is what the file and both model readers call it.
    df['votes'] = df['Coaches.Votes']
    df['CV_Player'] = df['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
    df['CV_Abbrev'] = df['Player.Name'].str.extract(r'\(([^)]+)\)')[0]
    df['CV_Team'] = df['CV_Abbrev'].map(TEAM_ABBREV)
    df['fixture'] = df['Home.Team'].astype(str) + ' v ' + df['Away.Team'].astype(str)
    return df


def load_game_counts():
    """Games per Season+Round, from sources independent of the coaches archive.

    Returns {(season, round): n_games}. Only whole-numbered rounds appear:
    finals carry string labels that coerce to NaN, and a round absent from this
    map is reported UNAVAILABLE by check 4 rather than failed.
    """
    counts = {}
    for path, round_col in ((STATS_CSV, 'Round'), (STATS_2006_CSV, 'Round_num')):
        if not path.exists():
            print(f"  note: {path.name} absent, seasons it covers have no denominator")
            continue
        cols = ['Season', round_col, 'Home.team', 'Away.team']
        d = pd.read_csv(path, usecols=lambda c: c in cols, low_memory=False)
        d['rn'] = pd.to_numeric(d[round_col], errors='coerce')
        d = d.dropna(subset=['rn'])
        fixtures = d[['Season', 'rn', 'Home.team', 'Away.team']].drop_duplicates()
        for (s, r), n in fixtures.groupby(['Season', 'rn']).size().items():
            counts[(int(s), int(r))] = int(n)
    return counts


def _unmapped_clubs(df):
    """Abbreviations TEAM_ABBREV does not resolve.

    Not one of the four checks, but reported because the model maps the same
    dict and a NaN club there merges to nothing and then fills to zero. Silence
    on this would hide a whole club.
    """
    bad = df[df.CV_Team.isna() & df.CV_Abbrev.notna()]
    return sorted(bad.CV_Abbrev.unique().tolist()), len(bad)


def check_duplicates(df):
    """1. Two or more rows sharing Season + Round + player + club.

    This is the check that matters most, because the model's groupby sums these
    rather than rejecting them. Every finding names both source fixtures and
    the total the merge would produce.
    """
    sizes = df.groupby(GROUP_KEY, dropna=False).size()
    keys = sizes[sizes > 1].index
    if not len(keys):
        return []
    dup = df.set_index(GROUP_KEY).loc[keys].reset_index()
    out = []
    for key, g in dup.groupby(GROUP_KEY, dropna=False):
        season, rnd, player, club = key
        out.append({
            'season': int(season), 'round': int(rnd),
            'player': player, 'club': club,
            'n': len(g),
            'total': float(g['votes'].sum()),
            'parts': [(row.fixture, float(row.votes))
                      for row in g.itertuples()],
        })
    return sorted(out, key=lambda d: (d['season'], d['round'], d['player']))


def check_fractional(df):
    """2. Coaches.Votes is not a whole number.

    Two coaches awarding 5-4-3-2-1 can only ever sum to an integer, so a
    fraction is a different quantity that has been written into this column.
    """
    bad = df[df['votes'].notna() & (df['votes'].mod(1) != 0)]
    return [{'season': int(r.Season), 'round': int(r.Round), 'player': r.CV_Player,
             'club': r.CV_Team, 'votes': float(r.votes),
             'fixture': r.fixture}
            for r in bad.itertuples()]


def check_ceiling(df):
    """3. Values above 10, before and after the model's summing.

    `raw` is what the archive stores. `summed` is what the groupby leaves, and
    is the number the model actually trains on. A group of one appears in both,
    which is intended: it says the archive was already out of range before the
    merge, rather than being pushed out of range by it.
    """
    raw = df[df['votes'] > VOTE_CEILING]
    raw_out = [{'season': int(r.Season), 'round': int(r.Round), 'player': r.CV_Player,
                'club': r.CV_Team, 'votes': float(r.votes),
                'fixture': r.fixture}
               for r in raw.itertuples()]
    agg = df.groupby(GROUP_KEY, dropna=False)['votes'].agg(['sum', 'size'])
    over = agg[agg['sum'] > VOTE_CEILING].reset_index()
    sum_out = [{'season': int(r.Season), 'round': int(r.Round), 'player': r.CV_Player,
                'club': r.CV_Team, 'total': float(r.sum), 'n': int(r.size)}
               for r in over.itertuples()]
    return raw_out, sum_out


def check_round_totals(df, games):
    """4. A round whose votes are not 30 * games.

    Rounds with no entry in `games` are returned separately as unavailable, not
    as failures. That is every finals round, since the denominator sources drop
    string-labelled rounds, and it is printed rather than skipped so a round
    never disappears silently.
    """
    bad, unavailable = [], []
    grouped = df.groupby(['Season', 'Round'])['votes'].agg(['sum', 'size'])
    for (season, rnd), row in grouped.iterrows():
        season, rnd = int(season), int(rnd)
        n_games = games.get((season, rnd))
        if n_games is None:
            unavailable.append({'season': season, 'round': rnd,
                                'votes': float(row['sum']), 'rows': int(row['size'])})
            continue
        expected = n_games * EXPECTED_VOTES_PER_GAME
        if float(row['sum']) != float(expected):
            bad.append({'season': season, 'round': rnd, 'votes': float(row['sum']),
                        'expected': float(expected), 'games': n_games,
                        'rows': int(row['size'])})
    return bad, unavailable


def _by_season(findings):
    out = {}
    for f in findings:
        out.setdefault(f['season'], []).append(f)
    return out


def print_report(df, dups, frac, raw_over, sum_over, bad_rounds, unavailable,
                 detail):
    seasons = sorted(int(s) for s in df.Season.dropna().unique())
    d_s, f_s, r_s, s_s, b_s = (_by_season(x) for x in
                               (dups, frac, raw_over, sum_over, bad_rounds))
    u_s = _by_season(unavailable)

    print()
    print('=' * 100)
    print('PER-SEASON SUMMARY')
    print('=' * 100)
    print(f"{'season':>7}  {'rows':>7}  {'dup':>5}  {'frac':>5}  "
          f"{'>10 raw':>8}  {'>10 sum':>8}  {'bad rnd':>8}  {'no denom':>9}  status")
    print('-' * 100)
    for s in seasons:
        n = int((df.Season == s).sum())
        counts = (len(d_s.get(s, [])), len(f_s.get(s, [])), len(r_s.get(s, [])),
                  len(s_s.get(s, [])), len(b_s.get(s, [])))
        status = 'FAIL' if any(counts) else 'ok'
        print(f"{s:>7}  {n:>7,}  {counts[0]:>5}  {counts[1]:>5}  {counts[2]:>8}  "
              f"{counts[3]:>8}  {counts[4]:>8}  {len(u_s.get(s, [])):>9}  {status}")
    print('-' * 100)
    print(f"{'TOTAL':>7}  {len(df):>7,}  {len(dups):>5}  {len(frac):>5}  "
          f"{len(raw_over):>8}  {len(sum_over):>8}  {len(bad_rounds):>8}  "
          f"{len(unavailable):>9}")

    if dups:
        print()
        print('=' * 100)
        print(f'CHECK 1  DUPLICATE Season+Round+player+club  ({len(dups)} group(s))')
        print('=' * 100)
        print('The model sums these. "total" is what it trains on as one game.')
        print()
        for d in dups[:detail]:
            flag = '  BREACHES CEILING' if d['total'] > VOTE_CEILING else ''
            print(f"  {d['season']} R{d['round']:<2} {d['player']} ({d['club']})"
                  f"  ->  total {d['total']:g}{flag}")
            for fixture, v in d['parts']:
                print(f"        {v:>6g}  in  {fixture}")
        if len(dups) > detail:
            print(f"  ... {len(dups) - detail} more, raise --detail to see them")

    if frac:
        print()
        print('=' * 100)
        print(f'CHECK 2  FRACTIONAL Coaches.Votes  ({len(frac)} row(s))')
        print('=' * 100)
        print('Votes are integers. A fraction is a different quantity in this column.')
        print()
        byfix = {}
        for f in frac:
            byfix.setdefault(f['fixture'], []).append(f)
        for fixture, rows in sorted(byfix.items(), key=lambda kv: -len(kv[1])):
            ss = sorted({r['season'] for r in rows})
            rr = sorted({r['round'] for r in rows})
            print(f"  {len(rows):>4} row(s)  {fixture}")
            print(f"        seasons {ss}  rounds {rr}")
        print()
        for f in frac[:detail]:
            print(f"  {f['season']} R{f['round']:<2} {f['player']} ({f['club']})"
                  f"  {f['votes']:g}  in  {f['fixture']}")
        if len(frac) > detail:
            print(f"  ... {len(frac) - detail} more, raise --detail to see them")

    if raw_over or sum_over:
        print()
        print('=' * 100)
        print(f'CHECK 3  ABOVE THE CEILING OF {VOTE_CEILING}  '
              f'({len(raw_over)} as stored, {len(sum_over)} after summing)')
        print('=' * 100)
        print('As stored is the archive. After summing is what the model sees.')
        print()
        for r in raw_over[:detail]:
            print(f"  stored  {r['season']} R{r['round']:<2} {r['player']} "
                  f"({r['club']})  {r['votes']:g}  in  {r['fixture']}")
        if len(raw_over) > detail:
            print(f"  ... {len(raw_over) - detail} more stored")
        print()
        for r in sum_over[:detail]:
            src = f"{r['n']} rows summed" if r['n'] > 1 else 'single row'
            print(f"  summed  {r['season']} R{r['round']:<2} {r['player']} "
                  f"({r['club']})  {r['total']:g}  ({src})")
        if len(sum_over) > detail:
            print(f"  ... {len(sum_over) - detail} more summed")

    if bad_rounds:
        print()
        print('=' * 100)
        print(f'CHECK 4  ROUND TOTAL IS NOT {EXPECTED_VOTES_PER_GAME} x GAMES  '
              f'({len(bad_rounds)} round(s))')
        print('=' * 100)
        print('Games counted from fitzroy_stats_all.csv / game_level_2006.csv,')
        print('never from the coaches file, whose fixture columns are what is suspect.')
        print()
        print(f"  {'season':>7} {'round':>6} {'votes':>8} {'expected':>9} "
              f"{'games':>6} {'rows':>6}  delta")
        for b in bad_rounds[:detail]:
            delta = b['votes'] - b['expected']
            print(f"  {b['season']:>7} {b['round']:>6} {b['votes']:>8g} "
                  f"{b['expected']:>9g} {b['games']:>6} {b['rows']:>6}  {delta:+g}")
        if len(bad_rounds) > detail:
            print(f"  ... {len(bad_rounds) - detail} more, raise --detail to see them")

    if unavailable:
        print()
        print(f'DENOMINATOR UNAVAILABLE  ({len(unavailable)} round(s), not a failure)')
        print('  Finals, which the denominator sources drop as string-labelled rounds.')
        print('  Listed so no round disappears from the report without saying so.')
        by = {}
        for u in unavailable:
            by.setdefault(u['season'], []).append(u['round'])
        for s in sorted(by):
            print(f"    {s}: rounds {sorted(by[s])}")


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Validate the historical coaches vote archive. Reports only, '
                    'never edits. Exit 1 if any check fires.')
    p.add_argument('--season', type=int, action='append', default=None,
                   metavar='YEAR', help='limit to a season, repeatable')
    p.add_argument('--detail', type=int, default=25, metavar='N',
                   help='max rows printed per check, default 25')
    p.add_argument('--coaches', default=str(COACHES_CSV),
                   help='path to the coaches archive')
    args = p.parse_args(argv)

    path = Path(args.coaches)
    if not path.exists():
        return _fail(f'{path} not found')

    print(f'Reading {path.name}')
    df = load_coaches(path)
    print(f'  {len(df):,} rows, seasons {int(df.Season.min())} to {int(df.Season.max())}')

    if args.season:
        df = df[df.Season.isin(args.season)]
        print(f'  filtered to {sorted(args.season)}: {len(df):,} rows')
        if df.empty:
            # An empty frame passes every check vacuously, which would print a
            # clean report having tested nothing. That is a failed run.
            return _fail(f'no rows for season(s) {sorted(args.season)}, nothing tested')

    unmapped, n_unmapped = _unmapped_clubs(df)
    if unmapped:
        print(f'  note: {n_unmapped} row(s) carry a club abbreviation TEAM_ABBREV '
              f'does not resolve: {unmapped}')

    games = load_game_counts()
    print(f'  denominator: {len(games):,} season-rounds with a game count')

    dups = check_duplicates(df)
    frac = check_fractional(df)
    raw_over, sum_over = check_ceiling(df)
    bad_rounds, unavailable = check_round_totals(df, games)

    print_report(df, dups, frac, raw_over, sum_over, bad_rounds, unavailable,
                 args.detail)

    fired = [n for n, c in (('duplicate', dups), ('fractional', frac),
                            ('ceiling stored', raw_over), ('ceiling summed', sum_over),
                            ('round total', bad_rounds)) if c]
    print()
    if fired:
        print(f'FAIL  checks firing: {", ".join(fired)}')
        return 1
    print('OK  all four checks clean')
    return 0


if __name__ == '__main__':
    sys.exit(main())
