# Handover: TikTok market decks, 17 September 2026

A TikTok photo carousel per Brownlow market, six selections each: three safe,
two value, one longshot. **The 3 Vote Games deck is built and rendered.** The
other markets have not been started.

Count night is **Monday 21 September**, so the useful life of anything here is
three days from 18 September.

---

## Where it stands

The eight-slide deck exists as PNGs and has not been posted yet. Prices were
re-read on the morning of **18 September** and the deck re-rendered against them:
two of the six had moved, Ashcroft $2.50 to $2.30 and Daniel $11.00 to $9.00,
both shorter, both still positive. The review copy on the phone is the artifact,
which now carries all eight slides.

| Where | What |
|---|---|
| `drafts/tiktok_3votes/` | the eight 1080x1920 PNGs, gitignored |
| `OneDrive/Pictures/ChaChing Slides/` | the same eight, synced so the phone can see them |
| `drafts/tiktok_3votes_2026.md` | caption, hashtags, slide table, cautions |
| https://claude.ai/artifact/F461Tto1oG6oiMMHJtxuQY | the review page: all eight slides, the figures, the caption, the four open calls |

The artifact is current as of 18 September. The rejected layout mockups it used
to carry are still published as `lay-a/b/c.jpg` and `action-*.jpg` on it, unreferenced
by the page; the local originals are in `drafts/tiktok_market/`.

## New files, all untracked

| File | Job |
|---|---|
| `scripts/sb_3vote_board.py` | fetch Sportsbet competition 16767 and price all 1,152 selections against the model. Writes `data_betting/sb_3vote_board.csv` |
| `scripts/afl_headshots.py` | the AFL's cutout headshot for any player, by AFLTables name. Caches to `ChaChingContent/headshots/` |
| `scripts/tiktok_market.py` | the deck: cover, six pick slides, closer, plus the caption draft |

`data_betting/sb_3vote_board.csv` is untracked and probably should stay that
way; it is a price snapshot, not a data source.

## Running it

```bash
python scripts/sb_3vote_board.py --top 25   # refresh prices, see the best edges
python scripts/tiktok_market.py             # rebuild all eight slides
python scripts/tiktok_market.py --only cripps   # one slide, while iterating
```

`tiktok_market.py` copies to the OneDrive folder on every run; `--no-phone`
skips that.

## The six selections

Prices read off Sportsbet the morning of 18 September. **They move**: 101 of
1,150 selections moved in the 24 hours before this deck was first built and 97 in
the 24 hours after, so re-run `sb_3vote_board.py` before posting and re-render.

| Tier | Player | Game | Price | Model | Fair |
|---|---|---|---|---|---|
| Safe | Isaac Heeney | R23 v Essendon | $2.30 | 80% | $1.24 |
| Safe | Patrick Cripps | R11 v Port Adelaide | $1.65 | 82% | $1.22 |
| Safe | Will Ashcroft | R17 v Geelong | $2.30 | 70% | $1.43 |
| Value | Caleb Daniel | R4 v Carlton | $9.00 | 65% | $1.54 |
| Value | Oliver Dempsey | R22 v Essendon | $8.00 | 44% | $2.30 |
| Longshot | Tom Papley | R4 v West Coast | $21.00 | 22% | $4.51 |

Caleb Daniel is the biggest edge on all 207 games: coaches' maximum 10 that
night, model 65%, and the price drifted from the $8.00 on the slip out to $11
and has since come half of the way back to $9.00. Five of the six are already on `data_betting/brownlow_slip_2026.csv`;
Heeney, Cripps and Ashcroft are not, because the flat $5 staking skipped the
short-priced end.

## Decisions already taken, so they do not get re-litigated

- **Layout A**, the price as the hero figure, on the **AFL cutout headshot**
  over a club colour wash. Layouts B (the book's price beside the model's fair
  price) and C (the model's chance as the hero) were built and rejected; the
  mockups are in `drafts/tiktok_market/` if either is wanted back.
- **The longshot chip is a gold outline, not a third hue.** Midnight Turf has
  emerald and gold and nothing else that is not a loss colour. An earlier
  mockup used a mauve that is not in the palette.
- **The round leads the fixture line**, at 38px against the fixture's 24px. A
  carousel slide gets read out of order, so which game it is has to survive
  alone. The club name is no longer on the slide at all; it is on the jumper
  and in the wash.
- **The cover is the headline and the six prices, nothing else.** "BEST PICKS
  FOR THE BROWNLOW" over "TO POLL 3 VOTES" in emerald, then the price grid and
  SWIPE. The "six picks from 207 games" line and the 207 / 19 / 93 credentials
  row were cut on 18 September as too much to take in; those facts live in the
  caption and on the closer.
- **Three stat cells are fixed and three vary.** Disposals top left, score
  involvements and coaches votes opening the second row, because a fixed
  midfield set put "3 CLEARANCES" on the slide arguing Dempsey should have
  polled the 3, which is the slide arguing against itself.

## Open questions, none answered yet

1. **Picks or bets.** Five of six are on the slip. If the deck should be the
   position rather than the board, Heeney, Cripps and Ashcroft come out and Sam
   Walsh, Wayne Milera and Shai Bolton go in.
2. **Dempsey's third and sixth cells.** "2 marks inside 50" and "89% time on
   ground" are the weakest figures in the deck. His game genuinely reads thin on
   paper, which IS the pick's thesis (the book prices disposals, the coaches
   gave him the max), but the two filler cells could be dropped for a four-cell
   row on that slide alone.
3. **The gambling line.** The closer carries `18+ GAMBLE RESPONSIBLY` and the
   caption carries the help line. Both were added on judgement, not on a
   decision. TikTok may restrict reach on the post regardless.
4. **Which market next.** Placings is done (see below). The original ask was a deck per market. Candidates
   with a real board behind them: poll a vote (1+), 10+/15+/20+/25+/30+, top 3
   / top 5 / top 10 finish, team totals. The market book at
   https://claude.ai/artifact/3qxUeNUQbjnJPZKGTGdsgR has 3,131 selections across
   five books, and `handover_2026-09-16_betting_strategy.md` says which
   estimator prices which market. **Do not price a 1+ or 2+ market off the
   per-game sampler**; that file's table is the authority.

## The placings deck, built 18 September

One carousel across Sportsbet's top 3, 5, 10 and 20 finish boards, not four
decks: top 3 and top 5 have no short-priced runner the model rates above the
book, so a deck per board had no honest safe tier on two of them. Charlie chose
the single deck and chose to keep the SAFE PICK chip even though safe here
means 37 to 48%.

| Where | What |
|---|---|
| `scripts/sb_placings_board.py` | fetch the four boards (competition 6136) and price them off the season simulator. Writes `data_betting/sb_placings_board.csv`. `--check` backtests it |
| `scripts/tiktok_placings.py` | the deck. Draws through `tiktok_market.py`'s functions |
| `drafts/tiktok_placings/`, `drafts/tiktok_placings_2026.md` | slides and caption |
| `OneDrive/Pictures/ChaChing Slides/Placings/` | the phone copy, a subfolder so file names never collide |
| https://claude.ai/artifact/NL6fbRgdgp9UeuUidZteTx | the review page |

```bash
python scripts/sb_placings_board.py --top 40   # refresh prices
python scripts/tiktok_placings.py              # rebuild the eight slides
```

| Tier | Player | Board | Price | Model |
|---|---|---|---|---|
| Safe | Harry Sheezel | Top 10 | $2.50 | 48% |
| Safe | Sam Walsh | Top 20 | $3.50 | 43% |
| Safe | Jason Horne-Francis | Top 10 | $3.50 | 37% |
| Value | Shai Bolton | Top 20 | $12.00 | 39% |
| Value | Will Ashcroft | Top 3 | $13.00 | 20% |
| Longshot | Clayton Oliver | Top 10 | $71.00 | 18% |

All six are positive on the 11 September book's blended view too, not just the
model. Bolton and Oliver are already on the slip.

**The simulator is a rebuild and is not bit identical to the book.** The
recipe in memory (sharpen P**1.4, the sigma schedule, the conditional sampler)
did not reproduce the book to the decimal; the closest variant normalises each
game's columns, sharpens, and normalises again. It sits 0.3 points from the
book on average at top 3 and 1.4 at top 10, and it passes its own backtest on
all four boards (top 3: 53.7 said, 54.0 happened; top 5 89.6 / 90.0; top 10
179.4 / 178.7; top 20 359.3 / 357.0). Internal only: the deck claims no
accuracy figure.

**`tiktok_market.py` was generalised, not forked.** Each pick now carries its
market's wording (`mast`, `lead`, `qual`, `note`, `cover_label`), `draw_cover`
takes the subtitle and `draw_closer` the prose lines. The 3 vote deck was
checked byte-identical by SHA1 before and after.

**Two cells fixed, four per player.** Projected votes and coaches votes down the
left column; the other four make that player's case. A fixed set put "1 GAMES AS
FAVOURITE" and "1 COACHES BOG" on the Oliver slide; his real case is 1st in the
league for contested possessions a game and 4th for clearances.

Open, none blocking: there is no top 5 pick though the cover names top 5 (Lachie
Neale $5.50, 28%, is the candidate), and whichever deck posts second needs its
board re-run that day.

## Things that will bite the next session

- **`drafts/` is gitignored and local, so nothing in it reaches the phone.**
  That is why the first deck never appeared in TikTok's picker. The route is
  `OneDrive/Pictures/ChaChing Slides/`, which `tiktok_market.py` now writes to
  on every run. OneDrive files may still need saving to the camera roll before
  TikTok's picker offers them.
- **Score involvements is `Score_Involvements_Actual` from the footywire join,
  never the engineered `Score_Involvements` column in game_level.** The
  engineered one reads 5 for Cripps' round 11 where the real figure is 10.
  `tiktok_market.py`'s `STATS` registry routes the key to the right file; do not
  shortcut it.
- **Two board selections do not match and never will**: both are
  "Bailey J. Williams", refused by the uniqueness guard rather than guessed.
  Their games' "any other player" buckets are flagged `suspect` in the CSV.
  Never put a pick in one of those games without checking by hand.
- **The closer's site screenshot is dated.** `ChaChingContent/_site_hero.jpg`
  was captured 16 September and its countdown reads "Sept 21, 5 days". It is
  three days now. The text is small enough to be unreadable on a phone, but
  retake it if the closer is ever enlarged.
- `fetch_match_chains.UA` is a bare user agent **string**, not a header dict.
  `afl_headshots.py` wraps it as `HDRS`; anything else importing it must too.
