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

# A trailing parenthetical on a player name, which is how same-name players are
# stored disambiguated. See _label_with_team().
_TEAM_SUFFIX_RE = re.compile(r"\([^()]*\)$")

# First season with an AFL Opening Round. Kept in step with dashboard.py:407.
_OPENING_ROUND_FROM = 2024

# game_level_2026.csv is 167 columns wide and most of them are model features.
# Read only what load_latest_round()'s callers quote. Surname is the exception
# to "what the drafts quote": the drafts never print it, but landing_summary.py
# reuses load_latest_round() and needs the stored surname rather than one split
# out of Player_Name, which carries a team suffix for same-name players.
_GAME_COLS = (
    'Season', 'Round_num', 'Game_ID', 'Player_Name', 'Surname', 'Playing.for',
    'Home.team', 'Away.team', 'Outcome', 'Exp_Votes',
    'Disposals', 'Goals', 'Clearances',
)

SITE_URL = "chachingbrownlow.com"

TOP_N_PER_GAME = 3      # the 3/2/1
MOVERS_N = 5            # risers and fallers each
MOVERS_POOL_RANK = 50   # movers must sit inside this rank now or in the snapshot
SPOTLIGHT_VOTE_RANK = 2     # Exp_Votes rank of 1 or 2 inside the game
# Disposals rank of 10 or worse inside the game. Rank 4 admitted players on 26
# disposals, which is not the low-volume profile this section exists to surface.
SPOTLIGHT_DISPOSAL_RANK = 10
# Floor on the projection itself. Topping a game on Exp_Votes says little when
# the value is under 1.0, so the rank conditions alone were not enough.
SPOTLIGHT_MIN_VOTES = 1.4


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


def _label_with_team(player_name, team):
    """Player name followed by their team, unless the name already carries one.

    Players sharing a name are stored disambiguated, so 2026 holds both
    'Bailey Williams (Western Bulldogs)' and 'Bailey Williams (West Coast)'.
    Appending Playing.for to that printed the team twice.

    The test is on the name alone and never compares the suffix to `team`. If
    the two ever disagree, printing the stored name once is the honest
    rendering of what the data says; printing two different teams side by side
    is not, and silently replacing one with the other would hide the conflict.
    """
    name = str(player_name).strip()
    if _TEAM_SUFFIX_RE.search(name):
        return name
    return f"{name} ({team})"


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
        out.append(f"Round {disp_round} Predicted Votes")
        out.append(f"{home} v {away}")
        for slot, (_, r) in zip(range(TOP_N_PER_GAME, 0, -1), top.iterrows()):
            out.append(
                f"{slot}. {_label_with_team(r['Player_Name'], r['Playing.for'])} "
                f"{r['Exp_Votes']:.2f}"
            )
        out.append("")
        out.append(f"See them all on the Game Analysis tab at {SITE_URL}")
        out.append("```")
        out.append("")
    return out


def section_movers(season_now, disp_round, snapshot_path=None, played=None):
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

    Fallers are restricted to the players in `played`, the names appearing in
    the latest round's player-games. Exp_Total_Votes only ever accumulates, so
    a player who did not play gains nothing while the field scores around them
    and slides down the rank for as long as they are out. Unfiltered, the block
    reports the injury list every week instead of form. Risers need no
    equivalent filter: a flat total against a rising field can fall or hold,
    never climb, so nobody absent can reach the risers block anyway. Passing
    played=None filters nothing.
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

    # Review context for whoever checks the draft, not post copy. Deliberately
    # outside both fences so it is never pasted with a block.
    # Two appends, so this lands as two lines. Implicit concatenation inside a
    # single append would join the fragments back into one.
    out.append(
        f"Round {disp_round}. Pool is the top {MOVERS_POOL_RANK} by "
        f"Exp_Total_Votes now or in the previous snapshot."
    )
    out.append("Movement is measured across the full field.")
    out.append("")

    risers = movers[movers['delta'] > 0].sort_values(
        ['delta', 'rank_now'], ascending=[False, True]
    ).head(MOVERS_N)
    # Filtered before .head(), so the block still fills to MOVERS_N with players
    # who actually played rather than returning a short list.
    fallers_pool = movers[movers['delta'] < 0]
    if played is not None:
        fallers_pool = fallers_pool[fallers_pool['Player_Name'].isin(played)]
    fallers = fallers_pool.sort_values(
        ['delta', 'rank_now'], ascending=[True, True]
    ).head(MOVERS_N)

    def _block(title, rows):
        """One pasteable fence. The link goes inside it, not after it, because
        each block is copied out on its own.

        The sign comes from the delta itself rather than from a per-block
        argument, so a riser prints +21 and a faller -4 off one template.
        """
        out.append(f"### {title}")
        out.append("")
        if rows.empty:
            out.append("None.")
            out.append("")
            return
        out.append("```")
        out.append(f"Round {disp_round} Movement - Biggest {title}")
        out.append("")
        for _, r in rows.iterrows():
            out.append(
                f"{r['Player_Name']} {int(r['delta']):+d} "
                f"from {int(r['rank_prev'])} to {int(r['rank_now'])}"
            )
        out.append("")
        out.append(f"See the full leaderboard at {SITE_URL}")
        out.append("```")
        out.append("")

    _block("Risers", risers)
    _block("Fallers", fallers)
    return out


def section_spotlight(rnd, disp_round):
    """Shortlist, not a draft: model rates the game high, disposals do not.

    Three conditions, all required. Exp_Votes rank 1 or 2 inside the game, an
    Exp_Votes value of at least SPOTLIGHT_MIN_VOTES, and disposals rank
    SPOTLIGHT_DISPOSAL_RANK or worse in that same game.

    The value floor and the disposal rank are what make this a low-volume
    shortlist rather than a list of whoever happened to top a quiet game.
    Ranking first on Exp_Votes means little at 0.8 votes, and a disposal rank
    of 4 still admits players on 26 disposals.
    """
    out = ["## Spotlight candidates", ""]
    out.append(
        f"Round {disp_round}. Not drafts. Exp_Votes rank 1 or "
        f"{SPOTLIGHT_VOTE_RANK} in the game, Exp_Votes at least "
        f"{SPOTLIGHT_MIN_VOTES}, disposals rank {SPOTLIGHT_DISPOSAL_RANK} or "
        f"worse in the same game."
    )
    out.append("")
    sel = rnd[
        (rnd['vote_rank'] <= SPOTLIGHT_VOTE_RANK)
        & (rnd['Exp_Votes'] >= SPOTLIGHT_MIN_VOTES)
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
    # Names from the latest round's player-games, used to keep players who did
    # not play out of the fallers block.
    played = set(rnd['Player_Name'])
    lines += section_movers(
        season_now, disp_round, _prev_snapshot_path(latest_raw), played
    )
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


# ─────────────────────────────────────────────────────────────
# Closest calls
# ─────────────────────────────────────────────────────────────

# Its own column tuple rather than _GAME_COLS, which carries neither
# model_source nor the fixture teams this needs and does carry stat columns it
# does not. Kept separate so a change to one reader cannot quietly alter the
# other.
_CLOSEST_COLS = (
    'Season', 'Round_num', 'Game_ID', 'Player_Name', 'Playing.for',
    'Home.team', 'Away.team', 'Exp_Votes', 'model_source',
)


def _fmt_votes(x):
    """Exp_Votes to two decimals, where a nonzero value never prints as 0.00.

    Plain `:.2f` renders 0.004 as "0.00", which asserts a player earned nothing
    when the model gave them something. The magnitude is genuinely below the
    printed precision, so this says so rather than inventing a 0.01 the model
    did not produce.
    """
    if pd.isna(x):
        return "n/a"
    s = f"{float(x):.2f}"
    if s in ("0.00", "-0.00") and float(x) != 0.0:
        return "<0.01" if float(x) > 0 else ">-0.01"
    return "0.00" if s == "-0.00" else s


def build_closest_calls(season, round_num, path=GAME_LEVEL, out_dir=DRAFTS_DIR):
    """Every game of one round, ranked by how close its top two Exp_Votes are.

    Reads predictions/game_level_2026.csv and nothing else. No actual Brownlow
    votes are read: they do not exist for 2026 until count night, and the file's
    Brownlow.Votes column is all zeroes, which is absence rather than a result.

    The sort is on the top-two gap alone. Third place is printed because a tight
    three-way is worth seeing, but it never moves a game up or down: a game
    whose top two are level is the closest call in the round whatever sits
    third.

    Every game is listed. This is deliberately not a top N, so the round's
    clear-cut games are visible as the comparison that makes the close ones
    close.
    """
    df = pd.read_csv(path, usecols=lambda c: c in _CLOSEST_COLS)
    rnd = df[(df['Season'] == int(season)) &
             (df['Round_num'] == int(round_num))].copy()
    if rnd.empty:
        raise ValueError(
            f"no rows for season {season}, raw Round_num {round_num} in {path}. "
            f"Seasons present: {sorted(df['Season'].dropna().unique().astype(int))}; "
            f"rounds present for that season: "
            f"{sorted(df.loc[df['Season'] == int(season), 'Round_num'].dropna().unique().astype(int))}")

    disp_round = _display_round(round_num, season)
    sources = sorted(rnd['model_source'].dropna().unique().tolist())
    mixed = len(sources) > 1

    # 'Playing.for' holds a dot, which itertuples renames positionally, so the
    # club is read by label off the sorted frame instead. Same trap as
    # 'Coaches.Votes' elsewhere in this repo.
    rows = []
    for game_id, g in rnd.groupby('Game_ID'):
        if len(g) < 2:
            # Cannot form a gap from one player. Never silently skipped.
            raise ValueError(f"game {game_id} holds {len(g)} row(s), "
                             f"a top-two gap needs at least 2")
        top = g.sort_values('Exp_Votes', ascending=False).head(3).reset_index(drop=True)

        def _slot(i):
            """(label, Exp_Votes) for the i-th ranked player, or a no-data pair."""
            if i >= len(top):
                return "n/a", float('nan')
            return (_label_with_team(top.at[i, 'Player_Name'],
                                     top.at[i, 'Playing.for']),
                    float(top.at[i, 'Exp_Votes']))

        first, first_v = _slot(0)
        second, second_v = _slot(1)
        third, third_v = _slot(2)
        rows.append({
            'fixture': f"{g['Home.team'].iloc[0]} v {g['Away.team'].iloc[0]}",
            'gap': first_v - second_v,
            'first': first, 'first_v': first_v,
            'second': second, 'second_v': second_v,
            'third': third, 'third_v': third_v,
            'source': g['model_source'].iloc[0],
        })

    # Smallest gap first. Fixture breaks a tie so a re-run is byte-identical.
    rows.sort(key=lambda r: (r['gap'], r['fixture']))

    L = [f"# Round {disp_round} closest calls", ""]
    L.append(f"Source: `{path}`. Season {int(season)}, AFLTables Round_num "
             f"{int(round_num)}, shown throughout as Round {disp_round}.")
    L.append("")
    L.append(f"All {len(rows)} games of the round, ranked by the gap between the "
             f"top two Exp_Votes, smallest gap first. Every game is listed, this "
             f"is not a top N.")
    L.append("")
    L.append("Exp_Votes is a **model expectation, retrospective**. It scores a "
             "game that has already been played and is not a forecast.")
    L.append("")
    L.append("Actual Brownlow votes are not read here. They are not known until "
             "count night.")
    L.append("")
    if mixed:
        L.append(f"This round mixes model variants, so `model_source` is shown "
                 f"per game: {', '.join(sources)}.")
    else:
        L.append(f"Every game in this round ran on one model variant, "
                 f"`model_source` = `{sources[0] if sources else 'unknown'}`.")
    L.append("")

    head = "| # | fixture | gap | 1st | Exp | 2nd | Exp | 3rd | Exp |"
    rule = "|---|---|---|---|---|---|---|---|---|"
    if mixed:
        # Both already end in a pipe, so the extra cell appends. Trimming that
        # pipe first leaves the header a cell short of the data rows and the
        # table stops rendering as a table.
        head = head + " model_source |"
        rule = rule + "---|"
    L.append(head)
    L.append(rule)
    for i, r in enumerate(rows, 1):
        cells = [str(i), r['fixture'], _fmt_votes(r['gap']),
                 r['first'], _fmt_votes(r['first_v']),
                 r['second'], _fmt_votes(r['second_v']),
                 r['third'], _fmt_votes(r['third_v'])]
        if mixed:
            cells.append(str(r['source']))
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"closest_calls_r{disp_round}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L).rstrip() + "\n")
    print(f"OK wrote {out_path} ({len(rows)} games, "
          f"tightest gap {_fmt_votes(rows[0]['gap'])})")
    return out_path


def main_closest_calls(argv):
    if len(argv) != 2:
        print("usage: python draft_posts.py closest-calls <season> <raw_round_num>",
              file=sys.stderr)
        return 2
    build_closest_calls(int(argv[0]), int(argv[1]))
    return 0


if __name__ == "__main__":
    # No arguments runs the round card, which is what update.py invokes. The
    # subcommand is additive and leaves that path untouched.
    if len(sys.argv) > 1 and sys.argv[1] == "closest-calls":
        sys.exit(main_closest_calls(sys.argv[2:]))
    sys.exit(main())
