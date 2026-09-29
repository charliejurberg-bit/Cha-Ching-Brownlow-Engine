"""Write the AFLW half of the site's data, under site/data/aflw/.

    python aflw/export_site_aflw.py

The same exporters as the men's (export_site.py), fed AFLW frames: site_data's
loaders are pointed at aflw/site_frames.py for the length of this process, so
Leaderboard, Game Analysis, Player Profile and Stat Filter files come out in
exactly the shapes the men's pages already read. Run it as its own process;
nothing here is safe to import alongside a men's export.

AFLW-only pieces written here: tracker.json (the Live Tracker; the stats carry
the AFL's own player ids, so the feed joins by id with no name bridge),
modelcomp.json (Insights only: no bookmaker or outside model publishes AFLW
vote predictions to compare against) and polls.json (Cha Ching's own signal
only, for the same reason), plus index.json with display labels for the two
2022 seasons.
"""

import os
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

import export_site as es  # noqa: E402
import site_data as sd  # noqa: E402
import site_frames as sf  # noqa: E402
import evaluate as ev  # noqa: E402
import features as feat  # noqa: E402

OUT = os.path.join("site", "data", "aflw")
LIVE = sf.SEASON_IDS[sf.LIVE]


def install(frames):
    """Point site_data at the AFLW frames."""
    fit = sd._fit_game_probs
    games = {s: fit(g.copy()) for s, (g, _) in frames.items()}
    seasons = {s: se for s, (_, se) in frames.items()}
    sd._memo.clear()
    sd.LIVE_SEASON = LIVE
    sd.available_seasons = lambda: sorted(games, reverse=True)
    sd.load_game = lambda s: games.get(s)
    sd.load_season = lambda s: seasons.get(s)
    sd.display_round = lambda rn, s: int(rn)          # AFLW rounds are the official numbers
    sd.load_best_odds = lambda: None
    sd.load_season_projection = lambda: None
    sd.voted_seasons = lambda g: sorted({es._sid(s) for s, t in g.groupby("Season")["Brownlow.Votes"].sum().items() if t > 0})

    def career():
        g = pd.concat([games[s].assign(Season=s) for s in sorted(games)], ignore_index=True)
        g["_season_name"] = g.Player_Name
        g["Player_Name"] = g._base_name
        clash = g.groupby("Player_Name").ID.transform("nunique") > 1
        last = g.sort_values(["Season", "Round_num"]).groupby("ID").Team.last()
        g.loc[clash, "Player_Name"] = g.loc[clash, "Player_Name"] + " (" + g.loc[clash, "ID"].map(last) + ")"
        return g
    sd.load_game_career = career

    def stat_filter():
        g = pd.concat([games[s].assign(Season=int(float(s))) for s in games], ignore_index=True)
        g["ID"] = g.ID.str.replace(r"\D", "", regex=True).astype("int64")
        floors = {c: int(g.loc[g[c].notna(), "Season"].min()) for c in sd.SF_SLIDER_COLS
                  if c in g.columns and g[c].notna().any()}
        newest = g.sort_values("Season").drop_duplicates("ID", keep="last").set_index("ID")
        name = newest.Player_Name.astype(str)
        dup = name.groupby(name).transform("size") > 1
        labels = {pid: (f"{n} ({newest.Team[pid]})" if dup[pid] else n) for pid, n in name.items()}
        return g, {"null_ids_dropped": 0, "floors": floors, "labels": labels}
    sd.load_stat_filter_frame = stat_filter
    es.OUT_DIR = OUT
    return games


def tracker(g):
    """tracker.json for the live season, in export_tracker's shape."""
    g = g.drop_duplicates(["Game_ID", "Player_Name"]).reset_index(drop=True)
    last = g.sort_values("Round_num").groupby("Player_Name").last()
    names = sorted(last.index)
    pix = {n: i for i, n in enumerate(names)}
    players = [{"n": n, "b": str(last.loc[n, "_base_name"]), "p": str(last.loc[n, "_base_name"]),
                "t": str(last.loc[n, "Team"]), "id": str(last.loc[n, "ID"]),
                "k": feat.normalise_name(last.loc[n, "_base_name"])} for n in names]
    gm = g.drop_duplicates("Game_ID").sort_values(["Round_num", "Home.team"])
    gix = {k: i for i, k in enumerate(gm.Game_ID)}
    rows = {"pi": [pix[n] for n in g.Player_Name], "dr": [int(r) for r in g.Round_num],
            "g": [gix[k] for k in g.Game_ID]}
    for key, col in (("ev", "Exp_Votes"), ("pp", "Poll_Prob"), ("p1", "P_1"), ("p2", "P_2"), ("p3", "P_3")):
        rows[key] = [es._num(x, 3) for x in g[col]]
    counted = g["Brownlow.Votes"].notna().all()
    if counted:
        rows["bv"] = [int(v) for v in g["Brownlow.Votes"]]
    return {"season": LIVE, "counted": bool(counted), "countNight": None,
            "games": [[int(r), str(h), str(a)] for r, h, a in zip(gm.Round_num, gm["Home.team"], gm["Away.team"])],
            "players": players, "rows": rows,
            # The AFL's own player ids are the feed's ids: the map is exact.
            "feedMap": {str(last.loc[n, "ID"]): pix[n] for n in names}}


def insights(frames):
    """modelcomp.json: no consensus board (no outside AFLW models exist), and
    Insights built from each season's out-of-sample predictions."""
    out = []
    for s, (g, se) in sorted(frames.items()):
        # A season with partial actuals cannot give the top-10 error, and its
        # rank tests would rest on a published list alone: kept off Insights.
        if s == LIVE or se.Actual_Votes.isna().any():
            continue
        top10 = se.nlargest(10, "Exp_Total_Votes")
        top = se.Actual_Votes.max()
        if top <= 0:
            continue
        rk = se.Exp_Total_Votes.rank(ascending=False, method="min")
        winners = se[se.Actual_Votes == top]
        ranks = [int(rk[i]) for i in winners.index]
        out.append({
            "season": es._sid(s), "winner": " & ".join(winners.Player_Name),
            "predRank": min(ranks), "top3": min(ranks) <= 3, "top5": min(ranks) <= 5, "top10": min(ranks) <= 10,
            "avgErr": round(float((top10.Exp_Total_Votes - top10.Actual_Votes).abs().mean()), 1),
            "scatter": [[str(p), str(t), es._num(a, 1), es._num(v, 2), bool(a == top)]
                        for p, t, a, v in zip(top10.Player_Name, top10.Team, top10.Actual_Votes, top10.Exp_Total_Votes)],
        })
    # "What drives votes": the live model's standardised weights, as shares.
    f = sf.frame()
    th = ev.fit_pl(sf.pr.train_set(f), sf.pr.FEATS)
    w = pd.Series(np.abs(th[:len(sf.pr.FEATS)]), index=sf.pr.FEATS)
    w = (w / w.sum() * 100).sort_values(ascending=False)
    empty = {"rows": [], "agreeThr": 0, "nModels": 0}
    return {"season": LIVE, "counted": False, "hasPredictions": True,
            "boards": {"decimal": empty, "rounded": None},
            "stamps": {"afl": None, "espn": None, "betfair": None},
            "insights": {"btMin": es._sid(min(x["season"] for x in out)), "btMax": es._sid(max(x["season"] for x in out)),
                         "seasons": out},
            "importance": [[k, round(float(v), 2)] for k, v in w.items()]}


def main():
    frames = sf.build_all()
    install(frames)
    ids = sorted(frames)
    season_slug = es.export_profiles(ids)
    for s in ids:
        lb = es.export_leaderboard(s, season_slug.get(es._sid(s), {}))
        part = os.path.join(sf.ev.OUT, f"totals_partial_{int(s)}.csv") if float(s).is_integer() else ""
        if part and os.path.exists(part):
            src = pd.read_csv(part)
            lb["partialActuals"] = {"published": int(len(src)), "sources": sorted(set(src.source))}
        es._write(os.path.join(OUT, "leaderboard", f"{es._sid(s)}.json"), lb)
        ga = es.export_games(s, season_slug.get(es._sid(s), {}))
        es._write(os.path.join(OUT, "games", f"{es._sid(s)}.json"), ga)
        print(f"  {es._sid(s)}: leaderboard {len(lb['boards']['decimal']['players'])} players, games {len(ga['games'])}")
    sfo = es.export_stat_filter()
    sfo["comp"] = "aflw"
    es._write(os.path.join(OUT, "statfilter.json"), sfo)
    es._write(os.path.join(OUT, "tracker.json"), tracker(sd.load_game(LIVE)))
    es._write(os.path.join(OUT, "modelcomp.json"), insights(frames))
    es._write(os.path.join(OUT, "polls.json"), {
        "season": LIVE, "afl": None, "aflRound": None, "bf": None, "bfRound": None,
        "wh": {}, "whRound": {}, "espn": None, "espnRound": None, "espnRounds": []})
    seasons = sorted((es._sid(s) for s in ids), reverse=True)
    es._write(os.path.join(OUT, "index.json"), {
        "liveSeason": LIVE, "currentSeason": LIVE,
        "counted": [s for s in seasons if s != LIVE], "seasons": seasons,
        "labels": {str(k): v for k, v in sf.SEASON_LABELS.items()},
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    print(f"  index: {len(seasons)} seasons, live {LIVE}")


if __name__ == "__main__":
    main()
