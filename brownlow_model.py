"""
Brownlow Medal Prediction Engine v4.0
- Relative game features
- Wheelo rating points + quarter ratings + equity components
- Late season form (rolling EWMA of prior 5 rounds)
- Season momentum (last-6 vs first-6 coaches votes + disposals)
- Late-season sample weighting (last 5 rounds = 2x weight)
- Finals filtered out
- 2015-2025 training data
Run: python brownlow_model.py
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import pickle
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

# Load Wheelo data if available
wheelo_path = "data_wheelo/wheelo_all_seasons.csv"
wheelo = None
if os.path.exists(wheelo_path):
    wheelo = pd.read_csv(wheelo_path, low_memory=False)
    print(f"  Wheelo: {len(wheelo):,} rows")
else:
    print("  Wheelo: not found — running without rating points")

print("\nCleaning data...")
stats['Season'] = pd.to_numeric(stats['Season'], errors='coerce')
stats['Round_num'] = pd.to_numeric(stats['Round'], errors='coerce')
stats['Brownlow.Votes'] = pd.to_numeric(stats['Brownlow.Votes'], errors='coerce').fillna(0)

# Filter finals — string-labeled rounds (QF/EF/SF/PF/GF) become NaN; dynamic per-season max
before = len(stats)
stats = stats[stats['Round_num'].notna()].copy()
max_ha_per_season = stats.groupby('Season')['Round_num'].max().to_dict()
print(f"  Filtered finals: {before:,} -> {len(stats):,} rows ({before-len(stats):,} removed)")
print(f"  Max H&A round per season: { {int(k): int(v) for k, v in sorted(max_ha_per_season.items())} }")

stats['Player_Name'] = stats['First.name'].str.strip() + ' ' + stats['Surname'].str.strip()
stats['Home.score'] = pd.to_numeric(stats['Home.score'], errors='coerce')
stats['Away.score'] = pd.to_numeric(stats['Away.score'], errors='coerce')

def get_outcome(row):
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a): return pd.Series({'Outcome':'U','Margin':0})
    margin = h-a if row['Home.Away']=='Home' else a-h
    return pd.Series({'Outcome':'W' if margin>0 else ('L' if margin<0 else 'D'),'Margin':margin})

stats[['Outcome','Margin']] = stats.apply(get_outcome, axis=1)
stats['Abs_Margin'] = stats['Margin'].abs()
stats['Is_Win'] = (stats['Outcome']=='W').astype(int)
stats['Is_Loss'] = (stats['Outcome']=='L').astype(int)

for col in ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
            'Clearances','Contested.Possessions','Uncontested.Possessions',
            'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
            'Rebounds','One.Percenters','Clangers']:
    stats[col] = pd.to_numeric(stats[col], errors='coerce').fillna(0)

stats['Kick_to_HB_ratio'] = stats['Kicks']/(stats['Handballs']+1)
stats['Contested_rate'] = stats['Contested.Possessions']/(stats['Disposals']+1)
stats['Disposal_efficiency'] = (stats['Disposals']-stats['Clangers'])/(stats['Disposals']+1)
stats['Score_Involvements'] = stats['Goals']+stats['Goal.Assists']+stats['Marks.Inside.50']+stats['Inside.50s']
stats['Impact_Score'] = (stats['Contested.Possessions']*2.85 + stats['Hit.Outs']*1.51 +
                         stats['Marks']*3.5 + stats['Marks.Inside.50']*3.81 +
                         stats['Score_Involvements']*1.65 + stats['Tackles']*2.93)

def margin_bucket(m):
    if m>0: return 'close_win' if m<=15 else ('comfortable_win' if m<=40 else 'big_win')
    elif m<0: return 'close_loss' if m>=-15 else ('comfortable_loss' if m>=-40 else 'big_loss')
    return 'draw'
stats['Margin_Bucket'] = stats['Margin'].apply(margin_bucket)
le = LabelEncoder()
all_buckets = ['big_loss','big_win','close_loss','close_win','comfortable_loss','comfortable_win','draw','unknown']
le.fit(all_buckets)
stats['Margin_Bucket_enc'] = le.transform(stats['Margin_Bucket'].fillna('unknown'))

# ── Merge coaches votes ──────────────────────────────────────
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

# ── Merge Wheelo data ────────────────────────────────────────
WHEELO_FEATURES = []
if wheelo is not None:
    print("Merging Wheelo data...")
    wheelo['Season'] = pd.to_numeric(wheelo['Season'], errors='coerce')
    wheelo['Round'] = pd.to_numeric(wheelo['Round'], errors='coerce')
    
    # Filter finals from Wheelo too (string-labeled finals become NaN)
    wheelo = wheelo[wheelo['Round'].notna()].copy()
    
    # Numeric conversion for all Wheelo features
    WHEELO_COLS = ['RatingPoints','ExpVotes','Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4',
                   'Equity_PreClearance','Equity_PostClearance','Equity_Possession','Equity_BallUse',
                   'GroundBallGets','HitoutsToAdvantage','ScoreLaunches','FirstPossessions',
                   'Supercoach','TimeOnGround','DisposalEfficiency','CentreBounceAttendancePercentage']
    
    for col in WHEELO_COLS:
        if col in wheelo.columns:
            wheelo[col] = pd.to_numeric(wheelo[col], errors='coerce')
    
    # Normalize team names to match stats dataset
    wheelo['Team'] = wheelo['Team'].replace({'Brisbane': 'Brisbane Lions'})

    # Merge on Player name, Team, Season, Round (team disambiguates same-name players e.g. Bailey Williams)
    wheelo_merge = wheelo[['Player','Team','Season','Round'] +
                          [c for c in WHEELO_COLS if c in wheelo.columns]].copy()
    wheelo_merge.columns = ['Player_Name','Playing.for','Season','Round_num'] + \
                           [c for c in WHEELO_COLS if c in wheelo.columns]

    df = df.merge(wheelo_merge, on=['Player_Name','Playing.for','Season','Round_num'], how='left')
    
    # Fill missing with 0
    WHEELO_FEATURES = [c for c in WHEELO_COLS if c in df.columns]
    for col in WHEELO_FEATURES:
        df[col] = df[col].fillna(0)
    
    # Add quarter rating features
    if 'Rating_Q1' in df.columns and 'Rating_Q4' in df.columns:
        df['Rating_Q4_premium'] = df['Rating_Q4'] - df[['Rating_Q1','Rating_Q2','Rating_Q3']].mean(axis=1)
        df['Best_quarter_rating'] = df[['Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4']].max(axis=1)
        WHEELO_FEATURES += ['Rating_Q4_premium','Best_quarter_rating']
    
    print(f"  Wheelo features added: {len(WHEELO_FEATURES)}")
    match_rate = (df['RatingPoints'] > 0).mean() if 'RatingPoints' in df.columns else 0
    print(f"  Match rate: {match_rate:.1%} of rows have Wheelo data")

# ── Build relative game features ─────────────────────────────
print("Building relative game features...")
df['Game_ID'] = df['Season'].astype(str)+'_'+df['Round_num'].astype(str)+'_'+df['Home.team'].astype(str)+'_'+df['Away.team'].astype(str)

RANK_STATS = ['Disposals','Goals','Contested.Possessions','Clearances',
              'Kicks','Impact_Score','Score_Involvements','Coaches_Votes','Tackles']

# Add Wheelo stats to ranking if available
if 'RatingPoints' in df.columns:
    RANK_STATS += ['RatingPoints','ExpVotes']

for stat in RANK_STATS:
    if stat in df.columns:
        df[f'{stat}_game_rank'] = df.groupby('Game_ID')[stat].rank(ascending=False, method='min')
        df[f'{stat}_game_pct'] = df.groupby('Game_ID')[stat].rank(pct=True)
        df[f'{stat}_game_z'] = df.groupby('Game_ID')[stat].transform(lambda x: (x-x.mean())/(x.std()+0.001))

df['Top3_Disposals'] = (df['Disposals_game_rank']<=3).astype(int)
df['Top3_Coaches'] = (df['Coaches_Votes_game_rank']<=3).astype(int)
df['Top3_Impact'] = (df['Impact_Score_game_rank']<=3).astype(int)
df['BOG_Disposals'] = (df['Disposals_game_rank']==1).astype(int)
df['BOG_Coaches'] = (df['Coaches_Votes_game_rank']==1).astype(int)
df['BOG_Impact'] = (df['Impact_Score_game_rank']==1).astype(int)
if 'RatingPoints_game_rank' in df.columns:
    df['BOG_Rating'] = (df['RatingPoints_game_rank']==1).astype(int)
    df['Top3_Rating'] = (df['RatingPoints_game_rank']<=3).astype(int)

# ── Build form and momentum features ─────────────────────────
print("Building form and momentum features...")
df = df.sort_values(['Season', 'Player_Name', 'Round_num']).reset_index(drop=True)

# Late season form: EWMA (span=5) of prior rounds — shift(1) prevents lookahead
_form_src = 'ExpVotes' if 'ExpVotes' in df.columns else 'Coaches_Votes'
df['late_form_ewm'] = (
    df.groupby(['Season', 'Player_Name'])[_form_src]
    .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
    .fillna(0)
)

# Season momentum: avg of last 6 games minus avg of first 6 games
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
print(f"  Form/momentum features: {FORM_FEATURES}")

# ── Define all features ──────────────────────────────────────
BASE_FEATURES = ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
                 'Clearances','Contested.Possessions','Uncontested.Possessions',
                 'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
                 'Rebounds','One.Percenters','Clangers','Kick_to_HB_ratio',
                 'Contested_rate','Disposal_efficiency','Score_Involvements',
                 'Impact_Score','Is_Win','Is_Loss','Margin','Abs_Margin',
                 'Coaches_Votes','Season','Margin_Bucket_enc']

RELATIVE_FEATURES = [f'{s}_game_rank' for s in RANK_STATS if f'{s}_game_rank' in df.columns] + \
                    [f'{s}_game_pct' for s in RANK_STATS if f'{s}_game_pct' in df.columns] + \
                    [f'{s}_game_z' for s in RANK_STATS if f'{s}_game_z' in df.columns] + \
                    ['Top3_Disposals','Top3_Coaches','Top3_Impact',
                     'BOG_Disposals','BOG_Coaches','BOG_Impact']

if 'BOG_Rating' in df.columns:
    RELATIVE_FEATURES += ['BOG_Rating','Top3_Rating']

FEATURES = BASE_FEATURES + WHEELO_FEATURES + RELATIVE_FEATURES + FORM_FEATURES
TARGET = 'Brownlow.Votes'

# Remove any duplicates
FEATURES = list(dict.fromkeys(FEATURES))
# Keep only features that exist in df
FEATURES = [f for f in FEATURES if f in df.columns]

print(f"\nTotal features: {len(FEATURES)}")
print(f"  Base: {len(BASE_FEATURES)}")
print(f"  Wheelo: {len(WHEELO_FEATURES)}")
print(f"  Relative: {len(RELATIVE_FEATURES)}")
print(f"  Form/Momentum: {len(FORM_FEATURES)}")

model_df = df[FEATURES+[TARGET,'Player_Name','Playing.for','Round_num']]\
    .dropna(subset=FEATURES+[TARGET]).reset_index(drop=True)

print(f"Model dataset: {len(model_df):,} rows")
print(f"Vote distribution:\n{model_df[TARGET].value_counts().sort_index().to_string()}")

# ── Train model ──────────────────────────────────────────────
print("\nTraining XGBoost model v4.0...")
X = model_df[FEATURES].copy()
y = model_df[TARGET].astype(int)
# Late-season rows (last 5 rounds of each season) weighted 2x
_max_rnd = model_df.groupby('Season')['Round_num'].transform('max')
w = np.where(model_df['Round_num'] >= _max_rnd - 4, 2.0, 1.0)
groups = model_df['Season'].values.flatten().astype(int)

gkf = GroupKFold(n_splits=5)
model = xgb.XGBClassifier(n_estimators=300, max_depth=7, learning_rate=0.05,
                           subsample=0.85, colsample_bytree=0.8, min_child_weight=7,
                           gamma=0.1, reg_alpha=0.2, reg_lambda=2.0,
                           eval_metric='mlogloss', random_state=42, n_jobs=-1)

fold_scores = []
for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
    model.fit(X.iloc[train_idx], y.iloc[train_idx], sample_weight=w[train_idx],
              eval_set=[(X.iloc[val_idx], y.iloc[val_idx])], verbose=False)
    mae = mean_absolute_error(y.iloc[val_idx], model.predict(X.iloc[val_idx]))
    fold_scores.append(mae)
    print(f"  Fold {fold+1} | Seasons {np.unique(groups[val_idx])} | MAE: {mae:.4f}")

print(f"\nMean CV MAE: {np.mean(fold_scores):.4f}")
print(f"  v1 was 0.0954, v2 was 0.0910, v3 was 0.0902, v4 is 0.0904")
print("Fitting final model on all data...")
model.fit(X, y, sample_weight=w)

# Feature importance
imp = pd.DataFrame({'Feature':FEATURES,'Importance':model.feature_importances_})\
    .sort_values('Importance',ascending=False)
imp.to_csv("predictions/feature_importance.csv", index=False)
print("\n=== TOP 20 FEATURES ===")
print(imp.head(20).to_string(index=False))

# Save model artifacts
with open("predictions/model.pkl","wb") as f: pickle.dump(model, f)
with open("predictions/features.pkl","wb") as f: pickle.dump(FEATURES, f)
with open("predictions/label_encoder.pkl","wb") as f: pickle.dump(le, f)
with open("predictions/rank_stats.pkl","wb") as f: pickle.dump(RANK_STATS, f)
with open("predictions/wheelo_features.pkl","wb") as f: pickle.dump(WHEELO_FEATURES, f)
with open("predictions/form_features.pkl","wb") as f: pickle.dump(FORM_FEATURES, f)
print("OK Model artifacts saved")

# ── Generate predictions for all seasons ─────────────────────
print("\nGenerating predictions for all seasons...")
classes = list(model.classes_)
ALL_SEASONS = sorted(model_df['Season'].unique().astype(int).tolist())

for season in ALL_SEASONS:
    df_s = model_df[model_df['Season']==season].copy().reset_index(drop=True)
    proba = model.predict_proba(df_s[FEATURES])
    df_s['P_1'] = proba[:,classes.index(1)] if 1 in classes else 0
    df_s['P_2'] = proba[:,classes.index(2)] if 2 in classes else 0
    df_s['P_3'] = proba[:,classes.index(3)] if 3 in classes else 0
    df_s['Poll_Prob'] = df_s['P_1']+df_s['P_2']+df_s['P_3']
    df_s['Exp_Votes'] = df_s['P_1']*1+df_s['P_2']*2+df_s['P_3']*3
    df_s.to_csv(f"predictions/game_level_{season}.csv", index=False)
    totals = df_s.groupby('Player_Name').agg(
        Team=('Playing.for','last'), Games=('Round_num','count'),
        Actual_Votes=(TARGET,'sum'), Exp_Total_Votes=('Exp_Votes','sum'),
        Avg_Poll_Prob=('Poll_Prob','mean'), Exp_3vote_games=('P_3','sum'),
        Exp_2vote_games=('P_2','sum'), Exp_1vote_games=('P_1','sum'),
    ).reset_index().sort_values('Exp_Total_Votes', ascending=False)
    totals.to_csv(f"predictions/season_{season}.csv", index=False)
    print(f"  OK {season}: {len(totals)} players")

print("\nAll done. Run: python -m streamlit run dashboard.py")
