"""Round bests with an all-time rank, 1965-2026.

    build_round_bests(season, raw_round)

For one round: the best single-game figure in each stat, and where that figure
sits among every player-game the archive holds. The ranking is the point. A
round leaderboard is a stats page; a round leaderboard that says the figure is
the 47th best since 1976 is a post.

RECON / DRAFT OUTPUT ONLY. Like club_aliases, all_time_tables, fewest_games and
milestones, this module must not be imported by features.py, brownlow_model.py
or predict_2026.py: it canonicalises club strings, which would change the
model's feature space without a retrain.

A per-game record is not censored
---------------------------------
This is the one eligibility question here, and its answer is the opposite of
the career modules'.

`fewest_games.py` and `milestones.py` both rank career totals, so both have to
ask what a player did before the archive starts. A career total is short by
exactly the games no source records, and both modules exclude the affected
players.

A single game's figure has no such problem. Tom Mitchell's 54 disposals is 54
whether or not his earlier seasons are in the file, and it is comparable to
every other single game on record. There is no per-player eligibility test in
this module at all, and no `Career.Games` offset test, because nothing here
accumulates.

What IS limited is the comparison set
-------------------------------------
The denominator is limited instead, and per stat rather than per player. A
column that is all-null before 1987 cannot contribute a comparison from 1986,
so "all-time" means "since this column was completely populated" and that
season differs by stat. Tackles compare against 1987 on, clearances against
1998 on, goals against the whole 1965-2026 frame.

Every rank in this file therefore carries its own window and its own
denominator, stated per stat rather than once at the top, because a single
top-of-file window would be wrong for thirteen of the fourteen stats.

The floors are measured in the run, not read from a table
---------------------------------------------------------
Each stat's floor is computed here, every run, as the first season from which
the column is non-null on every row with no later gap. It is then checked
against `EXPECTED_FLOORS` and a disagreement raises rather than prints.

That check matters more than it looks. A floor moving is not a cosmetic
difference: it changes the denominator, and so silently changes the meaning of
every rank in the file. A backfill that populated tackles from 1980 would make
this run's "12th since 1987" and last run's "12th since 1987" two different
claims under one sentence. The run stops instead.

Ties and repeat entries
-----------------------
The ranked tables list performances, not players, so one player appears twice
where he has done it twice. Rank is `1 + the count of strictly better
performances`, so equal figures share a rank rather than being ordered
arbitrarily, and the count of equal performances is reported beside it.

All matches, home-and-away and finals
-------------------------------------
A single-game figure is neither a rate nor an appearance record, so the finals
rule in `project_brief.md` does not decide it. Finals are included: a record is
a record whenever it was set, and Brodie Grundy's 73 hit-outs in the 2019
preliminary final belongs in the hit-outs table. 2026 contributes
home-and-away games only, since `predictions/game_level_2026.csv` carries no
finals.

Rarity comes free
-----------------
The rank is computed from a count of performances at or above the figure, so
that count is reported. It is the signal a rare-lines format would be built
from: a figure reached 4 times in 389,376 player-games is a post on its own,
and one reached 3,000 times is not.

Player identity is keyed on `ID`, never name, and every output row prints the ID
beside the name.
"""

import os
import sys

import pandas as pd

import fewest_games as fg
from club_aliases import canonical_club
# Imported rather than copied, for the reason milestones.py records: CLAUDE.md
# already tracks three copies of this and a fourth makes that worse.
from draft_posts import _display_round

DRAFTS_DIR = "drafts"

# The stats ranked, in the order they appear in the output. Stored columns only.
#
# Clangers is deliberately absent. It is complete from 1998 and would rank
# cleanly, but a "round best" for a stat where high is bad inverts the whole
# frame of the post, and the ladder has no reading that is not a pile-on.
#
# Score_Involvements is also absent, and for a different reason. It is
# engineered by features.add_row_stats() rather than stored, so its "record"
# is a number this repo invented and no reader recognises. A record only works
# as a record when it is the same quantity the rest of the world counts.
STATS = ['Disposals', 'Kicks', 'Handballs', 'Marks', 'Goals', 'Tackles',
         'Hit.Outs', 'Clearances', 'Contested.Possessions', 'Inside.50s',
         'Marks.Inside.50', 'One.Percenters', 'Goal.Assists', 'Rebounds']

# The floor each stat is expected to measure at, with the evidence. Measured
# across all three sources as the first season from which the column is non-null
# on every row with no later gap. Checked every run; a disagreement raises,
# because a moved floor redefines every rank in the file under unchanged
# wording.
EXPECTED_FLOORS = {
    'Disposals': 1976,
    'Kicks': 1976,
    'Handballs': 1976,
    'Marks': 1976,
    'Goals': 1965,
    'Tackles': 1987,
    'Hit.Outs': 1979,
    'Clearances': 1998,
    'Contested.Possessions': 1999,
    'Inside.50s': 1998,
    'Marks.Inside.50': 1999,
    'One.Percenters': 1999,
    'Goal.Assists': 2003,
    'Rebounds': 1998,
}

# Four stats poll a value earlier than their floor and then break, which is why
# a floor is "first season with unbroken full coverage" rather than "first
# season populated". Carried as copy so each stat's window can explain itself.
FLOOR_NOTES = {
    'Disposals': "populated from 1965 but 1975 is only 96% non-null",
    'Kicks': "populated from 1965 but 1975 is only 96% non-null",
    'Handballs': "populated from 1965 but 1975 is only 96% non-null",
    'Marks': "populated from 1965 but 1975 is only 96% non-null",
    'Goals': "non-null on every row from the start of the data",
    'Tackles': "all-null 1965-1986",
    'Hit.Outs': "first polls in 1966 then collapses repeatedly, worst at 1974 "
                "where only 7% of rows are non-null",
    'Clearances': "all-null 1965-1997",
    'Contested.Possessions': "all-null 1965-1998",
    'Inside.50s': "all-null 1965-1997",
    'Marks.Inside.50': "all-null 1965-1998",
    'One.Percenters': "all-null 1965-1998",
    'Goal.Assists': "all-null 1965-2002",
    'Rebounds': "all-null 1965-1997",
}

NOT_CENSORED_NOTE = (
    "**A single-game figure is not censored.** Unlike a career total, it does "
    "not depend on how much of a player's career this archive holds, so there "
    "is no per-player eligibility test in this file and no `Career.Games` "
    "offset test. What is limited is the comparison set, per stat rather than "
    "per player: a column that is all-null before a given season cannot "
    "contribute a comparison from before it."
)

FINALS_NOTE = (
    "**All matches, home-and-away and finals.** A single-game figure is "
    "neither a rate nor an appearance record, so the finals rule does not "
    "decide it, and a record is a record whenever it was set. 2026 "
    "contributes home-and-away games only, since "
    "`predictions/game_level_2026.csv` carries no finals."
)

TABLE_NOTE = (
    "**The ranked tables list performances, not players.** A player who has "
    "produced the figure twice appears twice. Rank is one plus the count of "
    "strictly better performances, so equal figures share a rank rather than "
    "being ordered arbitrarily."
)


# ─────────────────────────────────────────────────────────────
# Windows
# ─────────────────────────────────────────────────────────────

def _measure_floor(df, stat):
    """First season from which `stat` is non-null on every row, with no gap."""
    v = pd.to_numeric(df[stat], errors='coerce')
    per = v.groupby(df['Season']).agg(n='size', nn='count')
    full = (per['nn'] / per['n']) >= 1.0
    for season in sorted(per.index):
        if full.loc[season:].all():
            return int(season)
    return None


def _windows(df):
    """Measured floor and comparable row count per stat, checked against
    EXPECTED_FLOORS."""
    out = {}
    drift = []
    for stat in STATS:
        if stat not in df.columns:
            raise ValueError(
                f"stat column {stat!r} absent from the concatenated frame, so "
                f"its ranking would be computed over nothing")
        floor = _measure_floor(df, stat)
        expected = EXPECTED_FLOORS[stat]
        if floor != expected:
            drift.append(f"{stat}: measured {floor}, expected {expected}")
        rows = int((df['Season'] >= floor).sum()) if floor else 0
        out[stat] = {'floor': floor, 'rows': rows}
    if drift:
        raise ValueError(
            "coverage floor(s) moved since EXPECTED_FLOORS was written: "
            + "; ".join(drift)
            + ". A moved floor changes the denominator and so changes what "
              "every rank in this file means, under wording that would not "
              "change. Re-measure, confirm the source revision is intended, "
              "then update EXPECTED_FLOORS and FLOOR_NOTES together.")
    return out


# ─────────────────────────────────────────────────────────────
# Ranking
# ─────────────────────────────────────────────────────────────

def _comparable(df, stat, floor):
    """Every player-game the rank is computed over, with the value coerced."""
    sub = df[df['Season'] >= floor].copy()
    sub['v'] = pd.to_numeric(sub[stat], errors='coerce')
    return sub[sub['v'].notna()]


def _rank_of(values, x):
    """Rank, count strictly better, count equal. Ties share a rank."""
    better = int((values > x).sum())
    equal = int((values == x).sum())
    return better + 1, better, equal


def _opponent(row):
    """The club on the other side, canonicalised.

    Home.Away is read first because Playing.for and Home.team/Away.team do not
    always spell a club the same way (Footscray against Western Bulldogs, GWS
    against Greater Western Sydney).
    """
    home = canonical_club(row.get('Home.team'))
    away = canonical_club(row.get('Away.team'))
    side = row.get('Home.Away')
    if side == 'Home':
        return away
    if side == 'Away':
        return home
    club = canonical_club(row.get('Playing.for'))
    if club == home:
        return away
    if club == away:
        return home
    return "unknown"


def _round_label(row):
    """Season and round as it should read, finals keeping their string label."""
    rn = pd.to_numeric(pd.Series([row['Round']]), errors='coerce').iloc[0]
    season = int(row['Season'])
    if pd.isna(rn):
        return f"{season} {row['Round']}"
    return f"{season} R{_display_round(int(rn), season)}"


def _write(lines, name, out_dir=DRAFTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


def _plural(n, singular, plural=None):
    word = singular if n == 1 else (plural or singular + "s")
    return f"{n:,} {word}"


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n:,}{suffix}"


# ─────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────

def build_round_bests(season, round_num, stats=None, top_n=10, round_top=5,
                      out_dir=DRAFTS_DIR, **kw):
    """The round's best figure in each stat, with its all-time rank."""
    stats = STATS if stats is None else list(stats)
    unknown = [s for s in stats if s not in EXPECTED_FLOORS]
    if unknown:
        raise ValueError(
            f"no measured window for {unknown}; add to EXPECTED_FLOORS and "
            f"FLOOR_NOTES together, since a stat with no floor has no "
            f"denominator and so no rank")
    if top_n < 2:
        raise ValueError(
            f"top_n must be at least 2, got {top_n}: a superlative has to "
            f"print the table it came from, and a one-row table is the claim "
            f"restated rather than the evidence for it")

    df, prov = fg.load_frame(**kw)
    win = _windows(df)

    rn_all = pd.to_numeric(df['Round'], errors='coerce')
    this_round = df[(df['Season'] == season) & (rn_all == round_num)].copy()
    if this_round.empty:
        raise ValueError(
            f"no rows for season {season} raw Round {round_num}. Rounds "
            f"present for {season}: "
            f"{sorted(rn_all[df['Season'] == season].dropna().astype(int).unique())}")
    round_games = len(this_round.drop_duplicates(subset=fg._GAME_KEY))
    disp = _display_round(round_num, season)

    sections = []
    headline = []
    for stat in stats:
        floor = win[stat]['floor']
        if season < floor:
            sections.append((stat, None))
            continue

        allv = _comparable(df, stat, floor)
        here = this_round.copy()
        here['v'] = pd.to_numeric(here[stat], errors='coerce')
        here = here[here['v'].notna()]
        if here.empty:
            sections.append((stat, None))
            continue

        best = float(here['v'].max())
        leaders = here[here['v'] == best]
        rank, better, equal = _rank_of(allv['v'], best)

        rows_round = []
        for r in here.nlargest(round_top, 'v').to_dict('records'):
            rows_round.append({
                'who': fg._who(r['Player'], r['ID']),
                'club': canonical_club(r['Playing.for']),
                'opp': _opponent(r),
                'v': float(r['v']),
            })

        # Marks every row drawn from the round being reported, whether it
        # reached the table on its own or was appended below it. Set on the
        # frame rather than recomputed per row, so a row is identified by its
        # index and not by re-matching season and round.
        allv = allv.assign(_here=allv.index.isin(this_round.index))

        def _all_row(r, appended=False):
            r_rank, _, _ = _rank_of(allv['v'], float(r['v']))
            return {
                'rank': r_rank,
                'who': fg._who(r['Player'], r['ID']),
                'club': canonical_club(r['Playing.for']),
                'when': _round_label(r),
                'v': float(r['v']),
                'is_here': bool(r.get('_here', False)) or appended,
                'appended': appended,
            }

        top = allv.nlargest(top_n, 'v')
        rows_all = [_all_row(r) for r in top.to_dict('records')]
        # The numerically largest rank in the top-N block, which is the cut
        # line. Rank 1 is best, so this is max and not min: taking min here
        # returns 1 every time and makes every round best look like a tie.
        worst_shown = max((x['rank'] for x in rows_all), default=0)

        # nlargest cuts by value alone, so a tie sitting on the cut line is
        # truncated arbitrarily and the round's own performance can be missing
        # from a table it is level with. Append it rather than drop it: a reader
        # told the figure ranks 6th and shown a table without it has been given
        # the claim and not the evidence. Matched on index, not on name, since
        # the same player can hold two entries.
        missing = leaders.loc[[i for i in leaders.index
                               if i not in set(top.index)]]
        rows_all += [_all_row(r, appended=True)
                     for r in missing.to_dict('records')]

        sections.append((stat, {
            'floor': floor, 'rows': win[stat]['rows'],
            'best': best, 'leaders': leaders, 'rank': rank,
            'better': better, 'equal': equal,
            'round_rows': rows_round, 'all_rows': rows_all,
            'top_n_shown': len(top), 'appended': len(missing),
            'worst_shown': worst_shown,
        }))
        headline.append((stat, best, rank, allv['v'].shape[0], floor,
                         rows_round[0]['who'] if rows_round else "?"))

    L = [f"# Round bests with an all-time rank, Round {disp} {season}", ""]
    L.append(f"The best single-game figure in each of {len(stats)} stats in "
             f"Round {disp} of {season} (AFLTables raw Round {round_num}), and "
             f"where that figure sits among every player-game on record. The "
             f"round held {_plural(round_games, 'game')}.")
    L.append("")
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
    L.append(NOT_CENSORED_NOTE)
    L.append("")
    L.append("**Every rank below carries its own window and its own "
             "denominator**, stated per stat rather than once here, because a "
             "single top-of-file window would be wrong for "
             f"{len(stats) - 1} of the {len(stats)} stats. Each floor is "
             "measured in this run as the first season from which the column "
             "is non-null on every row with no later gap, and checked against "
             "the value recorded in the module; a disagreement stops the run "
             "rather than printing, because a moved floor changes what every "
             "rank here means without changing a word of the wording.")
    L.append("")
    L.append(FINALS_NOTE)
    L.append("")
    L.append(TABLE_NOTE)
    L.append("")
    L.append("Players are keyed on `ID`, never on name, and each row prints the "
             "ID beside the name. Clubs are canonicalised through "
             "`club_aliases.canonical_club()`. Round numbers shown for past "
             "seasons are AFL display rounds; finals keep their label.")
    L.append("")

    L.append("## Summary")
    L.append("")
    L.append("| stat | round best | player | all-time rank | of | since |")
    L.append("|---|---|---|---|---|---|")
    for stat, best, rank, n, floor, who in headline:
        L.append("| " + " | ".join([
            stat, f"{best:g}", who, _ordinal(rank), f"{n:,}", str(floor)])
            + " |")
    L.append("")

    for stat, s in sections:
        L.append(f"## {stat}")
        L.append("")
        if s is None:
            L.append(f"No comparable data. `{stat}` is not populated for "
                     f"{season} or the round carries no non-null value for it, "
                     f"so no figure is ranked. Floor season "
                     f"{win[stat]['floor']}.")
            L.append("")
            continue

        names = ", ".join(fg._who(r['Player'], r['ID'])
                          for r in s['leaders'].to_dict('records'))
        L.append(f"**Round best: {s['best']:g}**, {names}.")
        L.append("")
        L.append(f"That figure ranks {_ordinal(s['rank'])} of "
                 f"{s['rows']:,} comparable player-games, seasons {s['floor']}-"
                 f"{prov['season_max']}. {_plural(s['better'], 'performance')} "
                 f"{'has' if s['better'] == 1 else 'have'} bettered it and "
                 f"{_plural(s['equal'] - 1, 'other performance')} "
                 f"{'has' if s['equal'] - 1 == 1 else 'have'} equalled it, so "
                 f"the figure or better has been reached "
                 f"{_plural(s['better'] + s['equal'], 'time')} in total.")
        L.append("")
        L.append(f"Window: `{stat}` is comparable from {s['floor']}, "
                 f"{FLOOR_NOTES[stat]}.")
        L.append("")
        L.append(f"Top {len(s['round_rows'])} in Round {disp}.")
        L.append("")
        L.append("| # | player | club | opponent | " + stat.lower() + " |")
        L.append("|---|---|---|---|---|")
        for i, r in enumerate(s['round_rows'], 1):
            L.append("| " + " | ".join([
                str(i), r['who'], str(r['club']), str(r['opp']),
                f"{r['v']:g}"]) + " |")
        L.append("")
        L.append(f"All-time top {s['top_n_shown']} since {s['floor']}, from "
                 f"{s['rows']:,} comparable player-games. This is the table the "
                 f"rank above is drawn from.")
        L.append("")
        L.append("| rank | player | club | when | " + stat.lower() + " |")
        L.append("|---|---|---|---|---|")
        for r in s['all_rows']:
            mark = " **(this round)**" if r['is_here'] else ""
            L.append("| " + " | ".join([
                _ordinal(r['rank']), r['who'] + mark, str(r['club']),
                r['when'], f"{r['v']:g}"]) + " |")
        L.append("")
        if s['appended']:
            added = ("The round's own entry is added" if s['appended'] == 1
                     else f"The round's {s['appended']} tied entries are added")
            # rank 1 is best, so the round best is inside the shown band when
            # its rank is at or above the cut line numerically.
            if s['rank'] <= s['worst_shown']:
                L.append(f"{added} below the top {s['top_n_shown']}, having "
                         f"been cut from it. The figure is **level on "
                         f"{s['best']:g}** with entries already in the table "
                         f"and ties at {_ordinal(s['rank'])}: the cut is made "
                         f"on value alone, so which of the tied performances "
                         f"filled the last places is arbitrary. Read it as a "
                         f"tie, not as a near miss.")
            else:
                L.append(f"{added} below the top {s['top_n_shown']}, which it "
                         f"does not reach: it sits at {_ordinal(s['rank'])}, "
                         f"against {_ordinal(s['worst_shown'])} at the cut "
                         f"line.")
            L.append("")

    name = f"round_bests_{season}_r{disp}"
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(headline)} of {len(stats)} stats ranked, "
          f"Round {disp} {season}, raw Round {round_num}, "
          f"{round_games} games)")
    for stat, best, rank, n, floor, who in headline:
        print(f"   {stat:24s} {best:>6g}  {_ordinal(rank):>9s} of {n:>8,} "
              f"since {floor}  {who}")
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_USAGE = ("usage: python round_bests.py <season> <raw_round> [top_n]\n"
          "  raw_round is the AFLTables Round_num, not the AFL round number")


def main(argv):
    if len(argv) not in (2, 3):
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        season, round_num = int(argv[0]), int(argv[1])
    except ValueError:
        print(f"season and raw_round must be integers, got {argv[0]!r} and "
              f"{argv[1]!r}", file=sys.stderr)
        return 2
    top_n = 10
    if len(argv) == 3:
        try:
            top_n = int(argv[2])
        except ValueError:
            print(f"top_n must be an integer, got {argv[2]!r}", file=sys.stderr)
            return 2
        if top_n < 2:
            print(f"top_n must be at least 2, got {top_n}", file=sys.stderr)
            return 2
    build_round_bests(season, round_num, top_n=top_n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
