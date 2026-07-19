"""features.py — the one definition of the model's feature construction.

brownlow_model.py (train), predict_2026.py (in-season predict) and backtest.py
(walk-forward) all build the same features and must agree exactly: the model is
fitted on what this produces and reads what this produces. They used to hold
three copies of that logic, and it cost two audit findings — a whole-season
momentum leak that was fixed in training while backtest.py silently kept
measuring the leaked version, and merge keys that dropped team in one script but
not the others.

The three scripts differ in ways that are real and are parameterised here rather
than duplicated:

  group_keys        training and backtest span many seasons and group by
                    ['Season','Player_Name']; predict is one season and groups
                    by ['Player_Name'].
  fill_missing      predict zero-fills a rank triplet whose source stat is
                    absent, because it must return a row for every player;
                    training and backtest drop incomplete rows instead.
  include_coaches   the NO_COACHES variant omits the six same-game coaches
                    features.
  include_momentum_cv  whether the variant also drops momentum_cv, which is
                    built from Coaches_Votes but reads prior rounds only.

Anything NOT parameterised is meant to be identical everywhere. If a script
needs to diverge, add a parameter — do not fork the function.
"""

import numpy as np
import pandas as pd

# ── Merge keys ───────────────────────────────────────────────
# Team is part of both keys and must stay there. Dropping it lets two players
# who share a name take each other's data: a West Coast Bailey Williams was
# reading a Western Bulldogs Bailey Williams's Wheelo ratings for seven rounds
# before this was caught.
COACHES_MERGE_KEYS = ['Season', 'Round_num', 'Player_Name', 'Playing.for']
WHEELO_MERGE_KEYS = ['Player_Name', 'Playing.for', 'Season', 'Round_num']

# Coaches CSVs carry the club as a bracketed abbreviation in Player.Name
# ("Justin McInerney (SYD)"); the stats frame uses full names in Playing.for.
TEAM_ABBREV = {
    'ADEL': 'Adelaide', 'BL': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FRE': 'Fremantle',
    'GCFC': 'Gold Coast', 'GEEL': 'Geelong', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WB': 'Western Bulldogs', 'WCE': 'West Coast',
}
# Wheelo's own spelling, normalised before it meets Playing.for.
WHEELO_TEAM_FIXES = {'Brisbane': 'Brisbane Lions'}

# ── Feature groups ───────────────────────────────────────────
BASE_FEATURES = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles', 'Hit.Outs',
                 'Clearances', 'Contested.Possessions', 'Uncontested.Possessions',
                 'Contested.Marks', 'Marks.Inside.50', 'Goal.Assists', 'Inside.50s',
                 'Rebounds', 'One.Percenters', 'Clangers', 'Kick_to_HB_ratio',
                 'Contested_rate', 'Disposal_efficiency', 'Score_Involvements',
                 'Impact_Score', 'Is_Win', 'Is_Loss', 'Margin', 'Abs_Margin',
                 'Coaches_Votes', 'Season', 'Margin_Bucket_enc']

RANK_STATS_BASE = ['Disposals', 'Goals', 'Contested.Possessions', 'Clearances',
                   'Kicks', 'Impact_Score', 'Score_Involvements', 'Coaches_Votes', 'Tackles']
RANK_STATS_WHEELO = ['RatingPoints', 'ExpVotes']

WHEELO_COLS = ['RatingPoints', 'ExpVotes', 'Rating_Q1', 'Rating_Q2', 'Rating_Q3', 'Rating_Q4',
               'Equity_PreClearance', 'Equity_PostClearance', 'Equity_Possession', 'Equity_BallUse',
               'GroundBallGets', 'HitoutsToAdvantage', 'ScoreLaunches', 'FirstPossessions',
               'Supercoach', 'TimeOnGround', 'DisposalEfficiency', 'CentreBounceAttendancePercentage']

# The six same-game coaches features. The NO_COACHES variant omits exactly these.
COACHES_FEATURES = ['Coaches_Votes', 'Coaches_Votes_game_rank', 'Coaches_Votes_game_pct',
                    'Coaches_Votes_game_z', 'Top3_Coaches', 'BOG_Coaches']

# ── Momentum ─────────────────────────────────────────────────
# Point-in-time: shift(1) first so the current game is never part of its own
# feature, then trailing windows over strictly prior rounds. The version this
# replaced took the last six games of the COMPLETED season minus the first six
# and broadcast one value onto every row, so a round-2 row carried round-23
# information. That leak was invisible to GroupKFold because it lived in the
# features, not the split.
MOM_RECENT = 6
MOM_MIN_EARLIER = 2


def pit_momentum(s):
    """Trailing recent-minus-earlier for one player-season, in round order.

    recent  = mean of the previous MOM_RECENT games
    earlier = mean of every game before those
    Needs MOM_RECENT + MOM_MIN_EARLIER prior games; NaN below that.
    """
    prior = s.shift(1)
    recent_sum = prior.rolling(MOM_RECENT, min_periods=MOM_RECENT).sum()
    recent_mean = recent_sum / MOM_RECENT
    all_sum = prior.expanding(min_periods=1).sum()
    all_cnt = prior.expanding(min_periods=1).count()
    earlier_sum = all_sum - recent_sum
    earlier_cnt = all_cnt - MOM_RECENT
    ok = earlier_cnt >= MOM_MIN_EARLIER
    earlier_mean = earlier_sum.where(ok) / earlier_cnt.where(ok)
    return recent_mean - earlier_mean


# ── Construction ─────────────────────────────────────────────
def rank_stats_for(df):
    """The stats ranked within each game — Wheelo's two only when present."""
    stats = list(RANK_STATS_BASE)
    if 'RatingPoints' in df.columns:
        stats += RANK_STATS_WHEELO
    return stats


def build_game_rank_features(df, rank_stats, fill_missing=False):
    """Per-game rank / percentile / z-score for each stat.

    Within-game only, so no cross-season leakage: these describe how a player
    compared to the 43 others in the game whose votes are being predicted.

    fill_missing=True zero-fills a triplet whose source stat is absent — the
    predict path needs a row for every player and cannot drop them.
    """
    for stat in rank_stats:
        if stat in df.columns:
            g = df.groupby('Game_ID')[stat]
            df[f'{stat}_game_rank'] = g.rank(ascending=False, method='min')
            df[f'{stat}_game_pct'] = g.rank(pct=True)
            df[f'{stat}_game_z'] = g.transform(lambda x: (x - x.mean()) / (x.std() + 0.001))
        elif fill_missing:
            df[f'{stat}_game_rank'] = 0
            df[f'{stat}_game_pct'] = 0
            df[f'{stat}_game_z'] = 0
    return df


def build_rank_flags(df, include_coaches=True):
    """Top-3 and best-on-ground flags off the game ranks."""
    # Assignment order is deliberate: it reproduces the column order the scripts
    # produced before this module existed, so the output CSVs stay byte-identical
    # across the refactor rather than differing only by column position.
    _cv = include_coaches and 'Coaches_Votes_game_rank' in df.columns
    df['Top3_Disposals'] = (df['Disposals_game_rank'] <= 3).astype(int)
    if _cv:
        df['Top3_Coaches'] = (df['Coaches_Votes_game_rank'] <= 3).astype(int)
    df['Top3_Impact'] = (df['Impact_Score_game_rank'] <= 3).astype(int)
    df['BOG_Disposals'] = (df['Disposals_game_rank'] == 1).astype(int)
    if _cv:
        df['BOG_Coaches'] = (df['Coaches_Votes_game_rank'] == 1).astype(int)
    df['BOG_Impact'] = (df['Impact_Score_game_rank'] == 1).astype(int)
    if 'RatingPoints_game_rank' in df.columns:
        df['BOG_Rating'] = (df['RatingPoints_game_rank'] == 1).astype(int)
        df['Top3_Rating'] = (df['RatingPoints_game_rank'] <= 3).astype(int)
    return df


def build_form_features(df, group_keys, include_momentum_cv=True):
    """late_form_ewm + momentum, both strictly prior-round.

    group_keys is ['Season','Player_Name'] across seasons, ['Player_Name'] for a
    single-season frame. Caller must have sorted by those keys plus Round_num.

    late_form_ewm reads ExpVotes (Wheelo) when available. The Coaches_Votes
    fallback does not fire on current data — wheelo_all_seasons.csv carries
    ExpVotes for every season — so this feature is Wheelo-derived, not
    coaches-derived, and stays in the NO_COACHES variant.
    """
    src = 'ExpVotes' if 'ExpVotes' in df.columns else 'Coaches_Votes'
    if src in df.columns:
        df['late_form_ewm'] = (
            df.groupby(group_keys)[src]
            .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
            .fillna(0)
        )
    else:
        df['late_form_ewm'] = 0

    specs = [('Coaches_Votes', 'momentum_cv'), ('Disposals', 'momentum_disp')]
    if not include_momentum_cv:
        specs = [(s, o) for s, o in specs if o != 'momentum_cv']
    for src_col, out_col in specs:
        df[out_col] = (df.groupby(group_keys)[src_col]
                         .transform(pit_momentum)
                         .fillna(0))
    return df


def form_feature_names(df):
    return [f for f in ('late_form_ewm', 'momentum_cv', 'momentum_disp') if f in df.columns]


def assemble_features(df, rank_stats, wheelo_features, form_features,
                      include_coaches=True, include_momentum_cv=True):
    """The final ordered feature list, filtered to what the frame actually has.

    include_coaches=False is the NO_COACHES variant. The assertion is the point:
    a coaches feature surviving into that variant would be trained on data that
    does not exist at predict time, and nothing downstream would say so.
    """
    relative = (
        [f'{s}_game_rank' for s in rank_stats if f'{s}_game_rank' in df.columns] +
        [f'{s}_game_pct' for s in rank_stats if f'{s}_game_pct' in df.columns] +
        [f'{s}_game_z' for s in rank_stats if f'{s}_game_z' in df.columns] +
        ['Top3_Disposals', 'Top3_Coaches', 'Top3_Impact',
         'BOG_Disposals', 'BOG_Coaches', 'BOG_Impact']
    )
    if 'BOG_Rating' in df.columns:
        relative += ['BOG_Rating', 'Top3_Rating']

    features = list(dict.fromkeys(
        BASE_FEATURES + list(wheelo_features) + relative + list(form_features)))
    features = [f for f in features if f in df.columns]

    if not include_coaches:
        features = [f for f in features if 'Coaches' not in f]
        if not include_momentum_cv:
            features = [f for f in features if f != 'momentum_cv']
        leaked = [f for f in features if 'Coaches' in f]
        if not include_momentum_cv:
            leaked += [f for f in features if f == 'momentum_cv']
        assert not leaked, f"NO_COACHES feature set still carries: {leaked}"
    return features
