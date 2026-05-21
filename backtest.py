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
stats['Score_Involvements'] = (stats['Goals'] + stats['Goal.Assists'] +
                               stats['Marks.Inside.50'] + stats['Inside.50s'])
stats['Impact_Score'] = (stats['Contested.Possessions'] * 2.85 + stats['Hit.Outs'] * 1.51 +
                         stats['Marks'] * 3.5 + stats['Marks.Inside.50'] * 3.81 +
                         stats['Score_Involvements'] * 1.65 + stats['Tackles'] * 2.93)

def margin_bucket(m):
    if m > 0: return 'close_win' if m <= 15 else ('comfortable_win' if m <= 40 else 'big_win')
    elif m < 0: return 'close_loss' if m >= -15 else ('comfortable_loss' if m >= -40 else 'big_loss')
    return 'draw'

stats['Margin_Bucket'] = stats['Margin'].apply(margin_bucket)
le = LabelEncoder()
all_buckets = ['big_loss','big_win','close_loss','close_win','comfortable_loss','comfortable_win','draw','unknown']
le.fit(all_buckets)
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

RANK_STATS = ['Disposals','Goals','Contested.Possessions','Clearances',
              'Kicks','Impact_Score','Score_Involvements','Coaches_Votes','Tackles']
if 'RatingPoints' in df.columns:
    RANK_STATS += ['RatingPoints','ExpVotes']

for stat in RANK_STATS:
    if stat in df.columns:
        df[f'{stat}_game_rank'] = df.groupby('Game_ID')[stat].rank(ascending=False, method='min')
        df[f'{stat}_game_pct'] = df.groupby('Game_ID')[stat].rank(pct=True)
        df[f'{stat}_game_z'] = df.groupby('Game_ID')[stat].transform(
            lambda x: (x - x.mean()) / (x.std() + 0.001))

df['Top3_Disposals'] = (df['Disposals_game_rank'] <= 3).astype(int)
df['Top3_Coaches']   = (df['Coaches_Votes_game_rank'] <= 3).astype(int)
df['Top3_Impact']    = (df['Impact_Score_game_rank'] <= 3).astype(int)
df['BOG_Disposals']  = (df['Disposals_game_rank'] == 1).astype(int)
df['BOG_Coaches']    = (df['Coaches_Votes_game_rank'] == 1).astype(int)
df['BOG_Impact']     = (df['Impact_Score_game_rank'] == 1).astype(int)
if 'RatingPoints_game_rank' in df.columns:
    df['BOG_Rating']  = (df['RatingPoints_game_rank'] == 1).astype(int)
    df['Top3_Rating'] = (df['RatingPoints_game_rank'] <= 3).astype(int)

# ── Build form and momentum features (identical to brownlow_model.py) ──
print("Building form and momentum features...")
df = df.sort_values(['Season', 'Player_Name', 'Round_num']).reset_index(drop=True)

_form_src = 'ExpVotes' if 'ExpVotes' in df.columns else 'Coaches_Votes'
df['late_form_ewm'] = (
    df.groupby(['Season', 'Player_Name'])[_form_src]
    .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
    .fillna(0)
)

df['_gseq'] = df.groupby(['Season', 'Player_Name']).cumcount()
df['_ng']   = df.groupby(['Season', 'Player_Name'])['Round_num'].transform('count')

_f6 = (df[df['_gseq'] < 6]
       .groupby(['Season', 'Player_Name'])[['Coaches_Votes', 'Disposals']]
       .mean()
       .rename(columns={'Coaches_Votes': '_f6cv', 'Disposals': '_f6d'})
       .reset_index())
_l6 = (df[df['_gseq'] >= df['_ng'] - 6]
       .groupby(['Season', 'Player_Name'])[['Coaches_Votes', 'Disposals']]
       .mean()
       .rename(columns={'Coaches_Votes': '_l6cv', 'Disposals': '_l6d'})
       .reset_index())

_mom = _f6.merge(_l6, on=['Season', 'Player_Name'], how='outer').fillna(0)
_mom['momentum_cv']   = _mom['_l6cv'] - _mom['_f6cv']
_mom['momentum_disp'] = _mom['_l6d']  - _mom['_f6d']

df = df.merge(_mom[['Season', 'Player_Name', 'momentum_cv', 'momentum_disp']],
              on=['Season', 'Player_Name'], how='left')
df[['momentum_cv', 'momentum_disp']] = df[['momentum_cv', 'momentum_disp']].fillna(0)
df.drop(columns=['_gseq', '_ng'], inplace=True)

FORM_FEATURES = ['late_form_ewm', 'momentum_cv', 'momentum_disp']

# ── Feature set (identical to brownlow_model.py) ──────────────
BASE_FEATURES = ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
                 'Clearances','Contested.Possessions','Uncontested.Possessions',
                 'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
                 'Rebounds','One.Percenters','Clangers','Kick_to_HB_ratio',
                 'Contested_rate','Disposal_efficiency','Score_Involvements',
                 'Impact_Score','Is_Win','Is_Loss','Margin','Abs_Margin',
                 'Coaches_Votes','Season','Margin_Bucket_enc']

RELATIVE_FEATURES = (
    [f'{s}_game_rank' for s in RANK_STATS if f'{s}_game_rank' in df.columns] +
    [f'{s}_game_pct'  for s in RANK_STATS if f'{s}_game_pct'  in df.columns] +
    [f'{s}_game_z'    for s in RANK_STATS if f'{s}_game_z'    in df.columns] +
    ['Top3_Disposals','Top3_Coaches','Top3_Impact','BOG_Disposals','BOG_Coaches','BOG_Impact']
)
if 'BOG_Rating' in df.columns:
    RELATIVE_FEATURES += ['BOG_Rating','Top3_Rating']

FEATURES = list(dict.fromkeys(BASE_FEATURES + WHEELO_FEATURES + RELATIVE_FEATURES + FORM_FEATURES))
FEATURES = [f for f in FEATURES if f in df.columns]
TARGET = 'Brownlow.Votes'

extra_cols = [c for c in [TARGET, 'Player_Name', 'Playing.for', 'Round_num', 'Season']
              if c not in FEATURES]
model_df = (df[FEATURES + extra_cols]
            .dropna(subset=FEATURES + [TARGET])
            .reset_index(drop=True))

print(f"Full dataset: {len(model_df):,} rows | {len(FEATURES)} features")

# ── Walk-forward back-test ────────────────────────────────────
# Start from the second available season so there is always at least one training year.
# With extended data this becomes ~2007; with the original 2015-2025 file it becomes 2016.
_all_seasons   = sorted(model_df['Season'].unique().astype(int).tolist())
BACKTEST_SEASONS = _all_seasons[1:]  # skip first season (nothing to train on before it)
print(f"Backtest seasons: {BACKTEST_SEASONS}")
all_results = []

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
    model.fit(train[FEATURES], train[TARGET].astype(int),
              sample_weight=np.ones(len(train)), verbose=False)

    proba  = model.predict_proba(test[FEATURES])
    classes = list(model.classes_)
    test = test.copy()
    test['P_1'] = proba[:, classes.index(1)] if 1 in classes else 0.0
    test['P_2'] = proba[:, classes.index(2)] if 2 in classes else 0.0
    test['P_3'] = proba[:, classes.index(3)] if 3 in classes else 0.0
    test['Exp_Votes'] = test['P_1'] * 1 + test['P_2'] * 2 + test['P_3'] * 3

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

    winner = season_agg.loc[season_agg['Rank_Actual'] == 1, 'Player_Name'].iloc[0]
    winner_pred_rank = int(season_agg.loc[season_agg['Player_Name'] == winner, 'Rank_Predicted'].values[0])
    top3 = season_agg[season_agg['Rank_Predicted'] <= 3]['Player_Name'].tolist()
    print(f"  Actual winner: {winner} | Predicted rank: {winner_pred_rank} | In top 3: {winner in top3}")

# ── Save results ──────────────────────────────────────────────
results = pd.concat(all_results, ignore_index=True)
results = results[['Season','Player_Name','Team','Actual_Votes','Predicted_Votes',
                   'Rank_Predicted','Rank_Actual']]
results.columns = ['Season','Player','Team','Actual_Votes','Predicted_Votes',
                   'Rank_Predicted','Rank_Actual']
results['Predicted_Votes'] = results['Predicted_Votes'].round(3)

out = "predictions/backtest_results.csv"
results.to_csv(out, index=False)
print(f"\nDone. {len(results):,} player-seasons saved -> {out}")
