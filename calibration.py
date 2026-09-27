"""calibration.py — a within-game recalibration layer over the model's vote probabilities.

    python calibration.py fit        # fit on 2026, print the held-out check, save the params
    python calibration.py check      # the held-out check only, nothing written

WHY IT EXISTS
The 2026 count showed the model's ORDER was right and its PROBABILITIES were too
flat: the favourite in a game got the 3 in 69% of games where the fitted P(3)
said 59%, and every season total in the top ten came in under. 2026 was also
the first season umpires had the stats (see the memory note on it), and the
votes moved with it: disposals and goals weighted up, marks and tackles down.
The trained model cannot know either, because every row it learned from is
2007-2025.

WHAT IT DOES
A Plackett-Luce layer on top of `_fit_game_probs` (dashboard.py), per game:

    s_i = a*log P3_game + c*log Poll_game + b . (Disposals_z, Goals_z, Marks_z, Tackles_z, Hit.Outs_z)
    the 3  ~ softmax(s)             over the whole game
    the 2  ~ softmax(t2 * s)        over everyone but the 3
    the 1  ~ softmax(t3 * s)        over everyone but the 3 and the 2

z-scores are within the game. The 3-2-1 is drawn jointly, so every game hands
out exactly 3, 2 and 1 and `Exp_Votes_cal` sums to 6 per game. The raw
`Exp_Votes` does not (3.8 to 8.3 per game in 2026).

MEASURED, 2026, EACH ROUND SCORED BY A LAYER FITTED ON THE OTHER 24
                                      current    this layer   Sportsbet
  log loss of the 3-vote winner         0.952        0.855
  P(3) Brier x1000                       9.80         8.83
  favourite: said / got              58.6/68.6    67.8/71.0
  season total MAE, 10+ vote players      3.66         2.58
  season total bias, same players        -3.35        -1.78
  3-vote board rows, Brier              0.0808       0.0731      0.0679
  3-vote board rows, log loss            0.926        0.841       0.805
  EV>0 bets on that board, ROI          -67.9%       -39.6%
  model's top pick every game, ROI       -5.8%        +0.6%      +3.6% (favourite)

It closes a bit more than half the gap to the book and does not pass it. A
log-linear blend with the book (about 35% model, weight also held out) beat the
book alone, Brier 0.0662 and log loss 0.766, so the model carries information
the price does not. But no EV screen off any of these made money on the 2026
per-game board: the blend's EV>0 bets went 20 from 118, -36.6%.

Hitouts earn their place: without them the stat terms mark every ruckman down
and Gawn's held-out total reads 13.6 against his 28 (18.4 with). Adding
clearances and contested possessions as well changed nothing material.

On the old regime the layer is harmless and slightly helpful (2008-2025 held
out: log loss 1.2927 to 1.2869), so it is not a 2026 overfit that only looks
good where it was fitted.

WHAT IT MUST NOT BE USED FOR
Anything published about 2026. It is fitted on 2026's results, so laying it
over the 2026 predictions shows a forecast that was never made. It is for 2027:
fit on 2026, apply to 2027, and refit on 2026 + 2027 once that count is in.
One season of the new regime is strong evidence, not proof; if 2027 reverts,
the old-regime fit (`--seasons 2008-2025`) is the fallback.

Nothing reads `predictions/calibration.pkl` yet. Wiring it in means applying
`apply()` after `_fit_game_probs` wherever a 2027 probability is shown or
priced: the dashboard's game loaders, sb_3vote_board.py (which would drop its
isotonic map, since this replaces it) and count_sim.py's sampler.
"""

import argparse
import ast
import os
import pickle

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

REPO = os.path.dirname(os.path.abspath(__file__))
PARAMS = os.path.join(REPO, "predictions", "calibration.pkl")
BACKTEST = os.path.join(REPO, "predictions", "backtest_game_level.csv")
VOTES_2026 = os.path.join(REPO, "data_2026", "brownlow_votes_2026.csv")
STATS = ["Disposals", "Goals", "Marks", "Tackles", "Hit.Outs"]
FEATURES = ["lp3", "lpoll"] + [s + "_z" for s in STATS]
RIDGE = 2.0          # on the stat weights only, toward zero
SIMS = 4000
EPS = 1e-6


def _dashboard_fns():
    """`_fit_game_probs` lifted out of dashboard.py by AST, as sb_3vote_board.py
    does. Importing dashboard.py would run the Streamlit app, and a second copy of
    the IPF here would be one more place for the two to drift apart."""
    ns = {"pd": pd, "np": np}
    src = open(os.path.join(REPO, "dashboard.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if ((isinstance(node, ast.FunctionDef) and node.name in ("_game_key", "_fit_game_probs"))
                or (isinstance(node, ast.Assign) and any(
                    getattr(t, "id", "") in ("_GAME_PROB_COLS", "_GAME_PROB_KEY_COLS")
                    for t in node.targets))):
            exec(compile(ast.Module([node], []), "dashboard-extract", "exec"), ns)
    return ns


def prepare(df):
    """Game-level rows -> the layer's inputs. Needs P_1..P_3, the four stats and
    Season / Round_num / Home.team / Away.team / Player_Name / Playing.for."""
    df = df.copy()
    df["gid"] = (df.Season.astype(str) + "_" + df.Round_num.astype(int).astype(str) + "_"
                 + df["Home.team"] + "_" + df["Away.team"])
    # A player can sit in one game twice (78 rows of 2025); two copies would take
    # two shares of the game's votes.
    df = df.drop_duplicates(["gid", "Player_Name", "Playing.for"])
    df = _dashboard_fns()["_fit_game_probs"](df)
    df["lp3"] = np.log(df.P_3_game.clip(EPS))
    df["lpoll"] = np.log((df.P_1_game + df.P_2_game + df.P_3_game).clip(EPS))
    g = df.groupby("gid")
    for s in STATS:
        sd = g[s].transform("std").replace(0, np.nan)
        df[s + "_z"] = ((df[s] - g[s].transform("mean")) / sd).fillna(0)
    return df.reset_index(drop=True)


def _pad(d):
    """(games x players) arrays; the mask is False on padding."""
    codes = d.gid.astype("category").cat.codes.values
    pos = d.groupby(codes).cumcount().values
    G, N = codes.max() + 1, pos.max() + 1
    X = np.zeros((G, N, len(FEATURES)))
    X[codes, pos] = d[FEATURES].values
    M = np.zeros((G, N), bool)
    M[codes, pos] = True
    V = np.zeros((G, N), int)
    V[codes, pos] = d["Brownlow.Votes"].values
    return X, M, V


def _lse(u, m):
    return logsumexp(np.where(m, u, -np.inf), axis=1)


def _nll(th, X, M, V, prior):
    k = len(FEATURES)
    s = X @ th[:k]
    t2, t3 = th[k], th[k + 1]
    ll = ((s * (V == 3)).sum(1) - _lse(s, M)).sum()
    m2 = M & (V != 3)
    ll += ((t2 * s * (V == 2)).sum(1) - _lse(t2 * s, m2)).sum()
    m1 = m2 & (V != 2)
    ll += ((t3 * s * (V == 1)).sum(1) - _lse(t3 * s, m1)).sum()
    return -ll + RIDGE * ((th - prior)[2:k] ** 2).sum()


def fit(d):
    """Maximum likelihood over the observed 3-2-1 of every game in `d`.

    Starts from, and shrinks the stat weights toward, the identity: a=1, c=0,
    stats 0, t2=t3=1, which is a plain Plackett-Luce draw on the existing P(3).
    """
    X, M, V = _pad(d)
    prior = np.r_[1.0, np.zeros(len(FEATURES) - 1), 1.0, 1.0]
    th = minimize(_nll, prior.copy(), args=(X, M, V, prior), method="L-BFGS-B").x
    return {"features": FEATURES, "w": th[:len(FEATURES)], "t2": th[-2], "t3": th[-1]}


def apply(d, params, sims=SIMS, seed=0):
    """Adds P3_cal / P2_cal / P1_cal / Exp_Votes_cal. P(3) is exact; the 2 and
    the 1 are sampled, because a Plackett-Luce marginal past the first pick has
    no closed form."""
    rng = np.random.default_rng(seed)
    d = d.copy()
    s_all = d[params["features"]].values @ params["w"]
    out = np.zeros((len(d), 3))
    for idx in d.groupby("gid").indices.values():
        s = s_all[idx]
        n = len(idx)
        out[idx, 0] = np.exp(s - logsumexp(s))
        rows = np.arange(sims)
        w3 = (s + rng.gumbel(size=(sims, n))).argmax(1)
        u2 = params["t2"] * s + rng.gumbel(size=(sims, n))
        u2[rows, w3] = -np.inf
        w2 = u2.argmax(1)
        u1 = params["t3"] * s + rng.gumbel(size=(sims, n))
        u1[rows, w3] = -np.inf
        u1[rows, w2] = -np.inf
        w1 = u1.argmax(1)
        out[idx, 1] = np.bincount(w2, minlength=n) / sims
        out[idx, 2] = np.bincount(w1, minlength=n) / sims
    d["P3_cal"], d["P2_cal"], d["P1_cal"] = out.T
    d["Exp_Votes_cal"] = 3 * d.P3_cal + 2 * d.P2_cal + d.P1_cal
    return d


def load(seasons):
    """Out-of-sample model probabilities with the votes that followed them.

    2008-2025 read the walk-forward backtest (every row scored by a model that
    never saw its season) with stats from game_level_<season>.csv. 2026 reads
    game_level_2026.csv, which the model never trained on, with the votes from
    data_2026/brownlow_votes_2026.csv.
    """
    key = ["Season", "Round_num", "Home.team", "Away.team", "Player_Name", "Playing.for"]
    frames = []
    old = [s for s in seasons if s < 2026]
    if old:
        bt = pd.read_csv(BACKTEST)
        bt = bt[bt.Season.isin(old)]
        stats = pd.concat([pd.read_csv(os.path.join(REPO, "predictions", f"game_level_{s}.csv"),
                                       low_memory=False, usecols=key[1:] + STATS).assign(Season=s)
                           for s in old])
        frames.append(bt.merge(stats.drop_duplicates(key), on=key, how="inner"))
    if 2026 in seasons:
        g = pd.read_csv(os.path.join(REPO, "predictions", "game_level_2026.csv"), low_memory=False)
        g = g.drop(columns=["Brownlow.Votes"]).assign(Season=2026)
        v = pd.read_csv(VOTES_2026)
        g = g.merge(v[key + ["Brownlow.Votes"]], on=key, how="left")
        g["Brownlow.Votes"] = g["Brownlow.Votes"].fillna(0)
        frames.append(g)
    d = prepare(pd.concat(frames, ignore_index=True))
    # Only complete games can be scored: a game that lost a vote-getter in a join
    # would teach the layer that nobody polled.
    tot = d.groupby("gid")["Brownlow.Votes"].transform("sum")
    threes = d.groupby("gid")["Brownlow.Votes"].transform(lambda x: (x == 3).sum())
    return d[(tot == 6) & (threes == 1)].reset_index(drop=True)


def scores(d, P3, ev):
    y = (d["Brownlow.Votes"] == 3).values
    fav = d.assign(P=P3).groupby("gid").P.idxmax()
    pl = d.assign(ev=ev).groupby(["Season", "Player_Name", "Playing.for"]).agg(
        ev=("ev", "sum"), act=("Brownlow.Votes", "sum"))
    top = pl[pl.act >= 10]
    return {"logloss_3": -np.log(np.clip(P3[y], 1e-9, 1)).mean(),
            "brier_3_x1000": 1000 * ((P3 - y) ** 2).mean(),
            "fav_said": P3[fav.values].mean(),
            "fav_got": y[fav.values].mean(),
            "season_MAE_10plus": (top.ev - top.act).abs().mean(),
            "season_bias_10plus": (top.ev - top.act).mean()}


def check(d):
    """Leave one round out: each round scored by a layer that never saw it."""
    base = d.P_3_game.values
    res = {"no layer": scores(d, base, 3 * d.P_3_game + 2 * d.P_2_game + d.P_1_game)}
    parts = []
    for r in sorted(d.Round_num.unique()):
        p = fit(d[d.Round_num != r])
        parts.append(apply(d[d.Round_num == r], p))
    held = pd.concat(parts).loc[d.index]
    res["layer, held out"] = scores(d, held.P3_cal.values, held.Exp_Votes_cal.values)
    return pd.DataFrame(res).T


def _seasons(txt):
    a, _, b = txt.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["fit", "check"])
    ap.add_argument("--seasons", default="2026",
                    help="season or range to fit on, e.g. 2026 or 2008-2025")
    a = ap.parse_args()
    seasons = _seasons(a.seasons)
    d = load(seasons)
    print(f"{d.gid.nunique()} games, seasons {seasons[0]}-{seasons[-1]}")
    pd.set_option("display.width", 200)
    print(check(d).round(4).to_string())
    if a.cmd == "fit":
        p = fit(d)
        p["seasons"] = seasons
        p["games"] = int(d.gid.nunique())
        print("params:", dict(zip(p["features"], np.round(p["w"], 3))),
              "t2", round(p["t2"], 3), "t3", round(p["t3"], 3))
        with open(PARAMS, "wb") as f:
            pickle.dump(p, f)
        print(f"saved -> {os.path.relpath(PARAMS, REPO)}")


if __name__ == "__main__":
    main()
