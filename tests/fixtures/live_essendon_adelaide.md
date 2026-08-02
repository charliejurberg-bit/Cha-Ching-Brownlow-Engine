# Preview drafts: Essendon v Adelaide

**Fixture:** Essendon v Adelaide
**Round:** raw Round_num 22, display **Round 21**
**Date:** Sunday 2 August 2026
**Venue:** Marvel Stadium, stored by fitzRoy as `Docklands` (Essendon home)

Round derived, not assumed. The latest completed raw Round_num in
`predictions/game_level_2026.csv` is 21, a full nine-game round, so the next
fixture is raw Round_num 22. AFLTables round numbers run one ahead of the AFL's
official count, giving display Round 21.

Home club is **not** derivable from any file in this repository. No 2026 fixture
list is held here: `game_level_2026.csv` and `afltables_2026.csv` stop at the
last completed round, and every odds and predictor file carries season-long
Brownlow markets rather than match data. Essendon is recorded as home from the
AFL's own round listing for this match, per the copy rule that an unknown match
tag is looked up rather than constructed.

## Standing scope for every figure below

- Sources: `data_history/brownlow_votes_1990_2006.csv` concatenated with
  `fitzroy_stats_all.csv` for all career and all-time claims. Expected-vote
  figures come from `predictions/game_level_2026.csv`. Coaches votes come from
  `coaches_votes_all.csv`.
- Votes per game is computed over vote-eligible home and away games. Both
  history files store unscored votes as null, so `.mean()` drops them. The 2026
  file records a count for them instead, so no career average is ever taken
  from it.
- Every career rate excludes the current season. 2026 votes are not public until
  count night, and including them would drag every career rate down for no
  reason other than that the count has not happened. The clubs have not met in
  2026 in any case.
- Finals excluded everywhere. Coaches votes were filtered by cross-referencing
  the maximum home and away round per season, not by `isdigit` alone; no
  finals rows were present for this fixture.
- Grouped on fitzRoy player ID, not on name.
- Club naming reconciled across files: `Adelaide Crows` in `coaches_votes_all.csv`
  maps to `Adelaide` in the stats files, and the `(ADEL)` and `(ESS)` name
  suffixes map the same way. No Footscray or Kangaroos style mismatch applies here.

## Meeting cap

The clubs have met **44 times** in home and away football, 1991 to 2025.
Adelaide entered the competition in 1991, so 44 is the ceiling and a low meeting
count is a function of a player's career span, not an absence worth writing
about. No player is near
it: Dustin Fletcher leads on 22, and the most by anyone currently listed is well
below that.

---

# The drafts

## 1. Zach Merrett, the opponent he saves it for

> Round 21 at Marvel Stadium. Zach Merrett has 15 Brownlow votes from 11 home
> and away meetings with Adelaide, at 1.36 votes per vote-eligible game.
> <!-- claim: merrett-adelaide-best-vpg -->
> That is his best return against any of the 17 opponents he has faced five or
> more times, and more than double his career mark of 0.65.
>
> #AFLBombersCrows #Brownlow

> Four of those 11 meetings were three-vote games.
> <!-- claim: essendon-adelaide-fixture-most-votes -->
> He has polled in each of his last three, for 6 votes, and his 15 in the
> fixture trail only Scott Thompson's 18 across the whole history of it.
>
> #AFLBombersCrows #Brownlow

> The ground agrees with the opponent. At Docklands he sits at 0.74 votes per
> vote-eligible game from 88 games, third of the nine grounds he has played five
> or more times, and above his career rate.
>
> #AFLBombersCrows #Brownlow

**Supporting figures.** 11 meetings, 6 polls, 5 zero-vote meetings, 15 votes,
1.36 votes per vote-eligible game against a career mark of 0.65 from 247 home
and away games, 74 polls and 160 votes. Vote composition against Adelaide: 5
zero-vote meetings, one 1-vote game, one 2-vote game, 4 three-vote games. Last
three meetings all polled: 2024 at Adelaide Oval for 3, 2024 at Docklands for 2,
2025 at the M.C.G. for 1.
<!-- claim: essendon-adelaide-coaches-votes-most -->
Coaches votes in the fixture: 55 from 7 polls, the most of any player over the
24 meetings from 2006 onward for which coaches votes exist, out of the 44 the
clubs have played, though that file holds rows only for players who polled, so
meetings played and zero-vote games are not derivable from it and no rate is
quoted. One club throughout, so no club-change caveat applies.

Cross-check: block 2 and block 7 agree on 11 meetings, 6 polls and 15 votes.
Merrett has faced Adelaide 11 times against a 44-meeting ceiling, so the claim
is not an artefact of a thin fixture list.

<!-- claim: merrett-adelaide-best-vpg -->
Full ranked table for the "best return" claim, every opponent Merrett has faced
five or more times, sorted by votes per vote-eligible game descending. All 17
opponents clear the threshold, and 2026 is excluded throughout.

| Opponent | Meetings | Polls | Zeros | Votes | Votes/game |
|---|---|---|---|---|---|
| Adelaide | 11 | 6 | 5 | 15 | 1.36 |
| North Melbourne | 16 | 8 | 8 | 19 | 1.19 |
| Melbourne | 11 | 4 | 7 | 10 | 0.91 |
| Hawthorn | 15 | 7 | 8 | 12 | 0.8 |
| Brisbane Lions | 14 | 5 | 9 | 11 | 0.79 |
| Gold Coast | 14 | 4 | 10 | 11 | 0.79 |
| West Coast | 14 | 5 | 9 | 11 | 0.79 |
| Sydney | 18 | 6 | 12 | 14 | 0.78 |
| Collingwood | 18 | 5 | 13 | 11 | 0.61 |
| Richmond | 17 | 5 | 12 | 10 | 0.59 |
| Greater Western Sydney | 14 | 4 | 10 | 8 | 0.57 |
| Fremantle | 13 | 3 | 10 | 7 | 0.54 |
| Geelong | 15 | 3 | 12 | 6 | 0.4 |
| Port Adelaide | 15 | 4 | 11 | 6 | 0.4 |
| Western Bulldogs | 14 | 2 | 12 | 4 | 0.29 |
| St Kilda | 13 | 2 | 11 | 3 | 0.23 |
| Carlton | 15 | 1 | 14 | 2 | 0.13 |

## 2. Jordan Dawson's record against Essendon is a Sydney record

> Round 21 at Marvel Stadium. Jordan Dawson leads Adelaide's 2026 expected votes
> on 15.9 from 16 games, clear of Izak Rankine on 9.7. He has met Essendon 11
> times for 3 Brownlow votes, 0.27 per vote-eligible game against a career mark
> of 0.52.
>
> #AFLBombersCrows #Brownlow

> That 0.27 is two clubs, not one. 6 of the 11 meetings came as a Sydney player
> and none of them produced a vote. In the 5 since he joined Adelaide he has
> polled twice for 3 votes, and the most recent meeting, in 2025, brought 2 of
> them.
>
> #AFLBombersCrows #Brownlow

**Supporting figures.** 11 meetings, 2 polls, 9 zero-vote meetings, 3 votes,
0.27 votes per vote-eligible game, against a career mark of 0.52 from 153
vote-eligible home and away games, 40 polls and 80 votes. Career-scoped, and the
clubs are named because the record was earned at two of them: 6 meetings for
Sydney between 2018 and 2021 for 0 votes, 5 for Adelaide between 2022 and 2025
for 3. Vote composition against Essendon: 9 zero-vote meetings, one 1-vote game,
one 2-vote game, no three-vote game. Both polls came as an Adelaide player, and
the more recent of them is the most recent meeting of the 11.

Essendon ranks 4 of the 17 opponents Dawson has met five or more times, sorted
by votes per vote-eligible game ascending, so it sits among his leaner matchups
without being the leanest.
<!-- claim: dawson-essendon-lowest-at-10 -->
No superlative is claimed and none is available:
Essendon is his lowest opponent only if the threshold is raised to 10 meetings,
which cuts the field to 6 and is a threshold chosen to fit the claim rather
than one the claim survives. At the block 8 minimum of five, Sydney on 0.0,
Melbourne on 0.11 and Carlton on 0.22 all sit below Essendon.

This is a candidate, not a pick. The Adelaide-era sample is 5 meetings, too thin
to carry a claim of its own. It is offered as the reason the 0.27 career figure
should not be read as a fixture effect, not as evidence of the opposite one.

Full ranked table for the rank claim, every opponent Dawson has met five or more
times, sorted by votes per vote-eligible game ascending. 2026 is excluded
throughout, and meetings earned at Sydney are included, which is why Sydney
appears as an opponent for the meetings played since he joined Adelaide.

| Opponent | Meetings | Polls | Zeros | Votes | Votes/game |
|---|---|---|---|---|---|
| Sydney | 5 | 0 | 5 | 0 | 0.0 |
| Melbourne | 9 | 1 | 8 | 1 | 0.11 |
| Carlton | 9 | 1 | 8 | 2 | 0.22 |
| Essendon | 11 | 2 | 9 | 3 | 0.27 |
| Collingwood | 12 | 3 | 9 | 4 | 0.33 |
| Geelong | 9 | 1 | 8 | 3 | 0.33 |
| Brisbane Lions | 8 | 2 | 6 | 3 | 0.38 |
| Fremantle | 7 | 1 | 6 | 3 | 0.43 |
| Hawthorn | 9 | 2 | 7 | 4 | 0.44 |
| Greater Western Sydney | 10 | 2 | 8 | 5 | 0.5 |
| North Melbourne | 9 | 4 | 5 | 6 | 0.67 |
| Gold Coast | 10 | 3 | 7 | 7 | 0.7 |
| Western Bulldogs | 7 | 3 | 4 | 5 | 0.71 |
| West Coast | 10 | 3 | 7 | 8 | 0.8 |
| Port Adelaide | 11 | 4 | 7 | 9 | 0.82 |
| St Kilda | 8 | 4 | 4 | 9 | 1.13 |
| Richmond | 7 | 4 | 3 | 8 | 1.14 |

## Blocks that returned nothing

- **Block 1, active streaks.** No Essendon player has a run of three or more
  consecutive games ranked top three by expected votes. Adelaide has two runs,
  Jordan Dawson's 5 and Izak Rankine's 3, but neither runs to raw Round_num 21,
  so neither is active.
- **Block 3, the 2026 meeting.** Not applicable. Essendon and Adelaide have not
  met in 2026.
