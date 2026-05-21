"""
Time Decay Search
Tests decay rates from 0.70 to 0.98 (step 0.02) with the best Impact Score formula
and optimised hyperparameters. Saves results to predictions/time_decay_results.csv.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import os, warnings
warnings.filterwarnings('ignore')

os.makedirs("predictions", exist_ok=True)

RESULTS_PATH = "predictions/time_decay_results.csv"
N_SPLITS = 5
DECAY_RATES = np.round(np.arange(0.70, 0.99, 0.02), 4).tolist() + [1.0]

# Best Impact Score formula from impact_score_search
BEST_FORMULA = {
    'Contested.Possessions': 2.85,
    'Hit.Outs':              1.51,
    'Marks':                 3.50,
    'Marks.Inside.50':       3.81,
    'Score_Involvements':    1.65,
    'Tackles':               2.93,
}

# Optimised hyperparameters
XGB_PARAMS = dict(
    max_depth=7, learning_rate=0.05, subsample=0.85,
    colsample_bytree=0.8, min_child_weight=7, gamma=0.1,
    reg_alpha=0.2, reg_lambda=2.0, n_estimators=300,
    eval_metric='mlogloss', random_state=42, n_jobs=-1,
)

# ── Load data ──────────────────────────────────────────────────
print("Loading data...")
stats = pd.read_csv("fitzroy_stats_2015_2025.csv", low_memory=False)
coaches = pd.read_csv("coaches_votes_2015_2025.csv")
print(f"  Stats: {len(stats):,} rows | Coaches: {len(coaches):,} rows")

wheelo_path = "data_wheelo/wheelo_all_seasons.csv"
wheelo = None
if os.path.exists(wheelo_path):
    wheelo = pd.read_csv(wheelo_path, low_memory=False)
    print(f"  Wheelo: {len(wheelo):,} rows")
else:
    print("  Wheelo: not found — running without rating points")

# ── Clean stats ────────────────────────────────────────────────
print("\nCleaning data...")
stats['Season'] = pd.to_numeric(stats['Season'], errors='coerce')
stats['Round_num'] = pd.to_numeric(stats['Round'], errors='coerce')
stats['Brownlow.Votes'] = pd.to_numeric(stats['Brownlow.Votes'], errors='coerce').fillna(0)

before = len(stats)
stats = stats[stats['Round_num'].notna()].copy()
print(f"  Filtered finals: {before:,} -> {len(stats):,} rows ({before - len(stats):,} removed)")

stats['Player_Name'] = stats['First.name'].str.strip() + ' ' + stats['Surname'].str.strip()
stats['Home.score'] = pd.to_numeric(stats['Home.score'], errors='coerce')
stats['Away.score'] = pd.to_numeric(stats['Away.score'], errors='coerce')

def get_outcome(row):
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a):
        return pd.Series({'Outcome': 'U', 'Margin': 0})
    margin = h - a if row['Home.Away'] == 'Home' else a - h
    return pd.Series({'Outcome': 'W' if margin > 0 else ('L' if margin < 0 else 'D'), 'Margin': margin})

stats[['Outcome', 'Margin']] = stats.apply(get_outcome, axis=1)
stats['Abs_Margin'] = stats['Margin'].abs()
stats['Is_Win'] = (stats['Outcome'] == 'W').astype(int)
stats['Is_Loss'] = (stats['Outcome'] == 'L').astype(int)

for col in ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles', 'Hit.Outs',
            'Clearances', 'Contested.Possessions', 'Uncontested.Possessions',
            'Contested.Marks', 'Marks.Inside.50', 'Goal.Assists', 'Inside.50s',
            'Rebounds', 'One.Percenters', 'Clangers']:
    stats[col] = pd.to_numeric(stats[col], errors='coerce').fillna(0)

stats['Kick_to_HB_ratio'] = stats['Kicks'] / (stats['Handballs'] + 1)
stats['Contested_rate'] = stats['Contested.Possessions'] / (stats['Disposals'] + 1)
stats['Disposal_efficiency'] = (stats['Disposals'] - stats['Clangers']) / (stats['Disposals'] + 1)
stats['Score_Involvements'] = (stats['Goals'] + stats['Goal.Assists'] +
                               stats['Marks.Inside.50'] + stats['Inside.50s'])

def margin_bucket(m):
    if m > 0:
        return 'close_win' if m <= 15 else ('comfortable_win' if m <= 40 else 'big_win')
    elif m < 0:
        return 'close_loss' if m >= -15 else ('comfortable_loss' if m >= -40 else 'big_loss')
    return 'draw'

stats['Margin_Bucket'] = stats['Margin'].apply(margin_bucket)
le = LabelEncoder()
all_buckets = ['big_loss', 'big_win', 'close_loss', 'close_win',
               'comfortable_loss', 'comfortable_win', 'draw', 'unknown']
le.fit(all_buckets)
stats['Margin_Bucket_enc'] = le.transform(stats['Margin_Bucket'].fillna('unknown'))

# ── Merge coaches votes ────────────────────────────────────────
print("Merging coaches votes...")
coaches['Season'] = pd.to_numeric(coaches['Season'], errors='coerce')
coaches['Round'] = pd.to_numeric(coaches['Round'], errors='coerce')
coaches['Coaches.Votes'] = pd.to_numeric(coaches['Coaches.Votes'], errors='coerce').fillna(0)
TEAM_ABBREV = {
    'ADEL': 'Adelaide',       'BL': 'Brisbane Lions',     'CARL': 'Carlton',
    'COLL': 'Collingwood',    'ESS': 'Essendon',          'FRE': 'Fremantle',
    'GCFC': 'Gold Coast',     'GEEL': 'Geelong',          'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn',        'MELB': 'Melbourne',        'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide',  'RICH': 'Richmond',         'STK': 'St Kilda',
    'SYD': 'Sydney',          'WB': 'Western Bulldogs',   'WCE': 'West Coast',
}
coaches['CV_Player'] = coaches['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
coaches['CV_Team'] = coaches['Player.Name'].str.extract(r'\(([^)]+)\)')[0].map(TEAM_ABBREV)
coaches_agg = (coaches.groupby(['Season', 'Round', 'CV_Player', 'CV_Team'])['Coaches.Votes']
               .sum().reset_index())
coaches_agg.columns = ['Season', 'Round_num', 'Player_Name', 'Playing.for', 'Coaches_Votes']
df = stats.merge(coaches_agg, on=['Season', 'Round_num', 'Player_Name', 'Playing.for'], how='left')
df['Coaches_Votes'] = df['Coaches_Votes'].fillna(0)

# ── Merge Wheelo data ──────────────────────────────────────────
WHEELO_FEATURES = []
if wheelo is not None:
    print("Merging Wheelo data...")
    wheelo['Season'] = pd.to_numeric(wheelo['Season'], errors='coerce')
    wheelo['Round'] = pd.to_numeric(wheelo['Round'], errors='coerce')
    wheelo = wheelo[wheelo['Round'].notna()].copy()

    WHEELO_COLS = ['RatingPoints', 'ExpVotes', 'Rating_Q1', 'Rating_Q2', 'Rating_Q3', 'Rating_Q4',
                   'Equity_PreClearance', 'Equity_PostClearance', 'Equity_Possession', 'Equity_BallUse',
                   'GroundBallGets', 'HitoutsToAdvantage', 'ScoreLaunches', 'FirstPossessions',
                   'Supercoach', 'TimeOnGround', 'DisposalEfficiency', 'CentreBounceAttendancePercentage']
    for col in WHEELO_COLS:
        if col in wheelo.columns:
            wheelo[col] = pd.to_numeric(wheelo[col], errors='coerce')
    wheelo['Team'] = wheelo['Team'].replace({'Brisbane': 'Brisbane Lions'})
    wheelo_merge = wheelo[['Player', 'Team', 'Season', 'Round'] +
                          [c for c in WHEELO_COLS if c in wheelo.columns]].copy()
    wheelo_merge.columns = (['Player_Name', 'Playing.for', 'Season', 'Round_num'] +
                            [c for c in WHEELO_COLS if c in wheelo.columns])
    df = df.merge(wheelo_merge, on=['Player_Name', 'Playing.for', 'Season', 'Round_num'], how='left')
    WHEELO_FEATURES = [c for c in WHEELO_COLS if c in df.columns]
    for col in WHEELO_FEATURES:
        df[col] = df[col].fillna(0)
    if 'Rating_Q1' in df.columns and 'Rating_Q4' in df.columns:
        df['Rating_Q4_premium'] = df['Rating_Q4'] - df[['Rating_Q1', 'Rating_Q2', 'Rating_Q3']].mean(axis=1)
        df['Best_quarter_rating'] = df[['Rating_Q1', 'Rating_Q2', 'Rating_Q3', 'Rating_Q4']].max(axis=1)
        WHEELO_FEATURES += ['Rating_Q4_premium', 'Best_quarter_rating']
    print(f"  Wheelo features: {len(WHEELO_FEATURES)}")

# ── Game_ID ────────────────────────────────────────────────────
df['Game_ID'] = (df['Season'].astype(str) + '_' + df['Round_num'].astype(str) + '_' +
                 df['Home.team'].astype(str) + '_' + df['Away.team'].astype(str))

# ── Impact Score (fixed best formula) ─────────────────────────
print("Computing best Impact Score formula...")
df['Impact_Score'] = sum(
    coef * df[col].values for col, coef in BEST_FORMULA.items() if col in df.columns
)

# ── Relative features ──────────────────────────────────────────
print("Building relative features...")
RANK_STATS_BASE = ['Disposals', 'Goals', 'Contested.Possessions', 'Clearances',
                   'Kicks', 'Score_Involvements', 'Coaches_Votes', 'Tackles', 'Impact_Score']
if 'RatingPoints' in df.columns:
    RANK_STATS_BASE += ['RatingPoints', 'ExpVotes']

for stat in RANK_STATS_BASE:
    if stat in df.columns:
        df[f'{stat}_game_rank'] = df.groupby('Game_ID')[stat].rank(ascending=False, method='min')
        df[f'{stat}_game_pct'] = df.groupby('Game_ID')[stat].rank(pct=True)
        df[f'{stat}_game_z'] = df.groupby('Game_ID')[stat].transform(
            lambda x: (x - x.mean()) / (x.std() + 0.001))

df['Top3_Disposals'] = (df['Disposals_game_rank'] <= 3).astype(int)
df['Top3_Coaches'] = (df['Coaches_Votes_game_rank'] <= 3).astype(int)
df['Top3_Impact'] = (df['Impact_Score_game_rank'] <= 3).astype(int)
df['BOG_Disposals'] = (df['Disposals_game_rank'] == 1).astype(int)
df['BOG_Coaches'] = (df['Coaches_Votes_game_rank'] == 1).astype(int)
df['BOG_Impact'] = (df['Impact_Score_game_rank'] == 1).astype(int)
if 'RatingPoints_game_rank' in df.columns:
    df['BOG_Rating'] = (df['RatingPoints_game_rank'] == 1).astype(int)
    df['Top3_Rating'] = (df['RatingPoints_game_rank'] <= 3).astype(int)

# ── Feature lists ──────────────────────────────────────────────
TARGET = 'Brownlow.Votes'

BASE_FEATURES = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles', 'Hit.Outs',
                 'Clearances', 'Contested.Possessions', 'Uncontested.Possessions',
                 'Contested.Marks', 'Marks.Inside.50', 'Goal.Assists', 'Inside.50s',
                 'Rebounds', 'One.Percenters', 'Clangers', 'Kick_to_HB_ratio',
                 'Contested_rate', 'Disposal_efficiency', 'Score_Involvements',
                 'Impact_Score', 'Is_Win', 'Is_Loss', 'Margin', 'Abs_Margin',
                 'Coaches_Votes', 'Season', 'Margin_Bucket_enc']

REL_FEATURES = ([f'{s}_game_rank' for s in RANK_STATS_BASE if f'{s}_game_rank' in df.columns] +
                [f'{s}_game_pct'  for s in RANK_STATS_BASE if f'{s}_game_pct'  in df.columns] +
                [f'{s}_game_z'    for s in RANK_STATS_BASE if f'{s}_game_z'    in df.columns] +
                ['Top3_Disposals', 'Top3_Coaches', 'Top3_Impact',
                 'BOG_Disposals', 'BOG_Coaches', 'BOG_Impact'])
if 'BOG_Rating' in df.columns:
    REL_FEATURES += ['BOG_Rating', 'Top3_Rating']

FEATURES = list(dict.fromkeys(BASE_FEATURES + WHEELO_FEATURES + REL_FEATURES))
FEATURES = [f for f in FEATURES if f in df.columns]

# ── Prepare clean dataset ──────────────────────────────────────
keep_cols = list(dict.fromkeys(FEATURES + [TARGET, 'Season']))
df_clean = (df[keep_cols]
            .dropna(subset=FEATURES + [TARGET])
            .copy().reset_index(drop=True))

X = df_clean[FEATURES].values
y = df_clean[TARGET].astype(int)
seasons = df_clean['Season'].values.flatten().astype(float)
max_s = seasons.max()
groups = seasons.astype(int)

gkf = GroupKFold(n_splits=N_SPLITS)

print(f"\nDataset: {len(df_clean):,} rows | {len(FEATURES)} features")
print(f"Seasons: {sorted(np.unique(groups))}")
print(f"\nDecay rates to test: {DECAY_RATES}")
print(f"Total trials: {len(DECAY_RATES)}\n")

# ── Load existing results (resume support) ─────────────────────
results = []
tested_rates = set()
if os.path.exists(RESULTS_PATH):
    existing = pd.read_csv(RESULTS_PATH)
    results = existing.to_dict('records')
    tested_rates = set(round(r['decay_rate'], 4) for r in results)
    print(f"Resuming: {len(results)} results already saved")

# ── Search ─────────────────────────────────────────────────────
print(f"{'Decay':>7}  {'MAE':>8}  {'Fold MAEs'}")
print("-" * 55)

for decay in DECAY_RATES:
    decay = round(decay, 4)
    if decay in tested_rates:
        print(f"  {decay:.2f}   [already done — skipping]")
        continue

    w = (decay ** (max_s - seasons))

    fold_maes = []
    model = xgb.XGBClassifier(**XGB_PARAMS)
    for train_idx, val_idx in gkf.split(X, y, groups):
        model.fit(X[train_idx], y.iloc[train_idx], sample_weight=w[train_idx],
                  eval_set=[(X[val_idx], y.iloc[val_idx])], verbose=False)
        fold_maes.append(mean_absolute_error(y.iloc[val_idx], model.predict(X[val_idx])))

    mean_mae = float(np.mean(fold_maes))
    fold_str = '  '.join(f'{m:.4f}' for m in fold_maes)

    result = {
        'decay_rate': decay,
        'mae': round(mean_mae, 6),
        'fold_mae_1': round(fold_maes[0], 6),
        'fold_mae_2': round(fold_maes[1], 6),
        'fold_mae_3': round(fold_maes[2], 6),
        'fold_mae_4': round(fold_maes[3], 6),
        'fold_mae_5': round(fold_maes[4], 6),
    }
    results.append(result)
    tested_rates.add(decay)
    pd.DataFrame(results).sort_values('decay_rate').to_csv(RESULTS_PATH, index=False)

    best_so_far = min(r['mae'] for r in results)
    marker = ' *** BEST ***' if mean_mae == best_so_far else ''
    print(f"  {decay:.2f}   {mean_mae:.6f}   [{fold_str}]{marker}")

# ── Print final results ────────────────────────────────────────
results_df = pd.DataFrame(results).sort_values('mae').reset_index(drop=True)
best = results_df.iloc[0]

print(f"\n{'='*55}")
print(f"TIME DECAY SEARCH COMPLETE — {len(DECAY_RATES)} rates tested")
print(f"{'='*55}")
print(f"Best decay rate :  {best['decay_rate']:.2f}")
print(f"Best MAE        :  {best['mae']:.6f}")
print(f"\nAll results (sorted by MAE):")
print(results_df[['decay_rate', 'mae']].to_string(index=False))
print(f"\nFull results saved to {RESULTS_PATH}")
