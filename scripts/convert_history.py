"""Convert the pre-2007 AFLTables archive into game_level season files.

    python scripts/convert_history.py

Reads data_history/fitzroy_stats_1965_2006.csv.gz, keeps seasons 1990-2006 and
home-and-away rows, and writes one data_history/game_level_{season}.csv per
season in the schema predictions/game_level_*.csv already uses.

Output goes to data_history/, never to predictions/. AVAILABLE_SEASONS in
dashboard.py is built by scanning predictions/ for season_*.csv, and it drives
the season selector on every page rather than Stat Filter alone, so a
game_level file landing there would offer seasons the rest of the app cannot
answer for.

Read once, iterate seasons in memory. The gz peaks around 545 MB inside
read_csv, because a gzip stream has to be inflated and parsed in full before
usecols can discard anything, and that cost is paid per call. Seventeen
per-season reads would pay it seventeen times.

What the output does not carry, and why:

    Coaches_Votes        coaches_votes_all.csv starts in 2006
    Score_Involvements   needs Goal.Assists, which starts in 2003
    RatingPoints         data_wheelo starts in 2015

Those three are omitted rather than emitted empty. Exp_Votes is emitted and
left null on every row: the model does not cover this era, and a zero there
would read as a real projection of no votes rather than as absence of one.

Player_Name is display text and carries no '(Team)' suffix. Identity is the
fitzRoy ID column, which this output carries on every row under the same name
predictions/game_level_*.csv uses for it, ID. Any consumer that needs to tell
two people apart groups on ID and never on the name.

Several carried columns are themselves null before the season AFLTables began
recording them (Tackles 1987, Clearances 1998, Contested.Possessions 1999,
Goal.Assists 2003). They are still emitted, all-null seasons included, so every
file shares one schema. That matches predictions/, where RatingPoints is
present and entirely null across 2007-2014.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from club_aliases import canonical_club  # noqa: E402

SRC = "data_history/fitzroy_stats_1965_2006.csv.gz"
OUT_DIR = "data_history"

# Reference for the output schema. The 2007-2025 files carry an identical
# 108-column header in identical order, so any of them answers the question;
# the tuple exists so a missing file is not a failure.
SCHEMA_REFS = (
    "predictions/game_level_2015.csv",
    "predictions/game_level_2016.csv",
    "predictions/game_level_2007.csv",
)

SEASON_MIN, SEASON_MAX = 1990, 2006

FINALS_LABELS = {"QF", "EF", "SF", "PF", "GF"}

# Present in the reference schema but never in the archive. Named here so the
# omission is a decision on the page rather than an accident of a set
# intersection quietly coming up short.
OMITTED = ("Coaches_Votes", "Score_Involvements", "RatingPoints")

# Source columns the conversion needs that are not themselves output columns.
SOURCE_ONLY = ("Round", "Player", "Home.Away")

# Derived rather than carried: the archive holds scores and a home/away flag,
# so all four follow from arithmetic on columns it does have.
DERIVED = ("Margin", "Abs_Margin", "Is_Win", "Is_Loss")


def schema_columns():
    """The reference game_level header, in order."""
    for path in SCHEMA_REFS:
        if os.path.exists(path):
            return list(pd.read_csv(path, nrows=0).columns), path
    raise SystemExit(
        "no reference game_level file found; looked for "
        + ", ".join(SCHEMA_REFS)
    )


def report_shared_names(df):
    """Name the players whose name is carried by more than one fitzRoy ID.

    Reported, not repaired. Player_Name here is display text and ID is
    identity, so a shared name costs nothing as long as no consumer groups on
    the name. It is printed because the reverse mistake is easy to make and
    silent when it is made.
    """
    by_name = df.groupby("Player_Name")["ID"].nunique()
    return sorted(by_name[by_name > 1].index)


def convert():
    schema, ref = schema_columns()
    print(f"schema reference: {ref} ({len(schema)} columns)")

    src_cols = set(pd.read_csv(SRC, nrows=0).columns)
    carried = [c for c in schema if c in src_cols and c not in OMITTED]
    missing = [c for c in OMITTED if c in src_cols]
    if missing:
        raise SystemExit(f"expected {missing} to be absent from {SRC}")

    usecols = sorted(set(carried) | set(SOURCE_ONLY) | {"Season", "ID"})
    print(f"reading {SRC} with {len(usecols)} columns")
    df = pd.read_csv(SRC, usecols=usecols, low_memory=False)
    print(f"  {len(df):,} rows, seasons {int(df.Season.min())}-{int(df.Season.max())}")

    df = df[(df.Season >= SEASON_MIN) & (df.Season <= SEASON_MAX)].copy()
    rows_in = len(df)

    label = df["Round"].astype(str).str.strip().str.upper()
    is_final = label.isin(FINALS_LABELS)
    odd = df[~is_final & ~df["Round"].astype(str).str.strip().str.isdigit()]
    if len(odd):
        raise SystemExit(
            f"unrecognised round labels: {sorted(odd['Round'].astype(str).unique())}"
        )
    finals_excluded = int(is_final.sum())
    df = df[~is_final].copy()
    rows_out = len(df)
    print(f"{SEASON_MIN}-{SEASON_MAX}: rows_in={rows_in:,} "
          f"finals_excluded={finals_excluded:,} rows_out={rows_out:,} "
          f"check={rows_in - finals_excluded == rows_out}")

    df["Round_num"] = df["Round"].astype(int)

    # canonical_club is applied to Playing.for and never to the archive's own
    # Team column. The two disagree on 20,772 rows across the file and do not
    # agree on which of them holds the historical name, so only one can be
    # trusted: Playing.for is the club the row was recorded under. The result
    # is written to both output columns, which is the state load_all_historical
    # leaves 2007-2025 in.
    df["Playing.for"] = df["Playing.for"].map(canonical_club)
    df["Team"] = df["Playing.for"]

    # Bare name, no '(Team)' suffix. dashboard._disambiguate_players adds one
    # because the frames it assembles have no usable ID for every era; this
    # output carries ID on every row, so the suffix would add nothing and take
    # something away. Gary Ablett is the case that settles it: father and son
    # both finished at Geelong, so the suffix cannot separate them, and the son
    # is stored bare in predictions/, so suffixing here would split one person
    # across the era boundary while still merging him with his father inside
    # this half. Identity is ID.
    df["Player_Name"] = df["Player"]
    shared = report_shared_names(df)
    print(f"names carried by more than one ID: {len(shared)} "
          f"(display only, identity is ID)")
    if shared:
        print(f"  {', '.join(shared)}")

    own = df["Home.score"].where(df["Home.Away"] == "Home", df["Away.score"])
    opp = df["Away.score"].where(df["Home.Away"] == "Home", df["Home.score"])
    df["Margin"] = own - opp
    df["Abs_Margin"] = df["Margin"].abs()
    df["Is_Win"] = (df["Margin"] > 0).astype(int)
    df["Is_Loss"] = (df["Margin"] < 0).astype(int)

    # Null, not zero. Absence of a projection, not a projection of nothing.
    df["Exp_Votes"] = pd.NA

    out_cols = [c for c in schema
                if c in set(carried) | set(DERIVED) | {"Player_Name", "Round_num",
                                                       "Team", "Exp_Votes"}]
    print(f"output schema: {len(out_cols)} of {len(schema)} reference columns")
    print(f"  omitted, absent pre-2007: {', '.join(OMITTED)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for season, part in df.groupby("Season", sort=True):
        path = f"{OUT_DIR}/game_level_{int(season)}.csv"
        part[out_cols].to_csv(path, index=False)
        total += len(part)
        print(f"  wrote {path}  {len(part):,} rows")
    print(f"\ntotal written {total:,} (expected {rows_out:,}) "
          f"check={total == rows_out}")
    return df, out_cols


if __name__ == "__main__":
    convert()
