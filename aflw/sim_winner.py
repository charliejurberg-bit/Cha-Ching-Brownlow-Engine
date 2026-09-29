"""Who wins the AFLW Best and Fairest from here: Monte Carlo over the season.

    python aflw/sim_winner.py [sims]            default 20000

Played rounds: each match's 3-2-1 is drawn jointly from the model (Plackett-
Luce on the match's own scores, recovered as log P(3), which equals the score
up to a constant within a match), so every match hands out one of each and
teammates compete for the same votes. The count is secret, so played rounds
are as uncertain as future ones.

Future rounds: the real remaining fixtures, each club fielding the players who
played at least three of its last four matches, each player scored at the log
of her season-average P(3). A simplification: form, injury and selection
change are not modelled.

Sharpness: every simulated season draws its own gamma. Held out, the best-
fitting sharpness ran 0.66 to 1.48 across AFLW seasons (calibrate.py), so a
fixed gamma would claim more certainty than the history supports. Drawn
log-normal around 1 with the historical spread of log gamma.

Ties are dead heats: a k-way tie scores 1/k to each, as the bookmakers settle
a shared award (2021 was shared). Eligibility (a suspension rules a player
out) is not modelled.

Prints, per regime scenario (predict.py), each contender's win probability.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import evaluate as ev  # noqa: E402
import predict as pr  # noqa: E402

SEASON = 2026
LOG_GAMMA_SD = float(np.std(np.log([0.66, 0.98, 1.27, 1.48, 1.38, 0.88, 0.82])))


def draw(s, t2, t3, gam, rng):
    """(sims x n) scores -> index of the 3, the 2 and the 1 per sim."""
    sims, n = s.shape
    s = s * gam[:, None]
    rows = np.arange(sims)
    w3 = (s + rng.gumbel(size=(sims, n))).argmax(1)
    u2 = t2 * s + rng.gumbel(size=(sims, n))
    u2[rows, w3] = -np.inf
    w2 = u2.argmax(1)
    u1 = t3 * s + rng.gumbel(size=(sims, n))
    u1[rows, w3] = -np.inf
    u1[rows, w2] = -np.inf
    return w3, w2, u1.argmax(1)


def main(argv):
    sims = int(argv[0]) if argv else 20000
    rng = np.random.default_rng(0)
    f = pd.read_csv(os.path.join(ev.OUT, "frame.csv"), low_memory=False)
    f["margin_c"] = f.margin.clip(-60, 60) / 30
    th = ev.fit_pl(pr.train_set(f), pr.FEATS)
    t2, t3 = th[len(pr.FEATS)], th[len(pr.FEATS) + 1]
    preds = pd.read_csv(os.path.join(ev.OUT, f"predictions_{SEASON}.csv"))

    st = pd.read_csv(os.path.join(ev.OUT, f"stats_{SEASON}.csv"), low_memory=False)
    fut = st[(st.status == "SCHEDULED") & st["round.name"].str.startswith("Round")].drop_duplicates("providerId")
    from features import AFL_AWARD_TEAM_FIXES as FIX
    fut = [(FIX.get(h, h), FIX.get(a, a)) for h, a in zip(fut["home.team.name"], fut["away.team.name"])]
    preds["team"] = preds.team.replace(FIX)

    last_rounds = sorted(preds.rnd.unique())[-4:]
    recent = preds[preds.rnd.isin(last_rounds)].groupby(["team", "playerId"]).size()
    squad = {t: [p for (tt, p), n in recent.items() if tt == t and n >= 3] for t in preds.team.unique()}
    names = preds.drop_duplicates("playerId").set_index("playerId").player
    gam = np.exp(rng.normal(0, LOG_GAMMA_SD, sims))

    for scen in ("proportional", "none", "full"):
        col = f"P3_{scen}"
        pid = sorted(preds.playerId.unique())
        ix = {p: i for i, p in enumerate(pid)}
        tot = np.zeros((sims, len(pid)))
        rows = np.arange(sims)

        def award(players, scores):
            s = np.broadcast_to(np.asarray(scores, float), (sims, len(players))).copy()
            w3, w2, w1 = draw(s, t2, t3, gam, rng)
            pl = np.array([ix[p] for p in players])
            np.add.at(tot, (rows, pl[w3]), 3)
            np.add.at(tot, (rows, pl[w2]), 2)
            np.add.at(tot, (rows, pl[w1]), 1)

        for _, g in preds.groupby("matchId"):
            award(list(g.playerId), np.log(g[col].clip(1e-9)).values)
        avg = preds.groupby("playerId")[col].mean()
        for h, a in fut:
            players = squad.get(h, []) + squad.get(a, [])
            award(players, np.log(avg.reindex(players).clip(1e-9)).values)

        top = tot.max(1, keepdims=True)
        share = (tot == top) / (tot == top).sum(1, keepdims=True)
        win = pd.Series(share.mean(0), index=[names[p] for p in pid]).sort_values(ascending=False)
        med = pd.Series(np.median(tot, 0), index=[names[p] for p in pid])
        print(f"\nscenario {scen}: win probability (dead heats shared), {sims:,} seasons")
        for n, p in win.head(8).items():
            print(f"  {n:22} {p:6.1%}   fair odds {1 / p if p else float('inf'):6.2f}   median total {med[n]:.0f}")


if __name__ == "__main__":
    main(sys.argv[1:])
