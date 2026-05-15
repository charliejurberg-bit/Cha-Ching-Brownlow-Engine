"""
Brownlow Model — Hyperparameter Grid Search
Uses the same feature pipeline as brownlow_model.py v3.0
Uses early stopping to dramatically speed up each combination.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold, ParameterSampler
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import os, warnings, time
warnings.filterwarnings('ignore')

# ── Load data ─────────────────────────────────────────────────────────────────
MAX_HOME_AWAY_ROUND = 24
print("Loading data...", flush=True)
stats = pd.read_csv("fitzroy_stats_2015_2025.csv", low_memory=False)
coaches = pd.read_csv("coaches_votes_2015_2025.csv")
print(f"  Stats: {len(stats):,} rows | Coaches: {len(coaches):,} rows", flush=True)

wheelo_path = "data_wheelo/wheelo_all_seasons.csv"
wheelo = None
if os.path.exists(wheelo_path):
    wheelo = pd.read_csv(wheelo_path, low_memory=False)
    print(f"  Wheelo: {len(wheelo):,} rows", flush=True)

# ── Feature engineering (identical to brownlow_model.py) ──────────────────────
stats['Season'] = pd.to_numeric(stats['Season'], errors='coerce')
stats['Round_num'] = pd.to_numeric(stats['Round'], errors='coerce')
stats['Brownlow.Votes'] = pd.to_numeric(stats['Brownlow.Votes'], errors='coerce').fillna(0)
stats = stats[stats['Round_num'].notna() & (stats['Round_num'] <= MAX_HOME_AWAY_ROUND)].copy()
stats['Player_Name'] = stats['First.name'].str.strip() + ' ' + stats['Surname'].str.strip()
stats['Home.score'] = pd.to_numeric(stats['Home.score'], errors='coerce')
stats['Away.score'] = pd.to_numeric(stats['Away.score'], errors='coerce')

def get_outcome(row):
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a): return pd.Series({'Outcome': 'U', 'Margin': 0})
    margin = h - a if row['Home.Away'] == 'Home' else a - h
    return pd.Series({'Outcome': 'W' if margin > 0 else ('L' if margin < 0 else 'D'), 'Margin': margin})

stats[['Outcome', 'Margin']] = stats.apply(get_outcome, axis=1)
stats['Abs_Margin'] = stats['Margin'].abs()
stats['Is_Win'] = (stats['Outcome'] == 'W').astype(int)
stats['Is_Loss'] = (stats['Outcome'] == 'L').astype(int)

for col in ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
            'Clearances','Contested.Possessions','Uncontested.Possessions',
            'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
            'Rebounds','One.Percenters','Clangers']:
    stats[col] = pd.to_numeric(stats[col], errors='coerce').fillna(0)

stats['Kick_to_HB_ratio'] = stats['Kicks'] / (stats['Handballs'] + 1)
stats['Contested_rate'] = stats['Contested.Possessions'] / (stats['Disposals'] + 1)
stats['Disposal_efficiency'] = (stats['Disposals'] - stats['Clangers']) / (stats['Disposals'] + 1)
stats['Score_Involvements'] = stats['Goals'] + stats['Goal.Assists'] + stats['Marks.Inside.50'] + stats['Inside.50s']
stats['Impact_Score'] = stats['Goals']*3 + stats['Clearances']*1.5 + stats['Contested.Possessions']*1.2 + stats['Kicks']*0.8

def margin_bucket(m):
    if m > 0: return 'close_win' if m <= 15 else ('comfortable_win' if m <= 40 else 'big_win')
    elif m < 0: return 'close_loss' if m >= -15 else ('comfortable_loss' if m >= -40 else 'big_loss')
    return 'draw'

stats['Margin_Bucket'] = stats['Margin'].apply(margin_bucket)
le = LabelEncoder()
all_buckets = ['big_loss','big_win','close_loss','close_win','comfortable_loss','comfortable_win','draw','unknown']
le.fit(all_buckets)
stats['Margin_Bucket_enc'] = le.transform(stats['Margin_Bucket'].fillna('unknown'))

coaches['Season'] = pd.to_numeric(coaches['Season'], errors='coerce')
coaches['Round'] = pd.to_numeric(coaches['Round'], errors='coerce')
coaches['Coaches.Votes'] = pd.to_numeric(coaches['Coaches.Votes'], errors='coerce').fillna(0)
coaches['CV_Player'] = coaches['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
coaches_agg = coaches.groupby(['Season','Round','CV_Player'])['Coaches.Votes'].sum().reset_index()
coaches_agg.columns = ['Season','Round_num','Player_Name','Coaches_Votes']
df = stats.merge(coaches_agg, on=['Season','Round_num','Player_Name'], how='left')
df['Coaches_Votes'] = df['Coaches_Votes'].fillna(0)

WHEELO_FEATURES = []
if wheelo is not None:
    wheelo['Season'] = pd.to_numeric(wheelo['Season'], errors='coerce')
    wheelo['Round'] = pd.to_numeric(wheelo['Round'], errors='coerce')
    wheelo = wheelo[wheelo['Round'] <= MAX_HOME_AWAY_ROUND].copy()
    WHEELO_COLS = ['RatingPoints','ExpVotes','Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4',
                   'Equity_PreClearance','Equity_PostClearance','Equity_Possession','Equity_BallUse',
                   'GroundBallGets','HitoutsToAdvantage','ScoreLaunches','FirstPossessions',
                   'Supercoach','TimeOnGround','DisposalEfficiency','CentreBounceAttendancePercentage']
    for col in WHEELO_COLS:
        if col in wheelo.columns:
            wheelo[col] = pd.to_numeric(wheelo[col], errors='coerce')
    wheelo_merge = wheelo[['Player','Season','Round'] + [c for c in WHEELO_COLS if c in wheelo.columns]].copy()
    wheelo_merge.columns = ['Player_Name','Season','Round_num'] + [c for c in WHEELO_COLS if c in wheelo.columns]
    df = df.merge(wheelo_merge, on=['Player_Name','Season','Round_num'], how='left')
    WHEELO_FEATURES = [c for c in WHEELO_COLS if c in df.columns]
    for col in WHEELO_FEATURES:
        df[col] = df[col].fillna(0)
    if 'Rating_Q1' in df.columns and 'Rating_Q4' in df.columns:
        df['Rating_Q4_premium'] = df['Rating_Q4'] - df[['Rating_Q1','Rating_Q2','Rating_Q3']].mean(axis=1)
        df['Best_quarter_rating'] = df[['Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4']].max(axis=1)
        WHEELO_FEATURES += ['Rating_Q4_premium','Best_quarter_rating']

df['Game_ID'] = (df['Season'].astype(str) + '_' + df['Round_num'].astype(str) + '_' +
                 df['Home.team'].astype(str) + '_' + df['Away.team'].astype(str))

RANK_STATS = ['Disposals','Goals','Contested.Possessions','Clearances',
              'Kicks','Impact_Score','Score_Involvements','Coaches_Votes','Tackles']
if 'RatingPoints' in df.columns:
    RANK_STATS += ['RatingPoints','ExpVotes']

for stat in RANK_STATS:
    if stat in df.columns:
        df[f'{stat}_game_rank'] = df.groupby('Game_ID')[stat].rank(ascending=False, method='min')
        df[f'{stat}_game_pct'] = df.groupby('Game_ID')[stat].rank(pct=True)
        df[f'{stat}_game_z'] = df.groupby('Game_ID')[stat].transform(lambda x: (x - x.mean()) / (x.std() + 0.001))

df['Top3_Disposals'] = (df['Disposals_game_rank'] <= 3).astype(int)
df['Top3_Coaches'] = (df['Coaches_Votes_game_rank'] <= 3).astype(int)
df['Top3_Impact'] = (df['Impact_Score_game_rank'] <= 3).astype(int)
df['BOG_Disposals'] = (df['Disposals_game_rank'] == 1).astype(int)
df['BOG_Coaches'] = (df['Coaches_Votes_game_rank'] == 1).astype(int)
df['BOG_Impact'] = (df['Impact_Score_game_rank'] == 1).astype(int)
if 'RatingPoints_game_rank' in df.columns:
    df['BOG_Rating'] = (df['RatingPoints_game_rank'] == 1).astype(int)
    df['Top3_Rating'] = (df['RatingPoints_game_rank'] <= 3).astype(int)

BASE_FEATURES = ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
                 'Clearances','Contested.Possessions','Uncontested.Possessions',
                 'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
                 'Rebounds','One.Percenters','Clangers','Kick_to_HB_ratio',
                 'Contested_rate','Disposal_efficiency','Score_Involvements',
                 'Impact_Score','Is_Win','Is_Loss','Margin','Abs_Margin',
                 'Coaches_Votes','Season','Margin_Bucket_enc']
RELATIVE_FEATURES = ([f'{s}_game_rank' for s in RANK_STATS if f'{s}_game_rank' in df.columns] +
                     [f'{s}_game_pct' for s in RANK_STATS if f'{s}_game_pct' in df.columns] +
                     [f'{s}_game_z' for s in RANK_STATS if f'{s}_game_z' in df.columns] +
                     ['Top3_Disposals','Top3_Coaches','Top3_Impact','BOG_Disposals','BOG_Coaches','BOG_Impact'])
if 'BOG_Rating' in df.columns:
    RELATIVE_FEATURES += ['BOG_Rating','Top3_Rating']

FEATURES = list(dict.fromkeys(BASE_FEATURES + WHEELO_FEATURES + RELATIVE_FEATURES))
FEATURES = [f for f in FEATURES if f in df.columns]
TARGET = 'Brownlow.Votes'

model_df = df[FEATURES + [TARGET]].dropna(subset=FEATURES + [TARGET]).reset_index(drop=True)
X = model_df[FEATURES].copy()
y = model_df[TARGET].astype(int)
max_s = model_df['Season'].max()
w = (0.85 ** (max_s - model_df['Season'])).values.flatten()
groups = model_df['Season'].values.flatten().astype(int)

print(f"Dataset: {len(model_df):,} rows, {len(FEATURES)} features", flush=True)
print(f"Seasons: {sorted(np.unique(groups))}", flush=True)

# ── Hyperparameter grid ───────────────────────────────────────────────────────
# Use early stopping (n_estimators=800, early_stopping_rounds=30) for speed.
# Effective trees will typically be 100-300 rather than 800, cutting fit time 3-5x.
param_grid = {
    'max_depth':        [4, 5, 6, 7, 8],
    'learning_rate':    [0.02, 0.03, 0.05, 0.08, 0.1],
    'subsample':        [0.65, 0.75, 0.8, 0.85, 0.9],
    'colsample_bytree': [0.65, 0.75, 0.8, 0.85, 0.9],
    'min_child_weight': [1, 3, 5, 7],
    'gamma':            [0, 0.05, 0.1, 0.2],
    'reg_alpha':        [0, 0.05, 0.1, 0.2],
    'reg_lambda':       [0.5, 1.0, 1.5, 2.0],
}

N_ITER = 40
rng = np.random.RandomState(42)
sampler = list(ParameterSampler(param_grid, n_iter=N_ITER, random_state=rng))

print(f"\nRunning {N_ITER} random combos × 5-fold GroupKFold (early stopping after 30 rounds)...", flush=True)
print(f"Baseline (v3.0): max_depth=6 lr=0.05 subsample=0.8 colsample=0.8 mcw=1\n", flush=True)

gkf = GroupKFold(n_splits=5)
results = []

for i, params in enumerate(sampler):
    t0 = time.time()
    model = xgb.XGBClassifier(
        n_estimators=800,
        early_stopping_rounds=30,
        **params,
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1,
    )
    fold_maes = []
    best_iters = []
    for train_idx, val_idx in gkf.split(X, y, groups):
        model.fit(X.iloc[train_idx], y.iloc[train_idx],
                  sample_weight=w[train_idx],
                  eval_set=[(X.iloc[val_idx], y.iloc[val_idx])],
                  verbose=False)
        fold_maes.append(mean_absolute_error(y.iloc[val_idx], model.predict(X.iloc[val_idx])))
        best_iters.append(model.best_iteration)
    mean_mae = np.mean(fold_maes)
    avg_trees = int(np.mean(best_iters))
    elapsed = time.time() - t0
    results.append({'params': params, 'mae': mean_mae, 'fold_maes': fold_maes, 'avg_trees': avg_trees})
    print(f"  [{i+1:2d}/{N_ITER}] MAE={mean_mae:.4f}  {elapsed:.0f}s  trees~{avg_trees}  "
          f"depth={params['max_depth']} lr={params['learning_rate']:.3f} "
          f"sub={params['subsample']} col={params['colsample_bytree']} "
          f"mcw={params['min_child_weight']}",
          flush=True)

# ── Results ───────────────────────────────────────────────────────────────────
results.sort(key=lambda r: r['mae'])
best = results[0]

print("\n" + "="*70, flush=True)
print(f"BEST MAE: {best['mae']:.4f}  (fold MAEs: {[f'{m:.4f}' for m in best['fold_maes']]})", flush=True)
print(f"Avg trees used: {best['avg_trees']}", flush=True)
print(f"\nBest hyperparameters:", flush=True)
for k, v in sorted(best['params'].items()):
    print(f"  {k:20s}: {v}", flush=True)

print("\nTop 10 combinations:", flush=True)
print(f"  {'Rank':>4}  {'MAE':>7}  {'Trees':>5}  {'depth':>5}  {'lr':>6}  {'sub':>5}  {'col':>5}  {'mcw':>3}", flush=True)
for rank, r in enumerate(results[:10], 1):
    p = r['params']
    print(f"  {rank:4d}  {r['mae']:7.4f}  {r['avg_trees']:5d}  {p['max_depth']:5d}  "
          f"{p['learning_rate']:6.3f}  {p['subsample']:5.2f}  {p['colsample_bytree']:5.2f}  "
          f"{p['min_child_weight']:3d}",
          flush=True)

os.makedirs("predictions", exist_ok=True)
rows = [{'mae': r['mae'], 'avg_trees': r['avg_trees'], **r['params']} for r in results]
pd.DataFrame(rows).sort_values('mae').to_csv("predictions/grid_search_results.csv", index=False)
print("\nFull results saved to predictions/grid_search_results.csv", flush=True)
