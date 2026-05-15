"""
Brownlow Medal Prediction Engine
Generates predictions for all seasons 2015-2025
Run: python brownlow_model.py
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

print("Loading data...")
stats = pd.read_csv("fitzroy_stats_2015_2025.csv", low_memory=False)
coaches = pd.read_csv("coaches_votes_2015_2025.csv")
print(f"  Stats: {len(stats):,} rows | Coaches: {len(coaches):,} rows")

print("\nEngineering features...")
stats['Season'] = pd.to_numeric(stats['Season'], errors='coerce')
stats['Round_num'] = pd.to_numeric(stats['Round'], errors='coerce')
stats['Brownlow.Votes'] = pd.to_numeric(stats['Brownlow.Votes'], errors='coerce').fillna(0)
stats = stats[stats['Round_num'].notna()].copy()
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
stats['Impact_Score'] = stats['Goals']*3+stats['Clearances']*1.5+stats['Contested.Possessions']*1.2+stats['Kicks']*0.8

def margin_bucket(m):
    if m>0: return 'close_win' if m<=15 else ('comfortable_win' if m<=40 else 'big_win')
    elif m<0: return 'close_loss' if m>=-15 else ('comfortable_loss' if m>=-40 else 'big_loss')
    return 'draw'
stats['Margin_Bucket'] = stats['Margin'].apply(margin_bucket)
le = LabelEncoder()
stats['Margin_Bucket_enc'] = le.fit_transform(stats['Margin_Bucket'])

print("Merging coaches votes...")
coaches['Season'] = pd.to_numeric(coaches['Season'], errors='coerce')
coaches['Round'] = pd.to_numeric(coaches['Round'], errors='coerce')
coaches['Coaches.Votes'] = pd.to_numeric(coaches['Coaches.Votes'], errors='coerce').fillna(0)
coaches['CV_Player'] = coaches['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
coaches_agg = coaches.groupby(['Season','Round','CV_Player'])['Coaches.Votes'].sum().reset_index()
coaches_agg.columns = ['Season','Round_num','Player_Name','Coaches_Votes']
df = stats.merge(coaches_agg, on=['Season','Round_num','Player_Name'], how='left')
df['Coaches_Votes'] = df['Coaches_Votes'].fillna(0)

FEATURES = ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
            'Clearances','Contested.Possessions','Uncontested.Possessions',
            'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
            'Rebounds','One.Percenters','Clangers','Kick_to_HB_ratio',
            'Contested_rate','Disposal_efficiency','Score_Involvements',
            'Impact_Score','Is_Win','Is_Loss','Margin','Abs_Margin',
            'Coaches_Votes','Season','Margin_Bucket_enc']
TARGET = 'Brownlow.Votes'

model_df = df[FEATURES+[TARGET,'Player_Name','Playing.for','Round_num']]\
    .dropna(subset=FEATURES+[TARGET]).reset_index(drop=True)

print(f"\nModel dataset: {len(model_df):,} rows, {len(FEATURES)} features")

X = model_df[FEATURES].copy()
y = model_df[TARGET].astype(int)
max_s = model_df['Season'].max()
w = (0.85**(max_s - model_df['Season'])).values.flatten()
groups = model_df['Season'].values.flatten().astype(int)

print("\nTraining XGBoost model...")
gkf = GroupKFold(n_splits=5)
model = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
                           subsample=0.8, colsample_bytree=0.8,
                           eval_metric='mlogloss', random_state=42, n_jobs=-1)

fold_scores = []
for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
    model.fit(X.iloc[train_idx], y.iloc[train_idx], sample_weight=w[train_idx],
              eval_set=[(X.iloc[val_idx], y.iloc[val_idx])], verbose=False)
    mae = mean_absolute_error(y.iloc[val_idx], model.predict(X.iloc[val_idx]))
    fold_scores.append(mae)
    print(f"  Fold {fold+1} | Seasons {np.unique(groups[val_idx])} | MAE: {mae:.4f}")

print(f"\nMean CV MAE: {np.mean(fold_scores):.4f}")
print("Fitting final model on all data...")
model.fit(X, y, sample_weight=w)

pd.DataFrame({'Feature':FEATURES,'Importance':model.feature_importances_})\
    .sort_values('Importance',ascending=False)\
    .to_csv("predictions/feature_importance.csv", index=False)
print("✓ feature_importance.csv")

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
    print(f"  ✓ {season}: {len(totals)} players")

print("\nAll done. Run: python -m streamlit run dashboard.py")
