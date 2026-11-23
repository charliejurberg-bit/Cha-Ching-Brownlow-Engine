"""site/data/aflw/landing.json: the home page's figures for the AFLW season.

Built by aflw/export_site_aflw.py from the live season's frame, in exactly the
schema landing_summary.py writes for the men (components/landing/landing-data.ts
validates both), and with landing_summary's own helpers for club codes, chip
names and colliding surnames, so the two cannot drift apart in form.

Every figure describes rounds already played: the chips and ticker are the
latest round's top three by expected votes, the leader is the season board's.
`brownlowNight` is the AFLW count date from AFLW_COUNT_NIGHT, or null until the
AFL announces it; the page then reads "TBC" rather than counting down to a
guess.
"""

import os
import sys

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import landing_summary as ls  # noqa: E402

AFLW_COUNT_NIGHT = "2026-11-23"   # W Awards, Monday 23 November 2026 (Charlie, 29 Sep 2026)
EM_DASH = ls.EM_DASH


def build(g, se, season):
    """g: the season's game frame (site_frames schema); se: its season board."""
    stats = pd.read_csv(os.path.join(REPO, "data_aflw", f"stats_{int(season)}.csv"), low_memory=False,
                        usecols=["player.player.player.playerId", "player.player.player.surname"])
    surname = dict(zip(stats["player.player.player.playerId"], stats["player.player.player.surname"]))
    g = g.copy()
    g["Surname"] = g.ID.map(surname)
    g["Playing.for"] = g.Team
    latest = int(g.Round_num.max())
    rnd = g[g.Round_num == latest]

    ranked = se.sort_values("Exp_Total_Votes", ascending=False)
    top = float(ranked.Exp_Total_Votes.iloc[0])
    second = float(ranked.Exp_Total_Votes.iloc[1]) if len(ranked) > 1 else top
    return {
        "round": latest,
        "brownlowNight": AFLW_COUNT_NIGHT,
        "leader": {"name": str(ranked.Player_Name.iloc[0]), "votes": round(top, 1),
                   "clear": round(top - second, 1), "bestOdds": EM_DASH},
        "chips": ls.build_chips(rnd),
        "ticker": ls.build_ticker(rnd),
        **({"final": final(se, season)} if (se.Actual_Votes > 0).any() else {}),
    }


def final(se, season):
    """The count, in landing_summary.build_final's shape. Written only once the
    season's votes are saved, which aflw/fetch_votes.py refuses for a partial
    count. Ranks are tie-aware and every player level with the top is a winner."""
    se = se.assign(Actual_Votes=se.Actual_Votes.fillna(0).astype(int)).sort_values(
        ["Actual_Votes", "Player_Name"], ascending=[False, True]).reset_index(drop=True)
    top = int(se.Actual_Votes.iloc[0])
    below = se.loc[se.Actual_Votes < top, "Actual_Votes"]
    board = []
    for _, r in se.head(ls.FINAL_BOARD_N).iterrows():
        v = int(r.Actual_Votes)
        board.append({"rank": int((se.Actual_Votes > v).sum()) + 1, "tied": int((se.Actual_Votes == v).sum()) > 1,
                      "name": str(r.Player_Name).strip(), "team": ls._team_code(r.Team), "votes": v,
                      "model": round(float(r.Exp_Total_Votes), 1)})
    return {"season": int(season), "winners": [b["name"] for b in board if b["votes"] == top], "votes": top,
            "margin": int(top - below.iloc[0]) if not below.empty else 0, "board": board}
