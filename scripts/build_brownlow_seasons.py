"""Build data_history/brownlow_seasons_1924_1983.csv

Run from the repository root, not from inside scripts/:
    python scripts/build_brownlow_seasons.py

Season-level Brownlow vote totals from AFLTables, covering the years that sit
BELOW the per-game floor in the rest of this repo.

Why this file exists
--------------------
Every per-game vote source here starts in 1984:
`data_history/fitzroy_stats_1965_2006.csv.gz` carries `Brownlow.Votes` as
all-null for 1965-1983 and fully populated from 1984, and AFLTables' own
detailed records are titled "Brownlow Records 1984-2025" with no earlier
equivalent. That is a boundary in the source, not a fetch-range choice: the
1965-1983 rows were pulled and came back with kicks and marks populated and
votes empty.

What this file can and cannot support
-------------------------------------
It carries SEASON TOTALS per player, never game attribution. It can extend a
career-total or season-leader claim back to 1924. It CANNOT extend any
opponent-scoped or fixture-scoped claim ("votes against Melbourne", "votes in
Carlton v Fremantle"), because a season total does not record which game a vote
came from. Those claims stay capped at 1984 permanently.

Recon-only. Nothing in the model pipeline reads this file.

Politeness
----------
One request per season, ~57 requests, 1.0s apart, single pass, no retry storm.
"""

import csv
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

from bs4 import BeautifulSoup

BASE = "https://afltables.com/afl/brownlow/brownlow{year}.html"
UA = "Mozilla/5.0 (compatible; brownlow_engine research; contact via repo)"
DELAY = 1.0

# Closed range. The upper bound is 1983 because 1984 onward is already held at
# game level and a season total would be a worse duplicate of it.
FIRST, LAST = 1924, 1983

# No Brownlow was awarded 1942-1945. These years have no page rather than an
# empty one, so they are skipped rather than fetched and tolerated.
WAR_YEARS = {1942, 1943, 1944, 1945}

OUT = os.path.join("data_history", "brownlow_seasons_1924_1983.csv")
HEADER = ["Season", "Player", "Surname", "First_name", "Teams", "Votes",
          "Games", "Votes_3", "Votes_2", "Votes_1", "Games_polled",
          "Vote_system"]

# The scoring system changed in 1931 and the column layout did not, which is the
# single most dangerous thing about this file.
#
# 1924-1930 awarded ONE vote to one player per match. AFLTables still writes
# that count into the column headed "3", so a row reading Votes=7, Votes_3=7 is
# seven single votes, NOT seven three-vote games. Measured across the era:
# Votes == Votes_3 on 387 of 390 rows, and no row carries a 2. The three
# exceptions (McCracken 1925, Corrigan 1925, Matthews 1928) each hold Votes=1
# with the vote written into the "1" column instead, which is a source
# inconsistency rather than a different system: all three still satisfy
# Games_polled == 1.
#
# From 1931 the 3-2-1 system applies and the weighted identity holds
# (Bunton 1931: 6*3 + 3*2 + 2*1 == 26).
#
# Vote_system is emitted per row so no downstream sum can silently add a
# 1924-1930 single vote to a post-1931 three-vote game.
SYSTEM_CHANGE = 1931

EXPECTED_COLS = ["Player", "Teams", "Votes", "Games", "3", "2", "1", "GP"]


def fetch(year):
    req = urllib.request.Request(BASE.format(year=year), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def cell_int(text):
    """AFLTables writes a zero count as an empty cell.

    Returned as None rather than 0 so a blank is distinguishable from a real
    zero downstream. 1946 has the whole 3/2/1 breakdown blank for every player
    while carrying a Votes total, so collapsing blank to 0 would silently
    invent a breakdown that the source does not have.
    """
    t = text.strip()
    if t == "":
        return None
    try:
        return int(t)
    except ValueError:
        return None


def parse(year, html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise ValueError(f"{year}: no table found")

    rows = tables[0].find_all("tr")
    head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    if head != EXPECTED_COLS:
        raise ValueError(f"{year}: unexpected header {head!r}, expected {EXPECTED_COLS!r}")

    out = []
    for tr in rows[1:]:
        c = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if len(c) != len(EXPECTED_COLS):
            raise ValueError(f"{year}: row has {len(c)} cells, expected {len(EXPECTED_COLS)}: {c!r}")

        name = c[0]
        # AFLTables writes "Surname, First name". Split on the first comma only:
        # a first-name field can itself contain a space, and a surname cannot
        # contain a comma.
        if "," in name:
            surname, first = [p.strip() for p in name.split(",", 1)]
        else:
            surname, first = name.strip(), ""

        out.append({
            "Season": year,
            "Player": f"{first} {surname}".strip(),
            "Surname": surname,
            "First_name": first,
            "Teams": c[1],
            "Votes": cell_int(c[2]),
            "Games": cell_int(c[3]),
            "Votes_3": cell_int(c[4]),
            "Votes_2": cell_int(c[5]),
            "Votes_1": cell_int(c[6]),
            "Games_polled": cell_int(c[7]),
            "Vote_system": "3-2-1" if year >= SYSTEM_CHANGE else "single",
        })
    return out


def audit(rows):
    """Per-season diagnostics, printed rather than enforced.

    Two identities are tested on every row that carries any part of a
    breakdown:

      weighted:  Votes == 3*Votes_3 + 2*Votes_2 + 1*Votes_1
      counted:   Games_polled == Votes_3 + Votes_2 + Votes_1

    Neither is enforced, because both fail for reasons that are properties of
    the source rather than parse errors:

    - weighted fails across 1924-1930 by construction, since a single vote is
      written into the "3" column. See SYSTEM_CHANGE above. The audit therefore
      tests weighted only from 1931 and prints "n/a (single)" before it.
    - counted cannot be tested at all in 1976 and 1977, where AFLTables leaves
      the GP column blank for every player while still publishing the 3/2/1
      split. That is reported as "n/a (no GP)" rather than counted as 0 correct,
      which is what an earlier version of this audit did.

    A row is "no brkdn" only when ALL THREE of Votes_3/Votes_2/Votes_1 are
    blank. Testing Votes_3 alone undercounts, because a player can have a blank
    3 and a populated 1.
    """
    by_season = {}
    for r in rows:
        by_season.setdefault(r["Season"], []).append(r)

    print("\n--- per-season audit ---")
    print(f"{'season':>6} {'rows':>5} {'no brkdn':>9} {'weighted':>14} {'counted':>14}")
    summary = Counter()
    for season in sorted(by_season):
        rs = by_season[season]
        blank = w_ok = w_bad = c_ok = c_bad = no_gp = 0
        for r in rs:
            trio = (r["Votes_3"], r["Votes_2"], r["Votes_1"])
            if all(v is None for v in trio):
                blank += 1
                continue
            t3, t2, t1 = (v or 0 for v in trio)
            if season >= SYSTEM_CHANGE:
                if r["Votes"] == 3 * t3 + 2 * t2 + t1:
                    w_ok += 1
                else:
                    w_bad += 1
            if r["Games_polled"] is None:
                no_gp += 1
            elif r["Games_polled"] == t3 + t2 + t1:
                c_ok += 1
            else:
                c_bad += 1

        w = f"{w_ok}/{w_ok + w_bad}" if (w_ok + w_bad) else "n/a (single)"
        c = f"{c_ok}/{c_ok + c_bad}" if (c_ok + c_bad) else ("n/a (no GP)" if no_gp else "n/a")
        print(f"{season:>6} {len(rs):>5} {blank:>9} {w:>14} {c:>14}")

        summary["rows"] += len(rs)
        summary["blank"] += blank
        summary["w_ok"] += w_ok
        summary["w_bad"] += w_bad
        summary["c_ok"] += c_ok
        summary["c_bad"] += c_bad
        summary["no_gp"] += no_gp
    return summary


def main():
    if not os.path.isdir("data_history"):
        sys.exit("run from the repository root: data_history/ not found here")

    years = [y for y in range(FIRST, LAST + 1) if y not in WAR_YEARS]
    print(f"fetching {len(years)} seasons, {FIRST}-{LAST}, skipping {sorted(WAR_YEARS)}")

    rows, failed = [], []
    for i, y in enumerate(years):
        try:
            got = parse(y, fetch(y))
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
            print(f"  {y}: FAILED {e}")
            failed.append(y)
        else:
            rows.extend(got)
            print(f"  {y}: {len(got)} players")
        if i < len(years) - 1:
            time.sleep(DELAY)

    if failed:
        # A partial file is worse than none: a missing season reads downstream as
        # a season in which nobody polled.
        sys.exit(f"\n{len(failed)} season(s) failed: {failed}. Nothing written.")

    summary = audit(rows)

    print("\n--- pre-write checks ---")
    print(f"rows: {len(rows)}  cols: {len(HEADER)}")
    print(f"seasons: {len(set(r['Season'] for r in rows))} "
          f"({min(r['Season'] for r in rows)}-{max(r['Season'] for r in rows)})")
    print(f"rows with no 3/2/1 breakdown: {summary['blank']} of {summary['rows']}")
    print(f"weighted identity (1931+): {summary['w_ok']} hold, {summary['w_bad']} fail")
    print(f"counted identity:  {summary['c_ok']} hold, {summary['c_bad']} fail, "
          f"{summary['no_gp']} untestable (GP blank)")
    single = sum(1 for r in rows if r["Vote_system"] == "single")
    print(f"rows in the pre-1931 single-vote era: {single} "
          f"(Votes_3 there counts single votes, not three-vote games)")
    missing_votes = sum(1 for r in rows if r["Votes"] is None)
    print(f"rows with no Votes value: {missing_votes}")
    nonascii = [r["Player"] for r in rows if any(ord(ch) > 127 for ch in r["Player"])]
    print(f"rows containing non-ASCII names: {len(nonascii)}"
          + (f" {sorted(set(nonascii))}" if nonascii else ""))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in HEADER})

    print(f"\nwrote {OUT}")
    print("DONE")


if __name__ == "__main__":
    main()
