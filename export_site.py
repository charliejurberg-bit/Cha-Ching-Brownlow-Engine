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

Pages exported so far: Leaderboard.
"""

import json
import os
import sys
from datetime import datetime, timezone

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


def _board(season, rounded, live):
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


def export_leaderboard(season):
    live = season == sd.LIVE_SEASON
    decimal = _board(season, False, live)
    if decimal is None:
        print(f"  {season}: no season file, skipped")
        return None
    rounded = _board(season, True, live)
    rounds = decimal["rounds"] or (rounded or {}).get("rounds", [])
    return {
        "season": season,
        "live": live,
        "rounds": rounds,
        "roundLabels": [str(sd.display_round(rn, season)) for rn in rounds],
        "boards": {"decimal": decimal, "rounded": rounded},
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
    lb_dir = os.path.join(OUT_DIR, "leaderboard")
    for s in seasons:
        data = export_leaderboard(s)
        if data is None:
            continue
        size = _write(os.path.join(lb_dir, f"{s}.json"), data)
        n = len(data["boards"]["decimal"]["players"])
        print(f"  leaderboard {s}: {n} players, {size / 1024:.0f} KB")
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
