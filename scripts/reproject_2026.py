"""Recompute 2026's Floor_Projection and Ceiling_Projection in place.

Run from the repository root, not from inside scripts/:
    python scripts/reproject_2026.py

Why this exists rather than a re-run of predict_2026.py
-------------------------------------------------------
The Monte Carlo in predict_2026.py averaged each player's p1/p2/p3 across his
season and drew multinomial(games_played, p_avg), treating 22 different games as
22 identical ones. That is mean-preserving, so Exp_Total_Votes and every ranking
were correct and nothing looked wrong. It inflates the variance though: one draw
at the average p is more uncertain than the average of draws at each game's own
p. Every band was too wide, in the same direction, for every player. Across the
2026 top 15 the mean interval was 14.5 votes where the model implies 9.2, a 36%
overstatement, ceilings ~2.8 votes high and floors ~2.5 low.

predict_2026.py is fixed. This script exists because 2026 does not need the
model re-run to get the right answer: P_1, P_2 and P_3 in
predictions/game_level_2026.csv are already correct and already committed, and
floor and ceiling are a pure function of them. Recomputing from that file means
the model never re-runs, no artifact can shift underneath, and the change is
provably confined to two columns. The script asserts exactly that before it
writes, and refuses if anything else moved.

The season is complete at raw round 25, so these are the final figures before
count night. Rerunning after any future change to game_level_2026.csv is safe
and idempotent: same input, same seed, same output.

Duplicate rows, deliberately kept
---------------------------------
game_level_2026.csv carries 89 duplicated Round_num + ID rows, so 11 players
have an inflated game count. That is a real upstream defect, recorded in
CLAUDE.md, and it is NOT corrected here. The published Exp_Total_Votes already
includes those rows, so deduplicating for the band alone would produce an
interval that disagrees with the total printed beside it. The band stays
consistent with its own total; the duplicates are a separate fix.
"""

import os
import sys

import numpy as np
import pandas as pd

GAME = "predictions/game_level_2026.csv"
PROJ = "predictions/season_projection_2026.csv"
SIMS = 10_000
SEED = 42
# Every column that must come through untouched. Only the two band columns may
# differ; anything else moving means this script did more than it claims.
FROZEN = ['Player', 'Team', 'Actual_Votes', 'Games_Played',
          'Avg_Predicted_Per_Game', 'Remaining_Rounds',
          'Projected_Remaining', 'Season_Total_Projected']


def bands(game_df):
    """10th/90th percentile of the season total, sampling each game separately.

    A player's games are independent draws from DIFFERENT categorical
    distributions over {0,1,2,3}. Summing them is the whole computation; there
    is no averaging step to be had.
    """
    rng = np.random.default_rng(SEED)
    floor, ceil = {}, {}
    for name, pg in game_df.groupby('Player_Name'):
        P = pg[['P_1', 'P_2', 'P_3']].to_numpy(dtype=float)
        p0 = np.clip(1.0 - P.sum(axis=1), 0, None)
        pr = np.column_stack([p0, P]).clip(0)
        pr /= pr.sum(axis=1, keepdims=True)
        cdf = pr.cumsum(axis=1)
        u = rng.random((len(pr), SIMS))
        sim = (cdf[:, :, None] < u[:, None, :]).sum(axis=1).sum(axis=0)
        floor[name] = float(np.percentile(sim, 10))
        ceil[name] = float(np.percentile(sim, 90))
    return floor, ceil


def main():
    for p in (GAME, PROJ):
        if not os.path.exists(p):
            print(f"FAIL  {p} not found. Run from the repository root.")
            return 1

    g = pd.read_csv(GAME)
    old = pd.read_csv(PROJ)

    # The raw frame, duplicates included, because that is the population
    # predict_2026.py projected and the one Games_Played already counts.
    counts = g.groupby('Player_Name').size()
    mismatched = [p for p, n in zip(old.Player, old.Games_Played)
                  if counts.get(p) != n]
    if mismatched:
        print(f"FAIL  {len(mismatched)} player(s) whose Games_Played does not match "
              f"{GAME}, e.g. {mismatched[:5]}. The projection was built from a "
              f"different frame than this file and must not be rewritten from it.")
        return 1

    floor, ceil = bands(g)
    new = old.copy()
    new['Floor_Projection'] = new['Player'].map(floor).fillna(0).round(1)
    new['Ceiling_Projection'] = new['Player'].map(ceil).fillna(0).round(1)

    for c in FROZEN:
        if not old[c].equals(new[c]):
            print(f"FAIL  column {c} changed; this script may only touch the "
                  f"two band columns. Nothing written.")
            return 1
    if list(old.columns) != list(new.columns) or len(old) != len(new):
        print("FAIL  shape or column order changed. Nothing written.")
        return 1

    d_c = (new.Ceiling_Projection - old.Ceiling_Projection)
    d_f = (new.Floor_Projection - old.Floor_Projection)
    w_old = (old.Ceiling_Projection - old.Floor_Projection)
    w_new = (new.Ceiling_Projection - new.Floor_Projection)
    wider = int((w_new > w_old).sum())

    new.to_csv(PROJ, index=False)
    print(f"OK  rewrote {PROJ}: {len(new)} players, two columns changed, "
          f"{len(FROZEN)} columns verified unchanged")
    print(f"    mean interval {w_old.mean():.2f} -> {w_new.mean():.2f} votes "
          f"({(1 - w_new.mean() / w_old.mean()) * 100:.0f}% narrower)")
    print(f"    ceiling {d_c.mean():+.2f} votes, floor {d_f.mean():+.2f} votes, "
          f"on average")
    print(f"    {wider} player(s) ended up with a WIDER band "
          f"(expected: few, and only from Monte Carlo noise on tiny samples)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
