# Handover, weekly formats

Written 18 August 2026, continuing from `HANDOVER_weekly_formats.md`. That
handover diagnosed the problem as "none of it is weekly" and named five
candidate formats ranked by weekly reliability. Three are now built.

## What this session produced

Three modules, all pushed, all verified against a direct read of the source
CSVs by a script sharing no logic with the module under test.

**`milestones.py`** (`7965ded`), candidate 1. Two builders: milestones passed in
a round, and milestones within reach for the round about to be played. Raw
Round 24 produced 20 crossings; the Round 25 preview produced 39 within reach.
`clubs=` cuts a single fixture's block and goes into the filename.

The find is `Career.Games`. It is AFLTables' own inclusive career counter and it
carries games played before this archive starts, so Ted Whitten sits at 248 in a
1965 row. A games milestone is therefore exact for a pre-1965 debutant. Zero in
that column is a missing value rather than a count, on 145 rows across 61
players; nulled, the offset between counter and row index is constant for all
6,038 players carrying it, and that offset IS the per-player left-censoring.

**`round_bests.py`** (`7f5f557`), candidate 2. The best figure in each of 14
stats for a round, with its rank among every player-game on record, and the
ranked table the rank is drawn from. A per-game record is not censored, which is
the opposite of the career modules, so there is no per-player eligibility test
here at all. What is limited is the comparison set, per stat: tackles compare
from 1987, goal assists from 2003, goals across the whole frame. Floors are
measured every run and a drift raises.

**`stat_streaks.py`** (`70e3de9`), candidate 4 in its preview-native half. Runs
of consecutive appearances clearing a threshold, active and longest on record,
plus a 14-pair board. Distinct from `streaks.py`, which is polling streaks only.

## The three things worth knowing before touching any of them

**"Consecutive games" is ambiguous and the ambiguity is expensive.** McKenna's
goal streak measures 121 appearances here; Collingwood played 140 matches in
that window and he missed 19 of them. The published figure is usually 119 and it
is deliberately not reconciled, because the published figure does not travel
with its definition. Every streak row prints club matches in the span and how
many were missed. A run with 0 missed is safe to write plainly. Ben King's 23 is
clean, Jack Higgins' 11 spans 6 missed matches, and without the column both get
written the same way.

**Two bugs were found by verification, not by review.** Club matches were
counted over the union of a traded player's clubs, turning Bailey Smith's
45-game run into 94 missed matches instead of 4. And the active test was "last
appearance at or after the season start", which admits every later season, so a
1995 board answered with Matt Rowell, who debuted in 2020. Both are fixed and
both are recorded in the commit messages. Assume the same class of error is
still present somewhere and keep writing the independent checker before
believing an output.

**The three modules share `fewest_games.load_frame()` deliberately**, and
`stat_streaks` imports its floors from `round_bests`, so a re-measured window
moves both at once. The only edit to an existing file was widening
`fewest_games._BASE_COLS` by `Career.Games`; that tuple feeds only `_WANTED`, so
nothing `fewest_games` computes changed.

## The thing that reframes the schedule

**Only one home-and-away round remains.** The data runs through raw Round 24 and
2026 has 25 raw H&A rounds, so raw Round 25 is the last one. The original
handover framed these formats as "carrying an entire content schedule between
now and 21 September", and that premise no longer holds in the form it was
written: after next week there are no more H&A rounds to preview or review.

What survives into September, and what does not:

- `round_bests.py` and `stat_streaks.py` both run on finals without change,
  since both already count finals and neither needs votes. A finals round best
  ranked against 1965 is a strong post and there are four finals weeks.
- `milestones.py` runs on finals too, but its `HA_ROUNDS` note and the
  "rounds remaining" line assume an H&A schedule. Check that copy before using
  it on a finals week.
- Every vote-based format stops. The disagreement table is still parked on the
  private coaches feed and nothing changes that before count night.

Plan the remaining weeks as one H&A round, four finals weeks and count night,
not as five more rounds.

## What is left from the candidate list

**Candidate 3, rare lines, is now cheap.** `round_bests` already computes, for
each round best, how many player-games have reached that figure or better. A
rare-lines format is that same count applied to every performance in the round
rather than only the leader, filtered to counts below some N. The machinery
exists; it needs a threshold chosen and a builder written. It stays "empty most
weeks", so it supplements a schedule rather than carrying one.

**Candidate 5, threshold combos, is unbuilt.** The presentation shape it wants
already exists in `round_bests`, which appends the current entry into the
all-time table and marks it.

**Candidate 4's other half is unbuilt.** Venue and opponent droughts at
*player-stat* level. `team_h2h*` is thorough at team level and
`fixture_recon_spec.md` blocks 6 and 7 are vote level, so the gap the original
handover identified, that "the preview is thin because it draws on vote history
alone", is only partly closed. Milestones and streaks widened it; per-player
stat records against an opponent and at a venue are still missing, and those are
two of the five blocks the handover's "what the preview needs" list asked for.

## Open, not blocking

- **None of the three is wired into `update.py`.** They are run by hand.
- **None writes a `.facts.json`.** They are recon tables, consistent with
  `all_time_tables.py` and `fewest_games.py`, but `draft_gate.py` hard-fails on
  a draft without a facts sibling, so copy drafted from these still needs one
  built by hand. If these become a weekly posting path, that is the gap to close
  first.
- **Thresholds and ladder steps are house convention, not derived.** The
  milestone ladders (games 50, goals 100, disposals 1,000, tackles 250, marks
  500) and the 14 streak pairs were chosen so each fires and each is a number a
  reader recognises. They are defensible, not measured.
- **`fewest_games.py` still uses the blunter left-censoring rule**, excluding
  every player whose first game falls in 1965. `milestones.py`'s offset test is
  sharper in both directions, recovering 118 genuine 1965 debutants and catching
  18 later debutants the old rule cannot see. Left alone deliberately, since
  changing it would move already-published tables. Unifying them is a real task
  with a real consequence and should be its own session.
- **The McKenna 119 against 121 question is unresolved by choice.** Do not
  "fix" it without a published source that states its own definition.
- Metres gained and spoils still need a fryzigg fetch.
- The three medallist-dependent tables are still unblocked and unbuilt.

## Next session

Rare lines, built on `round_bests`' existing rarity count, is the cheapest real
addition and it fires hardest exactly when it matters. But if only one thing
gets done before finals, make it the finals-week check: run all three modules
against a finals round and fix the copy that assumes an H&A schedule. The
formats are worth more in September than in the one round left before it.
