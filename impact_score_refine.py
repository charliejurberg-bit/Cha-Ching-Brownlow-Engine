"""
Impact Score Formula — Refined Search
300 random combinations, 4-10 stats from the full pool (18 stats).
Best 6 stats use ±50% refined ranges; all others use 0.5-4.0.
Saves results to predictions/impact_score_refine_results.csv as it goes.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import os, warnings, random
warnings.filterwarnings('ignore')

os.makedirs("predictions", exist_ok=True)

RESULTS_PATH = "predictions/impact_score_refine_results.csv"
N_TRIALS = 300
N_SPLITS = 5
RANDOM_SEED = 42
TIME_DECAY = 0.85
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Full stat pool: label -> column name in DataFrame
STAT_POOL = {
    'Disposals':               'Disposals',
    'Goals':                   'Goals',
    'Clearances':              'Clearances',
    'Inside_50s':              'Inside.50s',
    'Goal_Assists':            'Goal.Assists',
    'Rebounds':                'Rebounds',
    'Handballs':               'Handballs',
    'Kicks':                   'Kicks',
    'Contested_Marks':         'Contested.Marks',
    'One_Percenters':          'One.Percenters',
    'Clangers':                'Clangers',
    'Uncontested_Possessions': 'Uncontested.Possessions',
    'Contested_Possessions':   'Contested.Possessions',
    'Hit_Outs':                'Hit.Outs',
    'Marks':                   'Marks',
    'Marks_Inside_50':         'Marks.Inside.50',
    'Score_Involvements':      'Score_Involvements',
    'Tackles':                 'Tackles',
}
STAT_LABELS = list(STAT_POOL.keys())

# Refined ranges for the 6 best stats: ±50% around best values
BEST_COEFFICIENTS = {
    'Contested_Possessions': 2.85,
    'Hit_Outs':              1.51,
    'Marks':                 3.50,
    'Marks_Inside_50':       3.81,
    'Score_Involvements':    1.65,
    'Tackles':               2.93,
}
REFINED_RANGES = {
    stat: (round(val * 0.5, 4), round(val * 1.5, 4))
    for stat, val in BEST_COEFFICIENTS.items()
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

# ── Static relative features (no Impact_Score yet) ────────────
print("Building static relative features...")
RANK_STATS_BASE = ['Disposals', 'Goals', 'Contested.Possessions', 'Clearances',
                   'Kicks', 'Score_Involvements', 'Coaches_Votes', 'Tackles']
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
df['BOG_Disposals'] = (df['Disposals_game_rank'] == 1).astype(int)
df['BOG_Coaches'] = (df['Coaches_Votes_game_rank'] == 1).astype(int)
if 'RatingPoints_game_rank' in df.columns:
    df['BOG_Rating'] = (df['RatingPoints_game_rank'] == 1).astype(int)
    df['Top3_Rating'] = (df['RatingPoints_game_rank'] <= 3).astype(int)

# ── Feature lists ──────────────────────────────────────────────
TARGET = 'Brownlow.Votes'

BASE_STATIC = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles', 'Hit.Outs',
               'Clearances', 'Contested.Possessions', 'Uncontested.Possessions',
               'Contested.Marks', 'Marks.Inside.50', 'Goal.Assists', 'Inside.50s',
               'Rebounds', 'One.Percenters', 'Clangers', 'Kick_to_HB_ratio',
               'Contested_rate', 'Disposal_efficiency', 'Score_Involvements',
               'Is_Win', 'Is_Loss', 'Margin', 'Abs_Margin',
               'Coaches_Votes', 'Season', 'Margin_Bucket_enc']

REL_STATIC = ([f'{s}_game_rank' for s in RANK_STATS_BASE if f'{s}_game_rank' in df.columns] +
              [f'{s}_game_pct'  for s in RANK_STATS_BASE if f'{s}_game_pct'  in df.columns] +
              [f'{s}_game_z'    for s in RANK_STATS_BASE if f'{s}_game_z'    in df.columns] +
              ['Top3_Disposals', 'Top3_Coaches', 'BOG_Disposals', 'BOG_Coaches'])
if 'BOG_Rating' in df.columns:
    REL_STATIC += ['BOG_Rating', 'Top3_Rating']

STATIC_FEATURES = list(dict.fromkeys(BASE_STATIC + WHEELO_FEATURES + REL_STATIC))
STATIC_FEATURES = [f for f in STATIC_FEATURES if f in df.columns]

# Impact-score features recomputed each trial
IMPACT_NAMES = ['Impact_Score',
                'Impact_Score_game_rank', 'Impact_Score_game_pct', 'Impact_Score_game_z',
                'Top3_Impact', 'BOG_Impact']

ALL_FEATURES = STATIC_FEATURES + IMPACT_NAMES

# ── Prepare clean dataset ──────────────────────────────────────
stat_cols_needed = [c for c in STAT_POOL.values() if c in df.columns]
keep = list(dict.fromkeys(
    STATIC_FEATURES + [TARGET, 'Player_Name', 'Playing.for', 'Round_num', 'Game_ID', 'Season'] +
    stat_cols_needed
))
df_clean = (df[keep].dropna(subset=STATIC_FEATURES + [TARGET])
            .copy().reset_index(drop=True))

y = df_clean[TARGET].astype(int)
max_s = df_clean['Season'].max()
w = (TIME_DECAY ** (max_s - df_clean['Season'])).values.flatten()
groups = df_clean['Season'].values.flatten().astype(int)

gkf = GroupKFold(n_splits=N_SPLITS)
X_static = df_clean[STATIC_FEATURES].values
game_ids = df_clean['Game_ID'].values

print(f"\nDataset: {len(df_clean):,} rows | {len(STATIC_FEATURES)} static + {len(IMPACT_NAMES)} impact features")
print(f"Time decay: {TIME_DECAY}")
print(f"\nRefined coefficient ranges:")
for stat, (lo, hi) in REFINED_RANGES.items():
    print(f"  {stat:25s}: [{lo:.4f}, {hi:.4f}]  (best={BEST_COEFFICIENTS[stat]})")
print(f"\nOther stats: coefficient range [0.5, 4.0]")

# ── Helper: compute impact columns ────────────────────────────
def compute_impact_cols(formula):
    impact = np.zeros(len(df_clean), dtype=np.float64)
    for stat_label, coef in formula.items():
        col = STAT_POOL[stat_label]
        if col in df_clean.columns:
            impact += coef * df_clean[col].values

    gid_series = pd.Series(game_ids)
    imp_series = pd.Series(impact)
    rank = imp_series.groupby(gid_series).rank(ascending=False, method='min').values
    pct  = imp_series.groupby(gid_series).rank(pct=True).values
    z    = imp_series.groupby(gid_series).transform(
        lambda x: (x - x.mean()) / (x.std() + 0.001)).values
    top3 = (rank <= 3).astype(np.float64)
    bog  = (rank == 1).astype(np.float64)
    return np.column_stack([impact, rank, pct, z, top3, bog])

# ── Load existing results (resume support) ─────────────────────
results = []
if os.path.exists(RESULTS_PATH):
    existing = pd.read_csv(RESULTS_PATH)
    results = existing.to_dict('records')
    print(f"\nResuming: {len(results)} results already saved")

# ── Search ─────────────────────────────────────────────────────
print(f"\nSearching {N_TRIALS} combinations...")
start_trial = len(results)

for trial_idx in range(start_trial, N_TRIALS):
    n_stats = random.randint(4, 10)
    selected = random.sample(STAT_LABELS, n_stats)

    formula = {}
    for s in selected:
        if s in REFINED_RANGES:
            lo, hi = REFINED_RANGES[s]
            formula[s] = round(random.uniform(lo, hi), 3)
        else:
            formula[s] = round(random.uniform(0.5, 4.0), 3)

    formula_str = ' + '.join(f"{coef}*{stat}" for stat, coef in sorted(formula.items()))

    impact_cols = compute_impact_cols(formula)
    X = np.hstack([X_static, impact_cols])

    fold_maes = []
    model = xgb.XGBClassifier(**XGB_PARAMS)
    for train_idx, val_idx in gkf.split(X, y, groups):
        model.fit(X[train_idx], y.iloc[train_idx], sample_weight=w[train_idx],
                  eval_set=[(X[val_idx], y.iloc[val_idx])], verbose=False)
        fold_maes.append(mean_absolute_error(y.iloc[val_idx], model.predict(X[val_idx])))

    mean_mae = float(np.mean(fold_maes))

    result = {
        'trial': trial_idx + 1,
        'n_stats': n_stats,
        'mae': round(mean_mae, 6),
        'formula': formula_str,
        **{f'coef_{s}': formula.get(s, np.nan) for s in STAT_LABELS},
    }
    results.append(result)
    pd.DataFrame(results).to_csv(RESULTS_PATH, index=False)

    best_so_far = min(r['mae'] for r in results)
    marker = ' *** BEST ***' if mean_mae == best_so_far else ''
    print(f"  [{trial_idx+1:3d}/{N_TRIALS}] MAE {mean_mae:.4f}{marker}  {formula_str}")

# ── Final results ──────────────────────────────────────────────
results_df = pd.DataFrame(results).sort_values('mae').reset_index(drop=True)
best = results_df.iloc[0]

print(f"\n{'='*70}")
print(f"REFINED SEARCH COMPLETE — {N_TRIALS} combinations tested")
print(f"{'='*70}")
print(f"Best MAE  :  {best['mae']:.6f}")
print(f"Formula   :  {best['formula']}")
print(f"N stats   :  {int(best['n_stats'])}")
print(f"\nTop 10 formulas:")
print(results_df[['trial', 'mae', 'n_stats', 'formula']].head(10).to_string(index=False))
print(f"\nFull results saved to {RESULTS_PATH}")
