"""AFLW Best and Fairest predictions for the live season.

    python aflw/predict.py [season]            default: the latest season in the frame

Writes data_aflw/predictions_<season>.csv (per player per match) and
data_aflw/board_<season>.csv (season totals), each under three regime
scenarios, and prints the board.

THE MODEL is the one aflw/evaluate.py measured best: Plackett-Luce over every
within-match feature plus the coaches votes (pl_coach), fitted on every season
with both votes per match and coaches votes. Its sharpness is corrected by one
exponent, gamma, fitted on those seasons' held-out predictions (calibrate.py
showed the raw model a little too sure at the top).

THE REGIME. From 2026 umpires vote with the match stats in front of them. The
men's count showed what that did (aflw/regime.py): only disposals and goals
moved beyond an ordinary year, each by about 30%. AFLW has had no count under
the new rules, so three scenarios are carried until it does:

  none          the model as fitted on the old rules
  proportional  AFLW's own disposals and goals weights raised by the men's
                2026 ratio (x1.30, x1.33). The default: the change is the same
                rule, and AFLW's weights sit at about two thirds of the men's
  full          the men's absolute 2026 shift added unchanged

After the AFLW count, refit on the new season rather than keep any of these.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate as cal  # noqa: E402
import evaluate as ev  # noqa: E402
import regime as rg  # noqa: E402

FEATS = ev.FULL + ["coaches_z", "coaches_pct"]


def train_set(f):
    return f[(f.label_kind == "match")].dropna(subset=["coaches"]).reset_index(drop=True)


def fit_gamma(f):
    """Pooled sharpness exponent over the training seasons' held-out predictions."""
    d = cal.loso(f, FEATS, need_coaches=True)
    got = d.votes == 3
    r = minimize_scalar(lambda g: -np.log(cal.p3(d, g)[got].clip(1e-12)).sum(), bounds=(0.3, 3), method="bounded")
    return r.x


def regime_delta(f):
    """{scenario: {feature: extra weight}} on regime.py's common z features."""
    with open(os.path.join(ev.OUT, "regime_2026.json")) as fh:
        reg = json.load(fh)
    lab = rg.zs(f[f.label_kind == "match"].copy())
    aflw = rg.per_season(lab).mean()                   # AFLW's own weights, old rules
    shift = pd.Series(reg["delta"])
    ratio = {}
    m = rg.per_season(rg.mens())
    mu = m.loc[[str(s) for s in rg.OLD]].mean()
    for k, v in shift.items():
        if v:
            ratio[k] = m.loc["2026", k] / mu[k] - 1
    return {"none": {},
            "proportional": {k: aflw[k] * r for k, r in ratio.items()},
            "full": {k: v for k, v in shift.items() if v}}


def score(d, th, gamma, delta):
    k = len(FEATS)
    s = d[FEATS].fillna(0).values @ th[:k]
    for feat, w in delta.items():
        s = s + w * d[feat].values
    return gamma * s


def check_2023(f, th, gamma):
    """2023 was never trained on: its season totals test the model's board."""
    d = f[f.label_kind == "total"].reset_index(drop=True)
    if d.empty or d.coaches.isna().all():
        return
    d = rg.zs(d)
    P = ev.pl_probs(d, score(d, th, gamma, {}), th[len(FEATS)], th[len(FEATS) + 1])
    d["ev"] = 3 * P[:, 0] + 2 * P[:, 1] + P[:, 2]
    b = d.groupby("playerId").agg(player=("player", "first"), ev=("ev", "sum"), act=("season_total", "first"))
    b["rk"] = b.ev.rank(ascending=False, method="min")
    top = b.act.max()
    print(f"2023 out of sample: medallist ({', '.join(b[b.act == top].player)}) ranked "
          f"{int(b.loc[b.act == top, 'rk'].min())} on the model board; "
          f"{len(set(b.nlargest(10, 'ev').index) & set(b.nlargest(10, 'act').index))} of the top 10; "
          f"total MAE, top 20 by actual, {(b.nlargest(20, 'act').ev - b.nlargest(20, 'act').act).abs().mean():.2f}")


def main(argv):
    f = pd.read_csv(os.path.join(ev.OUT, "frame.csv"), low_memory=False)
    f["margin_c"] = f.margin.clip(-60, 60) / 30
    season = argv[0] if argv else f.season.iloc[-1]
    tr = train_set(f)
    th = ev.fit_pl(tr, FEATS)
    gamma = fit_gamma(f)
    print(f"model: pl_coach on {tr.matchId.nunique()} matches ({', '.join(sorted(tr.season.unique()))}); "
          f"sharpness gamma {gamma:.2f}")
    check_2023(f, th, gamma)

    live = rg.zs(f[f.season == season].reset_index(drop=True)).copy()
    deltas = regime_delta(f)
    k = len(FEATS)
    board = live.groupby("playerId").agg(player=("player", "first"), team=("team", "last"),
                                         games=("matchId", "nunique"))
    cols = {}
    for name, delta in deltas.items():
        P = ev.pl_probs(live, score(live, th, gamma, delta), th[k], th[k + 1])
        cols[f"P3_{name}"], cols[f"P2_{name}"], cols[f"P1_{name}"] = P.T
        cols[f"ev_{name}"] = 3 * P[:, 0] + 2 * P[:, 1] + P[:, 2]
        board[f"ev_{name}"] = pd.Series(cols[f"ev_{name}"]).groupby(live.playerId.values).sum()
        print(f"  scenario {name:12} extra weights: " + (", ".join(f"{a} +{b:.2f}" for a, b in delta.items()) or "none"))
    keep = ["season", "rnd", "matchId", "playerId", "player", "team", "opponent"] + \
        [c for c in live.columns if c.startswith(("P3_", "P2_", "P1_", "ev_"))]
    live[keep].to_csv(os.path.join(ev.OUT, f"predictions_{season}.csv"), index=False)
    board = board.sort_values("ev_proportional", ascending=False)
    board.to_csv(os.path.join(ev.OUT, f"board_{season}.csv"))
    rounds = sorted(live.rnd.unique())
    print(f"\n{season} board through round {rounds[-1]} ({live.matchId.nunique()} matches), expected votes:")
    print(board.head(15)[["player", "team", "games", "ev_none", "ev_proportional", "ev_full"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
