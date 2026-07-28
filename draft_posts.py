"""Templated draft post generator for the weekly round writeup.

Reads what predict_2026.py just wrote and emits drafts/round_<display>.md for
manual review. There is no model here, no LLM call, no network access and no
posting. Every line of generated output is a format string filled with a number
that came straight out of the CSVs.

COPY RULES
These constrain the generated markdown. They are the reason this file is
templated rather than generative, so any edit that adds prose has to keep them.
  * No accuracy percentages of any kind in generated text.
  * No em dashes.
  * Every draft carries the display round number.
  * Numbers only, no adjectives, no claims about likelihood.

ROUND NUMBERING
Round_num in the CSVs is the raw AFLTables number. Seasons from 2024 onward open
with an Opening Round, so their AFLTables number runs one ahead of the AFL round
the world uses. Every round number that reaches a draft or a filename goes
through _display_round() first. That logic is copied from dashboard.py:409
rather than imported, because importing dashboard.py executes a Streamlit page.

SNAPSHOT
Section 2 diffs the current season table against a snapshot of season_2026.csv
kept in predictions/snapshots/, one file per raw Round_num, named
_snapshot_season_r<raw>.csv. Each run reads the newest snapshot from a round
strictly earlier than the one it is drafting, then writes its own. Keying on the
round rather than on run order is what makes a re-run safe: it overwrites only
this round's snapshot, with identical data, and never touches the earlier round
the diff depends on. When no earlier snapshot exists, section 2 is skipped with
a note in the file. Git history is never consulted.

Run standalone, or as the last step of update.py:
    python draft_posts.py
"""

import os
import re
import shutil
import sys
from datetime import datetime

import pandas as pd

GAME_LEVEL = "predictions/game_level_2026.csv"
SEASON = "predictions/season_2026.csv"
SNAPSHOT_DIR = "predictions/snapshots"
DRAFTS_DIR = "drafts"

# Snapshots are named _snapshot_season_r<raw Round_num>.csv inside SNAPSHOT_DIR.
_SNAPSHOT_RE = re.compile(r"^_snapshot_season_r(\d+)\.csv$")

# First season with an AFL Opening Round. Kept in step with dashboard.py:407.
_OPENING_ROUND_FROM = 2024

# game_level_2026.csv is 167 columns wide and most of them are model features.
# Read only what the drafts quote.
_GAME_COLS = (
    'Season', 'Round_num', 'Game_ID', 'Player_Name', 'Playing.for',
    'Home.team', 'Away.team', 'Outcome', 'Exp_Votes',
    'Disposals', 'Goals', 'Clearances',
)

TOP_N_PER_GAME = 3      # the 3/2/1
MOVERS_N = 5            # risers and fallers each
MOVERS_POOL_RANK = 50   # movers must sit inside this rank now or in the snapshot
SPOTLIGHT_VOTE_RANK = 2     # Exp_Votes rank of 1 or 2 inside the game
SPOTLIGHT_DISPOSAL_RANK = 4  # Disposals rank of 4 or worse inside the game


def _display_round(round_num, season):
    """AFLTables Round_num to the AFL round number shown to readers.

    Copied from dashboard.py:409. Season-aware: only 2024 onward run one ahead,
    so this must not be flattened to a bare `rn - 1`.
    """
    try:
        rn = int(round_num)
        sn = int(season)
    except (TypeError, ValueError):
        return round_num
    return rn - 1 if sn >= _OPENING_ROUND_FROM else rn


def _snapshot_path(raw_round, snapshot_dir=SNAPSHOT_DIR):
    """Path this round's snapshot is written to.

    Sole place the filename pattern is built, so _prev_snapshot_path() and the
    write at the end of main() cannot drift apart.
    """
    return os.path.join(snapshot_dir, f"_snapshot_season_r{int(raw_round)}.csv")


def _prev_snapshot_path(latest_raw, snapshot_dir=SNAPSHOT_DIR):
    """Path of the newest snapshot from a round strictly before latest_raw.

    None when the directory is absent or holds nothing earlier, which is also
    what happens on the first run of a season.

    The round is parsed out of each filename and compared as an int. Sorting the
    names as strings would put r9 after r21, and would also pick up any unrelated
    file that happened to sort last, so anything not matching _SNAPSHOT_RE is
    ignored rather than assumed to be a snapshot.
    """
    if not os.path.isdir(snapshot_dir):
        return None
    latest_raw = int(latest_raw)
    earlier = [
        int(m.group(1))
        for m in (_SNAPSHOT_RE.match(name) for name in os.listdir(snapshot_dir))
        if m and int(m.group(1)) < latest_raw
    ]
    if not earlier:
        return None
    return _snapshot_path(max(earlier), snapshot_dir)


def _rank_desc(s):
    """Rank a series with 1 as the highest value.

    method='min' so tied players share the better rank, matching how a reader
    would describe a two-way tie for most disposals.
    """
    return s.rank(ascending=False, method='min')


def load_latest_round(path=GAME_LEVEL):
    """The latest round's player-games, with in-game ranks attached.

    Ranks are computed here from Exp_Votes and Disposals rather than read from
    the pipeline's own rank columns: game_level carries `ExpVotes_game_rank`,
    which ranks the Wheelo ExpVotes feature, not the model's `Exp_Votes` output.
    The two names differ by one underscore and mean different things.
    """
    df = pd.read_csv(path, usecols=lambda c: c in _GAME_COLS)
    latest = int(df['Round_num'].max())
    rnd = df[df['Round_num'] == latest].copy()
    rnd['vote_rank'] = rnd.groupby('Game_ID')['Exp_Votes'].transform(_rank_desc)
    rnd['disp_rank'] = rnd.groupby('Game_ID')['Disposals'].transform(_rank_desc)
    season = int(rnd['Season'].max())
    return rnd, latest, season


def section_three_two_one(rnd, disp_round):
    """Per game, the top three by Exp_Votes as a 3/2/1 draft block."""
    out = ["## Round 3/2/1", ""]
    for _gid, g in rnd.groupby('Game_ID', sort=True):
        home = str(g['Home.team'].iloc[0])
        away = str(g['Away.team'].iloc[0])
        top = g.sort_values(
            ['Exp_Votes', 'Player_Name'], ascending=[False, True]
        ).head(TOP_N_PER_GAME)
        out.append(f"### {home} v {away}")
        out.append("")
        out.append("```")
        out.append(f"Round {disp_round} projected votes")
        out.append(f"{home} v {away}")
        for slot, (_, r) in zip(range(TOP_N_PER_GAME, 0, -1), top.iterrows()):
            out.append(
                f"{slot}. {r['Player_Name']} ({r['Playing.for']}) "
                f"{r['Exp_Votes']:.2f}"
            )
        out.append("```")
        out.append("")
    return out


def section_movers(season_now, disp_round, snapshot_path=None):
    """Season rank now against the previous round's snapshot.

    Left join on Player_Name, never positional: the player pool grows week to
    week, so row N of one file is not row N of the other. Anyone missing from
    the snapshot is a new entrant, and is dropped rather than being handed a
    fabricated rank to move from.

    Movement is measured across the full field, so a climb from 60 to 45 reads
    as +15. Only eligibility for the printed list is capped, at MOVERS_POOL_RANK
    now or in the snapshot. Exp_Total_Votes is cumulative from zero, so without
    the cap the list fills with fringe players vaulting hundreds of ranks off a
    single game while the contenders barely shuffle. Keeping last week's top 50
    eligible is what lets a player who drops out of it still show as a faller.
    """
    out = ["## Biggest movers", ""]
    if snapshot_path is None or not os.path.exists(snapshot_path):
        out.append(
            f"No snapshot from an earlier round, so there is nothing to diff "
            f"Round {disp_round} against. This section populates next round."
        )
        out.append("")
        return out

    prev = pd.read_csv(snapshot_path, usecols=['Player_Name', 'Exp_Total_Votes'])
    cur = season_now[['Player_Name', 'Team', 'Exp_Total_Votes']].copy()
    cur['rank_now'] = _rank_desc(cur['Exp_Total_Votes'])
    prev = prev.copy()
    prev['rank_prev'] = _rank_desc(prev['Exp_Total_Votes'])

    merged = cur.merge(prev[['Player_Name', 'rank_prev']], on='Player_Name', how='left')
    # Absent from the snapshot means no rank to move from, so no delta exists.
    movers = merged[merged['rank_prev'].notna()].copy()
    movers['delta'] = movers['rank_prev'] - movers['rank_now']
    movers = movers[
        (movers['rank_now'] <= MOVERS_POOL_RANK)
        | (movers['rank_prev'] <= MOVERS_POOL_RANK)
    ]

    out.append(
        f"Round {disp_round}. Pool is the top {MOVERS_POOL_RANK} by "
        f"Exp_Total_Votes now or in the previous snapshot. Movement is measured "
        f"across the full field."
    )
    out.append("")

    risers = movers[movers['delta'] > 0].sort_values(
        ['delta', 'rank_now'], ascending=[False, True]
    ).head(MOVERS_N)
    fallers = movers[movers['delta'] < 0].sort_values(
        ['delta', 'rank_now'], ascending=[True, True]
    ).head(MOVERS_N)

    def _block(title, rows, sign):
        out.append(f"### {title}")
        out.append("")
        if rows.empty:
            out.append("None.")
            out.append("")
            return
        out.append("```")
        out.append(f"Round {disp_round} {title.lower()}")
        for _, r in rows.iterrows():
            out.append(
                f"{r['Player_Name']} ({r['Team']}) "
                f"{int(r['rank_prev'])} to {int(r['rank_now'])} "
                f"({sign}{abs(int(r['delta']))}), {r['Exp_Total_Votes']:.1f}"
            )
        out.append("```")
        out.append("")

    _block("Risers", risers, "+")
    _block("Fallers", fallers, "-")
    return out


def section_spotlight(rnd, disp_round):
    """Shortlist, not a draft: model rates the game high, disposals do not.

    Exp_Votes rank 1 or 2 inside the game while sitting 4th or worse for
    disposals in that same game.
    """
    out = ["## Spotlight candidates", ""]
    out.append(
        f"Round {disp_round}. Not drafts. Exp_Votes rank 1 or 2 in the game, "
        f"disposals rank {SPOTLIGHT_DISPOSAL_RANK} or worse in the same game."
    )
    out.append("")
    sel = rnd[
        (rnd['vote_rank'] <= SPOTLIGHT_VOTE_RANK)
        & (rnd['disp_rank'] >= SPOTLIGHT_DISPOSAL_RANK)
    ].sort_values(['Exp_Votes', 'Player_Name'], ascending=[False, True])

    if sel.empty:
        out.append("None.")
        out.append("")
        return out

    out.append("| Player | Team | Votes rank | Exp_Votes | Disp rank | Disposals | Goals | Clearances | Result |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in sel.iterrows():
        out.append(
            f"| {r['Player_Name']} | {r['Playing.for']} | {int(r['vote_rank'])} | "
            f"{r['Exp_Votes']:.2f} | {int(r['disp_rank'])} | {int(r['Disposals'])} | "
            f"{int(r['Goals'])} | {int(r['Clearances'])} | {r['Outcome']} |"
        )
    out.append("")
    return out


def main():
    for path in (GAME_LEVEL, SEASON):
        if not os.path.exists(path):
            print(f"! {path} not found. Run predict_2026.py first.")
            return 1

    rnd, latest_raw, season = load_latest_round()
    disp_round = _display_round(latest_raw, season)
    season_now = pd.read_csv(SEASON)

    lines = [
        f"# Round {disp_round} draft posts",
        "",
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from "
        f"{GAME_LEVEL} and {SEASON}.",
        f"AFLTables Round_num {latest_raw}, shown throughout as Round {disp_round}.",
        "Drafts are templated from CSV values. Review before posting.",
        "",
    ]
    lines += section_three_two_one(rnd, disp_round)
    lines += section_movers(season_now, disp_round, _prev_snapshot_path(latest_raw))
    lines += section_spotlight(rnd, disp_round)

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    out_path = os.path.join(DRAFTS_DIR, f"round_{disp_round}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    # Snapshot last, so the diff above ran against the earlier round's copy.
    # Keyed on the raw round, so a re-run overwrites this round's own snapshot
    # with identical data and leaves the one the diff reads alone.
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snapshot_path = _snapshot_path(latest_raw)
    shutil.copyfile(SEASON, snapshot_path)

    print(f"OK wrote {out_path} ({len(lines)} lines)")
    print(f"OK snapshot written to {snapshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
