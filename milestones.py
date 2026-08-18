"""Career milestones passed and approaching, 1965-2026.

    build_milestones_passed(season, round_num)   the round just played
    build_milestones_upcoming(season)            the round about to be played

Two tables from one frame. The first is a result post: every career milestone
crossed in a given round, with the game it was crossed in. The second is a
preview: every active player whose next milestone is within one game's reach,
with the exact number still required.

RECON / DRAFT OUTPUT ONLY. Like club_aliases, all_time_tables and fewest_games,
this module must not be imported by features.py, brownlow_model.py or
predict_2026.py: it canonicalises club strings, which would change the model's
feature space without a retrain.

Preview safety
--------------
Nothing here is model output. There is no Exp_Votes, no vote claim and no
forward projection of any kind. Every figure in the upcoming table is a fact
that is already true before the first bounce: a career total, a gap to the next
rung, and the player's own season figures to date. The gap is arithmetic, not a
forecast, and the header says so. A reader decides whether the gap is reachable;
this module never does.

The two eligibility rules, and why they differ
----------------------------------------------
A games milestone and a stat milestone are censored differently, so they are
tested differently.

`Career.Games` is AFLTables' own career counter and it carries games played
before this data begins. Ted Whitten sits at 248 in a 1965 row, and Kevin Murray
first appears in 1967 already at 167. A games milestone is therefore exact for a
pre-1965 debutant, where a cumulative count over these rows would be short by
however many games the archive never saw.

A stat total has no such counter. It is summed over the rows present, so it is
truncated by exactly those unseen games, and a player who has any is excluded.

Zero is a missing value in `Career.Games`, not a count
------------------------------------------------------
145 rows across 61 players carry `Career.Games` of 0 in the middle of a career:
Darryl White reads 0 in 1992 R23 and 20 in the following game. Read literally,
the counter looks non-monotonic on 60 players and worthless. Read with 0 as
missing, it is exactly consistent on every player in the frame.

That is measured rather than asserted. Let n be a player's row index in this
frame, ordered by date, and cg their non-zero `Career.Games`. The offset cg - n
is constant across every one of the 6,038 players who carry the column at all;
zero players hold two different offsets. One player, ID 372, carries 0 on all 38
of his rows and so has no counter to read.

The offset IS the censoring, per player
---------------------------------------
Because the offset is constant, it is not a curiosity. It is the number of games
the player played before this frame's coverage begins, measured for that player
rather than inferred from a debut season:

    games_played = row_index + offset

An offset of 0 means the whole career is present and a stat total is complete.
An offset above 0 means the stat total is short by that many games and the
player is excluded from every stat ladder, while still ranking correctly on the
games ladder. 328 players carry a positive offset. Only 18 of them first appear
after 1965, which is why a debut-season rule catches most of this and not all of
it.

This is strictly sharper than the left-censoring rule in `fewest_games.py`,
which excludes every player whose first game falls in 1965. That rule is
directionally right and blunt in both directions: it drops 118 players who
genuinely debuted in 1965 and carry offset 0, and it cannot see the 18 later
debutants who carry a positive offset. `fewest_games.py` is deliberately left
alone here, since changing its eligibility would move published tables. The
difference is recorded so the two are not mistaken for the same test.

Per-stat coverage still applies
-------------------------------
Offset 0 says no game is missing from the frame. It does not say every game
present carries a value for the stat. Tackles are all-null before 1987 whatever
a player's offset is, so the stat ladders also run `fewest_games._coverage_mask`
over the raw frame, before `features.add_row_stats()` can turn a missing input
into a legitimate-looking zero. Both exclusions are counted in every header.

Shared loader
-------------
The frame comes from `fewest_games.load_frame()`, unchanged, so the two modules
cannot drift on which files they read, which rows they drop or how the game key
is built. All matches are counted, home-and-away and finals, because this counts
appearances rather than rates. 2026 contributes home-and-away games only, since
`predictions/game_level_2026.csv` carries no finals.

Player identity is keyed on `ID`, never name, and every output row prints the ID
beside the name.
"""

import os
import sys

import pandas as pd

import fewest_games as fg
from club_aliases import canonical_club
# Imported rather than copied. CLAUDE.md records that _display_round already
# exists in three places (dashboard.py, draft_posts.py, streaks.py) and that
# changing one means changing all three; a fourth copy makes that worse.
# draft_posts.py imports only os/re/shutil/sys/datetime/pandas and runs nothing
# at module level, so it is safe to import, which dashboard.py is not.
from draft_posts import _display_round

DRAFTS_DIR = "drafts"

# ─────────────────────────────────────────────────────────────
# The ladders
# ─────────────────────────────────────────────────────────────

# A milestone is a rung on a repeating ladder rather than one chosen number.
# That is deliberate: it sidesteps the open question in the fewest-games work,
# where seven of ten stats have no obvious single round number to aim at. A
# ladder needs a step, and a step is a house convention rather than a claim.
#
# 'Games' is not a stat column. It reads Career.Games and is the only ladder
# valid for a player with a positive offset.
#
# The reach column counts how many players in the frame have ever reached the
# ladder's first rung, measured at build time and printed in the header, so a
# step that turns out to fire every week or never can be seen rather than
# guessed at.
LADDERS = {
    'Games':     {'step': 50,   'first': 50,   'unit': 'games'},
    'Goals':     {'step': 100,  'first': 100,  'unit': 'goals'},
    'Disposals': {'step': 1000, 'first': 1000, 'unit': 'disposals'},
    'Tackles':   {'step': 250,  'first': 250,  'unit': 'tackles'},
    'Marks':     {'step': 500,  'first': 500,  'unit': 'marks'},
}

GAMES_LADDER = 'Games'

# Measured across all three sources, per season, as the first season from which
# the column is non-null on every row with no later gap. Reported as a
# diagnostic only: the per-player coverage test supersedes it, exactly as in
# fewest_games.py. Goals is complete on every row from 1965.
STAT_FLOORS = {
    'Goals': (1965, "non-null on every row from the start of the data"),
    'Disposals': (1976, "populated from 1965 but 1975 is only 96% non-null, "
                        "so unbroken coverage starts 1976"),
    'Marks': (1976, "populated from 1965 but 1975 is only 96% non-null, so "
                    "unbroken coverage starts 1976"),
    'Tackles': (1987, "all-null 1965-1986, fully populated from 1987"),
}

# Total home-and-away rounds in the AFLTables numbering for each season, used
# only to say how many rounds are left when the upcoming table is built. 2026
# runs raw Rounds 1-25, an Opening Round plus official Rounds 1-24. Recorded in
# CLAUDE.md under "Round numbering".
HA_ROUNDS = {2026: 25}

CENSORING_NOTE = (
    "**Career totals are censored at the near end.** Any player still active "
    "has an unfinished count, so a total here is a total to date and not a "
    "final one."
)

GAMES_RULE = (
    "**Games are not censored at the far end.** `Career.Games` is AFLTables' "
    "own inclusive career counter and it carries games played before this data "
    "begins, so a games milestone is exact for a player who debuted before "
    "1965. A cumulative count over these rows would be short by exactly the "
    "games the archive never saw."
)

STAT_RULE = (
    "**Stat totals are censored at the far end, and the censoring is measured "
    "per player.** A stat total is summed over the rows present, so it is short "
    "by however many career games precede this frame. That number is the "
    "player's `Career.Games` offset, and any player whose offset is above 0 is "
    "excluded from the stat ladders rather than ranked on a truncated total."
)

ZERO_SENTINEL_NOTE = (
    "**`Career.Games` of 0 is a missing value, not a count.** 145 rows across "
    "61 players carry 0 mid-career. Read literally the counter is "
    "non-monotonic on 60 players; read with 0 as missing it is exactly "
    "consistent, with a constant offset for every player who carries the "
    "column at all and no player holding two."
)

_GAME_KEY = fg._GAME_KEY


# ─────────────────────────────────────────────────────────────
# Career positions
# ─────────────────────────────────────────────────────────────

def _career_positions(df, prov):
    """Add row index, per-player Career.Games offset and true games played.

    Sorted on ID and Date alone. Date fully orders a career, since no player
    appears twice on one date, and the mixed Round column (strings in the two
    archives, integers in the 2026 file) is not safe to sort on after the
    concat.
    """
    d = df.sort_values(['ID', 'Date'], kind='mergesort').reset_index(drop=True)

    cg = pd.to_numeric(d['Career.Games'], errors='coerce')
    # 0 is the sentinel, so it is nulled BEFORE the offset is derived. Left in,
    # it manufactures a fake offset for that row and breaks the constancy test
    # the whole eligibility rule rests on.
    d['cg'] = cg.where(cg > 0)
    d['n'] = d.groupby('ID').cumcount() + 1

    off = d['cg'] - d['n']
    agg = off.groupby(d['ID']).agg(['nunique', 'max', 'count'])

    no_counter = set(agg.index[agg['count'] == 0])
    inconsistent = set(agg.index[agg['nunique'] > 1])
    prov['cg_no_counter'] = len(no_counter)
    prov['cg_inconsistent'] = len(inconsistent)
    prov['cg_zero_rows'] = int((cg == 0).sum())
    prov['cg_zero_players'] = int(d.loc[cg == 0, 'ID'].nunique())

    readable = agg[(agg['count'] > 0) & (agg['nunique'] == 1)]
    offset = readable['max'].astype(int)
    prov['cg_offset_positive'] = int((offset > 0).sum())
    prov['cg_offset_zero'] = int((offset == 0).sum())

    d['offset'] = d['ID'].map(offset)
    # games_played rather than the raw column: it fills the zero-sentinel holes
    # from the offset instead of reading them as a career reset.
    d['games_played'] = d['n'] + d['offset']
    return d, offset


def _opponent(row):
    """The club on the other side, canonicalised.

    Home.Away is read first because Playing.for and Home.team/Away.team do not
    always spell a club the same way (Footscray against Western Bulldogs, GWS
    against Greater Western Sydney). Comparing canonical strings is the fallback
    for a row where Home.Away is missing.
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


def _rungs_crossed(before, after, first, step):
    """Every ladder rung strictly above `before` and at or below `after`."""
    if after < first:
        return []
    lo = max(first, (int(before // step) + 1) * step)
    if before < first:
        lo = first
    return list(range(int(lo), int(after) + 1, int(step)))


def _next_rung(total, first, step):
    if total < first:
        return first
    return (int(total // step) + 1) * step


# ─────────────────────────────────────────────────────────────
# Eligibility
# ─────────────────────────────────────────────────────────────

def _eligible_for_stat(df, positions, offset, stat, prov):
    """IDs whose total for `stat` is complete: offset 0 and full coverage.

    The coverage test runs on the raw frame, before features.add_row_stats()
    coerces a missing input to 0, so a gap is caught as a gap rather than
    counted as a legitimate zero.
    """
    covered = fg._coverage_mask(df, stat)
    per = (df.assign(_cov=covered)
             .groupby('ID')['_cov'].agg(games='size', covered='sum'))
    incomplete = set(per.index[per['covered'] < per['games']])

    censored = set(offset.index[offset > 0])
    unreadable = set(positions['ID'].unique()) - set(offset.index)

    excluded = incomplete | censored | unreadable
    eligible = set(per.index) - excluded

    prov[f'{stat}_exc_coverage'] = len(incomplete)
    prov[f'{stat}_exc_censored'] = len(censored)
    prov[f'{stat}_exc_unreadable'] = len(unreadable)
    prov[f'{stat}_eligible'] = len(eligible)
    return eligible


def _stat_totals(positions, stat, eligible):
    """Per-appearance value and running career total, eligible players only."""
    w = positions[positions['ID'].isin(eligible)].copy()
    w['statval'] = pd.to_numeric(w[stat], errors='coerce').fillna(0.0)
    w['cumval'] = w.groupby('ID')['statval'].cumsum()
    w['before'] = w['cumval'] - w['statval']
    return w


# ─────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────

def _clubs_now(positions, season):
    """ID to the club they played for most recently in `season`."""
    s = positions[positions['Season'] == season]
    last = s.sort_values(['ID', 'Date']).groupby('ID').tail(1)
    return dict(zip(last['ID'], last['Playing.for'].map(canonical_club)))


def _sources_line(prov):
    return (f"Source files: `{fg.ARCHIVE}` "
            f"({prov['archive_seasons'][0]}-{prov['archive_seasons'][1]}, "
            f"{prov['archive_rows']:,} rows), `{fg.MODERN}` "
            f"({prov['modern_seasons'][0]}-{prov['modern_seasons'][1]}, "
            f"{prov['modern_rows']:,} rows) and `{fg.CURRENT}` "
            f"({prov['current_seasons'][0]}-{prov['current_seasons'][1]}, "
            f"{prov['current_rows']:,} rows).")


def _frame_line(prov):
    return (f"**All matches, home-and-away and finals**, because this counts "
            f"appearances rather than rates. The frame holds "
            f"**{prov['games']:,} games** ({prov['ha_games']:,} home-and-away "
            f"and {prov['finals_games']:,} finals) over {prov['rows']:,} "
            f"player-game rows, seasons {prov['season_min']}-"
            f"{prov['season_max']}, {prov['players']:,} players.")


def _plural(n, singular, plural=None):
    """Count and noun, agreeing. Written out because these counts reach copy."""
    word = singular if n == 1 else (plural or singular + "s")
    return f"{n:,} {word}"


def _counter_lines(prov):
    unreadable = prov['cg_no_counter'] + prov['cg_inconsistent']
    return [
        ZERO_SENTINEL_NOTE,
        "",
        f"In this frame that is {_plural(prov['cg_zero_rows'], 'zero row')} "
        f"across {_plural(prov['cg_zero_players'], 'player')}. After nulling "
        f"them, {_plural(prov['cg_offset_zero'], 'player')} carry offset 0 and "
        f"{prov['cg_offset_positive']:,} carry a positive offset. "
        f"{_plural(prov['cg_no_counter'], 'player has', 'players have')} no "
        f"readable counter at all and "
        f"{_plural(prov['cg_inconsistent'], 'holds', 'hold')} two different "
        f"offsets, so {_plural(unreadable, 'player is', 'players are')} "
        f"excluded from every ladder on the counter alone.",
    ]


def _ladder_line(stat, spec, reached):
    if stat == GAMES_LADDER:
        what = "`Career.Games`"
    else:
        floor, why = STAT_FLOORS[stat]
        what = f"`{stat}` (floor season {floor}, diagnostic only: {why})"
    return (f"- **{stat}**: every {spec['step']:,} from {spec['first']:,} "
            f"{spec['unit']}, read off {what}. {reached:,} players in the frame "
            f"have ever reached the first rung.")


def _write(lines, name, out_dir=DRAFTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


# ─────────────────────────────────────────────────────────────
# Shared preparation
# ─────────────────────────────────────────────────────────────

def _prepare(ladders, **kw):
    """Frame, positions, per-ladder eligible sets and running totals."""
    df, prov = fg.load_frame(**kw)
    positions, offset = _career_positions(df, prov)

    # _coverage_mask must see the raw frame in its original row order, so the
    # reordered `positions` is not passed to it.
    raw = df.set_index(pd.RangeIndex(len(df)))

    tables = {}
    reached = {}
    for stat, spec in ladders.items():
        if stat == GAMES_LADDER:
            readable = set(offset.index)
            w = positions[positions['ID'].isin(readable)].copy()
            w['cumval'] = w['games_played'].astype(float)
            w['before'] = w['cumval'] - 1.0
            prov['Games_eligible'] = len(readable)
            prov['Games_exc_unreadable'] = (
                positions['ID'].nunique() - len(readable))
            tables[stat] = w
        else:
            eligible = _eligible_for_stat(raw, positions, offset, stat, prov)
            tables[stat] = _stat_totals(positions, stat, eligible)
        peak = tables[stat].groupby('ID')['cumval'].max()
        reached[stat] = int((peak >= spec['first']).sum())

    return df, prov, positions, tables, reached


# ─────────────────────────────────────────────────────────────
# Builder: milestones passed
# ─────────────────────────────────────────────────────────────

def build_milestones_passed(season, round_num, ladders=None,
                            out_dir=DRAFTS_DIR, **kw):
    """Every career milestone crossed in one round, with the game it fell in."""
    ladders = LADDERS if ladders is None else ladders
    _, prov, positions, tables, reached = _prepare(ladders, **kw)

    disp = _display_round(round_num, season)

    rows = []
    for stat, spec in ladders.items():
        w = tables[stat]
        rn = pd.to_numeric(w['Round'], errors='coerce')
        here = w[(w['Season'] == season) & (rn == round_num)]
        for r in here.to_dict('records'):
            for rung in _rungs_crossed(r['before'], r['cumval'],
                                       spec['first'], spec['step']):
                rows.append({
                    'stat': stat,
                    'rung': rung,
                    'unit': spec['unit'],
                    'who': fg._who(r['Player'], r['ID']),
                    'club': canonical_club(r['Playing.for']),
                    'opp': _opponent(r),
                    'on': r['Date'].strftime('%Y-%m-%d'),
                    'total': r['cumval'],
                    'in_game': r['statval'] if 'statval' in r else None,
                })
    rows.sort(key=lambda x: (list(ladders).index(x['stat']), -x['rung'],
                             x['who']))

    L = [f"# Milestones passed, Round {disp} {season}", ""]
    L.append(f"Every career milestone crossed in Round {disp} of {season} "
             f"(AFLTables raw Round {round_num}), with the game it was crossed "
             f"in. A milestone is a rung on a repeating ladder, so a player "
             f"crossing two rungs in one game appears twice.")
    L.append("")
    L.append(_sources_line(prov))
    L.append("")
    L.append(_frame_line(prov))
    L.append("")
    L.append("**Ladders read, and their steps.**")
    for stat, spec in ladders.items():
        L.append(_ladder_line(stat, spec, reached[stat]))
    L.append("")
    L.append(GAMES_RULE)
    L.append("")
    L.append(STAT_RULE)
    L.append("")
    L.extend(_counter_lines(prov))
    L.append("")
    L.append("**Eligibility per ladder.**")
    L.append(f"- Games: {prov['Games_eligible']:,} players with a readable "
             f"counter, {prov['Games_exc_unreadable']:,} without one. No "
             f"coverage test and no censoring test, because the counter carries "
             f"what this frame does not.")
    for stat in ladders:
        if stat == GAMES_LADDER:
            continue
        L.append(f"- {stat}: {prov[f'{stat}_eligible']:,} eligible. Excluded: "
                 f"{prov[f'{stat}_exc_coverage']:,} for a career game carrying "
                 f"no {stat} value, {prov[f'{stat}_exc_censored']:,} for a "
                 f"positive `Career.Games` offset, "
                 f"{prov[f'{stat}_exc_unreadable']:,} for an unreadable "
                 f"counter. The three overlap, so they do not sum to the "
                 f"excluded total.")
    L.append("")
    L.append(CENSORING_NOTE)
    L.append("")
    L.append(f"**2026 contributes home-and-away games only and no finals.** "
             f"`{fg.CURRENT}` carries no string round labels because the "
             f"prediction pipeline drops finals.")
    L.append("")
    L.append("The game key includes `Date`, so the four replayed drawn finals "
             "(1972 SF, 1977 GF, 1990 QF, 2010 GF) count as two games each "
             "rather than collapsing into one.")
    L.append("")
    L.append("Players are keyed on `ID`, never on name, and each row prints the "
             "ID beside the name. Clubs are canonicalised through "
             "`club_aliases.canonical_club()`.")
    L.append("")

    if not rows:
        L.append(f"**No milestone on any ladder was crossed in Round {disp}.** "
                 f"That is a result, not a gap: the ladders and their steps are "
                 f"listed above and every one was checked.")
    else:
        L.append(f"**{len(rows):,} milestone{'' if len(rows) == 1 else 's'} "
                 f"crossed.**")
        L.append("")
        L.append("| milestone | player | club | opponent | date | "
                 "career total after |")
        L.append("|---|---|---|---|---|---|")
        for r in rows:
            L.append("| " + " | ".join([
                f"{r['rung']:,} {r['unit']}", r['who'], str(r['club']),
                str(r['opp']), r['on'], f"{r['total']:,.0f}"]) + " |")
    L.append("")

    name = f"milestones_passed_{season}_r{disp}"
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} milestone(s) crossed in "
          f"Round {disp} {season}, raw Round {round_num})")
    for r in rows:
        print(f"   {r['rung']:,} {r['unit']}: {r['who']} ({r['club']}) "
              f"v {r['opp']}, {r['on']}")
    return out_path


# ─────────────────────────────────────────────────────────────
# Builder: milestones upcoming
# ─────────────────────────────────────────────────────────────

def build_milestones_upcoming(season, games_ahead=1, ladders=None,
                              clubs=None, out_dir=DRAFTS_DIR, **kw):
    """Active players whose next milestone is within one game's reach.

    Inclusion is a fact rather than a forecast. A stat entry is listed when the
    gap is at or below the player's own best single game this season, meaning
    the figure required is one he has already produced at least once. A games
    entry is listed when the gap is at or below `games_ahead`.

    `clubs` filters to an iterable of canonical club names, which is how a
    single fixture's preview block is cut from the full table.
    """
    ladders = LADDERS if ladders is None else ladders
    _, prov, positions, tables, reached = _prepare(ladders, **kw)

    played = pd.to_numeric(positions.loc[positions['Season'] == season,
                                         'Round'], errors='coerce')
    if played.empty:
        raise ValueError(f"no {season} rows in the frame, so there is no round "
                         f"to preview")
    last_played = int(played.max())
    upcoming = last_played + 1
    total_rounds = HA_ROUNDS.get(season)
    rounds_left = None if total_rounds is None else total_rounds - last_played

    club_now = _clubs_now(positions, season)
    wanted = None if clubs is None else {canonical_club(c) for c in clubs}

    rows = []
    for stat, spec in ladders.items():
        w = tables[stat]
        active = w[w['Season'] == season]
        if active.empty:
            continue
        last = (active.sort_values(['ID', 'Date']).groupby('ID').tail(1)
                      .set_index('ID'))
        season_rows = active.groupby('ID')
        if stat == GAMES_LADDER:
            per_game_best = None
            per_game_avg = None
        else:
            per_game_best = season_rows['statval'].max()
            per_game_avg = season_rows['statval'].mean()
        season_games = season_rows.size()

        for pid, r in last.iterrows():
            club = club_now.get(pid)
            if wanted is not None and club not in wanted:
                continue
            total = float(r['cumval'])
            rung = _next_rung(total, spec['first'], spec['step'])
            gap = rung - total
            if stat == GAMES_LADDER:
                if gap > games_ahead:
                    continue
                best = avg = None
            else:
                best = float(per_game_best.loc[pid])
                avg = float(per_game_avg.loc[pid])
                # The gap must be a figure he has actually produced in a game
                # this season. A gap nobody has met is not within reach, and
                # deciding otherwise would be a projection.
                if best <= 0 or gap > best:
                    continue
            rows.append({
                'stat': stat, 'rung': rung, 'unit': spec['unit'],
                'who': fg._who(r['Player'], pid),
                'club': club if club else canonical_club(r['Playing.for']),
                'total': total, 'gap': gap,
                'games': int(season_games.loc[pid]),
                'avg': avg, 'best': best,
            })
    rows.sort(key=lambda x: (list(ladders).index(x['stat']), x['gap'],
                             -x['rung'], x['who']))

    disp_next = _display_round(upcoming, season)
    disp_last = _display_round(last_played, season)

    L = [f"# Milestones within reach, Round {disp_next} {season}", ""]
    L.append(f"Career milestones reachable in Round {disp_next} of {season} "
             f"(AFLTables raw Round {upcoming}), with the exact number still "
             f"required. Totals are complete through Round {disp_last} (raw "
             f"Round {last_played}), the last round in the data.")
    if rounds_left is not None:
        L.append("")
        L.append(f"{season} runs {total_rounds} home-and-away rounds in the "
                 f"AFLTables numbering, so {rounds_left} "
                 f"round{'' if rounds_left == 1 else 's'} "
                 f"remain{'s' if rounds_left == 1 else ''} after Round "
                 f"{disp_last}.")
    L.append("")
    L.append("**No model output appears in this table.** There is no "
             "`Exp_Votes`, no vote claim and no projection. Every figure is "
             "already true before the first bounce: a career total to date, the "
             "arithmetic gap to the next rung, and the player's own "
             f"{season} figures. Selection is not modelled either, so a listed "
             "player reaches the milestone only if he plays.")
    L.append("")
    L.append("**Inclusion rule, which is a fact and not a forecast.** A stat "
             "entry is listed when the gap is at or below that player's best "
             f"single game of {season} for the stat, meaning the number "
             "required is one he has already produced in a game this season. A "
             f"games entry is listed when the gap is at or below "
             f"{games_ahead}. Nothing here judges whether he will do it again.")
    L.append("")
    L.append(_sources_line(prov))
    L.append("")
    L.append(_frame_line(prov))
    L.append("")
    L.append("**Ladders read, and their steps.**")
    for stat, spec in ladders.items():
        L.append(_ladder_line(stat, spec, reached[stat]))
    L.append("")
    L.append(GAMES_RULE)
    L.append("")
    L.append(STAT_RULE)
    L.append("")
    L.extend(_counter_lines(prov))
    L.append("")
    L.append("**Eligibility per ladder.**")
    L.append(f"- Games: {prov['Games_eligible']:,} players with a readable "
             f"counter, {prov['Games_exc_unreadable']:,} without one.")
    for stat in ladders:
        if stat == GAMES_LADDER:
            continue
        L.append(f"- {stat}: {prov[f'{stat}_eligible']:,} eligible. Excluded: "
                 f"{prov[f'{stat}_exc_coverage']:,} for a career game carrying "
                 f"no {stat} value, {prov[f'{stat}_exc_censored']:,} for a "
                 f"positive `Career.Games` offset, "
                 f"{prov[f'{stat}_exc_unreadable']:,} for an unreadable "
                 f"counter.")
    L.append("")
    L.append(CENSORING_NOTE)
    L.append("")
    L.append(f"**The {season} per-game figures are home-and-away only.** "
             f"`{fg.CURRENT}` carries no finals, and the denominator for both "
             f"the average and the best is the player's {season} games in that "
             f"file, printed per row.")
    L.append("")
    if wanted is not None:
        L.append(f"**Filtered to {', '.join(sorted(wanted))}.** Club is the "
                 f"club the player last played for in {season}, canonicalised "
                 f"through `club_aliases.canonical_club()`.")
        L.append("")
    L.append("Players are keyed on `ID`, never on name, and each row prints the "
             "ID beside the name.")
    L.append("")

    if not rows:
        L.append(f"**No player on any ladder is within reach for Round "
                 f"{disp_next}.** That is a result, not a gap: the ladders, "
                 f"their steps and the inclusion rule are all stated above.")
    else:
        L.append(f"**{len(rows):,} milestone{'' if len(rows) == 1 else 's'} "
                 f"within reach.**")
        L.append("")
        L.append(f"| milestone | player | club | career total | needs | "
                 f"{season} games | {season} avg | {season} best |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            L.append("| " + " | ".join([
                f"{r['rung']:,} {r['unit']}", r['who'], str(r['club']),
                f"{r['total']:,.0f}", f"{r['gap']:,.0f}", str(r['games']),
                "n/a" if r['avg'] is None else f"{r['avg']:.1f}",
                "n/a" if r['best'] is None else f"{r['best']:,.0f}"]) + " |")
    L.append("")

    # The club filter goes in the filename. Without it a fixture cut overwrites
    # the full round table, which is the same trap two files apart: both are
    # legitimate outputs for the same season and round, and the narrower one
    # silently replacing the wider one is not detectable by reading either.
    name = f"milestones_upcoming_{season}_r{disp_next}"
    if wanted is not None:
        name += "_" + "_".join(fg._slug(c).replace('_', '')
                               for c in sorted(wanted))
    out_path = _write(L, name, out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} milestone(s) within reach for "
          f"Round {disp_next} {season}, raw Round {upcoming})")
    for r in rows:
        print(f"   {r['rung']:,} {r['unit']}: {r['who']} ({r['club']}) needs "
              f"{r['gap']:,.0f}, on {r['total']:,.0f}")
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_USAGE = ("usage: python milestones.py passed <season> <raw_round>\n"
          "       python milestones.py upcoming <season> [games_ahead]\n"
          "  raw_round is the AFLTables Round_num, not the AFL round number")


def main(argv):
    if not argv or argv[0] not in ('passed', 'upcoming'):
        print(_USAGE, file=sys.stderr)
        return 2
    mode = argv[0]
    rest = argv[1:]
    if mode == 'passed':
        if len(rest) != 2:
            print(_USAGE, file=sys.stderr)
            return 2
        try:
            season, round_num = int(rest[0]), int(rest[1])
        except ValueError:
            print(f"season and raw_round must be integers, got "
                  f"{rest[0]!r} and {rest[1]!r}", file=sys.stderr)
            return 2
        build_milestones_passed(season, round_num)
        return 0

    if len(rest) not in (1, 2):
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        season = int(rest[0])
    except ValueError:
        print(f"season must be an integer, got {rest[0]!r}", file=sys.stderr)
        return 2
    games_ahead = 1
    if len(rest) == 2:
        try:
            games_ahead = int(rest[1])
        except ValueError:
            print(f"games_ahead must be an integer, got {rest[1]!r}",
                  file=sys.stderr)
            return 2
        if games_ahead < 1:
            print(f"games_ahead must be at least 1, got {games_ahead}",
                  file=sys.stderr)
            return 2
    build_milestones_upcoming(season, games_ahead=games_ahead)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
