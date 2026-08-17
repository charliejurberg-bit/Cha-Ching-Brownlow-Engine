"""The extended tier: pre-1965 records, and the all-time figures they unlock.

    from team_h2h_pre1965 import extended_series
    out = extended_series('Essendon', 'Sydney')

Opt-in. `team_h2h.py` runs this only under `--extended` and the 1965+ preview
is unchanged whether it runs or not.

Two tiers, one series
---------------------
The 1965+ tier derives matches from player-level files and stops at 1965
because AFLTables player statistics do. This module adds the 1897-1964 tier
from a match-level feed and computes:

  - the pre-1965 record on its own, so the added history is visible as its own
    population rather than folded invisibly into a bigger number
  - the ALL-TIME record across both tiers, for the sections both can compute

The second is the point. A combined series overview and a combined match-basis
streak are strictly better than either tier alone, because the meeting sequence
is contiguous across the join: the tiers meet at 1964/1965 with no gap and no
overlap, and `validate_join()` checks the feeds agree on 1965 before any of
this is trusted.

What does NOT extend, and why it must be said rather than left blank
--------------------------------------------------------------------
Timeslot, venue x timeslot, quarter-by-quarter, the Q1-Q4 streak bases and the
with/without cut cannot cross the join, because the pre-1965 feed has no start
time, no quarter scores and no player rows. Those sections keep their 1965
floor. A blank section reads as "no matches"; the truth is "the field was never
recorded", so `UNAVAILABLE` is printed instead.

**The mixed-floor trap this exists to prevent.** With two floors in one file,
the failure mode is a reader taking an all-time figure from section 12 and a
1965-floored figure from section 8 and writing them into one sentence. Every
frame this module returns therefore carries a `floor` column naming its own
floor, and the writer prints the floor on every extended table.
"""

import pandas as pd

from team_h2h_records import (H2HError, _by_day, _by_venue, _orient,
                              _same_calendar_date, _scope_split,
                              _series_overview)
from team_h2h_streaks import NON_LOSS, WIN, _streaks_for
from team_match_table import load_match_table
from team_match_table_pre1965 import (TIER_HI, TIER_LO, UNAVAILABLE,
                                      load_pre1965_table)

# 1897 is the VFL's first season, so for a club in the competition since 1897
# this tier is complete VFL/AFL history and "since 1897" is not a hedge.
EXTENDED_FLOOR = TIER_LO

EXTENDED_CAVEAT = (
    f'Extended floor {EXTENDED_FLOOR}, the VFL\'s first season. For two clubs '
    f'both in the competition from {EXTENDED_FLOOR} this is complete VFL/AFL '
    f'history, so "since {EXTENDED_FLOOR}" and "in VFL/AFL history" are both '
    f'true of it. It is still NOT club history: clubs played in the VFA before '
    f'{EXTENDED_FLOOR} and no tier here holds those meetings. Where a club '
    f'entered later the series simply begins when it entered, which the first '
    f'meeting date shows.'
)

MIXED_FLOOR_WARNING = (
    'This file now carries TWO floors. Sections 1 to 11 are floored at 1965; '
    'section 12 is floored at 1897 for the cuts that can cross the join. Never '
    'combine a figure from one with a figure from the other in a single '
    'sentence. Every table below names its own floor.'
)

# The columns both tiers hold, after orientation. The combined frame is built
# by selecting these explicitly rather than by concatenating and letting pandas
# fill: a NaN quarter column on 6,558 pre-1965 rows is exactly the silent null
# the loaders refuse to create.
SHARED_COLS = ['season', 'round', 'is_final', 'went_to_extra_time', 'venue',
               'date', 'day_of_week', 'home_team', 'away_team', 'home_score',
               'away_score', 'source_file', 'subject_is_home', 'subject_score',
               'opp_score', 'result', 'day_month']


def _floored(df, floor):
    """Stamp a frame with the floor it was computed under.

    On every extended frame, not just the ranked ones. Two floors in one file
    is the failure mode this module is most exposed to, and a floor that
    travels as a column cannot be lost when a table is copied out of context.
    """
    if df is None or df.empty:
        return df
    d = df.copy()
    d['floor'] = floor
    return d


def _orient_or_none(table, subject, opponent):
    """Orient a tier to the subject, or return None when it holds no meetings.

    `_orient` raises on an empty series, which is right for the main tool: an
    empty 1965+ series is a failed lookup. Here it is an ordinary outcome. Two
    clubs that never coexisted in the competition before 1965 have no pre-1965
    record, and that is a fact to report rather than an error to raise.
    """
    try:
        return _orient(table, subject, opponent)
    except H2HError:
        return None


def extended_series(subject, opponent, scope='all', fixture_date=None,
                    pre=None, main=None):
    """Return the pre-1965 tier's records and the all-time combined figures.

    `scope` filters the record sections of both tiers, exactly as it does in
    `h2h_records`. It does NOT filter the streaks, matching the inversion in
    `h2h_streaks`: a final between two home-and-away results breaks continuity,
    and excluding it manufactures a streak that never happened.

    `pre` and `main` accept pre-loaded tables so a caller already holding them
    does not pay either load twice.

    Returns a dict of DataFrames plus `meta`. Every frame carries a `floor`
    column. `pre_*` frames are the 1897-1964 population alone; `all_*` frames
    are both tiers together. Where the pre-1965 tier holds no meetings for the
    pairing, the `pre_*` frames are None and `meta.pre_meetings` is 0.
    """
    pre_table = load_pre1965_table() if pre is None else pre
    main_table = load_match_table() if main is None else main

    pre_m = _orient_or_none(pre_table, subject, opponent)
    main_m = _orient(main_table, subject, opponent)  # raises, as it should

    if pre_m is None:
        combined = main_m[SHARED_COLS].copy()
    else:
        combined = pd.concat([pre_m[SHARED_COLS], main_m[SHARED_COLS]],
                             ignore_index=True)
    combined = combined.sort_values('date').reset_index(drop=True)

    # The join is contiguous by construction: the tier stops at 1964 and the
    # main table starts at 1965. Asserted rather than assumed, because a
    # duplicate here would inflate every all-time figure in the section.
    key = ['season', 'round', 'home_team', 'away_team', 'date']
    dup = combined[combined.duplicated(subset=key, keep=False)]
    if len(dup):
        raise H2HError(
            f'{len(dup)} match(es) appear in both tiers for {subject} v '
            f'{opponent}. The tiers must not overlap; every all-time figure '
            f'would be inflated.\n'
            + dup.sort_values(key).head(10)[key].to_string(index=False)
        )

    def _scoped(m):
        if m is None:
            return None
        d = m[~m.is_final] if scope == 'ha' else m[m.is_final] if scope == 'finals' else m
        return d.reset_index(drop=True) if len(d) else None

    pre_s, all_s = _scoped(pre_m), _scoped(combined)

    def _section(fn, m, floor, *args):
        return None if m is None else _floored(fn(m, *args), floor)

    pre_floor = f'{TIER_LO}-{TIER_HI}'
    all_floor = f'{EXTENDED_FLOOR}+'

    # Streaks run on the unscoped combined population, per the h2h_streaks
    # inversion. Match basis only: Q1-Q4 cannot cross the join.
    seq = combined.result
    streaks = {}
    for label, definition in (('win', WIN), ('non_loss', NON_LOSS)):
        live, longest = _streaks_for(combined, seq, definition, 'match', scope)
        f = pd.DataFrame([live, longest])
        # `_streaks_for` only attaches `ties` to a longest row that has a
        # qualifying run, so the column is absent entirely on a pairing with
        # none. Widening the archive is what makes ties likely, so the writer
        # always prints the column and it has to always exist.
        if 'ties' not in f.columns:
            f['ties'] = pd.NA
        streaks[label] = _floored(f, all_floor)

    meta = pd.DataFrame([{
        'subject': subject,
        'opponent': opponent,
        'scope': scope,
        'pre_meetings': 0 if pre_m is None else len(pre_m),
        'main_meetings': len(main_m),
        'all_meetings': len(combined),
        'reconciles': (0 if pre_m is None else len(pre_m)) + len(main_m) == len(combined),
        'first_meeting_all': combined.date.min().date().isoformat(),
        'first_meeting_main': main_m.date.min().date().isoformat(),
        'last_meeting_all': combined.date.max().date().isoformat(),
        'seasons_added': 0 if pre_m is None else int(pre_m.season.nunique()),
        # Carried so a "no pre-1965 meetings" result can be evidenced against
        # the size of the tier that was searched, rather than asserted. Read
        # from the loaded table, never hardcoded: the spec's rule for the 1965+
        # counts applies here too.
        'tier_matches': len(pre_table),
        'tier_range': f'{TIER_LO} to {TIER_HI}',
        'extended_caveat': EXTENDED_CAVEAT,
        'mixed_floor_warning': MIXED_FLOOR_WARNING,
        'unavailable': '; '.join(f'{k} ({v})' for k, v in UNAVAILABLE.items()),
        'source_file': '; '.join(sorted(set(combined.source_file))),
    }])
    if not meta.reconciles.iloc[0]:
        raise H2HError(
            f'pre {meta.pre_meetings.iloc[0]} plus main {len(main_m)} does not '
            f'equal combined {len(combined)}'
        )

    return {
        'pre_meetings': pre_m,
        'all_meetings': combined,
        'pre_overview': _section(_series_overview, pre_s, pre_floor),
        'all_overview': _section(_series_overview, all_s, all_floor),
        'pre_scope_split': _section(_scope_split, pre_s, pre_floor),
        'all_scope_split': _section(_scope_split, all_s, all_floor),
        'pre_by_venue': _section(_by_venue, pre_s, pre_floor),
        'all_by_venue': _section(_by_venue, all_s, all_floor),
        'all_by_day': _section(_by_day, all_s, all_floor),
        'all_same_calendar_date': _section(_same_calendar_date, all_s,
                                           all_floor, fixture_date),
        'all_win_streaks': streaks['win'],
        'all_non_loss_streaks': streaks['non_loss'],
        'meta': meta,
    }
