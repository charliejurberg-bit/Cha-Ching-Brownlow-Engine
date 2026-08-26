"""Rebuild coaches_votes_all.csv with the recovered pre-2006 seasons.

    python scripts/rebuild_coaches_all.py

Prepends data_history/coaches_votes_2003_2005.csv to the existing archive. The
existing rows are NOT reprocessed: they are carried across untouched and the
script refuses to write unless it can prove that, because coaches_votes_all.csv
is the input to every historical vote claim in the repo and a silent reshuffle
of it would be invisible until something downstream disagreed.

WHY THE ARCHIVE WAS SHORT
The AFLCA award began in 2003 but fetch_extended_data.R hardcodes
`for (yr in 2006:2014)`, so the award's first seasons were never fetched. Every
"all time" coaches-vote claim was really "2006 onward" and understated anyone
active before then. Four of the top sixteen career vote-getters were.

2003 IS STILL MISSING, AND IS NOT RECOVERABLE HERE
fitzRoy returns 2004 and 2005 cleanly. 2003 fails: an "invalid 'type'
(character) of argument" error on the batch path and a hard segfault when
fetched alone, on fitzRoy 1.7.0. The archive therefore runs 2004-2025 and an
"all time" claim should be stated as 2004 onward, not 2003. Anyone whose career
began in or before 2003 is still short by that one season.

The 2004 and 2005 data validates: all 352 games sum to exactly 30, which is
five-four-three-two-one from each of two coaches, and the season leaders are
era-correct (Tredrea and Judd in 2004, Hall and Cousins in 2005).

This script does not touch data_2026/coaches_votes_2026.csv, which holds the
hand-transcribed rounds 24 and 25 and must never be regenerated.
"""

import os
import sys

import pandas as pd

ALL = "coaches_votes_all.csv"
EARLY = "data_history/coaches_votes_2003_2005.csv"
KEY = ["Season", "Round", "Home.Team", "Away.Team", "Player.Name", "Coaches.Votes"]


def main():
    for p in (ALL, EARLY):
        if not os.path.exists(p):
            print(f"FAIL  {p} not found. Run from the repository root.")
            return 1

    old = pd.read_csv(ALL, low_memory=False)
    early = pd.read_csv(EARLY)

    if list(old.columns) != list(early.columns):
        print(f"FAIL  column mismatch.\n  {ALL}: {list(old.columns)}\n"
              f"  {EARLY}: {list(early.columns)}")
        return 1

    overlap = sorted(set(early.Season) & set(old.Season))
    if overlap:
        print(f"FAIL  {EARLY} carries season(s) {overlap} that {ALL} already has. "
              f"Prepending would double-count them.")
        return 1

    out = pd.concat([early, old], ignore_index=True)

    # The existing archive must come through byte-for-byte. Compared on values
    # with the index reset, so a shift of even one row is caught.
    carried = out[out.Season >= old.Season.min()].reset_index(drop=True)
    if not carried.equals(old.reset_index(drop=True)):
        print("FAIL  the existing rows changed during the concat. Nothing written.")
        return 1
    if len(out) != len(old) + len(early):
        print(f"FAIL  row count {len(out)} != {len(old)} + {len(early)}.")
        return 1

    games = out.groupby(["Season", "Round", "Home.Team", "Away.Team"])["Coaches.Votes"].sum()
    off = games[games != 30]
    out.to_csv(ALL, index=False)
    print(f"OK  {ALL}: {len(old):,} -> {len(out):,} rows")
    print(f"    seasons {int(out.Season.min())}-{int(out.Season.max())} "
          f"({out.Season.nunique()} seasons, added {sorted(early.Season.unique())})")
    print(f"    {len(old):,} existing rows verified unchanged")
    print(f"    {len(games):,} games, {int((games == 30).sum()):,} sum to 30, "
          f"{len(off)} do not"
          + (f" (all in {sorted(off.reset_index().Season.unique())}, pre-existing)"
             if len(off) else ""))
    print("\n    NOTE 2003 is still absent; fitzRoy cannot supply it. State any "
          "all-time claim as 2004 onward.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
