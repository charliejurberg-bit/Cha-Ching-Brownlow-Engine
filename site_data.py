"""site_data.py — the dashboard's data loaders, without Streamlit.

The public site is moving from Streamlit to the Next.js app in the
cha-ching-brownlow repo. Python stays the engine and never runs on Vercel:
export_site.py calls these loaders and writes small per-page JSON files under
site/data/, which the Next.js pages read from raw.githubusercontent.com exactly
as the landing page already reads site/landing.json.

Every function here is a port of the dashboard.py function OF THE SAME NAME,
minus its @st.cache_data decorator, and must produce the same frame. The two
copies are deliberate and temporary: dashboard.py is retired once every public
page has moved, and until then touching it risks the live app. So a change to
one of these loaders in dashboard.py must be mirrored here, or the site and the
Streamlit app disagree. scripts/check_site_parity.py compares them.

Caching is a plain per-process memo, because the only caller is a batch export.
Callers must not mutate a returned frame; every function that alters one copies
it first, as the dashboard versions do.
"""

import os

import numpy as np
import pandas as pd

import season as season_cfg

LIVE_SEASON = season_cfg.LIVE_SEASON
PRED_DIR = "predictions"
_SI_PATH = "data_advanced/score_involvements.csv"
_SI_COL = 'Score_Involvements_Actual'

_memo = {}


def _cached(fn):
    def wrap(*args):
        key = (fn.__name__,) + args
        if key not in _memo:
            _memo[key] = fn(*args)
        return _memo[key]
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap


def available_seasons():
    """Seasons with a predictions/season_<s>.csv, newest first (AVAILABLE_SEASONS)."""
    out = []
    if os.path.exists(PRED_DIR):
        for f in os.listdir(PRED_DIR):
            if f.startswith("season_") and f.endswith(".csv"):
                try:
                    out.append(int(f.replace("season_", "").replace(".csv", "")))
                except ValueError:
                    pass
    return sorted(out, reverse=True)


# ── Round display law ──────────────────────────────────────────
# Fourth copy of the constant (dashboard.py, draft_posts.py, streaks.py). See
# CLAUDE.md, "Round numbering": display only, never applied to stored values.
_OPENING_ROUND_FROM = 2024


def display_round(round_num, season):
    try:
        rn = int(round_num)
        sn = int(season)
    except (TypeError, ValueError):
        return round_num
    return rn - 1 if sn >= _OPENING_ROUND_FROM else rn


# ── Identity ───────────────────────────────────────────────────
_TEAM_ALIASES = {
    'Footscray': 'Western Bulldogs',
    'GWS': 'Greater Western Sydney',
    'Kangaroos': 'North Melbourne',
}


def _fix_team_names(df):
    for col in ('Team', 'Playing.for'):
        if col in df.columns:
            df[col] = df[col].replace(_TEAM_ALIASES)
    return df


@_cached
def _player_id_map():
    """(Player, Team, Season) -> fitzRoy player ID. See dashboard._player_id_map."""
    for path in ("fitzroy_stats_all.csv", "fitzroy_stats_2015_2025.csv"):
        if os.path.exists(path):
            try:
                src = pd.read_csv(path, usecols=["Player", "Team", "Season", "ID"])
            except Exception:
                continue
            src = _fix_team_names(src).dropna(subset=["Player", "Team", "Season", "ID"])
            src["Season"] = src["Season"].astype(int)
            src = src.drop_duplicates(["Player", "Team", "Season"])
            return {(r.Player, r.Team, r.Season): r.ID for r in src.itertuples(index=False)}
    return {}


def _disambiguate_players(df):
    """'Name (Team)' for names carried by more than one fitzRoy ID."""
    if 'Player_Name' not in df.columns or 'Season' not in df.columns:
        return df
    team_col = 'Team' if 'Team' in df.columns else ('Playing.for' if 'Playing.for' in df.columns else None)
    if team_col is None:
        return df
    df = df.copy()
    df['_base_name'] = df['Player_Name']
    id_map = _player_id_map()
    if not id_map:
        return df
    seasons = pd.to_numeric(df['Season'], errors='coerce').astype('Int64')
    df['_pid'] = [
        id_map.get((n, t, int(s))) if pd.notna(s) else None
        for n, t, s in zip(df['_base_name'], df[team_col], seasons)
    ]
    nunique_id = df.dropna(subset=['_pid']).groupby('_base_name')['_pid'].nunique()
    collision = set(nunique_id[nunique_id > 1].index)
    if collision:
        sub = df[df['_base_name'].isin(collision)]
        sort_cols = [c for c in ('Season', 'Round_num') if c in sub.columns]
        last_team = (sub.dropna(subset=['_pid']).sort_values(sort_cols)
                        .groupby('_pid')[team_col].last())
        mask = df['_base_name'].isin(collision)
        suffix = df.loc[mask, '_pid'].map(last_team).fillna(df.loc[mask, team_col])
        df.loc[mask, 'Player_Name'] = df.loc[mask, '_base_name'] + ' (' + suffix.astype(str) + ')'
    return df.drop(columns=['_pid'])


# ── Season and game frames ─────────────────────────────────────
@_cached
def load_game(season):
    path = f"{PRED_DIR}/game_level_{season}.csv"
    if not os.path.exists(path):
        return None
    return _fit_game_probs(_attach_real_si(
        _disambiguate_players(_fix_team_names(pd.read_csv(path, low_memory=False))), season))


@_cached
def load_season(season):
    path = f"{PRED_DIR}/season_{season}.csv"
    if not os.path.exists(path):
        return None
    sdf = _fix_team_names(pd.read_csv(path))
    g = load_game(season)
    if g is None or '_base_name' not in g.columns:
        return sdf
    split = set(g.loc[g['Player_Name'] != g['_base_name'], '_base_name'])
    if not split:
        return sdf
    team_col = 'Team' if 'Team' in g.columns else 'Playing.for'
    rebuilt = g[g['_base_name'].isin(split)].groupby('Player_Name').agg(
        Team=(team_col, 'last'), Games=('Round_num', 'count'),
        Actual_Votes=('Brownlow.Votes', 'sum'), Exp_Total_Votes=('Exp_Votes', 'sum'),
        Avg_Poll_Prob=('Poll_Prob', 'mean'), Exp_3vote_games=('P_3', 'sum'),
        Exp_2vote_games=('P_2', 'sum'), Exp_1vote_games=('P_1', 'sum'),
    ).reset_index()
    keep = sdf[~sdf['Player_Name'].isin(split)]
    out = pd.concat([keep, rebuilt], ignore_index=True)
    return out.sort_values('Exp_Total_Votes', ascending=False).reset_index(drop=True)


def _attach_real_si(df, season):
    if df is None or not os.path.exists(_SI_PATH):
        return df
    if 'ID' not in df.columns or 'Round_num' not in df.columns:
        return df
    si = pd.read_csv(_SI_PATH, usecols=['Season', 'Round_num', 'ID', _SI_COL])
    si = si[si['Season'] == season].drop(columns='Season')
    si = si.drop_duplicates(['Round_num', 'ID'])
    if si.empty:
        return df
    out = df.copy()
    out['_si_id'] = pd.to_numeric(out['ID'], errors='coerce')
    si['ID'] = si['ID'].astype('int64')
    out = out.merge(si.rename(columns={'ID': '_si_id'}),
                    on=['_si_id', 'Round_num'], how='left')
    return out.drop(columns='_si_id')


_HARD_VOTE_BY_RANK = {1: 3, 2: 2, 3: 1}


def _game_key(g):
    if 'Game_ID' in g.columns:
        return g['Game_ID'].astype(str)
    return (g['Round_num'].astype(str) + '|' +
            g['Home.team'].astype(str) + '|' + g['Away.team'].astype(str))


_GAME_PROB_COLS = ('P_1', 'P_2', 'P_3')


def _fit_game_probs(df):
    """P_1_game/P_2_game/P_3_game: each game hands out one 3, one 2, one 1.
    See dashboard._fit_game_probs for the measurement behind it."""
    if df is None or not set(_GAME_PROB_COLS) <= set(df.columns):
        return df
    if 'Game_ID' not in df.columns and not {'Home.team', 'Away.team'} <= set(df.columns):
        return df

    def _txt(s):
        return s.astype(object).where(s.notna(), '').astype(str)

    key = _game_key(df)
    if 'Season' in df.columns:
        key = df['Season'].astype(str) + '|' + key
    ok = key.notna().to_numpy()
    who = _txt(df['Player_Name'])
    if 'ID' in df.columns:
        who = who + '|' + _txt(df['ID'])
    pair = (_txt(key) + '#' + who).to_numpy()
    first = ok & ~pd.Series(pair).duplicated().to_numpy()
    if not first.any():
        return df
    raw = (df[list(_GAME_PROB_COLS)].apply(pd.to_numeric, errors='coerce')
           .fillna(0.0).to_numpy(dtype=float))
    P = raw[first]
    M = np.clip(np.column_stack([1.0 - P.sum(1), P]), 1e-12, None)
    codes, uniq = pd.factorize(key.to_numpy()[first])
    k = len(uniq)
    size = np.bincount(codes, minlength=k).astype(float)
    target = np.column_stack([np.maximum(size - 3, 1e-9), np.ones((k, 3))])
    for _ in range(1000):
        M /= M.sum(1, keepdims=True)
        col = np.column_stack([np.bincount(codes, weights=M[:, j], minlength=k)
                               for j in range(4)])
        if np.abs(col - target).max() < 1e-9:
            break
        M *= (target / col)[codes]
    M /= M.sum(1, keepdims=True)
    back = pd.Index(pair[first]).get_indexer(pair)
    out = df.copy()
    for j, c in enumerate(_GAME_PROB_COLS, start=1):
        vals = raw[:, j - 1].copy()
        vals[ok] = M[back[ok], j]
        out[f'{c}_game'] = vals
    return out


@_cached
def load_game_rounded(season):
    """Game-level frame with a Hard_Votes column holding the 3/2/1 award."""
    g = load_game(season)
    if g is None or 'Exp_Votes' not in g.columns:
        return None
    g = g.copy()
    g['_gkey'] = _game_key(g)
    _sort = ['_gkey', 'Exp_Votes'] + [c for c in ('Poll_Prob', 'P_3') if c in g.columns] + ['Player_Name']
    _asc = [True, False] + [False] * (len(_sort) - 3) + [True]
    g = g.sort_values(_sort, ascending=_asc)
    g['Hard_Votes'] = (g.groupby('_gkey').cumcount() + 1).map(_HARD_VOTE_BY_RANK).fillna(0).astype(int)
    return g


@_cached
def round_vote_matrix(season, rounded):
    """(rounds, {player: {round_num: value}}); a round not played is ABSENT."""
    g = load_game_rounded(season) if rounded else load_game(season)
    col = 'Hard_Votes' if rounded else 'Exp_Votes'
    if g is None or g.empty or col not in g.columns or 'Round_num' not in g.columns:
        return [], {}
    _w = g.groupby(['Player_Name', 'Round_num'])[col].sum().unstack()
    _rounds = [int(c) for c in _w.columns]
    _map = {p: {int(r): float(v) for r, v in row.items() if pd.notna(v)}
            for p, row in _w.to_dict('index').items()}
    return _rounds, _map


@_cached
def load_season_rounded(season):
    """Season totals under the 3-2-1 board, in load_season's schema."""
    g = load_game_rounded(season)
    if g is None or g.empty:
        return None
    team_col = 'Team' if 'Team' in g.columns else 'Playing.for'
    out = g.groupby('Player_Name').agg(
        Team=(team_col, 'last'),
        Games=('Hard_Votes', 'size'),
        Exp_Total_Votes=('Hard_Votes', 'sum'),
        _Decimal_Total=('Exp_Votes', 'sum'),
    ).reset_index()
    _counts = g.groupby('Player_Name')['Hard_Votes'].value_counts().unstack(fill_value=0)
    for _v, _c in ((3, 'Exp_3vote_games'), (2, 'Exp_2vote_games'), (1, 'Exp_1vote_games')):
        _src = _counts[_v] if _v in _counts.columns else None
        out[_c] = (out['Player_Name'].map(_src).fillna(0) if _src is not None else 0)
        out[_c] = out[_c].astype(int)
    _polled = out['Exp_3vote_games'] + out['Exp_2vote_games'] + out['Exp_1vote_games']
    out['Avg_Poll_Prob'] = _polled / out['Games'].where(out['Games'] > 0)
    if 'Brownlow.Votes' in g.columns:
        out['Actual_Votes'] = out['Player_Name'].map(
            g.groupby('Player_Name')['Brownlow.Votes'].sum()).fillna(0)
    else:
        out['Actual_Votes'] = 0
    out = out.sort_values(['Exp_Total_Votes', '_Decimal_Total'], ascending=False)
    return out.drop(columns=['_Decimal_Total']).reset_index(drop=True)


@_cached
def load_game_career():
    """Every season's game frame stacked, with names disambiguated ACROSS seasons.

    dashboard.load_game_career reads the CSVs again through load_all_historical;
    this builds the same frame from load_game, so each row also keeps the name
    the season view shows it under, in `_season_name`. The two differ only for
    a person whose name collides in some other season: 'Josh Kennedy' in a
    season with one of them, 'Josh Kennedy (Sydney)' in the career view.
    """
    frames = []
    for s in sorted(available_seasons()):
        g = load_game(s)
        if g is None:
            continue
        g = g.copy()
        g['Season'] = s
        g['_season_name'] = g['Player_Name']
        g['Player_Name'] = g['_base_name'] if '_base_name' in g.columns else g['Player_Name']
        g = g.drop(columns=[c for c in ('_base_name',) if c in g.columns])
        frames.append(g)
    if not frames:
        return None
    g = pd.concat(frames, ignore_index=True)
    if 'Playing.for' in g.columns:
        g['Team'] = g['Team'].fillna(g['Playing.for']) if 'Team' in g.columns else g['Playing.for']
    return _disambiguate_players(g)


def efficiency_from_df(df):
    """dashboard._efficiency_from_df: the Polling DNA rates per player."""
    overall = df.groupby('Player_Name').agg(
        Games=('Round_num', 'count'),
        Total_Votes=('Brownlow.Votes', 'sum'),
        Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()
    hd = df[df['Disposals'] >= 30].groupby('Player_Name').agg(
        HD_Games=('Round_num', 'count'),
        HD_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()
    wins = df[df['Is_Win'] == 1].groupby('Player_Name').agg(
        Win_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()
    losses = df[df['Is_Loss'] == 1].groupby('Player_Name').agg(
        Loss_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()
    eff = overall.merge(hd, on='Player_Name', how='left')
    eff = eff.merge(wins, on='Player_Name', how='left')
    return eff.merge(losses, on='Player_Name', how='left')


def voted_seasons(g):
    """Seasons whose game file carries a count. The live season reads 0 votes
    until season_rollover.py backfills it, and must not dilute career rates."""
    tot = g.groupby('Season')['Brownlow.Votes'].sum()
    return sorted(int(s) for s in tot[tot > 0].index)


def load_best_odds():
    path = season_cfg.data_path("best_odds.csv")
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None


@_cached
def load_season_projection():
    path = f"{PRED_DIR}/season_projection_{LIVE_SEASON}.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None
