"""AFLW season frames in the men's game-level schema, for the site export.

The site's exporters (export_site.py) read the men's frames through
site_data.load_game / load_season. aflw/export_site_aflw.py points those loaders
at the frames built here, so every AFLW page is produced by the same code, and
therefore in the same shape, as its men's page.

EVERY PREDICTION IS OUT OF SAMPLE. A season's figures come from a model fitted
on the OTHER labelled seasons: pl_coach (coaches votes included) where the
season has coaches votes, pl_full where it does not (2017, 2022). The live
season uses every labelled season with coaches votes plus the 2026 regime
layer's default scenario (aflw/predict.py). A season's history page therefore
shows what the model would have said without having seen its count.

Season ids are numbers, as the site's routes expect. 2022 held two seasons, so
they are 2022.6 and 2022.7, labelled "2022 S6" / "2022 S7" by SEASON_LABELS.
2018 and 2019 are left out: no votes per match or complete totals exist, so a
history page for them would show predictions against nothing.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate as ev  # noqa: E402
import predict as pr  # noqa: E402
import regime as rg  # noqa: E402

SEASON_IDS = {"2017": 2017, "2020": 2020, "2021": 2021, "2022S6": 2022.6, "2022S7": 2022.7,
              "2023": 2023, "2024": 2024, "2025": 2025, "2026": 2026}
SEASON_LABELS = {2022.6: "2022 S6", 2022.7: "2022 S7"}
LIVE = "2026"


def frame():
    f = pd.read_csv(os.path.join(ev.OUT, "frame.csv"), low_memory=False)
    f["margin_c"] = f.margin.clip(-60, 60) / 30
    return f


def probs(f, season):
    """(P3, P2, P1) for one season, from a model that never saw its votes."""
    lab = f[f.label_kind == "match"]
    test = rg.zs(f[f.season == season].reset_index(drop=True))
    if season == LIVE:
        th = ev.fit_pl(pr.train_set(f), pr.FEATS)
        delta = pr.regime_delta(f)["proportional"]
        k = len(pr.FEATS)
        return test, ev.pl_probs(test, pr.score(test, th, 1.0, delta), th[k], th[k + 1])
    train = lab[lab.season != season]
    has_cv = test.coaches.notna().any()
    feats = pr.FEATS if has_cv else ev.FULL
    if has_cv:
        train = train.dropna(subset=["coaches"])
    th = ev.fit_pl(train.reset_index(drop=True), feats)
    k = len(feats)
    return test, ev.pl_probs(test, test[feats].fillna(0).values @ th[:k], th[k], th[k + 1])


# The AFL writes six clubs in marketing form ("Gold Coast SUNS"); the site's
# club codes and colours key on the plain names the men's files use.
from features import AFL_AWARD_TEAM_FIXES as TEAM_FIXES  # noqa: E402


def to_mens_schema(d, P, sid):
    """The columns site_data's consumers read, named as in game_level_*.csv."""
    d = d.copy()
    for c in ("team", "home", "away", "opponent"):
        d[c] = d[c].replace(TEAM_FIXES)
    home = d.team == d.home
    score = d.score.where(home, d.opp_score)
    oscore = d.opp_score.where(home, d.score)
    g = pd.DataFrame({
        "Season": sid, "Round_num": d.rnd.astype(int), "Game_ID": d.matchId,
        "ID": d.playerId, "Player_Name": d.player, "Team": d.team, "Playing.for": d.team,
        "Home.team": d.home, "Away.team": d.away,
        "Home.score": score, "Away.score": oscore,
        "Is_Win": (d.margin > 0).astype(int), "Is_Loss": (d.margin < 0).astype(int),
        "Disposals": d.disposals, "Goals": d.goals, "Kicks": d.kicks,
        "Clearances": d["clearances.totalClearances"], "Contested.Possessions": d.contestedPossessions,
        "Coaches_Votes": d.coaches, "Tackles": d.tackles,
        "Score_Involvements_Actual": d.scoreInvolvements,
        # Per-match votes where known; NaN where the season has only totals
        # (2023) or no count yet, so no page reads an unknown as a zero.
        "Brownlow.Votes": d.votes.where(d.label_kind == "match"),
        "P_3": P[:, 0], "P_2": P[:, 1], "P_1": P[:, 2],
    })
    g["Poll_Prob"] = g.P_1 + g.P_2 + g.P_3
    g["Exp_Votes"] = 3 * g.P_3 + 2 * g.P_2 + g.P_1
    # Same-name players in one season are told apart by club, as the men's
    # _disambiguate_players does; AFL player ids decide who is one person.
    g["_base_name"] = g.Player_Name
    clash = g.groupby("Player_Name").ID.transform("nunique") > 1
    last_team = g.sort_values("Round_num").groupby("ID").Team.last()
    g.loc[clash, "Player_Name"] = g.loc[clash, "Player_Name"] + " (" + g.loc[clash, "ID"].map(last_team) + ")"
    return g, d


def build_all():
    """{season id: (game frame, season totals frame)}."""
    f = frame()
    out = {}
    for label, sid in SEASON_IDS.items():
        if label not in set(f.season):
            continue
        d, P = probs(f, label)
        g, d = to_mens_schema(d, P, sid)
        tot = d.groupby("playerId").season_total.first() if d.season_total.notna().any() else None
        se = g.groupby("Player_Name").agg(
            Team=("Team", "last"), Games=("Round_num", "size"), Exp_Total_Votes=("Exp_Votes", "sum"),
            Avg_Poll_Prob=("Poll_Prob", "mean"), Exp_3vote_games=("P_3", "sum"),
            Exp_2vote_games=("P_2", "sum"), Exp_1vote_games=("P_1", "sum"), ID=("ID", "first"),
        ).reset_index()
        se["Actual_Votes"] = se.ID.map(tot).fillna(0) if tot is not None and label != LIVE else 0
        se = se.sort_values("Exp_Total_Votes", ascending=False).reset_index(drop=True)
        out[sid] = (g, se)
        print(f"  {label:7} -> {sid}: {g.Game_ID.nunique()} matches, {len(se)} players", flush=True)
    return out
