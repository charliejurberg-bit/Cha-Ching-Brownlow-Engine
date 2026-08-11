"""Regression runner for update_wheelo_2026.py round derivation.

Usage:
    python tests/run_wheelo_round_tests.py

Covers the two failures that let 2026 round 23 sit incomplete for a week
without a word in the console:

  1. The round was stamped from the loop counter that built the URL, so the
     stored label asserted what the page should have held rather than reading
     what it did hold. attach_rounds now reads Wheelo's own MatchId, and a
     payload whose round cannot be read is skipped rather than guessed at.

  2. The freshness guard was round-level, so a round first fetched mid-play
     was frozen at whatever games existed at that moment.
     rounds_needing_fetch now tests per game.

No Selenium and no network: attach_rounds and rounds_needing_fetch are pure
functions over DataFrames, which is why fetch_round hands the payload back
rather than labelling it in place.
"""

import os
import sys
import traceback

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from update_wheelo_2026 import (          # noqa: E402
    attach_rounds,
    rounds_needing_fetch,
    STATUS_OK,
    STATUS_EMPTY,
    STATUS_NO_ROUND,
)

FAILURES = []


def check(name, got, want):
    if got == want:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}\n          got:  {got!r}\n          want: {want!r}")
        FAILURES.append(name)


def payload(match_ids, players=None):
    """Minimal stand-in for a Wheelo match-stats download."""
    players = players or [f"P{i}" for i in range(len(match_ids))]
    return pd.DataFrame({"MatchId": match_ids, "Player": players, "Disposals": 20})


# ── attach_rounds: the round comes from the payload ──────────────────────────
print("\nattach_rounds")

status, df, _ = attach_rounds(payload([20262201, 20262202]), requested_wheelo_round=22)
check("well-formed MatchId is accepted", status, STATUS_OK)
check("Wheelo round 22 maps to AFLTables round 23",
      sorted(df["Round"].unique()), [23])

status, df, _ = attach_rounds(payload([20260001, 20260005]), requested_wheelo_round=0)
check("Opening Round (Wheelo 0) maps to AFLTables round 1",
      sorted(df["Round"].unique()), [1])

# A float-typed column (any NaN in the download forces this) still parses.
status, df, _ = attach_rounds(payload([20262201.0, 20262202.0]), 22)
check("float-rendered MatchId still parses", status, STATUS_OK)

# ── The required case: a non-numeric round label ─────────────────────────────
# Previously impossible to detect, because no label was ever read. Now these
# must be refused outright rather than silently stamped with the counter.
print("\nnon-numeric round labels are refused, not guessed")

for label in ["Final Round", "R23 - Finals Eve", "Rd 23", "", "nan", "GF"]:
    status, df, detail = attach_rounds(payload([label, label]), requested_wheelo_round=22)
    check(f"{label!r} yields STATUS_NO_ROUND", status, STATUS_NO_ROUND)
    check(f"{label!r} writes no rows", df, None)

status, df, _ = attach_rounds(
    pd.DataFrame({"Player": ["A"], "Disposals": [20]}), requested_wheelo_round=22)
check("payload with no MatchId column at all", status, STATUS_NO_ROUND)

status, df, _ = attach_rounds(payload([20252201]), requested_wheelo_round=22)
check("MatchId from the wrong season is refused", status, STATUS_NO_ROUND)

status, df, _ = attach_rounds(payload([]), requested_wheelo_round=22)
check("empty payload reports EMPTY, not NO_ROUND", status, STATUS_EMPTY)

# Partly readable: keep what parses, drop what does not, say so.
status, df, detail = attach_rounds(payload([20262201, "Final Round"]), 22)
check("mixed payload keeps the readable rows", status, STATUS_OK)
check("mixed payload keeps exactly one row", len(df), 1)
check("mixed payload reports the drop", "dropped" in detail, True)

# The payload outranks the request. Overriding it with the number we asked for
# is precisely the inferred-counter bug being replaced.
status, df, detail = attach_rounds(payload([20261501]), requested_wheelo_round=22)
check("payload round wins over requested round",
      sorted(df["Round"].unique()), [16])
check("disagreement is reported", "payload wins" in detail, True)

# ── rounds_needing_fetch: completeness is per game ───────────────────────────
print("\nrounds_needing_fetch")

LAST_ROUND = 23
FULL_FIXTURES = {r: 9 for r in range(1, LAST_ROUND + 1)}


def season_frame(drop_ids=(), last_round=LAST_ROUND):
    """A complete season of stored Wheelo rows, minus the given MatchIds."""
    rows = []
    for aflt_round in range(1, last_round + 1):
        for game in range(1, 10):
            match_id = int(f"2026{aflt_round - 1:02d}{game:02d}")
            if match_id in drop_ids:
                continue
            rows.append({"MatchId": match_id,
                         "Player": f"P{match_id}",
                         "Round": aflt_round})
    return pd.DataFrame(rows)


complete = season_frame()
todo = rounds_needing_fetch(complete, expected=FULL_FIXTURES)
check("a complete season is left alone", todo, [])
check("no probe past the last real round",
      [r for r, _ in todo if r >= LAST_ROUND], [])

# The live 2026 case: round 23 stored with 8 of its 9 games, missing the game
# at index 6 (St Kilda v Carlton). Under the old round-level guard this was
# frozen forever; it must now come back as work to do.
short_r23 = season_frame(drop_ids=(20262206,))
todo = rounds_needing_fetch(short_r23, expected=FULL_FIXTURES)
check("a round short of the fixture list is refetched",
      [r for r, _ in todo], [22])
check("the reason names the shortfall", "8 of 9" in todo[0][1], True)

# Same gap, no fixture list to compare against: the index hole must still show.
todo = rounds_needing_fetch(short_r23, expected={})
check("index hole caught without a fixture list",
      [r for r, _ in todo], [22])
check("the reason names the hole", "hole" in todo[0][1], True)

# A trailing game missing leaves no index hole, so only the fixture list can
# catch it. This is why AFLTables is consulted rather than trusting the shape.
short_tail = season_frame(drop_ids=(20262209,))
todo = rounds_needing_fetch(short_tail, expected=FULL_FIXTURES)
check("a missing LAST game is caught via the fixture list",
      [r for r, _ in todo], [22])

todo = rounds_needing_fetch(short_tail, expected={})
check("newest round is rechecked when completeness is unknowable",
      [r for r, _ in todo], [22])

absent_r22 = season_frame(drop_ids=tuple(int(f"202621{g:02d}") for g in range(1, 10)))
todo = rounds_needing_fetch(absent_r22, expected=FULL_FIXTURES)
check("an absent round is fetched", [r for r, _ in todo], [21])
check("the reason says absent", "absent" in todo[0][1], True)

print()
if FAILURES:
    print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("All checks passed.")
sys.exit(0)
