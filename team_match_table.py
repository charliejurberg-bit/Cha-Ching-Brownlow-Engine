"""The shared match table for team_h2h.py. One row per match, 1965 onward.

    from team_match_table import load_match_table
    m = load_match_table()

No match-level file exists in a tracked directory, so the table is derived at
runtime from three player-level fitzRoy files and deduplicated down to matches.
See team_h2h_spec.md section 2.

This module loads and verifies. It does not orient to a subject team, does not
difference the quarter columns, and computes no record of any kind. All three
belong to the consumer:

  - orientation, because the subject is away in roughly half of any series
  - differencing, because the cumulative values are also what a half-time or
    three-quarter-time lead figure needs, and pre-differencing destroys them
  - records, because scope rules differ per section

What this module does guarantee is in `load_match_table`'s docstring: ten
assertions from spec section 12, every one of which raises rather than warns.

Two things the sources get wrong if read naively, both recorded in the spec:

  - The quarter columns are NOT `G.B` strings. They are separate int64 goal and
    behind columns plus a pre-computed `P` points column. A string parser
    crashes on them. `P == G*6 + B` is asserted here rather than assumed.
  - `HQ4P` is the FULL-TIME score, not the final score. Three finals went to
    extra time and the record books use the extra-time result. `home_score`
    and `away_score` therefore take extra time where it exists, while the
    quarter columns stay regulation-only, and `went_to_extra_time` marks the
    rows so no consumer can mix the two silently.
"""

import os

import pandas as pd

from club_aliases import canonical_club

# ---------------------------------------------------------------- sources

# (path, label, first season, last season). The label is carried into the
# output as `source_file` so every downstream figure can name where it came
# from, which spec section 11 requires of every raw count.
SOURCES = (
    ('data_history/fitzroy_stats_1965_2006.csv.gz', 1965, 2006),
    ('fitzroy_stats_all.csv', 2007, 2025),
    ('data_2026/afltables_2026.csv', 2026, 2026),
)

BASELINE = 'data_history/match_counts_baseline.csv'

# Seasons the baseline freezes. 2026 is live and is deliberately not baselined:
# it gains matches every week and an assertion against it would fail by design.
BASELINE_LO, BASELINE_HI = 1965, 2025

FINALS_CODES = frozenset({'QF', 'EF', 'SF', 'PF', 'GF'})

# Spec section 3: exactly three matches went to extra time, 1994 QF, 2007 SF and
# 2017 EF. A fourth means a new finding or a broken HQETP read, and assertion 10
# stops the build either way.
EXPECTED_EXTRA_TIME = 3

QUARTERS = (1, 2, 3, 4)
POINTS_COLS = tuple(f'{side}Q{q}P' for side in 'HA' for q in QUARTERS)
GOAL_COLS = tuple(f'{side}Q{q}G' for side in 'HA' for q in QUARTERS)
BEHIND_COLS = tuple(f'{side}Q{q}B' for side in 'HA' for q in QUARTERS)
ET_COLS = ('HQETP', 'AQETP')

# The natural key. There is no match ID in any fitzRoy file, and Date is not
# optional: without it the four drawn-final replays collapse to one row each.
RAW_KEY = ('Season', 'Round', 'Home.team', 'Away.team', 'Date')

# Columns read from each source. Wider than the output, because assertions 6, 8
# and 9 verify columns this table does not retain.
SOURCE_COLS = (
    'Season', 'Round', 'Date', 'Venue', 'Local.start.time',
    'Home.team', 'Away.team', 'Home.score', 'Away.score',
    'ID', 'Jumper.No.', 'url',
) + POINTS_COLS + GOAL_COLS + BEHIND_COLS + ET_COLS

# Dtypes cast explicitly at load, per spec section 12 assertion 8. ID is int64
# in the 1965-2006 archive and float64 in the other two purely because those
# carry nulls, and Jumper.No. flips the other way. Concatenating without a cast
# promotes silently and prints an ID as 755.0.
DECLARED_DTYPES = {'ID': 'Float64', 'Jumper.No.': 'Float64'}

OUTPUT_COLS = (
    ['season', 'round', 'is_final', 'went_to_extra_time', 'venue', 'date',
     'day_of_week', 'local_start_time', 'home_team', 'away_team',
     'home_score', 'away_score']
    + list(POINTS_COLS) + list(ET_COLS) + ['source_file']
)


class MatchTableError(AssertionError):
    """A build assertion failed. The message names which one and why."""


def _fail(number, what, detail=''):
    raise MatchTableError(
        f'team_match_table assertion {number} FAILED: {what}'
        + (f'\n{detail}' if detail else '')
    )


# ---------------------------------------------------------------- loading

def _read_source(path):
    """Read one source file, cast the hazardous dtypes, return the whole frame.

    The frame is player-level here. Deduplication to matches happens in
    `_project`, after the per-file assertions that need player rows have run.
    """
    if not os.path.exists(path):
        _fail(0, f'source file not found: {path}')
    available = set(pd.read_csv(path, nrows=0).columns)
    missing = [c for c in SOURCE_COLS if c not in available]
    if missing:
        _fail(0, f'{path} is missing expected columns',
              f'  missing: {", ".join(missing)}')
    df = pd.read_csv(path, usecols=list(SOURCE_COLS), low_memory=False)
    for col, dtype in DECLARED_DTYPES.items():
        df[col] = df[col].astype(dtype)
    return df


def _project(df, path):
    """Reduce a player-level frame to one row per match, in output shape."""
    m = df.drop_duplicates(subset=list(RAW_KEY)).copy()

    label = df['Round'].astype(str).str.strip().str.upper()
    label = label.loc[m.index]
    m['is_final'] = label.isin(FINALS_CODES)

    # Partition before casting, per spec section 2. A blanket to_numeric would
    # coerce every finals code to NaN and take the finals out of the table
    # without saying so.
    unknown = m[~m['is_final'] & ~label.str.fullmatch(r'\d+')]
    if len(unknown):
        _fail(0, f'{path} carries a round label that is neither a digit nor a '
                 f'known finals code',
              '  ' + ', '.join(sorted(unknown['Round'].astype(str).unique())))
    rnd = m['Round'].astype(str).str.strip()
    # Object column holding an int for a home-and-away round and the code
    # string for a final. Built element-wise because a str-dtype series will
    # not accept an int assignment, and casting the whole column either
    # stringifies the rounds or NaNs the finals.
    m['round'] = [lab if fin else int(lab)
                  for lab, fin in zip(rnd, m['is_final'])]

    m['went_to_extra_time'] = m['HQETP'].notna() | m['AQETP'].notna()
    m['season'] = m['Season'].astype(int)
    m['venue'] = m['Venue']
    m['date'] = pd.to_datetime(m['Date'])
    m['day_of_week'] = m['date'].dt.day_name()
    m['local_start_time'] = m['Local.start.time'].astype(int)
    # canonical_club on BOTH sides. Applying it to one lost 22 Kangaroos
    # fixtures in 2007 during recon.
    m['home_team'] = m['Home.team'].map(canonical_club)
    m['away_team'] = m['Away.team'].map(canonical_club)
    m['home_score'] = m['Home.score'].astype(int)
    m['away_score'] = m['Away.score'].astype(int)
    m['source_file'] = path
    return m[OUTPUT_COLS]


# ------------------------------------------------------------- assertions

def _assert_baseline(table):
    """1. Per-season counts for the frozen range match the committed baseline.

    This is the guard against a 2026 refresh, or a re-fetch of any source,
    silently rewriting history. It is per-season rather than a total, because a
    total can net out: a season losing a match while another gains one passes a
    row-count check and fails this one.
    """
    if not os.path.exists(BASELINE):
        _fail(1, f'baseline file missing: {BASELINE}',
              '  Generate it once with write_baseline() and commit it. Without '
              'it there is nothing to detect a rewrite against.')
    base = pd.read_csv(BASELINE)
    frozen = table[(table.season >= BASELINE_LO) & (table.season <= BASELINE_HI)]
    got = (frozen.groupby('season')['is_final']
           .agg(ha_matches=lambda s: int((~s).sum()),
                finals_matches='sum').reset_index())
    got['finals_matches'] = got['finals_matches'].astype(int)
    merged = base.merge(got, on='season', how='outer',
                        suffixes=('_baseline', '_now'), indicator=True)
    bad = merged[(merged._merge != 'both')
                 | (merged.ha_matches_baseline != merged.ha_matches_now)
                 | (merged.finals_matches_baseline != merged.finals_matches_now)]
    if len(bad):
        head = bad.head(10).to_string(index=False)
        _fail(1, f'{len(bad)} season(s) disagree with {BASELINE}',
              f'  first {min(10, len(bad))}:\n{head}')


def _assert_no_nulls(table):
    """2. No null in any field this tool reads.

    HQETP and AQETP are excluded on purpose: they are null on every match that
    did not go to extra time, which is 10,466 of them.
    """
    checked = (['venue', 'date', 'local_start_time', 'home_score', 'away_score',
                'home_team', 'away_team', 'season', 'round', 'day_of_week']
               + list(POINTS_COLS))
    counts = {c: int(table[c].isna().sum()) for c in checked}
    bad = {c: n for c, n in counts.items() if n}
    if bad:
        _fail(2, 'null values in fields that must be complete',
              '  ' + ', '.join(f'{c}: {n}' for c, n in bad.items()))


def _assert_unique_key(table):
    """3. No match key appears twice, with the date component included."""
    key = ['season', 'round', 'home_team', 'away_team', 'date']
    dup = table[table.duplicated(subset=key, keep=False)]
    if len(dup):
        _fail(3, f'{len(dup)} row(s) share a match key',
              dup.sort_values(key).head(10)[key].to_string(index=False))


def _assert_distinct_teams(table):
    """4. No match has the same club on both sides."""
    same = table[table.home_team == table.away_team]
    if len(same):
        _fail(4, f'{len(same)} match(es) have the same team on both sides',
              same.head(10)[['season', 'round', 'date', 'home_team']]
              .to_string(index=False))


def _assert_final_scores(table):
    """5. The cumulative-scores guard, extra-time aware.

    Without extra time the full-time cumulative equals the final score. With it
    the final score is the extra-time cumulative, and comparing against HQ4P
    would fail on all three such matches rather than catching a real defect.
    """
    reg = table[~table.went_to_extra_time]
    bad_reg = reg[(reg.HQ4P != reg.home_score) | (reg.AQ4P != reg.away_score)]
    et = table[table.went_to_extra_time]
    bad_et = et[(et.HQETP != et.home_score) | (et.AQETP != et.away_score)]
    if len(bad_reg) or len(bad_et):
        cols = ['season', 'round', 'date', 'home_team', 'away_team',
                'HQ4P', 'HQETP', 'home_score', 'AQ4P', 'AQETP', 'away_score']
        _fail(5, f'{len(bad_reg)} regulation and {len(bad_et)} extra-time '
                 f'match(es) where the cumulative total is not the final score',
              pd.concat([bad_reg, bad_et]).head(10)[cols].to_string(index=False))


def _assert_points_identity(rows, path):
    """6. P equals G*6 + B on every quarter and both teams.

    Runs on player rows before projection, so it covers every row read rather
    than one row per match. The identity is pre-computed in the source; it is
    asserted here rather than relied upon.
    """
    for p, g, b in zip(POINTS_COLS, GOAL_COLS, BEHIND_COLS):
        bad = rows[rows[p] != rows[g] * 6 + rows[b]]
        if len(bad):
            _fail(6, f'{path}: {len(bad)} row(s) where {p} != {g}*6 + {b}',
                  bad.head(5)[['Season', 'Round', p, g, b]].to_string(index=False))


def _assert_clubs_handled(table):
    """7. Every club value survives canonical_club() as a known club.

    canonical_club passes unknown strings through unchanged, so an unhandled
    club is invisible unless it is checked against the set of clubs the fold is
    supposed to produce. University is the known case, out of range at a 1965
    floor.
    """
    known = {
        'Adelaide', 'Brisbane Lions', 'Carlton', 'Collingwood', 'Essendon',
        'Fitzroy', 'Fremantle', 'Geelong', 'Gold Coast',
        'Greater Western Sydney', 'Hawthorn', 'Melbourne', 'North Melbourne',
        'Port Adelaide', 'Richmond', 'St Kilda', 'Sydney', 'West Coast',
        'Western Bulldogs',
    }
    seen = set(table.home_team) | set(table.away_team)
    unhandled = sorted(seen - known)
    if unhandled:
        _fail(7, f'{len(unhandled)} club value(s) not handled by canonical_club()',
              '  ' + ', '.join(unhandled))


def _assert_dtypes(frames):
    """8. The two hazardous columns arrive as declared, after an explicit cast."""
    for path, df in frames.items():
        for col, dtype in DECLARED_DTYPES.items():
            got = str(df[col].dtype)
            if got != dtype:
                _fail(8, f'{path}: {col} is {got} after an explicit cast to '
                         f'{dtype}')


def _assert_url_continuity(frames):
    """9. url means the same thing in every source file.

    Tested on players present in both the 1965-2006 archive and 2007-2025: if
    the strings differ, a with/without cut cannot span the join and would
    under-count without saying so. Spec section 13 item 3 listed this as
    unresolved; the assertion is what resolves it on every run.
    """
    paths = [p for p, _, _ in SOURCES]
    older, newer = frames[paths[0]], frames[paths[1]]
    a = older[['ID', 'url']].dropna().drop_duplicates('ID')
    b = newer[['ID', 'url']].dropna().drop_duplicates('ID')
    shared = a.merge(b, on='ID', suffixes=('_old', '_new'))
    if shared.empty:
        _fail(9, 'no player appears in both the archive and 2007-2025',
              '  An empty overlap is a failed check, not a passed one: it means '
              'the ID spaces do not meet and the join cannot be verified.')
    bad = shared[shared.url_old != shared.url_new]
    if len(bad):
        _fail(9, f'{len(bad)} of {len(shared)} shared players have a different '
                 f'url string across files',
              bad.head(10).to_string(index=False))


def _assert_extra_time_count(table):
    """10. Exactly three matches in the frozen range went to extra time."""
    frozen = table[(table.season >= BASELINE_LO) & (table.season <= BASELINE_HI)]
    et = frozen[frozen.went_to_extra_time]
    if len(et) != EXPECTED_EXTRA_TIME:
        cols = ['season', 'round', 'date', 'home_team', 'away_team',
                'HQ4P', 'HQETP', 'AQ4P', 'AQETP']
        _fail(10, f'{len(et)} extra-time match(es) in {BASELINE_LO}-'
                  f'{BASELINE_HI}, expected {EXPECTED_EXTRA_TIME}',
              et[cols].to_string(index=False))


def _assert_no_loss_at_concat(table, contributions):
    """Every source's match count survives concatenation.

    Not one of the spec's ten. It rides here because assertion 1 only covers
    the frozen range, so a 2026 source silently contributing nothing would pass
    every other check in this file.
    """
    for path, expected in contributions.items():
        got = int((table.source_file == path).sum())
        if got != expected:
            _fail(1, f'{path} projected {expected} matches but contributed '
                     f'{got} to the table')


# ---------------------------------------------------------------- public

def load_match_table():
    """Return the derived match table, one row per match, or raise.

    Ten assertions from team_h2h_spec.md section 12 run before the frame is
    returned, plus a concatenation check. Each raises MatchTableError naming
    the failure. No total row count is hardcoded anywhere: the expectation is
    the committed per-season baseline, recomputed from it on every call.

    Columns: season, round, is_final, went_to_extra_time, venue, date,
    day_of_week, local_start_time, home_team, away_team, home_score,
    away_score, HQ1P-HQ4P, AQ1P-AQ4P, HQETP, AQETP, source_file.

    `round` holds an int for home and away rounds and the finals code string
    for finals, which is what the source holds and what the match key needs.
    Read `is_final` rather than parsing it. Finals codes are era-dependent and
    are not a grouping variable; see spec section 2.
    """
    frames, projected, contributions = {}, [], {}
    for path, _lo, _hi in SOURCES:
        rows = _read_source(path)
        _assert_points_identity(rows, path)
        frames[path] = rows
        m = _project(rows, path)
        contributions[path] = len(m)
        projected.append(m)

    _assert_dtypes(frames)
    _assert_url_continuity(frames)

    table = pd.concat(projected, ignore_index=True)

    _assert_no_loss_at_concat(table, contributions)
    _assert_no_nulls(table)
    _assert_unique_key(table)
    _assert_distinct_teams(table)
    _assert_final_scores(table)
    _assert_clubs_handled(table)
    _assert_extra_time_count(table)
    _assert_baseline(table)

    return table.sort_values(['season', 'date', 'home_team']).reset_index(drop=True)


def write_baseline(path=BASELINE):
    """Write the frozen per-season match counts. Run once, by hand, then commit.

    Deliberately not wired to a CLI and never called by load_match_table().
    Regenerating this file is how the guard in assertion 1 gets disarmed, so it
    is a decision someone takes on purpose rather than a side effect of a run.
    """
    frames = []
    for src, _lo, _hi in SOURCES:
        frames.append(_project(_read_source(src), src))
    table = pd.concat(frames, ignore_index=True)
    frozen = table[(table.season >= BASELINE_LO) & (table.season <= BASELINE_HI)]
    out = (frozen.groupby('season')['is_final']
           .agg(ha_matches=lambda s: int((~s).sum()),
                finals_matches='sum').reset_index())
    out['finals_matches'] = out['finals_matches'].astype(int)
    out.to_csv(path, index=False)
    return out
