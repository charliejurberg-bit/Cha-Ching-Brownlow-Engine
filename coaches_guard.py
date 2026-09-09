"""Contaminated-game guard for the coaches vote archive.

Imported by brownlow_model.py and backtest.py, and by nothing else. The two must
apply this identically: if backtest.py filters differently from the trainer it
stops measuring the model that ships, so the logic lives here once rather than
being copied into both.

WHAT IS WRONG WITH THE ARCHIVE

coaches_votes_all.csv carries a broadcast defect from its upstream feed. A
single row is repeated identically across every round from 19 to the end of the
season, plus one finals round, on one fixture per season. Verified upstream:
scripts/fetch_coaches_2015_2025.R regenerates the 2015-2025 half from fitzRoy
and the result is row-for-row identical to what is checked in, so this is not a
write-path fault and cannot be fixed by refetching. It will recur whenever the
feed is next read, which is why the drop set is computed every run and no list
of games, seasons or fixtures is hardcoded anywhere in this file.

WHY DROP THE WHOLE GAME

Coaches_Votes_game_rank, _game_pct, _game_z, BOG_Coaches and Top3_Coaches are
all computed groupby('Game_ID') in features.py. One wrong value therefore
re-ranks every player in that game, so the collateral is far larger than the
contamination: on the current archive, 130 contaminated rows sit in games
holding 2,096 rows in total.

Dropping only the offending player-round, or nulling its value, both leave the
other players in that game in the frame and both still change their ranks,
because rank is computed over whatever rows survive. Removing a game's top
vote-getter promotes everyone below them. Only dropping the whole game leaves no
row whose features were computed against a contaminated population.

WHAT COUNTS AS CONTAMINATED

Three tests, applied to the coaches source frame and to the summed value the
merge produces. Any one of them condemns the group, and the group condemns its
whole game:

  1 DUPLICATE  two or more source rows share Season + Round + player + club.
               The readers collapse those with groupby(...).sum(), so the model
               trains on the total as if it were one game.
  2 FRACTIONAL the value is not a whole number. Two coaches awarding 5-4-3-2-1
               can only produce an integer.
  3 CEILING    the value exceeds 10, which is both coaches awarding their top
               place to one player and is the hard maximum.

The three are not redundant. On the current archive test 3 alone catches 14
groups that are integer-valued and non-duplicate, so tests 1 and 2 both miss
them: Bobby Hill at 15.0 repeated across 2023 rounds 19 to 24 and 28, and
Isaac Smith and Patrick Dangerfield in 2022. Those four extra games are the
difference between 42 games and 46.

THE PINNED EXPECTATION

A guard that quietly stops matching is worse than no guard, so the counts are
pinned. They are gated on a fingerprint of the source archive rather than
asserted unconditionally, because the archive is expected to grow: 2026 is not
in it yet and the same broadcast is expected when that feed reopens. When the
fingerprint matches, the counts are enforced exactly and a zero-drop run fails.
When it does not, the pin is reported stale and only the weaker invariant is
enforced, so a legitimately updated archive does not block a retrain while a
silently changed one cannot pass unnoticed.
"""

import numpy as np
import pandas as pd

__all__ = ['drop_contaminated_games', 'contaminated_keys', 'clean_source',
           'GuardError']

# Both coaches award 5-4-3-2-1, so one player's two-coach sum cannot exceed
# 2 * 5 and a game cannot carry other than 2 * (5+4+3+2+1).
VOTE_CEILING = 10
VOTES_PER_GAME = 30

GROUP_KEY = ['Season', 'Round', 'CV_Player', 'CV_Team']

# A copy of the readers' TEAM_ABBREV, used only when the caller has not already
# split Player.Name. Kept local rather than imported: importing either reader to
# borrow the dict would execute a training script.
TEAM_ABBREV = {
    'ADEL': 'Adelaide', 'BL': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FRE': 'Fremantle',
    'GCFC': 'Gold Coast', 'GEEL': 'Geelong', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WB': 'Western Bulldogs', 'WCE': 'West Coast',
}

# Fingerprint of the archive these counts were measured against, and the counts
# themselves. coaches_rows is the whole-file row count, which is what changes
# when a season is appended. Re-measure and update all three together; never
# update the counts alone.
EXPECTED = {
    'coaches_rows': 26151,   # coaches_votes_all.csv, seasons 2006-2025
    'games': 46,
    'rows': 2096,
}


class GuardError(RuntimeError):
    """The guard did not behave as pinned. Never caught inside this module."""


def _prepare(coaches):
    """The source frame with the same keys the readers merge on.

    CV_Player / CV_Team are reused when the caller has already built them, so
    this never disagrees with the merge it is guarding. They are derived only
    when absent.
    """
    c = coaches.copy()
    c['Season'] = pd.to_numeric(c['Season'], errors='coerce')
    c['Round'] = pd.to_numeric(c['Round'], errors='coerce')
    c['_v'] = pd.to_numeric(c['Coaches.Votes'], errors='coerce').fillna(0)
    if 'CV_Player' not in c.columns:
        c['CV_Player'] = c['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
    if 'CV_Team' not in c.columns:
        c['CV_Team'] = c['Player.Name'].str.extract(r'\(([^)]+)\)')[0].map(TEAM_ABBREV)
    return c


def contaminated_keys(coaches):
    """Groups failing any of the three tests, as a frame of GROUP_KEY plus flags.

    Computed from the data every call. Nothing here is a fixture list, a season
    list or a game list, so a defect that appears in a season this code has
    never seen is caught without an edit.
    """
    c = _prepare(coaches)
    g = c.groupby(GROUP_KEY, dropna=False)['_v']
    a = g.agg(['sum', 'size']).reset_index()
    # Applied to the source rows AND to the summed value. A pair of legal rows
    # can sum past the ceiling, and only the summed form is what the model sees.
    a = a.merge(g.apply(lambda s: bool((s.mod(1) != 0).any()))
                 .reset_index(name='_src_frac'), on=GROUP_KEY)
    a = a.merge(g.apply(lambda s: bool((s > VOTE_CEILING).any()))
                 .reset_index(name='_src_over'), on=GROUP_KEY)
    a['test_duplicate'] = a['size'] > 1
    a['test_fractional'] = a['_src_frac'] | (a['sum'].mod(1) != 0)
    a['test_ceiling'] = a['_src_over'] | (a['sum'] > VOTE_CEILING)
    a['contaminated'] = a.test_duplicate | a.test_fractional | a.test_ceiling
    return a[a.contaminated].copy()


def clean_source(coaches, verbose=False):
    """Source rows safe to SUM per player per season. For DISPLAY, not training.

    drop_contaminated_games is the training answer and stays the training
    answer. This is the answer for a reader-facing season total, and the two
    differ because they are protecting different things.

    WHY A DISPLAY TOTAL NEEDS ITS OWN RULE
    A card shows "coaches votes, 2025" as a season sum. There is no
    within-game ranking in that number, so the collateral argument that makes
    the trainer drop whole games does not apply, and dropping a whole game
    would delete real votes from a player's season for no gain. What a display
    total needs is the opposite: keep every vote that is real, drop every vote
    that is not.

    Left unguarded the damage is not subtle. The broadcast defect repeats one
    fixture across every round from 19 to the end of the season, so a player
    caught in it collects that game's votes eight times over: Will Ashcroft's
    2025 reads 166 in the raw archive against a true 58, which made him the
    league's leading coaches-vote getter by 40 from a figure that is 108 votes
    of one repeated game. The stored archive names the wrong leader in four of
    the five seasons 2021-2025.

    TWO STEPS, AND THE ORDER IS LOAD BEARING

      1 Drop every row belonging to a fixture whose votes do not sum to
        VOTES_PER_GAME. This removes the phantom fixture outright. A display
        pass can do this where the trainer cannot, because Home.Team and
        Away.Team identify the phantom directly and the trainer's merge key
        never carries them.
      2 Apply contaminated_keys to what survives and drop what it still
        condemns. Step 1 alone is not enough: 51 groups across 2018-2021 sit
        in fixtures that DO sum to 30, and are duplicates or over the ceiling
        inside a legitimate game.

    Running the two the other way round is worse than either. contaminated_keys
    condemns a player-round group when two source rows share its key, and the
    phantom shares the key of whatever real game that player played that round,
    so a group-first pass throws away the real row with the fake one. Ashcroft
    loses a genuine 9-vote round 20 and a genuine 3-vote round 23 that way, and
    reads 46 rather than 58. Removing the phantom first leaves one legal row
    and the group is no longer a duplicate.

    Returns a new frame carrying the caller's columns plus CV_Player and
    CV_Team. coaches is not modified. The fixture columns are required; a frame
    without them cannot be cleaned this way and raises rather than silently
    falling back to the weaker rule.
    """
    for col in ('Home.Team', 'Away.Team'):
        if col not in coaches.columns:
            raise GuardError(
                f'clean_source needs {col} to identify the repeated fixture, '
                f'and the frame does not carry it. Use contaminated_keys '
                f'directly if the source has no fixture columns.')

    c = _prepare(coaches)
    n0 = len(c)
    game = ['Season', 'Round', 'Home.Team', 'Away.Team']
    ok = np.isclose(c.groupby(game, dropna=False)['_v'].transform('sum'),
                    VOTES_PER_GAME)
    c = c[ok]
    n1 = len(c)

    bad = contaminated_keys(c)
    if len(bad):
        keys = bad[GROUP_KEY].assign(_bad=True)
        marked = c.merge(keys, on=GROUP_KEY, how='left')
        if len(marked) != len(c):
            raise GuardError(f'clean_source merge changed row count, {len(c):,} '
                             f'to {len(marked):,}. Refusing to guess.')
        c = marked[marked['_bad'].isna()].drop(columns='_bad')
    n2 = len(c)

    # Cheap post-conditions. Neither can hold if the two steps ran in the wrong
    # order or if a step silently matched nothing.
    v = c['_v']
    if (v.mod(1) != 0).any() or (v > VOTE_CEILING).any():
        raise GuardError('clean_source left a fractional or above-ceiling value '
                         'behind, so it did not do what it claims.')

    if verbose:
        print(f'Coaches source cleaned for display: {n0:,} rows in, {n2:,} out')
        print(f'  fixtures not summing to {VOTES_PER_GAME}: {n0 - n1:,} rows')
        print(f'  groups still condemned after that:       {n1 - n2:,} rows '
              f'({len(bad):,} groups)')
    return c.drop(columns='_v')


def drop_contaminated_games(df, coaches, enforce=True, label=''):
    """Drop every Game_ID holding at least one contaminated coaches row.

    df must already carry Game_ID, Season, Round_num, Player_Name and
    Playing.for, which is true from the line after Game_ID is built in both
    readers. coaches is the raw source frame, before the groupby.

    Returns a new frame. df is not modified.
    """
    for col in ('Game_ID', 'Season', 'Round_num', 'Player_Name', 'Playing.for'):
        if col not in df.columns:
            raise GuardError(
                f'coaches guard needs {col} and the frame does not carry it. '
                f'The guard runs after Game_ID is built, not before.')

    bad = contaminated_keys(coaches)
    tag = f' [{label}]' if label else ''
    print(f'\nCoaches contamination guard{tag}')
    print(f'  contaminated coaches groups: {len(bad):,}'
          f'  (duplicate {int(bad.test_duplicate.sum())},'
          f' fractional {int(bad.test_fractional.sum())},'
          f' above {VOTE_CEILING} {int(bad.test_ceiling.sum())};'
          f' tests overlap)')

    keys = bad.rename(columns={'Round': 'Round_num', 'CV_Player': 'Player_Name',
                               'CV_Team': 'Playing.for'})
    keys = keys[['Season', 'Round_num', 'Player_Name', 'Playing.for']].assign(_bad=True)
    marked = df.merge(keys, on=['Season', 'Round_num', 'Player_Name', 'Playing.for'],
                      how='left')
    if len(marked) != len(df):
        # keys is unique per group, so a left merge cannot fan out. If it did,
        # the drop set would be wrong and silently so.
        raise GuardError(f'guard merge changed row count, {len(df):,} to '
                         f'{len(marked):,}. Refusing to guess the drop set.')
    hit = marked['_bad'].fillna(False).to_numpy(dtype=bool)

    bad_games = pd.unique(marked.loc[hit, 'Game_ID'])
    in_bad = marked['Game_ID'].isin(bad_games).to_numpy(dtype=bool)
    n_games, n_rows = len(bad_games), int(in_bad.sum())

    print(f'  rows carrying a contaminated value: {int(hit.sum()):,}')
    print(f'  GAMES DROPPED: {n_games:,}')
    print(f'  ROWS DROPPED:  {n_rows:,} of {len(df):,} ({n_rows / max(len(df), 1):.3%})')

    if n_rows:
        per = (marked.loc[in_bad]
               .assign(_hit=hit[in_bad])
               .groupby('Season')
               .agg(games=('Game_ID', 'nunique'), rows=('Game_ID', 'size'),
                    contaminated=('_hit', 'sum')))
        per['collateral'] = per['rows'] - per['contaminated']
        print('  per season:')
        print(f"      {'season':>7} {'games':>6} {'rows':>7} "
              f"{'contaminated':>13} {'collateral':>11}")
        for s, r in per.iterrows():
            print(f"      {int(s):>7} {int(r.games):>6} {int(r.rows):>7} "
                  f"{int(r.contaminated):>13} {int(r.collateral):>11}")

    if enforce:
        _enforce(coaches, n_games, n_rows)

    out = df.loc[~in_bad].copy().reset_index(drop=True)
    print(f'  frame: {len(df):,} rows in, {len(out):,} rows out')
    return out


def _enforce(coaches, n_games, n_rows):
    """Hold the guard to its pinned counts, gated on the archive fingerprint."""
    fingerprint = len(coaches)
    if fingerprint != EXPECTED['coaches_rows']:
        print(f'  ! PIN STALE: coaches archive is {fingerprint:,} rows, the pinned '
              f"counts were measured against {EXPECTED['coaches_rows']:,}.")
        print(f'  ! Exact counts not enforced. Re-measure and update EXPECTED in '
              f'coaches_guard.py, all three values together.')
        if n_games == 0:
            print('  ! Zero games dropped on a changed archive. That is either a '
                  'genuinely clean feed or a broken guard, and this cannot tell '
                  'which. Verify with scripts/validate_coaches.py before trusting it.')
        return

    if n_games != EXPECTED['games'] or n_rows != EXPECTED['rows']:
        raise GuardError(
            f"guard drifted on an UNCHANGED archive ({fingerprint:,} rows). "
            f"Expected {EXPECTED['games']} games and {EXPECTED['rows']:,} rows, "
            f"got {n_games} games and {n_rows:,} rows. The archive is byte-stable "
            f"so the guard logic changed, not the data. Zero games dropped here "
            f"would be a failed guard, not a clean archive.")
    print(f"  pin OK: {EXPECTED['games']} games / {EXPECTED['rows']:,} rows, "
          f"archive fingerprint {fingerprint:,} rows")
