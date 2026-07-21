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
import features as feat
warnings.filterwarnings('ignore')

os.makedirs("predictions", exist_ok=True)

# ── Variant switch ───────────────────────────────────────────
# One script, two feature sets — NOT two scripts. A fork would let the variants
# drift apart the first time a feature is added to only one of them, and the
# whole point of the variant is that it is the same model minus coaches votes.
#
# NO_COACHES=1 drops the six same-game coaches features and takes Coaches_Votes
# out of RANK_STATS, for predicting rounds whose coaches votes are not published
# yet (the last two rounds before the count).
#
# DROP_MOMENTUM_CV is separate because momentum_cv is a SEVENTH coaches-derived
# feature and the answer is not obvious. Since the point-in-time fix it reads
# only PRIOR rounds, so in the target scenario — late rounds, where earlier
# coaches votes have long been published — it is genuinely computable. Dropping
# it buys independence from coaches data entirely; keeping it keeps real signal
# that is actually available. Both are trained and compared rather than assumed.
NO_COACHES       = os.environ.get('NO_COACHES', '0') == '1'
DROP_MOMENTUM_CV = os.environ.get('DROP_MOMENTUM_CV', '0') == '1'
_SUFFIX = ''
if NO_COACHES:
    _SUFFIX = '_nocv_nomom' if DROP_MOMENTUM_CV else '_nocv'
print(f"Variant: {'NO_COACHES' if NO_COACHES else 'FULL'}"
      f"{' (momentum_cv dropped)' if NO_COACHES and DROP_MOMENTUM_CV else ''}"
      f" | artifact suffix: {_SUFFIX or '(none)'}")

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

stats = feat.add_row_stats(stats)
le = LabelEncoder()
le.fit(feat.MARGIN_BUCKETS)
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

RANK_STATS = feat.rank_stats_for(df)
if NO_COACHES:
    RANK_STATS = [s for s in RANK_STATS if s != 'Coaches_Votes']

df = feat.build_game_rank_features(df, RANK_STATS)
df = feat.build_rank_flags(df, include_coaches=not NO_COACHES)

# ── Build form and momentum features ─────────────────────────
print("Building form and momentum features...")
df = df.sort_values(['Season', 'Player_Name', 'Round_num']).reset_index(drop=True)

df = feat.build_form_features(
    df, ['Season', 'Player_Name'],
    include_momentum_cv=not (NO_COACHES and DROP_MOMENTUM_CV),
)

FORM_FEATURES = feat.form_feature_names(df)
print(f"  Form/momentum features: {FORM_FEATURES}")

# ── Define all features ──────────────────────────────────────
FEATURES = feat.assemble_features(
    df, RANK_STATS, WHEELO_FEATURES, FORM_FEATURES,
    include_coaches=not NO_COACHES,
    include_momentum_cv=not (NO_COACHES and DROP_MOMENTUM_CV),
)
BASE_FEATURES = feat.BASE_FEATURES
TARGET = 'Brownlow.Votes'

print(f"\nTotal features: {len(FEATURES)}")
if NO_COACHES:
    print("  NO_COACHES: coaches features excluded (asserted in features.assemble_features)")
    if not DROP_MOMENTUM_CV and 'momentum_cv' in FEATURES:
        print("  NOTE: momentum_cv retained — built from Coaches_Votes over PRIOR "
              "rounds only, so it needs published history but not the current game.")

_id_cols = ['ID'] if 'ID' in df.columns else []
model_df = df[FEATURES+[TARGET,'Player_Name','Playing.for','Round_num']+_id_cols]\
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

# MAE is also split by round bucket so the late-season 2x weighting's effect is
# visible rather than assumed: early R1-8, mid R9-16, late R17+ (the weighted
# tail). Buckets are averaged across folds the same way overall MAE is.
_ROUND_BUCKETS = [('early (R1-8)', 1, 8), ('mid (R9-16)', 9, 16), ('late (R17+)', 17, 99)]
_rnd_vals = model_df['Round_num'].values

fold_scores = []
_bucket_scores = {b: [] for b, _, _ in _ROUND_BUCKETS}
for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
    model.fit(X.iloc[train_idx], y.iloc[train_idx], sample_weight=w[train_idx],
              eval_set=[(X.iloc[val_idx], y.iloc[val_idx])], verbose=False)
    _pred = model.predict(X.iloc[val_idx])
    _true = y.iloc[val_idx].values
    mae = mean_absolute_error(_true, _pred)
    fold_scores.append(mae)
    _vr = _rnd_vals[val_idx]
    for _b, _lo, _hi in _ROUND_BUCKETS:
        _m = (_vr >= _lo) & (_vr <= _hi)
        if _m.any():
            _bucket_scores[_b].append(np.abs(_true[_m] - _pred[_m]).mean())
    print(f"  Fold {fold+1} | Seasons {np.unique(groups[val_idx])} | MAE: {mae:.4f}")

print(f"\nMean CV MAE: {np.mean(fold_scores):.4f}")
print("  By round bucket: " + " | ".join(
    f"{_b} {np.mean(_s):.4f}" for (_b, _, _), _s in zip(_ROUND_BUCKETS, _bucket_scores.values())))
print("  Baselines: 0.0953 full model | 0.1013 no-coaches variant.")
print("  (Pre-2026-audit figures — v1 0.0954 / v2 0.0910 / v3 0.0902 / v4 0.0904 —")
print("   were all measured with the momentum leak in place, so none of them is")
print("   comparable to these and the apparent v1->v4 gain may be partly artefact.)")
print("Fitting final model on all data...")
model.fit(X, y, sample_weight=w)

# Feature importance
imp = pd.DataFrame({'Feature':FEATURES,'Importance':model.feature_importances_})\
    .sort_values('Importance',ascending=False)
imp.to_csv(f"predictions/feature_importance{_SUFFIX}.csv", index=False)
print("\n=== TOP 20 FEATURES ===")
print(imp.head(20).to_string(index=False))

# Save model artifacts
with open(f"predictions/model{_SUFFIX}.pkl","wb") as f: pickle.dump(model, f)
with open(f"predictions/features{_SUFFIX}.pkl","wb") as f: pickle.dump(FEATURES, f)
with open(f"predictions/label_encoder{_SUFFIX}.pkl","wb") as f: pickle.dump(le, f)
with open(f"predictions/rank_stats{_SUFFIX}.pkl","wb") as f: pickle.dump(RANK_STATS, f)
with open(f"predictions/wheelo_features{_SUFFIX}.pkl","wb") as f: pickle.dump(WHEELO_FEATURES, f)
with open(f"predictions/form_features{_SUFFIX}.pkl","wb") as f: pickle.dump(FORM_FEATURES, f)
print("OK Model artifacts saved")

# ── Disambiguate same-name players for output ────────────────
# Player_Name alone merges different people who share a name (the two Josh
# Kennedys -> one 535-game row). fitzRoy's ID is the true identity: names carried
# by more than one ID get that person's most-recent team appended. The suffix is
# the player's GLOBAL last team (across all seasons), so it stays identical in
# every season file — a single player who changed clubs (Tom Lynch: Gold Coast ->
# Richmond) keeps ONE identity, while genuinely different people are split apart.
if 'ID' in model_df.columns:
    _idn = model_df.dropna(subset=['ID']).groupby('Player_Name')['ID'].nunique()
    _collision = set(_idn[_idn > 1].index)
    if _collision:
        _sub = model_df[model_df['Player_Name'].isin(_collision)]
        _last_team = (_sub.dropna(subset=['ID']).sort_values(['Season', 'Round_num'])
                          .groupby('ID')['Playing.for'].last())
        _mask = model_df['Player_Name'].isin(_collision)
        _suffix = model_df.loc[_mask, 'ID'].map(_last_team).fillna(model_df.loc[_mask, 'Playing.for'])
        model_df.loc[_mask, 'Player_Name'] = (model_df.loc[_mask, 'Player_Name']
                                              + ' (' + _suffix.astype(str) + ')')
        print(f"  Disambiguated {len(_collision)} shared name(s): {sorted(_collision)}")
else:
    print("  No ID column found — skipping same-name disambiguation")

# ── Generate predictions for all seasons ─────────────────────
# Variant runs stop here. These CSVs are unsuffixed and are what the dashboard
# reads, so letting a variant reach them would silently replace the full model's
# published predictions with a deliberately weaker model's. The variant exists to
# be measured, not to serve.
if NO_COACHES:
    print(f"\nNO_COACHES variant: artifacts saved with suffix '{_SUFFIX}'.")
    print("Skipping per-season prediction CSVs — those belong to the full model.")
    raise SystemExit(0)

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
