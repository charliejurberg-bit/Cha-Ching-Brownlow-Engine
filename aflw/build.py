"""The AFLW modelling frame: one row per player per home-and-away match.

    python aflw/build.py

Writes data_aflw/frame.csv. Columns:

  keys      season (2017 ... 2022S6, 2022S7 ... 2026), rnd, matchId, playerId,
            player, team, opponent, utc
  stats     the AFL's per-match player stats (ratingPoints left out: it exists
            only for 2018 and half of 2019)
  context   team score, opponent score, margin, win
  ingame    within-match rank, percentile and z-score of the key stats, the
            relative features that carried the men's model
  coaches   the AFLCA votes for the match (NaN where the season has none:
            2017 and 2022 are missing from fitzRoy)
  label     votes: 0-3 where the season's per-match votes are known, NaN where
            only season totals are (see `label_kind`); season_total: the
            player's published total, wherever a totals file exists

label_kind is "match" (votes per match known), "total" (only the season total
is known, see aflw/recover_totals.py) or "none" (nothing published yet, 2026).
A "match" season's players who polled nothing read 0, which is exact: every
match of those seasons totals 6 in its source.
"""

import glob
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recover_votes as rv  # noqa: E402

OUT = rv.OUT
P = "player.player.player."

STATS = ["timeOnGroundPercentage", "goals", "behinds", "kicks", "handballs", "disposals", "marks",
         "bounces", "tackles", "contestedPossessions", "uncontestedPossessions", "totalPossessions",
         "inside50s", "marksInside50", "contestedMarks", "hitouts", "onePercenters",
         "disposalEfficiency", "clangers", "freesFor", "freesAgainst", "dreamTeamPoints",
         "rebound50s", "goalAssists", "turnovers", "intercepts", "tacklesInside50", "shotsAtGoal",
         "scoreInvolvements", "metresGained", "clearances.centreClearances",
         "clearances.stoppageClearances", "clearances.totalClearances"]

# The within-match relative features. The men's model found the rank of a
# player's figure in his own game worth more than the raw figure: a 20-disposal
# game is best on ground one week and anonymous the next.
INGAME = ["disposals", "dreamTeamPoints", "contestedPossessions", "clearances.totalClearances",
          "goals", "metresGained", "scoreInvolvements", "tackles", "intercepts", "marks",
          "inside50s", "hitouts", "coaches"]


def seasons():
    out = []
    for f in sorted(glob.glob(os.path.join(OUT, "stats_*.csv"))):
        year = re.search(r"stats_(\d{4})", f).group(1)
        out += [year + "S6", year + "S7"] if year == "2022" else [year]
    return out


def load(season):
    st = rv.load_stats(season)
    df = pd.DataFrame({
        "season": season, "rnd": st.rnd.values, "matchId": st.providerId.values,
        "playerId": st[P + "playerId"].values,
        "player": (st[P + "givenName"] + " " + st[P + "surname"]).values,
        "team": st["team.name"].values, "home": st["home.team.name"].values,
        "away": st["away.team.name"].values, "utc": st.utcStartTime.values,
        "_given": st._given.values, "_sur": st._sur.values,
    })
    for c in STATS:
        df[c] = pd.to_numeric(st[c], errors="coerce").values
    return df.drop_duplicates(["matchId", "playerId"])


def add_context(df):
    df["opponent"] = np.where(df.team == df.home, df.away, df.home)
    pts = (df.goals.fillna(0) * 6 + df.behinds.fillna(0)).groupby([df.matchId, df.team]).sum()
    df["score"] = [pts.get((m, t), np.nan) for m, t in zip(df.matchId, df.team)]
    df["opp_score"] = [pts.get((m, o), np.nan) for m, o in zip(df.matchId, df.opponent)]
    df["margin"] = df.score - df.opp_score
    df["win"] = np.sign(df.margin)
    return df


def add_coaches(df, season):
    """AFLCA votes by name within club and round. Unplaced names are reported;
    a player the feed does not name got none, which is what the 0 fill says."""
    path = os.path.join(OUT, f"coaches_{season[:4]}.csv")
    df["coaches"] = np.nan
    if not os.path.exists(path) or season.startswith("2022"):
        return df, None
    c = pd.read_csv(path)
    df["coaches"] = 0.0
    miss = 0
    for (rnd, h, a), g in c.groupby(["Round", "Home.Team", "Away.Team"]):
        try:
            clubs = {rv.club(h), rv.club(a)}
        except ValueError:
            miss += len(g); continue
        m = df[(df.rnd == int(rnd)) & df.home.isin(clubs) & df.away.isin(clubs)]
        if m.matchId.nunique() != 1:
            miss += len(g); continue
        for nm, v in zip(g["Player.Name"], g["Coaches.Votes"]):
            mm = re.fullmatch(r"(.+?)\s*\((\w+)\)", str(nm))
            name, code = (mm.group(1), mm.group(2)) if mm else (nm, None)
            try:
                cand = m[m.team == rv.club(code)] if code else m
            except ValueError:
                cand = m
            hit = rv._find(cand.rename(columns={"team": "_team"}).assign(
                **{P + "playerId": cand.playerId}), name)
            if len(hit) != 1:
                miss += 1; continue
            df.loc[(df.matchId == m.matchId.iloc[0]) & (df.playerId == hit[P + "playerId"].iloc[0]),
                   "coaches"] = float(v)
    return df, miss


def add_ingame(df):
    g = df.groupby("matchId")
    for c in INGAME:
        x = df[c]
        df[f"{c}_rank"] = g[c].rank(ascending=False, method="min")
        df[f"{c}_pct"] = g[c].rank(pct=True)
        mu, sd = g[c].transform("mean"), g[c].transform("std")
        df[f"{c}_z"] = (x - mu) / sd.replace(0, np.nan)
    return df


def add_labels(df, season):
    vpath = os.path.join(OUT, f"votes_{season}.csv")
    tpath = os.path.join(OUT, f"totals_{season}.csv")
    df["votes"], df["season_total"], df["label_kind"] = np.nan, np.nan, "none"
    if os.path.exists(vpath):
        v = pd.read_csv(vpath)
        key = dict(zip(zip(v.matchId, v.playerId), v.votes))
        df["votes"] = [key.get((m, p), 0) for m, p in zip(df.matchId, df.playerId)]
        missing = set(key) - set(zip(df.matchId, df.playerId))
        if missing:
            raise SystemExit(f"{season}: {len(missing)} vote rows match no player-match in the stats")
        df["label_kind"] = "match"
        df["season_total"] = df.groupby("playerId").votes.transform("sum")
    elif os.path.exists(tpath):
        t = pd.read_csv(tpath)
        tot = dict(zip(t.playerId, t.votes))
        df["season_total"] = df.playerId.map(tot).fillna(0)
        df["label_kind"] = "total"
    return df


def main():
    frames = []
    for s in seasons():
        df = add_context(load(s))
        df, miss = add_coaches(df, s)
        df = add_ingame(df)
        df = add_labels(df, s)
        cv = "none" if miss is None else f"{int((df.coaches > 0).sum())} rows, {miss} unplaced"
        print(f"  {s:7} {df.matchId.nunique():>3} matches  {len(df):>5} rows  labels {df.label_kind.iloc[0]:5}  coaches {cv}")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True).drop(columns=["_given", "_sur"])
    out.to_csv(os.path.join(OUT, "frame.csv"), index=False)
    print(f"  frame.csv: {len(out):,} rows, {out.matchId.nunique()} matches")


if __name__ == "__main__":
    main()
