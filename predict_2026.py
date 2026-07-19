"""
2026 In-Season Predictor v4.0
Uses saved model with Wheelo features, late-season form, and momentum features
"""

import pandas as pd
import numpy as np
import features as feat
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import pickle
import os, warnings
warnings.filterwarnings('ignore')

os.makedirs("data_2026", exist_ok=True)
os.makedirs("predictions", exist_ok=True)

# ── Load saved model ─────────────────────────────────────────
print("Loading saved model...")
if not os.path.exists("predictions/model.pkl"):
    print("ERROR: No saved model. Run brownlow_model.py first.")
    exit()

with open("predictions/model.pkl","rb") as f: model = pickle.load(f)
with open("predictions/features.pkl","rb") as f: FEATURES = pickle.load(f)
with open("predictions/label_encoder.pkl","rb") as f: le = pickle.load(f)
with open("predictions/rank_stats.pkl","rb") as f: RANK_STATS = pickle.load(f)
WHEELO_FEATURES = []
if os.path.exists("predictions/wheelo_features.pkl"):
    with open("predictions/wheelo_features.pkl","rb") as f: WHEELO_FEATURES = pickle.load(f)
FORM_FEATURES = []
if os.path.exists("predictions/form_features.pkl"):
    with open("predictions/form_features.pkl","rb") as f: FORM_FEATURES = pickle.load(f)

print(f"Model loaded. {len(FEATURES)} features.")

# ── No-coaches variant (optional) ────────────────────────────
# Trained by brownlow_model.py with NO_COACHES=1. Used for games whose coaches
# votes are not published yet — the last rounds before the count, which is
# exactly when the full model is blindest, since coaches features carry ~43% of
# its importance. Absent artifacts simply disable routing; the full model then
# handles every game as before.
MODEL_NOCV = FEATURES_NOCV = None
if os.path.exists("predictions/model_nocv.pkl") and os.path.exists("predictions/features_nocv.pkl"):
    with open("predictions/model_nocv.pkl","rb") as f: MODEL_NOCV = pickle.load(f)
    with open("predictions/features_nocv.pkl","rb") as f: FEATURES_NOCV = pickle.load(f)
    print(f"No-coaches variant loaded. {len(FEATURES_NOCV)} features.")
else:
    print("No-coaches variant not found — every game will use the full model.")

# The six same-game coaches features. Never fed to the variant, and blanked in
# the output for variant-routed games so the degenerate all-zero ranking is not
# published as if it were real: with no votes in a game, rank(method='min')
# gives EVERY player rank 1, so BOG_Coaches and Top3_Coaches would read 1 for
# all 22 — the exact inverse of what they mean.
COACHES_FEATURES = feat.COACHES_FEATURES

TARGET = 'Brownlow.Votes'

# ── Load 2026 stats ──────────────────────────────────────────
print("\nLoading 2026 data...")
path_2026 = "data_2026/afltables_2026.csv"
if not os.path.exists(path_2026):
    print("ERROR: afltables_2026.csv not found. Run the R script first.")
    exit()

df26 = pd.read_csv(path_2026, low_memory=False)
df26['Playing.for'] = df26['Playing.for'].replace('Footscray', 'Western Bulldogs')
df26['Season'] = 2026
df26['Round_num'] = pd.to_numeric(df26['Round'], errors='coerce')
# Finals are string-labeled (QF/EF/SF/PF/GF) -> NaN; dynamic max H&A round from data
df26 = df26[df26['Round_num'].notna()].copy()
max_ha_round = int(df26['Round_num'].max())
df26['Player_Name'] = df26['First.name'].str.strip() + ' ' + df26['Surname'].str.strip()
print(f"  {len(df26)} rows through Round {max_ha_round} (max H&A round detected dynamically)")

df26['Home.score'] = pd.to_numeric(df26['Home.score'], errors='coerce')
df26['Away.score'] = pd.to_numeric(df26['Away.score'], errors='coerce')

def get_outcome(row):
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a): return pd.Series({'Outcome':'U','Margin':0})
    margin = h-a if row['Home.Away']=='Home' else a-h
    return pd.Series({'Outcome':'W' if margin>0 else ('L' if margin<0 else 'D'),'Margin':margin})

df26[['Outcome','Margin']] = df26.apply(get_outcome, axis=1)
df26['Abs_Margin'] = df26['Margin'].abs()
df26['Is_Win'] = (df26['Outcome']=='W').astype(int)
df26['Is_Loss'] = (df26['Outcome']=='L').astype(int)

for col in ['Kicks','Handballs','Disposals','Goals','Marks','Tackles','Hit.Outs',
            'Clearances','Contested.Possessions','Uncontested.Possessions',
            'Contested.Marks','Marks.Inside.50','Goal.Assists','Inside.50s',
            'Rebounds','One.Percenters','Clangers']:
    df26[col] = pd.to_numeric(df26.get(col, 0), errors='coerce').fillna(0)

df26['Kick_to_HB_ratio'] = df26['Kicks']/(df26['Handballs']+1)
df26['Contested_rate'] = df26['Contested.Possessions']/(df26['Disposals']+1)
df26['Disposal_efficiency'] = (df26['Disposals']-df26['Clangers'])/(df26['Disposals']+1)
df26['Score_Involvements'] = df26['Goals']+df26['Goal.Assists']+df26['Marks.Inside.50']+df26['Inside.50s']
df26['Impact_Score'] = df26['Goals']*3+df26['Clearances']*1.5+df26['Contested.Possessions']*1.2+df26['Kicks']*0.8

def margin_bucket(m):
    if m>0: return 'close_win' if m<=15 else ('comfortable_win' if m<=40 else 'big_win')
    elif m<0: return 'close_loss' if m>=-15 else ('comfortable_loss' if m>=-40 else 'big_loss')
    return 'draw'
df26['Margin_Bucket'] = df26['Margin'].apply(margin_bucket)
df26['Margin_Bucket_enc'] = le.transform(df26['Margin_Bucket'].fillna('unknown'))

# Merge coaches votes
if os.path.exists("data_2026/coaches_votes_2026.csv"):
    cv26 = pd.read_csv("data_2026/coaches_votes_2026.csv")
    cv26['Round'] = pd.to_numeric(cv26['Round'], errors='coerce')
    cv26['Coaches.Votes'] = pd.to_numeric(cv26['Coaches.Votes'], errors='coerce').fillna(0)
    # Team is part of the key, matching brownlow_model.py. It was dropped here,
    # so two players sharing a name in one round had their votes SUMMED onto
    # both — silently, because an unmatched or wrong merge lands as 0 and 0 is
    # also the legitimate value for the ~86% of rows that poll nothing.
    # The team code is in the source file all along: "Justin McInerney (SYD)".
    #
    # Abbreviation map from features.py, shared with the training path.
    CV_TEAM_ABBREV = feat.TEAM_ABBREV
    cv26['CV_Player'] = cv26['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
    cv26['CV_Code'] = cv26['Player.Name'].str.extract(r'\(([^)]+)\)')[0]
    cv26['CV_Team'] = cv26['CV_Code'].map(CV_TEAM_ABBREV)

    # An unmapped code would quietly drop that club's votes to zero on a merge
    # this feature set leans on heavily, so say so rather than absorb it.
    _unmapped = sorted(cv26.loc[cv26['CV_Team'].isna(), 'CV_Code'].dropna().unique())
    if _unmapped:
        print(f"  WARNING: unmapped coaches-vote team code(s): {_unmapped}")
        print("           those rows will not merge — add them to CV_TEAM_ABBREV")

    cv26_agg = (cv26.groupby(['Round', 'CV_Player', 'CV_Team'])['Coaches.Votes']
                    .sum().reset_index())
    cv26_agg.columns = ['Round_num', 'Player_Name', 'Playing.for', 'Coaches_Votes']
    df26 = df26.merge(cv26_agg, on=['Round_num', 'Player_Name', 'Playing.for'], how='left')
    df26['Coaches_Votes'] = df26['Coaches_Votes'].fillna(0)
    print("  Coaches votes merged")
else:
    df26['Coaches_Votes'] = 0

# Merge 2026 Wheelo data if available
wheelo_2026_path = "data_wheelo/wheelo_2026.csv"
if os.path.exists(wheelo_2026_path) and WHEELO_FEATURES:
    print("  Merging 2026 Wheelo data...")
    w26 = pd.read_csv(wheelo_2026_path, low_memory=False)
    w26['Round_num'] = pd.to_numeric(w26['Round'], errors='coerce')
    w26 = w26.rename(columns={'Player': 'Player_Name'})
    # Team joins the key, matching brownlow_model.py — without it two players
    # sharing a name take each other's ratings. Wheelo says 'Brisbane' where
    # Playing.for says 'Brisbane Lions', so normalise BEFORE the rename or every
    # Brisbane player silently loses all 18 Wheelo features to the 0-fill below.
    # Training applies the identical replace for the identical reason.
    w26['Team'] = w26['Team'].replace(feat.WHEELO_TEAM_FIXES)
    w26 = w26.rename(columns={'Team': 'Playing.for'})
    wheelo_cols = [c for c in WHEELO_FEATURES if c in w26.columns]
    df26 = df26.merge(w26[['Player_Name', 'Playing.for', 'Round_num'] + wheelo_cols],
                      on=['Player_Name', 'Playing.for', 'Round_num'], how='left')

# Fill missing Wheelo features with 0
for f in WHEELO_FEATURES:
    if f not in df26.columns:
        df26[f] = 0
    else:
        df26[f] = df26[f].fillna(0)

# Quarter premium features
if 'Rating_Q4' in df26.columns and 'Rating_Q1' in df26.columns:
    df26['Rating_Q4_premium'] = df26['Rating_Q4'] - df26[['Rating_Q1','Rating_Q2','Rating_Q3']].mean(axis=1)
    df26['Best_quarter_rating'] = df26[['Rating_Q1','Rating_Q2','Rating_Q3','Rating_Q4']].max(axis=1)

# Build relative game features
print("Building relative features...")
df26['Game_ID'] = df26['Season'].astype(str)+'_'+df26['Round_num'].astype(str)+'_'+df26['Home.team'].astype(str)+'_'+df26['Away.team'].astype(str)

df26 = feat.build_game_rank_features(df26, RANK_STATS, fill_missing=True)
df26 = feat.build_rank_flags(df26)

# Form and momentum features
print("Building form and momentum features...")
df26 = df26.sort_values(['Player_Name', 'Round_num']).reset_index(drop=True)

df26 = feat.build_form_features(df26, ['Player_Name'])

# Fill any missing features
for f in FEATURES:
    if f not in df26.columns:
        df26[f] = 0

# ── Predict ──────────────────────────────────────────────────
print("\nGenerating predictions...")
df26_valid = df26[df26['Round_num'].notna()].copy().reset_index(drop=True)
df26_valid['Brownlow.Votes'] = 0

# ── Per-game model routing ───────────────────────────────────
# A game routes on whether ITS OWN rows carry any coaches votes, not on a round
# number: rounds are published in blocks but the rule should follow the data, so
# a late or partial release routes correctly with no constant to maintain.
#
# Zero votes across a whole game means "not published yet" rather than "nobody
# polled" — coaches award 5-4-3-2-1 in every game, so a played game always has
# nonzero votes somewhere once released.
_has_cv = df26_valid.groupby('Game_ID')['Coaches_Votes'].transform(lambda s: (s != 0).any())
df26_valid['model_source'] = np.where(_has_cv, 'full', 'no_cv')
if MODEL_NOCV is None:
    df26_valid['model_source'] = 'full'          # variant unavailable

_n_nocv_games = df26_valid.loc[df26_valid['model_source'] == 'no_cv', 'Game_ID'].nunique()
_n_full_games = df26_valid.loc[df26_valid['model_source'] == 'full', 'Game_ID'].nunique()
print(f"  Routing: {_n_full_games} game(s) -> full model, {_n_nocv_games} -> no-coaches variant")

for _c in ('P_1', 'P_2', 'P_3'):
    df26_valid[_c] = 0.0


def _fill_probs(_mask, _mdl, _feats):
    """Predict one routing group in place. Each model gets only its own feature
    list, so the variant never sees a coaches column."""
    if not _mask.any():
        return
    _pr = _mdl.predict_proba(df26_valid.loc[_mask, _feats])
    _cl = list(_mdl.classes_)
    for _v in (1, 2, 3):
        if _v in _cl:
            df26_valid.loc[_mask, f'P_{_v}'] = _pr[:, _cl.index(_v)]


_m_full = df26_valid['model_source'] == 'full'
_m_nocv = df26_valid['model_source'] == 'no_cv'
_fill_probs(_m_full, model, FEATURES)
if MODEL_NOCV is not None:
    _fill_probs(_m_nocv, MODEL_NOCV, FEATURES_NOCV)
    # Blank the coaches columns on variant rows AFTER predicting. They were
    # computed over a game with no votes, so every one of them is an artefact —
    # BOG_Coaches and Top3_Coaches would both read 1 for all 22 players. NaN
    # says "not available"; 1 would say "led the game for coaches votes".
    for _c in COACHES_FEATURES:
        if _c in df26_valid.columns:
            df26_valid.loc[_m_nocv, _c] = np.nan

df26_valid['Poll_Prob'] = df26_valid['P_1']+df26_valid['P_2']+df26_valid['P_3']
df26_valid['Exp_Votes'] = df26_valid['P_1']*1+df26_valid['P_2']*2+df26_valid['P_3']*3

# Disambiguate players who share a name but play for different teams
player_teams = df26_valid.groupby('Player_Name')['Playing.for'].nunique()
duplicate_names = player_teams[player_teams > 1].index
df26_valid['Player_Name'] = df26_valid.apply(
    lambda r: f"{r['Player_Name']} ({r['Playing.for']})" if r['Player_Name'] in duplicate_names else r['Player_Name'],
    axis=1
)

df26_valid.to_csv("predictions/game_level_2026.csv", index=False)

totals = df26_valid.groupby('Player_Name').agg(
    Team=('Playing.for','last'), Games=('Round_num','count'),
    Actual_Votes=('Brownlow.Votes','sum'), Exp_Total_Votes=('Exp_Votes','sum'),
    Avg_Poll_Prob=('Poll_Prob','mean'), Exp_3vote_games=('P_3','sum'),
    Exp_2vote_games=('P_2','sum'), Exp_1vote_games=('P_1','sum'),
).reset_index().sort_values('Exp_Total_Votes', ascending=False)

totals.to_csv("predictions/season_2026.csv", index=False)
current_round = int(df26_valid['Round_num'].max())

# ── Season projection ─────────────────────────────────────────
TOTAL_HA_ROUNDS = 23
remaining_rounds = max(0, TOTAL_HA_ROUNDS - current_round)

# Per-player average vote probabilities and game count from completed rounds
_probs = df26_valid.groupby('Player_Name').agg(
    p1=('P_1', 'mean'), p2=('P_2', 'mean'), p3=('P_3', 'mean'),
    games_played=('Round_num', 'count'),
).reset_index()
_probs['p0'] = (1 - _probs['p1'] - _probs['p2'] - _probs['p3']).clip(lower=0)

# Monte Carlo: simulate 10,000 realisations of the rounds already played,
# take 10th/90th percentile — floor/ceiling centred on current Exp_Total_Votes
_floor_map, _ceiling_map = {}, {}
_rng = np.random.default_rng(42)
_vote_vals = np.array([0, 1, 2, 3])
for _, _r in _probs.iterrows():
    _p = np.array([_r['p0'], _r['p1'], _r['p2'], _r['p3']]).clip(0)
    _p /= _p.sum()
    _sim = _rng.multinomial(int(_r['games_played']), _p, size=10_000) @ _vote_vals
    _floor_map[_r['Player_Name']] = float(np.percentile(_sim, 10))
    _ceiling_map[_r['Player_Name']] = float(np.percentile(_sim, 90))

season_proj = totals[['Player_Name', 'Team', 'Actual_Votes', 'Games', 'Exp_Total_Votes']].copy()
season_proj = season_proj.rename(columns={'Player_Name': 'Player', 'Games': 'Games_Played'})
season_proj['Avg_Predicted_Per_Game'] = (season_proj['Exp_Total_Votes'] / season_proj['Games_Played']).round(4)
season_proj['Remaining_Rounds'] = remaining_rounds
season_proj['Projected_Remaining'] = (season_proj['Avg_Predicted_Per_Game'] * remaining_rounds).round(2)
season_proj['Season_Total_Projected'] = (season_proj['Actual_Votes'] + season_proj['Projected_Remaining']).round(2)
season_proj['Floor_Projection'] = season_proj['Player'].map(_floor_map).fillna(0).round(1)
season_proj['Ceiling_Projection'] = season_proj['Player'].map(_ceiling_map).fillna(0).round(1)
season_proj = season_proj[['Player', 'Team', 'Actual_Votes', 'Games_Played',
                            'Avg_Predicted_Per_Game', 'Remaining_Rounds',
                            'Projected_Remaining', 'Season_Total_Projected',
                            'Floor_Projection', 'Ceiling_Projection']]\
    .sort_values('Season_Total_Projected', ascending=False).reset_index(drop=True)
season_proj.to_csv("predictions/season_projection_2026.csv", index=False)
print(f"Season projection saved ({remaining_rounds} rounds remaining of {TOTAL_HA_ROUNDS}).")

print(f"\nOK 2026 predictions - {len(totals)} players through Round {current_round}")
print("\n=== TOP 15 PROJECTED (v4.0) ===")
print(totals[['Player_Name','Team','Games','Exp_Total_Votes','Avg_Poll_Prob']].head(15).to_string(index=False))
print("\nDone. Refresh dashboard.")
