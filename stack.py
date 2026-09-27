"""stack.py — the shipping vote model from 2027: classifier + within-game ranker + regime layer.

    python stack.py train                # fit on every season with votes, save predictions/stack.pkl
    python stack.py train --weight 3     # count the latest season 3x in the base models

predict_2026.py calls `apply_if_ready()` after the classifier has filled P_1..P_3.

WHAT IT IS
Measured in ranker_backtest.py, which is the evidence for every choice here:
  classifier   brownlow_model.py's XGBClassifier and its 93 features, unchanged
  ranker       XGBRanker grouped by game, 93 + features.build_extra_features
  layer        one Plackett-Luce layer over both outputs plus within-game z of
               disposals, goals, marks, tackles and hitouts (the stat weights
               the umpires moved in 2026), drawing the 3, then the 2, then the 1
The stack beat the classifier in 12 of 13 walk-forward seasons, and in 2026 was
level with Sportsbet on log loss (0.797 vs 0.805). Every game hands out exactly
3, 2 and 1, so Exp_Votes sums to 6 per game, which the classifier never did.

HOW IT IS FITTED, and the one rule that matters
  1. Base models trained on every season BEFORE the latest one score the latest
     one. Those scores are out of sample.
  2. The layer is fitted on those out-of-sample scores against the latest
     season's actual 3-2-1. A layer fitted on in-sample scores would learn how
     confident an overfit model is on data it has seen, and sharpen everything.
  3. The base models are then refitted on every season including the latest,
     which is what predicts the next season.
The latest season is the new umpire regime (2026 was the first with stats
access), so the layer carries the regime and is refitted after every count.

THE IN-SAMPLE GUARD
`apply_if_ready(frame, season)` refuses any season the stack was trained on. A
stack trained through 2026 applied to the 2026 predictions would publish a
forecast built from the votes it claims to forecast. So the site's 2026 numbers
stay the classifier's, and the stack first speaks for 2027.

SEASON ROLLOVER
Actual votes come from game_level_<s>.csv up to 2025 and from
data_<s>/brownlow_votes_<s>.csv from 2026 (scripts/fetch_brownlow_votes.py).
ranker_backtest.LAST_SEASON follows the vote files, so after the 2027 count
scripts/fetch_brownlow_votes.py 2027 then python stack.py train is the whole job.
"""

import argparse
import datetime as dt
import os
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb

import features as feat
import ranker_backtest as rb

REPO = os.path.dirname(os.path.abspath(__file__))
STACK_PATH = os.path.join(REPO, "predictions", "stack.pkl")
PRED_COLS = ("P_1", "P_2", "P_3")


# ---------------------------------------------------------------- inputs
_ID_REF = None


def id_reference():
    """Player_Name -> ID pairs from every archived season, for fill_missing_ids."""
    global _ID_REF
    if _ID_REF is None:
        cols = ["Player_Name", "ID"]
        _ID_REF = pd.concat([pd.read_csv(os.path.join(REPO, "predictions", f"game_level_{s}.csv"),
                                         usecols=cols, low_memory=False)
                             for s in range(rb.FIRST_SEASON, 2100)
                             if os.path.exists(os.path.join(REPO, "predictions", f"game_level_{s}.csv"))])
    return _ID_REF


def season_votes():
    """Every player's actual season total, by fitzRoy ID, for every counted season."""
    cols = ["Round_num", "Player_Name", "Playing.for", "ID", "Brownlow.Votes"]
    frames = []
    for s in range(rb.FIRST_SEASON, 2100):
        vf = os.path.join(REPO, f"data_{s}", f"brownlow_votes_{s}.csv")
        gl = os.path.join(REPO, "predictions", f"game_level_{s}.csv")
        if os.path.exists(vf):
            v = pd.read_csv(vf, usecols=cols)
        elif os.path.exists(gl) and s <= 2025:
            # game_level files carry the real votes only for seasons whose count
            # happened before the season was predicted; from 2026 they carry 0.
            v = pd.read_csv(gl, usecols=cols, low_memory=False)
        else:
            continue
        # 2025's file carries 78 round-24 rows twice, which would count 5 votes twice.
        v = v.drop_duplicates(["Round_num", "Player_Name", "Playing.for"])
        v = feat.fill_missing_ids(v, id_reference())
        frames.append(v.groupby("ID")["Brownlow.Votes"].sum().rename("votes").reset_index().assign(Season=s))
    return pd.concat(frames, ignore_index=True)


def advanced_for(frame, season):
    """footywire's metres gained / score involvements / intercepts for `frame`.

    The saved join covers every round up to the last build. The current round is
    joined in memory onto the frame being predicted, because game_level for this
    season has not been rewritten yet. If footywire lags a round, those rows go
    in as missing, which the ranker treats like a pre-2015 row, not as zero.
    """
    import build_score_involvements as bsi
    saved = pd.read_csv(os.path.join(REPO, "data_advanced", "score_involvements.csv"))
    adv_file = os.path.join(bsi.ADV_DIR, f"advanced_{season}.csv")
    if os.path.exists(adv_file):
        try:
            live = bsi.build_season(season, [], gl=frame)
            saved = pd.concat([saved[saved.Season != season], live], ignore_index=True)
        except Exception as exc:       # a partial round fails the positional map
            print(f"  stack: in-memory footywire join failed ({exc}); using the saved join")
    return saved


def _gid(d):
    return (d.Season.astype(str) + "_" + d.Round_num.astype(int).astype(str) + "_"
            + d["Home.team"] + "_" + d["Away.team"])


def _raw(models, d):
    """Both base models' outputs for frame d, in the layer's column order."""
    clf, rnk, base, extra = models
    P = clf.predict_proba(d[base])
    t = d[["Season", "Round_num", "Home.team", "Away.team", "Player_Name", "ID"]].copy()
    t["P_1"], t["P_2"], t["P_3"] = P[:, 1], P[:, 2], P[:, 3]
    t = rb._ipf()(t)
    return np.c_[np.log(t.P_3_game.clip(1e-6)),
                 np.log((t.P_1_game + t.P_2_game + t.P_3_game).clip(1e-6)),
                 rnk.predict(d[extra])]


def _fit_models(tr, base, extra, weight_latest):
    w = rb.late_weight(tr) * np.where(tr.Season == tr.Season.max(), weight_latest, 1.0)
    clf = xgb.XGBClassifier(**rb.CLASSIFIER)
    clf.fit(tr[base], tr["Brownlow.Votes"].astype(int), sample_weight=w)
    trs = tr.assign(_w=w).sort_values("gid")
    qid = trs.gid.astype("category").cat.codes.values
    rnk = xgb.XGBRanker(**rb.RANKER)
    rnk.fit(trs[extra], trs["Brownlow.Votes"].astype(int), qid=qid,
            sample_weight=trs.groupby(qid)._w.first().values)
    return clf, rnk


# ---------------------------------------------------------------- train
def train(weight_latest):
    base = pickle.load(open(os.path.join(REPO, "predictions", "features.pkl"), "rb"))
    extra = base + feat.extra_feature_names()
    A = rb.load()
    latest = int(A.Season.max())
    print(f"{len(A):,} rows, seasons {int(A.Season.min())}-{latest}")

    # 1-2: out-of-sample scores on the latest season, and the layer fitted on them.
    # The earlier seasons are weighted as the final fit will weight them, with the
    # season before the latest standing in for "latest", so the layer sees scores
    # from a model built the same way as the one it will sit on.
    tr = A[A.Season < latest]
    te = A[(A.Season == latest) & A.complete].reset_index(drop=True)
    clf, rnk = _fit_models(tr, base, extra, weight_latest)
    X = np.hstack([_raw((clf, rnk, base, extra), te), rb.regime_z(te)])
    theta = rb.fit_pl(te.gid.values, X, te["Brownlow.Votes"].values.astype(int))
    P = rb.pl_marginals(te.gid.values, X, theta)
    fit = rb.metrics(te, P)
    print(f"layer fitted on {latest} ({te.gid.nunique()} games), in-sample for the layer only: "
          f"log loss {fit['logloss_3']:.3f}, favourite said {fit['fav_said']:.1%} got {fit['fav_got']:.1%}")
    names = ["log P3 (classifier)", "log poll (classifier)", "ranker score"] + [f"{s} z" for s in rb.REGIME_STATS]
    print("  weights: " + ", ".join(f"{n} {w:+.3f}" for n, w in zip(names, theta)) +
          f"; stage temperatures t2 {theta[-2]:.3f}, t3 {theta[-1]:.3f}")

    # 3: the models that will predict the next season
    clf, rnk = _fit_models(A, base, extra, weight_latest)
    obj = {"classifier": clf, "ranker": rnk, "base_features": base, "extra_features": extra,
           "theta": theta, "regime_stats": rb.REGIME_STATS, "trained_through": latest,
           "weight_latest": weight_latest, "created": dt.date.today().isoformat()}
    with open(STACK_PATH, "wb") as f:
        pickle.dump(obj, f)
    print(f"saved {os.path.relpath(STACK_PATH, REPO)}: trained through {latest}, "
          f"latest season weighted {weight_latest}x; applies to {latest + 1} onward")


# ---------------------------------------------------------------- apply
def load():
    if not os.path.exists(STACK_PATH):
        return None
    with open(STACK_PATH, "rb") as f:
        return pickle.load(f)


def apply_if_ready(frame, season):
    """Replace P_1..P_3 / Poll_Prob / Exp_Votes with the stack's, when allowed.

    Returns the frame unchanged, with a printed reason, when there is no stack
    or when `season` is one the stack was trained on. The classifier's own
    figures are kept beside the stack's as P_*_classifier either way they ran.
    """
    obj = load()
    if obj is None:
        print("  stack: no predictions/stack.pkl, keeping the classifier's probabilities")
        return frame
    if season <= obj["trained_through"]:
        print(f"  stack: trained through {obj['trained_through']}, so it is not applied to "
              f"{season} (that would publish an in-sample forecast); classifier kept")
        return frame

    d = feat.fill_missing_ids(frame, id_reference())
    d["Season"] = season
    d["gid"] = _gid(d)
    d = feat.build_extra_features(d, season_votes(), advanced_for(d, season))
    X = np.hstack([_raw((obj["classifier"], obj["ranker"], obj["base_features"],
                         obj["extra_features"]), d), rb.regime_z(d)])
    assert len(d) == len(frame), "a feature join multiplied rows; refusing to misalign"
    P = rb.pl_marginals(d.gid.values, X, obj["theta"])
    out = frame.copy()
    for c in PRED_COLS:
        out[f"{c}_classifier"] = frame[c].values
    out["P_3"], out["P_2"], out["P_1"] = P[:, 0], P[:, 1], P[:, 2]
    out["Poll_Prob"] = out.P_1 + out.P_2 + out.P_3
    out["Exp_Votes"] = out.P_1 + 2 * out.P_2 + 3 * out.P_3
    out["prob_source"] = "stack"
    per_game = out.groupby(d.gid.values).Exp_Votes.sum()
    print(f"  stack: applied to {d.gid.nunique()} games of {season}; Exp_Votes per game "
          f"{per_game.min():.2f} to {per_game.max():.2f}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["train"])
    ap.add_argument("--weight", type=float, default=1.0,
                    help="weight of the latest season in the base models (default 1)")
    a = ap.parse_args()
    train(a.weight)


if __name__ == "__main__":
    main()
