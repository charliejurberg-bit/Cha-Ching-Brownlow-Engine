"""How well the 2026 probabilities matched the count, for the two P(3)s in use.

    python scripts/calibration_2026.py

Two different figures were called "the model's P(3)" after the count, and a
table of one was once recorded as if it were the other. Both are printed here
so neither has to be taken on trust:

  displayed   P_3_game, the within-game fitted P(3) (_fit_game_probs) that
              Game Analysis and the Player Profile showed readers. This is the
              table on the site's Model Insights tab (export_site
              ._forward_scorecard).
  priced      that figure through the isotonic map scripts/sb_3vote_board.py
              fits on the 2008-2025 backtest, the one used to price Sportsbet's
              3-vote board. Never shown to a reader.

Buckets [from, to) on the stated probability; "took" is how many actually
polled 3. A player carried twice in one game counts once.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_data as sd  # noqa: E402

EDGES = [0.05, 0.10, 0.20, 0.35, 0.60, 1.0001]
KEY = ["Round_num", "Home.team", "Away.team", "Player_Name"]


def table(label, p, got):
    b = pd.cut(p, EDGES, right=False)
    t = pd.DataFrame({"p": p, "got": got}).groupby(b, observed=True).agg(
        n=("p", "size"), said=("p", "mean"), took=("got", "sum"))
    print(label)
    for iv, r in t.iloc[::-1].iterrows():
        print(f"  {iv.left:.2f} to {min(iv.right, 1):.2f}   n {int(r.n):>4}   said {r.said:6.1%}   "
              f"took {int(r.took):>3} = {r.took / r.n:6.1%}")


def favourite(label, df, col):
    top = df.loc[df.groupby("_gid")[col].idxmax()]
    print(f"  favourite in each game ({label}): said {top[col].mean():.1%}, took the 3 in "
          f"{int(top['_got'].sum())} of {len(top)} = {top['_got'].mean():.1%}")


def main():
    g = sd.load_game(2026).drop_duplicates(KEY).copy()
    g["_got"] = pd.to_numeric(g["Brownlow.Votes"], errors="coerce").eq(3)
    g["_gid"] = g["Round_num"].astype(str) + "|" + g["Home.team"] + "|" + g["Away.team"]
    table("displayed P(3) (P_3_game), every 2026 player-game", g["P_3_game"], g["_got"])
    favourite("displayed", g, "P_3_game")

    import sb_3vote_board as sb
    m = sb.model_probs().drop_duplicates(KEY)
    v = pd.read_csv("data_2026/brownlow_votes_2026.csv")[KEY + ["Brownlow.Votes"]]
    m = m.drop(columns=["Brownlow.Votes"]).merge(v, on=KEY, how="left")
    m["_got"] = m["Brownlow.Votes"].eq(3)
    m["_gid"] = m["Round_num"].astype(str) + "|" + m["Home.team"] + "|" + m["Away.team"]
    print()
    table("priced P(3) (isotonic, sb_3vote_board.model_probs), every 2026 player-game", m["P"], m["_got"])
    favourite("priced", m, "P")


if __name__ == "__main__":
    main()
