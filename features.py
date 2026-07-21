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

# ── Row-local derived stats ──────────────────────────────────
# Everything computable from a single player-game row, in the exact order the
# three scripts built it. Centralised because it was NOT before: predict_2026.py
# carried a stale four-term Impact_Score (Goals/Clearances/Contested/Kicks) while
# training and backtest used the six-term formula below, so the model was scored
# on an Impact_Score it had never been trained on. One definition now, imported
# by all three, so that can't recur — see the module docstring.

# Coerced to numeric (missing columns tolerated) before the ratios/Impact build.
NUMERIC_STATS = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles',
                 'Hit.Outs', 'Clearances', 'Contested.Possessions',
                 'Uncontested.Possessions', 'Contested.Marks', 'Marks.Inside.50',
                 'Goal.Assists', 'Inside.50s', 'Rebounds', 'One.Percenters', 'Clangers']

# LabelEncoder classes for Margin_Bucket. Already sorted, so a fresh fit and the
# pickled encoder agree; the encoder itself stays script-side (fit in training,
# unpickled at predict).
MARGIN_BUCKETS = ['big_loss', 'big_win', 'close_loss', 'close_win',
                  'comfortable_loss', 'comfortable_win', 'draw', 'unknown']


def get_outcome(row):
    """W/L/D and signed margin from the player's team's perspective."""
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a):
        return pd.Series({'Outcome': 'U', 'Margin': 0})
    margin = h - a if row['Home.Away'] == 'Home' else a - h
    return pd.Series({'Outcome': 'W' if margin > 0 else ('L' if margin < 0 else 'D'), 'Margin': margin})


def margin_bucket(m):
    """Signed margin -> a MARGIN_BUCKETS label (never 'unknown'; that's for NaN)."""
    if m > 0:
        return 'close_win' if m <= 15 else ('comfortable_win' if m <= 40 else 'big_win')
    elif m < 0:
        return 'close_loss' if m >= -15 else ('comfortable_loss' if m >= -40 else 'big_loss')
    return 'draw'


def add_row_stats(df):
    """All single-row derived stats, in the scripts' original order.

    Outcome/Margin/Abs_Margin/Is_Win/Is_Loss, then numeric coercion, the four
    ratios, Score_Involvements, the six-term Impact_Score, and the Margin_Bucket
    string. Margin_Bucket_enc is left to the caller: its LabelEncoder is fit in
    training but unpickled at predict, so the source differs by script.

    Assumes Home.score / Away.score / Home.Away already coerced upstream, as all
    three scripts do immediately before calling this.
    """
    df[['Outcome', 'Margin']] = df.apply(get_outcome, axis=1)
    df['Abs_Margin'] = df['Margin'].abs()
    df['Is_Win'] = (df['Outcome'] == 'W').astype(int)
    df['Is_Loss'] = (df['Outcome'] == 'L').astype(int)

    for col in NUMERIC_STATS:
        df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

    df['Kick_to_HB_ratio'] = df['Kicks'] / (df['Handballs'] + 1)
    df['Contested_rate'] = df['Contested.Possessions'] / (df['Disposals'] + 1)
    df['Disposal_efficiency'] = (df['Disposals'] - df['Clangers']) / (df['Disposals'] + 1)
    df['Score_Involvements'] = (df['Goals'] + df['Goal.Assists'] +
                                df['Marks.Inside.50'] + df['Inside.50s'])
    df['Impact_Score'] = (df['Contested.Possessions'] * 2.85 + df['Hit.Outs'] * 1.51 +
                          df['Marks'] * 3.5 + df['Marks.Inside.50'] * 3.81 +
                          df['Score_Involvements'] * 1.65 + df['Tackles'] * 2.93)

    df['Margin_Bucket'] = df['Margin'].apply(margin_bucket)
    return df


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


# Rank stats whose source can be entirely absent for whole seasons (Wheelo began
# in 2015; ExpVotes only exists for 2026). A game with an all-zero source has no
# real ranking, so its rank/pct/flags are neutralised to NaN — see the guard in
# build_game_rank_features. Scoped to the Wheelo family deliberately: base stats
# (Disposals etc.) are never all-zero, and all-zero-coaches games are a separate,
# pre-existing case handled by the NO_COACHES variant, not touched here.
ZERO_SOURCE_GUARD_STATS = set(RANK_STATS_WHEELO)


def build_game_rank_features(df, rank_stats, fill_missing=False):
    """Per-game rank / percentile / z-score for each stat.

    Within-game only, so no cross-season leakage: these describe how a player
    compared to the 43 others in the game whose votes are being predicted.

    All-zero-source guard (ZERO_SOURCE_GUARD_STATS): when a Wheelo source is
    entirely absent/zero within a game — every pre-2015 game for RatingPoints,
    every pre-2026 game for ExpVotes — the "rank" is a meaningless tie: rank 1
    for all 44 players, pct a game-size proxy (~0.5114), z 0. That asserts every
    player led the game. The raw value and its rank/pct/z are set to NaN instead,
    so XGBoost learns a default direction rather than a false leader. Same defect,
    same fix as the coaches-vote degeneracy.

    fill_missing=True leaves a triplet NaN when its source stat is absent from the
    whole frame — the predict path needs a row for every player and cannot drop
    them, and NaN (not 0) is the correct neutral value here too.
    """
    for stat in rank_stats:
        if stat in df.columns:
            g = df.groupby('Game_ID')[stat]
            df[f'{stat}_game_rank'] = g.rank(ascending=False, method='min')
            df[f'{stat}_game_pct'] = g.rank(pct=True)
            df[f'{stat}_game_z'] = g.transform(lambda x: (x - x.mean()) / (x.std() + 0.001))
            if stat in ZERO_SOURCE_GUARD_STATS:
                dead = g.transform(lambda x: x.abs().max()).fillna(0).eq(0)
                if dead.any():
                    df.loc[dead, [stat, f'{stat}_game_rank',
                                  f'{stat}_game_pct', f'{stat}_game_z']] = np.nan
        elif fill_missing:
            df[f'{stat}_game_rank'] = np.nan
            df[f'{stat}_game_pct'] = np.nan
            df[f'{stat}_game_z'] = np.nan
    return df


def _rank_flag(df, rank_col, threshold):
    """(rank <= threshold) as float, but NaN where the rank itself is NaN — so an
    all-zero-source game does not claim every player as BOG/Top3."""
    r = df[rank_col]
    out = (r <= threshold).astype(float)
    out[r.isna()] = np.nan
    return out


def build_rank_flags(df, include_coaches=True):
    """Top-3 and best-on-ground flags off the game ranks."""
    # Assignment order is deliberate: it reproduces the column order the scripts
    # produced before this module existed, so the output CSVs stay byte-identical
    # across the refactor rather than differing only by column position.
    # rank == 1 and rank <= 1 coincide (ranks are >= 1), so BOG uses threshold 1.
    _cv = include_coaches and 'Coaches_Votes_game_rank' in df.columns
    df['Top3_Disposals'] = _rank_flag(df, 'Disposals_game_rank', 3)
    if _cv:
        df['Top3_Coaches'] = _rank_flag(df, 'Coaches_Votes_game_rank', 3)
    df['Top3_Impact'] = _rank_flag(df, 'Impact_Score_game_rank', 3)
    df['BOG_Disposals'] = _rank_flag(df, 'Disposals_game_rank', 1)
    if _cv:
        df['BOG_Coaches'] = _rank_flag(df, 'Coaches_Votes_game_rank', 1)
    df['BOG_Impact'] = _rank_flag(df, 'Impact_Score_game_rank', 1)
    if 'RatingPoints_game_rank' in df.columns:
        df['BOG_Rating'] = _rank_flag(df, 'RatingPoints_game_rank', 1)
        df['Top3_Rating'] = _rank_flag(df, 'RatingPoints_game_rank', 3)
    return df


def wheelo_derived_features(df):
    """Feature names derived from a Wheelo source and present in df: the base
    Wheelo columns plus the RatingPoints/ExpVotes rank triplets and Rating flags.

    These are legitimately NaN in all-zero-source games (every pre-2015 game, and
    every training game for ExpVotes), so the trainer must keep them OUT of its
    dropna subset or it silently deletes every pre-Wheelo row — turning the fix
    into "train on 2015+ only". Base stats and coaches features stay in dropna."""
    cols = [c for c in WHEELO_COLS if c in df.columns]
    cols += [c for c in ('Rating_Q4_premium', 'Best_quarter_rating') if c in df.columns]
    for s in RANK_STATS_WHEELO:
        cols += [f'{s}_game_rank', f'{s}_game_pct', f'{s}_game_z']
    cols += ['BOG_Rating', 'Top3_Rating']
    return [c for c in dict.fromkeys(cols) if c in df.columns]


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
