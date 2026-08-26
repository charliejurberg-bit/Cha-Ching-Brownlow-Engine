"""Brownlow vote milestones a player could pass on count night.

    python scripts/vote_milestones.py "Sam Walsh"
    python scripts/vote_milestones.py --top 20        # sweep the countdown

Answers the question the countdown posts keep needing: what does this player
cross if the model is right, and what does he cross if he runs hot? Career
totals, all-time position, club records and multi-club feats, each reported
against the four 2026 scenarios (floor, expected, rounded 3-2-1, ceiling).

THE ARCHIVE, AND WHY THE MERGE IS THE WHOLE JOB
Per-game votes exist from 1984. Before that the only source is
data_history/brownlow_seasons_1924_1983.csv, which carries SEASON TOTALS and no
game attribution. Both halves are needed and neither is optional:

  - 1984 onward alone is not "all time". Thirty-six players cleared 100 career
    votes inside 1924-1983 by itself (Gary Dempsey 246, Leigh Matthews 194, Bob
    Skilton 180), so a rank computed from 1984 flatters every modern player.
  - The pre-1984 file has no fitzRoy ID, only a name, so it cannot simply be
    concatenated: a player active across the boundary would be counted once per
    half under two different keys, or worse, merged into a namesake.

So the pre-1984 totals are attached to a fitzRoy ID by name, and only where
exactly ONE post-1984 career carries that name. Where two do (Gary Ablett is
the case that matters, senior 1982-1996 and junior 2002-2020) the entry is
reported as ambiguous and left off rather than guessed at, because handing
senior's 1982-83 votes to junior would be a fabricated record. Names with no
post-1984 career stand alone as retired players.

WHAT THIS CANNOT DO
Draft-position records ("most votes by a No.1 pick") are NOT computable here.
Nothing in this repo records draft position; fitzroy_stats_all.csv carries Age,
DOB and Career.Games but no draft data. That angle needs an external source and
is flagged rather than estimated.

Nothing here is post-ready. It is research, and a claim of an all-time position
should be checked against a published list before it goes out: this archive is
assembled from two sources with a name-matched join across the seam.
"""

import argparse
import sys

import pandas as pd

COLS = ['Season', 'First.name', 'Surname', 'ID', 'Playing.for', 'Brownlow.Votes']
OLD = 'data_history/fitzroy_stats_1965_2006.csv.gz'
NEW = 'fitzroy_stats_all.csv'
PRE = 'data_history/brownlow_seasons_1924_1983.csv'
ROUND_NUMBERS = (50, 100, 150, 200, 250)


def modern():
    """Per-game votes 1984-2025, keyed on fitzRoy ID."""
    o = pd.read_csv(OLD, low_memory=False, usecols=COLS)
    n = pd.read_csv(NEW, low_memory=False, usecols=COLS)
    for d in (o, n):
        d['Season'] = pd.to_numeric(d['Season'], errors='coerce')
    a = pd.concat([o[o.Season.between(1984, 2006)], n[n.Season >= 2007]],
                  ignore_index=True)
    a['Brownlow.Votes'] = pd.to_numeric(a['Brownlow.Votes'], errors='coerce').fillna(0)
    a = a[a.ID.notna()].copy()
    a['ID'] = a.ID.astype(int)
    a['name'] = a['First.name'].str.strip() + ' ' + a['Surname'].str.strip()
    return a


def career_table(a):
    """One row per player, votes merged across the 1984 seam. See the docstring."""
    car = a.groupby('ID').agg(name=('name', 'first'),
                              modern_votes=('Brownlow.Votes', 'sum'),
                              first=('Season', 'min'),
                              last=('Season', 'max')).reset_index()

    pre = pd.read_csv(PRE)
    pre = pre[pre.Season <= 1983].groupby('Player')['Votes'].sum()

    # Attach a pre-1984 total only where exactly one modern career owns the name
    # AND that career reaches back to the boundary. A career starting in 2002
    # cannot own votes cast in 1983.
    boundary = car[car['first'] <= 1990]
    counts = boundary.name.value_counts()
    ambiguous, attached = [], {}
    for nm, v in pre.items():
        hits = boundary[boundary.name == nm]
        if len(hits) == 1:
            attached[int(hits.iloc[0].ID)] = float(v)
        elif len(hits) > 1:
            ambiguous.append(nm)
    car['pre_votes'] = car.ID.map(attached).fillna(0.0)
    car['votes'] = car.modern_votes + car.pre_votes

    # Players who finished before 1984 never appear in the modern archive, so
    # they are added as standalone rows or the ranking is missing its top end.
    known = set(car[car['first'] <= 1990].name)
    retired = pre[~pre.index.isin(known)]
    extra = pd.DataFrame({'ID': range(-1, -len(retired) - 1, -1),
                          'name': retired.index, 'modern_votes': 0.0,
                          'first': 0, 'last': 1983,
                          'pre_votes': retired.values, 'votes': retired.values})
    car = pd.concat([car, extra], ignore_index=True)
    return car.sort_values('votes', ascending=False).reset_index(drop=True), ambiguous


def scenarios(player):
    """2026 floor / expected / rounded / ceiling for one player."""
    se = pd.read_csv('predictions/season_2026.csv')
    sp = pd.read_csv('predictions/season_projection_2026.csv')
    g = pd.read_csv('predictions/game_level_2026.csv').drop_duplicates(
        ['Round_num', 'ID'], keep='first').copy()
    g['_k'] = (g.Round_num.astype(str) + '|' + g['Home.team'].astype(str)
               + '|' + g['Away.team'].astype(str))
    g = g.sort_values(['_k', 'Exp_Votes', 'Poll_Prob', 'P_3', 'Player_Name'],
                      ascending=[True, False, False, False, True])
    g['Hard'] = (g.groupby('_k').cumcount() + 1).map({1: 3, 2: 2, 3: 1}).fillna(0)
    e = se[se.Player_Name == player]
    r = sp[sp.Player == player]
    if e.empty:
        return None
    hard = float(g[g.Player_Name == player].Hard.sum())
    ceil = max(float(r.Ceiling_Projection.iloc[0]), hard) if len(r) else hard
    return {'floor': float(r.Floor_Projection.iloc[0]) if len(r) else 0.0,
            'expected': float(e.Exp_Total_Votes.iloc[0]),
            'rounded': hard, 'ceiling': ceil,
            'rank': int((se.Exp_Total_Votes > e.Exp_Total_Votes.iloc[0]).sum()) + 1}


def report(player, a, car, amb, sc):
    row = car[car.name == player]
    if row.empty:
        print(f"  {player}: no career votes in the archive")
        return
    if len(row) > 1:
        print(f"  {player}: {len(row)} players share this name; using the active one")
        row = row[row.last >= 2020]
    row = row.iloc[0]
    have = float(row.votes)
    order = list(car.votes)
    rank_now = sum(1 for v in order if v > have) + 1

    print(f"\n{'=' * 66}\n{player}   (career votes to end of 2025: {have:.0f}, "
          f"{rank_now} all time)\n{'=' * 66}")
    if sc is None:
        print("  no 2026 projection")
        return
    print(f"  2026 leaderboard position: {sc['rank']}")
    print(f"  {'scenario':<11}{'2026':>7}{'career':>9}{'all-time':>10}   milestone")
    for lab in ('floor', 'expected', 'rounded', 'ceiling'):
        v = sc[lab]
        tot = have + v
        rk = sum(1 for x in order if x > tot) + 1
        crossed = [str(m) for m in ROUND_NUMBERS if have < m <= tot]
        note = ("crosses " + ", ".join(crossed)) if crossed else ""
        print(f"  {lab:<11}{v:>7.1f}{tot:>9.1f}{rk:>10}   {note}")
    nxt = next((m for m in ROUND_NUMBERS if m > have), None)
    if nxt:
        print(f"  -> needs {nxt - have:.0f} for {nxt}; model expects {sc['expected']:.1f}")

    # Club splits: multi-club polling is its own class of record.
    pv = a[(a.name == player) & (a['Brownlow.Votes'] > 0)]
    by = pv.groupby('Playing.for')['Brownlow.Votes'].sum().sort_values(ascending=False)
    if len(by):
        print("  votes by club: " + ", ".join(f"{c} {v:.0f}" for c, v in by.items()))
        if len(by) > 1:
            print(f"  -> has polled for {len(by)} clubs")
    seasons = pv.groupby('Season')['Brownlow.Votes'].sum()
    if len(seasons):
        best = seasons.max()
        print(f"  best season: {best:.0f} ({int(seasons.idxmax())})"
              f"   2026 expected {sc['expected']:.1f}"
              f"{'  -> would be a career best' if sc['expected'] > best else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player", nargs="?")
    ap.add_argument("--top", type=int, help="sweep the top N of the 2026 board")
    args = ap.parse_args()

    a = modern()
    car, amb = career_table(a)
    print(f"career archive: {len(car):,} players, votes 1924-2025 "
          f"(per-game from 1984, season totals before)")
    if amb:
        print(f"ambiguous pre-1984 names, left unmerged: {', '.join(amb)}")

    if args.top:
        se = pd.read_csv('predictions/season_2026.csv').nlargest(args.top, 'Exp_Total_Votes')
        for p in se.Player_Name:
            report(p, a, car, amb, scenarios(p))
    elif args.player:
        report(args.player, a, car, amb, scenarios(args.player))
    else:
        ap.error("give a player name or --top N")
    return 0


if __name__ == '__main__':
    sys.exit(main())
