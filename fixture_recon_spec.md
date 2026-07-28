# Fixture recon spec

Status: written 28 July 2026. Hand-run twice before being written down, against
Fremantle v Western Bulldogs and St Kilda v Sydney. Not yet a script.

Purpose. Given one fixture, produce the retrospective material a preview tweet
can be built from. Everything is retrospective. The recon never projects and
never comments on the upcoming game.

Intended end state: a script taking two team names, so this becomes a command
rather than a session. Two scoping decisions below must be settled first.

## Standing preamble

Recon only. Read-only. Do not edit, commit, or run anything. PowerShell and
Select-String only. Report and stop.

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

## The seven blocks

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

## Three unsettled scoping questions

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

## Script hygiene

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
