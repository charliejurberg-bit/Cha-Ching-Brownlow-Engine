"""Who wins from here: a conditional 3-2-1 simulator for a count in progress.

    python scripts/count_sim.py --backtest        # calibration over 2008-2025
    python scripts/count_sim.py --backtest --sims 5000 --quick

WHAT IT ANSWERS
Part way through a count, a player sits on N votes and some rounds are still to
be read. Those games are already played and their votes already exist; what is
unknown is only which way they fall. So the question "how likely is he to win
from here" is answered by taking the votes read as fixed, sampling the rounds
still to come from the model's own per-game probabilities, and counting how
often he finishes on top. A player's chance therefore depends on every rival's
remaining draw as well as his own, which is what makes it a simulation rather
than an arithmetic.

THE SAMPLER TRAP, WHICH IS THE REASON THIS IS NOT THREE INDEPENDENT DRAWS
A game awards one 3, one 2 and one 1 to three DIFFERENT players. Drawing the 2
from raw P_2 and the 1 from raw P_1 double counts the case where a player
missed the 3, and it starves exactly the players the count turns on: a star
with a high P_3 carries a low P_2 precisely because he is expected to take the
3, and sampling him at that low rate after he has already missed understates
him. The conditional weights are P_2/(1-P_3) for the two and P_1/(1-P_3-P_2)
for the one, renormalised over the players not yet awarded in that game.

WHY A NUMBER OUT OF THIS GETS BACKTESTED BEFORE IT IS EVER POSTED
An uncalibrated version of this priced a leader at 88% against a market at 96%
and manufactured an edge that was not there. --backtest replays 18 completed
seasons from predictions/backtest_game_level.csv, stops at each checkpoint
round, asks the question as it would have been asked on the night, and compares
the answers against who actually won. A probability that does not survive that
does not go in a tweet.

DISPERSION, AND WHY THE SEASON SCHEDULE DOES NOT TRANSFER
Independent per-game draws under-disperse SEASON totals: real players run hot
and cold in ways a per-game model does not see, and a fitted per-player
multiplier corrects it. That schedule was fitted for a whole season. A count
part way through has already observed most of that spread in the votes read, so
applying the full multiplier to what is left over-corrects. The backtest carries
the variants side by side rather than assuming which one is right.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKTEST = "predictions/backtest_game_level.csv"
DEFAULT_SIMS = 20000
# Players per game the sampler considers. The rest carry a rounding error's
# worth of probability between them and cost time to keep.
TOP_PER_GAME = 12
CHECKPOINTS = (4, 8, 12, 16, 20)

# THE DISPERSION, CHOSEN BY BACKTEST AND NOT BY ARGUMENT.
# --backtest over 2008-2025, 18 seasons and 89 checkpoints, 10,000 sims, one
# fixed candidate set scored by every variant:
#
#   sigma   leader told   leader won   Brier
#   0.00        71.0%        66.3%     0.0179
#   0.10        67.9%        66.3%     0.0174
#   0.15        64.9%        66.3%     0.0176
#   0.20        61.4%        66.3%     0.0178
#   0.30        54.0%        66.3%     0.0188
#
# 0.15 is the pick. It lands the leader inside 1.5 points, the second favourite
# at 20.9% told against 19.1% realised and the third at 10.4% against 6.7%, and
# it holds stage by stage: after round 4 it says 47.9% and 50.0% happens, after
# round 8 55.9% against 55.6%, after round 12 64.8% against 66.7%. Zero
# dispersion is the failure this exists to avoid: it tells the leader 71% in a
# spot he wins two thirds of.
SIGMA = 0.15

# A tie counts as a win for each player tied, because a tied count shares the
# medal and both men are medallists. Two players' chances can therefore add to
# more than 100%: the excess is exactly the probability they finish level,
# counted once for each. It runs over 1.0 for the top two in 26 of 89 backtest
# checkpoints, at most 1.16, and always because a shared medal was genuinely
# live. Splitting ties instead would sum to 1 and would say a shared medal is
# half a win, which is not what the record books say.
# Players scored at each checkpoint. Everyone outside the top 25 on votes plus
# remaining expectation is a rounding error, and scoring a fixed set keeps the
# variants comparable.
CANDIDATES = 25


def _game_arrays(g, top_n=TOP_PER_GAME):
    """(player index, p3, p2, p1) per game, trimmed to the plausible field."""
    out = []
    for _, grp in g.groupby("_gkey", sort=False):
        grp = grp.nlargest(min(top_n, len(grp)), "Poll_Prob")
        p3 = grp.P_3.to_numpy(dtype=np.float64)
        p2 = grp.P_2.to_numpy(dtype=np.float64)
        p1 = grp.P_1.to_numpy(dtype=np.float64)
        if p3.sum() <= 0:
            continue
        out.append((grp._pidx.to_numpy(), p3, p2, p1))
    return out


def _sample_one(weights, rng, n_sims):
    """Row-wise categorical draw from an (n_sims, k) weight matrix."""
    tot = weights.sum(axis=1, keepdims=True)
    bad = tot[:, 0] <= 0
    if bad.any():                       # nothing left to award: spread evenly
        weights = np.where(bad[:, None], 1.0, weights)
        tot = weights.sum(axis=1, keepdims=True)
    cdf = np.cumsum(weights / tot, axis=1)
    u = rng.random((n_sims, 1))
    return (u > cdf).sum(axis=1).clip(0, weights.shape[1] - 1)


def simulate_remaining(games, n_players, n_sims, rng):
    """Votes each player draws from the games still to be read.

    Returns an (n_sims, n_players) int16 array. Each game awards its 3, 2 and 1
    to three different players, drawn on the conditional weights above.
    """
    out = np.zeros((n_sims, n_players), dtype=np.int16)
    rows = np.arange(n_sims)
    for pidx, p3, p2, p1 in games:
        k = len(pidx)
        w3 = np.tile(p3, (n_sims, 1))
        i3 = _sample_one(w3, rng, n_sims)

        # P_2 / (1 - P_3): the player's rate of taking the two GIVEN he did not
        # take the three. Without the division a favourite is sampled at his
        # unconditional P_2, which is low exactly because he was expected to
        # win the three he has just been shown to have missed.
        base2 = np.tile(p2 / np.clip(1.0 - p3, 1e-9, None), (n_sims, 1))
        base2[rows, i3] = 0.0
        i2 = _sample_one(base2, rng, n_sims)

        base1 = np.tile(p1 / np.clip(1.0 - p3 - p2, 1e-9, None), (n_sims, 1))
        base1[rows, i3] = 0.0
        base1[rows, i2] = 0.0
        i1 = _sample_one(base1, rng, n_sims)

        out[rows, pidx[i3]] += 3
        out[rows, pidx[i2]] += 2
        out[rows, pidx[i1]] += 1
    return out


def _disperse(rem, sigma, rng):
    """Multiply each player's remaining haul by a lognormal, mean 1.

    The correction for real players running hotter and colder than independent
    games imply. sigma 0 leaves the draw alone. Rounded stochastically, because
    rounding a fractional shift the same way every time snaps whole vote
    thresholds in one direction.
    """
    if not sigma:
        return rem
    mult = rng.lognormal(-0.5 * sigma ** 2, sigma, size=rem.shape)
    scaled = rem * mult
    floor = np.floor(scaled)
    return (floor + (rng.random(scaled.shape) < (scaled - floor))).astype(np.int16)


def win_probabilities(current, games, n_players, n_sims=DEFAULT_SIMS,
                      sigma=SIGMA, seed=0):
    """P(finishes on top) per player, given votes already read.

    current is an (n_players,) array of votes counted so far. A shared lead
    counts as a win for each player tied on it, because a tied count shares the
    medal. Returns (win probability array, simulated final totals).
    """
    rng = np.random.default_rng(seed)
    rem = simulate_remaining(games, n_players, n_sims, rng)
    rem = _disperse(rem, sigma, rng)
    totals = rem.astype(np.int32) + current.astype(np.int32)
    best = totals.max(axis=1, keepdims=True)
    return (totals == best).mean(axis=0), totals


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def _season_frame(df, season):
    g = df[df.Season == season].copy()
    g = g.drop_duplicates(["Round_num", "ID", "Playing.for"])
    g["_gkey"] = (g.Round_num.astype(str) + "|" + g["Home.team"].astype(str)
                  + "|" + g["Away.team"].astype(str))
    ids = pd.Index(sorted(g.ID.dropna().unique()))
    g = g[g.ID.notna()].copy()
    g["_pidx"] = ids.get_indexer(g.ID)
    return g, ids


def chances_from_frame(remaining, current_by_name, n_sims=DEFAULT_SIMS,
                       sigma=SIGMA, seed=0):
    """{player: chance of finishing on top} for a count in progress.

    `remaining` is the game-level frame for the rounds still to be read, with
    P_1/P_2/P_3 and Poll_Prob; `current_by_name` the votes already read. Also
    returns the simulated final totals per player, which is what the expected
    final tally is read off.
    """
    remaining = remaining.copy()
    remaining["_gkey"] = (remaining.Round_num.astype(str) + "|"
                          + remaining["Home.team"].astype(str) + "|"
                          + remaining["Away.team"].astype(str))
    names = pd.Index(sorted(set(remaining.Player_Name)
                            | set(current_by_name)))
    remaining["_pidx"] = names.get_indexer(remaining.Player_Name)
    current = np.array([current_by_name.get(n, 0) for n in names],
                       dtype=np.float64)
    games = _game_arrays(remaining)
    p, totals = win_probabilities(current, games, len(names), n_sims,
                                  sigma=sigma, seed=seed)
    mean_total = totals.mean(axis=0)
    return ({n: float(p[i]) for i, n in enumerate(names)},
            {n: float(mean_total[i]) for i, n in enumerate(names)})


def backtest(sims=DEFAULT_SIMS, sigmas=(0.0, 0.15, 0.30), quick=False):
    """Replay each completed season and score the answers against the result."""
    df = pd.read_csv(BACKTEST, low_memory=False)
    df = df[pd.to_numeric(df.Round_num, errors="coerce").notna()]
    df["Round_num"] = df.Round_num.astype(int)
    seasons = sorted(df.Season.unique())
    if quick:
        seasons = seasons[-6:]
    rows = []
    for season in seasons:
        g, ids = _season_frame(df, season)
        last = int(g.Round_num.max())
        actual = (g.groupby("_pidx")["Brownlow.Votes"].sum()
                  .reindex(range(len(ids)), fill_value=0.0).to_numpy())
        winners = set(np.flatnonzero(actual == actual.max()).tolist())
        for cp in CHECKPOINTS:
            if cp >= last:
                continue
            counted = g[g.Round_num <= cp]
            current = (counted.groupby("_pidx")["Brownlow.Votes"].sum()
                       .reindex(range(len(ids)), fill_value=0.0).to_numpy())
            ahead = g[g.Round_num > cp]
            games = _game_arrays(ahead)
            # ONE candidate set, scored by every sigma. Taking each variant's
            # own "players above a floor" makes the row sets differ and the
            # Brier scores incomparable: a wider variant is credited for the
            # extra near-zero rows it alone reports, which flatters it.
            exp_rem = (ahead.groupby("_pidx").Exp_Votes.sum()
                       .reindex(range(len(ids)), fill_value=0.0).to_numpy())
            cand = set(np.argsort(-(current + exp_rem))[:CANDIDATES].tolist())
            cand |= winners
            for sigma in sigmas:
                p, _ = win_probabilities(current, games, len(ids), sims,
                                         sigma=sigma, seed=season * 100 + cp)
                for idx in sorted(cand):
                    rows.append({"season": season, "cp": cp, "sigma": sigma,
                                 "pidx": int(idx), "p": float(p[idx]),
                                 "won": int(idx in winners)})
        print(f"  {season} done", flush=True)
    return pd.DataFrame(rows)


def report(res):
    """Calibration and sharpness per sigma, plus the leader's own record."""
    print(f"\n{'=' * 72}\nCALIBRATION, {res.season.nunique()} seasons, "
          f"checkpoints {sorted(res.cp.unique())}\n{'=' * 72}")
    bins = [0, .05, .15, .3, .5, .7, .9, 1.01]
    for sigma, sub in res.groupby("sigma"):
        brier = float(((sub.p - sub.won) ** 2).mean())
        print(f"\nsigma {sigma}:  Brier {brier:.4f}  "
              f"(rows {len(sub)}, winners {int(sub.won.sum())})")
        sub = sub.copy()
        sub["band"] = pd.cut(sub.p, bins, right=False)
        t = sub.groupby("band", observed=True).agg(
            n=("p", "size"), predicted=("p", "mean"), realised=("won", "mean"))
        for band, r in t.iterrows():
            flag = ""
            if r.n >= 8:
                d = r.predicted - r.realised
                flag = "   overconfident" if d > 0.12 else (
                    "   underconfident" if d < -0.12 else "")
            print(f"  {str(band):>14}  n {int(r.n):4}  said "
                  f"{r.predicted:6.1%}  happened {r.realised:6.1%}{flag}")

    print(f"\n{'=' * 72}\nTHE LEADER AT EACH CHECKPOINT\n{'=' * 72}")
    for sigma, sub in res.groupby("sigma"):
        lead = sub.loc[sub.groupby(["season", "cp"]).p.idxmax()]
        print(f"  sigma {sigma}: leader said {lead.p.mean():6.1%}, "
              f"won {lead.won.mean():6.1%}, over {len(lead)} checkpoints")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--sims", type=int, default=DEFAULT_SIMS)
    ap.add_argument("--quick", action="store_true", help="last 6 seasons only")
    ap.add_argument("--sigmas", default="0.0,0.15,0.30")
    args = ap.parse_args(argv)
    if not args.backtest:
        raise SystemExit("nothing to do: pass --backtest")
    sig = tuple(float(x) for x in args.sigmas.split(","))
    res = backtest(sims=args.sims, sigmas=sig, quick=args.quick)
    report(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
