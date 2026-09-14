# Cha Ching — Brownlow Medal Predictor & Betting Hub

AFL Brownlow Medal predictor plus a betting tracker. XGBoost model (v4.0) trained on 2007–2025 data. Dashboard live on Streamlit Cloud.

**Where things stand (14 September 2026):** the 2026 home and away season is
complete and fully predicted (207 games, coaches votes for all of them). The
count is **21 September 2026**; its engine is built, verified and pushed, and
the "Count night runbook" below is the whole procedure. What remains before it
is operational, listed under "Current priorities" in `project_brief.md`.

**Only the Betting Hub is personal.** The Brownlow section is the free public product, launched to AFL betting forums with no paywall and no paid tips; the Betting Hub is private and admin-gated. Treat any copy decision as public-facing unless it lives behind the gate.

> **Read `project_brief.md` first.** It contains the current page structure, the correct file sizes, the Midnight Turf colour tokens, and up-to-date known issues. The sections below cover architecture and constraints that change rarely.
>
> **Anchoring rule: locate code by function name or by a literal string, never by line number.** The brief carries no function line numbers and no function tables, deliberately: two earlier briefs carried tables and both went stale, the last recon finding one false entry for `dashboard.py` and six for `betting_hub.py`. Do not add them here either. Pages in particular are not functions, see "Dashboard pages".

## Quick start

```bash
# From brownlow_engine/
python -m streamlit run dashboard.py   # → http://localhost:8501

# Weekly in-season update (stats → odds → predictions)
python update.py

# Retrain model from scratch
python brownlow_model.py
python predict_2026.py
```

## Update chain

`python update.py` runs the nine step weekly chain: one R step (2026 stats) then
eight Python steps (odds, Betfair, ESPN, AFL predictor, Wheelo, predictions,
drafts, `site/landing.json`). The 2026 coaches fetch is commented out of it, see
below. Nothing in the chain stops on a failed step; read each step's exit code.
The 2026 home and away season is over, so the chain has nothing left to fetch
this year. One-off checks tied to a particular round are
recorded here.

**Routing check. The expected line is now `207 full / 0 no_cv`.** The 2026 home
and away season is complete at raw Round_num 25, 207 games, and
`data_2026/coaches_votes_2026.csv` holds every one of them: 1,346 rows, rounds 1
to 25. The no-coaches variant no longer engages anywhere in 2026. Anything other
than 207 / 0 means the coaches file has been damaged, and the first three
sections below say how.

**Where each round came from, because the two halves are not equally safe.**

| Raw rounds | Source | Safe to refetch |
|---|---|---|
| 1 to 23 | fitzRoy `fetch_coaches_votes()` | Yes |
| 24 and 25 | Hand-transcribed from afl.com.au | **No. A refetch deletes them** |

fitzRoy's feed stops at raw round 23 and has not moved since. The AFL publishes
the same votes in its "Coaches' votes, R<n>" articles, and **the AFL's official
round number is one behind AFLTables' raw `Round_num` in 2026**: the AFL's R23
is raw 24, its R24 is raw 25. Those two rounds were transcribed into the feed's
own schema by `scripts/append_coaches_2026_r24_r25.py`, which carries both
source URLs, refuses to append twice, and refuses to write unless the checks
below pass.

**The hazard this creates, stated plainly.** Running the fitzRoy coaches fetch
again overwrites the file with rounds 1 to 23 only and **silently deletes rounds
24 and 25**, dropping routing back to 189 / 18. `data_2026/fetch_coaches.R`'s
`write.csv` is unconditional and unguarded, which is why it stays commented out
of `update.py`'s `r_scripts`. `coaches_votes_2026_prev.csv` does **not** protect
against this: it predates the transcription. Re-run the append script to
recover, or restore the committed file.

**Two checks that make coaches-vote data verifiable, and should be used again.**

- **Every AFLCA game totals exactly 30.** Five-four-three-two-one from each of
  two coaches. A game summing to anything else is a transcription error.
- **The AFL's published season leaderboard is a free acceptance test.** Sum the
  file per player and compare. All 21 published figures across the two 2026
  articles reconciled exactly, which is what proved both the transcription and
  the pre-existing rounds at the same time.

**The feed mislabels rounds, and the fixture guard is load-bearing.** For a
period the feed published raw round 22's fixtures under the label "Round 23".
`predict_2026.py`'s per-round fixture guard catches this by checking each
coaches round's fixture set is a **subset** of the AFLTables fixtures for the
same round number, and drops the round if not. Subset rather than equality, so a
genuinely partial round survives. Do not weaken it to an equality or
byte-identity test: a copy with one vote edited walks straight through those
while still carrying the wrong round's fixtures, and the per-game routing then
reads a stale round as published and never engages the variant.

**Name reconciliation is already handled; do not pre-correct feed spellings.**
`features.resolve_feed_names()` maps the feed's spelling onto AFLTables'
(Harrison Petty to Harry Petty, De Goey to de Goey, O'Sullivan to OSullivan) and
prints an unmatched count. Transcribe names as published and let it report; the
2026 append resolved 1,319 exactly, 25 by surname plus team plus round, 2 by
override, 0 unmatched.

Background, still true and still relevant to 2027: the zero-source guard in
`features.py` (`ZERO_SOURCE_GUARD_STATS`, applied inside
`build_game_rank_features`) sets the **raw `Coaches_Votes` column** to NaN for a
game whose votes are all zero, not just the derived rank/pct/z triplet, and it
runs before the routing test. An unpublished game therefore reaches the
predicate holding NaN rather than 0, and any NaN-unsafe comparison reads that as
"votes published" and sends the game to the full model, so `model_nocv.pkl`
never engages. The predicate fixed in commit `800acc7` (`(s != 0).any()` to
`(s > 0).any()`) is NaN safe and was proven against raw round 23 while that
round was genuinely unpublished. Keep it NaN safe in any rewrite.

## Project structure

```
brownlow_engine/
├── dashboard.py          # Main Streamlit app — 9,130 lines. Brownlow pages + hub
│                         #   router + global CSS. NOT all pages: the Betting Hub
│                         #   pages render from betting_hub.py (except Predictions)
├── betting_hub.py        # Betting Hub module, imported by dashboard.py
│
├── brownlow_model.py     # Model training (v4.0) — runs once per season
├── predict_2026.py       # In-season predictor — run after each round
├── update.py             # Nine step weekly chain, ends with site/landing.json
│
├── scraper_stats.py      # Pulls player stats from Squiggle API → data_2026/
├── scraper_odds.py       # Scrapes multi-bookie odds from Oddschecker (undetected-chromedriver)
├── scraper_advanced.py   # footywire advanced match stats → data_advanced/. The
│                         #   ONLY source of real Score Involvements. See
│                         #   "Score involvements" below before touching it
├── build_score_involvements.py  # Joins the above onto fitzRoy IDs. Refuses to
│                         #   write below a 98% match rate; all twelve seasons
│                         #   currently join at 100.00%
├── fixture_recon.py      # Per-fixture PLAYER-level recon (blocks 1-8 of
│                         #   fixture_recon_spec.md) → gitignored drafts/. Review
│                         #   material, never post-ready. Team-level records are
│                         #   team_h2h.py's, not duplicated here
├── data_pull.py          # EMPTY, 0 bytes. Not a fetcher. The R paths that do
│                         #   work are fetch_extended_data.R and scripts/build_history.R
├── fetch_extended_data.R # R script for fitzRoy data (coaches votes etc.)
├── backtest.py           # Walk-forward backtest → predictions/backtest_game_level.csv
│
├── scripts/              # 36 tracked files. Three groups:
│   │                     #   count night: count_night.py (feed state + snapshot),
│   │                     #   count_tweets.py (the --watch drafter), count_sim.py
│   │                     #   (who wins from here), night_pack.py + night_sections.py
│   │                     #   (research pack), vote_milestones.py, keepalive.py
│   │                     #   post cards: *_card.py, round_votes_chart.py
│   │                     #   data builders: fetch_match_chains.py → data_chains/
│   │                     #   (read back by period_records.py), build_brownlow_seasons.py,
│   │                     #   append_coaches_2026_r24_r25.py, convert_history.py,
│   │                     #   reproject_2026.py, the coaches R fetches
│   │                     #   Nothing here feeds a page of the site. See "Count
│   │                     #   night and the Live Tracker" below
│
├── predictions/          # Model artifacts + CSV outputs
│   ├── model.pkl         # Trained XGBClassifier
│   ├── model_nocv.pkl    # No-coaches variant, for games whose coaches votes are
│   │                     #   unpublished. Idle in 2026 now: see "Update chain"
│   ├── backtest_game_level.csv  # Walk-forward per-game predictions, 2008-2025.
│   │                     #   The only out-of-sample set; every calibration uses it
│   ├── features.pkl      # Feature list (93 features)
│   ├── label_encoder.pkl # LabelEncoder for Margin_Bucket
│   ├── rank_stats.pkl    # Stats used for relative game features
│   ├── wheelo_features.pkl
│   ├── form_features.pkl
│   ├── game_level_2026.csv   # Per-game predictions (current season)
│   ├── season_2026.csv       # Season totals by player
│   └── season_projection_2026.csv  # Floor/ceiling projections (Monte Carlo)
│
├── data_advanced/        # footywire advanced stats, 2015 onward. Real Score
│   │                     #   Involvements plus metres gained, intercepts,
│   │                     #   centre clearances, effective disposals, TOG%
│   ├── advanced_<season>.csv        # One per season, as scraped
│   └── score_involvements.csv       # Joined to Season + Round_num + ID
│
├── data_chains/          # Per-player, per-QUARTER kicks/handballs/disposals from
│   │                     #   the AFL's play-by-play feed. The ONLY intra-game
│   │                     #   source anywhere near this repo. 2021 on. See
│   │                     #   "Player stats by quarter" below
│   ├── period_stats.csv  # One row per player per quarter. Tracked
│   └── raw/              # Fetch cache, 31 MB, gitignored. Refetched on demand
│
├── data_history/         # Pre-2007 archives. game_level_1990..2006.csv live here
│   │                     #   and NOT in predictions/, because AVAILABLE_SEASONS
│   │                     #   scans that directory and would offer the season
│   ├── brownlow_seasons_1924_1983.csv  # SEASON TOTALS only, no game attribution.
│   │                     #   See "Brownlow votes before 1984" below
│   └── fitzroy_stats_1965_2006.csv.gz  # Brownlow.Votes all-null before 1984
│
├── data_2026/            # Current season raw data
│   ├── afltables_2026.csv    # Player stats (from R/fitzRoy)
│   ├── coaches_votes_2026.csv    # Rounds 1-23 fitzRoy, 24-25 hand-transcribed.
│   │                             #   Do NOT refetch, see "Update chain"
│   ├── fetch_coaches.R           # Unguarded write.csv. Stays out of update.py
│   ├── bookmaker_odds.csv    # Wide: Player | Bookie1 | Bookie2 | …
│   └── best_odds.csv         # Long: player, best_odds, implied_prob, best_bookie
│
├── data_wheelo/          # Wheelo rating data (per-round, per-player)
│   ├── wheelo_all_seasons.csv
│   └── wheelo_2026.csv
│
├── data_betting/         # Betting Hub READ-ONLY fallback CSVs (4 files). Not the
│   │                     #   store — Supabase is. Nothing in the repo writes these.
│   ├── bets.csv          # Bet log (bet_id, date, match, market, selection, odds, result…)
│   ├── bets_prev.csv
│   ├── cha_ching_tips.csv
│   └── player_props_cache.csv
│
└── fitzroy_stats_all.csv      # Historical stats 2007–2025, 170,028 rows. This IS
                               #   the training range: brownlow_model.py and
                               #   backtest.py both prefer this file when it exists,
                               #   and neither filters by season
                               #   (fitzroy_stats_2015_2025.csv is the fallback;
                               #   fitzroy_stats_2007_2014.csv holds the earlier half)
    coaches_votes_all.csv      # Historical coaches votes 2006–2025
```

## Tech stack

| Layer | Tech |
|---|---|
| Dashboard | Streamlit (wide layout, collapsed sidebar) |
| Charts | Plotly. `paper_bgcolor`/`plot_bgcolor` are `rgba(0,0,0,0)`, transparent, so the Midnight Turf page shows through |
| Model | XGBoost `XGBClassifier` (multiclass: 0/1/2/3 votes) |
| Data — historical | fitzRoy (R package) via `fetch_extended_data.R` |
| Data — live stats | Squiggle API (`api.squiggle.com.au`) |
| Data — odds | Oddschecker scrape via `undetected-chromedriver` + BeautifulSoup |
| Data — coaches votes | fitzRoy `fetch_coaches_votes()` to raw round 23; afl.com.au round articles beyond it |
| Data — advanced stats | footywire match pages (`ft_match_statistics?mid=…&advv=Y`), 2015 onward |
| Serialisation | `pickle` for model artifacts |

## Model architecture (v4.0)

- **Algorithm**: `XGBClassifier` — predicts 0/1/2/3 Brownlow votes per player per game
- **Training data**: 2007–2025 H&A rounds only (finals filtered; string-labeled
  rounds → NaN). 19 seasons, 162,411 rows, 40.2% of them pre-2015. Measured, not
  assumed: see `project_brief.md`, "## Model". Do not restate this as 2015–2025
- **CV**: 5-fold `GroupKFold` grouped by season (no data leakage across seasons)
- **Sample weights**: last-5-rounds of each season weighted 2× (recency bias)
- **MAE**: **UNRESOLVED. Do not quote any MAE figure**, public or internal. The
  v1–v4 numbers (0.0954 / 0.0910 / 0.0902 / 0.0904) that this line previously
  stated as fact were all measured with a momentum leak in place, so none is
  comparable to the others or to the current model. `brownlow_model.py` prints
  them under the label "Pre-2026-audit figures"; its current printed baselines
  are 0.0953 full model and 0.1013 no-coaches. Re-run against the current model
  before any MAE figure is used anywhere. See `project_brief.md`, "## Model".
- **Feature count**: 93 total

**Feature groups:**
1. **Base** (28): raw stats (Kicks, Disposals, Goals, Clearances, etc.) + engineered ratios (`Kick_to_HB_ratio`, `Contested_rate`, `Disposal_efficiency`, `Score_Involvements`, `Impact_Score`) + game context (Margin, Is_Win, Coaches_Votes)
2. **Wheelo** (20, per `predictions/wheelo_features.pkl`; all 20 are in `features.pkl`): `RatingPoints`, `ExpVotes`, per-quarter ratings (`Rating_Q1`–`Q4`), equity components, ground ball gets, Supercoach, `TimeOnGround`, `DisposalEfficiency` + `Rating_Q4_premium`, `Best_quarter_rating`
3. **Relative game** (~44): per-stat rank/percentile/z-score within each game (`{stat}_game_rank`, `_game_pct`, `_game_z`); BOG and Top3 flags for disposals, coaches votes, impact, rating
4. **Form/Momentum** (3): `late_form_ewm` (EWMA span=5 of prior rounds — no lookahead), `momentum_cv`, `momentum_disp` (last-6 vs first-6 game averages)

**These four counts do not sum to 93 and are not all verified.** Only the total
(93, from `features.pkl`), Wheelo (20) and Form/Momentum (3) are backed by
artifacts. Base and Relative game are inherited from an earlier brief and no
artifact defines either group, so treat both as approximate. Count from
`features.py` before relying on them.

**Prediction outputs** (per game): `P_1`, `P_2`, `P_3`, `Poll_Prob` (P_1+P_2+P_3), `Exp_Votes` (weighted expected value).

**None of these add up within a game.** The model scores each player's row on
its own, so a 2026 game's `P_3` sums anywhere from 38% to 199% (112 of 207 over
100%) and its `Exp_Votes` from 3.8 to 8.3 rather than 6. Two consequences:

- **Displayed probabilities are fitted, totals are not.** `_fit_game_probs` in
  `dashboard.py` (commit `a39fe1b`) runs iterative proportional fitting over
  players x {0,1,2,3} so each game hands out one 3, one 2 and one 1, and writes
  `P_1_game`/`P_2_game`/`P_3_game` beside the raw columns inside `load_game` and
  the career loader. Game Analysis P(3) and the Player Profile game log read
  them. The joint fit beat dividing by the game total on the 3,467 backtest
  games (P(3) Brier x1000 13.54 raw, 13.14 divided, 13.01 fitted). Keying is on
  name plus ID, because ID is blank on 92 rows of 2026 and pandas 3 turns a
  blank into a missing key rather than the string "nan".
- **Fitting `Exp_Votes` itself is parked until after count night.** It would
  move public totals a week before the count (Heeney 22.9 to 21.1, Gawn 17th to
  14th, Daicos 48 to 46 on the 3-2-1 board). A source fix belongs in
  `predict_2026.py`, `brownlow_model.py` and `backtest.py`, which all compute
  `Exp_Votes` from the raw columns. Any sampler of a game's 3-2-1 must condition
  within the game (see `scripts/count_sim.py`), never draw the three columns
  independently.

**Season projection**: Monte Carlo (10,000 simulations) over completed rounds →
10th/90th percentile floor/ceiling. Two things about it are easy to get wrong.

- **Each game is sampled with its OWN probabilities.** Averaging a player's
  p1/p2/p3 across his season and drawing `multinomial(games_played, p_avg)` is
  mean-preserving, so totals and rankings stay right and nothing looks broken,
  but it inflates the variance and made every band on the board too wide in the
  same direction (2026 top 15: 14.5 votes where the model implies 9.2, a 36%
  overstatement). A player's games are independent draws from DIFFERENT
  categorical distributions; there is no averaging step to be had. Do not
  reintroduce one for speed.
- **The displayed ceiling is `max(p90, the 3-2-1 total)`, and the lift lives in
  `dashboard.py`, not in the CSV.** The two boards describe one season, so a
  reader who toggles must never see a total on one that breaks the stated
  maximum on the other — Daicos read 34-45 on the decimal board and 48 on the
  rounded one. p90 answers "what does he reach one year in ten"; the 3-2-1 total
  answers "what does he collect if every game the model gives him lands"; the
  ceiling bounds both. It must be `max()` and never a swap: the 3-2-1 total sits
  BELOW p90 for 293 of the 465 players with ten or more games, and for 198 of
  those it is at or below the player's own expected total. Only 2 players lift.
  Done in the dashboard so the 3-2-1 rule stays solely in `load_game_rounded`,
  which means `season_projection_2026.csv` carries the raw p90 and the board
  shows the lifted figure. That file has exactly one consumer, the Leaderboard.

## Score involvements: two different quantities, one name

**`Score_Involvements` in `features.py` is NOT the AFL's Score Involvements
stat.** `add_row_stats()` defines it as `Goals + Goal.Assists + Marks.Inside.50 +
Inside.50s`. That double counts (a mark inside 50 converted to a goal scores
twice for one act) and it omits the largest real component, any possession in a
scoring chain. For a midfielder both land in the same 6 to 9 per game range,
which is why the collision survived unnoticed: the wrong number looks right.
Ed Richards' 2026 "8.95 score involvements" was 149 inside 50s out of 197.

Two rules follow, and they pull in opposite directions on purpose.

- **The engineered column keeps its name and its definition.** It is one of the
  93 entries in `predictions/features.pkl`, along with its `_game_rank`,
  `_game_pct` and `_game_z` derivatives, and it feeds `Impact_Score`. Renaming
  or redefining it breaks `predict_2026.py` against the trained model. Changing
  it is a retrain, not an edit.
- **It must never be shown to a reader as a score involvement.** The real stat
  is `Score_Involvements_Actual`, sourced by `scraper_advanced.py` and joined by
  `build_score_involvements.py`. `round_bests.py` refuses to rank the engineered
  column, and says why in a comment worth reading: a record only works as a
  record when it is the same quantity the rest of the world counts. Every
  reader-facing surface now reads the real column, via `_SI_COL` in
  `dashboard.py` — the Stat Filter slider and its results table, and the Player
  Profile Compare tab's "Score involvements / game" row. Both go through
  `_SI_PATH`; grep `_SI_COL` rather than the literal string. The Stat Filter
  slider ceiling is 20, not the 15 the engineered column used: the real stat
  reaches 21 in a game and 15 is only its 99.9th percentile.

**Coverage starts in 2015**, measured rather than assumed: footywire's advanced
table carries no SI column for 2003 or 2010 through 2014, and does from 2015.
Nothing special-cases that in the dashboard. `_load_stat_filter_frame` measures
each column's floor from the first season it is non-null, so the Stat Filter's
existing season clamp picks it up like any other stat. Pre-2015 loses the filter
rather than falling back to the substitute.

**Three traps in the footywire scrape, each of which produced silently wrong
data before it was caught by a count rather than by reading code:**

1. **The stats table is nested two layers deep.** `find_all('tr')` on a wrapper
   returns the inner rows too, so every player is counted once per level. The
   first run wrote exactly 3x the expected rows. Parse only the innermost table,
   the one containing no table of its own.
2. **The player link names the player's CURRENT club, not the club he played
   that match for.** Reading the team from `pp-<club>--<name>` put Dangerfield,
   Jeremy Cameron and Isaac Smith in Geelong's 2015 round 1 table. Take the team
   from the table's own "<club> Match Statistics" heading.
3. **An unmapped club name drops a whole club silently.** GWS title-cased to a
   name the archive has never used and 529 rows joined to nothing with no error.
   `_heading_to_club` now raises on any club outside `KNOWN_CLUBS`, on the first
   match rather than after 206 requests.

**Two rules the JOIN must keep, both learned from a row count rather than from
reading code, and both enforced in `build_score_involvements.py`:**

1. **A candidate round is claimed at most once, and a match with no unclaimed
   candidate is DROPPED rather than placed over one.** Matches are positioned by
   the club pair they actually were, not by footywire's round label, because the
   label disagrees in rescheduled cases. But two matches of the same pair are two
   different games: putting both on one `Round_num` does not merge them, it makes
   them indistinguishable, and `drop_duplicates('kf')` then hands the round
   whichever sorted first. footywire files an Essendon v Gold Coast game under
   its Round 24 that the archive holds no fixture for at that date; nearest
   candidate placement dropped it onto `Round_num` 18 where the genuine meeting
   already sat, and 30 of the 32 players in both carried different figures. Half
   that round was wrong with the build still reporting a pass. Do not relax the
   claim back to nearest-candidate.
2. **The archive is the authority on which games happened.** A footywire match
   the fixture list has no room for cannot be placed, and guessing is worse than
   the gap. The 2025 case resolves to `Round_num` 1 by elimination, which its own
   player list confirms: 46 a side, 43 exact, the 3 misses pure name forms
   (Lachlan/Lachie Weller, Samuel/Sam Collins, Zachary/Zach Merrett).

**`predictions/game_level_*.csv` can carry the same player twice in one game,
and this is NOT fixed at the source.** 2025 has 78 such rows: every Essendon
player in Essendon v St Kilda and every Gold Coast player in Gold Coast v GWS,
both round 24. The copies are **not exact duplicates**: they differ in their
Wheelo columns and so in `P_1`-`P_3` and `Exp_Votes`, which means
`drop_duplicates()` with no subset removes none of them. Dedupe on game plus
player. 2026 currently has none (9,522 rows, exactly 207 games x 46, checked 14
September 2026). The 89 this line used to state no longer reproduces, and
nothing upstream stops it recurring. A duplicate does two kinds of
damage. On the right side of a left merge it multiplies the left row rather than
annotating it — the 2025 Stat Filter frame grew 9,561 rows to 9,639 before this
was caught. And it defeats name matching, which accepts only a key unique on
BOTH sides, so a player named twice in one round for one club reads as ambiguous
and is refused. `build_score_involvements.py` dedupes `gl` at load and
`dashboard.py` dedupes at both merge sites, so the SI path defends itself; every
other consumer of those files does not. Whatever writes them still emits the
duplicates.

**No career total of this stat is possible, in either version.** The engineered
column measures a quantity nobody recognises; the real one starts in 2015, and a
career total needs the whole career. There is no honest version, so
`fewest_games.py` now **refuses** `Score_Involvements` via `NOT_FOR_PUBLICATION`
rather than redirecting it, and the stale
`drafts/fewest_games_score_involvements_1000.md` carries a DO NOT POST banner.
Per-game and per-season figures are fine from 2015 on; it is the career ladder
that cannot be built.

## Player stats by quarter

**Nothing in this repo except `data_chains/` can answer an intra-game
question.** AFLTables, Wheelo, footywire and Squiggle all carry full-match
player totals only, and the `HQ1P`/`AQ1P` style quarter columns in
`fitzroy_stats_all.csv` are **team scores, not player stats**. Wheelo's
`Rating_Q1`-`Q4` are ratings, not counts. Before building any "at half time",
"in the last quarter" or "by quarter time" claim, the source is
`scripts/fetch_match_chains.py` and nothing else.

The feed is the AFL's own play-by-play:
`https://api.afl.com.au/cfs/afl/matchChains/{providerId}`, one row per match
event with `period`, `periodSeconds`, `playerId`, `teamId` and a `description`.
It needs an `x-media-mis-token`, minted free and unauthenticated from `POST
/cfs/afl/WMCTok`. **That POST needs `Origin`, `Referer` and an explicit
`Content-Length: 0`** or Akamai returns a bare HTML "Bad Request" rather than a
JSON error. The fixture walk on `aflapi.afl.com.au/afl/v2` needs no token.

**A disposal is an event whose `disposal` field is non-null, and there is no
description list to maintain.** That field is populated on exactly three
descriptions (Kick, Ground Kick, Handball) and null on the other 36. Counting by
description instead scored 37/46 players with `{Kick}` and 44/46 with `{Kick,
Ground Kick}` against the AFL's own live figures; the `disposal` field scored
45/46 and is the source's own definition.

**Two boundaries, both in the source rather than chosen:**

- **Coverage starts in 2021.** `matchChains` returns HTTP **200 with an empty
  list** for every season 2012-2020, checked across rounds 1, 5, 15 and 23-27 in
  2017-2020. It is not an error and not a missing-match case, so an unguarded
  run writes nothing and reports success. `FIRST_SEASON` refuses the range
  instead. Every record off this data is "youngest since 2021", never "ever".
- **The feed lags badly during a live match.** Mid-final-quarter of the 2026
  wildcard final the chains had Swadling on 20 disposals while the official
  `playerStats/match` feed had him on 30; both read 32 after the siren. Only
  matches whose fixture status is `CONCLUDED` or `POSTGAME` are fetched, and the
  raw cache from a live fetch is poison. The 98% reconciliation guard catches
  it, but clear the cached match rather than lowering the floor.

**The guard is a cross-endpoint check, not a self-check.** Per-period disposals
are summed per player and compared against `playerStats/match`, which Champion
Data computes independently. Currently 2,106 of 2,116 reconcile (99.53%) across
46 finals. Below `MIN_MATCH_RATE` the run refuses to write.

**Bounding the pre-2021 gap without the data.** A player cannot have N
disposals by half time without having N for the full match, so every possible
pre-2021 challenger to a half-time record sits in the full-game archive, which
does reach 1965. That converts an open-ended "but what about before 2021" into a
finite named candidate list. `scripts/period_records.py` prints the note under
every ladder.

## Brownlow votes before 1984

**Every per-game vote source in this repo starts in 1984**, and that is a
boundary in the source rather than a fetch-range choice.
`data_history/fitzroy_stats_1965_2006.csv.gz` carries `Brownlow.Votes` as
all-null for 1965 to 1983 and fully populated from 1984 — the earlier rows were
pulled and came back with kicks and marks present and votes empty. AFLTables'
own detailed records are titled "Brownlow Records 1984-2025" with no earlier
equivalent.

`scripts/build_brownlow_seasons.py` (run from the repo root, not from inside
`scripts/`) fetches AFLTables season totals for 1924 to 1983 into
`data_history/brownlow_seasons_1924_1983.csv`. **It carries season totals per
player and never game attribution**, which fixes what it can and cannot support:

- It CAN extend a career-total or season-leader claim back to 1924.
- It CANNOT extend any opponent-scoped or fixture-scoped claim ("votes against
  Melbourne", "votes in Carlton v Fremantle"). A season total does not record
  which game a vote came from, so those claims stay capped at 1984 permanently.

**1976 and 1977 doubled the vote pool, and the file does not say so.** Two
field umpires each awarded 3-2-1, so both seasons total exactly 1,512 votes
against 756 in 1975 and 792 in 1978. The `Vote_system` column labels them
"3-2-1" like every season from 1931, so nothing in the data flags them. A naive
all-time season ladder therefore opens with Graham Teasdale's 59 (1977) and
Graham Moss' 48 (1976), neither comparable to a modern total, and against a
single allocation Cripps' 45 in 2024 is the record. Measure the pool per season
rather than trusting the label. `night_pack.COMPARABLE` drops both seasons (and
the 1924-1930 one-vote era) and `count_tweets.py` filters through it;
`leaderboard_card.py` names Cripps rather than claiming a record for the same
reason. Any new season-total record must go through `COMPARABLE`.

Recon only. Nothing in the model pipeline reads this file.

## Count night runbook, 21 September 2026

**Read this before doing anything on the night.** Charlie runs the count from
his PHONE, over Remote Control, so the session answering him has none of the
context this file was written in. Everything needed is here.

**The watcher runs on the PC and must be detached from the Claude session.**
Started in the foreground it blocks that session for two hours; started as an
ordinary background task it can die with the session. Start it hidden and
independent, from PowerShell, and it survives Claude entirely:

```powershell
Start-Process -FilePath "python" `
  -ArgumentList "scripts/count_tweets.py","--watch" `
  -WorkingDirectory "C:\Users\charl\Python\brownlow_engine" `
  -WindowStyle Hidden -PassThru
```

Note the PID it prints; `Stop-Process -Id <pid>` is how the night ends early.
Sleep is not a risk: both `STANDBYIDLE` and `HIBERNATEIDLE` on AC read 0
(never), measured 13 September 2026.

**Checking in after a round is one command.**

```bash
python scripts/count_tweets.py --last        # the round that just landed
python scripts/count_tweets.py --last 3      # if a few went by
```

It reads `drafts/count_night_tweets.txt` and nothing else: no feed request, no
model, instant. **Relay its output verbatim** so the posts can be copied
straight into X. Do not summarise them, and do not rewrite the copy — every
post is templated on purpose, and the wording is signed off.

**What to expect, so nothing looks broken.** Before the count starts the log
says `refusing: PREDICTOR` once and then goes quiet; that is correct, not a
hang. Most rounds produce one post or none. A heartbeat prints every 10
minutes. The loop stops itself after the end-of-count posts.

**Do not run `--live` or `--watch` a second time to "check" it.** The drafted
rounds file is what stops a round drafting twice, and the failure modes are
silent in both directions. See the bullet below.

**If the watcher dies**, restart it with the same command. Rounds already
drafted are recorded, so it resumes rather than replaying the night. Nothing is
lost from the log, which is appended to.

**Never delete `drafts/count_night_drafted_2026.txt` mid-count** (the next poll
redrafts all 25 rounds and buries the one that just landed), and never write
rounds into it (`--watch` then concludes there is nothing new and drafts
NOTHING, with no error).

**Nothing here posts.** `--watch` and `--last` only draft. Posting is Charlie's,
from his phone.

**The site needs no action.** The Live Tracker flips itself from PREDICTION to
LIVE COUNT off the feed, and `.github/workflows/keepalive.yml` keeps the app
awake. Open the site yourself before the count anyway: the job fires every 1.6 to
5.6 hours in practice, so the first visitor after a quiet spell can still meet a
cold start. If asked whether it is live,
`python scripts/count_night.py status` answers in one line without touching the
site.

## Count night and the Live Tracker

**The AFL award endpoint serves the AFL's own PREDICTOR between counts and the
live votes on the night, at the same URL, in the same shape, with no field
saying which.** `aflapi.afl.com.au/afl/v2/compseasons/{id}/award/brownlow`.
Measured against two completed seasons rather than assumed: it says 2025 Dawson
32 where the count was Rowell 39, and 2024 Cripps 33 where the count was Cripps
45. So `any(totalVotes > 0)` is true all year and gates nothing. It was the
deployed test until 13 September 2026, and the live page spent the season
showing a pulsing LIVE badge over predicted totals.

**The only way to tell the two apart is a before-picture.**
`data_2026/brownlow_predictor_snapshot.json` is the pre-count payload, taken 10
September 2026: 630 players, 1,242 votes, Daicos 47. `scripts/count_night.py
snapshot` refuses to overwrite it without `--force`, and it cannot be retaken —
once the count starts the pre-count payload is gone from everywhere.

`_feed_state()` in `dashboard.py` compares against it and returns one of four
states. `scripts/count_night.py status` prints the same verdict from the CLI.

| State | Test | Pill / mode |
|---|---|---|
| PREDICTOR | totals match the snapshot | PREDICTION · Count not started |
| COUNTING | total < `207 * 6` = 1,242 | LIVE COUNT · progress by rounds read |
| COUNTED | full pool again, but changed | FINAL |
| UNKNOWN | snapshot missing or unreadable | UNVERIFIED · treat as unconfirmed |

**Three rules that are load-bearing, each learned from a way it went wrong:**

- **It must fail to UNKNOWN, never to "live".** Labelling predictions as the
  count is the one error that cannot be walked back.
- **The comparison runs over the SNAPSHOT's keys, not by dict equality.** The
  page's fetch early-stops on the first page whose tail is all zeros, so its
  payload is truncated (210 players) while the snapshot never is (630). A plain
  equality reads "different" on every poll and calls the predictor a live
  count. An absent player is a zero.
- **The pill, the mode line, the banner and the progress meter all derive from
  that one state.** They are `_LT_STATE_TXT`, `_LT_STATE_NOTE` and `_prog_txt`
  in `dashboard.py`. Each one that was ever written independently ended up
  contradicting the others on the same payload: UNVERIFIED over a banner saying
  the count had not started, and a full green "Round 24 of 24 counted" over a
  banner saying the same. Add a new surface to the map, never beside it.

**Round numbering here is the AFL feed's, not AFLTables'.** Opening Round is 0
and the rest are 1 to 24, 25 in all, so the progress meter is
`(_disp_round + 1) / 25` and round 0 is "Opening Round", not "Round 0". Do NOT
apply the `Round_num - 1` law in this page; `last_round` and `_disp_round`
arrive already offset, and `_rounds_of()` says so at its definition.

**`ttl=60` on `fetch_live_brownlow_data` and the auto-refresh `sleep(60)` must
move together**, or each refresh lands on a warm cache and pulls nothing. At
the old 300 the board could sit five minutes stale with the votes already
public. A round is read out every five or six minutes; unknown until the night
is how fast the AFL feed updates against the broadcast.

**The app is kept awake by `.github/workflows/keepalive.yml`**, driving a real
browser via `scripts/keepalive.py`. A curl ping cannot do this job: Streamlit
Cloud serves the host page with a 200 while the app behind it sleeps, and the
sleep screen is itself a 200. **The cron asks for every 15 minutes and GitHub
does not deliver it:** the ten runs from 12 to 14 September 2026 all succeeded,
spaced 1.6 to 5.6 hours apart. Enough to stop the app sleeping, not enough to
promise a warm start. `gh` is not installed on this PC; the public Actions API
(`api.github.com/repos/charliejurberg-bit/Cha-Ching-Brownlow-Engine/actions/workflows/keepalive.yml/runs`)
answers without it.

**`scripts/` does not feed the page.** The Live Tracker calls
`fetch_live_brownlow_data()` itself and computes bolters, landed and the
leaderboard inline. Fixing one does not fix the other.

**Driving the night: `python scripts/count_tweets.py --watch`.** One command
for the whole count. It polls every 60s, drafts each round once it is finished,
teas the night to `drafts/count_night_tweets.txt`, and stops itself after the
end-of-count posts. It never posts.

**It must stay a plain Python loop, not a `/loop`.** Every post in
`count_tweets.py` is templated, which the module states as a deliberate choice
in its own header: a templated post cannot invent an accuracy claim under time
pressure. So nothing on the night needs a model, and a `/loop` would spend a
full model call per tick, roughly 25 of them, for deterministic output. Token
cost of `--watch` is zero.

**`drafts/count_night_drafted_<season>.txt` is what stops a round drafting
twice**, and it is the file to be careful with. If it already lists every round,
`--watch` correctly draws the conclusion that there is nothing new and drafts
NOTHING, with no error. Any test of the live path must redirect `_seen_path`
elsewhere rather than write it. Deleting it mid-count is the opposite failure:
the next poll redrafts the whole night and buries the round that just landed.

**The feed's player names must be bridged onto the model frame, and a missing
model value reads as ZERO rather than as absent.** That asymmetry is what makes
this a correctness bug and not a blank cell: the leaderboard shows an
unbridged player's whole total as outperformance, and Zone 1's bolter test
(`_e < BOLTER_MODEL_MAX`) puts him under "polled, nobody called it". Measured on
the 2026 feed, three vote-getters were in that state, the worst being Matt
Carroll — 2 votes in display round 10, with the model on 0.86 Exp_Votes and a
47% poll probability.

Two structural causes, neither a typo. `load_game` runs
`_disambiguate_players`, which appends `(Team)` to any name carried by more than
one fitzRoy ID, and no feed will ever produce that suffix; and the feed uses the
full given name ("Matthew Carroll") where the archive uses the short one.

`_lt_feed_to_model_names` handles both, above the cache key so every downstream
lookup shares one namespace. **Do not write a second resolver**: step 1 is
`features.resolve_feed_names`, whose own docstring names the two Bailey
Williamses as the case it exists for, and whose uniqueness guard refuses rather
than guesses. Step 2 is the `(base name, club)` hop onto the disambiguated name,
which only this page needs.

`AFL_AWARD_TEAM_FIXES` is separate from `COACHES_TEAM_FIXES` on purpose and the
two must not be merged. The same six clubs differ from AFLTables in both feeds,
but this one shouts two of them — `Gold Coast SUNS`, `GWS GIANTS` — where the
coaches feed title-cases them, and `.replace()` is exact-match. Sharing the dict
leaves both clubs unfixed and every one of their players unresolvable by the
team-scoped layer, which is exactly where the two Bailey Williamses are told
apart.

**`asm["recon"]` is written and never read.** Its three buckets are named `hit`,
`blanked` and `bolter`, which mirror Zone 1's three panels exactly, so it reads
as the thing that fills them. It is not: the page builds `_bolters` / `_landed`
/ `_missed` inline. It also differs from the render in two ways, so it is not
even a stale copy — it skips `last_round == 0` (the whole Opening Round
segment) and it calls any 2+ vote player off the card a bolter without the
model test. Change the render, not this.

**A signed-in account renders four panels an anonymous visitor never sees**, so
verifying the page signed out verifies about half of it. `_wl_visible` is
`_wl is not None`, and `_wl` is `None` without a user — which drops Zone 3
(upcoming targets), the H2H panel, the ★ set and the "My watchlist only"
filter before they render. To exercise them, patch the four `user_auth`
loaders (`current_user`, `load_poll_picks`, `load_h2h_pair`, `load_watchlist`);
they are the page's whole interface to an account.

## Dashboard pages

Navigation is a **tab bar of at most two rows** (the hub row is admin-only, see
the row table below), and both rows are `st.button`s laid out in
`st.columns` — *not* `st.selectbox`, `st.sidebar`, or `st.tabs`. They only look
like tabs because of CSS. Each row's columns live in a **keyed container** —
`_render_hub_tabs()` → `st.container(key="ccnav_hub")`, `_render_page_nav()` →
`st.container(key="ccnav_page")`. Streamlit stamps `.st-key-ccnav_hub` /
`.st-key-ccnav_page` **on that container's own `stVerticalBlock`** (same element
as `data-testid="stVerticalBlock"`, not a parent wrapper), and the nav CSS (one
big `st.markdown` in `dashboard.py`) selects off those classes. Grep
`st-key-ccnav_` when changing nav styling. (The old `.nav-hub-anchor` /
`.nav-page-anchor` marker divs and their `:has()` selectors are gone.)

**Two traps here each cost a deploy — read before touching nav CSS:**
1. A plain `st.container(key=…)` puts the key class on the `stVerticalBlock`
   itself, so rules read `.st-key-ccnav_page <descendant>`, **never**
   `.st-key-ccnav_page > [data-testid="stVerticalBlock"]`. (A keyed *widget* like
   `st.button(key=…)` instead puts `.st-key-<key>` on its `stElementContainer` —
   that's how the page icons attach.)
2. Every nav selector is prefixed `.stApp` **for specificity, not scoping**. The
   old marker `:has()` selectors scored ~(0,3,1); a flat `.st-key-` rewrite is
   (0,1,1) and *loses* to `betting_hub.py` / `theme.py` button resets that
   re-inject **after** the nav CSS on `betting_hub.render_page()` pages — so the
   nav breaks on BH pages but not on inline ones (Predictions). `.stApp` lifts
   each rule a class. The active-pill rule goes further still —
   `.stApp .st-key-ccnav_* [data-testid="stButton"] button[kind="primary"]`
   (0,4,1) — to beat `render_bh_dashboard()`'s global (0,2,2)/(0,3,2) emerald
   fill. **Any new nav rule must out-specify those resets; verify on a Betting
   Hub page, not just an inline one.**

| Row | Rendered by | Contents |
|---|---|---|
| Hub toggle | `_render_hub_tabs()` | `Brownlow` · `Betting Hub`. **Admin only** — called under `if _is_admin:`, so an anonymous visitor sees one row, never two, and has no control that writes `active_hub`. |
| Page strip | `_render_page_nav()` | one button per page of the active hub (`_snav_pages`) |

Two pieces of state, both plain session keys:

- `st.session_state["active_hub"]` — `"brownlow"` (default) or `"betting"`
- `st.session_state["page"]` — the current page

| Hub | Pages (in strip order) |
|---|---|
| Brownlow | Leaderboard, Player Profile, Stat Filter, Game Analysis, Model Comparison, Live Tracker, **Polls a Vote** |
| Betting Hub (`_BH_PAGES`) | Performance, Predictions, Bet Tracker, Cha Ching Tips, Trends & Analysis |

**`_BH_PAGES` has five members and Polls a Vote is not one of them.** It left the
set and now sits at the end of the seven-button Brownlow strip, scoped per user
by RLS rather than by the gate. Membership drives three surfaces, not just the
nav strip: `_show_controls = _page not in _BH_PAGES`, the access gate
`if _page in _BH_PAGES and not _is_admin:`, and the responsible-gambling footer
guard `if _page not in _BH_PAGES:`. Filing Polls a Vote under the Betting Hub
would gate it, suppress the season controls, and drop the RG footer.

Behaviour worth knowing before touching nav:

- **There is no Landing page**, and no `if _page != 'Landing'` guard. Both
  `_page == 'Landing'` and `_page != 'Landing'` return zero hits in
  `dashboard.py`; "Landing" survives only in a stale comment. The page strip
  renders unconditionally.
- **Switching hub reassigns `page`** if the current page belongs to the other hub
  (→ `Leaderboard` / `Performance`), so the strip is never showing a page the hub
  doesn't own.
- **Page icons** come from `_PAGE_ICONS` × `_TI_GLYPHS` (Tabler webfont). Each nav
  button is keyed `nav_<Page>`, so its container carries `.st-key-nav_<Page>`, and
  the icon is a CSS `::before` on that (generated into `_nav_icon_css`) — no marker
  div. A page missing from `_TI_GLYPHS` renders iconless. Codepoints are verified
  against the pinned Tabler version (`_TABLER_HREF`, 2.47.0 — note `@latest`
  silently serves 2.47.0 because 3.x moved the file to `/dist/`).

Betting Hub pages render via `betting_hub.render_page(page_name)` (module imported at
top of `dashboard.py`) — **except `Predictions`, which `dashboard.py` renders itself**.
All `_BH_PAGES` sit behind an **admin-account check, not a password gate**:
`if _page in _BH_PAGES and not _is_admin:` renders a private panel and calls
`st.stop()`. `_is_admin = user_auth.is_admin()`, which matches the signed-in user
against `st.secrets["ADMIN_UID"]` and fails closed on every path;
`betting_hub.render_page()` carries an independent backstop on `cc_is_admin`.
**No password is collected anywhere in this flow.** `bh_authed` and
`BH_PASSWORD` survive only in historical comments and are never read or written.
The one surviving password, `TIPS_EDIT_PASSWORD`, gates Tips *editing* rather
than access. The gate runs after nav, so the bar stays visible.

Several pages that this table once listed separately are now `st.tabs` *inside* a page:
Player Profile → Profile / DNA / Compare · Model Comparison → 2026 (Live) / Insights ·
Predictions → Home / Value Finder.

## CSS design system

CSS lives in three places: `inject_global_theme()` in `theme.py` (the tokens and
the app-wide resets, called once from `dashboard.py`), the `<style>` blocks in
`dashboard.py` (20 in all: the global page CSS near the top, the nav rules
further down, and many page-scoped blocks such as Game Analysis' `_GA_CSS`),
and the `BH_CSS` string constant in `betting_hub.py`. Widget overrides use
`!important`. Find a rule by grepping its selector, not by position.

**Midnight Turf colour palette — never change these:**
```
Background:    #0a1017
Surface:       #101a24
Text:          #e9eef3
Emerald:       #34d399
Gold (betting):#f0b429
Muted red:     #ef7a6d
Border:        #1a2632
Muted text:    #7e8c99
Hairline:      rgba(140,165,185,.14)
```

Tokens are defined once in `theme.py` (`--bg`, `--surface`, `--emerald`,
`--gold`, `--text`, `--muted`, `--line`). `.streamlit/config.toml` sets
`base = "dark"`, `primaryColor = #34d399`, `backgroundColor = #0a1017`,
`secondaryBackgroundColor = #101a24`, `textColor = #e9eef3`.

The theme is **dark**. An earlier version of this file listed an "earthy"
light palette (`#faf7f2` background, `#2d5016` green, `#8b6f47` tan) as
inviolable; all nine of those values return **zero matches repo-wide**. Red
`#ef7a6d` is for losses and negative P&L only, never model errors, validation
nudges, or status indicators.

Beyond the seven named tokens, `theme.py` also defines `--surface-2`,
`--steel`, `--emerald-dim`/`-track`/`-pack`, `--gold-dim`, `--hairline-strong`
and `--ease-out`; page CSS uses them, so check there before hard-coding a tint.

**Fonts:** Archivo for headings, Sora for UI text, and **IBM Plex Mono for
numerics**, which `theme.py` loads and forces on dataframe headers and metric
values (96 uses in `dashboard.py`, 36 in `betting_hub.py`). DM Mono is still
loaded by `dashboard.py` and survives in 22 older rules there; it is a leftover,
not the standard.

**Key CSS patterns** (verified 14 September 2026; an earlier list here described
card shadows, hover lifts and a `::before` header bar that no longer exist):
- `.section-header` (`dashboard.py`): Sora 11px / 500 / 0.1em uppercase, muted,
  a hairline `border-bottom`. `.trend-header` (`betting_hub.py`): emerald 10px /
  800 / 2px uppercase, same border.
- Metric labels: muted, 11px / 500 / 0.07em uppercase.
- Anti-aliasing: `* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }`
- Custom scrollbar: 6px, `var(--line)` thumb, emerald on hover.
- Streamlit toolbar hidden: `[data-testid="stToolbar"] { display: none !important; }`

## Betting Hub data model

**Supabase is the store.** Bets live in the Supabase `bets` table and are written
only via `.upsert(..., on_conflict="bet_id")`.

`data_betting/bets.csv` is a **read-only local fallback**. Nothing in the repo
writes it, and `_load_bets` concatenates it *ahead* of the Supabase rows before
`drop_duplicates(subset=['bet_id'], keep='first')`, so a stale CSV row shadows
the cloud copy of the same `bet_id`. That shadowing is known and deferred.

Fallback CSV columns:
`bet_id, date, match, market_type, selection, bookmaker, odds, stake, result, profit_loss, is_cha_ching, cha_ching_criteria, notes`

**Cha Ching tip** = bet flagged by ≥3 checklist items (role change, player in/out, EV positive, line movement, confirmed team selection, custom note). Threshold `CC_THRESHOLD = 3` in `betting_hub.py`.

Bookmakers tracked: Sportsbet, TAB, Betfair, Ladbrokes, Neds, PointsBet, Unibet.
Market types: Disposals O/U, Goals O/U, Kicks O/U, Handballs O/U, Marks O/U, Match Result, Line.

## Key decisions & constraints

- **Round numbering**: from **2024 onward** AFLTables numbers Opening Round as Round 1, so its round numbers run 1 ahead of the AFL's official count (AFLTables Round 12 = AFL Round 11). **The subtraction is conditional on season, not unconditional.** The rule is `rn - 1 if sn >= _OPENING_ROUND_FROM else rn`, with `_OPENING_ROUND_FROM = 2024`; subtracting for a pre-2024 season is wrong. `_display_round` is defined in **three** places, `dashboard.py`, `draft_posts.py` and `streaks.py`, each carrying its own copy of the constant, so changing one means changing all three. Display only: the underlying data and all filtering always use the raw AFLTables `Round_num` value. Total H&A rounds in AFLTables for 2026 = 25 (raw Rounds 1–25), a 23-match season of Opening Round plus official Rounds 1–24, for 207 games (18 clubs x 23 / 2). Byes fall in official Rounds 12–14, so a club sitting on fewer than 23 games mid-season is not evidence of a short file.
- **Finals excluded**: Rounds with string labels (QF/EF/SF/PF/GF) are coerced to NaN and dropped in both training and prediction. Max H&A round detected dynamically per season (2023 and prior seasons had 24 rounds; current code handles any count).
- **No lookahead in form**: `late_form_ewm` uses `.shift(1)` before the EWMA so current-round data is never included.
- **Same-name disambiguation**: Players sharing a name but on different teams get `Name (Team)` appended.
- **Wheelo merge key**: Player + Team + Season + Round (team required to disambiguate e.g. two players named "Bailey Williams").
- **Model retrain**: Only needed at start of season or when feature set changes. Predictions (`predict_2026.py`) run weekly after each round.
- **Odds scraper**: Uses `undetected-chromedriver` (headless Chrome) to bypass Cloudflare on Oddschecker. Fragile — may need `--headless=new` flag updates if site changes.
- **Root-level `.pkl` files are session scratch and are gitignored** (`/*.pkl`). Eight of them, 215 MB of cached recon DataFrames referenced by no `.py` file in the repo, were once staged by a bare `git add` and came within a commit of being permanent. The rule is root-scoped on purpose: the model artifacts in `predictions/` are tracked and must stay that way. Prefer the scratchpad directory over the repo root for interactive caches.
