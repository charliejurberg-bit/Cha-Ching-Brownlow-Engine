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

WHY REPORT 2 COMPARES LONGEST AGAINST LONGEST
An active streak and an end-of-season streak are not the same measurement. An
active streak is observed at its maximum, because it is still running and has
not yet met the game that ends it. An end-of-season streak is whatever happened
to be running when the fixture stopped, truncated at a cutoff that has nothing
to do with the player. Putting one against the other flatters the live figure
and understates the finished one. Longest against longest is the like-for-like
pair, so report 2 shows each player's best run in each season and carries the
live 2026 figure alongside as a third, separately labelled column. The 2025
number covers a completed home and away season and the 2026 number covers the
season so far, which is the one asymmetry that remains and cannot be removed
while 2026 is still being played.

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

OUTPUT
Prints three reports to the terminal and writes the same three to
drafts/streaks_r<display round>.md as markdown tables. The file is in addition
to the terminal output, never instead of it, and is overwritten on a re-run the
way draft_posts.py overwrites its own draft. Pass --no-file for terminal only.

Both renderings read the same selected frames, built once by select_active()
and select_longest(), and the same preamble copy, built once by the notes_*
functions. Nothing is computed twice, so the file and the terminal cannot
disagree.

COPY RULES
Inherited from draft_posts.py, since this writes into the same drafts/ folder.
  * No accuracy percentages of any kind in generated text.
  * No em dashes.
  * Every table carries the display round number.

Run:
    python streaks.py
    python streaks.py --top-active 25 --top-ever 20
    python streaks.py --no-file
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd

PRED_DIR = "predictions"
DRAFTS_DIR = "drafts"
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

# Report 1 floor. Without it the table fills with streaks of one, which is just
# the list of players who polled in the latest round, ordered by a tiebreak
# rather than by anything the report is about.
MIN_ACTIVE_STREAK = 3

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


def _source_path(season):
    return os.path.join(PRED_DIR, f"game_level_{season}.csv")


def _load(season):
    """Read one game_level file, drop finals rows, dedupe player-games.

    Prints what it dropped rather than dropping quietly, because the 2025
    duplicate count is the number most likely to change under the reader's feet
    if predictions are ever regenerated.
    """
    path = _source_path(season)
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


# ----------------------------------------------------------------------
# selection
#
# The only place rows are chosen. Both the terminal tables and the markdown
# file render these same frames, so the two outputs cannot drift apart.
# ----------------------------------------------------------------------
def count_below_floor(cur_st):
    """Players on a live streak too short for report 1."""
    return int(((cur_st["trailing"] > 0)
                & (cur_st["trailing"] < MIN_ACTIVE_STREAK)).sum())


def select_active(cur_st, top_n):
    return cur_st[cur_st["trailing"] >= MIN_ACTIVE_STREAK].sort_values(
        ["trailing", "games_played", "Player_Name"],
        ascending=[False, False, True],
    ).head(top_n)


def select_longest(cur_st, top_n):
    return cur_st[cur_st["longest"] > 0].sort_values(
        ["longest", "games_played", "Player_Name"],
        ascending=[False, False, True],
    ).head(top_n)


def _prev_longest(prev_idx, name):
    if name in prev_idx.index:
        return f"{int(prev_idx.loc[name]['longest'])}"
    return _NA


def _missing_prev(live, prev_idx):
    return [n for n in live["Player_Name"] if n not in prev_idx.index]


# ----------------------------------------------------------------------
# preamble copy
#
# Written once and rendered twice. The terminal keeps these as separate
# lines; markdown joins each list into one paragraph.
# ----------------------------------------------------------------------
def title_active(top_n):
    return (f"1. LONGEST ACTIVE PROJECTED-POLL STREAKS, {CUR_SEASON} "
            f"(top {top_n})")


def title_side_by_side():
    return (f"2. THOSE SAME PLAYERS, {CUR_SEASON} PROJECTED NEXT TO "
            f"{PREV_SEASON} ACTUAL")


def title_longest(top_n):
    return (f"3. LONGEST PROJECTED-POLL STREAKS OF {CUR_SEASON}, ACTIVE OR "
            f"ENDED (top {top_n})")


def notes_active(latest_raw, below):
    return [
        f"Streaks alive as of AFLTables Round {latest_raw}, shown as "
        f"Round {_display_round(latest_raw, CUR_SEASON)}.",
        "Projected poll means Exp_Votes rank 1, 2 or 3 inside the game.",
        "Actual poll means Brownlow.Votes greater than zero.",
        "Lengths count consecutive games played, not rounds.",
        f"Minimum streak {MIN_ACTIVE_STREAK} games.",
        f"{below} player(s) with a live streak shorter than "
        f"{MIN_ACTIVE_STREAK} games excluded by the floor.",
    ]


def notes_side_by_side():
    return [
        "Longest against longest. An active streak is observed at its "
        "maximum because nothing has",
        "ended it yet, while a streak measured at a season cutoff is "
        "truncated by the fixture and",
        "not by the player, so the two are not comparable. The best run in "
        "each season is.",
        f"The live {CUR_SEASON} figure is carried alongside for reference. "
        f"{PREV_SEASON} covers a completed",
        f"home and away season, {CUR_SEASON} covers the season so far. "
        f"Three separate quantities,",
        "never added together.",
    ]


def notes_longest():
    return [
        "Best run anywhere in the season, whether or not it is still alive.",
        "Equal lengths resolve to the more recent run.",
    ]


# ----------------------------------------------------------------------
# terminal rendering
# ----------------------------------------------------------------------
def print_active(live, notes, top_n):
    _banner(title_active(top_n))
    for line in notes:
        print(line)
    print()

    if live.empty:
        print("None.")
        return

    print(f"{'#':>3}  {'player':<24} {'team':<24} {'streak':>7} "
          f"{'played':>7}  {'streak began':<14}")
    print(f"{'':>3}  {'':<24} {'':<24} {'(games)':>7} {'(games)':>7}")
    print("-" * 96)
    for i, (_, r) in enumerate(live.iterrows(), start=1):
        print(f"{i:>3}  {r['Player_Name']:<24} {r['Team']:<24} "
              f"{r['trailing']:>7} {r['games_played']:>7}  "
              f"{_rounds_label(r['trailing_start'], CUR_SEASON):<14}")


def print_side_by_side(live, prev_idx, notes):
    _banner(title_side_by_side())
    for line in notes:
        print(line)
    print()

    if live.empty:
        print("None.")
        return

    print(f"{'#':>3}  {'player':<24} {'team':<24} "
          f"{'2026 active':>13} {'2026 longest':>13} {'2025 longest':>13}")
    print(f"{'':>3}  {'':<24} {'':<24} "
          f"{'(live)':>13} {'(best so far)':>13} {'(best, full)':>13}")
    print("-" * 96)
    for i, (_, r) in enumerate(live.iterrows(), start=1):
        print(f"{i:>3}  {r['Player_Name']:<24} {r['Team']:<24} "
              f"{r['trailing']:>13} {r['longest']:>13} "
              f"{_prev_longest(prev_idx, r['Player_Name']):>13}")

    missing = _missing_prev(live, prev_idx)
    if missing:
        print()
        print(f"{_NA} means no {PREV_SEASON} home and away games in "
              f"game_level_{PREV_SEASON}.csv: "
              f"{', '.join(missing)}.")


def print_longest(best, notes, top_n):
    _banner(title_longest(top_n))
    for line in notes:
        print(line)
    print()

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


# ----------------------------------------------------------------------
# markdown rendering
#
# Same frames, same copy, different layout. Terminal sub-labels become part
# of the header cell, since a markdown table has only one header row.
# ----------------------------------------------------------------------
def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return out


def _md_section(title, notes, headers, rows, empty_note="None."):
    out = [f"## {title}", ""]
    out += notes
    out.append("")
    if not rows:
        out.append(empty_note)
        out.append("")
        return out
    out += _md_table(headers, rows)
    out.append("")
    return out


def build_markdown(live, best, prev_idx, latest_raw, disp_round,
                   top_active, top_ever, below):
    lines = [
        f"# Round {disp_round} streaks",
        "",
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from "
        f"{_source_path(CUR_SEASON)} and {_source_path(PREV_SEASON)}.",
        f"AFLTables Round_num {latest_raw}, shown throughout as "
        f"Round {disp_round}.",
        "Templated from CSV values. Review before posting.",
        "",
    ]

    lines += _md_section(
        title_active(top_active),
        notes_active(latest_raw, below),
        ["#", "player", "team", "streak (games)", "played (games)",
         "streak began"],
        [[i, r["Player_Name"], r["Team"], r["trailing"], r["games_played"],
          _rounds_label(r["trailing_start"], CUR_SEASON)]
         for i, (_, r) in enumerate(live.iterrows(), start=1)],
    )

    side_rows = [
        [i, r["Player_Name"], r["Team"], r["trailing"], r["longest"],
         _prev_longest(prev_idx, r["Player_Name"])]
        for i, (_, r) in enumerate(live.iterrows(), start=1)
    ]
    lines += _md_section(
        title_side_by_side(),
        notes_side_by_side(),
        ["#", "player", "team", f"{CUR_SEASON} active (live)",
         f"{CUR_SEASON} longest (best so far)",
         f"{PREV_SEASON} longest (best, full)"],
        side_rows,
    )
    missing = _missing_prev(live, prev_idx)
    if missing:
        lines.append(f"{_NA} means no {PREV_SEASON} home and away games in "
                     f"{_source_path(PREV_SEASON)}: {', '.join(missing)}.")
        lines.append("")

    lines += _md_section(
        title_longest(top_ever),
        notes_longest(),
        ["#", "player", "team", "streak (games)", "played (games)",
         "streak began", "still alive"],
        [[i, r["Player_Name"], r["Team"], r["longest"], r["games_played"],
          _rounds_label(r["longest_start"], CUR_SEASON),
          "yes" if r["active"] else "no"]
         for i, (_, r) in enumerate(best.iterrows(), start=1)],
    )
    return lines


def write_markdown(lines, disp_round):
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    out_path = os.path.join(DRAFTS_DIR, f"streaks_r{disp_round}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


def main():
    ap = argparse.ArgumentParser(
        description="Consecutive-games polling streaks. Prints to the terminal "
                    "and writes a markdown file."
    )
    ap.add_argument("--top-active", type=int, default=DEFAULT_TOP_ACTIVE,
                    help=f"rows in report 1 and 2 (default {DEFAULT_TOP_ACTIVE})")
    ap.add_argument("--top-ever", type=int, default=DEFAULT_TOP_EVER,
                    help=f"rows in report 3 (default {DEFAULT_TOP_EVER})")
    ap.add_argument("--no-file", action="store_true",
                    help="terminal output only, skip the markdown file")
    args = ap.parse_args()

    _banner("SOURCES")
    cur = _load(CUR_SEASON)
    prev = _load(PREV_SEASON)

    cur["polled"] = flag_projected_poll(cur)
    prev["polled"] = prev["Brownlow.Votes"] > 0

    latest_raw = int(cur["Round_num"].max())
    disp_round = _display_round(latest_raw, CUR_SEASON)
    cur_st = streaks(cur, "polled")
    prev_st = streaks(prev, "polled")

    below = count_below_floor(cur_st)
    live = select_active(cur_st, args.top_active)
    best = select_longest(cur_st, args.top_ever)
    prev_idx = prev_st.set_index("Player_Name")

    print_active(live, notes_active(latest_raw, below), args.top_active)
    print_side_by_side(live, prev_idx, notes_side_by_side())
    print_longest(best, notes_longest(), args.top_ever)
    print()

    if not args.no_file:
        lines = build_markdown(live, best, prev_idx, latest_raw, disp_round,
                               args.top_active, args.top_ever, below)
        out_path = write_markdown(lines, disp_round)
        print(f"OK wrote {out_path} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
