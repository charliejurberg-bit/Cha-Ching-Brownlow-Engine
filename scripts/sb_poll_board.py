# -*- coding: utf-8 -*-
"""Sportsbet's "To Poll a Vote" board, fetched and priced against the model.

    python scripts/sb_poll_board.py              # fetch, price, write the CSV
    python scripts/sb_poll_board.py --top 30     # and print the best edges
    python scripts/sb_poll_board.py --check      # and print the backtest bands

Writes `data_betting/sb_poll_board.csv`: one row per selection, with the book's
price, the model's calibrated chance of polling at least one vote, the fair
price and the edge. Nothing here places or recommends a bet.

THE ESTIMATOR IS NOT THE ONE THE 3 VOTE BOARD USES
A 1+ vote market is a SEASON question, so it needs the joint 3-2-1 simulator
over every game a player played, and it needs a correction layer on top. The
line between estimators was drawn by backtest in the 16 September betting
session and is recorded in `handover_2026-09-16_betting_strategy.md`:

    1+ vote    unsharpened sim + isotonic map fitted on the walk-forward seasons

Unsharpened means the raw P_3/P_2/P_1 go into the sampler as they are, gamma
1.0. The sharpened P**1.4 simulator that prices the 6+ boards overstates role
players here by 5 to 9 points in the 20 to 70% range, and a raw simulator does
too, which is what the map is for. The map is fitted on the 18 seasons in
`predictions/backtest_game_level.csv` by the same simulator, so it corrects
this simulator's bias and nothing else's.

THE SAMPLER IS count_sim's, AND IT KEEPS EVERY PLAYER
`simulate_remaining` awards each game's 3, 2 and 1 to three different players
on conditional weights, which is the one thing a 1+ price cannot get wrong: a
fringe player's chance lives entirely in the games where a star misses. The
count simulator trims each game to its top 12 by Poll_Prob for speed. This
board cannot, because the players it prices ARE the 13th to 20th in most games.

THE BOOK NAMES A PLAYER AND NOTHING ELSE
Sportsbet's selection carries no club, so the match is league wide: the
canonical key first, then surname plus a compatible first name, and anything
that resolves to more than one player is REFUSED rather than guessed. "Bailey
Williams" is the case it exists for. Two 2026 players carry that name, the
book lists one runner, and there is no way to tell which.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import requests
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from count_sim import _game_arrays, simulate_remaining                # noqa: E402
from features import first_names_compatible, name_parts, normalise_name  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(REPO, "data_betting", "sb_poll_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
BACKTEST = os.path.join(REPO, "predictions", "backtest_game_level.csv")
SEASON = 2026
COMP, MARKET = 24522, "To Poll a Vote"        # Pick Your Own Vote
API = "https://www.sportsbet.com.au/apigw/sportsbook-sports/Sportsbook/Sports"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
ALL_PLAYERS = 99              # no trim: see "keeps every player" above
SIMS_2026, SIMS_BACKTEST = 40000, 10000


def fetch():
    events = requests.get(f"{API}/Competitions/{COMP}/Events", headers=UA, timeout=30)
    events.raise_for_status()
    ev = [e for e in events.json() if e["name"].strip().lower() == MARKET.lower()]
    if len(ev) != 1:
        raise SystemExit(f"{len(ev)} events named {MARKET!r} in competition {COMP}")
    r = requests.get(f"{API}/Events/{ev[0]['id']}/Markets", headers=UA, timeout=30)
    r.raise_for_status()
    rows = [{"sel": s.get("name"), "odds": (s.get("price") or {}).get("winPrice")}
            for m in r.json() for s in m.get("selections", [])]
    sb = pd.DataFrame(rows).dropna(subset=["odds"])
    print(f"  fetched {len(sb)} selections")
    return sb


def poll_probs(frame, n_sims, seed=0):
    """Raw simulated P(at least one vote) per player, keyed name|club.

    Keyed on name plus club rather than ID because ID is blank on 92 rows of
    2026, and a player whose rows split across two keys would have his season
    cut in half. Nobody changes club inside a season, so the pair is unique.
    """
    f = frame.copy()
    f["_key"] = f.Player_Name.astype(str) + "|" + f["Playing.for"].astype(str)
    f["_gkey"] = (f.Round_num.astype(str) + "|" + f["Home.team"].astype(str)
                  + "|" + f["Away.team"].astype(str))
    keys = pd.Index(f._key.unique())
    f["_pidx"] = keys.get_indexer(f._key)
    games = _game_arrays(f, top_n=ALL_PLAYERS)
    tot = simulate_remaining(games, len(keys), n_sims, np.random.default_rng(seed))
    return pd.Series((tot >= 1).mean(axis=0), index=keys)


def calibration(check=False):
    """The isotonic map from this simulator's raw P(1+) to what happened."""
    b = pd.read_csv(BACKTEST)
    # 2025 carries 78 rows twice with different Wheelo columns, so a bare
    # drop_duplicates removes none of them. Key on game plus player.
    b = b.drop_duplicates(subset=["Season", "Round_num", "Home.team", "Away.team",
                                  "Player_Name"])
    parts = []
    for season, d in b.groupby("Season"):
        raw = poll_probs(d, SIMS_BACKTEST, seed=int(season))
        got = (d.assign(_key=d.Player_Name.astype(str) + "|" + d["Playing.for"].astype(str))
               .groupby("_key")["Brownlow.Votes"].sum() >= 1)
        parts.append(pd.DataFrame({"season": season, "raw": raw,
                                   "hit": got.reindex(raw.index).astype(int)}))
    bt = pd.concat(parts)

    if check:
        # Leave one season out, so the map never scores a season it was fitted on.
        bt["loso"] = np.nan
        for s in bt.season.unique():
            tr, te = bt.season != s, bt.season == s
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            bt.loc[te, "loso"] = iso.fit(bt.raw[tr], bt.hit[tr]).predict(bt.raw[te])
        live = bt[bt.raw >= 0.05]
        print(f"\n  backtest, {bt.season.nunique()} seasons, {len(live):,} players "
              f"with raw P >= 5%")
        print(f"  Brier raw {((live.raw - live.hit) ** 2).mean():.4f}   "
              f"leave-one-season-out {((live.loso - live.hit) ** 2).mean():.4f}")
        live = live.assign(band=pd.cut(live.loso, [0, .2, .4, .6, .8, .9, .95, 1.0]))
        t = live.groupby("band", observed=True).agg(n=("hit", "size"),
                                                    said=("loso", "mean"),
                                                    raw=("raw", "mean"),
                                                    got=("hit", "mean"))
        print(t.to_string(float_format=lambda v: f"{v:.3f}"))

    return IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(bt.raw, bt.hit)


def match(sb, season):
    """Book name onto one 2026 player, league wide, or refused."""
    who = season[["Player_Name", "Playing.for"]].drop_duplicates()
    # game_level already carries "Bailey Williams (West Coast)", the dashboard's
    # disambiguated form. Strip the suffix before keying, or the book's bare
    # name matches neither and is refused as missing rather than as ambiguous.
    base = who.Player_Name.str.replace(r"\s*\([^()]*\)$", "", regex=True)
    who = who.assign(_n=base.map(normalise_name),
                     _first=base.map(lambda s: name_parts(s)[0]),
                     _sur=base.map(lambda s: name_parts(s)[1]))
    names, clubs, why = [], [], []
    for sel in sb.sel:
        hit = who[who._n == normalise_name(sel)]
        if len(hit) == 0:                                  # layer 2: surname
            first, sur = name_parts(sel)
            cand = who[who._sur == sur]
            hit = cand[[first_names_compatible(first, f) for f in cand._first]]
        if len(hit) == 1:
            names.append(hit.Player_Name.iloc[0]); clubs.append(hit["Playing.for"].iloc[0])
            why.append("")
        else:
            names.append(None); clubs.append(None)
            why.append("ambiguous" if len(hit) > 1 else "unmatched")
    sb = sb.assign(player=names, club=clubs, refused=why)
    bad = sb[sb.refused != ""]
    print(f"  players  {len(sb) - len(bad)}/{len(sb)} matched"
          + (f", refused: {', '.join(f'{s} ({w})' for s, w in zip(bad.sel, bad.refused))}"
             if len(bad) else ""))
    return sb


def price(sb, iso):
    g = pd.read_csv(GAME_LEVEL, low_memory=False).drop_duplicates(
        subset=["Game_ID", "Player_Name"]).copy()
    raw = poll_probs(g, SIMS_2026, seed=SEASON)
    sb = match(sb, g)
    per = (g.assign(_key=g.Player_Name.astype(str) + "|" + g["Playing.for"].astype(str))
           .groupby("_key").agg(games=("Game_ID", "size"), exp_votes=("Exp_Votes", "sum")))
    sb["_key"] = sb.player.astype(str) + "|" + sb.club.astype(str)
    sb["p_raw"] = sb._key.map(raw)
    sb["p"] = np.where(sb.p_raw.notna(), iso.predict(sb.p_raw.fillna(0)), np.nan)
    sb = sb.join(per, on="_key").drop(columns="_key")
    sb["implied"] = 1 / sb.odds
    sb["fair"] = 1 / sb.p.clip(lower=1e-9)
    sb["ev"] = sb.p * sb.odds - 1
    return sb


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=0, help="print the N best edges")
    ap.add_argument("--check", action="store_true", help="print the backtest bands")
    a = ap.parse_args()
    os.chdir(REPO)

    sb = fetch()
    sb = price(sb, calibration(check=a.check))
    sb.to_csv(OUT_CSV, index=False)
    priced = sb.dropna(subset=["p"])
    print(f"  wrote {OUT_CSV}: {len(priced)} priced, {(priced.ev > 0).sum()} positive")

    if a.top:
        top = priced.nlargest(a.top, "ev")
        print(f"\n  {'Player':24s} {'$':>6} {'model':>6} {'raw':>6} {'fair':>6} "
              f"{'edge':>6} {'gms':>4} {'exp':>5}")
        for _, x in top.iterrows():
            print(f"  {str(x.sel)[:24]:24s} {x.odds:6.2f} {x.p:6.1%} {x.p_raw:6.1%} "
                  f"{x.fair:6.2f} {x.ev:+6.0%} {x.games:4.0f} {x.exp_votes:5.1f}")


if __name__ == "__main__":
    main()
