# Handover: betting strategy session, 16 September 2026

Count night is **Monday 21 September**. This file is the context for a separate
conversation about which bets to actually place and at what size. Read it instead
of re-deriving anything; the market book itself is the artifact, not this file.

**Market book:** https://claude.ai/artifact/3qxUeNUQbjnJPZKGTGdsgR (private,
Version 5). 3,131 selections, 600 markets, five books. The share link is pinned
to an older version, so move the share pin before sending it to anyone.

---

## What is in the book now

| Drop | What | Prices |
|---|---|---|
| 11 Sep | TAB, Betfair, Sportsbet, PointsBet, scraped | 3,452 |
| 16 Sep (1) | Dabble poll-a-vote, all 18 clubs | 363 |
| 16 Sep (2) | Dabble 2+ to 5+, most 2-vote games, team totals, team thresholds | 936 |
| 16 Sep (3) | Dabble 6+ to 36+ | 820 |

Dabble is **phone only**. Nothing can scrape it; every price was dictated over
text to speech and transcribed. Names arrive mangled ("Sam Bicconi" for Sam De
Koning, "Thomas Barrow" for Tom Sparrow, "CJ from Melbourne" for Changkuoth
Jiath). See `[[dabble-market-and-book-rules]]` in memory for the matching method.

## Which estimator prices which market

This is the thing most likely to be got wrong from cold. There are two
simulators and the line between them was set by backtest, not by preference.

| Market | Estimator |
|---|---|
| 1+ vote (poll a vote) | Unsharpened sim + season-by-season isotonic recalibration |
| 2+ to 5+ votes | Unsharpened sim + recalibration (backtest picks it at every one) |
| 6+ votes and above | Sharpened (P**1.4) + per-player dispersion, i.e. the book's existing simulator |
| Team totals, team thresholds | Sharpened + the fitted weak-club correction |
| Most 2-vote games | Sharpened, ties split among tied players |

From 6 up the two estimators finish within ~2% of Brier, so the tie was broken
in favour of not splitting one market between two definitions. Below 6 the gap is
real: priced the sharpened way, the model claimed Mark Keane was a 67% chance of
3+ votes off a 2.3-vote season.

The sharpened rebuild reproduces the book's own rows at r = 0.9999 (128 alt-vote
lines), r = 0.9996 (86 player over/unders) and r = 0.9998 (40 team totals), so it
is the book's engine, not an approximation of it.

---

## The finding that should drive the strategy

**Per-game 3 votes is by far the model's strongest market**, measured on
`predictions/backtest_game_level.csv`, 3,468 walk-forward games, 2008-2025.

Raw `P_3` is not a probability: a game's column sums between 38% and 199%. It has
to be normalised within the game first. Normalised, it is almost perfectly
calibrated:

| Model says | n | Actually got the 3 | Breakeven price |
|---|---|---|---|
| 24.8% | 1,500 | 23.6% | $4.24 |
| 34.8% | 1,064 | 33.9% | $2.95 |
| 45.1% | 868 | 44.0% | $2.27 |
| 54.9% | 771 | 56.7% | $1.76 |
| 64.9% | 743 | 68.9% | $1.45 |
| 77.1% | 627 | 77.7% | $1.29 |

No calibration layer is needed. It is slightly UNDER-confident at the top end
(65% said, 69% happened), which is the safe direction.

Hit rates, all games:

- top pick alone: **56.6%**
- inside top 2: 76.8%
- inside top 3: 86.9%

**2026 is an unusually concentrated season.** Favourite P(3) median 57.8%, and
165 of 207 games have a favourite above 45%, against 74% of games in the
backtest.

### On covering two or three runners in a game

The instinct is reasonable but the arithmetic is against blanket coverage:

| Cover | Lands | Average price the set must beat |
|---|---|---|
| top 1 | 56.6% | $1.77 |
| top 2 | 76.8% | $2.60 |
| top 3 | 86.9% | $3.45 |

Covering two runners means paying the book's margin twice in one market. On a
per-game 3-votes market with ~20 runners the overround is likely 120-140%, so
blanket covering is a losing structure even though the strike rate looks good.

Where covering does earn its place is the games the model is unsure about:

| Favourite's P(3) | Share of games | top 1 | top 2 | top 2 needs |
|---|---|---|---|---|
| under 30% | 3% | 17.1% | 43.8% | $4.57 |
| 30 to 45% | 22% | 39.5% | 65.9% | $3.04 |
| 45%+ | 74% | 63.4% | 81.5% | $2.46 |

**The right framing is not "cover two, lay the favourite". It is: back each
runner whose price exceeds his normalised model probability.** Sometimes that is
two runners in a game, often it is none. The coverage falls out of the pricing
rather than being the strategy.

---

## The thing to fix before sizing anything

The book's verdict rule tests whether each row is individually positive across
three views. It says nothing about how many rows there are or how much they
overlap. The result:

- **463 rows are tagged BACK / SMALL BACK / SPECULATIVE.**
- Raw quarter-Kelly across all of them is **576 units**, roughly 5.8x a 100-unit bank.
- **38 players carry more than one vote-threshold bet.** Clayton Oliver has eight
  (15+ through 22+), Jye Amiss eight, Hugo Garcia seven. These are one opinion
  about one player sliced into eight tickets, not eight independent edges.
- **240 of the 463 sit below a 20% chance** and lose 94% of the time each.

The slip's group budgets cap this in the render, but the underlying list is too
long to act on as given. Charlie raised this unprompted and he is right.

Suggested approach for the next conversation:
1. Collapse each player's threshold ladder to **one** bet, the line with the best
   blended EV, and stake the player once.
2. Treat "the model likes fringe players to poll" as a single idea with a single
   budget, which the slip already does for the poll-a-vote board.
3. Prefer per-game 3-vote bets over season-total bets where both exist, on the
   calibration evidence above.

---

## Open items

- **The per-game "to poll 3 votes" board is NOT in the book.** Charlie intended to
  paste it on 16 Sep with his own value picks marked and the message arrived
  empty. Nothing has been built for it. This is the first thing to do.
- **Eight price chains remain contradictory**: Adam Cerra, Ben Keays, Blake Acres,
  Callum Brown, Mabior Chol, Massimo D'Ambrosio, Will Hayward, Ben McKay are each
  priced shorter for 2+ votes than for 1+. The poll-a-vote board was read first,
  so one of the two is stale. Shown as given, not reconciled. Worth a re-check on
  the phone.
- **Two dictated reads were dropped rather than guessed**: a duplicate "Mason
  Drew" on the 3+ board, and a second "Dan Curtin" at $23 on the 4+ board where
  Daniel Curtin already sits at $26.
- **One existing figure was corrected**: Deven Robertson's 1+ chance was carried
  as exactly 0.000, which no player who takes the field has, and the 2+ board
  priced him above his own 1+ line. Now 8.7%.

## Scratch work

All build scripts are in this session's scratchpad, not the repo:
`pollsim.py`, `seasonsim.py`, `fit_thresholds.py`, `infer_shifts.py`,
`build_dabble.py` / `build3.py` / `build4.py`, `assemble*.py`, plus the raw
dictations in `dabble_raw{,2,3,4}.py`. They are session-scoped and will be gone;
the memory file records the method so it can be rebuilt from the repo alone.
