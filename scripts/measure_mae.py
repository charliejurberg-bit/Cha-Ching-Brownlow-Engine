"""Out-of-sample MAE of the vote model, from files already on disk.

    python scripts/measure_mae.py

Replaces the retired v1-v4 figures (all measured with the momentum leak in
place; see CLAUDE.md, "Model architecture"). Nothing is retrained. Two sets,
both genuinely out of sample:

  walk-forward   predictions/backtest_game_level.csv, each season predicted by a
                 model trained only on the seasons before it (backtest.py)
  forward        every completed season after the model's training range, read
                 from predictions/game_level_<s>.csv once its count is saved
                 (season.counted), which is what the public site showed

MAE is per player-game, |actual votes - Exp_Votes|, beside the all-zero
baseline (predict 0 for everyone), because a vote is 0 for about 87% of rows
and the bare MAE means little without it. A player carried twice in one game
(CLAUDE.md, 2025 round 24) counts once.

Measured 29 September 2026: walk-forward 2008-2025 0.1126 (baseline 0.1346,
3,468 games); forward 2026 0.0920 (baseline 0.1304, 207 games).
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import season as season_cfg  # noqa: E402

KEY = ["Season", "Round_num", "Home.team", "Away.team", "Player_Name"]
TRAIN_MAX = 2025  # brownlow_model.py trains on fitzroy_stats_all.csv, 2007-2025


def line(label, d):
    y = d["Brownlow.Votes"].astype(float)
    p = d["Exp_Votes"].astype(float)
    games = d.groupby(KEY[:4]).ngroups
    print(f"  {label:24} MAE {np.abs(y - p).mean():.4f}   all-zero {y.abs().mean():.4f}   "
          f"{games:,} games, {len(d):,} player-games")


def main():
    bt = pd.read_csv("predictions/backtest_game_level.csv")
    bt = bt.dropna(subset=["Brownlow.Votes", "Exp_Votes"]).drop_duplicates(KEY)
    print("Walk-forward (backtest_game_level.csv)")
    line(f"{int(bt.Season.min())}-{int(bt.Season.max())}", bt)
    for s, d in bt.groupby("Season"):
        line(str(int(s)), d)

    print("Forward (seasons after training, counted)")
    for s in range(TRAIN_MAX + 1, season_cfg.LIVE_SEASON + 1):
        path = season_cfg.pred_path("game_level_{s}.csv", s)
        if not (season_cfg.counted(s) and os.path.exists(path)):
            continue
        g = pd.read_csv(path, low_memory=False).drop_duplicates(KEY)
        if g["Brownlow.Votes"].fillna(0).sum() == 0:
            print(f"  {s}: counted but not backfilled; run season_rollover.py")
            continue
        line(str(s), g)


if __name__ == "__main__":
    main()
