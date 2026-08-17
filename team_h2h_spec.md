# team_h2h_spec.md

Governs `team_h2h.py`. Team-level head-to-head fixture preview.
Distinct from `fixture_recon_spec.md`, which is player-level.

Status: draft, not yet built. Recon completed and reflected below.

---

## 1. Scope and invocation

```
python team_h2h.py --teams "Richmond" "St Kilda" [--scope all|ha|finals] [--date 2026-08-15] [--without "Tim Taranto"]
```

- First team named is the **subject team**. All records, streaks and quarter
  results are oriented to the subject, never to the home side.
- `--scope` defaults to `all`.
- `--date` is the scheduled fixture date and feeds section 6 item 7 only. That
  section is undefined without a reference date, so omitting the flag reports
  it as not computed rather than inventing one.
- `--without` is opt-in only, repeatable, and never runs unless requested.
- Output is a markdown facts file to `drafts/`. No tweet copy is generated.
  `draft_gate.py` has no team-mode coverage, so no draft is produced here.

---

## 2. Data source

No match-level file exists in a tracked directory. The match table is **derived
at runtime** from three player-level fitzRoy files:

| File | Seasons | Matches |
|---|---|---|
| `data_history/fitzroy_stats_1965_2006.csv.gz` | 1965–2006 | 6,464 |
| `fitzroy_stats_all.csv` | 2007–2025 | 3,816 |
| `data_2026/afltables_2026.csv` | 2026 | 189 |

Expected derived total: **10,469 matches**, verified by the loader at 644a17e.

These are the **with-Date** counts. An earlier revision of this table read
6,461 / 3,815 / 189, which are the without-Date counts and sum to 10,465. The
difference is exactly the four drawn-final replays: three fall in the archive
(1972 SF, 1977 GF, 1990 QF) and one in 2007–2025 (2010 GF). If a count here
ever reads 10,465, Date has been dropped from the key.

The 2026 figure moves as the season progresses. Assert against a recomputed
expectation, never a literal.

`_tmp/match_results_all.csv` is **not** a source. It is untracked, sits under a
gitignored directory, was produced by a script that no longer exists, and
carries no start time and no quarter scores. Do not build on it and do not
adopt it later without a tracked regeneration path.

The 17 `data_history/game_level_YYYY.csv` files (1990–2006, 124,171 rows) are
**not** a source either, despite overlapping the archive's range. They carry no
venue, no date, no start time and no quarter scores, and they drop finals
entirely. Substituting them for the `.gz` would silently remove every final from
the record and disable the whole quarter-by-quarter engine. They are the Stat
Filter's source, read by `_load_stat_filter_frame()`, and produced by
`scripts/convert_history.py`.

### Match key

```
(Season, Round, canonical_club(Home), canonical_club(Away), Date)
```

**Date is mandatory in the key.** Without it four drawn-final replays collapse
into one row: 1972 SF, 1977 GF, 1990 QF, 2010 GF. Two of those involve Richmond
and Collingwood respectively, so the defect is not theoretical for club-history
enumeration. There is no ID column in the fitzRoy files to fall back on.

`canonical_club()` runs on **both** sides of every join. Omitting it on one side
lost 22 Kangaroos fixtures in 2007 during recon.

### Round column

`Round` is mixed type: integers for home and away, string codes for finals
(`SF`, `PF`, `GF`, `QF`, `EF`). Cast to int only after the finals rows are
partitioned off.

The finals key is **verified**: 455 distinct keys for 455 distinct finals
matches, zero collisions, all four drawn-final replays separated. Dropping Date
loses exactly those four.

**Finals codes are era-dependent and are not a grouping variable.** The same
code denotes different matches across five eras:

| Era | EF | QF | SF | PF | GF | Total |
|---|---|---|---|---|---|---|
| 1965–1971 final four | 0 | 0 | 2 | 1 | 1 | 4 |
| 1972–1990 final five | 1 | 1 | 2 | 1 | 1 | 6 |
| 1991–1993 final six | 2 | 1 | 2 | 1 | 1 | 7 |
| 1994–1999 final eight (McIntyre) | 0 | 4 | 2 | 2 | 1 | 9 |
| 2000–2025 final eight (current) | 2 | 2 | 2 | 2 | 1 | 9 |

QF doubles in meaning at 2000. EF vanishes for 1994–1999 and returns. Only the
`is_final` boolean and `GF` are safe across the whole range. No section of this
tool groups or reports by finals code, and any future one must partition by era
first.

### Dtype hazard at concatenation

`ID` is int64 in the 1965–2006 archive and float64 in the other two files,
purely because those two carry nulls. Concatenation silently promotes the whole
column to float64, producing `755.0`. `Jumper.No.` flips the other way. Cast
explicitly at load rather than relying on inference, and never key on `ID`
(see section 10).

---

## 3. Quarter scores — cumulative, and stored as integers

Quarter columns are **progressive cumulative scores**. `HQ4` equals the
full-time score.

**Storage format, corrected 12 August 2026.** There are no `G.B` strings. This
spec previously said there were, inferred from a printed dry run that was
formatting two columns for display. The sources carry:

- `HQ1G`, `HQ1B` … `AQ4G`, `AQ4B` — separate int64 goal and behind columns
- `HQ1P` … `AQ4P` — pre-computed points, where `P == G*6 + B` with zero
  mismatches across all 10,469 matches

Use the `P` columns directly. A string parser crashes on int64. The `G*6 + B`
identity is retained as a build assertion, not as the conversion path.

Per-quarter result for quarter *n*:

```
subject_qn = subject_P[n] - subject_P[n-1]
opp_qn     = opp_P[n]     - opp_P[n-1]
```

with `P[0] = 0`. The loader stores cumulative columns only; **differencing
belongs to the consumer**, because the cumulative values are also what a
half-time or three-quarter-time lead figure needs.

A comparison of raw `HQ2P` against `AQ2P` answers "who led at half time" and is
a different claim. If that figure is ever wanted it gets its own labelled
section and is never called a quarter result.

### Extra time

Three finals went to extra time: 1994 QF, 2007 SF, 2017 EF. Two of the three
involve West Coast, so this is live for real fixtures.

- **Match result uses extra time.** `subject_score` and `opp_score` take
  `HQETP`/`AQETP` where present, else `HQ4P`/`AQ4P`. There is no bare `HQET` or
  `AQET` column; the source carries `HQETG`, `HQETB`, `HQETP` and the away
  equivalents, all float64 and null on every match except the three. The record
  books use the extra-time result and so does every W-L-D section here.
- **Quarter results are regulation only.** `Q4 = P[4] - P[3]`. Extra time is not
  a quarter and is never folded into one.
- All three matches were drawn at full time, so the regulation result is a draw
  and the final result is a win or a loss. Both are true and they are different
  quantities.
- Every match row carries a `went_to_extra_time` boolean. Any quarter section
  whose population includes such a match prints a note naming it. This is the
  guard against a conditional claim silently mixing a regulation quarter record
  against an extra-time match record.

---

## 4. Coverage floor

Every field used here is populated for every match from **1965**, with zero
nulls across all 10,469 matches. There is no per-field floor; the floor is the
archive's.

The 1965 floor is a **hard truncation, not a club-history boundary.** Richmond
and St Kilda met from 1908; this archive holds 106 of those meetings. The
truncation caveat must accompany every superlative, every "in club history"
claim, and every all-time ranking, in the same form as the 1990 truncation rule.

Preferred phrasing: "since 1965", never "ever" or "in club history".

`Local.start.time` is an **integer HHMM**, not a string. 1420 is 2:20pm. It is
local to the venue, which is the correct basis for timeslot bins.

---

## 5. Club handling

- Fitzroy stays Fitzroy. Never folded into Brisbane.
- Brisbane Bears folds to Brisbane Lions via `canonical_club()`. **Assumption
  flagged:** this means a Brisbane Lions H2H silently includes the 1987–1996
  Bears era. That is the correct continuing-entity treatment, but any Brisbane
  preview must print the split so the reader can see it.
- Footscray folds to Western Bulldogs, GWS to Greater Western Sydney.
- Kangaroos folds to North Melbourne.
- University is unhandled by `canonical_club()`. Irrelevant at a 1965 floor
  (club existed 1908–1914). Add only if the floor ever moves earlier.

---

## 6. Fixed cut list

The cut list is **pre-declared and identical on every run.** No free search.

A 106-meeting series will always contain a striking pattern somewhere in
{4 quarters x W/L/D x venue x timeslot x day x home/away}. That is the search
space talking, not a finding. Every conditional claim prints the number of cuts
tested to surface it.

Sections, in order:

1. **Series overview.** W-L-D, denominator W+L+D, first and last meeting, floor
   caveat.
2. **Scope split.** Home and away vs finals, W-L-D each.
3. **Venue.** W-L-D per venue, denominator each.
4. **Timeslot.** W-L-D per bin, denominator each.
5. **Day of week.** W-L-D per day, denominator each.
6. **Venue x timeslot.** W-L-D per cell, denominator each. Cells with n=0
   suppressed.
7. **Same calendar date.** Meetings sharing day-and-month with the scheduled
   fixture. Expected n of 0–3. Reported as a fact, not a signal, per the
   team-splits rule. Denominator printed.
8. **Quarter by quarter.** W-L-D for Q1, Q2, Q3, Q4 separately, oriented to the
   subject, computed on differenced scores.
9. **Streaks.** See section 8.
10. **Cross-opponent enumeration.** See section 9. Conditional.
11. **With/without player.** Only when `--without` is passed. See section 10.

### Timeslot bins

**Assumption flagged, tunable:**

| Bin | Local start |
|---|---|
| Day | before 1600 |
| Twilight | 1600–1829 |
| Night | 1830 and later |

Every 1965-era match sits at 1420, so early seasons collapse entirely into Day.
The bin table prints its own season range per bin so that is visible.

---

## 7. Draws and records

- W-L-D as **three explicit columns.** Draws are never folded into either side.
- Denominator printed as W+L+D on every split.
- A drawn quarter is a draw, not a half-win.

---

## 8. Streak rules

```
- A loss breaks a streak. A draw does not.
- A run containing >=1 loss is not a streak.
- Run of W only        -> "won X consecutive"
- Run of W and D mixed -> "has not lost X consecutive"
- Run of D only        -> suppressed, not reported
- Every non-loss streak prints its W-D composition.
- Cross-opponent superlatives rank on ONE definition, named in the table
  header. Win-streaks and non-loss streaks are never mixed within a report.
```

**Scope interaction.** Streak sections **always compute on all matches**
regardless of `--scope`. A final sitting between two home-and-away results
breaks continuity, and excluding it manufactures a streak that never happened.
Finals exclusion is right for rates and wrong for counts.

Under `--scope ha`, every streak section additionally lists each final falling
inside the streak window, by season and round, so the inclusion is visible
rather than assumed.

Both a live streak (running as of the most recent meeting) and the longest
historical streak are reported, labelled distinctly. A live streak is the
post-worthy one; a historical streak is context.

---

## 9. Cross-opponent enumeration

Triggered only when a **live** streak for the subject team reaches length >= 4.
This gate is a cost control and is tunable.

When triggered, enumerate the subject team's equivalent streak against **every**
opponent it has met since 1965, and print:

- the full ranked table
- the gap to rank 2
- the denominator (number of opponents enumerated)
- the streak definition used, in the header
- the 1965 floor caveat

Per the superlative rule, no `only`, `no other`, `best`, `worst`, `highest` or
`lowest` claim ships without this table. Extending a range can kill a claim
rather than strengthen it, so the table is the output, not a supporting file.

---

## 10. With/without player

Opt-in via `--without`. Runs in addition to the full standard preview, never
instead of it.

### Identity

**`url` is the identifier. Not `ID`, and never a name.**

- `url` has zero nulls in all three files and carries more distinct values than
  `ID` in both files where `ID` is null (2,231 vs 2,230; 663 vs 654). It is
  available from 1965.
- `ID` is a valid secondary and is printed alongside for traceability, but it is
  null on 82 rows: one player in 2025, eleven in 2026 whose AFLTables numeric ID
  has not been minted yet. Those rows are exactly the recent players a
  with/without cut is most likely to be asked about.
- **Name to identifier is a failed lookup in principle, not in practice.** An
  identifier resolves to a person; a name does not. Eight names carry more than
  one identifier across 2007–2015 alone, four of them active simultaneously at
  different clubs: Josh Kennedy, Mitch Brown, Nathan Brown, Scott Thompson,
  Andrew Browne, Chris Johnson, Sam Reid, Tom Lynch.
- On a name argument the script resolves to candidate `url` values and, if more
  than one survives, **stops and reports the candidates** with club and season
  range. It never picks the one with more games, the more recent one, or the
  one matching the subject club. `--without` then accepts a `url` directly.
- `Player_Name` and its parenthetical suffix belong to
  `predictions/game_level_*.csv`, not to the three sources this tool reads.
  Keying on `url` means the module is never in a position to strip a suffix.
  Two Bailey Williamses exist in 2026 and separate cleanly on `url`.
- **An empty arm is not a contrast.** If either arm has a denominator of zero,
  the result is a bare record and must not be framed as a with/without finding.
  Tim Taranto is the worked case: he played all seven Richmond v St Kilda
  meetings in his Richmond tenure, so "1-6 with Taranto" has no comparator. The
  facts writer suppresses the framing and states the reason. The numbers are
  still returned; only the framing is withheld.
- Expect empty arms to be common. A regular player misses few matches against
  any single opponent, so the cut is most informative for long tenures, high
  meeting counts, or players with a significant injury absence.
- Tenure window is first-to-last appearance **for the subject club specifically**,
  not career-wide. A player who later moves clubs does not extend the window.
- Both sides reported with denominators: with (n), without (n).
- No quarter-by-quarter breakdown on the player cut.
- Matches inside the window where the player was listed but did not play are
  counted as "without". Availability, suspension and selection are not
  distinguishable from this data, and the output says so.

---

## 11. Output rules

- Every figure computed in the run that reports it. No figure carried forward,
  no figure hand-summed.
- Every rate states its denominator and source file.
- Every raw count carries a source file.
- No em dashes.
- Round number stated.
- No forward-looking claims. This tool is entirely retrospective and touches no
  model output.
- Facts file only. Copy is written separately once `draft_gate.py` covers team
  mode.

---

## 12. Build assertions

The script fails and reports rather than proceeding if any of these break:

1. Derived match table is not 10,469 rows for 1965–2026 (adjust as 2026
   progresses; assert against a recomputed expectation, not a literal).
2. Any of venue, date, start time, quarter scores or final scores contains a
   null.
3. Any match key appears more than once after the date component is included.
4. Any match has the same value for both teams.
5. For every match without extra time, `HQ4P` does not equal the home final
   score, or `AQ4P` does not equal the away final score. For matches with extra
   time, the same check runs against `HQET`/`AQET`. This is the cumulative-scores
   guard and it runs on every match.
6. `HQnP != HQnG*6 + HQnB` for any quarter or either team. The identity is
   pre-computed in the source and asserted here, not relied upon.
7. Any team value is not handled by `canonical_club()`.
8. `ID` or `Jumper.No.` arrives as a different dtype than declared at load.
   Cast explicitly, then assert.
9. `url` format differs across the three source files. Test by taking players
   appearing in both the 1965–2006 archive and 2007–2025, and confirming the
   `url` strings match exactly. If they do not, the with/without cut cannot
   span the join and the script says so rather than under-counting.
10. The extra-time match count for 1965–2025 is not exactly three. A fourth
    would mean either a new finding or a broken `HQET` read, and both need
    reporting rather than absorbing.

A check that returns empty is a failed check, not a passed one.

---

## 13. Unresolved before build

1. RESOLVED. Player identity is available from 1965. `url` is the key; see
   section 10.
2. RESOLVED. Finals key verified at 455 keys for 455 matches. See section 2.
3. RESOLVED at 644a17e by assertion 9. 499 players appear in both the archive
   and 2007–2025 and their `url` strings match exactly, all three files using
   the full `https://afltables.com/...` form. The with/without cut spans the
   join.
4. Timeslot bin boundaries (section 6) — assumption in place, needs a decision.
5. Cross-opponent trigger threshold of 4 (section 9) — assumption in place.
6. RESOLVED. `data_history/` documented in full at 285709c: 19 files, not one.
   The two that mattered were `fitzroy_stats_1965_2006.csv.gz` and the 17
   `game_level_YYYY.csv` files. Project Knowledge re-upload required.

---

## 14. Extended tier, 1897–1964

Added after the original build. **Opt-in via `--extended`; without the flag
nothing in sections 1–11 changes.** The one difference an unflagged run does
make is a section 12 heading carrying the same "Not run, opt-in via" stub that
sections 10 and 11 already print, so the file states that the tier exists and
was declined rather than staying silent about it. Verified by diffing an
unflagged run against the same run built from the commit before the tier: five
added lines, all of them that stub, with sections 1–11 and the closing floor
line untouched.

### Why the 1965 floor was never a results floor

Section 2 derives the match table from three **player-level** files, so the
floor is the floor of AFLTables player statistics, 1965. Nothing about the
*results* stops there. `fetch_results_afltables()` reaches 1897, the VFL's
first season, and carries date, venue, round, both clubs and full scores.

### The condition section 2 set, and how this meets it

Section 2 rules out `_tmp/match_results_all.csv` on three grounds: untracked,
gitignored directory, and **produced by a script that no longer exists**. It
adds: "do not adopt it later without a tracked regeneration path."

`scripts/fetch_results_pre1965.R` **is** that path. It writes
`data_history/match_results_1897_1965.csv` (tracked, 6,670 rows) and asserts
the points identity before writing.

The fourth ground stands and is not fixable: the feed carries **no start time
and no quarter scores**. That is why this is a separate tier rather than a
fourth entry in `SOURCES`.

| Tier | Source | Matches | Loader |
|---|---|---|---|
| 1897–1964 | `match_results_1897_1965.csv` | 6,558 | `team_match_table_pre1965.py` |
| 1965–2026 | the three player files | per section 2 | `team_match_table.py` |

The tiers **must not be concatenated blindly.** The pre-1965 table is
deliberately narrower and does not null-fill the columns it lacks, so a
consumer reaching for `local_start_time` fails at the point of the mistake
rather than binning 6,558 matches as "Unknown".

### What crosses the join and what does not

| Section | Extends | Why not |
|---|---|---|
| 1 overview, 2 scope split, 3 venue, 5 day, 7 same date | yes | |
| 9 streaks, **match basis only** | yes | |
| 4 timeslot, 6 venue × timeslot | no | no `Local.start.time` |
| 8 quarter by quarter, 9 streaks Q1–Q4 | no | no quarter scores |
| 11 with/without | no | no player rows |

Unavailability is **printed, never left blank.** A blank section reads as "no
matches"; the truth is "the field was never recorded". `UNAVAILABLE` in
`team_match_table_pre1965.py` is the machine-readable form.

### The overlap season

The fetch reaches 1965 even though the tier stops at 1964. That season is the
**join validation**: `validate_join()` checks the two feeds agree before any
combined figure is trusted. Verified at build: 112 matches both feeds, 112
scores agreeing, 112 venue strings agreeing. Without an overlap the join would
be unverifiable. The tier itself drops 1965, and assertion 8 enforces the
1897–1964 range so nothing is double-counted.

### Extra time pre-1965

`went_to_extra_time` is False on every pre-1965 row, and that is a fact about
the era rather than a missing field: extra time did not enter VFL finals until
1991, and a drawn final was replayed the following week as its own match.
Assertion 7 checks every drawn final has a replay, so the False is verified.

### Mixed floors — the new failure mode

An extended file carries **two floors**. The risk is a reader pairing an
all-time figure from section 12 with a 1965-floored figure from section 8 in
one sentence. Three guards:

1. Every section 12 frame carries a `floor` column, so a table copied out of
   context still names its floor.
2. `MIXED_FLOOR_WARNING` prints before any section 12 table, and a banner
   prints in the header.
3. Section 12's cells-tested count is reported **separately** from the 1965+
   count. They are the same cuts on a different population, so one number
   would misstate both.

### Claim strength, and the limit of it

1897 is the VFL's first season, so for two clubs in the competition from 1897
the extended tier IS complete VFL/AFL history: "since 1897" and "in VFL/AFL
history" are both true of it. It is still **not club history** — clubs played
in the VFA before 1897 and no tier here holds those meetings.

`ties` is printed on section 12 streaks and not on section 9's. Widening the
archive is exactly what creates ties at the longest, two equal runs from
different eras landing in one population. A tied longest written as a
superlative is the specific defect that column prevents.

### Clubs

University (1908–1914) appears and is deliberately NOT added to
`CLUB_ALIASES`. It maps to itself, which is already what `canonical_club()`
does with an unrecognised string, and it terminates rather than folding, like
Fitzroy. It is in `KNOWN_CLUBS` so the guard cannot pass it through unnoticed.
This supersedes section 5's "add only if the floor ever moves earlier": the
floor moved, and the answer was the known-club set rather than an alias.

Note the results feed already emits South Melbourne as "Sydney" where the
player feed emits "South Melbourne". `canonical_club()` runs on both sides in
both loaders, so the tiers land on the same string either way.
