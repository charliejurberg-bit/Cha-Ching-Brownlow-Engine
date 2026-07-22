"""
Walk-forward back-test for Brownlow Medal Prediction Engine.
For each season 2019-2025, trains on all prior seasons then predicts that season.
Same hyperparameters, Impact Score formula, feature pipeline, and equal season
weighting as brownlow_model.py.
Saves: predictions/backtest_results.csv
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import os, warnings
import features as feat
from brownlow_medallists import get_medallists
warnings.filterwarnings('ignore')

os.makedirs("predictions", exist_ok=True)

print("Loading data...")
stats_file   = "fitzroy_stats_all.csv"   if os.path.exists("fitzroy_stats_all.csv")   else "fitzroy_stats_2015_2025.csv"
coaches_file = "coaches_votes_all.csv"   if os.path.exists("coaches_votes_all.csv")   else "coaches_votes_2015_2025.csv"
print(f"  Stats file:   {stats_file}")
print(f"  Coaches file: {coaches_file}")
stats   = pd.read_csv(stats_file,   low_memory=False)
coaches = pd.read_csv(coaches_file, low_memory=False)
print(f"  Stats: {len(stats):,} rows | Coaches: {len(coaches):,} rows")

wheelo_path = "data_wheelo/wheelo_all_seasons.csv"
wheelo = None
if os.path.exists(wheelo_path):
    wheelo = pd.read_csv(wheelo_path, low_memory=False)
    print(f"  Wheelo: {len(wheelo):,} rows")
else:
    print("  Wheelo: not found — running without rating points")

# ── Data cleaning (identical to brownlow_model.py) ────────────
print("Cleaning stats...")
stats['Season'] = pd.to_numeric(stats['Season'], errors='coerce')
stats['Round_num'] = pd.to_numeric(stats['Round'], errors='coerce')
stats['Brownlow.Votes'] = pd.to_numeric(stats['Brownlow.Votes'], errors='coerce').fillna(0)
stats = stats[stats['Round_num'].notna()].copy()

stats['Player_Name'] = stats['First.name'].str.strip() + ' ' + stats['Surname'].str.strip()
stats['Home.score'] = pd.to_numeric(stats['Home.score'], errors='coerce')
stats['Away.score'] = pd.to_numeric(stats['Away.score'], errors='coerce')

stats = feat.add_row_stats(stats)
le = LabelEncoder()
le.fit(feat.MARGIN_BUCKETS)
stats['Margin_Bucket_enc'] = le.transform(stats['Margin_Bucket'].fillna('unknown'))

# ── Merge coaches votes ───────────────────────────────────────
print("Merging coaches votes...")
coaches['Season'] = pd.to_numeric(coaches['Season'], errors='coerce')
coaches['Round'] = pd.to_numeric(coaches['Round'], errors='coerce')
coaches['Coaches.Votes'] = pd.to_numeric(coaches['Coaches.Votes'], errors='coerce').fillna(0)
TEAM_ABBREV = {
    'ADEL': 'Adelaide', 'BL': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FRE': 'Fremantle',
    'GCFC': 'Gold Coast', 'GEEL': 'Geelong', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WB': 'Western Bulldogs', 'WCE': 'West Coast',
}
coaches['CV_Player'] = coaches['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
coaches['CV_Team'] = coaches['Player.Name'].str.extract(r'\(([^)]+)\)')[0].map(TEAM_ABBREV)
coaches_agg = coaches.groupby(['Season','Round','CV_Player','CV_Team'])['Coaches.Votes'].sum().reset_index()
coaches_agg.columns = ['Season','Round_num','Player_Name','Playing.for','Coaches_Votes']
df = stats.merge(coaches_agg, on=['Season','Round_num','Player_Name','Playing.for'], how='left')
df['Coaches_Votes'] = df['Coaches_Votes'].fillna(0)

# ── Merge Wheelo data ─────────────────────────────────────────
WHEELO_FEATURES = []
if wheelo is not None:
    print("Merging Wheelo data...")
    wheelo['Season'] = pd.to_numeric(wheelo['Season'], errors='coerce')
    wheelo['Round'] = pd.to_numeric(wheelo['Round'], errors='coerce')
    wheelo = wheelo[wheelo['Round'].notna()].copy()
    WHEELO_COLS = ['RatingPoints','ExpVotes','Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4',
                   'Equity_PreClearance','Equity_PostClearance','Equity_Possession','Equity_BallUse',
                   'GroundBallGets','HitoutsToAdvantage','ScoreLaunches','FirstPossessions',
                   'Supercoach','TimeOnGround','DisposalEfficiency','CentreBounceAttendancePercentage']
    for col in WHEELO_COLS:
        if col in wheelo.columns:
            wheelo[col] = pd.to_numeric(wheelo[col], errors='coerce')
    wheelo['Team'] = wheelo['Team'].replace({'Brisbane': 'Brisbane Lions'})
    wheelo_merge = wheelo[['Player','Team','Season','Round'] +
                           [c for c in WHEELO_COLS if c in wheelo.columns]].copy()
    wheelo_merge.columns = (['Player_Name','Playing.for','Season','Round_num'] +
                            [c for c in WHEELO_COLS if c in wheelo.columns])
    df = df.merge(wheelo_merge, on=['Player_Name','Playing.for','Season','Round_num'], how='left')
    WHEELO_FEATURES = [c for c in WHEELO_COLS if c in df.columns]
    for col in WHEELO_FEATURES:
        df[col] = df[col].fillna(0)
    if 'Rating_Q1' in df.columns and 'Rating_Q4' in df.columns:
        df['Rating_Q4_premium'] = df['Rating_Q4'] - df[['Rating_Q1','Rating_Q2','Rating_Q3']].mean(axis=1)
        df['Best_quarter_rating'] = df[['Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4']].max(axis=1)
        WHEELO_FEATURES += ['Rating_Q4_premium','Best_quarter_rating']
    print(f"  Wheelo features: {len(WHEELO_FEATURES)}")

# ── Relative game features (within-game only — no cross-season leakage) ─────
print("Building relative game features...")
df['Game_ID'] = (df['Season'].astype(str) + '_' + df['Round_num'].astype(str) + '_' +
                 df['Home.team'].astype(str) + '_' + df['Away.team'].astype(str))

RANK_STATS = feat.rank_stats_for(df)
df = feat.build_game_rank_features(df, RANK_STATS)
df = feat.build_rank_flags(df)

# ── Form and momentum ─────────────────────────────────────────
print("Building form and momentum features...")
df = df.sort_values(['Season', 'Player_Name', 'Round_num']).reset_index(drop=True)
df = feat.build_form_features(df, ['Season', 'Player_Name'])
FORM_FEATURES = feat.form_feature_names(df)

# ── Feature set (shared with training via features.py) ────────
FEATURES = feat.assemble_features(df, RANK_STATS, WHEELO_FEATURES, FORM_FEATURES)
FEATURES_NOCV = feat.assemble_features(
    df, RANK_STATS, WHEELO_FEATURES, FORM_FEATURES, include_coaches=False)

TARGET = 'Brownlow.Votes'

# Home.team / Away.team / ID are carried through purely so the per-game output
# below can be keyed and joined. They are NOT features: the model only ever sees
# train[_FEATS] / test[_FEATS], and _dropna_subset is built from FEATURES, so
# widening this projection cannot change which rows survive or how the model is
# fitted. brownlow_model.py already carries ID the same way via its _id_cols.
_passthrough = [TARGET, 'Player_Name', 'Playing.for', 'Round_num', 'Season',
                'Home.team', 'Away.team', 'ID']
extra_cols = [c for c in _passthrough
              if c not in FEATURES and c in df.columns]
# Wheelo- and coaches-derived features are NaN in all-zero-source games by design
# (see features.build_game_rank_features); excluding them from dropna keeps those
# rows, matching brownlow_model.py so the two measure the same training set.
_excluded = set(feat.wheelo_derived_features(df)) | set(feat.COACHES_FEATURES)
_dropna_subset = [f for f in FEATURES if f not in _excluded] + [TARGET]
model_df = (df[FEATURES + extra_cols]
            .dropna(subset=_dropna_subset)
            .reset_index(drop=True))

print(f"Full dataset: {len(model_df):,} rows | {len(FEATURES)} features")

# ── Walk-forward back-test ────────────────────────────────────
# Start from the second available season so there is always at least one training year.
# With extended data this becomes ~2007; with the original 2015-2025 file it becomes 2016.
_all_seasons   = sorted(model_df['Season'].unique().astype(int).tolist())
BACKTEST_SEASONS = _all_seasons[1:]  # skip first season (nothing to train on before it)
print(f"Backtest seasons: {BACKTEST_SEASONS}")

# Which feature set this pass measures. FULL is the shipping model; NOCV is the
# count-night variant, run over the SAME folds so the two are comparable.
_PASS = os.environ.get('BACKTEST_FEATURES', 'FULL').upper()
_FEATS = FEATURES_NOCV if _PASS == 'NOCV' else FEATURES
_SUFFIX = '_nocv' if _PASS == 'NOCV' else ''
print(f"Feature set: {_PASS} ({len(_FEATS)} features)")

# Column order of the per-game output. Written in addition to the existing
# aggregate outputs, which are unchanged.
_GAME_COLS = ['Season', 'Round_num', 'Player_Name', 'Playing.for',
              'Home.team', 'Away.team', 'Exp_Votes', 'P_3', 'P_2', 'P_1',
              'Poll_Prob', 'Brownlow.Votes', 'ID']

all_results = []
_mae_rows = []
_game_rows = []   # per-player-game predictions, one block per test season

for target_season in BACKTEST_SEASONS:
    train = model_df[model_df['Season'] < target_season].copy()
    test  = model_df[model_df['Season'] == target_season].copy()

    train_seasons = sorted(train['Season'].unique().astype(int).tolist())
    print(f"\n--- {target_season} | Train: {train_seasons} | Test rows: {len(test):,} ---")

    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=7, learning_rate=0.05,
        subsample=0.85, colsample_bytree=0.8, min_child_weight=7,
        gamma=0.1, reg_alpha=0.2, reg_lambda=2.0,
        eval_metric='mlogloss', random_state=42, n_jobs=-1,
    )
    # Recency weighting, matching brownlow_model.py: the last five rounds of each
    # training season count double. This was np.ones, which made backtest MAE
    # measure a differently-fitted model from the one that ships and left the
    # figure not comparable to the CV baseline.
    _tr_max = train.groupby('Season')['Round_num'].transform('max')
    _w = np.where(train['Round_num'] >= _tr_max - 4, 2.0, 1.0)
    model.fit(train[_FEATS], train[TARGET].astype(int),
              sample_weight=_w, verbose=False)

    proba  = model.predict_proba(test[_FEATS])
    classes = list(model.classes_)
    test = test.copy()
    test['P_1'] = proba[:, classes.index(1)] if 1 in classes else 0.0
    test['P_2'] = proba[:, classes.index(2)] if 2 in classes else 0.0
    test['P_3'] = proba[:, classes.index(3)] if 3 in classes else 0.0
    test['Exp_Votes'] = test['P_1'] * 1 + test['P_2'] * 2 + test['P_3'] * 3
    test['Poll_Prob'] = test['P_1'] + test['P_2'] + test['P_3']

    # Capture the per-game frame BEFORE the player-season groupby below throws the
    # per-game structure away. These rows are genuinely out-of-sample: target_season
    # was never in this fold's training window.
    _game_rows.append(test[[c for c in _GAME_COLS if c in test.columns]].copy())

    # Per-game MAE on the same scale as the CV figure: predicted class vs actual.
    _pred_cls = model.predict(test[_FEATS])
    _mae = float(np.abs(test[TARGET].astype(int).values - _pred_cls).mean())
    _mae_rows.append({'Season': target_season, 'MAE': _mae, 'Rows': len(test)})
    print(f"  MAE: {_mae:.4f}")

    season_agg = test.groupby('Player_Name').agg(
        Team=('Playing.for', 'last'),
        Actual_Votes=(TARGET, 'sum'),
        Predicted_Votes=('Exp_Votes', 'sum'),
    ).reset_index()
    season_agg['Season'] = target_season
    season_agg['Rank_Predicted'] = (season_agg['Predicted_Votes']
                                    .rank(ascending=False, method='min').astype(int))
    season_agg['Rank_Actual'] = (season_agg['Actual_Votes']
                                 .rank(ascending=False, method='min').astype(int))
    all_results.append(season_agg)

    # Actual winner comes from the canonical medallist list, matched by name AND team
    # (a max-vote derivation collides same-name players — the two Josh Kennedys etc.).
    medallists = get_medallists(target_season)
    winner_disp = ' & '.join(nm for nm, _tm in medallists) or '?'
    winner_ranks = []
    for _nm, _tm in medallists:
        _row = season_agg[(season_agg['Player_Name'] == _nm) & (season_agg['Team'] == _tm)]
        if not _row.empty:
            winner_ranks.append(int(_row['Rank_Predicted'].iloc[0]))
    winner_pred_rank = min(winner_ranks) if winner_ranks else None
    in_top3 = any(r <= 3 for r in winner_ranks)
    _wpr = winner_pred_rank if winner_pred_rank is not None else '—'
    print(f"  Actual winner: {winner_disp} | Predicted rank: {_wpr} | In top 3: {in_top3}")

# ── Save results ──────────────────────────────────────────────
results = pd.concat(all_results, ignore_index=True)
results = results[['Season','Player_Name','Team','Actual_Votes','Predicted_Votes',
                   'Rank_Predicted','Rank_Actual']]
results.columns = ['Season','Player','Team','Actual_Votes','Predicted_Votes',
                   'Rank_Predicted','Rank_Actual']
results['Predicted_Votes'] = results['Predicted_Votes'].round(3)

out = f"predictions/backtest_results{_SUFFIX}.csv"
results.to_csv(out, index=False)

# ── Per-game out-of-sample predictions ────────────────────────
# One row per player-game across every walk-forward test season. This is the
# honest source for per-game accuracy: predictions/game_level_*.csv is written
# by brownlow_model.py from a model refit on ALL seasons, so it is in-sample.
_games = pd.concat(_game_rows, ignore_index=True)
_games = _games[[c for c in _GAME_COLS if c in _games.columns]]
_game_out = f"predictions/backtest_game_level{_SUFFIX}.csv"
_games.to_csv(_game_out, index=False)
print(f"Per-game out-of-sample rows: {len(_games):,} -> {_game_out}")
_missing = [c for c in _GAME_COLS if c not in _games.columns]
if _missing:
    print(f"  WARNING: per-game output missing columns: {_missing}")

# ── Headline accuracy ─────────────────────────────────────────
# The figures the app quotes publicly, recomputed every run rather than written
# down anywhere — a hardcoded claim is how the pre-audit 86% outlived the model
# it described.
_mae_df = pd.DataFrame(_mae_rows)
_top10 = []
_med_top3 = []
for _s in BACKTEST_SEASONS:
    _sr = results[results['Season'] == _s]
    # Top-10 accuracy: how much of the actual top 10 the model put in its top 10.
    _act10 = set(_sr.nsmallest(10, 'Rank_Actual')['Player'])
    _prd10 = set(_sr.nsmallest(10, 'Rank_Predicted')['Player'])
    _top10.append({'Season': _s, 'Hits': len(_act10 & _prd10), 'Pct': len(_act10 & _prd10) / 10.0})
    _meds = get_medallists(_s)
    _rk = [int(_sr[(_sr['Player'] == _n) & (_sr['Team'] == _t)]['Rank_Predicted'].iloc[0])
           for _n, _t in _meds
           if not _sr[(_sr['Player'] == _n) & (_sr['Team'] == _t)].empty]
    _med_top3.append({'Season': _s, 'BestRank': min(_rk) if _rk else None,
                      'InTop3': bool(_rk) and min(_rk) <= 3})

_t10 = pd.DataFrame(_top10)
_m3 = pd.DataFrame(_med_top3)
_summary = _mae_df.merge(_t10[['Season', 'Hits', 'Pct']], on='Season') \
                  .merge(_m3[['Season', 'BestRank', 'InTop3']], on='Season')
_summary.to_csv(f"predictions/backtest_summary{_SUFFIX}.csv", index=False)

print(f"\n{'='*62}")
print(f"HEADLINE ACCURACY — {_PASS} feature set ({len(_FEATS)} features)")
print('='*62)
print(f"{'Season':>7}{'MAE':>9}{'Top10':>8}{'Medallist rank':>17}{'In top 3':>10}")
print('-'*62)
for _, r in _summary.iterrows():
    _br = int(r['BestRank']) if pd.notna(r['BestRank']) else '-'
    print(f"{int(r['Season']):>7}{r['MAE']:>9.4f}{int(r['Hits']):>6}/10"
          f"{str(_br):>17}{('yes' if r['InTop3'] else 'no'):>10}")
print('-'*62)
print(f"  Overall MAE              : {_mae_df['MAE'].mean():.4f}")
print(f"  Top-10 accuracy          : {_summary['Pct'].mean()*100:.1f}%")
print(f"  Medallist in top 3       : {_summary['InTop3'].mean()*100:.1f}% "
      f"({int(_summary['InTop3'].sum())}/{len(_summary)} seasons)")
print(f"  Medallist median rank    : {_summary['BestRank'].median():.1f}")
print(f"\nDone. {len(results):,} player-seasons saved -> {out}")
