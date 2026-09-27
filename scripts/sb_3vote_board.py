# -*- coding: utf-8 -*-
"""Sportsbet's AFL Brownlow 3 Vote Games board, fetched and priced against the model.

    python scripts/sb_3vote_board.py              # fetch, price, write the CSV
    python scripts/sb_3vote_board.py --top 30     # and print the best edges

Writes `data_betting/sb_3vote_board.csv`: one row per selection, with the book's
price, the model's fitted probability, the fair price and the edge. Nothing here
places or recommends a bet; it is the board the post cards read.

WHY THIS MARKET AND NOT THE SEASON TOTALS
Measured on `predictions/backtest_game_level.csv`, 3,468 walk-forward games
2008-2025, the within-game fitted P(3) needs no correction layer: 24.8% said
against 23.6% happened, 45.1% against 44.0%, 77.1% against 77.7%. It is
slightly UNDER-confident at the top, which is the safe direction. Every
season-total market needed an isotonic map; this one does not.

RAW P_3 IS NOT A PROBABILITY AND MUST BE FITTED FIRST
The model scores each player's row on its own, so a game's P_3 column sums
anywhere from 38% to 199%. `_fit_game_probs` in dashboard.py runs iterative
proportional fitting over players x {0,1,2,3} so each game hands out one 3, one
2 and one 1. It is imported out of dashboard.py by AST rather than by `import`,
because dashboard.py is a Streamlit page and importing it executes the app.

THREE JOINS, EACH ASSERTED RATHER THAN ASSUMED
  round    Sportsbet's "Opening Round" is Round_num 1 and its "Round N" is
           Round_num N+1, the 2026 offset law in CLAUDE.md.
  fixture  matched on the UNORDERED club pair. A book writes the home side
           first and so does AFLTables, but nothing guarantees it.
  player   matched INSIDE one game only, which makes a same-name clash between
           two clubs impossible by construction. Two layers, normalise_name
           then surname, and anything still unmatched is reported rather than
           quietly folded into the field bucket.

"ANY OTHER PLAYER" IS THE TRAP ON THIS BOARD
It is priced as 1 minus the named players' fitted probabilities, so every
unmatched name inflates it. Nine unmatched names once made it read 24 to 49%
against a true median of 4.5%, and it looked like the best bet on the board.
A large field number is a name-join failure until proven otherwise, and the
games carrying one are flagged `suspect` rather than priced.
"""

import argparse
import ast
import os
import sys
import time

import numpy as np
import pandas as pd
import requests
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features import normalise_name                                # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(REPO, "data_betting", "sb_3vote_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
BACKTEST = os.path.join(REPO, "predictions", "backtest_game_level.csv")
DASHBOARD = os.path.join(REPO, "dashboard.py")
SEASON = 2026
COMP = 16767                 # AFL Brownlow 3 Vote Games
API = "https://www.sportsbet.com.au/apigw/sportsbook-sports/Sportsbook/Sports"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
# Sportsbet's marketing names against the AFLTables spellings the archive uses.
SB_CLUBS = {"Sydney Swans": "Sydney", "Gold Coast SUNS": "Gold Coast",
            "Geelong Cats": "Geelong", "GWS GIANTS": "Greater Western Sydney",
            "West Coast Eagles": "West Coast", "Adelaide Crows": "Adelaide"}


def _dashboard_ns():
    """`_fit_game_probs` and `_game_key`, lifted out of dashboard.py by AST.

    Importing dashboard.py runs the Streamlit app. Executing just the two
    function definitions and the two constants they close over does not.
    """
    ns = {"pd": pd, "np": np}
    src = open(DASHBOARD, encoding="utf-8").read()
    for node in ast.parse(src).body:
        wanted = (isinstance(node, ast.FunctionDef)
                  and node.name in ("_game_key", "_fit_game_probs"))
        const = (isinstance(node, ast.Assign)
                 and any(getattr(t, "id", "") in ("_GAME_PROB_COLS", "_GAME_PROB_KEY_COLS")
                         for t in node.targets))
        if wanted or const:
            exec(compile(ast.Module([node], []), "dashboard-extract", "exec"), ns)
    return ns


def fetch():
    """Every selection on the board, one row per runner per game."""
    events = requests.get(f"{API}/Competitions/{COMP}/Events", headers=UA, timeout=30)
    events.raise_for_status()
    rows = []
    for ev in events.json():
        # The market call is scoped to the EVENT, not to the competition. The
        # competition-scoped path that lists the events 404s for markets.
        r = requests.get(f"{API}/Events/{ev['id']}/Markets", headers=UA, timeout=30)
        r.raise_for_status()
        for mkt in r.json():
            for sel in mkt.get("selections", []):
                rows.append({"round": ev["name"], "market": mkt.get("name"),
                             "sel": sel.get("name"),
                             "odds": (sel.get("price") or {}).get("winPrice")})
        time.sleep(0.1)
    sb = pd.DataFrame(rows)
    print(f"  fetched {len(sb)} selections over "
          f"{sb.groupby(['round', 'market']).ngroups} markets")
    return sb


def model_probs():
    """Fitted, isotonic-calibrated P(3) per player per 2026 game."""
    ns = _dashboard_ns()
    b = ns["_fit_game_probs"](pd.read_csv(BACKTEST).drop_duplicates())
    b["_k"] = b.Season.astype(str) + "|" + ns["_game_key"](b)
    votes = b.groupby("_k")["Brownlow.Votes"]
    # Only games whose votes are complete can train the map: a game missing its
    # 3 teaches the map that nobody polled.
    b = b[(votes.transform("sum") == 6)
          & (votes.transform(lambda s: (s == 3).sum()) == 1)]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(
        b.P_3_game, (b["Brownlow.Votes"] == 3).astype(int))

    g = ns["_fit_game_probs"](pd.read_csv(GAME_LEVEL, low_memory=False))
    # game_level can carry a player twice in one game with different Wheelo
    # columns, so a bare drop_duplicates removes none of them. Key on the pair.
    g = g.drop_duplicates(subset=["Game_ID", "Player_Name"])
    # The stack (stack.py) is calibrated by its own Plackett-Luce layer, fitted
    # on the latest regime. This map was fitted on the old classifier's 2008-2025
    # output and would pull the stack's figures back toward that regime.
    stacked = g.get("prob_source", pd.Series("", index=g.index)).eq("stack")
    g["P"] = np.where(stacked, g.P_3_game, iso.predict(g.P_3_game))
    g["_n"] = g.Player_Name.map(normalise_name)
    g["_sur"] = (g.Player_Name.str.replace(r"\s*\([^()]*\)$", "", regex=True)
                 .str.split().str[-1].str.lower())
    return g


def price(sb, g):
    sb = sb.dropna(subset=["odds"]).copy()
    sb["rn"] = sb["round"].map(
        lambda r: 1 if str(r).strip() == "Opening Round" else int(str(r).split()[-1]) + 1)
    sb["pair"] = sb.market.map(lambda m: frozenset(
        SB_CLUBS.get(p.strip(), p.strip()) for p in str(m).split(" v ")))
    fixtures = {(int(rn), frozenset((h, a))): gid for gid, rn, h, a
                in zip(g.Game_ID, g.Round_num, g["Home.team"], g["Away.team"])}
    sb["gid"] = [fixtures.get((rn, pr)) for rn, pr in zip(sb.rn, sb.pair)]
    sb["is_other"] = sb.sel.str.strip().str.lower().eq("any other player")

    by_game = {gid: d for gid, d in g.groupby("Game_ID")}
    probs, names, unmatched = [], [], []
    for gid, sel, other in zip(sb.gid, sb.sel, sb.is_other):
        if other or gid is None or gid not in by_game:
            probs.append(np.nan); names.append(None); continue
        d = by_game[gid]
        hit = d[d._n == normalise_name(sel)]
        if len(hit) != 1:                              # layer 2: surname in game
            hit = d[d._sur == str(sel).split()[-1].lower()]
        if len(hit) == 1:
            probs.append(float(hit.P.iloc[0])); names.append(hit.Player_Name.iloc[0])
        else:
            probs.append(np.nan); names.append(None)
            unmatched.append((gid, sel))
    sb["p"], sb["model_name"] = probs, names

    named = sb[~sb.is_other]
    print(f"  fixtures {sb.gid.notna().sum()}/{len(sb)} selections, "
          f"{sb[sb.gid.notna()].gid.nunique()}/207 games")
    print(f"  players  {named.p.notna().sum()}/{len(named)} named selections matched")
    if unmatched:
        print(f"  UNMATCHED ({len(unmatched)}): {[u[1] for u in unmatched][:10]}")

    covered = named.dropna(subset=["p"]).groupby("gid").p.sum()
    sb.loc[sb.is_other, "p"] = sb.loc[sb.is_other, "gid"].map(
        lambda gid: max(0.0, 1.0 - float(covered.get(gid, 0.0))))
    sb["suspect"] = sb.gid.isin({u[0] for u in unmatched}) & sb.is_other

    sb = sb.dropna(subset=["p"]).copy()
    sb["ev"] = sb.p * sb.odds - 1
    sb["fair"] = 1 / sb.p.clip(lower=1e-9)
    sb["disp_round"] = sb.rn - 1                       # the AFL's number, not AFLTables'
    meta = g.set_index(["Game_ID", "Player_Name"])[["Playing.for", "Home.team", "Away.team"]]
    sb = sb.join(meta, on=["gid", "model_name"])
    sb["opponent"] = np.where(sb["Playing.for"] == sb["Home.team"],
                              sb["Away.team"], sb["Home.team"])
    return sb.drop(columns=["pair"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=0,
                    help="print the N best edges among named selections")
    a = ap.parse_args()

    os.chdir(REPO)
    sb = price(fetch(), model_probs())
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    sb.to_csv(OUT_CSV, index=False)
    print(f"  wrote {OUT_CSV}: {len(sb)} rows, {(sb.ev > 0).sum()} positive value")

    if a.top:
        top = sb[(~sb.is_other) & (sb.p >= 0.10)].nlargest(a.top, "ev")
        print(f"\n  {'Rd':>3} {'Player':24s} {'$':>7} {'model':>6} {'fair':>7} {'edge':>7}")
        for _, x in top.iterrows():
            lab = "OR" if x.disp_round == 0 else f"{x.disp_round:.0f}"
            print(f"  {lab:>3} {str(x.sel)[:24]:24s} {x.odds:7.2f} {x.p:6.1%} "
                  f"{'$' + format(x.fair, '.2f'):>7} {x.ev:+7.0%}")


if __name__ == "__main__":
    main()
