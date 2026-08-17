"""Team-level head-to-head fixture preview. CLI and facts-file writer.

    python team_h2h.py --teams "Richmond" "St Kilda"
    python team_h2h.py --teams "Richmond" "St Kilda" --date 2026-08-15
    python team_h2h.py --teams "Richmond" "St Kilda" --scope ha --without "Tim Taranto"
    python team_h2h.py --teams "Richmond" "St Kilda" --extended

The first team named is the subject. Every record is oriented to it, never to
the home side.

`--extended` adds section 12, the 1897-1964 tier, for the cuts that can cross
the join. Timeslot, quarter records, the Q1-Q4 streak bases and with/without
cannot cross it and keep their 1965 floor, and section 12 says so rather than
printing them blank. Without the flag sections 1 to 11 are unchanged from
before the tier existed, and the only addition is a section 12 heading carrying
the same "Not run, opt-in via" stub sections 10 and 11 already print. See
team_h2h_spec.md section 14.

Output is a **markdown facts file** to drafts/, which is gitignored. No tweet
copy and no draft: draft_gate.py has no team-mode coverage, so nothing here is
post-ready and nothing here claims to be. Copy is written separately once the
gate covers team mode.

Three things the writer is built to prevent, each from the spec:

  - **A cut read as a finding.** A 106-meeting series always contains a
    striking pattern somewhere in the cut space. Every conditional section
    prints the number of cuts tested, so a pattern reads as one-in-N rather
    than as a discovery.
  - **A truncated archive read as club history.** The floor is 1965 and it is a
    hard truncation of the data, not the start of the fixture. Richmond and St
    Kilda met from 1908. The caveat is stated prominently once and repeated on
    every ranking.
  - **An empty arm read as a contrast.** If a with/without arm has no matches
    there is no comparator, so the numbers print and the framing is withheld
    with the reason given.
  - **Two floors read as one.** Under `--extended` the file carries a 1965
    floor for sections 1 to 11 and an 1897 floor for section 12. Every extended
    table names its own floor, and the two cells-tested counts are reported
    separately, so a figure cannot be lifted from one and paired with a figure
    from the other.
"""

import argparse
import os
import sys

import pandas as pd

from team_h2h_crossopp import LIVE_STREAK_TRIGGER, cross_opponent_streaks
from team_h2h_pre1965 import (EXTENDED_CAVEAT, EXTENDED_FLOOR,
                              MIXED_FLOOR_WARNING, extended_series)
from team_h2h_records import H2HError, h2h_records
from team_h2h_streaks import FLOOR_CAVEAT, FLOOR_SEASON, h2h_streaks
from team_h2h_without import h2h_without
from team_match_table import load_match_table
from team_match_table_pre1965 import UNAVAILABLE

OUT_DIR = 'drafts'

# Section 6 sections 3 to 8 are the conditional cuts. The count of cells across
# them is what makes a striking cell readable as one of N rather than as a
# finding, so it is computed from the frames rather than declared.
CUT_SECTIONS = ('by_venue', 'by_timeslot', 'by_day', 'by_venue_timeslot',
                'same_calendar_date', 'by_quarter')

# Section 12's own cuts. Counted and printed SEPARATELY from CUT_SECTIONS
# rather than added to it: they are the same pre-declared cuts run on a
# different population, so folding them into one number would understate how
# many cells an extended run has actually looked at while implying the 1965+
# sections got bigger.
EXTENDED_CUT_SECTIONS = ('pre_by_venue', 'all_by_venue', 'all_by_day',
                         'all_same_calendar_date')


def _slug(text):
    return ''.join(c.lower() if c.isalnum() else '' for c in text)


# Provenance is identical on every table in a run, so it is stated once in the
# header. The extra-time booleans are dropped as columns and re-expressed as a
# note under the tables that need one: a False in every row of every table is
# nine columns of noise, and the flag matters only when it is True.
DROP_ALWAYS = ('source_file', 'includes_extra_time', 'extra_time_n')

# Seasons arrive as float64 wherever a suppressed row put a NaN in the column,
# which prints 1972.0. Nullable Int64 keeps the blank and drops the decimal.
SEASON_COLS = ('season_first', 'season_last', 'start_season', 'end_season',
               'first_season', 'last_season', 'season')

# Same defect, different column. `ties` is attached only to a longest row, so
# the live row beside it is NaN and promotes the whole column to float, which
# prints a tie count of 1 as "1.0".
COUNT_COLS = ('ties',)


def _ints(df):
    """Cast season and count columns to nullable Int64.

    So a year is not printed as 1972.0 and a tie count is not printed as 1.0.
    """
    d = df.copy()
    for c in SEASON_COLS + COUNT_COLS:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors='coerce').astype('Int64')
    return d


def _table(df, cols=None):
    """A markdown table, or a stated absence. Never a silent blank."""
    if df is None or df.empty:
        return '_No rows. An empty section is a failed lookup, not a zero._\n'
    d = _ints(df)
    d = d[cols] if cols else d.drop(columns=[c for c in DROP_ALWAYS if c in d.columns])
    head = '| ' + ' | '.join(str(c) for c in d.columns) + ' |'
    rule = '|' + '---|' * len(d.columns)
    body = '\n'.join(
        '| ' + ' | '.join('' if pd.isna(v) else str(v) for v in row) + ' |'
        for row in d.itertuples(index=False)
    )
    return f'{head}\n{rule}\n{body}\n'


def _sources(df):
    if df is None or df.empty or 'source_file' not in df.columns:
        return ''
    seen = sorted({s for s in df.source_file.dropna() for s in str(s).split('; ')})
    return ', '.join(f'`{s}`' for s in seen)


def _et_note(df, meetings):
    """Name the extra-time matches under a table whose population holds one.

    Fires only when the count is above zero, per spec section 3: the flag has
    to stay visible when true, and naming the match is what makes it checkable
    rather than a warning the reader cannot act on.
    """
    if df is None or df.empty or 'extra_time_n' not in df.columns:
        return ''
    n = int(df.extra_time_n.sum())
    if n == 0:
        return ''
    et = meetings[meetings.went_to_extra_time]
    named = '; '.join(
        f'{int(r.season)} {r["round"]} v {r.away_team if r.subject_is_home else r.home_team} '
        f'({r.date.date().isoformat()})'
        for _, r in et.iterrows()
    )
    return (f'\n**Extra time in this population.** {len(et)} match(es) went to '
            f'extra time: {named}. The match result uses the extra-time score '
            f'and the quarter results are regulation, so a quarter record and a '
            f'match record are not the same quantity on those matches.\n')


def _et_note_once(frames, meetings):
    """The extra-time note for a whole section, emitted at most once.

    Sections 1 to 9 attach the note per table, which is right there: each of
    those tables is a differently scoped population and a reader may lift any
    one of them alone. Section 12's tables all draw from the SAME combined
    population, so the per-table form printed one identical paragraph five
    times in a file that already carried it. This collapses them, and fires if
    any frame in the section holds an extra-time match, so nothing is lost.
    """
    n = sum(int(f.extra_time_n.sum()) for f in frames
            if f is not None and not f.empty and 'extra_time_n' in f.columns)
    if not n:
        return ''
    # A one-row stand-in carrying only the flag. `_et_note` names the matches
    # from `meetings`, not from this frame, so the count here only has to be
    # non-zero to fire it.
    return _et_note(pd.DataFrame([{'extra_time_n': 1}]), meetings)


def _venue_home_split(meetings):
    """Venue crossed with whether the subject was at home.

    A display split of rows the venue table already covers, not a new cut, so
    it does not enter the cells-tested count. It exists because venue and home
    ground are collinear for most pairings: a venue table alone reads as a
    venue effect when part of it is a home effect.
    """
    rows = []
    for (venue, home), g in meetings.groupby(['venue', 'subject_is_home']):
        counts = g.result.value_counts()
        w, l, d = (int(counts.get(k, 0)) for k in 'WLD')
        rows.append({'venue': venue, 'subject': 'home' if home else 'away',
                     'wins': w, 'losses': l, 'draws': d, 'denominator': w + l + d,
                     'season_first': int(g.season.min()),
                     'season_last': int(g.season.max())})
    out = pd.DataFrame(rows)
    order = (out.groupby('venue').denominator.sum()
             .sort_values(ascending=False).index.tolist())
    out['_o'] = out.venue.map({v: i for i, v in enumerate(order)})
    return out.sort_values(['_o', 'subject']).drop(columns='_o').reset_index(drop=True)


def _streak_cols():
    return ['basis', 'kind', 'length', 'composition', 'phrase', 'start_season',
            'end_season', 'start_date', 'end_date', 'finals_in_window']


def _live_summary(f):
    """One line for the live rows when they all say the same thing.

    Ten identical suppressed rows, one per basis per definition, is a table the
    eye slides off. Where every live row carries the same reason it collapses
    to a sentence; where any basis has a live streak the rows are kept.
    """
    live = f[f.kind == 'live']
    if live.empty:
        return None
    if (live.length > 0).any():
        return None
    reasons = set(live.reason.dropna())
    return reasons.pop() if len(reasons) == 1 else None


def _extended_lines(subject, opponent, scope, fixture_date, table):
    """Section 12. The pre-1965 tier and the all-time figures it unlocks.

    Returns (lines, extended_cuts, meta). Every table here carries its own
    `floor` column, and the mixed-floor warning is printed before any of them:
    with two floors in one file, the live risk is a reader pairing an all-time
    number from here with a 1965-floored number from section 8.
    """
    ext = extended_series(subject, opponent, scope=scope,
                          fixture_date=fixture_date, main=table)
    em = ext['meta'].iloc[0]
    # Zero when the tier adds no meetings. The all-time frames still compute in
    # that case, but they are row-for-row the sections above, so counting their
    # cells would claim this section looked at cells it never printed.
    cuts = 0 if ext['pre_meetings'] is None else sum(
        len(ext[s]) for s in EXTENDED_CUT_SECTIONS if ext.get(s) is not None)

    L = [f'\n## 12. Extended tier, {EXTENDED_FLOOR} to {FLOOR_SEASON - 1}\n']
    a = L.append
    a(f'> **{MIXED_FLOOR_WARNING}**\n')
    a(f'> {EXTENDED_CAVEAT}\n')
    a(f'- Pre-{FLOOR_SEASON} meetings: **{int(em.pre_meetings)}** '
      f'across {int(em.seasons_added)} season(s)')
    a(f'- {FLOOR_SEASON}+ meetings: **{int(em.main_meetings)}** '
      f'(sections 1 to 11 above)')
    a(f'- All-time meetings: **{int(em.all_meetings)}**')
    a(f'- First meeting all-time: **{em.first_meeting_all}**, against '
      f'{em.first_meeting_main} in the {FLOOR_SEASON}+ tier alone')
    a(f'- Extended cells tested in this section: **{cuts}**. Counted '
      f'separately from the {FLOOR_SEASON}+ count above, because these are the '
      f'same cuts on a different population rather than extra cuts on the '
      f'same one.\n')
    a(f'**What does not extend, and why.** These sections keep their '
      f'{FLOOR_SEASON} floor. The fields are absent from a match-level feed, '
      f'so they are reported as unavailable rather than left blank: a blank '
      f'reads as "no matches" and the truth is "never recorded".\n')
    for k, v in UNAVAILABLE.items():
        a(f'- {k}: {v}')
    a('')

    if ext['pre_meetings'] is None:
        a(f'\n### 12.1 No pre-{FLOOR_SEASON} meetings\n')
        a(f'_{subject} and {opponent} did not meet before {FLOOR_SEASON}: at '
          f'least one of them was not in the competition. The extended tier '
          f'adds nothing to this pairing, so every all-time figure equals its '
          f'section 1 to 11 counterpart. This is a real zero, not a failed '
          f'lookup: the tier searched holds {int(em.tier_matches):,} matches '
          f'across {em.tier_range}._\n')
        return L, cuts, em

    # Extra time can only enter through the 1965+ half of a combined
    # population, since the pre-1965 tier has none. The note still has to fire
    # on the all-time tables: an all-time quarter claim does not exist here,
    # but the match record on those rows is the extra-time one and the reader
    # is owed the same flag section 1 gives them.
    all_m = ext['all_meetings']
    a(_et_note_once([ext['all_overview'], ext['all_scope_split'],
                     ext['all_by_venue'], ext['all_by_day'],
                     ext['all_win_streaks'], ext['all_non_loss_streaks']],
                    all_m))

    a(f'\n### 12.1 Series overview\n')
    a(f'_Pre-{FLOOR_SEASON} tier alone, then all-time. The two are printed '
      f'separately so the added history is visible as its own population '
      f'rather than folded invisibly into a bigger number._\n')
    a(_table(ext['pre_overview']))
    a(_table(ext['all_overview']))

    a(f'\n### 12.2 Scope split, home and away against finals\n')
    a(_table(ext['pre_scope_split']))
    a(_table(ext['all_scope_split']))

    a(f'\n### 12.3 Venue\n')
    a('_Venue strings are the era\'s own. A ground that changed name across '
      'the join appears under both, and no two rows are merged on a guess._\n')
    a(_table(ext['pre_by_venue']))
    a(_table(ext['all_by_venue']))

    a(f'\n### 12.4 Day of week, all-time\n')
    a(_table(ext['all_by_day']))

    a(f'\n### 12.5 Same calendar date, all-time\n')
    if fixture_date is None:
        a('_Not computed. Needs `--date`, as section 7 does._\n')
    a(_table(ext['all_same_calendar_date']))

    a(f'\n### 12.6 Streaks, all-time, match basis only\n')
    a(f'_The match basis is the ONLY one that crosses the join, because the '
      f'pre-{FLOOR_SEASON} tier has no quarter scores. The Q1 to Q4 streaks in '
      f'section 9 keep their {FLOOR_SEASON} floor and are not restated here._\n')
    a(f'_Computed on all {int(em.all_meetings)} meetings whatever the scope, '
      f'the same inversion section 9 applies: a final between two home-and-away '
      f'results breaks continuity._\n')
    # `ties` is printed here and not in section 9. Widening the archive is
    # exactly what creates ties at the longest: two runs of equal length that
    # sat in different eras now sit in one population. A tied longest presented
    # as "the" longest is a superlative the data does not support, so the count
    # travels with the row.
    a(f'_A `ties` above 1 means the longest is SHARED. It is not a '
      f'superlative and must not be written as one._\n')
    for label, key in (('Win streaks', 'all_win_streaks'),
                       ('Non-loss streaks', 'all_non_loss_streaks')):
        a(f'\n**{label}**\n')
        a(_table(ext[key], cols=_streak_cols() + ['ties', 'floor']))
    return L, cuts, em


def build_facts(subject, opponent, scope='all', fixture_date=None,
                without=(), matches=None, extended=False):
    """Return the facts file as markdown text, and the run's own metadata."""
    table = load_match_table() if matches is None else matches

    # --without is resolved BEFORE anything is written. An ambiguous name stops
    # the run rather than skipping the cut and continuing, because a preview
    # that quietly omits the section it was asked for is worse than no preview.
    resolved = []
    for player in without:
        cut = h2h_without(subject, opponent, player, matches=table)
        if cut['status'] in ('ambiguous', 'not_found'):
            return None, cut
        resolved.append((player, cut))

    rec = h2h_records(subject, opponent, scope=scope,
                      fixture_date=fixture_date, matches=table)
    stk = h2h_streaks(subject, opponent, scope=scope, matches=table)
    m = rec['meetings']
    ov = rec['series_overview'].iloc[0]

    cuts_tested = sum(len(rec[s]) for s in CUT_SECTIONS if s in rec)

    L = []
    a = L.append
    a(f'# {subject} v {opponent}, head to head facts\n')
    a(f'Subject team: **{subject}**. Every record below is oriented to '
      f'{subject}, never to the home side.\n')
    a(f'- Scope: `{scope}`')
    a(f'- Meetings in scope: **{int(ov.denominator)}**')
    a(f'- Fixture date supplied: {fixture_date or "none, section 7 not computed"}')
    a(f'- Conditional cells tested across sections 3 to 8: **{cuts_tested}**')
    a(f'- Source, identical for every table below: '
      f'{_sources(rec["series_overview"])}')
    a(f'- Generated by `team_h2h.py`. Facts only: no tweet copy, no draft, '
      f'and `draft_gate.py` has no team-mode coverage.\n')
    # FLOOR_CAVEAT already opens with "Archive floor 1965.", so it is quoted
    # rather than prefixed.
    a(f'> {FLOOR_CAVEAT}\n')
    if extended:
        a(f'> **Two floors in this file.** `--extended` was passed, so section '
          f'12 adds the {EXTENDED_FLOOR} to {FLOOR_SEASON - 1} tier. The '
          f'caveat above governs sections 1 to 11 and nothing else. Section 12 '
          f'names its own floor on every table.\n')
    a('> **Reading the cuts.** A series this long will contain a striking '
      'pattern somewhere in {quarters x result x venue x timeslot x day}. '
      f'{cuts_tested} cells were tested to produce the sections below, so any '
      'single striking cell is one of ' + str(cuts_tested) + ', not a finding. '
      'Every cell prints its own denominator.\n')
    a('---\n')

    a('## 1. Series overview\n')
    a(_table(rec['series_overview']))
    a(_et_note(rec['series_overview'], m))

    a('\n## 2. Scope split, home and away against finals\n')
    a(_table(rec['scope_split']))

    for n, key, title in ((3, 'by_venue', 'Venue'),
                          (4, 'by_timeslot', 'Timeslot'),
                          (5, 'by_day', 'Day of week'),
                          (6, 'by_venue_timeslot', 'Venue x timeslot')):
        a(f'\n## {n}. {title}\n')
        if key == 'by_timeslot':
            a('_Bins are Day before 1600, Twilight 1600 to 1829, Night 1830 '
              'and later, on the venue-local HHMM start time. Each row carries '
              'its own season range because the bins are not comparable across '
              'eras: every 1965-era match started at 1420 and lands in Day._\n')
        if key == 'by_venue_timeslot':
            a('_Cells with no matches are suppressed. A suppressed cell never '
              'existed rather than having been filtered out._\n')
        a(_table(rec[key]))
        a(_et_note(rec[key], m))
        if key == 'by_venue':
            a('\n_Venue split by whether the subject was at home. Venue and '
              'home ground are collinear for most pairings, so the table above '
              'reads as a venue effect when part of it is a home effect. This '
              'is a display split of the same rows, not an additional cut, and '
              'it does not enter the cells-tested count._\n')
            a(_table(_venue_home_split(m)))

    a('\n## 7. Same calendar date\n')
    if fixture_date is None:
        a('_Not computed. This section needs the scheduled fixture date, and '
          'inventing a reference date would fabricate the whole section. Pass '
          '`--date`._\n')
    else:
        a(f'_Meetings sharing day and month with {fixture_date}, any year. '
          f'Reported as a fact rather than a signal: an expected count of 0 to '
          f'3 across a century is noise unless read with its denominator._\n')
    a(_table(rec['same_calendar_date']))

    a('\n## 8. Quarter by quarter\n')
    a('_Regulation quarters, differenced from the cumulative scores. Extra '
      'time is not a quarter and is never folded into one._\n')
    a(_table(rec['by_quarter']))
    a(_et_note(rec['by_quarter'], m))

    a('\n## 9. Streaks\n')
    a(f'_Streaks compute on **all {len(stk["population"])} meetings** whatever '
      f'the scope. A final between two home and away results breaks '
      f'continuity, and excluding it manufactures a streak that never '
      f'happened. Finals exclusion is right for rates and wrong for counts._\n')
    a(f'_A loss breaks a run, a draw does not. Win streaks and non-loss '
      f'streaks are separate definitions and are never mixed. Archive floor '
      f'{FLOOR_SEASON}: say "since {FLOOR_SEASON}", never "ever"._\n')
    # Where a run contains no draw the two definitions land on the same rows.
    # The underlying computations stay separate, per spec section 8; only the
    # printing of an identical row is collapsed, and the reason is stated.
    cmp_cols = ['length', 'composition', 'start_date', 'end_date']
    wl = stk['win_streaks'].set_index(['basis', 'kind'])
    nl = stk['non_loss_streaks'].set_index(['basis', 'kind'])
    same = [ix for ix in wl.index
            if ix in nl.index and wl.loc[ix, cmp_cols].equals(nl.loc[ix, cmp_cols])]
    same_longest = sorted({b for b, k in same if k == 'longest'})

    for label, key in (('Win streaks', 'win_streaks'),
                       ('Non-loss streaks', 'non_loss_streaks')):
        f = stk[key]
        a(f'\n### {label}\n')
        live_line = _live_summary(f)
        if live_line:
            a(f'_No live streak on any basis: {live_line}. The live rows are '
              f'collapsed to this line rather than repeated per basis._\n')
            f = f[f.kind != 'live']
        if key == 'non_loss_streaks' and same_longest:
            a(f'_Identical to the win streak on {", ".join(same_longest)}, '
              f'because those runs contain no draw and the two definitions '
              f'coincide there. Those bases are omitted below rather than '
              f'printed twice; the definitions themselves stay separate._\n')
            f = f[~((f.kind == 'longest') & (f.basis.isin(same_longest)))]
        if f.empty:
            a('_Every row on this definition coincided with the win streak '
              'above. Nothing differs._\n')
        else:
            a(_table(f, cols=_streak_cols()))
        a(_et_note(f, m))
        if scope == 'ha':
            a('\n**Finals inside these streak windows.** Scope is `ha`, but '
              'streaks still count finals. Each one inside a window is named '
              'here so the inclusion is visible rather than assumed.\n')
            rows = []
            for _, r in f.iterrows():
                for d in (r.get('finals_detail') or []):
                    rows.append({'basis': r.basis, 'kind': r.kind, **d})
            a(_table(pd.DataFrame(rows)) if rows else
              '_No final falls inside any window on this definition._\n')

    a('\n## 10. Cross-opponent enumeration\n')
    live = stk['win_streaks']
    live_match = int(live[(live.basis == 'match') & (live.kind == 'live')].length.iloc[0])
    if live_match < LIVE_STREAK_TRIGGER:
        a(f'_Not run. The trigger is a live win streak of '
          f'{LIVE_STREAK_TRIGGER} or more on the match basis, and the live '
          f'streak is {live_match}. The trigger is a cost control and is '
          f'tunable._\n')
    else:
        cross = cross_opponent_streaks(subject, 'win', 'match', matches=table)
        cm = cross['meta'].iloc[0]
        a(f'_Live win streak of {live_match} reached the trigger of '
          f'{LIVE_STREAK_TRIGGER}. The full ranked table follows: every '
          f'opponent, no top-N and no minimum-meetings floor, because a '
          f'collection floor removes exactly the rows that would contest the '
          f'claim._\n')
        a(f'- Definition: **win streak**, basis **match**, one definition '
          f'throughout')
        a(f'- Denominator: **{int(cm.denominator)} opponents** enumerated')
        a(f'- Rank 1: **{cm.rank1_opponents}** on {int(cm.rank1_length)}')
        if cm.tied_at_rank1:
            a(f'- **Tied at rank 1.** Gap to rank 2 is 0 and this is NOT a '
              f'superlative. No tie is broken by recency, meetings or anything '
              f'else.')
        else:
            a(f'- Gap to rank 2: **{cm.gap_to_rank_2}**')
        a(f'- Archive floor {FLOOR_SEASON}: this ranks meetings since '
          f'{FLOOR_SEASON}, not in club history.\n')
        a(_table(cross['table'], cols=['rank', 'opponent', 'length',
                                       'composition', 'start_season',
                                       'end_season', 'meetings',
                                       'finals_in_window', 'note']))

    a('\n## 11. With and without\n')
    if not resolved:
        a('_Not run. Opt-in via `--without`, repeatable._\n')
    for player, cut in resolved:
        meta = cut['meta'].iloc[0]
        arms = cut['arms']
        a(f'\n### {meta.player}\n')
        a(f'- Identifier: `{meta.url}`')
        a(f'- fitzRoy ID: {meta.ID or "null, not yet minted"} '
          f'(traceability only; `url` is the key)')
        a(f'- Clubs on record: {meta.clubs_on_record}')
        a(f'- Tenure at {meta.tenure_club}: **{meta.tenure_first} to '
          f'{meta.tenure_last}**, {int(meta.tenure_games_for_club)} games of '
          f'{int(meta.career_games)} career')
        a(f'- Reconciles: {int(meta.with_n)} with plus {int(meta.without_n)} '
          f'without plus {int(meta.outside_n)} outside the window equals '
          f'{int(meta.series_meetings)} meetings\n')
        a(_table(arms, cols=['arm', 'wins', 'losses', 'draws', 'denominator',
                             'first_meeting', 'last_meeting', 'finals']))
        with_n = int(arms.loc[arms.arm == 'with', 'denominator'].iloc[0])
        without_n = int(arms.loc[arms.arm == 'without', 'denominator'].iloc[0])
        if with_n == 0 or without_n == 0:
            empty = 'with' if with_n == 0 else 'without'
            a(f'\n**No contrast available.** The `{empty}` arm has a '
              f'denominator of 0, so there is nothing to compare against and '
              f'this is a bare record rather than a with/without finding. The '
              f'numbers are printed above; the framing is withheld. Do not '
              f'write this as "{subject} are X with {meta.player}" as though a '
              f'comparator existed.\n')
        a(f'\n_{meta.availability_note}_\n')
        a(f'\n_No quarter-by-quarter breakdown on this cut._\n')

    extended_cuts, extended_meta = 0, None
    if not extended:
        a(f'\n## 12. Extended tier, pre-{FLOOR_SEASON}\n')
        a(f'_Not run. Opt-in via `--extended`, which adds the {EXTENDED_FLOOR} '
          f'to {FLOOR_SEASON - 1} tier for the cuts that can cross the join._\n')
    else:
        lines, extended_cuts, extended_meta = _extended_lines(
            subject, opponent, scope, fixture_date, table)
        L.extend(lines)

    a('\n---\n')
    a(f'_Facts only. No forward-looking claim appears above: this tool is '
      f'retrospective and touches no model output. Archive floor '
      f'{FLOOR_SEASON}'
      + (f' for sections 1 to 11, {EXTENDED_FLOOR} for section 12.'
         if extended else '.') + '_\n')

    run = {'subject': subject, 'opponent': opponent, 'scope': scope,
           'fixture_date': fixture_date, 'meetings': int(ov.denominator),
           'cuts_tested': cuts_tested, 'live_match_streak': live_match,
           'without': [p for p, _ in resolved], 'extended': extended,
           'extended_cuts': extended_cuts,
           'all_meetings': (int(extended_meta.all_meetings)
                            if extended_meta is not None else None),
           'pre_meetings': (int(extended_meta.pre_meetings)
                            if extended_meta is not None else None)}
    return '\n'.join(L), run


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Team-level head-to-head fixture preview, facts file only.')
    p.add_argument('--teams', nargs=2, required=True, metavar=('SUBJECT', 'OPPONENT'),
                   help='subject team first; every record is oriented to it')
    p.add_argument('--scope', default='all', choices=('all', 'ha', 'finals'))
    p.add_argument('--date', default=None,
                   help='scheduled fixture date, YYYY-MM-DD. Feeds section 7 '
                        'only; without it that section reports as not computed')
    p.add_argument('--without', action='append', default=[], metavar='PLAYER',
                   help='player name or afltables url, repeatable, opt-in')
    p.add_argument('--extended', action='store_true',
                   help=f'add section 12, the {EXTENDED_FLOOR} to '
                        f'{FLOOR_SEASON - 1} tier, for the cuts that can cross '
                        f'the join. Timeslot, quarters and with/without cannot '
                        f'and keep their {FLOOR_SEASON} floor')
    p.add_argument('--out-dir', default=OUT_DIR)
    args = p.parse_args(argv)

    subject, opponent = args.teams
    try:
        text, run = build_facts(subject, opponent, scope=args.scope,
                                fixture_date=args.date, without=args.without,
                                extended=args.extended)
    except H2HError as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 1

    if text is None:
        # An ambiguous or unresolvable --without stops the run. The candidates
        # are printed so the caller can pass a url, and nothing is written.
        print(f'STOPPED: {run["message"]}', file=sys.stderr)
        cand = run.get('candidates')
        if cand is not None and not cand.empty:
            print(cand.to_string(index=False), file=sys.stderr)
        print('Nothing was written.', file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir,
                        f'h2h_{_slug(subject)}_{_slug(opponent)}.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(f'wrote {path}')
    print(f'  {run["meetings"]} meetings, scope {run["scope"]}, '
          f'{run["cuts_tested"]} cells tested, live match streak '
          f'{run["live_match_streak"]}')
    if run['without']:
        print(f'  with/without: {", ".join(run["without"])}')
    if run['extended']:
        print(f'  extended: {run["all_meetings"]} all-time meetings '
              f'({run["pre_meetings"]} pre-{FLOOR_SEASON}), '
              f'{run["extended_cuts"]} extended cells tested')
    return 0


if __name__ == '__main__':
    sys.exit(main())
