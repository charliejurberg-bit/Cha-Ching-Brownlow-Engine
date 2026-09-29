"""export_site.py — write the JSON the Next.js site reads.

    python export_site.py                  every season
    python export_site.py 2026 2025        just these

Output lives under site/data/ and is git tracked, like site/landing.json: the
Next.js app (cha-ching-brownlow repo) fetches it from raw.githubusercontent.com
on master and revalidates hourly, so a commit and push is what publishes it.

One file per page per season. Each carries only what that page renders, already
computed, so the site does no modelling and never sees the 137 MB of game-level
CSVs. The logic is the Streamlit page's, moved rather than rewritten: rank
order, movement arrows, the Floor-Ceiling lift and the round grid all follow
the Leaderboard block in dashboard.py line for line (see the comments there for
why each rule exists). site_data.py holds the loaders.

Pages exported: Leaderboard, Player Profile, Game Analysis, Stat Filter, Model
Comparison, Live Tracker (tracker.json) and Polls a Vote (polls.json).
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import site_data as sd

OUT_DIR = os.path.join("site", "data")


def _num(x, dp):
    """A float rounded for the wire, or None for missing."""
    if x is None or pd.isna(x):
        return None
    v = round(float(x), dp)
    return int(v) if dp == 0 else v


def _sid(s):
    """A season id for the wire: an int, except AFLW's two 2022 seasons, which
    are 2022.6 and 2022.7 (aflw/site_frames.py). int() would merge them."""
    f = float(s)
    return int(f) if f.is_integer() else round(f, 1)


def _movement(board, g, col, live):
    """Rank change since the previous round, measured in the board's own units.
    Live season only, as on the page."""
    if not live or g is None or g.empty:
        return {}
    max_rnd = int(g['Round_num'].max())
    cur = g[g['Round_num'] == max_rnd].groupby('Player_Name')[col].sum()
    a = board[['Player_Name', 'Exp_Total_Votes']].copy()
    a['Prev_Total'] = a['Exp_Total_Votes'] - a['Player_Name'].map(cur).fillna(0)
    a['Curr_Rank'] = range(1, len(a) + 1)
    prev = a.sort_values('Prev_Total', ascending=False).reset_index(drop=True)
    prev['Prev_Rank'] = range(1, len(prev) + 1)
    m = a.merge(prev[['Player_Name', 'Prev_Rank']], on='Player_Name')
    m['Move'] = m['Prev_Rank'] - m['Curr_Rank']
    return dict(zip(m['Player_Name'], m['Move']))


def _board(season, rounded, live, slugs):
    """One board (decimal or 3-2-1) in page order, or None if unavailable."""
    board = sd.load_season_rounded(season) if rounded else sd.load_season(season)
    if board is None or board.empty:
        return None
    dp = 0 if rounded else 1

    floor, ceiling = {}, {}
    if live and not rounded:
        proj = sd.load_season_projection()
        if proj is not None and 'Floor_Projection' in proj.columns:
            floor = dict(zip(proj['Player'], proj['Floor_Projection']))
            ceiling = dict(zip(proj['Player'], proj['Ceiling_Projection']))
            # The displayed ceiling is max(p90, 3-2-1 total), never a swap.
            # CLAUDE.md, "Season projection".
            rt = sd.load_season_rounded(season)
            if rt is not None:
                for pn, hv in zip(rt['Player_Name'], rt['Exp_Total_Votes']):
                    if pn in ceiling and float(hv) > float(ceiling[pn]):
                        ceiling[pn] = float(hv)

    g, col = ((sd.load_game_rounded(season), 'Hard_Votes') if rounded
              else (sd.load_game(season), 'Exp_Votes'))
    move = _movement(board, g, col, live)
    rounds, rmap = sd.round_vote_matrix(season, rounded)

    players = []
    for r in board.itertuples(index=False):
        name = str(r.Player_Name)
        pr = rmap.get(name, {})
        row = {
            "name": name,
            "slug": slugs.get(name),
            "team": str(r.Team),
            "games": int(r.Games) if pd.notna(r.Games) else 0,
            "votes": _num(r.Exp_Total_Votes, dp),
            "poll": _num(r.Avg_Poll_Prob, 3),
            "rounds": [_num(pr.get(rn), dp) for rn in rounds],
        }
        if not live:
            # None where the count exists but this player's total was never
            # published (AFLW 2018 and 2019 carry their top 10 only). The men's
            # season files are always complete, so they never reach it.
            row["actual"] = int(r.Actual_Votes) if pd.notna(r.Actual_Votes) else None
        if move.get(name):
            row["move"] = int(move[name])
        if name in ceiling:
            row["floor"] = _num(floor.get(name), 1)
            row["ceiling"] = _num(ceiling.get(name), 1)
        players.append(row)
    return {"rounds": rounds, "players": players}


def export_leaderboard(season, slugs):
    live = season == sd.LIVE_SEASON
    decimal = _board(season, False, live, slugs)
    if decimal is None:
        print(f"  {season}: no season file, skipped")
        return None
    rounded = _board(season, True, live, slugs)
    rounds = decimal["rounds"] or (rounded or {}).get("rounds", [])
    return {
        "season": season,
        "live": live,
        "rounds": rounds,
        "roundLabels": [str(sd.display_round(rn, season)) for rn in rounds],
        "boards": {"decimal": decimal, "rounded": rounded},
    }


# ── Player Profile ─────────────────────────────────────────────
# One file per person, every game of the career, under players/<slug>.json.
# The page filters it to a season or shows it whole, so Profile, DNA and
# Compare (season or career) all read the same rows. profile/<season>.json and
# profile/career.json carry what needs the whole field: the picker, the
# DNA rank, season totals for Compare and, for the live season only, odds.

# Per-game columns: (output key, source column, decimals). Decimals None keeps
# an integer. Columns absent from a season's file export as null.
_GAME_COLS = (
    ("round", "Round_num", None),
    ("team", "Team", "str"),
    ("home", "Home.team", "str"),
    ("away", "Away.team", "str"),
    ("win", "Is_Win", None),
    ("loss", "Is_Loss", None),
    ("disp", "Disposals", None),
    ("goals", "Goals", None),
    ("kicks", "Kicks", None),
    ("clr", "Clearances", None),
    ("cp", "Contested.Possessions", None),
    ("cv", "Coaches_Votes", None),
    ("tck", "Tackles", None),
    ("si", sd._SI_COL, None),
    ("bv", "Brownlow.Votes", None),
    ("ev", "Exp_Votes", 3),
    ("poll", "Poll_Prob", 4),
    ("p1", "P_1", 4), ("p2", "P_2", 4), ("p3", "P_3", 4),
    ("g1", "P_1_game", 4), ("g2", "P_2_game", 4), ("g3", "P_3_game", 4),
)


def _slug(name):
    s = "".join(c.lower() if c.isalnum() else "-" for c in name)
    return "-".join(p for p in s.split("-") if p)


def _col(df, src, dp):
    if src not in df.columns:
        return [None] * len(df)
    if dp == "str":
        # The fixture columns never went through _fix_team_names, so 2007
        # still says Kangaroos there while Team says North Melbourne.
        return [None if pd.isna(v) else sd._TEAM_ALIASES.get(str(v), str(v)) for v in df[src]]
    return [_num(v, 0 if dp is None else dp) for v in df[src]]


def _eff_rows(eff):
    out = {}
    for r in eff.itertuples(index=False):
        out[r.Player_Name] = {
            "games": int(r.Games),
            "poll": _num(r.Poll_Rate, 4),
            "win": _num(r.Win_Poll_Rate, 4),
            "loss": _num(r.Loss_Poll_Rate, 4),
            "hd": _num(r.HD_Poll_Rate, 4),
            "hdGames": 0 if pd.isna(r.HD_Games) else int(r.HD_Games),
        }
    return out


def export_profiles(seasons):
    g = sd.load_game_career()
    if g is None:
        print("  profiles: no game files, skipped")
        return {}
    g = g.sort_values(["Player_Name", "Season", "Round_num"], kind="stable")

    # Slugs from the career name, which is unique per person. A slug collision
    # between two different names (punctuation only) takes a numeric suffix.
    slug_of, taken = {}, set()
    for name in sorted(g["Player_Name"].unique()):
        s, i = _slug(name), 2
        while s in taken:
            s, i = f"{_slug(name)}-{i}", i + 1
        taken.add(s)
        slug_of[name] = s

    pdir = os.path.join(OUT_DIR, "players")
    os.makedirs(pdir, exist_ok=True)
    total = 0
    for name, pg in g.groupby("Player_Name", sort=False):
        obj = {
            "name": name,
            "slug": slug_of[name],
            "team": str(pg["Team"].iloc[-1]),
            "games": {"season": [_sid(s) for s in pg["Season"]]},
        }
        obj["games"].update({k: _col(pg, src, dp) for k, src, dp in _GAME_COLS})
        # The season view's name, only where it differs from the career one.
        sn = [None if a == name else a for a in pg["_season_name"]]
        if any(sn):
            obj["games"]["seasonName"] = sn
        total += _write(os.path.join(pdir, f"{slug_of[name]}.json"), obj)
    # A player file for a person no longer in any season would be stale.
    for f in os.listdir(pdir):
        if f.endswith(".json") and f[:-5] not in taken:
            os.remove(os.path.join(pdir, f))
    print(f"  players: {len(slug_of)} files, {total / 1024 / 1024:.1f} MB")

    # Season-view name -> slug, per season, for the pickers and the Leaderboard.
    season_slug = {}
    for (s, sn), name in (g.groupby(["Season", "_season_name"])["Player_Name"].first().items()):
        season_slug.setdefault(_sid(s), {})[sn] = slug_of[name]

    prdir = os.path.join(OUT_DIR, "profile")
    odds = sd.load_best_odds()
    for s in seasons:
        board = sd.load_season(s)
        gs = sd.load_game(s)
        if board is None or gs is None:
            continue
        live = s == sd.LIVE_SEASON
        eff = _eff_rows(sd.efficiency_from_df(gs))
        players = []
        for r in board.itertuples(index=False):
            nm = str(r.Player_Name)
            if nm not in season_slug.get(s, {}):
                continue
            players.append({
                "name": nm,
                "slug": season_slug[s][nm],
                "team": str(r.Team),
                "expTotal": _num(r.Exp_Total_Votes, 2),
                "avgPoll": _num(r.Avg_Poll_Prob, 4),
                "eff": eff.get(nm),
            })
        players.sort(key=lambda p: p["name"])
        obj = {"season": s, "live": live, "maxRound": int(gs["Round_num"].max()), "players": players}
        # Odds are the live season's market. dashboard.py joins them onto any
        # season by name, which prices a 2019 comparison at 2026 odds; here
        # they ship only with the season they belong to.
        if live and odds is not None:
            obj["odds"] = {str(r.player): [_num(r.best_odds, 2), _num(r.implied_prob, 3)]
                           for r in odds.itertuples(index=False) if pd.notna(r.best_odds)}
        _write(os.path.join(prdir, f"{s}.json"), obj)

    voted = sd.voted_seasons(g)
    eff_c = _eff_rows(sd.efficiency_from_df(g[g["Season"].isin(voted)]))
    last = g.groupby("Player_Name").agg(team=("Team", "last"), games=("Round_num", "size"))
    career = [{"name": n, "slug": slug_of[n], "team": str(r.team), "games": int(r.games),
               "eff": eff_c.get(n)} for n, r in last.iterrows()]
    career.sort(key=lambda p: p["name"])
    _write(os.path.join(prdir, "career.json"),
           {"votedSeasons": voted, "players": career})
    print(f"  profile: {len(seasons)} season indexes + career ({len(career)} players)")
    return season_slug


# ── Game Analysis ──────────────────────────────────────────────
# games/<season>.json: every match of the season with its players ranked by
# expected votes, as the Streamlit page draws them. Player rows are arrays to
# keep a season small: [name, side, exp votes, fitted P(3) %, disposals,
# contested possessions, clearances, goals, coaches votes]. Side is 0 for the
# home club, 1 for the away club, or the club name if it matches neither.
_GA_ROW = ("name", "side", "ev", "p3", "disp", "cp", "clr", "goals", "cv")


def _side(team, head):
    t = sd._TEAM_ALIASES.get(str(team), str(team))
    home = sd._TEAM_ALIASES.get(str(head["Home.team"]), str(head["Home.team"]))
    away = sd._TEAM_ALIASES.get(str(head["Away.team"]), str(head["Away.team"]))
    return 0 if t == home else 1 if t == away else t


def _int0(v):
    return 0 if v is None or pd.isna(v) else int(round(float(v)))


def export_games(season, slugs):
    g = sd.load_game(season)
    if g is None:
        return None
    g = g.copy()
    g["_key"] = g["Round_num"].astype(str) + "|" + g["Home.team"] + " vs " + g["Away.team"]
    p3col = "P_3_game" if "P_3_game" in g.columns else "P_3"
    games = []
    # File order of first appearance, as the page's drop_duplicates takes it.
    for key in g["_key"].drop_duplicates():
        gp = g[g["_key"] == key]
        # One player can sit in a game twice (78 rows in 2025, see CLAUDE.md);
        # the page listed both copies. Dedupe on the player, keeping the first.
        gp = gp.drop_duplicates("Player_Name")
        gp = gp.sort_values("Exp_Votes", ascending=False, kind="stable")
        head = gp.iloc[0]
        games.append({
            "round": int(head["Round_num"]),
            "home": sd._TEAM_ALIASES.get(str(head["Home.team"]), str(head["Home.team"])),
            "away": sd._TEAM_ALIASES.get(str(head["Away.team"]), str(head["Away.team"])),
            "homeScore": None if pd.isna(head["Home.score"]) else int(head["Home.score"]),
            "awayScore": None if pd.isna(head["Away.score"]) else int(head["Away.score"]),
            "players": [
                # Rounded once, to what the page shows and the way it rounds:
                # a second rounding on the site moved ~1 cell in 60 by 0.01.
                [str(n), _side(t, head), 0.0 if pd.isna(ev) else round(float(ev), 2),
                 int(round((0 if pd.isna(p3) else float(p3)) * 100)),
                 _int0(d), _int0(cp), _int0(c), _int0(gl), _int0(cv)]
                for n, t, ev, p3, d, cp, c, gl, cv in zip(
                    gp["Player_Name"], gp["Team"], gp["Exp_Votes"], gp[p3col], gp["Disposals"],
                    gp["Contested.Possessions"], gp["Clearances"], gp["Goals"], gp["Coaches_Votes"])
            ],
        })
    return {"season": season, "live": season == sd.LIVE_SEASON, "row": list(_GA_ROW),
            "slugs": {n: slugs[n] for n in g["Player_Name"].unique() if n in slugs},
            "games": games}


# ── Stat Filter ────────────────────────────────────────────────
# statfilter.json: every game 1990 on (sd.load_stat_filter_frame), for the
# page to filter in the browser. Visitors combine nine thresholds with player,
# club, result and season, so nothing here can be precomputed; instead the
# frame ships whole, about 1.3 MB gzipped.
#
# Encoding: rows sorted by season then round (stable). Each column is a string
# with one character per row from _SF_ALPHA, value = index; the last character
# means null. Stats are floored first: for a whole-number threshold t,
# x >= t exactly when floor(x) >= t, so every filter the page offers gives the
# same answer. RatingPoints goes negative and carries an offset. Player is two
# characters, an index into `players`.
_SF_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_SF_NULL = len(_SF_ALPHA) - 1
_SF_STATS = (  # key, column, offset
    ("bv", "Brownlow.Votes", 0), ("disp", "Disposals", 0), ("goals", "Goals", 0),
    ("kicks", "Kicks", 0), ("clr", "Clearances", 0), ("cp", "Contested.Possessions", 0),
    ("cv", "Coaches_Votes", 0), ("tck", "Tackles", 0), ("si", sd._SI_COL, 0),
    ("rating", "RatingPoints", 12),
)


def _sf_col(values, offset=0):
    out = []
    for x in values:
        if x is None or pd.isna(x):
            out.append(_SF_ALPHA[_SF_NULL])
            continue
        v = int(np.floor(float(x))) + offset
        if not 0 <= v < _SF_NULL:
            raise SystemExit(f"statfilter: value {x} (+{offset}) outside the one-character range")
        out.append(_SF_ALPHA[v])
    return "".join(out)


def export_stat_filter():
    g, meta = sd.load_stat_filter_frame()
    if g is None:
        return None
    g = g.sort_values(["Season", "Round_num"], kind="stable").reset_index(drop=True)
    ids = sorted(g["ID"].unique())
    if len(ids) > len(_SF_ALPHA) ** 2:
        raise SystemExit("statfilter: more players than two characters can index")
    pidx = {pid: i for i, pid in enumerate(ids)}
    newest = g.drop_duplicates("ID", keep="last").set_index("ID")["Player_Name"]
    teams = sorted(g["Team"].dropna().astype(str).unique())
    tidx = {t: i for i, t in enumerate(teams)}
    A = _SF_ALPHA
    seasons = []
    for s, grp in g.groupby("Season", sort=True):
        seasons.append([int(s), int(grp.index[0]), len(grp)])
    result = ["W" if w == 1 else "L" if l == 1 else "D" for w, l in zip(g["Is_Win"], g["Is_Loss"])]
    obj = {
        "n": len(g),
        "liveSeason": sd.LIVE_SEASON,
        "alphabet": A,
        "seasons": seasons,
        "round": _sf_col(g["Round_num"]),
        "result": "".join(result),
        "player": "".join(A[pidx[p] // len(A)] + A[pidx[p] % len(A)] for p in g["ID"]),
        "team": "".join(A[tidx[str(t)]] for t in g["Team"]),
        "stats": {k: _sf_col(g[c], off) if c in g.columns else A[_SF_NULL] * len(g)
                  for k, c, off in _SF_STATS},
        "offsets": {k: off for k, _, off in _SF_STATS if off},
        "players": [[int(p), str(newest[p]), meta["labels"][p]] for p in ids],
        "teams": teams,
        "floors": {k: meta["floors"][c] for k, c, _ in _SF_STATS if c in meta["floors"]},
        "nullIdsDropped": meta["null_ids_dropped"],
    }
    return obj


# ── Model Comparison ───────────────────────────────────────────
# modelcomp.json: the consensus table (both vote scales) and the Insights tab,
# finished, so the page only filters and draws. The consensus logic is the
# Model Comparison block of dashboard.py, moved with the same pandas calls so
# ranks come out identical. One change: the dashboard gathers candidates into a
# set and sorts them with an unstable sort, so tied consensus rows swap places
# between runs (CLAUDE.md, "Two page comparisons can differ run to run"). Here
# candidates are iterated in sorted order and sorted stably, so ties are fixed.
import re as _re

_MC_TEAM_COLOURS = {
    'Collingwood': '#4a4a4a', 'Geelong': '#1b3a6b', 'Port Adelaide': '#2e7d7d',
    'Western Bulldogs': '#a33333', 'Brisbane Lions': '#6b1a2f', 'Brisbane': '#6b1a2f',
    'Sydney': '#c0392b', 'Hawthorn': '#8b5e3c', 'Fremantle': '#6c3483', 'GWS': '#c06a20',
    'Greater Western Sydney': '#c06a20', 'Carlton': '#1a3a5c', 'Melbourne': '#1a3060',
    'Richmond': '#8b7a00', 'West Coast': '#003087', 'Adelaide': '#c72c41',
    'Essendon': '#cc0000', 'St Kilda': '#cc2222', 'Gold Coast': '#e07000',
    'North Melbourne': '#003fa0',
}
_NAME_SUFFIX_RE = _re.compile(r'\s+(?:Jr\.?|Sr\.?|Snr\.?|II|III|IV|V)$', _re.IGNORECASE)
_UNICODE_DASHES_RE = _re.compile(r'[‐‑‒–—―−﹘﹣－]')


def _normalise_name(name):
    """dashboard.normalise_name: the cross-model match key."""
    if pd.isna(name):
        return ''
    s = str(name).title().strip()
    s = _UNICODE_DASHES_RE.sub('-', s)
    s = s.replace("'", '').replace('-', ' ')
    while '  ' in s:
        s = s.replace('  ', ' ')
    return _NAME_SUFFIX_RE.sub('', s).strip()


def _mc_name_reference(season=None):
    path = sd.season_cfg.data_path("afltables_{s}.csv", season)
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    df['Round_num'] = pd.to_numeric(df['Round'], errors='coerce')
    df = df.dropna(subset=['Round_num'])
    df['Player_Name'] = df['First.name'].str.strip() + ' ' + df['Surname'].str.strip()
    return df[['Player_Name', 'Playing.for', 'Round_num']]


def _mc_feed(csv_path, team_col=None, team_fixes=None, label='feed', season=None):
    """dashboard._load_csv_fallback + _resolve_feed_names."""
    import features as feat
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if 'Rank' not in df.columns:
        df['Rank'] = df.index + 1
    ref = _mc_name_reference(season)
    if ref.empty or df.empty or 'Player' not in df.columns:
        return df
    if team_col and team_col in df.columns:
        fd = df.copy()
        if team_fixes:
            fd[team_col] = fd[team_col].replace(team_fixes)
        out, _ = feat.resolve_feed_names(fd, ref, feed_name_col='Player', feed_team_col=team_col,
                                         feed_round_col=None, label=label, verbose=False)
        out[team_col] = df[team_col].values
        return out
    out, _ = feat.resolve_names_simple(df, ref['Player_Name'].unique(), 'Player', label=label, verbose=False)
    return out


def _file_stamp(path):
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d %b %H:%M')


def _mc_sources(season):
    """The four outside boards, each with Player, <X>_Rank and _match_key."""
    import features as feat
    dp = lambda name: sd.season_cfg.data_path(name, season)
    afl_raw = _mc_feed(dp("afl_predictor_predictions.csv"), 'Team', feat.COACHES_TEAM_FIXES, 'afl-predictor', season)
    afl = pd.DataFrame()
    if not afl_raw.empty and 'Total_Votes' in afl_raw.columns:
        s = afl_raw.sort_values('Total_Votes', ascending=False).reset_index(drop=True)
        s['AFL_Rank'] = s.index + 1
        afl = s[['Player', 'Total_Votes', 'AFL_Rank']].rename(columns={'Total_Votes': 'AFL_Votes'})
        afl['Player'] = afl['Player'].str.title().str.strip()
    bf = _mc_feed(dp("betfair_predictions.csv"), 'Team', feat.BETFAIR_TEAM_FIXES, 'betfair', season)
    if not bf.empty:
        bf = bf.rename(columns={'Total_Votes': 'BF_Votes', 'Rank': 'BF_Rank'}, errors='ignore')
        bf['Player'] = bf['Player'].str.title().str.strip()
    wh = pd.DataFrame()
    pub, legacy = dp("wheelo_brownlow_predictions.csv"), f"data_wheelo/wheelo_{season}.csv"
    if os.path.exists(pub):
        raw = pd.read_csv(pub, usecols=lambda c: c in {'Player', 'Votes'})
        if {'Player', 'Votes'} <= set(raw.columns):
            agg = raw.groupby('Player')['Votes'].sum().reset_index().sort_values(
                'Votes', ascending=False).reset_index(drop=True)
            agg['WH_Rank'] = agg.index + 1
            wh = agg.rename(columns={'Votes': 'WH_Votes'})
    elif os.path.exists(legacy):
        raw = pd.read_csv(legacy, usecols=lambda c: c in {'Player', 'ExpVotes', 'RatingPoints'})
        col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in raw.columns), None)
        if col:
            agg = raw.groupby('Player')[col].sum().reset_index().sort_values(
                col, ascending=False).reset_index(drop=True)
            agg['WH_Rank'] = agg.index + 1
            wh = agg.rename(columns={col: 'WH_Votes'})
    if not wh.empty:
        wh['Player'] = wh['Player'].str.title().str.strip()
    espn = _mc_feed(dp("espn_predictions.csv"), label='espn', season=season)
    if not espn.empty:
        espn = espn.rename(columns={'Total_Votes': 'ESPN_Votes', 'Rank': 'ESPN_Rank'}, errors='ignore')
        espn['Player'] = espn['Player'].str.title().str.strip()
    return afl, bf, wh, espn


def _mc_board(cc_raw, sources, actual=None):
    afl, bf, wh, espn = sources
    cc = pd.DataFrame()
    if cc_raw is not None:
        cc_raw = cc_raw.sort_values('Exp_Total_Votes', ascending=False).reset_index(drop=True)
        cc_raw['CC_Rank'] = cc_raw.index + 1
        cols = ['Player_Name', 'Exp_Total_Votes', 'CC_Rank'] + (['Team'] if 'Team' in cc_raw.columns else [])
        cc = cc_raw[cols].rename(columns={'Player_Name': 'Player', 'Exp_Total_Votes': 'CC_Votes'})
        cc['Player'] = cc['Player'].str.title().str.strip()
    models = [(cc, 'CC_Rank'), (afl, 'AFL_Rank'), (bf, 'BF_Rank'), (wh, 'WH_Rank'), (espn, 'ESPN_Rank')]
    for df, _ in models:
        if not df.empty and 'Player' in df.columns:
            df['_match_key'] = df['Player'].apply(_normalise_name)
    canonical = {}
    for df in (espn, wh, bf, afl, cc):
        if not df.empty and '_match_key' in df.columns:
            for p, k in zip(df['Player'], df['_match_key']):
                canonical[k] = p
    cc_team = dict(zip(cc['_match_key'], cc['Team'])) if 'Team' in cc.columns and not cc.empty else {}

    def rank_of(df, k, rc):
        if df.empty or '_match_key' not in df.columns:
            return None
        hit = df[df['_match_key'] == k]
        return int(hit.iloc[0][rc]) if not hit.empty else None

    keys = set()
    for df, _ in models:
        if not df.empty and '_match_key' in df.columns:
            keys.update(df.head(20)['_match_key'].tolist())
    rows = []
    for k in sorted(keys):
        rk = [rank_of(df, k, rc) for df, rc in models]
        avail = [r for r in rk if r is not None]
        cons = round(sum(avail) / len(avail), 1) if avail else 40.0
        rows.append({'player': canonical.get(k, k), 'key': k, 'consAvg': cons,
                     'cc': rk[0], 'afl': rk[1], 'bf': rk[2], 'wh': rk[3], 'espn': rk[4]})
    rows.sort(key=lambda r: r['consAvg'])
    rows = rows[:25]
    avail_models = [(df, rc) for df, rc in models if not df.empty]
    agree_thr = max(3, len(avail_models) - 1)
    for i, r in enumerate(rows, start=1):
        others = [r[c] for c in ('afl', 'bf', 'wh', 'espn') if r[c] is not None]
        r['cons'] = i
        r['edge'] = int(round(sum(others) / len(others) - r['cc'])) if r['cc'] is not None and others else None
        top10 = [(rank_of(df, r['key'], rc) or 99) <= 10 for df, rc in avail_models]
        r['full'] = i <= 10 and all(top10)
        r['strong'] = i <= 10 and sum(top10) >= agree_thr
        r['out'] = r['edge'] is not None and abs(r['edge']) >= 5
        a = [r[c] for c in ('cc', 'afl', 'bf', 'wh', 'espn') if r[c] is not None]
        r['nAvail'] = len(a)
        r['spread'] = (max(a) - min(a)) if a else None
        team = cc_team.get(r['key'], '')
        r['colour'] = _MC_TEAM_COLOURS.get(team, '#7e8c99')
        if actual is not None:
            r['actual'] = actual.get(r['key'], 0)
        del r['key']
    return {'rows': rows, 'agreeThr': agree_thr, 'nModels': len(avail_models)}


_CALIB_EDGES = [0.05, 0.10, 0.20, 0.35, 0.60, 1.0001]


def _forward_scorecard(season):
    """How a season the site predicted live went, from files. Counts, not
    claims: every figure is re-derivable from the season's game file.

    Calibration reads P_3_game, the within-game fitted P(3) that Game Analysis
    and the Player Profile displayed, bucketed by what it said. MAE is
    scripts/measure_mae.py's definition. The top pick is the raw P_3 argmax,
    dashboard.top_pick_record's rule, so it matches the published 145 of 207.
    """
    g = sd.load_game(season).drop_duplicates(['Player_Name', 'Round_num', 'Home.team', 'Away.team']).copy()
    g['_v'] = pd.to_numeric(g['Brownlow.Votes'], errors='coerce').fillna(0)
    gid = g['Round_num'].astype(str) + '|' + g['Home.team'] + '|' + g['Away.team']
    ok = g.groupby(gid)['_v'].transform('sum') == 6
    top = g[ok].loc[g[ok].groupby(gid[ok])['P_3'].idxmax()]
    se = sd.load_season(season)
    act = se.sort_values(['Actual_Votes', 'Exp_Total_Votes'], ascending=False)['Player_Name'].tolist()
    mod = se.sort_values('Exp_Total_Votes', ascending=False)['Player_Name'].tolist()
    b = pd.cut(g['P_3_game'], _CALIB_EDGES, right=False)
    cal = g.groupby(b, observed=True).agg(n=('P_3_game', 'size'), says=('P_3_game', 'mean'),
                                          hit=('_v', lambda v: int((v == 3).sum())))
    return {
        'topPick': [int((top['_v'] == 3).sum()), int(len(top))],
        'top3InOrder': act[:3] == mod[:3],
        'top10': len(set(act[:10]) & set(mod[:10])),
        'top20': len(set(act[:20]) & set(mod[:20])),
        'mae': round(float((g['_v'] - g['Exp_Votes']).abs().mean()), 4),
        'maeZero': round(float(g['_v'].mean()), 4),
        'calib': [[round(float(iv.left), 2), round(min(float(iv.right), 1.0), 2), int(r.n), round(float(r.says), 3), int(r.hit)]
                  for iv, r in cal.iterrows()],
    }


def export_model_comparison():
    """The consensus board for the season the site leads with.

    That is season_cfg.current_season(), not LIVE_SEASON: straight after a
    rollover the new season has no boards yet, and the finished one is still
    the story. Once that season is counted each row carries its actual votes.
    """
    from brownlow_medallists import get_medallists
    live = sd.season_cfg.current_season()
    counted = sd.season_cfg.counted(live)
    cc_path = sd.season_cfg.pred_path("season_{s}.csv", live)
    cc_dec = (pd.read_csv(cc_path, usecols=lambda c: c in {'Player_Name', 'Team', 'Exp_Total_Votes', 'Actual_Votes'})
              if os.path.exists(cc_path) else None)
    actual = None
    if counted and cc_dec is not None and 'Actual_Votes' in cc_dec.columns:
        actual = {_normalise_name(str(n).title().strip()): int(v)
                  for n, v in zip(cc_dec['Player_Name'], cc_dec['Actual_Votes'].fillna(0))}
    sources = _mc_sources(live)
    decimal = _mc_board(cc_dec.drop(columns=['Actual_Votes'], errors='ignore') if cc_dec is not None else None,
                        sources, actual)
    r = sd.load_season_rounded(live)
    rounded = (_mc_board(r[['Player_Name', 'Team', 'Exp_Total_Votes']].copy(), _mc_sources(live), actual)
               if r is not None and not r.empty else None)
    dp = lambda name: sd.season_cfg.data_path(name, live)
    obj = {
        'season': live,
        'counted': counted,
        'hasPredictions': cc_dec is not None,
        'boards': {'decimal': decimal, 'rounded': rounded},
        'stamps': {'afl': _file_stamp(dp("afl_predictor_predictions.csv")),
                   'espn': _file_stamp(dp("espn_predictions.csv")),
                   'betfair': _file_stamp(dp("betfair_predictions.csv"))},
    }

    # Insights: the walk-forward backtest and feature importance.
    bt_path = os.path.join(sd.PRED_DIR, "backtest_results.csv")
    if os.path.exists(bt_path):
        bt = pd.read_csv(bt_path)
        frames = [(int(season), bt[bt['Season'] == season], False) for season in sorted(bt['Season'].unique())]
        # Forward seasons: every counted season after the backtest, from the
        # live predictions the site published. The same test as a backtest
        # season (a model trained only on earlier years, scored against the
        # count), built the way backtest.py builds one: season totals of
        # Exp_Votes, rank method 'min'. Flagged so the page can say which is which.
        for season in range(int(bt['Season'].max()) + 1, sd.LIVE_SEASON + 1):
            se = sd.load_season(season) if sd.season_cfg.counted(season) else None
            if se is None or se['Actual_Votes'].fillna(0).sum() == 0:
                continue
            f = se.rename(columns={'Player_Name': 'Player', 'Exp_Total_Votes': 'Predicted_Votes'})
            f = f[['Player', 'Team', 'Actual_Votes', 'Predicted_Votes']].copy()
            f['Actual_Votes'] = f['Actual_Votes'].fillna(0)
            f['Rank_Predicted'] = f['Predicted_Votes'].rank(ascending=False, method='min').astype(int)
            frames.append((season, f, True))
        seasons = []
        for season, s, forward in frames:
            top10 = s[s['Rank_Predicted'] <= 10]
            avg_err = (top10['Predicted_Votes'] - top10['Actual_Votes']).abs().mean()
            meds = get_medallists(season)
            ranks = []
            for nm, tm in meds:
                hit = s[(s['Player'] == nm) & (s['Team'] == tm)]
                if not hit.empty:
                    ranks.append(int(hit['Rank_Predicted'].iloc[0]))
            meds_set = set(meds)
            seasons.append({
                'season': season,
                'forward': forward,
                'winner': ' & '.join(nm for nm, _ in meds) or '?',
                'predRank': min(ranks) if ranks else None,
                'top3': any(x <= 3 for x in ranks), 'top5': any(x <= 5 for x in ranks),
                'top10': any(x <= 10 for x in ranks),
                'avgErr': round(float(avg_err), 1),
                'scatter': [[str(p), str(t), _num(a, 1), _num(pv, 2), (p, t) in meds_set]
                            for p, t, a, pv in top10.sort_values('Rank_Predicted')[
                                ['Player', 'Team', 'Actual_Votes', 'Predicted_Votes']].itertuples(index=False)],
            })
        for x in seasons:
            if x['forward']:
                x['live'] = _forward_scorecard(x['season'])
        obj['insights'] = {'btMin': int(bt['Season'].min()), 'btMax': int(bt['Season'].max()),
                           'fwdMax': max(x['season'] for x in seasons), 'seasons': seasons}
    imp_path = os.path.join(sd.PRED_DIR, "feature_importance.csv")
    if os.path.exists(imp_path):
        imp = pd.read_csv(imp_path)
        imp['pct'] = (imp['Importance'] * 100).round(2)
        imp = imp.sort_values('pct', ascending=False).reset_index(drop=True)
        obj['importance'] = [[str(f), float(p)] for f, p in zip(imp['Feature'], imp['pct'])]
    return obj


# ── Live Tracker and Polls a Vote ──────────────────────────────
# Both pages work on one season, the one the site leads with
# (season_cfg.current_season()), and share one model export: tracker.json holds
# every player-game of that season with the per-round signal the Streamlit
# Live Tracker assembles in _assemble_live_tracker. polls.json adds the four
# outside boards Polls a Vote reads for its consensus verdict.
#
# The live AFL feed is never read at runtime here. When the season is counted
# the actual votes ride in tracker.json and the page needs nothing else; before
# that, the Next.js route /api/tracker proxies the AFL feed and the page joins it
# to this file by AFL provider id through `feedMap`, which this export builds
# with features.resolve_feed_names. The site cannot run that resolver, and a
# name that fails to bridge reads as a model value of ZERO (see the Live Tracker
# section of CLAUDE.md), so the bridge is done here, where the real one lives.

def _tracker_frame(season):
    g = sd.load_game(season)
    if g is None or g.empty:
        return None
    g = g.copy()
    g['Round_num'] = pd.to_numeric(g['Round_num'], errors='coerce')
    g = g.dropna(subset=['Round_num', 'Player_Name'])
    g['_gk'] = sd._game_key(g)
    # A player carried twice in one game (CLAUDE.md, 2025 round 24) counts once.
    g = g.drop_duplicates(['Player_Name', '_gk']).reset_index(drop=True)
    g['_dr'] = [sd.display_round(r, season) for r in g['Round_num']]
    return g


def _tracker_players(g):
    team_col = 'Playing.for' if 'Playing.for' in g.columns else 'Team'
    last = g.sort_values('Round_num').groupby('Player_Name').last()
    names = sorted(last.index)
    pick = g['Player'].fillna(g['Player_Name']) if 'Player' in g.columns else g['Player_Name']
    pick_of = dict(zip(g['Player_Name'], pick))
    base_of = dict(zip(g['Player_Name'], g['_base_name'] if '_base_name' in g.columns else g['Player_Name']))
    import features as feat
    out = []
    for n in names:
        pid = last.loc[n, 'ID'] if 'ID' in last.columns else None
        pid = str(int(float(pid))) if pid is not None and pd.notna(pid) else None
        out.append({'n': n, 'b': str(base_of[n]), 'p': str(pick_of[n]), 't': str(last.loc[n, team_col]),
                    'id': pid, 'k': feat.normalise_name(pick_of[n])})
    return out


def _tracker_feed_map(season, g, players):
    """{AFL provider id: player index} from the award endpoint's roster.

    Empty, never raising, when the AFL has not published the season or the
    network is down: the page then falls back to a plain name and club match,
    which is what an unbridged player needs anyway.
    """
    import features as feat
    try:
        import requests
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
        import bfawards_feed as bf
        roster = bf.award_roster(season)
        r = requests.get(f"{bf.BASE}/teams?pageSize=50", headers=bf.HDRS, timeout=bf.TMO)
        r.raise_for_status()
        tname = {t['id']: t['name'] for t in r.json().get('teams', []) if isinstance(t.get('id'), int)}
    except Exception as e:
        print(f"  tracker: no AFL roster for {season} ({type(e).__name__}); feedMap left empty")
        return {}
    if not roster:
        return {}
    feed = pd.DataFrame({
        'pid': [p['providerId'] for p in roster],
        'Player': [f"{p['firstName']} {p['surname']}".strip() for p in roster],
        'Team': [tname.get(p.get('teamId'), '') for p in roster],
    })
    feed['Team'] = feed['Team'].replace(feat.AFL_AWARD_TEAM_FIXES)
    team_col = 'Playing.for' if 'Playing.for' in g.columns else 'Team'
    target = pd.DataFrame({'Player_Name': g['_base_name'] if '_base_name' in g.columns else g['Player_Name'],
                           'Playing.for': g[team_col], 'Round_num': g['Round_num']})
    out, _ = feat.resolve_feed_names(feed, target, feed_name_col='Player', feed_team_col='Team',
                                     feed_round_col=None, label='afl-roster', verbose=False)
    idx = {(feat.normalise_name(p['b']), p['t']): i for i, p in enumerate(players)}
    fmap = {}
    for pid, nm, tm in zip(out['pid'], out['Player'], out['Team']):
        i = idx.get((feat.normalise_name(nm), tm))
        if i is not None:
            fmap[pid] = i
    print(f"  tracker: feedMap bridges {len(fmap)} of {len(roster)} AFL roster players")
    return fmap


def export_tracker():
    season = sd.season_cfg.current_season()
    g = _tracker_frame(season)
    if g is None:
        return None
    counted = sd.season_cfg.counted(season)
    players = _tracker_players(g)
    pix = {p['n']: i for i, p in enumerate(players)}
    games = g.drop_duplicates('_gk').sort_values(['Round_num', 'Home.team'])
    gix = {k: i for i, k in enumerate(games['_gk'])}
    rows = {
        'pi': [pix[n] for n in g['Player_Name']],
        'dr': [int(d) for d in g['_dr']],
        'g': [gix[k] for k in g['_gk']],
        'ev': [_num(x, 3) for x in g['Exp_Votes']],
        'pp': [_num(x, 3) for x in g['Poll_Prob']],
        'p1': [_num(x, 3) for x in g['P_1']],
        'p2': [_num(x, 3) for x in g['P_2']],
        'p3': [_num(x, 3) for x in g['P_3']],
    }
    if counted:
        rows['bv'] = [int(v) for v in pd.to_numeric(g['Brownlow.Votes'], errors='coerce').fillna(0)]
    cfg = sd.season_cfg.SEASONS.get(season, {})
    return {
        'season': season,
        'counted': counted,
        'countNight': cfg.get('count_night'),
        'games': [[int(d), str(h), str(a)] for d, h, a in
                  zip(games['_dr'], games['Home.team'], games['Away.team'])],
        'players': players,
        'rows': rows,
        'feedMap': {} if counted else _tracker_feed_map(season, g, players),
    }


def export_polls(season):
    """The four outside boards, keyed by features.normalise_name, for the
    Polls a Vote consensus. Thresholds and round conventions are the page's
    (render_polls_a_vote in dashboard.py); this only moves the data."""
    import features as feat
    dp = lambda name: sd.season_cfg.data_path(name, season)
    k = feat.normalise_name

    def totals(path):
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path)
        if 'Total_Votes' not in df.columns:
            return None
        return {k(p): _num(v if pd.notna(v) else 0, 2) for p, v in zip(df['Player'], df['Total_Votes'])}

    def rounds(path):
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path)
        if not {'Player', 'Round', 'Vote'} <= set(df.columns):
            return None
        out = {}
        for p, r, v in zip(df['Player'], df['Round'], df['Vote']):
            out.setdefault(k(p), []).append([int(r), _num(v if pd.notna(v) else 0, 2)])
        return out

    wh_total, wh_round = {}, {}
    wpath = f"data_wheelo/wheelo_{season}.csv"
    if os.path.exists(wpath):
        wh = pd.read_csv(wpath)
        col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in wh.columns), None)
        if col:
            for p, s in wh.groupby('Player')[col].sum().items():
                wh_total[k(p)] = _num(s, 2)
        if {'ExpVotes', 'Round'} <= set(wh.columns):
            for p, r, v in zip(wh['Player'], wh['Round'], wh['ExpVotes']):
                if pd.isna(v) or pd.isna(r):
                    continue
                wh_round.setdefault(k(p), []).append([int(r) - 1, _num(v, 2)])
    espn_round = rounds(dp("espn_round_votes.csv"))
    return {
        'season': season,
        'afl': totals(dp("afl_predictor_predictions.csv")),
        'aflRound': rounds(dp("afl_predictor_round_votes.csv")),
        'bf': totals(dp("betfair_predictions.csv")),
        'bfRound': rounds(dp("betfair_round_votes.csv")),
        'wh': wh_total,
        'whRound': wh_round,
        'espn': totals(dp("espn_predictions.csv")),
        'espnRound': espn_round,
        'espnRounds': sorted({r for v in (espn_round or {}).values() for r, _ in v}),
    }


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return os.path.getsize(path)


def main(argv):
    all_seasons = sd.available_seasons()
    seasons = [int(a) for a in argv] if argv else all_seasons
    # Profiles first: player files span every season, so they are always
    # rebuilt whole, and the Leaderboard links each row to one.
    season_slug = export_profiles(all_seasons)
    lb_dir = os.path.join(OUT_DIR, "leaderboard")
    for s in seasons:
        data = export_leaderboard(s, season_slug.get(s, {}))
        if data is None:
            continue
        size = _write(os.path.join(lb_dir, f"{s}.json"), data)
        n = len(data["boards"]["decimal"]["players"])
        print(f"  leaderboard {s}: {n} players, {size / 1024:.0f} KB")
        ga = export_games(s, season_slug.get(s, {}))
        if ga is not None:
            size = _write(os.path.join(OUT_DIR, "games", f"{s}.json"), ga)
            print(f"  games {s}: {len(ga['games'])} matches, {size / 1024:.0f} KB")
    sf = export_stat_filter()
    if sf is not None:
        size = _write(os.path.join(OUT_DIR, "statfilter.json"), sf)
        print(f"  statfilter: {sf['n']:,} games, {size / 1024:.0f} KB")
    mc = export_model_comparison()
    size = _write(os.path.join(OUT_DIR, "modelcomp.json"), mc)
    print(f"  modelcomp: {len(mc['boards']['decimal']['rows'])} consensus rows, {size / 1024:.0f} KB")
    tr = export_tracker()
    if tr is not None:
        size = _write(os.path.join(OUT_DIR, "tracker.json"), tr)
        print(f"  tracker {tr['season']}: {len(tr['players'])} players, "
              f"{'counted' if tr['counted'] else 'not counted'}, {size / 1024:.0f} KB")
        pv = export_polls(tr['season'])
        size = _write(os.path.join(OUT_DIR, "polls.json"), pv)
        print(f"  polls {pv['season']}: {size / 1024:.0f} KB")
    # The index lists what exists on disk, not what this run touched, so a
    # partial run never shrinks the season picker. currentSeason is the one the
    # default pages open on (season_cfg.current_season); liveSeason is
    # LIVE_SEASON, which straight after a rollover has no files yet.
    on_disk = sorted((int(f[:-5]) for f in os.listdir(lb_dir)
                      if f.endswith(".json") and f[:-5].isdigit()), reverse=True)
    current = sd.season_cfg.current_season()
    _write(os.path.join(OUT_DIR, "index.json"), {
        "liveSeason": sd.LIVE_SEASON,
        "currentSeason": current,
        "counted": [s for s in on_disk if sd.season_cfg.counted(s) or s < sd.LIVE_SEASON],
        "seasons": on_disk,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    print(f"  index: {len(on_disk)} seasons, live {sd.LIVE_SEASON}, current {current}")


if __name__ == "__main__":
    main(sys.argv[1:])
