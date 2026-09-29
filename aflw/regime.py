"""Did umpires seeing stats change how they vote, and should AFLW 2026 inherit it?

    python aflw/regime.py

From 2026 AFL and AFLW umpires both vote with the official match stats in front
of them (afl.com.au/aflw/news/1625586: "AFLW umpires have access to player
statistics for the first time when voting this year", the same 16-category
change as the Brownlow). The men's count has happened and the AFLW count has
not, so the men's 2026 is the only evidence of what the change does.

Method. One Plackett-Luce vote model (evaluate.py's) is fitted PER SEASON on
features both competitions record the same way: within-match z-scores of the
stats below, plus result. Per-season fits give every weight a year-to-year
spread under the old rules, so the men's 2026 shift can be read in units of
that spread: a weight that moves 3 spreads is the rule change; one that moves
0.5 is an ordinary year. Only the weights that genuinely moved are carried to
AFLW, in data_aflw/regime_2026.json, as an additive layer on top of whatever
the AFLW model scores.

The same per-season fit on AFLW shows whether AFLW's own weights sit near the
men's (so a men's shift is plausibly transferable) and how much they wander
anyway (so a transferred shift is not mistaken for signal it cannot beat).
"""

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate as ev  # noqa: E402

REPO = os.path.dirname(ev.OUT)
# men's AFLTables name -> AFLW frame name
COMMON = {"Disposals": "disposals", "Contested.Possessions": "contestedPossessions",
          "Clearances": "clearances.totalClearances", "Goals": "goals", "Tackles": "tackles",
          "Marks": "marks", "Inside.50s": "inside50s", "Hit.Outs": "hitouts",
          "Marks.Inside.50": "marksInside50", "Goal.Assists": "goalAssists"}
FEATS = [v + "_cz" for v in COMMON.values()] + ["win"]
OLD = range(2021, 2026)


def zs(d):
    g = d.groupby("matchId")
    for c in COMMON.values():
        d[c + "_cz"] = ((d[c] - g[c].transform("mean")) / g[c].transform("std").replace(0, np.nan)).fillna(0)
    return d


def mens():
    cache = os.path.join(ev.OUT, "_mens_common.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    cols = ["Season", "Round", "Home.team", "Away.team", "Playing.for", "ID", "Home.score", "Away.score",
            "Brownlow.Votes", *COMMON]
    hist = pd.read_csv(os.path.join(REPO, "fitzroy_stats_all.csv"), usecols=cols, low_memory=False)
    cur = pd.read_csv(os.path.join(REPO, "data_2026", "afltables_2026.csv"), usecols=cols, low_memory=False)
    v = pd.read_csv(os.path.join(REPO, "data_2026", "brownlow_votes_2026.csv"))
    cur = cur.drop(columns="Brownlow.Votes").merge(
        v[["Round_num", "ID", "Brownlow.Votes"]].rename(columns={"Round_num": "Round"}).assign(
            Round=lambda d: d.Round.astype(str)), how="left",
        left_on=[cur.Round.astype(str), "ID"], right_on=["Round", "ID"], suffixes=("", "_v"))
    m = pd.concat([hist[hist.Season >= 2015], cur], ignore_index=True)
    m["Round"] = pd.to_numeric(m.Round, errors="coerce")
    m = m.dropna(subset=["Round"])
    m["matchId"] = m.Season.astype(str) + "_" + m.Round.astype(int).astype(str) + "_" + m["Home.team"] + "_" + m["Away.team"]
    m = m.rename(columns=COMMON)
    home = m["Playing.for"] == m["Home.team"]
    m["win"] = np.sign(np.where(home, m["Home.score"] - m["Away.score"], m["Away.score"] - m["Home.score"]))
    m["votes"] = m["Brownlow.Votes"].fillna(0)
    m = m.drop_duplicates(["matchId", "ID"])
    m = m[m.groupby("matchId").votes.transform("sum") == 6]
    m["season"] = m.Season.astype(int).astype(str)
    m = zs(m)
    m.to_pickle(cache)
    return m


def per_season(d):
    out = {}
    for s, g in d.groupby("season"):
        th = ev.fit_pl(g.reset_index(drop=True), FEATS)
        out[s] = th[:len(FEATS)]
    return pd.DataFrame(out, index=FEATS).T


def main():
    m = mens()
    print(f"men: {m.matchId.nunique():,} matches, {m.season.nunique()} seasons "
          f"(2026: {m[m.season == '2026'].matchId.nunique()})")
    bm = per_season(m)
    old = bm.loc[[str(s) for s in OLD]]
    mu, sd = old.mean(), old.std()
    hist_sd = bm.loc[[s for s in bm.index if s != "2026"]].std()
    shift = bm.loc["2026"] - mu
    z = shift / hist_sd
    print("\nMEN, per-season weights (within-match z features):")
    print(bm.round(2).to_string())
    print("\n2026 shift against 2021-25, in units of the 2015-25 year-to-year spread:")
    print(pd.DataFrame({"2021-25": mu, "2026": bm.loc["2026"], "shift": shift, "spreads": z}).round(2).to_string())

    f = pd.read_csv(os.path.join(ev.OUT, "frame.csv"), low_memory=False)
    f = zs(f[f.label_kind == "match"].copy())
    bw = per_season(f)
    print("\nAFLW, per-season weights on the same features:")
    print(bw.round(2).to_string())
    print("\nAFLW mean vs men's 2021-25 mean:")
    print(pd.DataFrame({"AFLW": bw.mean(), "AFLW spread": bw.std(), "men 21-25": mu}).round(2).to_string())

    # Carry only the weights whose men's 2026 move beats two ordinary years.
    keep = z.abs() >= 2
    delta = shift.where(keep, 0.0)
    out = {"features": FEATS, "common": COMMON, "delta": delta.round(4).to_dict(),
           "shift_all": shift.round(4).to_dict(), "spreads": z.round(2).to_dict(),
           "rule": "delta = men's 2026 weight minus its 2021-25 mean, kept only where |shift| >= 2 "
                   "year-to-year spreads (2015-25); add lambda * delta . x_cz to the AFLW score"}
    with open(os.path.join(ev.OUT, "regime_2026.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nkept {int(keep.sum())} of {len(FEATS)} shifts -> data_aflw/regime_2026.json:",
          {k: round(v, 2) for k, v in delta.items() if v})


if __name__ == "__main__":
    main()
