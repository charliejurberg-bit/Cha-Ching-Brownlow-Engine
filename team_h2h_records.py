"""Head-to-head records and the fixed cut list, oriented to a subject team.

    from team_h2h_records import h2h_records
    out = h2h_records('Richmond', 'St Kilda')          # dict of DataFrames

Records and the eight fixed cuts from team_h2h_spec.md section 6. No streaks,
no cross-opponent enumeration, no with/without, no CLI, no markdown. This
module returns data; formatting and posting belong elsewhere.

Three things it is careful about, each recorded in the spec:

  - **Orientation.** Every result is oriented to the subject team, never the
    home side. The subject is away in roughly half of any series, so reading
    `home_score` as "our score" inverts half the record.
  - **Extra time.** The match result uses the extra-time-inclusive score the
    loader already stored in `home_score` / `away_score`. Quarter results are
    regulation only, differenced locally from the cumulative P columns. All
    three extra-time matches were drawn at full time, so their regulation Q4
    is a draw while their match result is a win or a loss. Both are true and
    they are different quantities, which is why every returned frame carries
    `includes_extra_time`.
  - **Cumulative quarters.** The loader stores cumulative points and does not
    difference them, because the cumulative values are also what a half-time
    lead figure needs. This module differences locally. A raw comparison of
    `subject_q2P` against `opp_q2P` answers "who led at half time" and is a
    different claim; it is deliberately not computed here.

The fixed cut list is pre-declared and identical on every run. A 106-meeting
series will always contain a striking pattern somewhere in {4 quarters x W/L/D
x venue x timeslot x day x home/away}; that is the search space talking. Every
frame therefore carries its denominator so the reader can see how thin a cell
is, and no section here searches for an angle.
"""

import pandas as pd

from team_match_table import load_match_table

SCOPES = ('all', 'ha', 'finals')

# Spec section 6. Assumption flagged there and tunable: every 1965-era match
# starts at 1420, so early seasons collapse entirely into Day. Each bin reports
# its own season range so that collapse is visible rather than inferred.
TIMESLOT_BINS = (
    ('Day', 0, 1600),
    ('Twilight', 1600, 1830),
    ('Night', 1830, 2400),
)

QUARTERS = (1, 2, 3, 4)

# Draws are a third column everywhere. Never folded into either side, never a
# half-win. Spec section 7.
RESULT_COLS = ['wins', 'losses', 'draws']


class H2HError(ValueError):
    """The requested series cannot be built. The message says why."""


# ---------------------------------------------------------------- helpers

def _timeslot(hhmm):
    """Bin an integer HHMM local start time. 1420 is 2:20pm."""
    for name, lo, hi in TIMESLOT_BINS:
        if lo <= hhmm < hi:
            return name
    return 'Unknown'


def _orient(matches, subject, opponent):
    """Reduce the match table to one series, oriented to the subject.

    Adds subject_score, opp_score, subject_is_home, and the cumulative
    subject_q1P..q4P / opp_q1P..q4P. Nothing is differenced here.
    """
    m = matches[
        ((matches.home_team == subject) & (matches.away_team == opponent))
        | ((matches.home_team == opponent) & (matches.away_team == subject))
    ].copy()
    if m.empty:
        raise H2HError(
            f'{subject} and {opponent} have no meetings in the match table. '
            f'An empty series is a failed lookup, not an empty record: check '
            f'the club spelling against canonical_club().'
        )

    home = m.home_team == subject
    m['subject_is_home'] = home
    m['subject_score'] = m.home_score.where(home, m.away_score)
    m['opp_score'] = m.away_score.where(home, m.home_score)
    for q in QUARTERS:
        m[f'subject_q{q}P'] = m[f'HQ{q}P'].where(home, m[f'AQ{q}P'])
        m[f'opp_q{q}P'] = m[f'AQ{q}P'].where(home, m[f'HQ{q}P'])

    # Match result, extra-time inclusive. home_score/away_score already carry
    # the extra-time total where one exists; the loader asserts that on every
    # match, so this does not re-derive it.
    m['result'] = _result(m.subject_score, m.opp_score)
    m['timeslot'] = m.local_start_time.map(_timeslot)
    m['day_month'] = m.date.dt.strftime('%m-%d')
    return m.sort_values('date').reset_index(drop=True)


def _result(subject, opp):
    """W, L or D as a Series. A draw is a draw."""
    return pd.Series(
        ['W' if s > o else 'L' if s < o else 'D' for s, o in zip(subject, opp)],
        index=subject.index,
    )


def _wld(df, result_col='result', by=None, extra=None):
    """W-L-D with denominator, provenance and the extra-time flag.

    `by` is a column name, a list of them, or None for the whole population.
    The denominator is W+L+D and is printed on every row, because a cut is
    only readable next to how many matches produced it.
    """
    if df.empty:
        cols = (by if isinstance(by, list) else [by] if by else []) + \
               RESULT_COLS + ['denominator', 'includes_extra_time',
                              'extra_time_n', 'source_file']
        return pd.DataFrame(columns=cols)

    keys = by if isinstance(by, list) else ([by] if by else [])
    grouped = df.groupby(keys, dropna=False) if keys else [((), df)]
    rows = []
    for key, g in (grouped if keys else grouped):
        rec = dict(zip(keys, key if isinstance(key, tuple) else (key,))) if keys else {}
        counts = g[result_col].value_counts()
        rec['wins'] = int(counts.get('W', 0))
        rec['losses'] = int(counts.get('L', 0))
        rec['draws'] = int(counts.get('D', 0))
        rec['denominator'] = rec['wins'] + rec['losses'] + rec['draws']
        # Spec section 3: a section whose population includes an extra-time
        # match must say so, or a regulation quarter record and an extra-time
        # match record get read as the same quantity.
        rec['includes_extra_time'] = bool(g.went_to_extra_time.any())
        rec['extra_time_n'] = int(g.went_to_extra_time.sum())
        rec['source_file'] = '; '.join(sorted(g.source_file.unique()))
        if extra:
            rec.update(extra(g))
        rows.append(rec)
    return pd.DataFrame(rows)


def _season_range(g):
    return {'season_first': int(g.season.min()), 'season_last': int(g.season.max())}


# ---------------------------------------------------------------- sections

def _series_overview(m):
    """1. Whole population, plus the first and last meeting."""
    out = _wld(m, extra=lambda g: {
        'season_first': int(g.season.min()),
        'season_last': int(g.season.max()),
        'first_meeting': g.date.min().date().isoformat(),
        'last_meeting': g.date.max().date().isoformat(),
        'subject_home_matches': int(g.subject_is_home.sum()),
    })
    return out


def _scope_split(m):
    """2. Home and away against finals, within the current scope."""
    d = m.assign(population=m.is_final.map({False: 'home and away', True: 'finals'}))
    return _wld(d, by='population', extra=_season_range)


def _by_venue(m):
    """3. W-L-D per venue."""
    return _wld(m, by='venue', extra=_season_range).sort_values(
        'denominator', ascending=False).reset_index(drop=True)


def _by_timeslot(m):
    """4. W-L-D per timeslot bin, each with its own season range.

    The season range is on the row because the bins are not comparable across
    eras: every 1965-era match starts at 1420 and lands in Day, so a Day record
    spans the whole archive while a Night record starts decades later.
    """
    return _wld(m, by='timeslot', extra=lambda g: dict(
        _season_range(g),
        start_time_first=int(g.local_start_time.min()),
        start_time_last=int(g.local_start_time.max()),
    ))


def _by_day(m):
    """5. W-L-D per day of week."""
    return _wld(m, by='day_of_week', extra=_season_range).sort_values(
        'denominator', ascending=False).reset_index(drop=True)


def _by_venue_timeslot(m):
    """6. Venue x timeslot. Cells with no matches are suppressed.

    groupby only emits observed combinations, so a suppressed cell is one that
    never existed rather than one filtered out. The denominator column is what
    makes a one-match cell readable as a one-match cell.
    """
    return _wld(m, by=['venue', 'timeslot'], extra=_season_range).sort_values(
        'denominator', ascending=False).reset_index(drop=True)


def _same_calendar_date(m, fixture_date):
    """7. Meetings sharing day-and-month with the scheduled fixture, any year.

    Reported as a fact, not a signal. Expected n of 0 to 3 across a century, so
    this cut is noise unless it is read alongside its denominator.

    Returns an empty frame carrying a `reason` column when no fixture date is
    given, because "same calendar date" is undefined without one and inventing
    a reference date would fabricate the whole section.
    """
    if fixture_date is None:
        return pd.DataFrame([{
            'day_month': None, **{c: 0 for c in RESULT_COLS},
            'denominator': 0, 'includes_extra_time': False, 'extra_time_n': 0,
            'source_file': None,
            'reason': 'no fixture_date given; section not computed',
        }])
    ref = pd.to_datetime(fixture_date).strftime('%m-%d')
    hit = m[m.day_month == ref]
    out = _wld(hit, by='day_month', extra=_season_range)
    if out.empty:
        out = pd.DataFrame([{
            'day_month': ref, **{c: 0 for c in RESULT_COLS},
            'denominator': 0, 'includes_extra_time': False, 'extra_time_n': 0,
            'source_file': None,
        }])
    out['fixture_date'] = pd.to_datetime(fixture_date).date().isoformat()
    return out


def _by_quarter(m):
    """8. W-L-D per quarter, regulation only, differenced locally.

    Q(n) = P[n] - P[n-1] with P[0] = 0. Extra time is not a quarter and is
    never folded into one, so a match that went to extra time contributes its
    regulation Q4 here and its extra-time result to every other section. All
    three such matches were drawn at full time, which is why the flag on these
    rows matters more than anywhere else.
    """
    rows = []
    for q in QUARTERS:
        prev_s = m[f'subject_q{q - 1}P'] if q > 1 else 0
        prev_o = m[f'opp_q{q - 1}P'] if q > 1 else 0
        d = m.assign(
            quarter=f'Q{q}',
            q_result=_result(m[f'subject_q{q}P'] - prev_s,
                             m[f'opp_q{q}P'] - prev_o),
        )
        rows.append(_wld(d, result_col='q_result', by='quarter',
                         extra=_season_range))
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------- public

def h2h_records(subject, opponent, scope='all', fixture_date=None, matches=None):
    """Return the fixed cut list for one series, oriented to `subject`.

    `scope` filters the population for every section in this module: 'all',
    'ha' for home and away, or 'finals'. The streak rule in spec section 8,
    where streaks always compute on all matches regardless of scope, governs a
    module that is not this one and does not apply here.

    `fixture_date` is optional and additive to the signature the build order
    specified. Section 7 asks for meetings sharing day-and-month with the
    scheduled fixture, and that is undefined without a reference date. Passing
    None returns that one section empty with a stated reason rather than
    inventing a reference date and reporting a cut nobody asked for.

    `matches` accepts a pre-loaded match table so a caller running several
    series does not pay the load repeatedly. It is verified by
    load_match_table() when omitted.

    Returns a dict of DataFrames: meetings, series_overview, scope_split,
    by_venue, by_timeslot, by_day, by_venue_timeslot, same_calendar_date,
    by_quarter. Every frame carries a denominator column and a source_file
    column, and every frame except meetings carries includes_extra_time.
    """
    if scope not in SCOPES:
        raise H2HError(f'unknown scope {scope!r}, expected one of {SCOPES}')
    if subject == opponent:
        raise H2HError(f'subject and opponent are both {subject!r}')

    table = load_match_table() if matches is None else matches
    m = _orient(table, subject, opponent)

    if scope == 'ha':
        m = m[~m.is_final]
    elif scope == 'finals':
        m = m[m.is_final]
    if m.empty:
        raise H2HError(
            f'{subject} v {opponent} has no meetings under scope {scope!r}. '
            f'An empty population is a failed check, not a zero record.'
        )
    m = m.reset_index(drop=True)

    return {
        'meetings': m,
        'series_overview': _series_overview(m),
        'scope_split': _scope_split(m),
        'by_venue': _by_venue(m),
        'by_timeslot': _by_timeslot(m),
        'by_day': _by_day(m),
        'by_venue_timeslot': _by_venue_timeslot(m),
        'same_calendar_date': _same_calendar_date(m, fixture_date),
        'by_quarter': _by_quarter(m),
    }
