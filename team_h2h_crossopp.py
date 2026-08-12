"""Cross-opponent streak enumeration for one subject team.

    from team_h2h_crossopp import cross_opponent_streaks
    out = cross_opponent_streaks('Richmond', 'win', 'match')

Enumeration only. No with/without, no CLI, no markdown.

This module exists to stop a superlative shipping unchecked. Spec section 9:
no `only`, `no other`, `best`, `worst`, `highest` or `lowest` claim ships
without the full ranked table, because extending a range can kill a claim
rather than strengthen it. The table is the output, not a supporting file.

**One definition throughout.** `definition` and `basis` are both required and
have no defaults. That is deliberate: a caller who omits one would otherwise
get a table whose rows were built on whatever the default happened to be, and
a cross-opponent ranking that mixes win streaks with non-loss streaks is not a
ranking. Spec section 8 puts it as: win-streaks and non-loss streaks are never
mixed within a report.

**Every opponent is returned, including zeros.** No top-N, no minimum-meetings
floor, no dropping of opponents the subject has never beaten. A collection
floor removes exactly the rows that would contest the claim, so the denominator
would flatter the ranking it is supposed to test.

**Ties are reported as ties.** Where rank 1 is shared, the gap to rank 2 is
zero and `is_superlative` is False. Nothing breaks a tie: not recency, not
meetings played, not alphabetical order. A tied claim is a different claim and
the caller is told so rather than handed an arbitrary winner.

The trigger in spec section 9, a live streak of 4 or more, is a cost control
that belongs to the caller and is not enforced here. It is recorded as
LIVE_STREAK_TRIGGER so the number lives in code rather than only in prose, and
so a caller can gate on it without re-reading the spec.
"""

import time

import pandas as pd

from team_h2h_records import H2HError
from team_h2h_streaks import (FLOOR_CAVEAT, FLOOR_SEASON, NON_LOSS, WIN,
                              h2h_streaks)
from team_match_table import load_match_table

# Spec section 9. A cost control on the caller's side, not a gate in here: this
# module enumerates whenever it is asked to. Tunable by design.
LIVE_STREAK_TRIGGER = 4

DEFINITIONS = (WIN, NON_LOSS)

# Accepted lowercase, mapped to the labels team_h2h_streaks uses internally.
BASIS_ALIASES = {'match': 'match', 'q1': 'Q1', 'q2': 'Q2', 'q3': 'Q3', 'q4': 'Q4'}

# Spec section 5. Fitzroy is never folded into Brisbane: the 1996 merger created
# a new entity and attributing Fitzroy's record to Brisbane would be a different
# claim. Brisbane Bears does fold, which is the correct continuing-entity
# treatment and means that one row silently spans two eras unless it is
# labelled. The note below is that label.
BEARS_NOTE = ('Brisbane Lions folds Brisbane Bears via canonical_club(), so '
              'this row spans the 1987-1996 Bears era as well. Fitzroy is not '
              'folded and is a distinct opponent.')


def opponents_of(subject, matches):
    """Every club the subject has met since the archive floor, sorted."""
    played = matches[(matches.home_team == subject)
                     | (matches.away_team == subject)]
    if played.empty:
        raise H2HError(
            f'{subject!r} has no meetings in the match table. An empty opponent '
            f'set is a failed lookup, not an empty enumeration: check the club '
            f'spelling against canonical_club().'
        )
    seen = set(played.home_team) | set(played.away_team)
    return sorted(seen - {subject})


def cross_opponent_streaks(subject, definition, basis, matches=None):
    """Rank the subject's longest streak against every opponent it has met.

    `definition` is 'win' or 'non_loss' and `basis` is 'match' or 'q1'..'q4'.
    Both are required. One definition and one basis govern every row, and both
    are named in the returned metadata so a table cannot be read without them.

    The match table is loaded once here and passed down to every per-opponent
    call, because reloading it per opponent would pay a 3 second read eighteen
    times over for one enumeration.

    Returns a dict:
      table       DataFrame, one row per opponent, ranked, ties shared
      meta        one-row DataFrame: definition, basis, denominator, gap to
                  rank 2, tie state, floor caveat, elapsed seconds
      leaders     DataFrame, the rank 1 row or rows
    """
    if definition not in DEFINITIONS:
        raise H2HError(
            f'definition must be one of {DEFINITIONS}, got {definition!r}. It '
            f'is required and has no default so a ranking cannot mix win '
            f'streaks with non-loss streaks by omission.'
        )
    key = str(basis).lower()
    if key not in BASIS_ALIASES:
        raise H2HError(
            f'basis must be one of {tuple(BASIS_ALIASES)}, got {basis!r}. It '
            f'is required and has no default.'
        )
    basis_label = BASIS_ALIASES[key]
    frame_key = 'win_streaks' if definition == WIN else 'non_loss_streaks'

    started = time.time()
    table = load_match_table() if matches is None else matches
    opponents = opponents_of(subject, table)

    rows = []
    for opponent in opponents:
        out = h2h_streaks(subject, opponent, matches=table)
        f = out[frame_key]
        longest = f[(f.basis == basis_label) & (f.kind == 'longest')].iloc[0]
        live = f[(f.basis == basis_label) & (f.kind == 'live')].iloc[0]
        pop = out['population']
        rows.append({
            'opponent': opponent,
            'length': int(longest.length),
            'wins': int(longest.wins),
            'draws': int(longest.draws),
            'composition': longest.composition,
            'phrase': longest.phrase,
            'start_season': longest.start_season,
            'end_season': longest.end_season,
            'start_date': longest.start_date,
            'end_date': longest.end_date,
            'live_length': int(live.length),
            'meetings': len(pop),
            'includes_extra_time': bool(longest.includes_extra_time),
            'finals_in_window': int(longest.finals_in_window),
            'suppressed': bool(longest.suppressed),
            'reason': longest.reason,
            'note': BEARS_NOTE if opponent == 'Brisbane Lions' else '',
            'source_file': longest.source_file,
        })

    t = pd.DataFrame(rows).sort_values(
        ['length', 'opponent'], ascending=[False, True]).reset_index(drop=True)
    # min ranking, so a shared rank 1 reads as two firsts rather than a first
    # and a second.
    t['rank'] = t['length'].rank(ascending=False, method='min').astype(int)

    top = int(t.length.iloc[0])
    leaders = t[t['rank'] == 1]
    tied = len(leaders) > 1
    # Gap to rank 2 is the distance to the next DIFFERENT length. Where rank 1
    # is shared that distance is zero and the claim is not a superlative.
    lower = t[t.length < top]
    gap = 0 if tied else (top - int(lower.length.iloc[0]) if len(lower) else None)

    elapsed = time.time() - started
    meta = pd.DataFrame([{
        'subject': subject,
        'definition': definition,
        'basis': basis_label,
        'denominator': len(t),
        'opponents_enumerated': ', '.join(t.opponent),
        'rank1_length': top,
        'rank1_opponents': ', '.join(leaders.opponent),
        'tied_at_rank1': tied,
        'gap_to_rank_2': gap,
        'is_superlative': bool(not tied and gap not in (0, None)),
        'live_streak_trigger': LIVE_STREAK_TRIGGER,
        'trigger_enforced_here': False,
        'floor_season': FLOOR_SEASON,
        'floor_caveat': FLOOR_CAVEAT,
        'elapsed_seconds': round(elapsed, 2),
        'source_file': '; '.join(sorted(table.source_file.unique())),
    }])

    return {'table': t, 'meta': meta, 'leaders': leaders}
