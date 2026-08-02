# Fixture recon spec

Status: written 28 July 2026. Hand-run twice before being written down, against
Fremantle v Western Bulldogs and St Kilda v Sydney. Not yet a script.

Purpose. Given one fixture, produce the retrospective material a preview tweet
can be built from. Everything is retrospective. The recon never projects and
never comments on the upcoming game.

Intended end state: a script taking two team names, so this becomes a command
rather than a session. Four scoping decisions below must be settled first.

## Standing preamble

Interactive mode, default: read-only. Do not edit, commit, or run anything.
PowerShell and Select-String only. Report and stop.

Autonomous mode, only when the prompt says so explicitly: the Script hygiene
section governs. Throwaway python scripts in _tmp/ are permitted.

For every player-level record, report meetings PLAYED, polls, and zero-vote
games as three separate numbers. Never report a poll count in language that
implies a meeting count. This is the defect that produced a false draft tweet:
"his last five meetings" was actually his last five polls, with three zero-vote
meetings sitting inside the window.

Do not open game_level_2025.csv. It carries 39 duplicate rows in Round_num 24
and needs a documented dedupe at read time. If any block would require it, say
so and stop rather than working around it.

## Existence checks, before any block

A. Team naming. List the distinct Team values in fitzroy_stats_all.csv for both
   clubs. Team and Home.Team/Away.Team do not always agree. Known cases: the
   Bulldogs store as Team = Footscray but Home/Away = Western Bulldogs; GWS
   stores as Team = GWS but Home/Away = Greater Western Sydney, so a Sydney
   filter must be exact or it pulls GWS. Coaches votes use different names
   again, e.g. Sydney Swans. Check per file, do not assume across files.

B. Venue strings. List every distinct Venue value in fitzroy_stats_all.csv
   corresponding to the fixture ground, with the season range each covers.
   fitzRoy normalises most grounds to a single string; Docklands is one string
   covering 2007 to 2025 with no Marvel, Etihad, Telstra Dome or Colonial
   variants. Perth Stadium likewise. Verify rather than assume, and use every
   matching string in block 6.

C. 2026 meeting. Confirm whether the two clubs have met in 2026 in
   game_level_2026.csv, and at which raw Round_num.

D. Roster check. For every player named in blocks 2, 4, 6 and 7, report whether
   they appear in game_level_2026.csv, and if so at which club. Anyone absent is
   retired or delisted. Anyone at a different club than their historical record
   shows must be labelled with both. Run this before writing any block that
   describes a player as current. This check exists because a draft described
   Jack Steele as a fading St Kilda player when he is not on the list at all.

## The blocks

1. Active streaks. Any player at either club with a run of 3 or more consecutive
   games ranked top three by Exp_Votes in game_level_2026.csv. Give raw
   Round_num, opponent, Exp_Votes and in-game rank for each game in the run.
   State explicitly if no player qualifies.

2. Actual Brownlow votes in this fixture, home and away, 2007 to 2025. Report
   total meetings. For every player with two or more polls: club, meetings
   played, polls, zeros, total votes, and season/round/vote detail. Flag any
   player whose polls are not contiguous. Key the detail lookup on name AND
   club: a player who has appeared for both clubs will otherwise print one
   merged list against both rows.

3. Exp_Votes in the 2026 meeting if one exists. Top three by Exp_Votes, with
   club.

4. Coaches votes in this fixture, from coaches_votes_all.csv. Player.Name
   carries a club suffix, e.g. "Dean Cox (WCE)". Report leaders by total votes
   with poll counts, then the recent record for current players only, per check
   D. Before reporting, inspect the 2020 rows for this fixture specifically: the
   known duplication is per-fixture, not season-wide, appearing as identical
   per-player vote values repeated across R18 to R23. Exclude 2020 only if that
   pattern is present here, and say which way you went.

   Exemption to the three-number rule: coaches_votes_all.csv holds rows only
   for players who polled. Meetings played and zero-vote games are not
   derivable from this file. Report total votes and poll counts only, and
   state that the denominator is unavailable rather than inferring one.

5. 2026 Exp_Votes season totals, top 8 per club, with games played.

6. Venue record, actual votes, all opponents, using every venue string from
   check B. Report season range covered and total H&A games at the ground. List
   players with six or more polls: club, polls, votes. Then separately, for each
   club's 2026 top 8 from block 5, their individual record at that ground:
   games played, polls, zeros, votes. The per-player split is the part that
   matters. A club-level venue table cannot answer whether a specific player
   travels well.

7. Droughts against this opponent, home and away only. For each club's 2026 top
   8: meetings played, polls, votes, and the date and vote value of the most
   recent poll. Flag anyone with three or more meetings and zero career polls
   against this opponent.

## Block 8, player deep dive

Run this automatically on every player who survives the judgment pass in step 2,
before drafting. It is the difference between a number and an insight: a
fixture record means nothing until it is read against the player's own baseline.

For each shortlisted player, from fitzroy_stats_all.csv, home and away only:

  a. Career votes by opponent. For each opponent: meetings played, polls, zeros,
     total votes, votes per game, and the season and vote value of the most
     recent poll. Sort by votes per game ascending. State where this fixture's
     opponent ranks among opponents faced five or more times, and how many
     opponents clear that threshold.

  b. Career votes by venue, same shape, sorted by votes per game ascending.
     State where this fixture's ground ranks among grounds played five or more
     times.

  c. Career totals: games, polls, votes, votes per game. This is the baseline
     both tables are read against. A rate is meaningless without it.

  d. Vote composition against this opponent and at this ground: how the total
     splits across 1, 2 and 3 vote games. Three single votes and one 3-vote game
     both total 3, and they are different stories.

  e. If the player has changed clubs, label which club each opponent and venue
     record was earned at. A record earned elsewhere is still true and still
     usable, but the copy must name the club or the tweet asserts something
     false.

Reading it. The opponent or venue is only worth writing about when it sits near
an extreme of the player's own distribution. Isaac Heeney against St Kilda was
second lowest of 17 opponents at 0.23 against a career 0.44, which is the story.
Mid-table is not a story and should be discarded rather than dressed up.

Also check that the claim is not an artefact of the fixture list. Clayton Oliver
had never faced Port Adelaide as a Giant, which was true and meant nothing: the
two clubs had not met since he moved. Before drafting a never or a first, check
whether the opportunity existed.

## Four unsettled scoping questions

Career-scoped vs fixture-scoped. Block 7 currently counts every career meeting
against the opponent regardless of the player's club at the time, so its meeting
counts exceed block 2's fixture count. Brodie Grundy's poll against St Kilda was
at Collingwood; Charlie Curnow's was at Carlton. Both are true and neither
belongs in a tweet about this fixture without the club named. Pick one scope for
the script and apply it consistently, or report both columns explicitly.

Club alias merging. Where a club name changed across the period, state whether
opponent records were merged or split, per club, in the output.

Name-level vs name-and-club grouping. Block 6 grouped on name and club splits a
player who changed clubs across two rows, which can drop him below a poll cut
that name-only grouping would clear. Lance Franklin at York Park and Josh
Kennedy at Adelaide Oval both behave this way. Report block 6 both ways wherever
the two differ, and label which grouping any drafted number uses.

Current-season games in career rates. 2026 votes are not public until count
night, so how a 2026 row reads depends on which file it came from. In
data_2026/afltables_2026.csv the votes column is null and those rows behave
exactly like the finals rows in fitzroy_stats_all.csv. In
predictions/game_level_2026.csv the same games are stored as zero, so .mean()
counts them rather than dropping them. See the finals denominator rule below.
Whether they belong in a career denominator is unsettled.
Excluding them keeps a career rate comparable across the season but makes it
answer a narrower question than "per game played". Including them drags every
career rate down by however many 2026 games the player has, for no reason except
that the votes have not been published yet. Pick one and apply it in every
block, because the current position is that .mean() decides it implicitly and
differently depending on which rows a given filter happened to leave in.

## Reading the output

The recon flags candidates, it does not pick them. Both hand-runs surfaced a
wrong headline that the raw numbers supported.

A drought only reads as a drought when the player is a live chance. Bradley Hill
at 16 meetings and never polled is not a story: he sits at 4.06 expected votes
for 2026 and holds 3 polls from 83 career games at the ground. Apply a floor on
2026 Exp_Votes before drought or streak logic earns a draft.

A career or fixture aggregate can hide a venue split that reverses it. Marcus
Bontempelli against Fremantle reads as near-automatic until it is split by
ground, where his away record at Perth Stadium is two polls from four meetings
against four from five at home. Always check block 6 against blocks 2 and 7
before drafting.

Cross-check any number that will appear in copy against a second block. Block 2
and block 7 should agree on polls and votes for the same player; where they do
not, the scoping question above is usually why.

Superlative claims must print the table they came from. Any draft containing
"only", "no other", "best", "worst", "highest" or "lowest" must print the full
ranked table it is drawn from, not just the leading entry. The Sam Walsh v
Brisbane draft claimed Brisbane was the only opponent he averaged more than a
vote against. Geelong at 1.14 and Port Adelaide at 1.11 also cleared it. The
recon had the data and the draft never asked for the ranking. A superlative is
the one claim shape where the supporting figure and the copy can diverge without
either being individually wrong: "highest of 17" was true, "the only one" was
not, and only the full table shows the difference.

Finals denominator. Votes per game is computed over vote-eligible games, meaning
home and away rows only. Finals rows carry null votes, not zero, and pandas
.mean() silently drops them, so any figure computed with .mean() over a column
that still contains finals is already using this convention by accident rather
than by choice. State the convention in every report. The consequence is that
one record yields two defensible numbers: Walsh v Brisbane is 1.20 per
vote-eligible game and 0.86 per game played, from 5 H&A meetings and 2 finals.
Both answer "how often does he poll against Brisbane" and they disagree, so the
denominator has to be named wherever the figure appears.

Null versus zero is not consistent across files, so the denominator depends on
which file the figure came from. fitzroy_stats_all.csv finals rows and
data_2026/afltables_2026.csv store unscored votes as null, so .mean() drops
them. predictions/game_level_2026.csv stores them as zero, so .mean() counts
them and drags every career average down. Recon reads the first, the app reads
the third. Any average votes per game figure must state which file it came from.

## Script hygiene

This section applies in autonomous mode only.

Write throwaway scripts to _tmp/ inside the working directory, never to
$env:TEMP. Run them as: python _tmp/name.py

Use literal relative paths only. No $env: variables, no PowerShell script
blocks, no inline multi-line PowerShell. If logic is needed, put it in a .py
file and run that file.

Clean up with: Remove-Item _tmp/*.py

This exists because every permission prompt in the first autonomous run was
triggered by the same two things: $env:TEMP expanding to an unknown value, and
inline script blocks. Both are avoidable. Literal paths and .py files are
matched by the allow rules in .claude/settings.local.json and run without
prompting.

## Filters that must be applied every run

Finals exclusion. Every block is home and away only. fitzroy_stats_all.csv can
be filtered on a digit round, but coaches_votes_all.csv numbers finals
continuously, so a semi-final appears as a plain round number and survives an
isdigit() filter. In the Port Adelaide v GWS run this smuggled the 2023 semi
final into block 4 and cost 10 votes from one player and 8 from another before
it was caught by hand. Filter finals explicitly by season round count or by
cross-referencing the fitzRoy fixture list, never by isdigit alone. Report the
number of finals excluded per file.

Club name canonicalisation before check D. Check D compares a player's
historical club against their 2026 club, and the two sources spell clubs
differently: Team = GWS against Home.team = Greater Western Sydney, Team =
Footscray against Home.team = Western Bulldogs, Kangaroos against North
Melbourne. Canonicalise both sides before comparing or check D flags every
player at those clubs as a club change every run. In the Port Adelaide v GWS run
it produced three false positives. Report the canonical mapping used.

## Facts file, required output

Every autonomous run that produces a draft must also write
drafts/<name>.facts.json alongside it. A draft without a facts file cannot be
posted, because draft_gate.py hard-fails on the missing sibling.

Schema, which must match draft_gate.py exactly:

    fixture        str
    round          int, display round
    raw_round      int, the AFLTables round number, one ahead of display
    source_files   list of str, every file the run read
    rates          list of {subject, value, denominator,
                            denominator_type, source_file}
    totals         list of {subject, value, source_file}
    ranked_tables  list of {subject, window, rows}
    superlatives   list of {claim_id, subject, scale, window, threshold,
                            threshold_unit, set_size, top5 [{rank, name,
                            value}], gap_to_rank_2, stricter_threshold,
                            survives_stricter, looser_threshold,
                            survives_looser, at_set_ceiling,
                            threshold_chosen_to_fit, source_file}
    base_rates     list of {claim_id, subject, event, base_rate,
                            base_rate_window, trials, observed_count,
                            p_observed, source_file}

round and raw_round are both exempt from the orphan-number check, because a
draft cites the AFL's round number and AFLTables' raw one and neither is a
claim about a player. Carry raw_round even when the copy never prints it.

denominator_type is one of the values in draft_gate.DENOMINATOR_TYPES. Vote
rates may only carry vote_eligible_games or matches_between_clubs. A rate may
never carry unavailable; where the denominator cannot be derived, state that in
the copy instead of printing a rate.

totals holds the raw counts a rate is read against. Block 8c mandates career
games, polls, votes and votes per game for every shortlisted player: the votes
per game lives in rates, and the games, polls and votes it is computed from live
in totals. Without the counts the gate treats them as orphan figures the moment
the copy prints them, which is the correct answer, because a rate with no
baseline is the thing block 8c exists to prevent.

A totals entry carries no denominator and no denominator_type, and the gate
hard-fails if either key appears. A figure with a denominator is a rate, never a
total; putting one in totals would route it around every denominator check.

Every ranked_tables entry must state its window, including the minimum meetings
threshold and whether the current season is included.

Any entry whose denominator_type is matches_between_clubs, or whose window says
anything about finals, must also carry three integers:

    rows_in          rows read for this entry before the finals filter
    finals_excluded  rows the filter removed
    rows_out         rows the figure was computed from

and rows_in minus finals_excluded must equal rows_out. The three share whatever
unit the entry counts in: matches for a figure about matches, player rows for a
ranking over players. This exists because a filter can drop rows it never meant
to touch and still report an honest zero. A season-to-max-round map built from
fitzroy_stats_all.csv, which starts in 2007, mapped 2006 to nothing, so every
2006 row compared false in both directions and disappeared: 24 meetings in, 23
out, no finals reported. The arithmetic catches that whether or not the run
understands why rows went missing.

Commit order note, recorded not fixed: 5ef1fcb landed this check before acac6a0
landed the CHECK 3 claim attribution, so a checkout of 5ef1fcb fails on any
draft citing a figure attributed by declaration.

superlatives records the depth behind a superlative that ranked_tables cannot
show: the size of the set, the gap from rank 1 to rank 2, and whether the claim
survives the threshold being moved in both directions. top5 carries five rows,
or the whole set when it is smaller than five. Where threshold_chosen_to_fit is
true the copy must print both the threshold and the set size inside that claim's
own scope, so the reader of the claim sees it was cut to shape rather than
finding the admission in another section. gap_to_rank_2 is checked against the first two
top5 rows and must agree with them to within 0.001, so carry top5 values at the
precision the gap was computed at rather than at display precision.

at_set_ceiling is true when rank 1 holds the maximum attainable value for the
set rather than the highest one observed: a player who has appeared in every
meeting the two clubs have played is at the ceiling, and no threshold can
dislodge him. Both survival flags must then be true, and the gate says so on
stdout, because survival proves nothing about a claim that had nowhere to fall.
A rate is almost never at a ceiling, so it is false there.

Every claim_id must appear in the draft as an HTML comment, <!-- claim: slug -->,
on the line immediately above the sentence it governs, not above the block that
sentence sits in. Its scope runs from the comment to the first sentence
terminator after it, which is ". ", "! ", "? " or a blank line. A comment covers
a sentence pair only where no terminator falls between them; a claim that
genuinely needs two sentences is written as two comments sharing one claim_id,
and the scope is their union. Both the superlative scan and the threshold
disclosure scan run against that narrowed scope. An entry with
no comment fails, a comment with no entry fails, and any superlative word
sitting outside every scope fails, which is what forces a superlative to carry
its depth rather than pass by being undeclared.

A claim comment also attributes figures. The orphan-number check normally asks
whether the subject of the entry carrying a figure is named nearby, but inside
a claim's scope it accepts any figure that claim's entry carries, because the
comment has already declared what the sentence is about. That is what lets a
sentence cite its own window, such as the number of meetings a ranking covers,
without repeating the player or the clubs to satisfy a name match.

base_rates carries the arithmetic behind a claim that something has not
happened. Copy asserts absence with a small set of words, and the gate treats
any of them as a trigger: never, no votes, yet to, zero, without a, drought,
hasn't polled, has not polled. A trigger must sit inside a claim scope, exactly
as a superlative must, and the claim governing it must carry a base_rates
entry.

The entry exists because none of those words says whether the silence is
surprising. That depends on how often the thing happens and how many chances
there were. A player who polls in one game in twenty and has not polled in four
meetings has done nothing at all: the record predicted the silence. So the
entry states the rate the event happens at, the window that rate was measured
over, the number of chances, what was observed, and the probability of seeing
that little. Where p_observed is at or above 0.50 the gate stops the draft,
because the absence is the most likely single outcome and the sentence is
describing the base rate rather than the player.

p_observed is checked against base_rate and trials the way gap_to_rank_2 is
checked against top5, to within 0.005, which is the slack a probability quoted
to two decimal places needs. Only observed_count of zero is recomputed, where
the expected value is (1 - base_rate) ** trials. Above zero, P(X = k) and
P(X <= k) are different numbers and the entry does not say which one it holds,
so the figure is shape-checked, faces the ceiling, and is otherwise taken on
trust rather than checked against a definition the gate would have to guess.

The zero trigger does not match "zero-vote" or "zero vote". That phrase is the
count label the three-number rule in the standing preamble requires of every
player record, and a denominator is not a claim that anything is absent. No
other token is narrowed and no category of prose is exempt: method prose
asserting that a filter never used isdigit is reworded, not excused, because a
check that exempts the sections its author finds inconvenient is not a check.

base_rates entries are attributable sources like rates and totals, so prose
inside a base rate claim can cite the entry's own figures. That is what lets a
sentence say "no votes against Essendon in 6 meetings" without the 6 orphaning
under the attribution check, since the trial count the claim rests on is
carried by the entry making the claim.

Sentence scope has a cost worth planning for: a claim sentence has to begin at
the start of a line, so wrapped prose usually needs its line break moved before
the comment can go in. Inside a tweet the comment goes inside the blockquote,
&gt; &lt;!-- claim: slug --&gt;, or the unquoted line breaks the quote. Strip the
comments before posting with python draft_gate.py --strip drafts/&lt;name&gt;.md,
which removes the whole line either way.

The run ends by executing python draft_gate.py drafts/<name>.md and reporting
the exit code. A non-zero exit is a failed run, not a warning.

The gate's own regression suite is tests/run_gate_tests.py, which runs every
fixture in tests/fixtures/ and compares each exit code against the one declared
alongside it. Any change to draft_gate.py runs it, and a non-zero exit is a
failed change, not a warning.
