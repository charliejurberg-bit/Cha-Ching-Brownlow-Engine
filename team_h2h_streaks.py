"""Head-to-head streaks, oriented to a subject team.

    from team_h2h_streaks import h2h_streaks
    out = h2h_streaks('Richmond', 'St Kilda')

Streaks only. No cross-opponent enumeration, no with/without, no CLI, no
markdown. Orientation is reused from team_h2h_records rather than re-derived,
so a change to how a subject is oriented moves both modules at once.

**Scope is inverted here, and that is the point of the module.** Every other
section in this tool filters its population by scope. Streaks always compute on
ALL matches regardless of scope, because a final sitting between two home and
away results breaks continuity, and excluding it manufactures a streak that
never happened. Finals exclusion is right for rates and wrong for counts. Under
scope='ha' the finals are still counted, and every streak additionally lists
the finals falling inside its own window so the inclusion is visible rather
than assumed.

Two definitions are computed and they are never merged. A run of wins is a win
streak; a run with no loss in it is a non-loss streak. They are returned in
separate frames because spec section 9 requires a cross-opponent ranking to use
one definition throughout, and handing back a single ambiguous "streak" number
is how that requirement gets broken by accident downstream.

Two kinds are computed and labelled distinctly. The live streak runs as of the
most recent meeting and is the post-worthy one; the longest historical streak
is context. Where the most recent meeting ends a run, the live streak is
returned as length 0 with a stated reason rather than omitted, because a
missing row reads as "not computed" and a zero reads as "computed, and it is
zero".
"""

import pandas as pd

from team_h2h_records import QUARTERS, H2HError, _result, h2h_records

# Spec section 4. A hard truncation, not a club-history boundary: Richmond and
# St Kilda met from 1908 and this archive holds the meetings from 1965 on. The
# caveat travels as a field on every streak rather than living in a docstring,
# because a streak is exactly the figure someone will lift into copy.
FLOOR_SEASON = 1965
FLOOR_CAVEAT = (
    f'Archive floor {FLOOR_SEASON}. This is a hard truncation of the data, not '
    f'a club-history boundary: earlier meetings exist and are not held here. '
    f'Say "since {FLOOR_SEASON}", never "ever" or "in club history".'
)

# The two definitions, kept apart end to end.
WIN, NON_LOSS = 'win', 'non_loss'

# What each definition treats as continuing a run. A loss breaks a streak; a
# draw does not.
CONTINUES = {WIN: lambda r: r == 'W', NON_LOSS: lambda r: r != 'L'}

BASES = ('match',) + tuple(f'Q{q}' for q in QUARTERS)


def _runs(results, keep):
    """Every maximal run where `keep` holds, as inclusive (start, end) indices."""
    out, start = [], None
    for i, r in enumerate(results):
        if keep(r):
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(results) - 1))
    return out


def _quarter_results(m):
    """Per-quarter W-L-D for the subject, regulation only.

    Differenced here because the loader stores cumulative points on purpose:
    the cumulative values are what a half-time lead figure needs. Extra time is
    not a quarter and never enters this, so a match that went to extra time
    contributes its regulation Q4 here and its extra-time result to the match
    basis.
    """
    out = {}
    for q in QUARTERS:
        prev_s = m[f'subject_q{q - 1}P'] if q > 1 else 0
        prev_o = m[f'opp_q{q - 1}P'] if q > 1 else 0
        out[f'Q{q}'] = _result(m[f'subject_q{q}P'] - prev_s,
                               m[f'opp_q{q}P'] - prev_o)
    return out


def _describe(m, results, lo, hi, definition, basis, kind, scope, reason=''):
    """One streak row: composition, window, provenance and the caveats."""
    n = 0 if lo is None else hi - lo + 1
    window = m.iloc[lo:hi + 1] if n else m.iloc[0:0]
    seq = list(results[lo:hi + 1]) if n else []
    wins = seq.count('W')
    draws = seq.count('D')
    row = {
        'basis': basis,
        'definition': definition,
        'kind': kind,
        'length': n,
        'wins': wins,
        'draws': draws,
        # Spec section 8: every non-loss streak prints its W-D composition, so
        # a reader can see whether "has not lost 9" is nine wins or five wins
        # and four draws.
        'composition': f'{wins}W-{draws}D' if n else '',
        'phrase': (f'won {n} consecutive' if definition == WIN and n else
                   f'has not lost {n} consecutive' if n else ''),
        'start_season': int(window.season.iloc[0]) if n else None,
        'end_season': int(window.season.iloc[-1]) if n else None,
        'start_round': window['round'].iloc[0] if n else None,
        'end_round': window['round'].iloc[-1] if n else None,
        'start_date': window.date.iloc[0].date().isoformat() if n else None,
        'end_date': window.date.iloc[-1].date().isoformat() if n else None,
        'includes_extra_time': bool(window.went_to_extra_time.any()) if n else False,
        'extra_time_n': int(window.went_to_extra_time.sum()) if n else 0,
        'finals_in_window': int(window.is_final.sum()) if n else 0,
        'suppressed': bool(reason),
        'reason': reason,
        'denominator': len(m),
        'population': 'all matches regardless of scope',
        'floor_caveat': FLOOR_CAVEAT,
        'source_file': '; '.join(sorted(window.source_file.unique())) if n else None,
    }
    # Spec section 8: under scope='ha' the finals are still counted, so each one
    # inside the window is named. Listing them is what makes the inclusion
    # visible rather than something the reader has to infer from the dates.
    if scope == 'ha':
        row['finals_detail'] = [
            {'season': int(r.season), 'round': r['round'],
             'date': r.date.date().isoformat(), 'result': res}
            for (_, r), res in zip(window.iterrows(), seq) if r.is_final
        ] if n else []
    return row


def _streaks_for(m, results, definition, basis, scope):
    """The live and longest streaks for one basis under one definition."""
    seq = list(results)
    runs = _runs(seq, CONTINUES[definition])

    # A run of draws only is suppressed, not reported. It is a real run and it
    # is not a streak anyone means, so it is excluded from the longest and
    # named as the reason when it is what the team is currently on.
    def all_draws(lo, hi):
        return 'W' not in seq[lo:hi + 1]

    live_run = next((r for r in runs if r[1] == len(seq) - 1), None)
    if live_run is None:
        live = _describe(m, seq, None, None, definition, basis, 'live', scope,
                         reason=f'most recent meeting was a '
                                f'{"loss" if seq[-1] == "L" else seq[-1]}, '
                                f'so no {definition.replace("_", "-")} streak '
                                f'is running')
    elif definition == NON_LOSS and all_draws(*live_run):
        live = _describe(m, seq, None, None, definition, basis, 'live', scope,
                         reason='current run is draws only, suppressed per '
                                'spec section 8')
    else:
        live = _describe(m, seq, *live_run, definition, basis, 'live', scope)

    eligible = [r for r in runs
                if not (definition == NON_LOSS and all_draws(*r))]
    if not eligible:
        longest = _describe(m, seq, None, None, definition, basis, 'longest',
                            scope, reason='no qualifying run in the archive')
    else:
        best = max(eligible, key=lambda r: r[1] - r[0])
        longest = _describe(m, seq, *best, definition, basis, 'longest', scope)
        span = best[1] - best[0]
        longest['ties'] = sum(1 for r in eligible if r[1] - r[0] == span)
    return live, longest


def h2h_streaks(subject, opponent, scope='all', matches=None):
    """Return the streak set for one series, oriented to `subject`.

    `scope` is accepted and recorded, and deliberately does NOT filter the
    population. Streaks compute on every meeting whatever the scope, per spec
    section 8. Under scope='ha' each returned streak carries `finals_detail`
    naming the finals inside its own window.

    Returns a dict:
      win_streaks       DataFrame, one row per basis per kind
      non_loss_streaks  DataFrame, same shape, never merged with the above
      population        the oriented meeting list the streaks were computed on
      meta              one-row DataFrame of the run's own parameters

    Bases are 'match' plus Q1 to Q4. The match basis uses the extra-time
    inclusive result; the quarter bases use regulation, per spec section 3.
    """
    # scope='all' here on purpose: this is the inversion. The population is
    # every meeting, and h2h_records is asked for it under the one scope that
    # does not filter. Orientation is reused rather than re-derived so the two
    # modules cannot drift on what "subject" means.
    m = h2h_records(subject, opponent, scope='all', matches=matches)['meetings']
    if scope not in ('all', 'ha', 'finals'):
        raise H2HError(f'unknown scope {scope!r}')
    m = m.sort_values('date').reset_index(drop=True)

    series = {'match': m.result}
    series.update(_quarter_results(m))

    frames = {}
    for definition in (WIN, NON_LOSS):
        rows = []
        for basis in BASES:
            live, longest = _streaks_for(m, series[basis], definition, basis, scope)
            rows.extend([live, longest])
        frames[definition] = pd.DataFrame(rows)

    meta = pd.DataFrame([{
        'subject': subject,
        'opponent': opponent,
        'scope_requested': scope,
        'scope_applied_to_streaks': 'none, all matches used',
        'meetings': len(m),
        'finals_in_population': int(m.is_final.sum()),
        'extra_time_in_population': int(m.went_to_extra_time.sum()),
        'first_meeting': m.date.min().date().isoformat(),
        'last_meeting': m.date.max().date().isoformat(),
        'floor_caveat': FLOOR_CAVEAT,
        'source_file': '; '.join(sorted(m.source_file.unique())),
    }])

    return {
        'win_streaks': frames[WIN],
        'non_loss_streaks': frames[NON_LOSS],
        'population': m,
        'meta': meta,
    }
