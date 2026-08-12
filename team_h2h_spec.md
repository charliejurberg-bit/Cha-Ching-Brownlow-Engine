# team_h2h_spec.md

Governs `team_h2h.py`. Team-level head-to-head fixture preview.
Distinct from `fixture_recon_spec.md`, which is player-level.

Status: draft, not yet built. Recon completed and reflected below.

---

## 1. Scope and invocation

```
python team_h2h.py --teams "Richmond" "St Kilda" [--scope all|ha|finals] [--without "Tim Taranto"]
```

- First team named is the **subject team**. All records, streaks and quarter
  results are oriented to the subject, never to the home side.
- `--scope` defaults to `all`.
- `--without` is opt-in only, repeatable, and never runs unless requested.
- Output is a markdown facts file to `drafts/`. No tweet copy is generated.
  `draft_gate.py` has no team-mode coverage, so no draft is produced here.

---

## 2. Data source

No match-level file exists in a tracked directory. The match table is **derived
at runtime** from three player-level fitzRoy files:

| File | Seasons | Matches |
|---|---|---|
| `data_history/fitzroy_stats_1965_2006.csv.gz` | 1965–2006 | 6,461 |
| `fitzroy_stats_all.csv` | 2007–2025 | 3,815 |
| `data_2026/afltables_2026.csv` | 2026 | 189 |

Expected derived total: **10,469 matches**. This count is a build assertion.
If the build produces a different number, it fails and reports rather than
proceeding.

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

## 3. Quarter scores — cumulative

Quarter columns are **progressive cumulative scores**, not per-quarter scores.
`HQ4` equals the final score. Verified on four sampled matches across 1965,
2020, 2025 and 2026.

Per-quarter result for quarter *n*:

```
subject_qn = subject_cumulative[n] - subject_cumulative[n-1]
opp_qn     = opp_cumulative[n]     - opp_cumulative[n-1]
```

with `cumulative[0] = 0`. Scores are stored as `G.B` strings and must be
converted to points as `G*6 + B` before differencing.

A comparison of raw `HQ2` against `AQ2` answers "who led at half time" and is a
different claim. If a half-time lead figure is ever wanted it gets its own
labelled section and is never called a quarter result.

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
- The disambiguating parenthetical suffix in `Player_Name` is never stripped.
  Two Bailey Williamses exist in 2026.
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
5. `HQ4` converted to points does not equal the home final score, and likewise
   for away. This is the cumulative-scores guard and it runs on every match.
6. Any team value is not handled by `canonical_club()`.
7. `ID` or `Jumper.No.` arrives as a different dtype than declared at load.
   Cast explicitly, then assert.
8. `url` format differs across the three source files. Test by taking players
   appearing in both the 1965–2006 archive and 2007–2025, and confirming the
   `url` strings match exactly. If they do not, the with/without cut cannot
   span the join and the script says so rather than under-counting.

A check that returns empty is a failed check, not a passed one.

---

## 13. Unresolved before build

1. RESOLVED. Player identity is available from 1965. `url` is the key; see
   section 10.
2. RESOLVED. Finals key verified at 455 keys for 455 matches. See section 2.
3. **`url` continuity across the three files is untested.** 499 `ID` values are
   shared between the archive and 2007–2025, so the numbering is continuous, but
   nobody has confirmed `url` uses an identical format across files rather than
   full URL in one and filename in another. Build assertion 8 covers it.
4. Timeslot bin boundaries (section 6) — assumption in place, needs a decision.
5. Cross-opponent trigger threshold of 4 (section 9) — assumption in place.
6. RESOLVED. `data_history/` documented in full at 285709c: 19 files, not one.
   The two that mattered were `fitzroy_stats_1965_2006.csv.gz` and the 17
   `game_level_YYYY.csv` files. Project Knowledge re-upload required.
