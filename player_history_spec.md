# Player history spec

Status: written 4 August 2026. Not yet hand-run. Written from the Nathan Broad
recon of the same date, which produced every worked example below. Not a script.

Purpose. Given one player, produce the career material a retirement, milestone
or debut post can be built from. Everything is retrospective. The recon never
projects and never comments on games not yet played.

Intended end state: a script taking a player name and a mode, so this becomes a
command rather than a session. The unsettled scoping questions at the end must
be settled first.

Invocation is one line: "run player history on Patrick Cripps, retirement mode".
The name is resolved to an ID before anything else runs, per check A.

## Standing preamble

Interactive mode, default: read-only. Do not edit, commit, or run anything.
Report and stop.

Autonomous mode, only when the prompt says so explicitly: the Script hygiene
section governs. Throwaway python scripts in _tmp/ are permitted.

Key by ID, never by name. Every grouping, join, filter and ranking in every
block keys on the fitzRoy ID column. Two players named Josh Kennedy played in
the same era at different clubs; two Bailey Williamses are on lists in 2026. A
name-keyed career total merges them and reads as one enormous career. Name is
for display only, and a name printed next to a figure must have been looked up
from the ID that produced it, not used to produce it.

State the source file for every figure. The three sources disagree about what a
null means and about which columns exist, so a figure without a named file
cannot be checked. This is not a formatting preference. A career total that
silently spans two files with different coverage is a different number from the
one the reader thinks they are reading.

## The three sources

    data_history/fitzroy_stats_1965_2006.csv.gz   266,687 rows, 1965-2006
    fitzroy_stats_all.csv                         170,028 rows, 2007-2025
    data_2026/afltables_2026.csv                    8,280 rows, 2026

Same 81 columns in the same order across all three. Verified at the 2006/2007
seam: zero season overlap, no missing seasons, and zero of the 499 IDs shared
across that seam mapping to a different name. The 2025/2026 seam shares 566 IDs,
also with zero name mismatches.

Dtypes differ across the seam and the difference is inference, not schema drift.
A stat that did not exist yet is null, and null forces float64 where the later
file reads int64. Substitute and DOB are empty across the whole of 1965-2006 and
read as float64 against str. Concatenation coerces both sides. A run that needs
stable types passes them explicitly rather than trusting inference.

Do not read predictions/game_level_2026.csv in any block. It stores unscored
votes as zero where the three sources above store null, so .mean() counts them
and drags every career rate down. If a block would need it, say so and stop.

## Existence checks, before any block

A. Identity. Resolve the name to an ID against all three sources. Report the ID,
   the row count in each file, the season span, and every club the ID appears
   under. Report any other ID whose name matches, and stop if more than one
   survives rather than picking. Nathan Broad resolved to ID 12456, 170 rows in
   fitzroy_stats_all.csv plus 19 in the 2026 file, one club, 2016-2026.

B. Null ID sweep. Count rows in each source where ID is null, and list the
   players they belong to. The subject may be one of them, in which case every
   ID-keyed block silently drops those games and the run must stop. Even when
   the subject is clean, a null-ID player inside the comparison field is missing
   from every ranking, so the denominator is understated by however many such
   players cleared the threshold.

C. Games reconciliation. Report matches played, home and away rows, and finals
   rows, as three numbers that sum. Check the total against the published games
   figure in the prompt. Broad reconciled at 189 matches, 177 home and away, 12
   finals, against a stated 189. A mismatch here means the ID is wrong or a
   source is short, and every block downstream inherits it.

D. Club history. Report games per club with the season range of each. Where the
   subject changed clubs, every club-scoped block runs per club and the totals
   are labelled with the club they were earned at. A career record earned
   elsewhere is still true and still usable, but unlabelled it asserts something
   false.

E. Stat coverage for this subject. For every stat column, report non-null rows
   out of matches played. A stat that is null for part of the subject's own
   career cannot carry a career total without the gap being stated. Broad's
   Brownlow.Votes was null on 31 of 189 rows, being all 12 finals plus all 19
   games of an uncounted 2026, and his Bounces was null for one match where the
   whole 44-player fixture was null at source.

## The windows rule

Every rank prints on two windows: the stat's true window, and the AFL era from
1990. Both, every time, in the same table.

Never select a window per player. The window is a property of the stat, fixed
before the subject is known. A run that picks the window after seeing the ranks
is choosing the number it prefers, and the resulting claim describes the choice
rather than the player. This is the single easiest way to produce a true
sentence that misleads, because both windows are defensible and only one was
tried.

The true window per stat, from data_history/fitzroy_stats_1965_2006.csv.gz and
verified against the later files:

    Goals                        1897
    Kicks Handballs Disposals    1965
    Marks Behinds                1965
    Frees For, Frees Against     1965
    Hit Outs                     1966, with holes: 6.5% in 1974, 42.8% in 1975,
                                 continuous only from 1976
    Brownlow Votes               1984, after a gap: present 1931-1934, absent
                                 1935-1983
    Tackles                      1987
    Rebounds Clangers            1998
    Clearances Inside 50s        1998
    Contested Possessions        1999
    Uncontested Possessions      1999
    Contested Marks              1999
    Marks Inside 50              1999
    One Percenters Bounces       1999
    Goal Assists                 2003
    Time on Ground               2003

Where a stat's true window begins at or after 1990 the two windows coincide.
Print one table and say the windows are identical. Printing the same figures
twice under two labels implies a comparison was made that was not.

Hit Outs and Brownlow Votes carry holes inside their windows. Print the hole
with the rank. A rank measured across a window containing a season at 6.5%
coverage is not measured across that window.

Never print "all time" without the window in the same sentence. One Percenters
cannot reach past 1999 and a reader hears "all time" as the whole history of the
club. The phrase is accurate only for Goals.

## The blocks

1. Career totals and rates. Every stat column: total over all matches, per game
   over home and away only, best single game, and the non-null count from check
   E. This is the baseline every other block is read against. A rank without it
   is a position with no magnitude.

2. Stat rankings, three scales. For every stat, rank the subject by career total
   and by per-game rate, on both windows, against each of:

     club     every player who recorded the stat for that club
     league   every player who recorded the stat
     active   every player appearing in data_2026/afltables_2026.csv

   Three, not four. An earlier draft listed all time as a fourth scale, and it
   is not a population: it is the league scale on the stat's true window, which
   the windows rule already produces for every stat on every run. Listing it
   separately invites the same figure to be reported twice under two names, and
   a reader who meets it twice will take it for two findings. Where the copy
   wants the phrase, it is the league row on the true-window line, and the
   windows rule already requires that window to be printed beside it.

   Active needs its definition printed every time it appears. Appearing in the
   2026 file excludes the season-long injured and the delisted, which is not
   what a reader hears in "active". Say which set was used.

   The Broad run computed 204 ranks across the three scales, two windows and two
   metrics, of which ten survived suppression and all ten were club scale. Expect
   the league and active scales to produce nothing for most subjects. They are
   run anyway, because a subject who does reach the top 20 at league scale has
   the only rank in the set that needs no qualifying, and not running them makes
   that indistinguishable from not checking.

3. Venues. Matches by venue, ranked by count, all matches. Then for the two or
   three venues carrying most of the career, the subject's per-game rate at each
   against the career rate. Venue strings are normalised by fitzRoy to one value
   per ground across the whole span, so Docklands and Perth Stadium each appear
   once rather than under their sponsor names, but verify rather than assume and
   report every matching string used.

4. Finals record. Every final, listed individually with season, final type,
   venue and the stat line. Finals are few enough to print in full and they are
   the games a retirement post is built from. Report the finals count against
   matches played from check C. Where the subject played in a premiership,
   separate the premiership seasons and give games played in each, since a flag
   won off ten games is a different story from one won off twenty-four.

5. Season by season, rate against career. For every season: matches, home and
   away games, finals, total, per-game rate, and the difference from the career
   rate. The last three seasons are reported separately as their own table,
   because the question a retirement post asks is whether the player was still
   the player. Broad's One Percenters ran 3.682 in 2024 against a career 4.492,
   then 4.455 and 4.895, so the three-year average of 4.317 hid a rising finish.
   A trailing average is the wrong shape for that question and will answer it
   backwards.

   Flag any season played under a materially different format. 2020 ran
   shortened quarters and every counting stat in it is depressed league-wide.
   Broad's 2.769 that year is the lowest of his career and means nothing about
   his form. Rates expressed as percentages, Time on Ground being the only one,
   are unaffected and must not carry the flag.

6. Profile comparison, three kinds, each labelled with which kind it is.

   a. Manual. A named comparison the prompt asked for. Print both players'
      career totals and rates side by side on the same window, with both
      denominators.

   b. Nearest neighbour. Z-score each player's per-game rates across the stat
      set over the shared window, restricted to players clearing the games
      minimum, and rank by Euclidean distance from the subject. Print the ten
      nearest with their distances. This is a similarity heuristic and must be
      labelled one. It says two players produced similar numbers, not that they
      played alike, and a defender who never went forward will sit near every
      other defender who never went forward.

   c. Position group. Where a position is available, the same comparison
      restricted to the group. Position is not carried in the three sources, and
      as things stand this block cannot run at all.

      The blocker is identity, not depth. An earlier draft of this spec said
      position came from fetch_player_details_afl and was limited only by that
      endpoint reaching back to 2012. The real problem is that the endpoint
      keys on a different ID namespace: Nathan Broad is id 1032 there against ID
      12456 in the three stats sources, and 12456 appears nowhere in its output.
      There is no ID join. Restricting a comparison field by position would mean
      matching on name, which the preamble forbids, so the block does not run
      and the report says why.

      Depth is a second, smaller problem, recorded so it is not rediscovered.
      Even inside the 2012 floor the position column is absent for five of
      fifteen seasons: 2012, 2015, 2016, 2017 and 2018, leaving 447 of 672
      Richmond rows populated. Broad carries no position for his own 2016 to
      2018 seasons and reads MEDIUM_DEFENDER only from 2019. A block built on
      this would be describing the seasons the AFL happened to publish.

      Do not work around either problem by matching names. If the block is
      wanted, the fix is an ID crosswalk between the two namespaces, built and
      verified once, and that has not been done.

## Field and denominator

The field for a total is every player who recorded that stat, with no minimum.
The field for a rate is that field restricted by a games minimum, defaulted to
100 home and away games in that stat.

Print both denominators, always, on every rank. "Third at Richmond" is not a
claim until the reader knows whether the field is 238 or 45. Broad ranked third
of 238 on One Percenters total and third of 45 on the rate, and the two
sentences carry different weight.

The games minimum counts non-null rows for that specific stat, not matches
played. A player whose career straddles the stat's first season has fewer
qualifying games than games played, and qualifying him on the latter computes a
rate over a window he was only partly present for.

## Suppression

Omit any rank outside the top 20. A rank of 566 is not a finding and printing it
pads the output with material no post will use.

Report the count of suppressed blocks. Suppression that leaves no trace reads as
absence, and a reader who cannot see that forty ranks were computed and dropped
will take the survivors as the whole picture. Say how many were dropped and at
what threshold. Never drop a block silently.

Suppression applies to output, not to computation. Every rank is computed before
any is dropped, because the count of suppressed blocks is itself a finding: a
subject with two surviving ranks out of forty-six is a specialist, and that is
the post.

## Modes

Retirement. The full spec. Blocks 1 through 6, both windows, all three scales.
Emphasis on blocks 4 and 5: the finals record and whether the late-career rate
held. Career is closed, so every figure is final and no block needs a
provisional label.

Milestone. Blocks 1, 2, 3 and 5. Report the milestone count against check C and
name which number it is, since games played and matches in the data can differ
where a source is short. The career is open, so every total is provisional and
must be labelled with the date it was computed. Skip block 4 unless the
milestone is itself a finals milestone.

Debut. Blocks 1 and 6 only, and both run against the debut context rather than a
career. There is no career to rank, so block 2 is skipped entirely rather than
run on a handful of games. Report the club's debut history: most recent debutants
and how their first seasons went. Nearest neighbour runs against first-season
figures only and must say so, since a distance computed over one season is far
noisier than one computed over ten and will read as more meaningful than it is.

## Output

Three artifacts, all to drafts/, all named for the subject and mode:

    drafts/<slug>_<mode>.md          the full recon, every block, every window
    drafts/<slug>_<mode>_card.md     the card, one screen, the surviving ranks
    drafts/<slug>_<mode>_tweet.md    the templated draft

The markdown is the record and carries everything, including the suppressed
count. The card carries only ranks inside the top 20 with their denominators.
The tweet is a template with the figures substituted, never free prose, because
a template cannot introduce a claim the recon did not compute.

Every figure in all three names its source file. In the card and the tweet this
may be a footnote, but it may not be dropped.

## Integrity rules

ID keying. Stated in the preamble and repeated here because it is the rule most
easily lost when a block is written in a hurry: every grouping keys on ID.

Finals split between counts and rates. Counts use every match played. Rates use
home and away only. The two denominators are different numbers and both are
correct, so every figure names which one it used. Broad played 189 matches and
177 home and away, and his One Percenters read 4.50 per match or 4.79 per home
and away game depending only on that choice.

This is not merely a convention to state. Where a stat is null in finals rows,
as Brownlow Votes is, .mean() drops them and the home and away convention
happens by accident. Where the stat is present in finals, as every counting stat
is, .mean() includes them and the convention is violated silently. Filter finals
explicitly. Do not rely on nulls to do it.

Filter finals by round label, never by isdigit alone on a shared column. The
finals labels are EF, QF, SF, PF and GF across all three sources, and the 2026
file carries no finals yet.

Superlatives print the ranked table. Any claim containing only, no other, best,
worst, highest, lowest, first or last prints the full ranked table it came from,
not the leading entry. "Highest of 17" and "the only one" are both consistent
with the same top row and only the table separates them.

State the source file for every figure. Repeated from the preamble for the same
reason as ID keying.

Report the window and the field size in the same breath as the rank. A rank
carries three parts and any one missing makes it unreadable.

## Known traps

Replayed and round-robin finals share a round label. The 2010 drawn Grand Final
and its replay both store as GF in the same season, 84 rows across Collingwood
and St Kilda, with different stat lines in each. They are two matches and both
count. A Game_ID built as season plus round plus teams collides on that fixture
and will deduplicate a real game out of the record. The same shape appears
earlier: Richmond's 1924 semi-finals ran as a round robin with several matches
all labelled SF, and the 1972 semi-final against St Kilda was drawn and
replayed. All are finals, so all are excluded from rates and affect counts only.

Null IDs in the 2026 file. 70 rows carry no ID, across eight players at six
clubs: Charlie Cameron 20 games, Jack Ross 16, Billy Wilson 12, Jack Graham 10,
Jack Williams 9, and one game each for Archie Ludowyke, Aidan Schubert and Oscar
Ryan. Cameron's entire 2026 season is invisible to an ID-keyed run. Check B
exists to catch this. The consequence for a subject who is one of them is that
the run stops; the consequence for everyone else is that the comparison field is
understated, so the denominator printed alongside every 2026-inclusive rank is
low by up to eight players.

Two of those eight, Jack Graham and Jack Williams, are at the same club in the
same rounds, so they also collide with each other on any key using ID plus round
plus club. They are different players and neither is a duplicate row.

Height and weight are deferred. fitzRoy carries them on two endpoints and
neither is usable here yet. fetch_player_details_afltables returns HT and WT for
every player back to 1908 debuts, complete from the 1940s, but carries no ID
column at all: it keys on player name plus a cap number, which is exactly the
name matching this spec forbids. fetch_player_details_afl carries id and
providerId and is per season, but the earliest season with any data is 2012,
which is shallower than the stats already are. Adding height means either
accepting name matching or accepting a 2012 floor, and that decision has not
been made. Do not add it to a block until it has.

Weight is worse than shallow, it is poisoned. On fetch_player_details_afl the
weightInKg column stores a missing weight as zero rather than null: 472 of 672
Richmond rows across 2012 to 2026, including every one of Broad's eleven
seasons, which read 192cm and 0kg. A zero passes isna, passes notna, passes a
dropna, and then drags a mean toward nothing while looking like a measurement.
There is no way to tell a genuine missing weight from a recorded one without
treating zero as a sentinel, and nothing in the column says it is one.

So weight is excluded, and stays excluded even if height is built. Height on
the same rows is clean: no nulls, no zeros, and Broad reads a stable 192cm
across all eleven seasons. The two columns sit side by side and only one of
them is usable, which is exactly the shape that gets missed when a block pulls
both because they arrived together.

Team naming differs by file and by column. Playing.for and Home.team do not
always agree, the Bulldogs store as Footscray in some columns, and GWS stores as
both GWS and Greater Western Sydney. Check per file and per column, never across
files. The 1965-2006 archive was built against the same schema so it inherits
the same divergence.

## Script hygiene

This section applies in autonomous mode only.

Write throwaway scripts to _tmp/ inside the working directory, never to
$env:TEMP. Run them as: python _tmp/name.py

Use literal relative paths only. No $env: variables, no PowerShell script
blocks, no inline multi-line PowerShell. If logic is needed, put it in a .py
file and run that file.

Write every ranked table to _tmp/ as CSV alongside the report, one file per
rank, named for the stat, scale and window. A ranking summarised to a top ten in
prose cannot be rechecked, and the superlative rule requires the full table to
be available whether or not it is printed.

Clean up with: Remove-Item _tmp/*.py

## Unsettled scoping questions

Gate integration. draft_gate.py's facts schema is fixture-shaped: it requires
fixture, round and raw_round, and a player history draft has none of the three.
Either the gate grows a player mode or these drafts sit outside it. Until that
is decided, a player history tweet has no facts file and no gate run, which
means the superlative and base rate checks that govern fixture drafts do not
govern these. Say so on every tweet draft produced under this spec rather than
letting the absence pass as a pass.

Current-season games in career rates. 2026 votes are not public until count
night and the 2026 file stores them as null. For every stat other than Brownlow
Votes the 2026 rows are complete and belong in the denominator. For Brownlow
Votes they are null and .mean() drops them, which is the right answer by
accident. Decide whether a career rate spanning an incomplete season is labelled
as such, and apply it in every block.

Retired-player fields in the active scale. A subject who has retired does not
appear in the 2026 file, so the active scale ranks him against a field he is not
in. Either exclude the active scale in retirement mode or state that the subject
is being compared to a field he has left. The second is more useful and needs
the label to be honest.

Games minimum for the rate field. Defaulted to 100 above, which was the figure
used in the Broad recon and produced fields of 45 at club scale and 682 to 954
at league scale. It has not been tested against a subject with a shorter career.
A minimum that excludes the subject makes every rate rank unreportable, and the
run must stop and say so rather than lowering the threshold to admit him.
