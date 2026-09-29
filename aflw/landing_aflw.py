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

AFLW_COUNT_NIGHT = None          # e.g. "2026-11-23" once announced
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
    }
