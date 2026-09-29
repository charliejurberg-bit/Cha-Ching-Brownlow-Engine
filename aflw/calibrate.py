"""Are the AFLW model's probabilities right, and what should train it.

    python aflw/calibrate.py reliability     # held-out P(3) by band, per model
    python aflw/calibrate.py totals          # can season totals stand in for match votes?

reliability: leave-one-season-out predictions from evaluate.py's two leading
candidates, P(3) bucketed against what happened, plus the sharpness exponent
(gamma, as in the men's regime note) that would have fitted each held-out
season best. gamma > 1 means the model was too flat, < 1 too sharp.

totals: 2023 carries season totals, not match votes. This tests, on seasons
where the truth is known, how well totals alone recover the per-match 3-vote
winner when combined with the model (iterative proportional fitting of the
model's P(3) to each player's total and each match's single 3), and whether
training on that recovered season improves the held-out scores of the others.
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate as ev  # noqa: E402

EDGES = [0, 0.05, 0.10, 0.20, 0.35, 0.60, 1.0001]


def frame():
    f = pd.read_csv(os.path.join(ev.OUT, "frame.csv"), low_memory=False)
    f["margin_c"] = f.margin.clip(-60, 60) / 30
    return f


def loso(f, feats, need_coaches=False):
    """Held-out (season, row) predictions with raw scores kept."""
    lab = f[f.label_kind == "match"]
    if need_coaches:
        lab = lab.dropna(subset=["coaches"])
    out = []
    for s in sorted(lab.season.unique()):
        test, train = lab[lab.season == s].reset_index(drop=True), lab[lab.season != s].reset_index(drop=True)
        th = ev.fit_pl(train, feats)
        k = len(feats)
        test = test.assign(score=test[feats].fillna(0).values @ th[:k], t2=th[k], t3=th[k + 1])
        out.append(test)
    return pd.concat(out, ignore_index=True)


def p3(d, gamma=1.0):
    s = d.score * gamma
    return np.exp(s - d.assign(_s=s).groupby("matchId")._s.transform(lambda x: logsumexp(x)))


def reliability():
    f = frame()
    for name, feats, nc in [("pl_full", ev.FULL, False), ("pl_coach", ev.FULL + ["coaches_z", "coaches_pct"], True)]:
        d = loso(f, feats, nc)
        d["P3"] = p3(d)
        d["got"] = d.votes == 3
        b = pd.cut(d.P3, EDGES, right=False)
        t = d.groupby(b, observed=True).agg(n=("P3", "size"), said=("P3", "mean"), took=("got", "mean"))
        print(f"\n{name}: held-out P(3) by band, {d.matchId.nunique()} matches")
        for iv, r in t.iloc[::-1].iterrows():
            print(f"  {iv.left:.2f}-{min(iv.right, 1):.2f}  n {int(r.n):>5}  said {r.said:6.1%}  took {r.took:6.1%}")
        fav = d.loc[d.groupby("matchId").P3.idxmax()]
        print(f"  favourite: said {fav.P3.mean():.1%}, took {fav.got.mean():.1%}")
        print("  best sharpness per held-out season (gamma):", end="")
        for s, g in d.groupby("season"):
            res = minimize_scalar(lambda gm: -np.log(p3(g, gm)[g.got].clip(1e-12)).sum(), bounds=(0.3, 3), method="bounded")
            print(f"  {s} {res.x:.2f}", end="")
        print()


# ── Totals as labels ────────────────────────────────────────────

def soft_threes(d, totals):
    """Per-row probability of being the match's 3, fitted so each match has one
    3 and each player's expected votes match her published total.

    Votes are 3-2-1, so a player's total constrains all three levels. The fit
    alternates: scale each player's rows toward her total (using 3*q3 + 2*q2 +
    q1 with q2, q1 from the model's own ratios), then renormalise each match's
    q3, q2, q1 to one apiece. A player with total 0 is exactly 0 everywhere.
    """
    d = d.copy()
    for c in ("q3", "q2", "q1"):
        d[c] = d[c.replace("q", "P")]
    zero = d.playerId.map(totals).fillna(0) == 0
    d.loc[zero, ["q3", "q2", "q1"]] = 0.0
    for _ in range(60):
        for c in ("q3", "q2", "q1"):
            d[c] = d[c] / d.groupby("matchId")[c].transform("sum").replace(0, np.nan)
        exp = (3 * d.q3 + 2 * d.q2 + d.q1).groupby(d.playerId).transform("sum")
        want = d.playerId.map(totals).fillna(0)
        r = (want / exp.replace(0, np.nan)).fillna(0).clip(0, 50)
        for c in ("q3", "q2", "q1"):
            d[c] = d[c] * r
    return d.fillna({"q3": 0, "q2": 0, "q1": 0})


def with_probs(test, feats, th):
    k = len(feats)
    P = ev.pl_probs(test, test[feats].fillna(0).values @ th[:k], th[k], th[k + 1])
    return test.assign(P3=P[:, 0], P2=P[:, 1], P1=P[:, 2])


def totals():
    """Recovery test: pretend each known season has only totals."""
    f = frame()
    lab = f[f.label_kind == "match"]
    feats = ev.FULL
    print("Recovering the 3-vote winner of each match from season totals + the model:")
    for s in sorted(lab.season.unique()):
        test, train = lab[lab.season == s].reset_index(drop=True), lab[lab.season != s].reset_index(drop=True)
        th = ev.fit_pl(train, feats)
        t = with_probs(test, feats, th)
        tot = t.groupby("playerId").votes.sum().to_dict()
        q = soft_threes(t, tot)
        pick_model = t.loc[t.groupby("matchId").P3.idxmax()]
        pick_tot = q.loc[q.groupby("matchId").q3.idxmax()]
        print(f"  {s:7} model alone {(pick_model.votes == 3).mean():.1%}   model + totals "
              f"{(pick_tot.votes == 3).mean():.1%}   mean q3 on the true 3 {q.loc[q.votes == 3, 'q3'].mean():.2f}")


def fit_soft(hard, soft, feats, w_soft=1.0):
    """Plackett-Luce on the hard seasons plus a soft season's recovered q3.

    The soft season enters through its first pick only, sum q3*s - lse(s): the
    expected log-likelihood of who got the 3 under the recovered distribution.
    The 2 and the 1 are left out for it, because their masks depend on which
    player took the 3, which is exactly what is uncertain.
    """
    from scipy.optimize import minimize
    Xh, Mh, Vh = ev.pad(hard, feats)
    Xs, Ms, _ = ev.pad(soft, feats)
    Q = np.zeros(Ms.shape)
    codes = soft.matchId.astype("category").cat.codes.values
    pos = soft.groupby(codes).cumcount().values
    Q[codes, pos] = soft.q3.values
    k = len(feats)

    def obj(th):
        s = Xs @ th[:k]
        ll_soft = ((Q * s).sum(1) - ev._lse(s, Ms)).sum()
        return ev.nll(th, Xh, Mh, Vh) - w_soft * ll_soft

    return minimize(obj, np.r_[np.zeros(k), 1.0, 1.0], method="L-BFGS-B").x


def withtotals():
    """Leave-one-season-out, with and without 2023's recovered labels in training."""
    f = frame()
    lab = f[f.label_kind == "match"]
    s23 = f[f.label_kind == "total"].reset_index(drop=True)
    tot23 = s23.groupby("playerId").season_total.first().to_dict()
    feats = ev.FULL
    rows = []
    for s in sorted(lab.season.unique()):
        test, train = lab[lab.season == s].reset_index(drop=True), lab[lab.season != s].reset_index(drop=True)
        th0 = ev.fit_pl(train, feats)
        # 2023's labels are recovered with a model that never saw the held-out season.
        q = soft_threes(with_probs(s23, feats, th0), tot23)
        th1 = fit_soft(train, q, feats)
        for name, th in (("without 2023", th0), ("with 2023", th1)):
            k = len(feats)
            P = ev.pl_probs(test, test[feats].fillna(0).values @ th[:k], th[k], th[k + 1])
            r = ev.score(test, P)
            rows.append({"season": s, "train": name, **r})
            print(f"  {s:7} {name:13} top1 {r['top1']:.3f}  ll3 {r['ll3']:.3f}  brier3 {r['brier3']:.2f}", flush=True)
    res = pd.DataFrame(rows)
    print(res.groupby("train")[["top1", "ll3", "brier3", "win_rk", "top10"]].mean().round(3).to_string())


if __name__ == "__main__":
    {"reliability": reliability, "totals": totals, "withtotals": withtotals}[
        sys.argv[1] if len(sys.argv) > 1 else "reliability"]()
