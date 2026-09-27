"""Walk-forward test of a within-game RANKER against the shipping classifier.

    python ranker_backtest.py              # the full comparison, about 5 minutes
    python ranker_backtest.py --quick      # test seasons 2023 on only

WHY
The shipping model (brownlow_model.py) is an XGBClassifier that scores each
player's row on its own. Nothing ties one player's P(3) to his teammates', which
is why a 2026 game's P_3 summed anywhere from 38% to 199% and why every
probability came out too flat. A ranker is trained on the question the umpires
actually answer: who was best IN THIS GAME.

WHAT IS COMPARED, every model trained only on seasons before the test season
  classifier   the shipping XGBClassifier, the shipping 93 features
  ranker       XGBRanker (pairwise, grouped by game), 93 + the extra features
               in features.build_extra_features (last season's votes, metres
               gained, real score involvements, intercepts)
  stack        one Plackett-Luce layer over both models' outputs
Every model's raw output becomes a joint 3-2-1 through the same Plackett-Luce
layer, fitted on the out-of-sample predictions of the three seasons BEFORE the
test season, never on the test season itself. 2026 is then also scored with the
regime layer of calibration.py on top (within-game stat terms), fitted leave one
round out inside 2026, which is how a 2027 prediction would be made.

MEASURED 27 September 2026 (an ablation also ran the ranker on the 93 features
alone and the classifier with the extras: each helped, the two together most)
  log loss of the 3-vote winner          2013-2025 mean    2026 (layer from 2023-25)
    classifier                               1.235              0.998
    ranker                                   1.218              0.920
    stack                                    1.199              0.934
  the stack beats the classifier in 12 of 13 seasons; the ranker alone in 7
  2026 + regime layer, each round held out: classifier 0.844, ranker 0.814,
  stack 0.813; top-20 season MAE 3.19 / 2.59 / 2.77

  On Sportsbet's 2026 3-vote board (Brier / log loss / top pick ROI / EV>0 ROI):
    shipping board          0.0808 / 0.926 / -5.8% / -67.9%
    classifier + layer      0.0724 / 0.832 / +3.6% / -34.1%
    ranker + layer          0.0706 / 0.794 / +1.2% / -17.8%
    stack + layer           0.0703 / 0.797 / +0.9% / -24.6%
    Sportsbet, devigged     0.0679 / 0.805 / +3.6%
    stack blended with book 0.0652 / 0.748
Level with the book on log loss, still behind it on Brier, and the blend beats
both. No EV screen made money. A scratch run with the extra columns in a
different order read 0.780 for the ranker and +10.2% on the stack's top pick:
column order moves colsample, so differences under about 0.015 in 2026 log loss,
and every single-season ROI, are noise.

WHAT THIS DOES NOT DO
It writes nothing the site reads. predictions/ranker_backtest_game_level.csv is
the out-of-sample per-game output for inspection. Shipping the ranker needs the
extra features computed weekly, which means scraper_advanced.py and
build_score_involvements.py joining update.py's chain, and last season's actual
votes (data_2026/brownlow_votes_2026.csv for 2027).
"""

import argparse
import os
import pickle
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.optimize import minimize
from scipy.special import logsumexp

import calibration
import features as feat

REPO = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, "predictions", "ranker_backtest_game_level.csv")
OUT_2026 = os.path.join(REPO, "predictions", "ranker_2026_regime_layer.csv")
FIRST_SEASON = 2007


def _counted_seasons():
    """Seasons whose actual votes are on disk. Up to 2025 the game_level files
    carry them; from 2026 they live in data_<s>/brownlow_votes_<s>.csv, written
    by scripts/fetch_brownlow_votes.py after the count. The last of these is the
    newest season a model can be trained or scored on, so a new count extends
    everything here with no constant to move."""
    out = [s for s in range(FIRST_SEASON, 2026)]
    s = 2026
    while os.path.exists(os.path.join(REPO, f"data_{s}", f"brownlow_votes_{s}.csv")):
        out.append(s)
        s += 1
    return out


LAST_SEASON = _counted_seasons()[-1]
CLASSIFIER = dict(n_estimators=300, max_depth=7, learning_rate=0.05, subsample=0.85,
                  colsample_bytree=0.8, min_child_weight=7, gamma=0.1, reg_alpha=0.2,
                  reg_lambda=2.0, random_state=42, n_jobs=-1)     # brownlow_model.py's
RANKER = dict(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.85,
              colsample_bytree=0.8, min_child_weight=7, gamma=0.1, reg_alpha=0.2,
              reg_lambda=2.0, random_state=42, n_jobs=-1, objective="rank:pairwise",
              lambdarank_pair_method="topk", lambdarank_num_pair_per_sample=8)
REGIME_STATS = ["Disposals", "Goals", "Marks", "Tackles", "Hit.Outs"]
KEY = ["Season", "Round_num", "Home.team", "Away.team", "Player_Name", "Playing.for"]


# ---------------------------------------------------------------- data
def load():
    """brownlow_model.py writes its exact training frame, all 93 features plus the
    votes, to predictions/game_level_<season>.csv, and predict_2026.py writes the
    same features for 2026. Reading those rather than rebuilding means this script
    cannot drift from what the shipping model was fitted on."""
    frames = []
    for s in range(FIRST_SEASON, LAST_SEASON + 1):
        g = pd.read_csv(os.path.join(REPO, "predictions", f"game_level_{s}.csv"), low_memory=False)
        frames.append(g.assign(Season=s))
    A = pd.concat(frames, ignore_index=True)
    A["gid"] = (A.Season.astype(str) + "_" + A.Round_num.astype(int).astype(str) + "_"
                + A["Home.team"] + "_" + A["Away.team"])
    # 78 rows of 2025 carry one player twice in a game; see CLAUDE.md.
    A = A.drop_duplicates(["gid", "Player_Name", "Playing.for"]).reset_index(drop=True)
    A = feat.fill_missing_ids(A, A)
    # From 2026 the game_level file reads 0 votes on every row (it is the live
    # prediction); the count lives in data_<s>/brownlow_votes_<s>.csv.
    for s in range(2026, LAST_SEASON + 1):
        v = pd.read_csv(os.path.join(REPO, f"data_{s}", f"brownlow_votes_{s}.csv"))
        A = A.merge(v[KEY + ["Brownlow.Votes"]].rename(columns={"Brownlow.Votes": "_v"}), on=KEY, how="left")
        m = A.Season == s
        A.loc[m, "Brownlow.Votes"] = A.loc[m, "_v"].fillna(0)
        A = A.drop(columns="_v")
    sv = A.groupby(["Season", "ID"])["Brownlow.Votes"].sum().rename("votes").reset_index()
    adv = pd.read_csv(os.path.join(REPO, "data_advanced", "score_involvements.csv"))
    A = feat.build_extra_features(A, sv, adv)
    tot = A.groupby("gid")["Brownlow.Votes"].transform("sum")
    n3 = A.groupby("gid")["Brownlow.Votes"].transform(lambda x: (x == 3).sum())
    A["complete"] = (tot == 6) & (n3 == 1)
    return A


def late_weight(d):
    """brownlow_model.py's recency weighting: the last five rounds count double."""
    mx = d.groupby("Season").Round_num.transform("max")
    return np.where(d.Round_num >= mx - 4, 2.0, 1.0)


# ---------------------------------------------------------------- models
_IPF = None


def _ipf():
    global _IPF
    if _IPF is None:
        _IPF = calibration._dashboard_fns()["_fit_game_probs"]
    return _IPF


def classifier_output(tr, te, feats):
    m = xgb.XGBClassifier(**CLASSIFIER)
    m.fit(tr[feats], tr["Brownlow.Votes"].astype(int), sample_weight=late_weight(tr))
    P = m.predict_proba(te[feats])
    t = te[["Season", "Round_num", "Home.team", "Away.team", "Player_Name", "ID"]].copy()
    t["P_1"], t["P_2"], t["P_3"] = P[:, 1], P[:, 2], P[:, 3]
    t = _ipf()(t)
    return np.c_[np.log(t.P_3_game.clip(1e-6)),
                 np.log((t.P_1_game + t.P_2_game + t.P_3_game).clip(1e-6))]


def ranker_output(tr, te, feats):
    tr = tr.sort_values("gid")
    qid = tr.gid.astype("category").cat.codes.values
    w = pd.Series(late_weight(tr), index=tr.index).groupby(qid).first().values
    m = xgb.XGBRanker(**RANKER)
    m.fit(tr[feats], tr["Brownlow.Votes"].astype(int), qid=qid, sample_weight=w)
    return m.predict(te[feats])[:, None]


# ---------------------------------------------------------------- Plackett-Luce layer
def _pad(gid, X, V):
    codes = pd.Series(gid).astype("category").cat.codes.values
    pos = pd.Series(codes).groupby(codes).cumcount().values
    G, N = codes.max() + 1, pos.max() + 1
    Xp = np.zeros((G, N, X.shape[1]))
    Xp[codes, pos] = X
    M = np.zeros((G, N), bool)
    M[codes, pos] = True
    Vp = np.zeros((G, N), int)
    Vp[codes, pos] = V
    return Xp, M, Vp


def _lse(u, m):
    return logsumexp(np.where(m, u, -np.inf), axis=1)


def _nll(th, X, M, V):
    k = X.shape[2]
    s = X @ th[:k]
    t2, t3 = th[k], th[k + 1]
    ll = ((s * (V == 3)).sum(1) - _lse(s, M)).sum()
    m2 = M & (V != 3)
    ll += ((t2 * s * (V == 2)).sum(1) - _lse(t2 * s, m2)).sum()
    m1 = m2 & (V != 2)
    ll += ((t3 * s * (V == 1)).sum(1) - _lse(t3 * s, m1)).sum()
    return -ll


def fit_pl(gid, X, V):
    th0 = np.r_[1.0, np.zeros(X.shape[1] - 1), 1.0, 1.0]
    return minimize(_nll, th0, args=_pad(gid, X, V), method="L-BFGS-B").x


def pl_marginals(gid, X, th, sims=3000, seed=0):
    """P(3) exact, P(2) and P(1) by Gumbel-max sampling of the ordered draw."""
    rng = np.random.default_rng(seed)
    k = X.shape[1]
    s_all = X @ th[:k]
    t2, t3 = th[k], th[k + 1]
    out = np.zeros((len(gid), 3))
    for idx in pd.Series(gid).groupby(gid).indices.values():
        s, n, r = s_all[idx], len(idx), np.arange(sims)
        out[idx, 0] = np.exp(s - logsumexp(s))
        w3 = (s + rng.gumbel(size=(sims, n))).argmax(1)
        u2 = t2 * s + rng.gumbel(size=(sims, n))
        u2[r, w3] = -np.inf
        w2 = u2.argmax(1)
        u1 = t3 * s + rng.gumbel(size=(sims, n))
        u1[r, w3] = -np.inf
        u1[r, w2] = -np.inf
        w1 = u1.argmax(1)
        out[idx, 1] = np.bincount(w2, minlength=n) / sims
        out[idx, 2] = np.bincount(w1, minlength=n) / sims
    return out


# ---------------------------------------------------------------- scoring
def metrics(te, P):
    y = te["Brownlow.Votes"].values
    d = te[["gid", "Player_Name", "Playing.for"]].assign(
        P3=P[:, 0], ev=3 * P[:, 0] + 2 * P[:, 1] + P[:, 2], V=y)
    fav = d.loc[d.groupby("gid").P3.idxmax()]
    pl = d.groupby(["Player_Name", "Playing.for"]).agg(ev=("ev", "sum"), act=("V", "sum"))
    top20 = pl.act.nlargest(20).index
    h = d.sort_values(["gid", "ev"], ascending=[True, False])
    h["h"] = h.groupby("gid").cumcount().map({0: 3, 1: 2, 2: 1}).fillna(0)
    ph = h.groupby(["Player_Name", "Playing.for"]).h.sum()
    return {"logloss_3": -np.log(np.clip(P[y == 3, 0], 1e-9, 1)).mean(),
            "brier_3_x1000": 1000 * ((P[:, 0] - (y == 3)) ** 2).mean(),
            "fav_said": fav.P3.mean(), "fav_got": (fav.V == 3).mean(),
            "decimal_MAE_top20": (pl.ev[top20] - pl.act[top20]).abs().mean(),
            "decimal_bias_top20": (pl.ev[top20] - pl.act[top20]).mean(),
            "321_MAE_top20": (ph[top20] - pl.act[top20]).abs().mean(),
            "top10_named": len(set(pl.ev.nlargest(10).index) & set(pl.act.nlargest(10).index))}


def regime_z(te):
    g = te.groupby("gid")
    return np.c_[tuple(((te[c] - g[c].transform("mean")) / g[c].transform("std").replace(0, np.nan))
                       .fillna(0).values for c in REGIME_STATS)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    base = pickle.load(open(os.path.join(REPO, "predictions", "features.pkl"), "rb"))
    extra = base + feat.extra_feature_names()
    A = load()
    print(f"{len(A):,} rows, {A.gid.nunique():,} games, {len(base)} + {len(extra) - len(base)} features")

    first_test = 2020 if a.quick else 2010
    eval_from = first_test + 3
    raw = {"classifier": {}, "ranker": {}}
    rows, keep = [], []
    for s in range(first_test, LAST_SEASON + 1):
        t0 = time.time()
        tr = A[A.Season < s]
        te = A[(A.Season == s) & A.complete].reset_index(drop=True)
        raw["classifier"][s] = classifier_output(tr, te, base)
        raw["ranker"][s] = ranker_output(tr, te, extra)
        raw.setdefault("_te", {})[s] = te
        if s < eval_from:
            continue
        prior = [q for q in raw["classifier"] if s - 3 <= q < s]
        gp = np.concatenate([raw["_te"][q].gid.values for q in prior])
        Vp = np.concatenate([raw["_te"][q]["Brownlow.Votes"].values.astype(int) for q in prior])
        for name, parts in (("classifier", ["classifier"]), ("ranker", ["ranker"]),
                            ("stack", ["classifier", "ranker"])):
            X = np.hstack([raw[p][s] for p in parts])
            Xp = np.vstack([np.hstack([raw[p][q] for p in parts]) for q in prior])
            P = pl_marginals(te.gid.values, X, fit_pl(gp, Xp, Vp))
            rows.append({"Season": s, "model": name, **metrics(te, P)})
            if name == "stack":
                keep.append(te[KEY + ["Brownlow.Votes"]].assign(P_3=P[:, 0], P_2=P[:, 1], P_1=P[:, 2]))
        print(f"  {s} done in {time.time() - t0:.0f}s", flush=True)

    R = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    cols = [c for c in R.columns if c not in ("Season", "model")]
    old = R[R.Season < 2026]
    print(f"\n{old.Season.min()}-{old.Season.max()} mean, each season out of sample:")
    print(old.groupby("model")[cols].mean().round(4).to_string())
    ll = old.pivot(index="Season", columns="model", values="logloss_3")
    for m in ("ranker", "stack"):
        print(f"  {m} beats the classifier on log loss in "
              f"{int((ll[m] < ll['classifier']).sum())} of {len(ll)} seasons")
    print("\n2026, layer fitted on 2023-2025 only:")
    print(R[R.Season == 2026].set_index("model")[cols].round(4).to_string())

    # 2026 with the regime layer, leave one round out inside 2026
    te = raw["_te"][2026]
    Z = regime_z(te)
    out = {}
    held = te[KEY + ["gid", "Brownlow.Votes"]].copy()
    for name, parts in (("classifier", ["classifier"]), ("ranker", ["ranker"]),
                        ("stack", ["classifier", "ranker"])):
        X = np.hstack([raw[p][2026] for p in parts] + [Z])
        P = np.zeros((len(te), 3))
        for r in sorted(te.Round_num.unique()):
            trm = (te.Round_num != r).values
            th = fit_pl(te.gid.values[trm], X[trm], te["Brownlow.Votes"].values[trm].astype(int))
            P[~trm] = pl_marginals(te.gid.values[~trm], X[~trm], th)
        out[name + " + regime layer"] = metrics(te, P)
        held[f"P3_{name}"] = P[:, 0]
    print("\n2026 with the regime layer, each round held out:")
    print(pd.DataFrame(out).T[cols].round(4).to_string())

    held.to_csv(OUT_2026, index=False)
    pd.concat(keep).to_csv(OUT, index=False)
    print(f"\nstack's out-of-sample per-game probabilities -> {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
