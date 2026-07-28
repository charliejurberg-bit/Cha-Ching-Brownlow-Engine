"""
streaks.py

Consecutive-games polling streaks, printed to the terminal.

Offline and standalone. Nothing imports this, the dashboard never reaches it,
it makes no network calls, loads no model and writes no files. It reads two
CSVs out of predictions/ and prints.

DEFINITIONS
  Projected poll   Exp_Votes rank 1, 2 or 3 inside the game.
  Actual poll      Brownlow.Votes greater than zero.
  Streak           Consecutive GAMES PLAYED, in round order. A missed game does
                   not break a streak, it is simply not part of the sequence.
                   Every length printed below counts games and never rounds, so
                   a player out injured for a month resumes the same streak on
                   return.

WHY 2026 IS PROJECTED AND 2025 IS ACTUAL
game_level_2026.csv has a Brownlow.Votes column but every value is zero: the
count has not happened. game_level_2025.csv carries the real votes, 1,242 of
them across 207 home and away games. So 2026 can only be measured on what the
model projects and 2025 is measured on what actually polled. Report 2 prints
the two next to each other because that comparison is the point, but they are
different quantities from different seasons and are never added or combined.

GAME KEY
2026 has a Game_ID column. 2025 does not, so a game there is Round_num plus
Home.team plus Away.team, the same key accuracy_report.py uses. Both files were
checked and already exclude finals: 2025 holds exactly the 207 home and away
games, 2026 holds 171 games through Round_num 21. Round_num is coerced to
numeric and non-numeric rounds are dropped regardless, so a finals row
appearing in a later regeneration cannot silently enter a streak.

DUPLICATE PLAYER-GAMES
game_level_2025.csv contains 39 duplicated player-games, all in Round_num 24,
left by the Wheelo round collision that accuracy_report.py documents. They are
not identical rows, they differ across every Wheelo column, so a plain
drop_duplicates() does not remove them. Left in they inflate the season to
9,561 rows and 1,247 votes and give one game 66 player rows. Deduping on
Round_num plus Player_Name plus Playing.for restores 9,522 rows, 1,242 votes,
and 46 rows in each of the 207 games with every game summing to 6. This matters
more here than in a season total: a duplicated player-game counts as a second
game played and overstates a streak by one.

PLAYER IDENTITY
Report 2 joins 2025 to 2026 on Player_Name, not ID. Both files carry ID, but it
is null for 62 rows in 2026 and 4 in 2025, and across these two seasons the
mapping is clean both ways: no name resolves to more than one ID and no ID to
more than one name. Name and ID give the same 544 player overlap, so name is
used because it also covers the null-ID rows. If a future season brings two
players sharing a name, this join needs ID with a name fallback.

Run:
    python streaks.py
    python streaks.py --top-active 25 --top-ever 20
"""

import argparse
import os
import sys

import pandas as pd

PRED_DIR = "predictions"
CUR_SEASON = 2026
PREV_SEASON = 2025

# Identity of a player-game, and the fallback game key for the season with no
# Game_ID column. Both match accuracy_report.py.
DEDUPE_KEY = ["Round_num", "Player_Name", "Playing.for"]
GAME_KEY = ["Round_num", "Home.team", "Away.team"]

USECOLS = ["Season", "Round_num", "Home.team", "Away.team",
           "Player_Name", "Playing.for", "Exp_Votes", "Brownlow.Votes"]

POLL_RANK = 3               # Exp_Votes rank 1, 2 or 3 inside the game
DEFAULT_TOP_ACTIVE = 15
DEFAULT_TOP_EVER = 10

# First season with an AFL Opening Round. Kept in step with draft_posts.py:47.
_OPENING_ROUND_FROM = 2024

_NA = "n/a"


def _display_round(round_num, season):
    """AFLTables Round_num to the AFL round number shown to readers.

    Copied from draft_posts.py:64, which copied it from dashboard.py:409, and
    not imported: importing draft_posts is harmless but importing dashboard
    executes a Streamlit page, and keeping both copies of this in step is
    easier than remembering which module is safe to import.

    Season-aware, so it must not be flattened to a bare `rn - 1`.
    """
    try:
        rn = int(round_num)
        sn = int(season)
    except (TypeError, ValueError):
        return round_num
    return rn - 1 if sn >= _OPENING_ROUND_FROM else rn


def _banner(title):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


def _load(season):
    """Read one game_level file, drop finals rows, dedupe player-games.

    Prints what it dropped rather than dropping quietly, because the 2025
    duplicate count is the number most likely to change under the reader's feet
    if predictions are ever regenerated.
    """
    path = os.path.join(PRED_DIR, f"game_level_{season}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"ABORT: {path} not found. Run predict_2026.py first.")

    df = pd.read_csv(path, usecols=USECOLS, low_memory=False)
    n_in = len(df)

    df["Round_num"] = pd.to_numeric(df["Round_num"], errors="coerce")
    df = df.dropna(subset=["Round_num"])
    n_ha = len(df)

    df = df.drop_duplicates(subset=DEDUPE_KEY, keep="first")
    n_kept = len(df)

    df["Round_num"] = df["Round_num"].astype(int)
    games = df.groupby(GAME_KEY).ngroups
    print(f"  {path}")
    print(f"    {n_in:>6,} rows in | {n_in - n_ha:>3,} non-numeric round dropped "
          f"| {n_ha - n_kept:>3,} duplicate player-games dropped "
          f"| {n_kept:>6,} kept across {games} games")
    return df


def flag_projected_poll(df):
    """True where Exp_Votes ranks 1, 2 or 3 inside the game.

    method='min' so a tie for third flags both players, matching how a reader
    would describe a two-way tie. A game can therefore contribute more than
    three projected pollers, which is the intended behaviour and not a bug.
    """
    rank = df.groupby(GAME_KEY)["Exp_Votes"].rank(ascending=False, method="min")
    return rank <= POLL_RANK


def streaks(df, flag_col):
    """One row per player: games played, trailing streak, longest streak.

    `trailing` is the run still alive at the player's most recent game, which
    is zero if that game did not poll. `longest` is the best run anywhere in
    the season.

    Equal-length runs resolve to the most recent one (`>=`, not `>`). That
    keeps `longest` consistent with `active`: a still-running streak that only
    matches an earlier one is the run reported, so the active flag never points
    at a run that ended.
    """
    rows = []
    for name, g in df.groupby("Player_Name", sort=False):
        g = g.sort_values("Round_num")
        flags = g[flag_col].tolist()
        rounds = g["Round_num"].tolist()

        trailing = 0
        for polled in reversed(flags):
            if not polled:
                break
            trailing += 1
        trailing_start = rounds[len(flags) - trailing] if trailing else None

        longest = run = 0
        longest_start = run_start = None
        for rnd, polled in zip(rounds, flags):
            if not polled:
                run = 0
                continue
            run += 1
            if run == 1:
                run_start = rnd
            if run >= longest:
                longest, longest_start = run, run_start

        rows.append({
            "Player_Name": name,
            "Team": g["Playing.for"].iloc[-1],
            "Season": int(g["Season"].iloc[-1]),
            "games_played": len(g),
            "trailing": trailing,
            "trailing_start": trailing_start,
            "longest": longest,
            "longest_start": longest_start,
            "active": longest > 0 and trailing == longest,
        })
    return pd.DataFrame(rows)


def _rounds_label(raw, season):
    if raw is None:
        return _NA
    return f"Round {_display_round(raw, season)}"


def report_active(cur_st, top_n, latest_raw):
    _banner(f"1. LONGEST ACTIVE PROJECTED-POLL STREAKS, {CUR_SEASON} "
            f"(top {top_n})")
    print(f"Streaks alive as of AFLTables Round {latest_raw}, shown as "
          f"Round {_display_round(latest_raw, CUR_SEASON)}.")
    print("Projected poll means Exp_Votes rank 1, 2 or 3 inside the game.")
    print("Lengths count consecutive games played, not rounds.")
    print()

    live = cur_st[cur_st["trailing"] > 0].sort_values(
        ["trailing", "games_played", "Player_Name"],
        ascending=[False, False, True],
    ).head(top_n)

    if live.empty:
        print("None.")
        return live

    print(f"{'#':>3}  {'player':<24} {'team':<24} {'streak':>7} "
          f"{'played':>7}  {'streak began':<14}")
    print(f"{'':>3}  {'':<24} {'':<24} {'(games)':>7} {'(games)':>7}")
    print("-" * 96)
    for i, (_, r) in enumerate(live.iterrows(), start=1):
        print(f"{i:>3}  {r['Player_Name']:<24} {r['Team']:<24} "
              f"{r['trailing']:>7} {r['games_played']:>7}  "
              f"{_rounds_label(r['trailing_start'], CUR_SEASON):<14}")
    return live


def report_side_by_side(live, prev_st, top_n):
    _banner(f"2. THOSE SAME PLAYERS, {CUR_SEASON} PROJECTED NEXT TO "
            f"{PREV_SEASON} ACTUAL")
    print(f"Left column is the {CUR_SEASON} streak the model projects and is "
          f"still running.")
    print(f"Right column is the {PREV_SEASON} streak of real votes as it stood "
          f"at the end of that")
    print("home and away season, which is zero if the player did not poll in "
          "their last game.")
    print("Two different quantities from two different seasons. They are not "
          "added together.")
    print()

    if live.empty:
        print("None.")
        return

    prev_idx = prev_st.set_index("Player_Name")

    print(f"{'#':>3}  {'player':<24} {'team':<24} "
          f"{'2026 projected':>15} {'2025 actual':>13} {'2025 played':>12}")
    print(f"{'':>3}  {'':<24} {'':<24} "
          f"{'(games, live)':>15} {'(games, end)':>13} {'(games)':>12}")
    print("-" * 96)
    for i, (_, r) in enumerate(live.iterrows(), start=1):
        name = r["Player_Name"]
        if name in prev_idx.index:
            p = prev_idx.loc[name]
            actual = f"{int(p['trailing'])}"
            played = f"{int(p['games_played'])}"
        else:
            actual = played = _NA
        print(f"{i:>3}  {name:<24} {r['Team']:<24} "
              f"{r['trailing']:>15} {actual:>13} {played:>12}")

    missing = [n for n in live["Player_Name"] if n not in prev_idx.index]
    if missing:
        print()
        print(f"{_NA} means no {PREV_SEASON} home and away games in "
              f"game_level_{PREV_SEASON}.csv: "
              f"{', '.join(missing)}.")


def report_longest_ever(cur_st, top_n):
    _banner(f"3. LONGEST PROJECTED-POLL STREAKS OF {CUR_SEASON}, ACTIVE OR "
            f"ENDED (top {top_n})")
    print("Best run anywhere in the season, whether or not it is still alive.")
    print("Equal lengths resolve to the more recent run.")
    print()

    best = cur_st[cur_st["longest"] > 0].sort_values(
        ["longest", "games_played", "Player_Name"],
        ascending=[False, False, True],
    ).head(top_n)

    if best.empty:
        print("None.")
        return

    print(f"{'#':>3}  {'player':<24} {'team':<24} {'streak':>7} "
          f"{'played':>7}  {'streak began':<14} {'still alive':<11}")
    print(f"{'':>3}  {'':<24} {'':<24} {'(games)':>7} {'(games)':>7}")
    print("-" * 96)
    for i, (_, r) in enumerate(best.iterrows(), start=1):
        print(f"{i:>3}  {r['Player_Name']:<24} {r['Team']:<24} "
              f"{r['longest']:>7} {r['games_played']:>7}  "
              f"{_rounds_label(r['longest_start'], CUR_SEASON):<14} "
              f"{'yes' if r['active'] else 'no':<11}")


def main():
    ap = argparse.ArgumentParser(
        description="Consecutive-games polling streaks. Prints to stdout only."
    )
    ap.add_argument("--top-active", type=int, default=DEFAULT_TOP_ACTIVE,
                    help=f"rows in report 1 and 2 (default {DEFAULT_TOP_ACTIVE})")
    ap.add_argument("--top-ever", type=int, default=DEFAULT_TOP_EVER,
                    help=f"rows in report 3 (default {DEFAULT_TOP_EVER})")
    args = ap.parse_args()

    _banner("SOURCES")
    cur = _load(CUR_SEASON)
    prev = _load(PREV_SEASON)

    cur["polled"] = flag_projected_poll(cur)
    prev["polled"] = prev["Brownlow.Votes"] > 0

    latest_raw = int(cur["Round_num"].max())
    cur_st = streaks(cur, "polled")
    prev_st = streaks(prev, "polled")

    live = report_active(cur_st, args.top_active, latest_raw)
    report_side_by_side(live, prev_st, args.top_active)
    report_longest_ever(cur_st, args.top_ever)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
