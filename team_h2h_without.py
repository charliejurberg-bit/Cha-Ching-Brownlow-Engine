"""The with/without player cut for one head-to-head series.

    from team_h2h_without import h2h_without
    out = h2h_without('Richmond', 'St Kilda', 'Tim Taranto')

This cut only. No CLI, no markdown. It runs in addition to the standard
preview, never instead of it.

**`url` is the identifier. Not `ID`, and never a name.**

`url` has zero nulls across all three sources, 6,046 distinct values over
445,409 player rows, and is available from 1965. `ID` is carried alongside for
traceability and is null on 82 rows: one player in 2025 and eleven in 2026
whose AFLTables numeric ID has not been minted yet. Those are exactly the
recent players this cut gets asked about, so keying on `ID` would fail on the
question most likely to be posed.

A name is not an identifier. Scott Thompson resolves to two people who played
simultaneously at different clubs, and both Bailey Williamses were active in
2026. On a name that resolves to more than one `url` this function **stops and
returns the candidates** with club and season range. It never picks the one
with more games, the more recent one, or the one matching the subject club.
Pass a `url` directly to disambiguate.

**Tenure is the subject club's, not the career's.** The window runs from the
player's first to last appearance for the subject team specifically. A player
who later moves clubs does not extend it, which matters here because Tim
Taranto's career spans Greater Western Sydney and Richmond and only the
Richmond half is a Richmond tenure.

**Listed but did not play counts as "without".** Availability, suspension,
selection and a late withdrawal are not distinguishable from this data. The
returned metadata says so rather than letting a reader infer that "without"
means injured.

No quarter-by-quarter breakdown on this cut, per spec section 10. The match
result is the extra-time inclusive one the loader stored, per section 3.
"""

import pandas as pd

from club_aliases import canonical_club
from team_h2h_records import H2HError, h2h_records
from team_h2h_streaks import FLOOR_CAVEAT
from team_match_table import SOURCES, FINALS_CODES
from team_match_table import load_match_table

# The key the loader builds its table on. Player rows reduce to it exactly:
# 10,469 distinct keys on both sides with zero orphans either way.
KEY = ['season', 'round', 'home_team', 'away_team', 'date']

PLAYER_COLS = ['Season', 'Round', 'Date', 'Home.team', 'Away.team',
               'Playing.for', 'First.name', 'Surname', 'ID', 'url']

AVAILABILITY_NOTE = (
    'A meeting inside the tenure window where the player has no row is counted '
    'as "without". This data cannot distinguish being dropped from being '
    'injured, suspended, rested or a late withdrawal, so "without" means only '
    'that he did not take the field.'
)


def _player_rows():
    """Every player row across the three sources, keyed to the match table."""
    frames = []
    for path, _lo, _hi in SOURCES:
        frames.append(pd.read_csv(path, usecols=PLAYER_COLS, low_memory=False))
    p = pd.concat(frames, ignore_index=True)
    label = p['Round'].astype(str).str.strip().str.upper()
    is_final = label.isin(FINALS_CODES)
    rnd = p['Round'].astype(str).str.strip()
    p['round'] = [lab if fin else int(lab) for lab, fin in zip(rnd, is_final)]
    p['season'] = p['Season'].astype(int)
    p['date'] = pd.to_datetime(p['Date'])
    p['home_team'] = p['Home.team'].map(canonical_club)
    p['away_team'] = p['Away.team'].map(canonical_club)
    p['club'] = p['Playing.for'].map(canonical_club)
    # Built from First.name and Surname, which have zero nulls in all three
    # sources. `Player` is null on 69 rows and is not used for resolution.
    p['name'] = p['First.name'].str.strip() + ' ' + p['Surname'].str.strip()
    return p


def resolve_player(player, rows=None):
    """Return the candidate rows for a player argument, as a DataFrame.

    A `url` returns at most one candidate. A name returns one per distinct
    person carrying that name, which is the point: the caller sees the
    ambiguity rather than a silently chosen winner.
    """
    p = _player_rows() if rows is None else rows
    hit = p[p.url == player] if str(player).startswith('http') else p[p.name == player]
    if hit.empty:
        return pd.DataFrame(columns=['url', 'name', 'clubs', 'first_season',
                                     'last_season', 'games', 'ID'])
    return (hit.groupby('url')
            .agg(name=('name', 'first'),
                 clubs=('club', lambda s: ', '.join(sorted(s.unique()))),
                 first_season=('season', 'min'), last_season=('season', 'max'),
                 games=('season', 'size'),
                 # Printed for traceability only. May be empty, which is the
                 # reason url and not ID is the key.
                 ID=('ID', lambda s: ', '.join(sorted({str(int(x)) for x in s.dropna()})) or ''))
            .reset_index())


def _wld(df, arm, note=''):
    """W-L-D with its denominator for one arm."""
    counts = df.result.value_counts() if len(df) else {}
    wins = int(counts.get('W', 0))
    losses = int(counts.get('L', 0))
    draws = int(counts.get('D', 0))
    return {
        'arm': arm,
        'wins': wins, 'losses': losses, 'draws': draws,
        'denominator': wins + losses + draws,
        'first_meeting': df.date.min().date().isoformat() if len(df) else None,
        'last_meeting': df.date.max().date().isoformat() if len(df) else None,
        'includes_extra_time': bool(df.went_to_extra_time.any()) if len(df) else False,
        'finals': int(df.is_final.sum()) if len(df) else 0,
        'note': note,
        'source_file': '; '.join(sorted(df.source_file.unique())) if len(df) else None,
    }


def h2h_without(subject, opponent, player, matches=None):
    """Split one series by whether a player took the field, oriented to subject.

    `player` is a `url` or a name. A name resolving to more than one person
    returns `{'status': 'ambiguous', 'candidates': DataFrame, ...}` and computes
    nothing, because choosing between two people is not this function's call.

    Returns on success `{'status': 'ok', 'arms': DataFrame, 'meta': DataFrame,
    'meetings': DataFrame}`. `arms` carries three rows: with, without, and the
    meetings outside the tenure window, which are in neither arm. The three
    denominators sum to the series total, so nothing is quietly dropped.
    """
    table = load_match_table() if matches is None else matches
    rows = _player_rows()

    candidates = resolve_player(player, rows)
    if candidates.empty:
        return {'status': 'not_found', 'candidates': candidates,
                'message': f'{player!r} matched no player. A name must match '
                           f'First.name plus Surname exactly, or pass a url.'}
    if len(candidates) > 1:
        return {
            'status': 'ambiguous',
            'candidates': candidates.sort_values('first_season'),
            'message': f'{player!r} resolves to {len(candidates)} people. This '
                       f'function will not choose between them: not by games, '
                       f'not by recency, not by matching the subject club. '
                       f'Pass one of the url values above.',
        }

    cand = candidates.iloc[0]
    url = cand.url
    subject_c = canonical_club(subject)

    series = h2h_records(subject, opponent, scope='all', matches=table)['meetings']
    mine = rows[rows.url == url]
    at_subject = mine[mine.club == subject_c]
    if at_subject.empty:
        return {
            'status': 'no_tenure',
            'candidates': candidates,
            'message': f'{cand["name"]} has no appearance for {subject_c}. '
                       f'Clubs on record: {cand["clubs"]}. A tenure window is '
                       f'the subject club\'s, so there is nothing to split.',
        }

    # Tenure is first-to-last appearance FOR THE SUBJECT CLUB. A later move
    # does not extend it. Where a player left and returned the window spans the
    # gap, which is what first-to-last means and is reported as a date range so
    # the reader can see it.
    lo, hi = at_subject.date.min(), at_subject.date.max()
    in_window = series[(series.date >= lo) & (series.date <= hi)]
    outside = series[(series.date < lo) | (series.date > hi)]

    played_keys = set(map(tuple, mine[KEY].drop_duplicates().itertuples(index=False)))
    played = in_window[[tuple(r) in played_keys
                        for r in in_window[KEY].itertuples(index=False)]]
    absent = in_window[[tuple(r) not in played_keys
                        for r in in_window[KEY].itertuples(index=False)]]

    arms = pd.DataFrame([
        _wld(played, 'with'),
        _wld(absent, 'without', AVAILABILITY_NOTE),
        _wld(outside, 'outside tenure window',
             'Meetings before the first or after the last appearance for '
             f'{subject_c}. In neither arm, reported so the three denominators '
             'reconcile to the series total.'),
    ])

    meta = pd.DataFrame([{
        'subject': subject_c,
        'opponent': canonical_club(opponent),
        'player': cand['name'],
        'url': url,
        'ID': cand['ID'] or None,
        'id_is_null': not bool(cand['ID']),
        'clubs_on_record': cand['clubs'],
        'tenure_club': subject_c,
        'tenure_first': lo.date().isoformat(),
        'tenure_last': hi.date().isoformat(),
        'tenure_games_for_club': int(len(at_subject)),
        'career_games': int(len(mine)),
        'series_meetings': len(series),
        'in_window': len(in_window),
        'with_n': len(played),
        'without_n': len(absent),
        'outside_n': len(outside),
        'reconciles': len(played) + len(absent) + len(outside) == len(series),
        'availability_note': AVAILABILITY_NOTE,
        'quarter_breakdown': 'not computed on this cut, per spec section 10',
        'floor_caveat': FLOOR_CAVEAT,
        'source_file': '; '.join(sorted(series.source_file.unique())),
    }])
    if not meta.reconciles.iloc[0]:
        raise H2HError(
            f'with {len(played)} plus without {len(absent)} plus outside '
            f'{len(outside)} does not equal the series total {len(series)}'
        )

    tagged = series.assign(
        arm=['with' if tuple(r) in played_keys else 'without'
             for r in series[KEY].itertuples(index=False)])
    tagged.loc[(tagged.date < lo) | (tagged.date > hi), 'arm'] = 'outside tenure window'

    return {'status': 'ok', 'arms': arms, 'meta': meta, 'meetings': tagged}
