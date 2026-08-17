"""The pre-1965 match table. One row per match, 1897-1964. A SEPARATE TIER.

    from team_match_table_pre1965 import load_pre1965_table
    m = load_pre1965_table()

This is not an extension of `team_match_table.load_match_table()` and must
never be concatenated with it blindly. It is a second tier with a **narrower
column set**, and the columns it lacks are exactly the ones several sections of
the preview run on.

Why the tiers differ at all
---------------------------
The 1965+ tier derives its match table from player-level fitzRoy files, so its
floor is the floor of AFLTables player statistics: 1965, the first season
disposals were recorded. Nothing about the *results* stops there. This tier
comes from `fetch_results_afltables()`, a match-level feed reaching back to
1897, which carries no player statistics and therefore also carries:

  - no `Local.start.time`   -> no timeslot bin, so no section 4 and no section 6
  - no quarter scores       -> no section 8, and only the match streak basis
  - no player rows          -> no with/without cut

Those four absences are structural in the source. This module does NOT
null-fill the missing columns. A column that does not exist is absent from the
frame, so a consumer that reaches for `local_start_time` on this tier fails
loudly at the point of the mistake rather than grouping every pre-1965 match
into an "Unknown" bin and printing it next to real ones.

`AVAILABLE` and `UNAVAILABLE` below are the machine-readable form of that
split, and are what the writer prints instead of a blank section.

Extra time
----------
`went_to_extra_time` is False on every row, and that is a fact about the era
rather than a missing field. Extra time did not enter VFL finals until 1991: a
drawn final was replayed the following week and the replay appears here as its
own match. Assertion 7 checks that, so the False is verified rather than
assumed. The consequence for the reader is that a drawn pre-1965 final counts
as a draw AND its replay counts as a separate result, which is how the record
books treat them.

Clubs
-----
University (1908-1914) appears here and is deliberately NOT added to
`CLUB_ALIASES`. It maps to itself, which is already what `canonical_club()`
does with an unrecognised string, and it is a terminated entity that folds into
nothing, exactly like Fitzroy. What it needs is to be in the known-club set so
the guard cannot pass it through unnoticed, which is `KNOWN_CLUBS` here.

Note the feed already emits South Melbourne as "Sydney", where the player-level
feed emits "South Melbourne" and relies on `canonical_club()` to fold it.
`canonical_club()` runs on both sides here regardless, so the two tiers land on
the same string either way.
"""

import os

import pandas as pd

from club_aliases import canonical_club

SOURCE = 'data_history/match_results_1897_1965.csv'
BASELINE = 'data_history/match_counts_baseline_pre1965.csv'

# The tier is 1897-1964. The source file also holds 1965 on purpose: it is the
# overlap season, and it exists so `validate_join()` can check this feed against
# the 1965+ tier on a season both hold. It is dropped from the tier itself, so
# no match is ever counted twice.
TIER_LO, TIER_HI = 1897, 1964
OVERLAP_SEASON = 1965

# Finals in this range are SF/PF/GF only. QF and EF are later formats and their
# absence is a fact about the era, not a filter.
FINALS_CODES = frozenset({'QF', 'EF', 'SF', 'PF', 'GF'})

SOURCE_COLS = ('Season', 'Round', 'Round.Type', 'Round.Number', 'Date', 'Venue',
               'Home.Team', 'Home.Goals', 'Home.Behinds', 'Home.Points',
               'Away.Team', 'Away.Goals', 'Away.Behinds', 'Away.Points',
               'Margin')

OUTPUT_COLS = ['season', 'round', 'is_final', 'went_to_extra_time', 'venue',
               'date', 'day_of_week', 'home_team', 'away_team', 'home_score',
               'away_score', 'source_file']

# What a consumer may and may not ask of this tier. The writer prints the
# second list rather than leaving a section blank, because a blank section reads
# as "no matches" and the truth is "the field was never recorded".
AVAILABLE = ('series overview', 'scope split', 'venue', 'day of week',
             'same calendar date', 'streaks on the match basis')
UNAVAILABLE = {
    'timeslot': 'no Local.start.time in a match-level feed',
    'venue x timeslot': 'no Local.start.time in a match-level feed',
    'quarter by quarter': 'no quarter scores in a match-level feed',
    'streaks on the Q1-Q4 bases': 'no quarter scores in a match-level feed',
    'with and without': 'no player rows in a match-level feed',
}

KNOWN_CLUBS = {
    'Carlton', 'Collingwood', 'Essendon', 'Fitzroy', 'Geelong', 'Hawthorn',
    'Melbourne', 'North Melbourne', 'Richmond', 'St Kilda', 'Sydney',
    'University', 'Western Bulldogs',
}


class PreTierError(AssertionError):
    """A tier build assertion failed. The message names which one and why."""


def _fail(number, what, detail=''):
    raise PreTierError(
        f'team_match_table_pre1965 assertion {number} FAILED: {what}'
        + (f'\n{detail}' if detail else '')
    )


# ---------------------------------------------------------------- loading

def _read_source():
    if not os.path.exists(SOURCE):
        _fail(0, f'source file not found: {SOURCE}',
              '  Regenerate it with: Rscript scripts/fetch_results_pre1965.R')
    available = set(pd.read_csv(SOURCE, nrows=0).columns)
    missing = [c for c in SOURCE_COLS if c not in available]
    if missing:
        _fail(0, f'{SOURCE} is missing expected columns',
              f'  missing: {", ".join(missing)}')
    return pd.read_csv(SOURCE, usecols=list(SOURCE_COLS), low_memory=False)


def _project(df):
    """Shape the raw feed into the tier's output columns."""
    m = df.copy()
    m['is_final'] = m['Round.Type'].str.strip() != 'Regular'

    label = m['Round'].astype(str).str.strip().str.upper()
    bad = m[m['is_final'] & ~label.isin(FINALS_CODES)]
    if len(bad):
        _fail(0, 'a finals row carries an unrecognised round label',
              '  ' + ', '.join(sorted(bad['Round'].astype(str).unique())))
    # Same convention as the 1965+ tier: an int for a home-and-away round, the
    # code string for a final. Built element-wise for the same reason.
    m['round'] = [lab if fin else int(num)
                  for lab, num, fin in zip(label, m['Round.Number'], m['is_final'])]

    m['season'] = m['Season'].astype(int)
    m['venue'] = m['Venue']
    m['date'] = pd.to_datetime(m['Date'])
    m['day_of_week'] = m['date'].dt.day_name()
    # canonical_club on BOTH sides, as in the 1965+ tier. Footscray folds to
    # Western Bulldogs here; South Melbourne arrives already emitted as Sydney.
    m['home_team'] = m['Home.Team'].map(canonical_club)
    m['away_team'] = m['Away.Team'].map(canonical_club)
    m['home_score'] = m['Home.Points'].astype(int)
    m['away_score'] = m['Away.Points'].astype(int)
    # A fact about the era, not a missing field. Verified by assertion 7.
    m['went_to_extra_time'] = False
    m['source_file'] = SOURCE
    return m[OUTPUT_COLS]


# ------------------------------------------------------------- assertions

def _assert_no_nulls(table):
    """1. No null in any field this tier carries."""
    bad = {c: int(table[c].isna().sum()) for c in OUTPUT_COLS
           if int(table[c].isna().sum())}
    if bad:
        _fail(1, 'null values in fields that must be complete',
              '  ' + ', '.join(f'{c}: {n}' for c, n in bad.items()))


def _assert_unique_key(table):
    """2. No match key appears twice, date included.

    Date carries more weight here than in the 1965+ tier. Drawn finals were
    replayed rather than decided in extra time, and a replay shares season,
    round label and both clubs with the drawn match. Without Date they collapse.
    """
    key = ['season', 'round', 'home_team', 'away_team', 'date']
    dup = table[table.duplicated(subset=key, keep=False)]
    if len(dup):
        _fail(2, f'{len(dup)} row(s) share a match key',
              dup.sort_values(key).head(10)[key].to_string(index=False))


def _assert_distinct_teams(table):
    """3. No match has the same club on both sides."""
    same = table[table.home_team == table.away_team]
    if len(same):
        _fail(3, f'{len(same)} match(es) have the same team on both sides',
              same.head(10)[['season', 'round', 'date', 'home_team']]
              .to_string(index=False))


def _assert_points_identity(rows):
    """4. Points equals Goals*6 + Behinds on both sides of every match."""
    for side in ('Home', 'Away'):
        bad = rows[rows[f'{side}.Points']
                   != rows[f'{side}.Goals'] * 6 + rows[f'{side}.Behinds']]
        if len(bad):
            _fail(4, f'{len(bad)} row(s) where {side}.Points is not '
                     f'{side}.Goals*6 + {side}.Behinds',
                  bad.head(5)[['Season', 'Round', f'{side}.Points',
                               f'{side}.Goals', f'{side}.Behinds']]
                  .to_string(index=False))


def _assert_margin_identity(rows):
    """5. Margin is home minus away, so the scores and the margin agree.

    A free integrity check the 1965+ tier has no equivalent of, because that
    feed carries no margin column. If the feed ever reorients Margin to the
    winner rather than the home side, this catches it.
    """
    bad = rows[rows['Margin'] != rows['Home.Points'] - rows['Away.Points']]
    if len(bad):
        _fail(5, f'{len(bad)} row(s) where Margin is not Home.Points minus '
                 f'Away.Points',
              bad.head(5)[['Season', 'Round', 'Home.Points', 'Away.Points',
                           'Margin']].to_string(index=False))


def _assert_clubs_handled(table):
    """6. Every club survives canonical_club() as a known club.

    canonical_club() passes an unrecognised string through unchanged, so an
    unhandled club is invisible without this check. University is expected here
    and is in KNOWN_CLUBS; anything else is a new fold to decide on.
    """
    seen = set(table.home_team) | set(table.away_team)
    unhandled = sorted(seen - KNOWN_CLUBS)
    if unhandled:
        _fail(6, f'{len(unhandled)} club value(s) not handled',
              '  ' + ', '.join(unhandled))


def _assert_draws_replayed(table):
    """7. Every drawn final is followed by a replay between the same clubs.

    This is what makes `went_to_extra_time = False` a verified statement rather
    than an assumption. Extra time did not enter VFL finals until 1991; before
    that a drawn final was replayed. If a drawn final here has no replay, the
    era assumption is wrong somewhere and the flag cannot stand.
    """
    drawn = table[table.is_final & (table.home_score == table.away_score)]
    orphans = []
    for _, r in drawn.iterrows():
        pair = {r.home_team, r.away_team}
        later = table[(table.season == r.season) & (table.date > r.date)
                      & table.is_final]
        if not any({x.home_team, x.away_team} == pair
                   for _, x in later.iterrows()):
            orphans.append(f'{r.season} {r["round"]} {r.home_team} v '
                           f'{r.away_team} ({r.date.date()})')
    if orphans:
        _fail(7, f'{len(orphans)} drawn final(s) with no replay, so '
                 f'went_to_extra_time=False is not safe',
              '  ' + '; '.join(orphans))


def _assert_tier_range(table):
    """8. The tier holds 1897-1964 only, so it cannot double-count with 1965+."""
    lo, hi = int(table.season.min()), int(table.season.max())
    if lo != TIER_LO or hi != TIER_HI:
        _fail(8, f'tier covers {lo}-{hi}, expected {TIER_LO}-{TIER_HI}',
              '  A tier reaching 1965 or beyond would double-count every match '
              'the 1965+ table already holds.')


def _assert_baseline(table):
    """9. Per-season counts match the committed baseline.

    Stronger here than in the 1965+ tier: this range is closed and can never
    legitimately gain a match, so ANY movement is a defect rather than a
    season in progress.
    """
    if not os.path.exists(BASELINE):
        _fail(9, f'baseline file missing: {BASELINE}',
              '  Generate it once with write_baseline() and commit it.')
    base = pd.read_csv(BASELINE)
    got = (table.groupby('season')['is_final']
           .agg(ha_matches=lambda s: int((~s).sum()),
                finals_matches='sum').reset_index())
    got['finals_matches'] = got['finals_matches'].astype(int)
    merged = base.merge(got, on='season', how='outer',
                        suffixes=('_baseline', '_now'), indicator=True)
    bad = merged[(merged._merge != 'both')
                 | (merged.ha_matches_baseline != merged.ha_matches_now)
                 | (merged.finals_matches_baseline != merged.finals_matches_now)]
    if len(bad):
        _fail(9, f'{len(bad)} season(s) disagree with {BASELINE}',
              f'  first {min(10, len(bad))}:\n'
              f'{bad.head(10).to_string(index=False)}')


# ---------------------------------------------------------------- public

def load_pre1965_table():
    """Return the pre-1965 match table, one row per match, or raise.

    Columns: season, round, is_final, went_to_extra_time, venue, date,
    day_of_week, home_team, away_team, home_score, away_score, source_file.

    Deliberately NARROWER than `load_match_table()`. There is no
    local_start_time and there are no quarter columns, because the source has
    neither. See `UNAVAILABLE` for what that costs and why.
    """
    raw = _read_source()
    _assert_points_identity(raw)
    _assert_margin_identity(raw)

    table = _project(raw)
    table = table[table.season <= TIER_HI].reset_index(drop=True)

    _assert_no_nulls(table)
    _assert_unique_key(table)
    _assert_distinct_teams(table)
    _assert_clubs_handled(table)
    _assert_draws_replayed(table)
    _assert_tier_range(table)
    _assert_baseline(table)

    return table.sort_values(['season', 'date', 'home_team']).reset_index(drop=True)


def validate_join(main_table=None):
    """Check the two feeds agree on 1965, the one season both hold.

    Returns a one-row DataFrame of the comparison. Raises if they disagree on
    the match count or on any result, because a tier join is only as good as
    the evidence that the two sources describe the same competition. Without an
    overlap season this would be unverifiable, which is why the fetch reaches
    1965 and the tier stops at 1964.

    `main_table` accepts a pre-loaded 1965+ table so a caller does not pay the
    load twice.
    """
    from team_match_table import load_match_table

    theirs = (load_match_table() if main_table is None else main_table)
    theirs = theirs[theirs.season == OVERLAP_SEASON]

    mine = _project(_read_source())
    mine = mine[mine.season == OVERLAP_SEASON]

    if len(mine) != len(theirs):
        _fail(10, f'{OVERLAP_SEASON} has {len(mine)} matches in this feed and '
                  f'{len(theirs)} in the 1965+ table',
              '  The two feeds do not describe the same season, so the tier '
              'join is not safe.')

    key = ['season', 'round', 'home_team', 'away_team', 'date']
    merged = mine.merge(theirs, on=key, how='outer', suffixes=('_pre', '_main'),
                        indicator=True)
    unmatched = merged[merged._merge != 'both']
    if len(unmatched):
        _fail(10, f'{len(unmatched)} {OVERLAP_SEASON} match(es) do not join '
                  f'across the two feeds',
              unmatched.head(10)[key + ['_merge']].to_string(index=False))

    disagree = merged[(merged.home_score_pre != merged.home_score_main)
                      | (merged.away_score_pre != merged.away_score_main)]
    if len(disagree):
        _fail(10, f'{len(disagree)} {OVERLAP_SEASON} match(es) disagree on the '
                  f'score across the two feeds',
              disagree.head(10)[key + ['home_score_pre', 'home_score_main',
                                       'away_score_pre', 'away_score_main']]
              .to_string(index=False))

    venue_same = int((merged.venue_pre == merged.venue_main).sum())
    return pd.DataFrame([{
        'overlap_season': OVERLAP_SEASON,
        'matches_both_feeds': len(merged),
        'scores_agree': len(merged) - len(disagree),
        'venue_strings_agree': venue_same,
        'verdict': 'joined',
    }])


def write_baseline(path=BASELINE):
    """Write the frozen per-season match counts. Run once, by hand, then commit.

    Not wired to a CLI and never called by load_pre1965_table(), for the same
    reason as its 1965+ counterpart: regenerating this file disarms assertion 9,
    so it is a decision taken on purpose rather than a side effect of a run.
    """
    table = _project(_read_source())
    table = table[table.season <= TIER_HI]
    out = (table.groupby('season')['is_final']
           .agg(ha_matches=lambda s: int((~s).sum()),
                finals_matches='sum').reset_index())
    out['finals_matches'] = out['finals_matches'].astype(int)
    out.to_csv(path, index=False)
    return out
