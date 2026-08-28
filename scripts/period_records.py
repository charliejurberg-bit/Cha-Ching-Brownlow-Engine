"""Youngest-player ladders over the per-quarter data in data_chains/period_stats.csv

Run from the repository root, not from inside scripts/:
    python scripts/period_records.py                        # 18+ disposals at half time
    python scripts/period_records.py --through 1 --min 12    # first quarter
    python scripts/period_records.py --through all --min 32  # full match
    python scripts/period_records.py --min 18 --clubs "Collingwood,Western Bulldogs"

Reads what scripts/fetch_match_chains.py writes, folds the quarters up to a
chosen point, attaches each player's exact age on the day, and ranks by age.
The question it exists to answer is "who is the youngest to have N disposals by
the end of quarter Q", which no other data in this repository can express.

Ages are exact to the day, and come from AFLTables
--------------------------------------------------
AFLTables stores age as years plus days measured on the match date, and fitzRoy
carries it as a decimal: `Age = years + days / 365.25`. So `floor(Age)` is the
years and `round(frac(Age) * 365.25)` is the days, exactly, with no leap-year
reconstruction needed. Verified against the DOB column where both exist.

2026 is not in fitzroy_stats_all.csv yet, so its ages are computed from the DOB
column of data_2026/afltables_2026.csv instead. A finals debutant who never
played a home-and-away game has no DOB there and drops out with a warning
rather than being silently aged wrong.

Rows with `Age <= 0` are dropped. That is AFLTables' missing-DOB sentinel, not
a real age, and three 2021-22 finals rows carry it.

Reading this against the full-match archive
-------------------------------------------
This file only reaches back to 2021, because that is where the AFL's chains
feed starts (see fetch_match_chains.py). A record found here is therefore
"youngest since 2021", never "youngest ever", and the script prints that window
under every ladder so the caveat travels with the numbers. To bound how much
the missing years could matter, note that a player cannot have N disposals by
half time without having N for the full match, so the candidate set for any
pre-2021 challenger is exactly the players younger than the leader with N+ for
the whole game, and THAT is checkable back to 1965 in fitzroy_stats_all.csv
plus data_history/fitzroy_stats_1965_2006.csv.gz.

Recon only. Nothing in the model pipeline reads this.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from club_aliases import canonical_club          # noqa: E402
from features import normalise_name, resolve_feed_names  # noqa: E402

PERIOD_CSV = os.path.join(REPO, "data_chains", "period_stats.csv")
FITZROY = os.path.join(REPO, "fitzroy_stats_all.csv")
CURRENT = os.path.join(REPO, "data_2026", "afltables_2026.csv")

FINALS_LABELS = ["EF", "QF", "SF", "PF", "GF"]
DAYS = 365.25

# The AFL feed's spelling to AFLTables', for names that resolve_feed_names
# cannot bridge. Kept HERE rather than in features.FIRST_NAME_ALIASES on
# purpose: that map is documented as first-name spelling variants only, is tuned
# against the 2026 model feeds, and is imported by the training pipeline.
# "Junior" for "Willie" is a different name, not a variant, and does not belong
# in a constant the model depends on.
FEED_NAME_FIXES = {"Junior Rioli": "Willie Rioli"}


def _age_parts(age):
    yrs = np.floor(age).astype(int)
    days = ((age - yrs) * DAYS).round().astype(int)
    return yrs, days


def _load_periods(through):
    if not os.path.exists(PERIOD_CSV):
        raise SystemExit(
            f"{PERIOD_CSV} not found. Build it first:\n"
            f"    python scripts/fetch_match_chains.py")
    df = pd.read_csv(PERIOD_CSV)
    if through is not None:
        df = df[df["Period"] <= through]
        if df.empty:
            raise SystemExit(f"No rows at or before period {through}.")
    keys = ["Season", "MatchId", "RoundName", "utc", "Home", "Away", "Player", "Team"]
    out = (df.groupby(keys, as_index=False)[["Kicks", "Handballs", "Disposals"]].sum())
    out["Date"] = pd.to_datetime(out["utc"]).dt.tz_convert("Australia/Melbourne").dt.date.astype(str)
    return out


def _attach_ages(df):
    """Exact age per row. Historical seasons from AFLTables, 2026 from DOB."""
    hist = df[df.Season <= 2025].copy()
    curr = df[df.Season >= 2026].copy()
    parts = []

    if len(hist):
        fz = pd.read_csv(FITZROY, low_memory=False)
        fz["R"] = fz["Round"].astype(str)
        fz = fz[fz["R"].isin(FINALS_LABELS) & (fz["Season"] >= hist.Season.min())].copy()
        fz["Date"] = fz["Date"].astype(str)
        hist["Player"] = hist["Player"].replace(FEED_NAME_FIXES)
        hist, _ = resolve_feed_names(
            hist, fz, "Player", "Team", "Date",
            target_name_col="Player", target_team_col="Playing.for",
            target_round_col="Date", label="chains")
        hist = hist.merge(fz[["Season", "Player", "Date", "Age", "R"]],
                          on=["Season", "Player", "Date"], how="left")
        parts.append(hist)

    if len(curr):
        cur = pd.read_csv(CURRENT, low_memory=False).dropna(subset=["DOB"])
        cur["_n"] = cur["Player"].map(normalise_name)
        dob = cur.drop_duplicates("_n").set_index("_n")["DOB"]
        curr["DOB"] = curr["Player"].map(normalise_name).map(dob)
        missing = curr.loc[curr.DOB.isna(), "Player"].unique()
        if len(missing):
            print(f"  no DOB for {len(missing)} player(s), dropped: {', '.join(sorted(missing))}")
        curr["Age"] = (pd.to_datetime(curr["Date"])
                       - pd.to_datetime(curr["DOB"], format="%d-%b-%Y")).dt.days / DAYS
        curr["R"] = ""
        parts.append(curr)

    out = pd.concat(parts, ignore_index=True)
    dropped = int(((out.Age.isna()) | (out.Age <= 0)).sum())
    if dropped:
        print(f"  dropped {dropped} row(s) with a missing or zero age")
    out = out[out.Age.notna() & (out.Age > 0)].copy()

    yrs, days = _age_parts(out["Age"])
    out["AgeStr"] = yrs.astype(str) + "y " + days.astype(str) + "d"
    out["AgeDays"] = (out["Age"] * DAYS).round().astype(int)

    out["Team"] = out["Team"].map(canonical_club)
    home = out["Home"].map(_afl_to_afltables).map(canonical_club)
    away = out["Away"].map(_afl_to_afltables).map(canonical_club)
    out["Opp"] = np.where(out["Team"] == home, away, home)
    return out


# The fixture feed spells clubs its own way ("Geelong Cats", "GWS GIANTS"); the
# player rows already carry the AFLTables spelling via fetch_match_chains.CD_TEAM.
_AFL_SPELLING = {
    "Adelaide Crows": "Adelaide", "Geelong Cats": "Geelong",
    "Gold Coast SUNS": "Gold Coast", "GWS GIANTS": "Greater Western Sydney",
    "Sydney Swans": "Sydney", "West Coast Eagles": "West Coast",
}


def _afl_to_afltables(name):
    return _AFL_SPELLING.get(name, name)


def _label(through):
    if through is None:
        return "full match"
    return {1: "quarter time", 2: "half time", 3: "three-quarter time"}.get(
        through, f"end of quarter {through}")


def report(through, minimum, stat, clubs, top):
    df = _attach_ages(_load_periods(through))
    window = f"{df.Season.min()}-{df.Season.max()}"
    what = _label(through)

    if clubs:
        wanted = {canonical_club(c.strip()) for c in clubs.split(",")}
        df = df[df["Team"].isin(wanted)]
        scope = " / ".join(sorted(wanted))
    else:
        scope = "all teams"

    q = df[df[stat] >= minimum].sort_values(["AgeDays", stat])
    print(f"\n  YOUNGEST WITH {minimum}+ {stat.upper()} AT {what.upper()} IN A FINAL")
    print(f"  {scope}, {window} only ({df.MatchId.nunique()} finals in the file)")
    print(f"  {len(q)} qualifying performance(s)\n")
    if q.empty:
        print("    none")
    for i, (_, r) in enumerate(q.head(top).iterrows(), 1):
        print(f"  {i:2d}. {r.AgeStr:9s} {r.Player:22s} {r.Team:22s} "
              f"{r[stat]:3.0f}  {r.RoundName:32s} {r.Season}  v {r.Opp}")
    if len(q) > top:
        print(f"      ... {len(q) - top} more, raise --top to see them")

    print(f"\n  Window note: the AFL chains feed starts in 2021, so this is "
          f"'youngest since {df.Season.min()}', not 'youngest ever'. A pre-2021 "
          f"challenger must also have had {minimum}+ for the FULL match, which is "
          f"checkable back to 1965 in fitzroy_stats_all.csv.")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--through", default="2",
                    help="last quarter to include: 1, 2, 3, 4 or 'all' (default: 2, half time)")
    ap.add_argument("--min", type=int, default=18, dest="minimum",
                    help="minimum count to qualify (default: 18)")
    ap.add_argument("--stat", default="Disposals", choices=["Disposals", "Kicks", "Handballs"],
                    help="which count to rank on (default: Disposals)")
    ap.add_argument("--clubs", default=None,
                    help='comma-separated club filter, e.g. "Collingwood,Western Bulldogs"')
    ap.add_argument("--top", type=int, default=25, help="rows to print (default: 25)")
    args = ap.parse_args(argv)

    through = None if str(args.through).lower() in {"all", "0", "4"} else int(args.through)
    return report(through, args.minimum, args.stat, args.clubs, args.top)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
