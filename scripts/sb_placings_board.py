# -*- coding: utf-8 -*-
"""Sportsbet's Top 3 / 5 / 10 / 20 finish boards, priced against the model.

    python scripts/sb_placings_board.py              # fetch, price, write the CSV
    python scripts/sb_placings_board.py --top 30     # and print the best edges
    python scripts/sb_placings_board.py --check      # and backtest the simulator

Writes `data_betting/sb_placings_board.csv`: one row per selection per board,
with the book's price, the model's chance of that finish, the fair price, the
edge, and the player's simulated season (mean, 10th and 90th percentile as lo
and hi, rank on the mean). Nothing here places or recommends a bet.

THE ESTIMATOR IS THE SEASON SIMULATOR, AND IT IS A REBUILD
A finishing position is a season question, so it needs the joint 3-2-1 sampler
over every game, and the line drawn in `handover_2026-09-16_betting_strategy.md`
puts placings with the 6+ boards: SHARPENED and DISPERSED.

  sharpening   each game's P_3, P_2 and P_1 columns are normalised within the
               game, raised to GAMMA, and normalised again. Raw columns sum to
               anything from 38% to 199% of a game, so the normalising is not
               optional; the power concentrates each game on its favourites.
  dispersion   every player draws one lognormal multiplier per simulated season
               and it scales his weight in every game he plays. Independent
               games under-disperse season totals 1.5 to 2x. Sigma follows the
               schedule SIGMA_KNOTS on raw expected votes, because a constant
               sigma over-disperses the elite.
  sampler      count_sim's conditional 3-2-1, one draw per award, so a game
               never gives two votes to one player.

The market book of 11 September priced placings with the same three parts, but
its script lived in a session scratchpad and is gone. This rebuild reproduces
its figures on identical inputs to r = 0.9997 at top 3 and 0.9975 at top 10,
mean absolute gap 0.3 points at top 3 and 1.4 at top 10, and is not bit
identical. `--check` is what licenses it, not the resemblance.

DEAD HEAT RULES APPLY, AND THEY ARE PRICED
Sportsbet's blurb says so. A player tied on the boundary of a top N gets the
fraction of the places left over the number tied: two players level on 5th
and 6th both hold half a top 5. Counting him fully in would overstate every
fringe price in a season that settles on integers.

THE BOARDS INCLUDE INELIGIBLE PLAYERS, AND SO DOES THE SIMULATOR
Every player's votes are counted whatever his tribunal record, which is what
"(Includes Ineligible)" in each market name means.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sb_poll_board import match                                    # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(REPO, "data_betting", "sb_placings_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
BACKTEST = os.path.join(REPO, "predictions", "backtest_game_level.csv")
SEASON = 2026
API = "https://www.sportsbet.com.au/apigw/sportsbook-sports/Sportsbook/Sports"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
COMP = 6136                  # Brownlow Hub
BOARDS = (3, 5, 10, 20)
GAMMA = 1.4
# Sigma of the per-season lognormal multiplier against raw expected votes,
# linear between knots and flat beyond them. Fitted in the 11 September book.
SIGMA_KNOTS = ([20.0, 22.5, 27.5, 32.5], [0.55, 0.50, 0.38, 0.22])
SIMS_2026, SIMS_BACKTEST, BATCH = 100_000, 10_000, 20_000


# ------------------------------------------------------------------ fetch
def fetch():
    ev = requests.get(f"{API}/Competitions/{COMP}/Events", headers=UA, timeout=30)
    ev.raise_for_status()
    rows = []
    for n in BOARDS:
        want = f"top {n} finish"
        hit = [e for e in ev.json() if e["name"].strip().lower().startswith(want)]
        if len(hit) != 1:
            raise SystemExit(f"{len(hit)} events named {want!r} in competition {COMP}")
        r = requests.get(f"{API}/Events/{hit[0]['id']}/Markets", headers=UA, timeout=30)
        r.raise_for_status()
        for m in r.json():
            for s in m.get("selections", []):
                rows.append({"board": n, "sel": s.get("name"),
                             "odds": (s.get("price") or {}).get("winPrice")})
    sb = pd.DataFrame(rows).dropna(subset=["odds"])
    print(f"  fetched {len(sb)} selections: "
          + ", ".join(f"top {n} {int((sb.board == n).sum())}" for n in BOARDS))
    return sb


# ------------------------------------------------------------------ simulate
def _prepare(frame):
    """Per-game arrays of (player index, p3, p2, p1), sharpened, plus sigma."""
    f = frame.copy()
    f["_key"] = f.Player_Name.astype(str) + "|" + f["Playing.for"].astype(str)
    f["_gkey"] = (f.Round_num.astype(str) + "|" + f["Home.team"].astype(str)
                  + "|" + f["Away.team"].astype(str))
    keys = pd.Index(f._key.unique())
    f["_pidx"] = keys.get_indexer(f._key)
    games = []
    for _, grp in f.groupby("_gkey", sort=False):
        cols = []
        for c in ("P_3", "P_2", "P_1"):
            p = grp[c].to_numpy(dtype=np.float64).clip(0, None)
            if p.sum() <= 0:
                break
            p = (p / p.sum()) ** GAMMA
            cols.append(p / p.sum())
        if len(cols) == 3:
            games.append((grp._pidx.to_numpy(), *cols))
    ev = f.groupby("_pidx").Exp_Votes.sum().reindex(range(len(keys))).fillna(0)
    sigma = np.interp(ev.to_numpy(), *SIGMA_KNOTS)
    return keys, games, sigma, ev.to_numpy()


def _draw(w, rng):
    cdf = np.cumsum(w / w.sum(axis=1, keepdims=True), axis=1)
    return (rng.random((w.shape[0], 1)) > cdf).sum(axis=1).clip(0, w.shape[1] - 1)


def _season_batch(games, sigma, n, rng):
    """(n, players) season totals. One 3, one 2 and one 1 per game, to three
    different players, on the conditional weights count_sim documents."""
    k = len(sigma)
    mult = np.exp(sigma * rng.standard_normal((n, k)) - sigma ** 2 / 2).astype(np.float32)
    tot = np.zeros((n, k), dtype=np.int16)
    rows = np.arange(n)
    for pidx, p3, p2, p1 in games:
        m = mult[:, pidx]
        i3 = _draw(p3 * m, rng)
        w2 = (p2 / np.clip(1.0 - p3, 1e-9, None)) * m
        w2[rows, i3] = 0.0
        i2 = _draw(w2, rng)
        w1 = (p1 / np.clip(1.0 - p3 - p2, 1e-9, None)) * m
        w1[rows, i3] = 0.0
        w1[rows, i2] = 0.0
        i1 = _draw(w1, rng)
        tot[rows, pidx[i3]] += 3
        tot[rows, pidx[i2]] += 2
        tot[rows, pidx[i1]] += 1
    return tot


def _topn_share(tot, n):
    """Each player's dead-heat share of a top n, per simulated season."""
    s = -np.sort(-tot, axis=1)
    v = s[:, n - 1:n]
    above = (s > v).sum(axis=1, keepdims=True)
    tied = (s == v).sum(axis=1, keepdims=True)
    return np.where(tot > v, 1.0, np.where(tot == v, (n - above) / tied, 0.0))


def simulate(frame, n_sims, seed=0, boards=BOARDS):
    """Per player: P(top n) for each board as topN, plus mean votes and the
    10th and 90th percentiles as lo and hi."""
    keys, games, sigma, ev = _prepare(frame)
    rng = np.random.default_rng(seed)
    acc = {b: np.zeros(len(keys)) for b in boards}
    totals, done = [], 0
    while done < n_sims:
        n = min(BATCH, n_sims - done)
        tot = _season_batch(games, sigma, n, rng)
        for b in boards:
            acc[b] += _topn_share(tot, b).sum(axis=0)
        totals.append(tot)
        done += n
    tot = np.vstack(totals)
    out = pd.DataFrame({f"top{b}": acc[b] / n_sims for b in boards}, index=keys)
    out["mean"] = tot.mean(axis=0)
    out["lo"] = np.percentile(tot, 10, axis=0)
    out["hi"] = np.percentile(tot, 90, axis=0)
    out["exp_votes"] = ev
    out["rank"] = out["mean"].rank(ascending=False, method="min").astype(int)
    return out


# ------------------------------------------------------------------ backtest
def check():
    """Walk-forward calibration of every top n over 2008-2025.

    Each season is simulated from its own out-of-sample game predictions and
    scored against the count that happened, with the same dead-heat rule the
    book settles on. Nothing is fitted here, so there is nothing to leak.
    """
    b = pd.read_csv(BACKTEST)
    b = b.drop_duplicates(subset=["Season", "Round_num", "Home.team", "Away.team",
                                  "Player_Name"])
    parts = []
    for season, d in b.groupby("Season"):
        sim = simulate(d, SIMS_BACKTEST, seed=int(season))
        votes = (d.assign(_key=d.Player_Name.astype(str) + "|" + d["Playing.for"].astype(str))
                 .groupby("_key")["Brownlow.Votes"].sum())
        tot = votes.to_numpy()[None, :]
        got = pd.DataFrame({f"g{n}": _topn_share(tot, n)[0] for n in BOARDS},
                           index=votes.index)
        parts.append(sim.join(got).assign(season=season))
        print(f"  {season} simulated", flush=True)
    bt = pd.concat(parts)
    print(f"\n  backtest, {bt.season.nunique()} seasons")
    bands = [0, .02, .05, .1, .2, .35, .5, .65, .8, .9, .97, 1.0001]
    for n in BOARDS:
        live = bt[bt[f"top{n}"] >= 0.005]
        brier = ((live[f"top{n}"] - live[f"g{n}"]) ** 2).mean()
        print(f"\n  top {n}: said {live[f'top{n}'].sum():.1f} finishes, "
              f"{live[f'g{n}'].sum():.1f} happened, Brier {brier:.4f}")
        t = (live.assign(band=pd.cut(live[f"top{n}"], bands, right=False))
             .groupby("band", observed=True)
             .agg(n=(f"g{n}", "size"), said=(f"top{n}", "mean"), got=(f"g{n}", "mean")))
        print(t.to_string(float_format=lambda v: f"{v:.3f}"))
    return bt


# ------------------------------------------------------------------ price
def price(sb):
    g = pd.read_csv(GAME_LEVEL, low_memory=False).drop_duplicates(
        subset=["Game_ID", "Player_Name"]).copy()
    sim = simulate(g, SIMS_2026, seed=SEASON)
    sb = match(sb, g)
    sb["_key"] = sb.player.astype(str) + "|" + sb.club.astype(str)
    sb = sb.join(sim[["mean", "lo", "hi", "exp_votes", "rank"]], on="_key")
    sb["p"] = [sim.at[k, f"top{b}"] if k in sim.index else np.nan
               for k, b in zip(sb._key, sb.board)]
    sb = sb.drop(columns="_key")
    sb["implied"] = 1 / sb.odds
    sb["fair"] = 1 / sb.p.clip(lower=1e-9)
    sb["ev"] = sb.p * sb.odds - 1
    return sb


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=0, help="print the N best edges")
    ap.add_argument("--check", action="store_true", help="backtest the simulator")
    a = ap.parse_args()
    os.chdir(REPO)

    if a.check:
        check()
        return
    sb = price(fetch())
    sb.to_csv(OUT_CSV, index=False)
    priced = sb.dropna(subset=["p"])
    print(f"  wrote {OUT_CSV}: {len(priced)} priced, {(priced.ev > 0).sum()} positive")

    if a.top:
        top = priced.nlargest(a.top, "ev")
        print(f"\n  {'top':>4} {'Player':24s} {'$':>7} {'model':>6} {'fair':>7} "
              f"{'edge':>6} {'mean':>5} {'rank':>4}")
        for _, x in top.iterrows():
            print(f"  {x.board:4d} {str(x.sel)[:24]:24s} {x.odds:7.2f} {x.p:6.1%} "
                  f"{x.fair:7.2f} {x.ev:+6.0%} {x['mean']:5.1f} {x['rank']:4d}")


if __name__ == "__main__":
    main()
