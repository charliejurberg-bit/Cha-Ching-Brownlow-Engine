"""Fewest games played to reach a cumulative stat threshold, 1965-2026.

    build_fewest_games(stat, threshold, top_n=10)

Ranks players by how many appearances they needed to accumulate `threshold` of
`stat`, fewest first. Only completed runs rank: a player still short of the
threshold appears nowhere.

RECON / DRAFT OUTPUT ONLY. Like club_aliases and all_time_tables, this module
must not be imported by features.py, brownlow_model.py or predict_2026.py: it
canonicalises club strings, which would change the model's feature space without
a retrain.

All matches, home-and-away AND finals
-------------------------------------
This counts appearances, not rates, so a finals game is a game and is included.
Both archive files carry finals every season (labels EF/GF/PF/QF/SF, 283 finals
games 1965-2006 and 172 across 2007-2025). `game_level_2026.csv` carries none:
its Round values run 1-24 with no string labels, because the prediction pipeline
drops finals. **2026 therefore contributes home-and-away games only**, which is
stated in every header this module writes.

The game key includes Date
--------------------------
Four drawn finals were replayed, and a key of season + round + teams collapses
each pair into one fixture, deleting a game from every player in both team
lists:

    1972 SF  Carlton v Richmond              61-61  replayed 1972-09-23
    1977 GF  Collingwood v North Melbourne    76-76  replayed 1977-10-01
    1990 QF  Collingwood v West Coast         90-90  replayed 1990-09-15
    2010 GF  Collingwood v St Kilda           68-68  replayed 2010-10-02

Three of the four involve Collingwood, so the undercount is not evenly spread
and would bias any "fewest games" ranking. With Date in the key every season's
fixture count matches data_history/match_counts_baseline.csv exactly, and no
season 1965-2025 is missing a home-and-away fixture.

Per-stat floors
---------------
A stat's column exists long before it is populated, and a present-but-empty
column is not coverage. Each floor below is the first season from which the
column is non-null on every row with no later gap, measured per season across
all three sources. The floors are not all the first season the column polls a
value: four stats poll earlier and then break.

Player identity is keyed on `ID`, never name, and every output row prints the ID
beside the name.
"""

import os
import sys

import pandas as pd

import features as feat
from club_aliases import canonical_club

# ─────────────────────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────────────────────

ARCHIVE = "data_history/fitzroy_stats_1965_2006.csv.gz"
MODERN = "fitzroy_stats_all.csv"
CURRENT = "predictions/game_level_2026.csv"
DRAFTS_DIR = "drafts"

# ─────────────────────────────────────────────────────────────
# Per-stat floors, and the recon evidence for each
# ─────────────────────────────────────────────────────────────

# Measured per season 1965-2026 across all three sources: row count, non-null
# count, and whether every non-null value is zero. No column is ever all-zero in
# this range, so the failure mode is all-null or partially-null, not zero-fill.
#
# Four stats poll a value earlier than their floor and then break, which is why
# the floor is "first season with unbroken full coverage" and not "first season
# populated":
#
#   Disposals       first 1965, but 1975 is 5,280/5,520 non-null (96%)
#   Frees.For       first 1965, but 1975-1978 run 94-96%
#   Frees.Against   first 1965, but 1975-1978 run 94-96%
#   Hit.Outs        first 1966, then collapses repeatedly: 1972 (94%), 1974
#                   (360/5,520 = 7%), 1975 (43%), 1977-1978 (97-99%). 1974 is
#                   the reason this one cannot be trusted before 1979.
#
# The rest are clean: all-null until the floor, fully populated from it on.
#
#   Tackles         all-null 1965-1986, populated 1987 on
#   Clearances      all-null 1965-1997, populated 1998 on
#   One.Percenters  all-null 1965-1998, populated 1999 on
#   Goal.Assists    all-null 1965-2002, populated 2003 on
#
# Score_Involvements is engineered, not stored, so its floor is the latest of
# its four inputs: Goals 1965, Inside.50s 1998, Marks.Inside.50 1999 and
# Goal.Assists 2003. Reconstructing it earlier would silently drop the assists
# term and produce a different statistic under the same name.
#
# Wins need only Home.Away and the two score columns, which are complete from
# 1965, so its floor is the start of the data.
STAT_FLOORS = {
    'Disposals': (1976, "populated from 1965 but 1975 is only 96% non-null, "
                        "so unbroken coverage starts 1976"),
    'Frees.For': (1979, "populated from 1965 but 1975-1978 run 94-96% "
                        "non-null, so unbroken coverage starts 1979"),
    'Frees.Against': (1979, "populated from 1965 but 1975-1978 run 94-96% "
                            "non-null, so unbroken coverage starts 1979"),
    'Hit.Outs': (1979, "first polls in 1966 but collapses repeatedly, worst at "
                       "1974 where only 360 of 5,520 rows are non-null (7%), "
                       "so unbroken coverage starts 1979"),
    'Tackles': (1987, "all-null 1965-1986, fully populated from 1987"),
    'Clearances': (1998, "all-null 1965-1997, fully populated from 1998"),
    'One.Percenters': (1999, "all-null 1965-1998, fully populated from 1999"),
    'Goal.Assists': (2003, "all-null 1965-2002, fully populated from 2003"),
    'Score_Involvements': (2003, "engineered from Goals (1965), Inside.50s "
                                 "(1998), Marks.Inside.50 (1999) and "
                                 "Goal.Assists (2003); the floor is the latest "
                                 "of the four"),
    'Wins': (1965, "needs only Home.Away and the two score columns, complete "
                   "from the start of the data"),
}

# Reconstructed by features.add_row_stats(), never re-typed here.
ENGINEERED = {'Score_Involvements'}
# Derived from Home.Away / Home.score / Away.score. A draw is neither a win nor
# a loss and contributes nothing toward the threshold.
DERIVED_WIN = 'Wins'

ELIGIBILITY_RULE = (
    "A player is included only if their first game anywhere in the data falls "
    "on or after this stat's floor season. Anyone who debuted earlier is "
    "excluded outright, because their pre-floor games are invisible to the "
    "stat and they would rank as having reached the threshold faster than they "
    "actually did."
)

# Columns read from every source. The engineered path needs more than the stat
# itself, because features.add_row_stats() computes the whole row-stat block.
_BASE_COLS = ('Season', 'Round', 'Date', 'ID', 'Player', 'Player_Name',
              'Playing.for', 'Home.team', 'Away.team', 'Home.score',
              'Away.score', 'Home.Away')
_STAT_COLS = ('Disposals', 'Frees.For', 'Frees.Against', 'Hit.Outs', 'Tackles',
              'Clearances', 'One.Percenters', 'Goal.Assists')
# Taken from features.NUMERIC_STATS rather than restated, because
# add_row_stats() coerces every one of them and reads absent columns as the
# scalar 0, which then fails on .fillna. Deriving the list means a change to
# features.py cannot leave this projection silently short.
_ENG_COLS = tuple(feat.NUMERIC_STATS)

_WANTED = set(_BASE_COLS) | set(_STAT_COLS) | set(_ENG_COLS)

_GAME_KEY = ['Season', 'Round', 'Date', 'Home.team', 'Away.team']


# ─────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────

def _read_source(path, label, prov):
    """One source to a frame, with its own row and finals counts recorded."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} source absent: {path}")
    df = pd.read_csv(path, low_memory=False, usecols=lambda c: c in _WANTED)
    # game_level_2026.csv carries both Player and Player_Name; the archives
    # carry only Player. Normalise to one column before the concat.
    if 'Player' not in df.columns and 'Player_Name' in df.columns:
        df = df.rename(columns={'Player_Name': 'Player'})
    df = df.drop(columns=[c for c in ('Player_Name',) if c in df.columns])
    df['_source'] = label
    prov[f'{label}_rows'] = len(df)
    # Finals are KEPT. Counted only so the header can state what each source
    # contributes; a string round label is a final.
    is_final = pd.to_numeric(df['Round'], errors='coerce').isna()
    prov[f'{label}_final_rows'] = int(is_final.sum())
    prov[f'{label}_seasons'] = (int(df['Season'].min()), int(df['Season'].max()))
    return df


def load_frame(archive=ARCHIVE, modern=MODERN, current=CURRENT):
    """All three sources concatenated, all matches, plus header provenance."""
    prov = {}
    parts = [_read_source(archive, 'archive', prov),
             _read_source(modern, 'modern', prov),
             _read_source(current, 'current', prov)]
    df = pd.concat(parts, ignore_index=True)

    df['Season'] = pd.to_numeric(df['Season'], errors='coerce')
    df = df[df['Season'].notna()].copy()
    df['Season'] = df['Season'].astype(int)

    seasons = {}
    for label in ('archive', 'modern', 'current'):
        lo, hi = prov[f'{label}_seasons']
        for s in range(lo, hi + 1):
            seasons.setdefault(s, []).append(label)
    dupes = sorted(s for s, labs in seasons.items() if len(labs) > 1)
    if dupes:
        raise ValueError(
            f"sources overlap on season(s) {dupes}, which double-counts every "
            f"game in them")

    # Identity is keyed on ID, so a row without one cannot be attributed.
    prov['nan_id_dropped'] = int(df['ID'].isna().sum())
    df = df[df['ID'].notna()].copy()
    df['ID'] = df['ID'].astype(int)

    # Date is part of the game key, so a row without one cannot be ordered.
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    prov['nan_date_dropped'] = int(df['Date'].isna().sum())
    df = df[df['Date'].notna()].copy()

    df['Club'] = df['Playing.for'].map(canonical_club)
    for c in ('Home.score', 'Away.score'):
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # Every add_row_stats input must be a real column in the concatenated frame.
    # A missing one would be read as the scalar 0 and silently zero the stat for
    # every row rather than failing.
    absent = [c for c in _ENG_COLS if c not in df.columns]
    if absent:
        raise ValueError(
            f"{len(absent)} features.NUMERIC_STATS column(s) absent from the "
            f"concatenated frame, so add_row_stats would zero-fill them: "
            f"{absent}")

    prov['rows'] = len(df)
    prov['season_min'] = int(df['Season'].min())
    prov['season_max'] = int(df['Season'].max())
    prov['games'] = len(df.drop_duplicates(subset=_GAME_KEY))
    finals_mask = pd.to_numeric(df['Round'], errors='coerce').isna()
    prov['finals_games'] = len(
        df[finals_mask].drop_duplicates(subset=_GAME_KEY))
    prov['ha_games'] = prov['games'] - prov['finals_games']
    prov['players'] = int(df['ID'].nunique())
    return df, prov


def _stat_series(work, stat):
    """The per-game contribution of `stat` on the working frame.

    Score_Involvements comes from features.add_row_stats() rather than being
    re-typed, and Wins from the same module's W/L/D derivation. Everything else
    is a stored column.
    """
    if stat in ENGINEERED or stat == DERIVED_WIN:
        # add_row_stats mutates and needs Home.score/Away.score/Home.Away
        # already coerced, which load_frame does. It computes the whole row-stat
        # block, of which Score_Involvements and Is_Win are the two we use.
        work = feat.add_row_stats(work.copy())
        if stat == DERIVED_WIN:
            # A draw is Outcome 'D', so Is_Win is 0 and it contributes nothing.
            return work['Is_Win'].astype(float), work
        return work['Score_Involvements'].astype(float), work
    return pd.to_numeric(work[stat], errors='coerce'), work


# ─────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────

def _who(name, player_id):
    label = "unknown" if pd.isna(name) else str(name)
    return f"{label} (ID {int(player_id)})"


def _clubs_in_season_order(df):
    """ID to its clubs ordered by the first season at each, comma separated."""
    first = (df.groupby(['ID', 'Club'], dropna=False)['Season'].min()
               .reset_index().sort_values(['ID', 'Season', 'Club']))
    return (first.groupby('ID')['Club']
                 .apply(lambda s: ", ".join(x for x in s
                                            if isinstance(x, str))))


def _plural(n, unit):
    return f"{n} {unit[:-1] if n == 1 and unit.endswith('s') else unit}"


def _gap_line(rows, field, unit):
    """Rank 1 to rank 2 gap. A tie is reported as a tie, not as 'gap 0'."""
    if len(rows) < 2:
        return (f"Only {len(rows)} ranked entr"
                f"{'y' if len(rows) == 1 else 'ies'}, so no rank 1 to rank 2 "
                f"gap exists.")
    gap = rows[1][field] - rows[0][field]
    if gap == 0:
        return (f"**Rank 1 and rank 2 are level** on "
                f"{_plural(rows[0][field], unit)}, so the gap is 0.")
    return (f"**Gap between rank 1 and rank 2: {_plural(gap, unit)}** "
            f"({rows[0][field]} against {rows[1][field]}).")


def _slug(stat):
    return stat.replace('.', '_').replace(' ', '_').lower()


def _write(lines, name, out_dir=DRAFTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


# ─────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────

def build_fewest_games(stat, threshold, top_n=10, out_dir=DRAFTS_DIR, **kw):
    """Players ranked by games played to reach `threshold` of `stat`."""
    if stat not in STAT_FLOORS:
        raise ValueError(
            f"unknown stat {stat!r}, expected one of "
            f"{', '.join(sorted(STAT_FLOORS))}")
    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")

    floor, why = STAT_FLOORS[stat]
    df, prov = load_frame(**kw)

    # Debut is measured on the FULL frame, never on the floor-restricted one.
    # Measuring it after the restriction would read a 1974 debutant's first
    # post-floor game as their debut and let them in.
    debut = df.groupby('ID')['Season'].min()
    eligible = set(debut[debut >= floor].index)
    excluded = set(debut.index) - eligible

    work = df[df['ID'].isin(eligible)].copy()
    # Eligible players cannot have a pre-floor game by construction. Asserted
    # rather than assumed, because it is also what guarantees no engineered
    # value is computed before its floor.
    if len(work) and int(work['Season'].min()) < floor:
        raise ValueError(
            f"eligible rows reach back to {int(work['Season'].min())}, before "
            f"the {stat} floor of {floor}; debut filtering is broken")

    values, work = _stat_series(work, stat)
    # No leading underscore on these: itertuples renames underscore-prefixed
    # columns positionally, the same trap this repo documents for dotted names
    # like 'Playing.for'. Rows are read by label off records() below regardless.
    work['statval'] = values.fillna(0.0)
    prov['nan_stat_rows'] = int(values.isna().sum())

    # One row per appearance, ordered so the cumulative sum walks a career.
    work = work.sort_values(['ID', 'Date', 'Season', 'Round'],
                            kind='mergesort').reset_index(drop=True)
    work['game_no'] = work.groupby('ID').cumcount() + 1
    work['cumval'] = work.groupby('ID')['statval'].cumsum()

    reached = work[work['cumval'] >= threshold]
    first = reached.groupby('ID').head(1)

    clubs = _clubs_in_season_order(work)
    rows = []
    for r in first.to_dict('records'):
        pid = int(r['ID'])
        rows.append({
            'who': _who(r['Player'], pid),
            'clubs': clubs.get(pid, ""),
            'debut': int(debut.loc[pid]),
            'games': int(r['game_no']),
            'on': r['Date'].strftime('%Y-%m-%d'),
            'total': float(r['cumval']),
        })
    rows.sort(key=lambda x: (x['games'], x['on'], x['who']))
    shown = rows[:top_n]

    unit = "games"
    L = [f"# Fewest games to {threshold:g} {stat}", ""]
    L.append(f"Players ranked by how many appearances they needed to "
             f"accumulate {threshold:g} {stat}, fewest first. Only completed "
             f"runs rank: a player still short of {threshold:g} appears "
             f"nowhere.")
    L.append("")
    L.append(f"Source files: `{ARCHIVE}` "
             f"({prov['archive_seasons'][0]}-{prov['archive_seasons'][1]}, "
             f"{prov['archive_rows']:,} rows), `{MODERN}` "
             f"({prov['modern_seasons'][0]}-{prov['modern_seasons'][1]}, "
             f"{prov['modern_rows']:,} rows) and `{CURRENT}` "
             f"({prov['current_seasons'][0]}-{prov['current_seasons'][1]}, "
             f"{prov['current_rows']:,} rows).")
    L.append("")
    L.append(f"**All matches, home-and-away and finals**, because this counts "
             f"appearances rather than rates. The frame holds "
             f"**{prov['games']:,} games** ({prov['ha_games']:,} home-and-away "
             f"and {prov['finals_games']:,} finals) over {prov['rows']:,} "
             f"player-game rows, seasons {prov['season_min']}-"
             f"{prov['season_max']}.")
    L.append("")
    L.append(f"**2026 contributes home-and-away games only and no finals.** "
             f"`{CURRENT}` carries no string round labels because the "
             f"prediction pipeline drops finals, so a 2026 debutant's tally is "
             f"complete for the home-and-away season and nothing else.")
    L.append("")
    L.append(f"**Floor season for {stat}: {floor}.** {why[0].upper()}{why[1:]}.")
    L.append("")
    L.append(f"**Eligibility.** {ELIGIBILITY_RULE}")
    L.append("")
    L.append(f"**{len(excluded):,} players excluded as pre-{floor} debutants**, "
             f"leaving {len(eligible):,} of the frame's {prov['players']:,} "
             f"players eligible. Of those, {len(rows):,} reached "
             f"{threshold:g} {stat} and rank below.")
    L.append("")
    L.append("The game key includes `Date`, so the four replayed drawn finals "
             "(1972 SF, 1977 GF, 1990 QF, 2010 GF) count as two games each "
             "rather than collapsing into one.")
    L.append("")
    L.append("Players are keyed on `ID`, never on name, and each row prints the "
             "ID beside the name. Clubs are canonicalised through "
             "`club_aliases.canonical_club()` and listed in the order the "
             "player first appeared for each.")
    L.append("")
    L.append(_gap_line(shown, 'games', unit))
    L.append("")
    L.append(f"Full ranked table to {top_n}, of {len(rows):,} players who "
             f"reached {threshold:g}.")
    L.append("")
    L.append("| # | player | clubs | debut | games to "
             f"{threshold:g} | reached on |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(shown, 1):
        L.append("| " + " | ".join([
            str(i), r['who'], str(r['clubs']), str(r['debut']),
            str(r['games']), r['on']]) + " |")
    L.append("")

    name = f"fewest_games_{_slug(stat)}_{threshold:g}"
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} players reached "
          f"{threshold:g} {stat}, top {len(shown)} shown)")
    print(f"   floor {floor} | {len(excluded):,} pre-floor debutants excluded "
          f"| {len(eligible):,} eligible")
    print("   " + _gap_line(shown, 'games', unit).replace("**", ""))
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_USAGE = ("usage: python fewest_games.py <stat> <threshold> [top_n]\n"
          "  stat: " + " | ".join(sorted(STAT_FLOORS)))


def main(argv):
    if len(argv) not in (2, 3):
        print(_USAGE, file=sys.stderr)
        return 2
    stat = argv[0]
    if stat not in STAT_FLOORS:
        print(f"unknown stat {stat!r}, expected one of "
              f"{', '.join(sorted(STAT_FLOORS))}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        threshold = float(argv[1])
    except ValueError:
        print(f"threshold must be a number, got {argv[1]!r}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    if threshold <= 0:
        print(f"threshold must be positive, got {threshold:g}", file=sys.stderr)
        return 2
    top_n = 10
    if len(argv) == 3:
        try:
            top_n = int(argv[2])
        except ValueError:
            print(f"top_n must be an integer, got {argv[2]!r}", file=sys.stderr)
            print(_USAGE, file=sys.stderr)
            return 2
        if top_n < 2:
            print(f"top_n must be at least 2, got {top_n}: the rank 1 to rank "
                  f"2 gap needs two rows", file=sys.stderr)
            return 2
    build_fewest_games(stat, threshold, top_n=top_n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
