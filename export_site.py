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

Pages exported so far: Leaderboard, Player Profile, Game Analysis, Stat Filter.
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
            row["actual"] = int(r.Actual_Votes) if pd.notna(r.Actual_Votes) else 0
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
            "games": {"season": [int(s) for s in pg["Season"]]},
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
        season_slug.setdefault(int(s), {})[sn] = slug_of[name]

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
    # The index lists what exists on disk, not what this run touched, so a
    # partial run never shrinks the season picker.
    on_disk = sorted((int(f[:-5]) for f in os.listdir(lb_dir)
                      if f.endswith(".json") and f[:-5].isdigit()), reverse=True)
    _write(os.path.join(OUT_DIR, "index.json"), {
        "liveSeason": sd.LIVE_SEASON,
        "seasons": on_disk,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    print(f"  index: {len(on_disk)} seasons, live {sd.LIVE_SEASON}")


if __name__ == "__main__":
    main(sys.argv[1:])
