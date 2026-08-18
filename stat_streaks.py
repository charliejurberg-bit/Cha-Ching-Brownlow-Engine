"""Consecutive-games stat streaks, active and all-time, 1965-2026.

    build_stat_streaks(stat, threshold, season)   one stat, one threshold
    build_streak_board(season)                    the default pairs, one table

A streak is preview-native in a way a career total is not. It is a fact carried
into the game, it changes every round by definition, since it either extends or
breaks, and it needs no model output to state.

`streaks.py` already covers polling streaks, meaning Exp_Votes rank and actual
Brownlow votes. This module covers stat streaks and shares nothing with it: no
votes, no model output, no `Exp_Votes`.

RECON / DRAFT OUTPUT ONLY. Like club_aliases, all_time_tables, fewest_games,
milestones and round_bests, this module must not be imported by features.py,
brownlow_model.py or predict_2026.py: it canonicalises club strings, which
would change the model's feature space without a retrain.

"Consecutive games" means two different things
----------------------------------------------
This is the trap, and it is worth more than the rest of the module.

Peter McKenna's goal streak measures 121 here: 121 straight appearances with at
least one goal, from Round 1 1968 to Round 3 1974. In the same window
Collingwood played 140 matches. He missed 19 of them, and none of those absences
broke the run, because under this convention a missed game neither breaks a
streak nor extends it.

The figure usually published for McKenna is 119. This module cannot reconcile
121 against 119, because the published figure does not travel with its
definition, and the gap is the size that a finals rule, a different span or a
different absence rule would each produce. So no reconciliation is claimed. What
is done instead is to state the convention used and to print, for every streak
shown, how many club matches fell inside the run and how many of them the player
missed.

That disclosure is the point. A run with no missed matches means the same thing
under either convention and can be written without qualification. A run with
missed matches inside it is a different claim under each, and the copy has to
choose one and say so. "45 straight games" is ambiguous in AFL writing, and a
post that picks the wrong reading is wrong even though the arithmetic is right.

The convention used here, stated once
--------------------------------------
A streak is consecutive APPEARANCES by the player clearing the threshold.
Streaks span seasons, because a season boundary is not a break in anything the
player did. Finals count, since a streak is an appearance record and the finals
rule in `project_brief.md` puts appearance records on all matches.

Active streaks
--------------
A run is active when it ends on the player's most recent appearance in the
frame AND that appearance falls in the reporting season. Both halves are needed:
the first makes it unbroken, the second stops a player who last played in 2019
from carrying a permanently "active" streak.

A player can be active and still have missed the latest round, through injury or
omission, so every active row prints the round he was last seen in. A streak
carried by a player who has not played for a month is still unbroken and is a
weaker preview line, and the reader should be able to see which they have.

The window truncates runs, and only downward
--------------------------------------------
Each stat is comparable only from the season its column is completely
populated, reusing the floors measured and checked in `round_bests.py` rather
than restating them, so the two modules cannot drift on what "all-time" means.

A run in progress at the floor is cut off at it. That error runs one way: a
truncated run is reported shorter than it was, never longer. A leader can
therefore be understated, and a player whose real run began before the floor can
be missing from the top of a table. Every all-time table says so.

Player identity is keyed on `ID`, never name. The two Josh Kennedys hold
separate runs here and would fuse into one impossible streak if keyed by name.
"""

import os
import sys

import pandas as pd

import fewest_games as fg
from club_aliases import canonical_club
from draft_posts import _display_round
# Floors, the drift guard and the two formatters are imported rather than
# restated. If round_bests re-measures a floor, "all-time" moves in both
# modules at once, which is the only safe way for two files to share a window.
from round_bests import EXPECTED_FLOORS, _measure_floor, _ordinal, _plural

DRAFTS_DIR = "drafts"

# The board's default pairs, in output order. Chosen so each fires: every one
# has at least one active run in 2026 and a non-trivial all-time table.
DEFAULT_PAIRS = [
    ('Disposals', 30), ('Disposals', 25), ('Disposals', 20),
    ('Goals', 3), ('Goals', 2), ('Goals', 1),
    ('Tackles', 8), ('Tackles', 5),
    ('Marks', 7),
    ('Clearances', 5),
    ('Contested.Possessions', 15),
    ('Inside.50s', 5),
    ('Hit.Outs', 30), ('Hit.Outs', 20),
]

CONVENTION_NOTE = (
    "**A streak here is consecutive APPEARANCES clearing the threshold.** A "
    "game the player missed neither breaks the run nor extends it. Streaks "
    "span seasons, because a season boundary is not a break in anything the "
    "player did, and finals count, because a streak is an appearance record."
)

AMBIGUITY_NOTE = (
    "**\"Consecutive games\" has a second meaning, and every row below says "
    "which applies.** Under the other reading a run breaks the moment the "
    "player misses one of his club's matches. Each row prints the club matches "
    "that fell inside the run and how many the player missed. A run with 0 "
    "missed means the same thing under either reading and can be written "
    "without qualification; a run with missed matches inside it is a different "
    "claim under each, and the copy has to pick one and say so."
)

TRUNCATION_NOTE = (
    "**Runs are cut off at the window, and the error runs one way.** A run "
    "still in progress in the first comparable season is reported from that "
    "season only, so it is understated and never overstated. A leader can "
    "therefore be understated, and a player whose real run began before the "
    "floor can be missing from the top of this table."
)


# ─────────────────────────────────────────────────────────────
# Runs
# ─────────────────────────────────────────────────────────────

def _runs(sub):
    """One row per unbroken run of clearing appearances, keyed on ID.

    Blocks are cut whenever the hit flag flips OR the player changes. Sorting by
    ID first and taking the flip against a per-player shift means a block can
    never span two players, so no run is stitched across careers.
    """
    sub = sub.sort_values(['ID', 'Date'], kind='mergesort')
    flip = sub['_hit'] != sub.groupby('ID')['_hit'].shift()
    sub = sub.assign(_blk=flip.cumsum())
    hits = sub[sub['_hit']]
    if hits.empty:
        return pd.DataFrame(columns=['ID', 'n', 'start', 'end', 'clubs'])
    runs = (hits.groupby(['ID', '_blk'])
                .agg(n=('_hit', 'size'), start=('Date', 'min'),
                     end=('Date', 'max'),
                     clubs=('Playing.for',
                            lambda s: tuple(sorted({canonical_club(x)
                                                    for x in s}))))
                .reset_index())
    return runs


def _matches_for_club(df, club, lo, hi):
    window = df[(df['Date'] >= lo) & (df['Date'] <= hi)]
    if window.empty:
        return 0
    home = window['Home.team'].map(canonical_club)
    away = window['Away.team'].map(canonical_club)
    theirs = window[(home == club) | (away == club)]
    return len(theirs.drop_duplicates(subset=fg._GAME_KEY))


def _missed_inside(df, run):
    """Club matches inside the run's span, and how many the player missed.

    This is the figure that disambiguates the two readings of "consecutive
    games", so it is computed for the rows actually printed rather than
    inferred.

    Counted per club SEGMENT, not over the union of his clubs. A player traded
    mid-run could only ever have played the fixtures of the club he was at, so
    the span is split at each move and each part counted against that club
    alone. Counting the union instead roughly doubles the denominator for any
    player who moved: Bailey Smith's 45-game run came out as 94 missed matches
    that way, because his Western Bulldogs fixtures and his Geelong fixtures
    were both counted across the whole span.
    """
    pid, lo, hi = run['ID'], run['start'], run['end']
    mine = df[(df['ID'] == pid) & (df['Date'] >= lo)
              & (df['Date'] <= hi)].sort_values('Date')
    if mine.empty:
        return 0, 0
    club = mine['Playing.for'].map(canonical_club)
    segment = (club != club.shift()).cumsum()
    matches = 0
    for _, part in mine.groupby(segment):
        matches += _matches_for_club(
            df, canonical_club(part['Playing.for'].iloc[0]),
            part['Date'].min(), part['Date'].max())
    # Measured against his appearances in the span rather than the run length.
    # Inside a run the two are equal by construction, since a non-clearing
    # appearance would have ended the run, and using the measured count keeps
    # the subtraction honest if that ever stops holding.
    return matches, matches - len(mine)


# ─────────────────────────────────────────────────────────────
# Preparation
# ─────────────────────────────────────────────────────────────

def _window(df, stat):
    """Measured floor for `stat`, checked against round_bests.EXPECTED_FLOORS."""
    if stat not in EXPECTED_FLOORS:
        raise ValueError(
            f"no measured window for {stat!r}; round_bests.EXPECTED_FLOORS is "
            f"the single source for these floors, so add it there rather than "
            f"here, or the two modules disagree on what all-time means")
    floor = _measure_floor(df, stat)
    if floor != EXPECTED_FLOORS[stat]:
        raise ValueError(
            f"coverage floor for {stat} moved: measured {floor}, expected "
            f"{EXPECTED_FLOORS[stat]}. A moved floor changes which runs are "
            f"truncated and so changes every streak length in this file, under "
            f"wording that would not change. Re-measure and update "
            f"round_bests.EXPECTED_FLOORS.")
    return floor


def _streaks_for(df, stat, threshold, season):
    """All runs, the active subset, and the per-player best, for one pair.

    The frame is truncated at `season` before anything is computed, so the whole
    file is an "as at the end of season" snapshot. Without it a historical board
    reports the future: asked for 1995 an untruncated frame answered with Matt
    Rowell, who debuted in 2020, because his run ended on his latest appearance
    and that appearance was merely later than 1995 rather than in it.
    """
    floor = _window(df, stat)
    sub = df[(df['Season'] >= floor) & (df['Season'] <= season)].copy()
    v = pd.to_numeric(sub[stat], errors='coerce')
    sub = sub[v.notna()].copy()
    sub['_v'] = v[v.notna()]
    sub['_hit'] = sub['_v'] >= threshold

    runs = _runs(sub)
    if runs.empty:
        return floor, runs, runs, len(sub)

    last_app = sub.groupby('ID')['Date'].max()
    last_season = sub.groupby('ID')['Season'].max()
    runs['last_app'] = runs['ID'].map(last_app)
    # Active needs both halves: unbroken, meaning the run ends on his latest
    # appearance, and current, meaning that appearance falls in the reporting
    # season. The second test reads the Season column rather than the date's
    # calendar year, since Season is what every other filter in this repo uses.
    in_season = runs['ID'].map(last_season) == season
    active = runs[(runs['end'] == runs['last_app']) & in_season].copy()

    # All-time is one run per player, the longest, which is what "longest
    # streaks" means. Listing every run would fill the table with one player's
    # repeats.
    best = (runs.sort_values(['n', 'end'], ascending=[False, True])
                .drop_duplicates('ID'))
    return floor, active, best, len(sub)


def _decorate(df, rows, names, last_round):
    """Add name, clubs, missed-match disclosure and last-seen round."""
    out = []
    for r in rows.to_dict('records'):
        matches, missed = _missed_inside(df, r)
        pid = int(r['ID'])
        out.append({
            'who': fg._who(names.get(pid), pid),
            'clubs': ", ".join(r['clubs']),
            'n': int(r['n']),
            'start': r['start'].strftime('%Y-%m-%d'),
            'end': r['end'].strftime('%Y-%m-%d'),
            'matches': matches,
            'missed': missed,
            'last_seen': last_round.get(pid, "n/a"),
        })
    return out


def _write(lines, name, out_dir=DRAFTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


def _last_round_map(df, season):
    """ID to the display round of their most recent appearance in `season`."""
    s = df[df['Season'] == season]
    if s.empty:
        return {}
    last = s.sort_values('Date').groupby('ID').tail(1)
    out = {}
    for r in last.to_dict('records'):
        rn = pd.to_numeric(pd.Series([r['Round']]), errors='coerce').iloc[0]
        out[int(r['ID'])] = ("final" if pd.isna(rn)
                             else f"R{_display_round(int(rn), season)}")
    return out


def _header(L, prov, season):
    L.append(f"Source files: `{fg.ARCHIVE}` "
             f"({prov['archive_seasons'][0]}-{prov['archive_seasons'][1]}, "
             f"{prov['archive_rows']:,} rows), `{fg.MODERN}` "
             f"({prov['modern_seasons'][0]}-{prov['modern_seasons'][1]}, "
             f"{prov['modern_rows']:,} rows) and `{fg.CURRENT}` "
             f"({prov['current_seasons'][0]}-{prov['current_seasons'][1]}, "
             f"{prov['current_rows']:,} rows).")
    L.append("")
    L.append(f"The frame holds **{prov['games']:,} games** "
             f"({prov['ha_games']:,} home-and-away and {prov['finals_games']:,} "
             f"finals) over {prov['rows']:,} player-game rows, seasons "
             f"{prov['season_min']}-{prov['season_max']}.")
    L.append("")
    L.append(CONVENTION_NOTE)
    L.append("")
    L.append(AMBIGUITY_NOTE)
    L.append("")
    L.append(TRUNCATION_NOTE)
    L.append("")
    L.append(f"**The frame is truncated at {season}.** Everything here is a "
             f"snapshot as at the end of that season, so an all-time table "
             f"means longest through {season} and not longest ever recorded. "
             f"Without the truncation a historical board answers with the "
             f"future, since a run ending on a player's latest appearance is "
             f"unbroken whenever that appearance happens to fall.")
    L.append("")
    L.append(f"**No model output appears here.** No `Exp_Votes`, no vote claim "
             f"and no projection. A streak is a fact already true before the "
             f"first bounce, and whether it extends is not this module's "
             f"question.")
    L.append("")
    L.append("Players are keyed on `ID`, never on name, and each row prints the "
             "ID beside the name. Clubs are canonicalised through "
             "`club_aliases.canonical_club()`.")
    L.append("")


def _streak_table(L, rows, label, stat):
    L.append(f"| {label} | player | clubs | run | from | to | "
             f"club matches in span | missed | last seen |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        L.append("| " + " | ".join([
            str(i), r['who'], r['clubs'], str(r['n']), r['start'], r['end'],
            str(r['matches']), str(r['missed']), str(r['last_seen'])]) + " |")


# ─────────────────────────────────────────────────────────────
# Builder: one stat and threshold
# ─────────────────────────────────────────────────────────────

def build_stat_streaks(stat, threshold, season, top_n=10, out_dir=DRAFTS_DIR,
                       **kw):
    """Active and all-time streaks of clearing `threshold` of `stat`."""
    if top_n < 2:
        raise ValueError(
            f"top_n must be at least 2, got {top_n}: a superlative has to "
            f"print the table it came from")
    df, prov = fg.load_frame(**kw)
    names = df.drop_duplicates('ID').set_index('ID')['Player'].to_dict()
    last_round = _last_round_map(df, season)

    floor, active, best, comparable = _streaks_for(df, stat, threshold, season)

    act_rows = _decorate(df, active.nlargest(top_n, 'n'), names, last_round) \
        if len(active) else []
    all_rows = _decorate(df, best.nlargest(top_n, 'n'), names, last_round) \
        if len(best) else []

    L = [f"# {stat} {threshold}+ streaks, {season}", ""]
    L.append(f"Runs of consecutive appearances with at least {threshold} "
             f"{stat.lower()}, active and all-time. Comparable from {floor}, "
             f"over {comparable:,} player-games.")
    L.append("")
    _header(L, prov, season)

    L.append("## Active streaks")
    L.append("")
    if not act_rows:
        if season < floor:
            L.append(f"**Not comparable in {season}.** `{stat}` is only fully "
                     f"populated from {floor}, so no run can be measured in "
                     f"this season at all.")
        else:
            L.append(f"**No active run.** No player whose most recent "
                     f"appearance falls in {season} is on an unbroken run of "
                     f"{threshold:g}+ {stat.lower()}.")
    else:
        L.append(f"{_plural(len(active), 'run')} active, meaning the run ends "
                 f"on the player's most recent appearance and that appearance "
                 f"falls in {season}. Top {len(act_rows)} shown.")
        L.append("")
        _streak_table(L, act_rows, "#", stat)
    L.append("")

    L.append(f"## Longest since {floor}, through {season}")
    L.append("")
    L.append(f"One run per player, the longest, from {len(best):,} players who "
             f"have ever put two or more together. This is the table any "
             f"superlative above is drawn from.")
    L.append("")
    if all_rows:
        _streak_table(L, all_rows, "rank", stat)
    else:
        L.append("No run of any length.")
    L.append("")

    name = f"streaks_{fg._slug(stat)}_{threshold:g}_{season}"
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(active):,} active, {len(best):,} players "
          f"with a run, comparable from {floor})")
    for r in act_rows[:5]:
        print(f"   active {r['n']:>4d}  {r['who']} ({r['clubs']}), "
              f"missed {r['missed']} inside, last seen {r['last_seen']}")
    return out_path


# ─────────────────────────────────────────────────────────────
# Builder: the board
# ─────────────────────────────────────────────────────────────

def _clubs_now(df, season):
    """ID to the club they last played for in `season`."""
    s = df[df['Season'] == season]
    if s.empty:
        return {}
    last = s.sort_values(['ID', 'Date']).groupby('ID').tail(1)
    return {int(r['ID']): canonical_club(r['Playing.for'])
            for r in last.to_dict('records')}


def build_streak_board(season, pairs=None, top_n=3, clubs=None,
                       out_dir=DRAFTS_DIR, **kw):
    """The longest active run for each default pair, in one table.

    `clubs` filters the ACTIVE side to an iterable of canonical club names,
    which is how a single fixture's preview block is cut. The longest-on-record
    column is deliberately left unfiltered: it is there for scale, and scaling a
    club's run against that club's own history rather than against the record
    would make a modest run look like a landmark.
    """
    pairs = DEFAULT_PAIRS if pairs is None else list(pairs)
    df, prov = fg.load_frame(**kw)
    names = df.drop_duplicates('ID').set_index('ID')['Player'].to_dict()
    last_round = _last_round_map(df, season)
    scope = df[df['Season'] <= season]
    wanted = None if clubs is None else {canonical_club(c) for c in clubs}
    club_now = _clubs_now(df, season) if wanted is not None else {}

    blocks = []
    for stat, threshold in pairs:
        floor, active, best, comparable = _streaks_for(df, stat, threshold,
                                                       season)
        if wanted is not None and len(active):
            active = active[active['ID'].map(
                lambda i: club_now.get(int(i)) in wanted)]
        act_rows = _decorate(scope, active.nlargest(top_n, 'n'), names,
                             last_round) if len(active) else []
        all_rows = _decorate(scope, best.nlargest(1, 'n'), names,
                             last_round) if len(best) else []
        blocks.append({
            'stat': stat, 'threshold': threshold, 'floor': floor,
            'n_active': len(active), 'act': act_rows,
            'record': all_rows[0] if all_rows else None,
        })

    L = [f"# Active stat streaks, {season}", ""]
    L.append(f"The longest active run on each of {len(pairs)} thresholds, with "
             f"the longest on record beside it for scale. A streak changes "
             f"every "
             f"round by definition, since it either extends or breaks.")
    L.append("")
    _header(L, prov, season)

    if wanted is not None:
        L.append(f"**Active runs filtered to {', '.join(sorted(wanted))}**, on "
                 f"the club the player last turned out for in {season}. The "
                 f"longest-on-record column is NOT filtered: it is there for "
                 f"scale, and scaling a club's run against that club's own "
                 f"history rather than against the record would make a modest "
                 f"run look like a landmark.")
        L.append("")

    L.append("## Summary")
    L.append("")
    L.append("| threshold | longest active | player | missed inside | "
             "last seen | longest on record | since |")
    L.append("|---|---|---|---|---|---|---|")
    for b in blocks:
        lead = b['act'][0] if b['act'] else None
        rec = b['record']
        L.append("| " + " | ".join([
            f"{b['stat']} {b['threshold']}+",
            str(lead['n']) if lead else "none",
            lead['who'] if lead else "n/a",
            str(lead['missed']) if lead else "n/a",
            str(lead['last_seen']) if lead else "n/a",
            f"{rec['who']} {rec['n']}" if rec else "n/a",
            str(b['floor'])]) + " |")
    L.append("")

    for b in blocks:
        L.append(f"## {b['stat']} {b['threshold']}+")
        L.append("")
        if not b['act']:
            # A season before the floor has no data at all, which is a
            # different statement from a season where nobody is on a run.
            if season < b['floor']:
                L.append(f"**Not comparable in {season}.** `{b['stat']}` is "
                         f"only fully populated from {b['floor']}, so no run "
                         f"can be measured in this season at all.")
            else:
                L.append(f"**No active run.** Comparable from {b['floor']}, "
                         f"and no player whose most recent appearance falls in "
                         f"{season} is on an unbroken run.")
            L.append("")
            continue
        L.append(f"{_plural(b['n_active'], 'run')} active. Top "
                 f"{len(b['act'])} shown. Comparable from {b['floor']}.")
        L.append("")
        _streak_table(L, b['act'], "#", b['stat'])
        L.append("")
        if b['record']:
            r = b['record']
            L.append(f"Longest since {b['floor']} through {season}: "
                     f"**{r['n']}**, "
                     f"{r['who']} ({r['clubs']}), {r['start']} to {r['end']}, "
                     f"with {_plural(r['missed'], 'club match', 'club matches')}"
                     f" missed inside the run.")
            L.append("")

    # The club filter goes in the filename, so a fixture cut cannot overwrite
    # the full board. Same trap milestones.py records.
    name = f"streak_board_{season}"
    if wanted is not None:
        name += "_" + "_".join(fg._slug(c).replace('_', '')
                               for c in sorted(wanted))
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(pairs)} thresholds)")
    for b in blocks:
        lead = b['act'][0] if b['act'] else None
        print(f"   {b['stat']:>22s} {b['threshold']:<3d} active "
              + (f"{lead['n']:>3d}  {lead['who']} (missed {lead['missed']}, "
                 f"last {lead['last_seen']})" if lead else "none"))
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_USAGE = ("usage: python stat_streaks.py board <season>\n"
          "       python stat_streaks.py <stat> <threshold> <season> [top_n]\n"
          "  stat: " + " | ".join(sorted(EXPECTED_FLOORS)))


def main(argv):
    if not argv:
        print(_USAGE, file=sys.stderr)
        return 2
    if argv[0] == 'board':
        if len(argv) != 2:
            print(_USAGE, file=sys.stderr)
            return 2
        try:
            season = int(argv[1])
        except ValueError:
            print(f"season must be an integer, got {argv[1]!r}",
                  file=sys.stderr)
            return 2
        build_streak_board(season)
        return 0

    if len(argv) not in (3, 4):
        print(_USAGE, file=sys.stderr)
        return 2
    stat = argv[0]
    if stat not in EXPECTED_FLOORS:
        print(f"unknown stat {stat!r}, expected one of "
              f"{', '.join(sorted(EXPECTED_FLOORS))}", file=sys.stderr)
        return 2
    try:
        threshold, season = float(argv[1]), int(argv[2])
    except ValueError:
        print(f"threshold and season must be numbers, got {argv[1]!r} and "
              f"{argv[2]!r}", file=sys.stderr)
        return 2
    if threshold <= 0:
        print(f"threshold must be positive, got {threshold:g}", file=sys.stderr)
        return 2
    top_n = 10
    if len(argv) == 4:
        try:
            top_n = int(argv[3])
        except ValueError:
            print(f"top_n must be an integer, got {argv[3]!r}", file=sys.stderr)
            return 2
        if top_n < 2:
            print(f"top_n must be at least 2, got {top_n}", file=sys.stderr)
            return 2
    build_stat_streaks(stat, threshold, season, top_n=top_n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
