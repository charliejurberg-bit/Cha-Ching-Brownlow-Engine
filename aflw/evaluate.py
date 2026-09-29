"""Which way of predicting the AFLW Best and Fairest works best, measured.

    python aflw/evaluate.py

Leave-one-season-out over every season whose per-match votes are known
(label_kind "match" in data_aflw/frame.csv): each candidate is fitted on the
other seasons and scored on the held-out one, so every number here is out of
sample. Candidates:

  coaches      rank by AFLCA coaches votes alone (no fitting; seasons without
               coaches data score as missing, not as zero)
  fantasy      rank by dream team points alone (no fitting)
  pl_small     Plackett-Luce over a handful of within-match z-scores
  pl_full      Plackett-Luce over every within-match feature, ridge-shrunk
  xgb_rank     XGBoost ranker grouped by match, probabilities from a
               temperature fitted on the training seasons
  pl_coach     pl_full plus the coaches votes' within-match z and percentile,
               fitted and scored only on seasons that have coaches votes
  mens_pl      pl_small's features fitted on MEN'S games (2015-2025 AFLTables)
               and applied to AFLW unchanged: the "can we reuse the Brownlow"
               question, answered by measurement

Plackett-Luce draws the 3, then the 2 from the rest, then the 1, so every match
hands out exactly one of each (the property the men's classifier lacked; see
CLAUDE.md, "From 2027: the stack"). Metrics per held-out season:

  top1     share of matches where the favourite took the 3 votes
  ll3      mean -log P(the actual 3-vote winner): lower is better
  brier3   mean squared error of P(3) over every player-match, x1000
  win_rk   the medallist's rank on the model's expected-votes board
  top10    how many of the actual top 10 the model had in its top 10
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_aflw")
RIDGE = 1.0
SIMS = 2000

SMALL = ["disposals_z", "dreamTeamPoints_z", "contestedPossessions_z", "clearances.totalClearances_z",
         "goals_z", "tackles_z", "win"]
FULL = [c for c in pd.read_csv(os.path.join(OUT, "frame.csv"), nrows=1).columns
        if c.endswith(("_z", "_pct")) and not c.startswith("coaches")] + ["win", "margin_c"]


# ── Plackett-Luce ──────────────────────────────────────────────

def pad(d, feats):
    codes = d.matchId.astype("category").cat.codes.values
    pos = d.groupby(codes).cumcount().values
    G, N = codes.max() + 1, pos.max() + 1
    X = np.zeros((G, N, len(feats)))
    X[codes, pos] = d[feats].fillna(0).values
    M = np.zeros((G, N), bool)
    M[codes, pos] = True
    V = np.zeros((G, N), int)
    V[codes, pos] = d.votes.fillna(0).astype(int).values
    return X, M, V


def _lse(u, m):
    return logsumexp(np.where(m, u, -np.inf), axis=1)


def nll(th, X, M, V):
    k = X.shape[2]
    s = X @ th[:k]
    t2, t3 = th[k], th[k + 1]
    ll = ((s * (V == 3)).sum(1) - _lse(s, M)).sum()
    m2 = M & (V != 3)
    ll += ((t2 * s * (V == 2)).sum(1) - _lse(t2 * s, m2)).sum()
    m1 = m2 & (V != 2)
    ll += ((t3 * s * (V == 1)).sum(1) - _lse(t3 * s, m1)).sum()
    return -ll + RIDGE * (th[:k] ** 2).sum()


def fit_pl(d, feats):
    X, M, V = pad(d, feats)
    th0 = np.r_[np.zeros(len(feats)), 1.0, 1.0]
    th = minimize(nll, th0, args=(X, M, V), method="L-BFGS-B").x
    return th


def pl_probs(d, s_all, t2, t3, seed=0):
    """(P3, P2, P1) per row from scores: P(3) exact, the 2 and 1 sampled."""
    rng = np.random.default_rng(seed)
    out = np.zeros((len(d), 3))
    for idx in d.groupby("matchId").indices.values():
        s = s_all[idx]
        n = len(idx)
        out[idx, 0] = np.exp(s - logsumexp(s))
        rows = np.arange(SIMS)
        w3 = (s + rng.gumbel(size=(SIMS, n))).argmax(1)
        u2 = t2 * s + rng.gumbel(size=(SIMS, n))
        u2[rows, w3] = -np.inf
        w2 = u2.argmax(1)
        u1 = t3 * s + rng.gumbel(size=(SIMS, n))
        u1[rows, w3] = -np.inf
        u1[rows, w2] = -np.inf
        out[idx, 1] = np.bincount(w2, minlength=n) / SIMS
        out[idx, 2] = np.bincount(u1.argmax(1), minlength=n) / SIMS
    return out


# ── Candidates: each returns (P3, P2, P1) for the test rows ────

def cand_rank_by(col, scale):
    def run(train, test):
        # A single stat as a score, its sharpness fitted on the training seasons.
        tr = train.assign(_s=train[col].fillna(0))
        k = minimize(lambda a: nll(np.r_[a[0], 1.0, 1.0], *pad(tr, ["_s"])), [scale],
                     method="L-BFGS-B").x[0]
        return pl_probs(test, k * test[col].fillna(0).values, 1.0, 1.0)
    return run


def cand_pl(feats):
    def run(train, test):
        th = fit_pl(train, feats)
        k = len(feats)
        return pl_probs(test, test[feats].fillna(0).values @ th[:k], th[k], th[k + 1])
    return run


def cand_xgb(train, test):
    import xgboost as xgb
    feats = FULL
    tr = train.sort_values("matchId")
    m = xgb.XGBRanker(objective="rank:pairwise", n_estimators=300, max_depth=3,
                      learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=0)
    m.fit(tr[feats], tr.votes.fillna(0), group=tr.groupby("matchId", sort=False).size().values)
    s_tr = m.predict(train[feats])
    # Temperature: the ranker's scores are on no probability scale.
    a = minimize(lambda a: nll(np.r_[a[0], 1.0, 1.0], *pad(train.assign(_s=s_tr), ["_s"])), [1.0],
                 method="L-BFGS-B").x[0]
    return pl_probs(test, a * m.predict(test[feats]), 1.0, 1.0)


MENS_MAP = {"Disposals": "disposals", "Contested.Possessions": "contestedPossessions",
            "Clearances": "clearances.totalClearances", "Goals": "goals", "Tackles": "tackles"}


def mens_frame():
    """Men's games 2015-2025 with SMALL's features built the same way."""
    cache = os.path.join(OUT, "_mens_small.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    repo = os.path.dirname(OUT)
    m = pd.read_csv(os.path.join(repo, "fitzroy_stats_all.csv"), low_memory=False,
                    usecols=lambda c: c in {"Season", "Round", "Home.team", "Away.team", "Player", "Playing.for",
                                            "Home.score", "Away.score", "Brownlow.Votes", *MENS_MAP})
    m = m[m.Season >= 2015].copy()
    m["Round"] = pd.to_numeric(m.Round, errors="coerce")
    m = m.dropna(subset=["Round"])
    m["matchId"] = m.Season.astype(str) + "_" + m.Round.astype(int).astype(str) + "_" + m["Home.team"] + "_" + m["Away.team"]
    m = m.rename(columns=MENS_MAP)
    home = m["Playing.for"] == m["Home.team"]
    m["win"] = np.sign(np.where(home, m["Home.score"] - m["Away.score"], m["Away.score"] - m["Home.score"]))
    # AFLTables has no fantasy points; the men's equivalent is rebuilt from the
    # stats Dream Team scores (kick 3, handball 2, mark 3, tackle 4, goal 6):
    # disposals stand in for kicks+handballs at 2.5.
    m["dreamTeamPoints"] = 2.5 * m.disposals + 6 * m.goals + 4 * m.tackles
    g = m.groupby("matchId")
    for c in ["disposals", "dreamTeamPoints", "contestedPossessions", "clearances.totalClearances", "goals", "tackles"]:
        m[c + "_z"] = (m[c] - g[c].transform("mean")) / g[c].transform("std").replace(0, np.nan)
    m["votes"] = m["Brownlow.Votes"].fillna(0)
    ok = m.groupby("matchId").votes.transform("sum") == 6
    m = m[ok]
    m.to_pickle(cache)
    return m


def cand_mens(train, test):
    th = fit_pl(mens_frame(), SMALL)
    k = len(SMALL)
    return pl_probs(test, test[SMALL].fillna(0).values @ th[:k], th[k], th[k + 1])


# ── Scoring ─────────────────────────────────────────────────────

def score(test, P):
    t = test.assign(P3=P[:, 0], P2=P[:, 1], P1=P[:, 2])
    t["ev"] = 3 * t.P3 + 2 * t.P2 + t.P1
    got3 = t.votes == 3
    fav = t.loc[t.groupby("matchId").P3.idxmax()]
    win_p = t.loc[got3, "P3"].clip(1e-9)
    tot = t.groupby("playerId").agg(ev=("ev", "sum"), act=("votes", "sum"))
    tot["mr"] = tot.ev.rank(ascending=False, method="min")
    top = tot.act.max()
    act10 = set(tot.nlargest(10, "act").index)
    mod10 = set(tot.nlargest(10, "ev").index)
    return {"top1": (fav.votes == 3).mean(), "ll3": -np.log(win_p).mean(),
            "brier3": ((t.P3 - got3) ** 2).mean() * 1000,
            "win_rk": int(tot.loc[tot.act == top, "mr"].min()), "top10": len(act10 & mod10)}


def main():
    f = pd.read_csv(os.path.join(OUT, "frame.csv"), low_memory=False)
    f["margin_c"] = f.margin.clip(-60, 60) / 30
    f = f[f.label_kind == "match"].reset_index(drop=True)
    seasons = sorted(f.season.unique())
    cands = {
        "coaches": cand_rank_by("coaches", 0.2),
        "fantasy": cand_rank_by("dreamTeamPoints", 0.05),
        "pl_small": cand_pl(SMALL),
        "pl_full": cand_pl(FULL),
        "xgb_rank": cand_xgb,
        "pl_coach": cand_pl(FULL + ["coaches_z", "coaches_pct"]),
        "mens_pl": cand_mens,
    }
    rows = []
    for s in seasons:
        test, train = f[f.season == s].reset_index(drop=True), f[f.season != s].reset_index(drop=True)
        for name, run in cands.items():
            if name in ("coaches", "pl_coach") and test.coaches.isna().all():
                continue
            tr = train.dropna(subset=["coaches"]) if name in ("coaches", "pl_coach") else train
            r = score(test, run(tr, test))
            rows.append({"season": s, "model": name, **r})
            print(f"  {s:7} {name:9} top1 {r['top1']:.3f}  ll3 {r['ll3']:.3f}  brier3 {r['brier3']:.2f}  "
                  f"win_rk {r['win_rk']:>3}  top10 {r['top10']}", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT, "evaluate_results.csv"), index=False)
    cols = ["top1", "ll3", "brier3", "win_rk", "top10"]
    # Two tables, because the coaches candidates only exist for some seasons
    # and a mean over different seasons compares nothing.
    print("\nMean over every held-out season (models that need no coaches votes):")
    print(res[~res.model.isin(["coaches", "pl_coach"])].groupby("model")[cols].mean().round(3)
          .sort_values("ll3").to_string())
    cv = res[res.season.isin(res.loc[res.model == "pl_coach", "season"])]
    print(f"\nMean over the seasons with coaches votes ({', '.join(sorted(cv.season.unique()))}):")
    print(cv.groupby("model")[cols].mean().round(3).sort_values("ll3").to_string())


if __name__ == "__main__":
    main()
