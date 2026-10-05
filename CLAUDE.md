# Cha Ching — Brownlow Medal Predictor & Betting Hub

AFL Brownlow Medal predictor plus a betting tracker. XGBoost model (v4.0) trained on 2007–2025 data. Dashboard live on Streamlit Cloud.

**Where things stand (29 September 2026):** the 2026 count is done (21
September, Nick Daicos 47) and saved, and the pipeline has been **rolled over to
2027**: `season.LIVE_SEASON` is 2027 and 2026 is a finished season carrying its
actual votes in `game_level_2026.csv` / `season_2026.csv`. 2027 has no data yet,
so the public site leads with 2026 through `season.current_season()` (see
"Season rollover"). Every public page is now on the Next.js site; see "Streamlit
to Next.js migration".

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

`python update.py` runs the weekly chain for `season.LIVE_SEASON`: an R step
(`fetch_stats.R <season>`, plus the guarded `fetch_coaches.R <season>` when
`season.py` switches it on, off for 2026) then eleven Python steps (odds, Betfair,
ESPN, AFL predictor, Wheelo, footywire advanced stats and their ID join,
predictions, drafts, `site/landing.json`, `site/data/`). Nothing in the chain stops on a
failed step; read each step's exit code. See "Season rollover" below.
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
24 and 25**, dropping routing back to 189 / 18. The old
`data_2026/fetch_coaches.R` wrote unconditionally and is deleted; its
replacement, root `fetch_coaches.R`, **refuses any fetch missing a game already
on disk**. A row-count or last-round guard is not enough, measured on 27
September 2026: the feed returned 1,380 rows through "round 29" against the
file's 1,346 through round 25, passing both, yet its rounds 24-29 were the
finals mislabelled, 12 rows each, and still lacked the hand-transcribed home
and away rounds. `season.py` also keeps the coaches fetch off for 2026.
`coaches_votes_2026_prev.csv` does **not** protect against this: it predates
the transcription. Re-run the append script to recover, or restore the
committed file.

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

## Season rollover

**`season.py` holds the live season. Nothing else may write a season number.**
Every script in `update.py`'s chain, the count-night tools and the dashboard's
live-season logic read `season.LIVE_SEASON`; the `_2026` left in some filenames
(`predict_2026.py`, `update_wheelo_2026.py`) predates it and means nothing.
`BROWNLOW_SEASON=2027 <command>` overrides it for one run, for rehearsal.

The whole rollover, after a count:

```bash
python scripts/fetch_brownlow_votes.py 2027   # save the count; refuses a partial one
python season_rollover.py 2028                # check only
python season_rollover.py 2028 --apply        # backfill, retrain stack, switch season
```

`--apply` backfills the finished season's votes into `game_level_<old>.csv` and
`season_<old>.csv`, because from 2026 those files are written as live
predictions with 0 votes and the dashboard reads any season below
`LIVE_SEASON` as history. Skipping it makes every player of the old season
read as never polling. Then fill `season.SEASONS[<new>]` as the values become
known: `landing_summary.py` will not write without `count_night`, and
`scraper_espn.py` skips without `espn_slug`.

**Done for real on 29 September 2026** (2026 to 2027, stack already trained
through 2026 so step 2 was a no-op). Two helpers in `season.py` came with it and
are what the public site reads, never `LIVE_SEASON` directly:
`current_season()` is `LIVE_SEASON` once it has a `game_level` file, otherwise
the latest season that does, so between a rollover and the new season's first
predicted round every default page, `landing_summary.py`, the Model Comparison
export and the Live Tracker / Polls a Vote exports stay on the finished season
instead of opening on an empty one. `counted(season)` is whether
`data_<s>/brownlow_votes_<s>.csv` exists; it flips the tracker, Polls a Vote,
Model Comparison and the landing page (`final` block in `site/landing.json`)
from live to finished. The weekly chain still reads `LIVE_SEASON`. The
Streamlit app reads `LIVE_SEASON` too, so its Model Comparison, Live Tracker
and Polls a Vote show an empty 2027; it is being retired, so that is accepted.

**Rehearsed on 27 September 2026, not assumed.** Rolled to 2027 with no 2027
data at all, all seven Brownlow pages rendered; two failures were found and
fixed. Model Comparison crashed on an empty consensus table. The Live Tracker
hung because `bfawards_feed.season_ids` raised `SystemExit`, which the
dashboard's `except Exception` does not catch, for a season the AFL had not
published yet. Then everything was restored; 2026 output is byte identical.

**Two page comparisons can differ run to run with no code change.** Model
Comparison and the Live Tracker order tied rows through a set, and string
hashing is randomised per process. Compare them under `PYTHONHASHSEED=0`.

## Streamlit to Next.js migration

**Started 28 September 2026. The public Brownlow pages are moving, one at a
time, into the Next.js app in `C:\Users\charl\web\cha-ching-brownlow\`** (the
landing page's repo, branch `main`, Vercel, `chachingbrownlow.com`). Decided
with Charlie: the pages live in that repo, not a new one, and **the Betting Hub
is retired, not migrated**. It keeps running on Streamlit only until the
Streamlit app itself is switched off.

**Python stays the engine and never runs on Vercel.** `export_site.py` (step 12
of `update.py`) writes small per-page JSON under `site/data/`, tracked, and the
Next.js pages fetch it from raw.githubusercontent.com on **master** with hourly
ISR, exactly as the landing page reads `site/landing.json`. So a commit and push
of this repo is what publishes new figures. **Every page switches together
about six minutes after the push** (from 5 October 2026):
`.github/workflows/refresh-site.yml` runs on any push touching `site/`, waits
out raw GitHub's 5-minute cache, then POSTs the site's `/api/revalidate`, which
expires the `engine` fetch tag on every page at once. Before it, each page and
file ran its own hourly clock and a push reached the landing page and the
leaderboard up to two hours apart. It needs `REVALIDATE_SECRET` set, the same
value, as a GitHub repo secret here and a Vercel env var there; without it the
pages fall back to the hourly refresh, nothing breaks. Run it by hand from the
repo's Actions tab ("refresh-site", Run workflow). `site/data/index.json` lists the
seasons and the live season. Nothing on the site recomputes a figure: rank
order, movement, the Floor-Ceiling lift and the round grid all arrive computed.

**`site_data.py` began as a deliberate copy of the dashboard's loaders**
(`load_game`, `load_season`, `load_game_rounded`, `load_season_rounded`,
`round_vote_matrix`, `_fit_game_probs`, the identity helpers). Refactoring
`dashboard.py` to share them risked the live app and its memory ceiling on
Streamlit Cloud, so each function is ported under the same name. **A change to
one of those loaders in `dashboard.py` must be mirrored in `site_data.py`**, and
`python scripts/check_site_parity.py [seasons]` proves they agree: it renders
the Streamlit Leaderboard headless and compares 200 rows cell for cell with the
export, both boards, arrows included. It passed for 2026, 2025, 2019, 2010 and
2007 on the day it was written. **Since the Streamlit app was retired (29
September 2026) `site_data.py` is the source of truth** and the mirroring rule
no longer applies; the parity scripts still run (they set `CC_STREAMLIT_LIVE=1`
to get past the moved screen) and are worth running only if someone edits the
dashboard's loaders for reference.

| Page | Status |
|---|---|
| Leaderboard | Live, 28 Sep 2026: `/leaderboard`, `/leaderboard/[season]`. Names link to Player Profile |
| Player Profile | Ported: `/player/[slug]/[season or career]`. Profile, DNA, Compare. Figures checked against the Streamlit page for Daicos 2025 and career (strip, DNA rates, threshold finder, vote distribution). "Track this H2H" added 29 Sep 2026 (Compare tab, signed in; saves Player_Name pairs with null IDs, which the tracker resolves by name). Up to 3 pairs per season from 4 Oct 2026 (`supabase/07_h2h_multi.sql`, `H2H_MAX` in `lib/account-data.ts`); the Live Tracker stacks one H2H panel per pair |
| Game Analysis | Ported: `/games`, `/games/[season]`, with `?round=<AFL round>` or `?team=<club>` for sharing. `check_site_parity.py` compares every card of the default round, all rows shown; passes for 2026, 2025, 2019, 2010, 2007. Values are exported already rounded to what the page shows, because rounding twice moved about one cell in 60. One deliberate difference: a player carried twice in one game (2025 round 24) is listed once |
| Stat Filter | Ported: `/stat-filter`. The one page that computes in the browser: visitors combine nine thresholds with player, club, result and season, so `statfilter.json` ships every game since 1990 (296,006 rows, about 1.3 MB gzipped), one character per value per column, stats floored (which leaves every whole-number threshold test unchanged). The browser fetches it straight from raw GitHub, because Next's data cache refuses anything over 2 MB; `engineClientUrl` in `lib/engine.ts` swaps in a dev-only local route under `ENGINE_LOCAL_DIR`. `scripts/check_statfilter_parity.py` drives the running site against Streamlit on six filter sets; all matched on every readout |
| Model Comparison | Ported: `/model-comparison`, both tabs. `modelcomp.json` carries the finished consensus table (both scales) and the Insights data. `check_site_parity.py` compares every consensus row by player plus the backtest season table, and passed under three `PYTHONHASHSEED`s. Tied consensus rows are now in a fixed order: the dashboard's set-plus-unstable-sort reordered them every run. The admin Refresh ESPN / Betfair buttons were not ported; the weekly update writes those files. Insights adds every counted season after the backtest as a "live" row (29 Sep 2026: 2026), built from the published season file the way `backtest.py` builds a season, plus a scorecard and a calibration table off the displayed `P_3_game` (`_forward_scorecard`). That is the "displayed" column of the table under "Model architecture"; `scripts/calibration_2026.py` prints it beside the priced one |
| Landing page links | All internal (29 Sep 2026); Open Live Tracker goes to `/live-tracker`. With `final` in `landing.json` the hero, stat strip, cards and ticker report the result instead of the run-in |
| Live Tracker | Ported 29 Sep 2026: `/live-tracker`. `tracker.json` (`export_tracker`) holds the current season's per-round model signal and, once counted, the votes, so a finished count never touches the AFL. Before that the page polls `/api/tracker` every 60s, a route that mints the token and relays `bfawards/season/<id>` with `revalidate = 60`, and joins it by AFL provider id through `feedMap`, which the export builds with the real `resolve_feed_names` (666 of 669 model players for 2026). Checked: the feed path and the saved count agree on every round of all 183 vote-getters. Zone 1 can be pointed at any counted round; ranks are tie-aware. The ★ watchlist editor, picks (Zone 3) and H2H panel read the same Supabase tables; the signed-in panels were NOT exercised in a browser (no test account), only type-checked |
| Polls a Vote | Ported 29 Sep 2026: `/polls-a-vote`, against `user_poll_picks` with the anon key and RLS, saving the same `Player` spelling Streamlit did. `polls.json` (`export_polls`) carries the four outside boards keyed by `normalise_name`. Once the season is counted each pick shows what the player polled in its rounds and the add form closes. Signed-in paths type-checked only, as above |

**Player Profile data.** `players/<slug>.json` is one person's every game,
columnar, keyed by the career-disambiguated name (`site_data.load_game_career`),
with the season view's name carried per row where it differs.
`profile/<season>.json` and `profile/career.json` hold the field: picker, DNA
rates (`site_data.efficiency_from_df`), season totals and, live season only,
odds. 2,328 files, about 27 MB; a weekly run rewrites only the live season's
players. Four places the port deliberately differs from Streamlit, each a bug
there: the H2H ledger names the opponent from the player's club against the
fixture and flags a shared game by fixture (Streamlit needed `Home.Away` and
`Game_ID`, which only 2026 has, so before 2026 it named the player's own club as
the opponent whenever it was the home side and never found a shared game); odds
appear only on the live season (Streamlit priced any season at 2026 odds); a
draw reads D in the game log, not L; and the DNA rank is tie-aware (`#=3`)
where Streamlit's unstable sort put tied players in arbitrary order.
The fixture columns get the team alias fix at export, because 2007 still says
Kangaroos there.

**Previewing an export that is not pushed:** in the Next.js repo,
`ENGINE_LOCAL_DIR=C:\Users\charl\Python\brownlow_engine npm run dev` reads
`site/data/` from disk instead of GitHub (`lib/engine.ts`). Never set it on
Vercel. That repo's `next.config.mjs` has `ignoreBuildErrors: true`, so run
`npx tsc --noEmit` yourself; the build will not.

## AFLW Best and Fairest (started 29 September 2026)

**A separate model from the Brownlow, by Charlie's call and by measurement**:
the men's model applied to AFLW scored ll3 1.90 against 1.67 for an AFLW
model (`aflw/evaluate.py`). Everything lives in `aflw/` and `data_aflw/`; the
site toggle comes after the model.

- **Votes per match: 500 games, seven seasons**, each joined to stats by AFL
  player id, every match totalling 6, published totals reconciling:
  2017, 2020, 2021, 2022S6, 2022S7 recovered from AFL articles
  (`aflw/recover_votes.py`, womens.afl ones through the Internet Archive);
  2024, 2025 from the live feed (`aflw/fetch_votes.py`). 2023 has season totals
  only (`recover_totals.py`); 2018 and 2019 have nothing complete. Source
  traps are in memory, `aflw-bf-data-sources`.
- **2022 held two seasons**, labelled 2022S6 and 2022S7 everywhere.
- **The model** is Plackett-Luce over within-match features plus coaches votes
  (`pl_coach`), trained on 2020, 2021, 2024, 2025. Held-out calibration is
  close (60%+ band said 73.9%, took 69.1%; pooled sharpness gamma 1.00).
  Adding 2023 through its totals moved nothing (ll3 1.664 vs 1.665), so more
  totals-only seasons are not worth chasing for training.
- **The fitzRoy AFLW coaches feed mislabels rounds** like the men's: in
  September 2026 it served round 7 again as rounds 8-10. `build.py` keeps a
  coaches round only if its fixtures are that round's played matches.
- **On the site since 29 September 2026**: an AFL | AFLW switch beside the
  wordmark, every page under `/aflw/...`, the same components fed
  `site/data/aflw/` (`aflw/export_site_aflw.py`, which points the men's
  exporters at `aflw/site_frames.py`). Every AFLW history figure is out of
  sample: each season from a model fitted on the others. 2022's two seasons are
  ids 2022.6 / 2022.7 (labels in the Next.js `lib/comp.ts`); 2018 and 2019 are
  not on the site. AFLW account rows (picks, watchlist, H2H) sit at season
  100000 + year in the same tables. **Weekly: `python aflw/update.py`, then
  commit and push**; it is not part of `update.py`.
- **Umpires see stats from 2026 in AFLW too** (afl.com.au/aflw/news/1625586).
  `aflw/regime.py` measured the men's 2026 shift against year-to-year spread:
  only disposals (+30%) and goals (+33%) moved beyond an ordinary year.
  `predict.py` carries three scenarios (none, proportional, full); the default
  is proportional. After the AFLW count, refit on 2026 instead.

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
├── update.py             # Weekly chain for season.LIVE_SEASON, ends with site/landing.json
│                         #   then export_site.py → site/data/
├── site_data.py          # The dashboard's loaders without Streamlit. A COPY during
│                         #   the migration; see "Streamlit to Next.js migration"
├── export_site.py        # Writes site/data/<page>/<season>.json for the Next.js app
├── season.py             # THE live season, and per-season values (round and game
│                         #   counts, count night, ESPN article, coaches fetch on/off)
├── season_rollover.py    # One command to move to a new season; see "Season rollover"
├── fetch_stats.R         # Rscript fetch_stats.R <season>: AFLTables stats
├── fetch_coaches.R       # Rscript fetch_coaches.R <season>: coaches votes, GUARDED
├── stack.py              # FROM 2027 the shipping vote model: classifier + within-
│                         #   game ranker + regime layer, predictions/stack.pkl.
│                         #   predict_2026.py applies it only to a season AFTER the
│                         #   one it was trained through. See "From 2027: the stack"
├── ranker_backtest.py    # The evidence for stack.py: walk-forward, 2013-2026
├── calibration.py        # Regime layer over the classifier alone. Superseded for
│                         #   shipping by stack.py; kept for its 2026 measurements
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
├── scripts/              # 48 tracked files. Three groups:
│   │                     #   count night: count_night.py (feed state + snapshot),
│   │                     #   count_tweets.py (the --watch drafter), count_sim.py
│   │                     #   (who wins from here), night_pack.py + night_sections.py
│   │                     #   (research pack), vote_milestones.py
│   │                     #   post cards: *_card.py, round_votes_chart.py
│   │                     #   data builders: fetch_match_chains.py → data_chains/
│   │                     #   (read back by period_records.py), build_brownlow_seasons.py,
│   │                     #   append_coaches_2026_r24_r25.py, convert_history.py,
│   │                     #   reproject_2026.py, the coaches R fetches, and
│   │                     #   fetch_injury_lists.py → build_injury_ladder.py
│   │                     #   → data_injury/ (the ONLY source here that says WHY
│   │                     #   a player did not play; see "Injury data" below)
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
├── data_injury/          # The AFL's weekly published injury list, 2026 on. The
│   │                     #   ONLY source in the repo that separates injury from
│   │                     #   omission. See "Injury data" below
│   ├── injury_list_<season>.csv    # As published: club, player, injury, return
│   ├── injury_detail_<season>.csv  # Per player per round, with career games
│   ├── injury_ladder_<season>.csv  # Per club. The postable table
│   └── raw/              # HTML fetch cache, gitignored. Refetched on demand
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
│   │                             #   Do NOT force a refetch, see "Update chain"
│   ├── brownlow_votes_2026.csv   # The actual count, per player per game
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
- **MAE**: **resolved 29 September 2026, out of sample:** 0.1126 walk-forward
  2008-2025 (all-zero baseline 0.1346, 3,468 games) and 0.0920 on 2026, a true
  forward test (baseline 0.1304, 207 games), per player-game.
  `python scripts/measure_mae.py` reproduces both from files, retraining
  nothing. The v1–v4 numbers (0.0954 / 0.0910 / 0.0902 / 0.0904) stay retired,
  all measured with the momentum leak in place, and `brownlow_model.py`'s
  printed "0.0953 full model" is grouped CV on training seasons, comparable to
  neither. See `project_brief.md`, "## Model". Posts still carry no accuracy
  percentage unless Charlie supplies it.
  The Predictions page's "MAE 0.095" header and tile were replaced on 27
  September 2026 by the top-pick record, computed from files by
  `top_pick_record()` in `dashboard.py` (2026: 145 of 207, 70%).
- **Feature count**: 93 total

### From 2027: the stack (`stack.py`)

Built 27 September 2026 after the count exposed the classifier's flat
probabilities. A Plackett-Luce layer over (a) this classifier's within-game
fitted P(3) and poll, (b) an `XGBRanker` grouped by game on the 93 features plus
`features.build_extra_features` (last season's actual votes, footywire metres
gained / real score involvements / intercepts), and (c) within-game z of
disposals, goals, marks, tackles, hitouts. It draws the 3, then the 2, then the
1, so every game hands out exactly 3-2-1 and `Exp_Votes` sums to 6.

- **Evidence** (`ranker_backtest.py`): beats the classifier in 12 of 13
  walk-forward seasons (log loss 1.235 to 1.199); in 2026 level with Sportsbet's
  3-vote board on log loss (0.797 vs 0.805), behind on Brier (0.0703 vs 0.0679).
  No EV screen off it made money. Single-season differences under ~0.015 log loss
  are noise: column order alone moves them.
- **The layer is fitted on the latest season's OUT-OF-SAMPLE scores** (base
  models trained without it), then the base models are refitted including it.
  The latest season is the regime (2026: first with umpire stats access), so the
  layer carries it and is refitted after every count.
- **No extra weight on the latest season in the base models.** Measured: 3x or
  6x beat equal weight in 4 of 13 seasons and made the 2026 prediction worse.
- **In-sample guard.** `apply_if_ready` refuses any season `<= trained_through`,
  so while `stack.pkl` is trained through 2026 the 2026 site stays the
  classifier's, byte for byte. It first speaks for 2027.
- **2026 votes** live in `data_2026/brownlow_votes_2026.csv`
  (`scripts/fetch_brownlow_votes.py`); `game_level_2026.csv` still reads 0.
- **Rollover to 2027:** move `ranker_backtest.LAST_SEASON`, write
  `data_2027/brownlow_votes_2027.csv` after that count, rerun `python stack.py train`.

**Why the stack ships as built: the off-season check, 5 October 2026.** In plain
terms: the model picks the right player but undersold its picks in 2026 (said
59%, took the 3 about 70%), because 2026 was the first season umpires saw stats
and they voted more predictably. The stack's final layer, fitted on 2026's
votes, teaches it both to be more confident and to weight stats the way the
umpires now do. Every figure below is out of sample:

| 2026, P(3) of each game's favourite | Said | Took | Log loss |
|---|---|---|---|
| Displayed on the site (classifier, `P_3_game`) | 58.6% | 68.6% | |
| Stack, layer fitted on 2025 | 57.5% | 72.0% | 0.911 |
| Stack, layer fitted on 2026 rounds 1-8, scored on 9-25 | 66.5% | 75.7% | 0.798 |
| Stack, layer fitted on 2026, each round held out | 71.9% | 72.5% | 0.813 |

- **The stack alone does not fix 2026; the 2026-fitted layer does.** Fitted on
  earlier seasons, the stack is as compressed on 2026 as the classifier. In
  2013-2025 pooled it is calibrated (favourite said 59.9%, took 59.5%), so the
  2026 defect was the umpires changing, not the model.
- **The regime z terms carry real 2026 signal.** Layer on 2026 rounds 1-8 scored
  on 9-25: 0.830 without the z terms, 0.798 with them; rounds 1-13 to 14-25:
  0.772 against 0.726.
- **They cost something in an ordinary year.** Walk-forward 2014-2025, layer
  fitted on the season before, mean log loss: one season with z 1.230 (the
  shipping recipe, worst of the five), one season no z 1.203, three seasons no z
  1.197, three seasons with z 1.201. Ridge on the z weights (50) cut the
  ordinary-year cost to 1.213 but gave back most of the 2026 gain.
- **Decision: ship the one-season layer with z, fitted on 2026,** because
  umpires keep stats access and ignoring the regime brings back exactly the
  compression that broke 2026. **If the 2027 count shows the shift faded,
  fall back to three seasons without z.**
- **The layer can never be refitted mid-season.** Votes are secret until the
  count, so the 2026 layer is what readers see all of 2027 and it is judged only
  after the 2027 count. Until then any published probability is "fitted to
  2026", not proven. The rounds 1-8 test above uses 2026 votes and is not a
  2027 option; it only measures what a 2026-fitted layer captures.
- **Mechanics rehearsed:** the saved `stack.pkl`, its guard relaxed in memory,
  ran over all 207 games of `game_level_2026.csv` with no null `P_*` and every
  game summing to exactly 1 for `P_3` and 6 for `Exp_Votes`. That proves it runs,
  not its 2026 figures (in sample).
- **This settles the parked `Exp_Votes` fix for the live season** (see below):
  from 2027 `predict_2026.py` takes `P_1`-`P_3` and `Exp_Votes` from the stack.
  Only the historical figures in `brownlow_model.py` and `backtest.py` stay the
  classifier's.
- The test scripts were scratch and are not in the repo. Both tests reuse
  `ranker_backtest` functions: base models trained on seasons before s, then
  `fit_pl` on season s-1's (or early 2026's) out-of-sample scores, with and
  without `regime_z`.

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
- **Fitting `Exp_Votes` itself was parked until after count night**, and from
  2027 the stack does it (see "Why the stack ships as built"). It would
  move public totals a week before the count (Heeney 22.9 to 21.1, Gawn 17th to
  14th, Daicos 48 to 46 on the 3-2-1 board). A source fix belongs in
  `predict_2026.py`, `brownlow_model.py` and `backtest.py`, which all compute
  `Exp_Votes` from the raw columns. Any sampler of a game's 3-2-1 must condition
  within the game (see `scripts/count_sim.py`), never draw the three columns
  independently.

**Measured against the completed 2026 count, 207 games out of sample. The
ordering is excellent and the probabilities are compressed toward the middle.**
That one defect explains every result below, and it is a calibration problem
rather than a model problem.

What the ordering got right: the winner, the top three in order, 17 of the top
20, and the model's first pick in a game took the three votes in **145 of 207
games (70.0%)** against a 56.6% backtest baseline. The 3-2-1 board read Daicos
48 against an actual 47, Cripps and Heeney exactly, MAE 1.70 votes.

What the probabilities got wrong. **There are two P(3)s and they must not be
confused**; `python scripts/calibration_2026.py` prints both, every 2026
player-game, from files:

| Stated P(3) | Displayed (`P_3_game`): n, said, took the 3 | Priced (isotonic, `sb_3vote_board`): n, said, took the 3 |
|---|---|---|
| 0.60 to 1.00 | 97, 71.6%, **86.6%** | 94, 75.5%, **86.2%** |
| 0.35 to 0.60 | 114, 47.9%, **55.3%** | 117, 48.7%, **56.4%** |
| 0.20 to 0.35 | 108, 26.8%, 19.4% | 108, 26.4%, 19.4% |
| 0.10 to 0.20 | 152, 14.2%, 12.5% | 162, 14.1%, 12.3% |
| 0.05 to 0.10 | 188, 7.4%, 6.4% | 100, 7.9%, 6.0% |
| Favourite per game | said 58.6%, took 142 of 207 | said 60.5%, took 143 of 207 |

**Displayed** is what readers saw on Game Analysis and the Player Profile, and is
the table on the site's Model Insights tab. **Priced** is that figure through
the isotonic map `sb_3vote_board.py` fits on the 2008-2025 backtest to price
Sportsbet's board; it was never shown to a reader.

Corrected 29 September 2026. The table first recorded here was the PRICED
figure presented as "model `p`", with no column named. Its top three buckets and
its 60.5% favourite reproduce exactly from the priced column; its bottom two
(192 at 14.0% to 10.4%, 149 at 7.8% to 4.0%) and its 69.6% favourite hit rate
do not reproduce from anything on disk, most likely an earlier state of the
files, and are withdrawn. With them goes the claim that the model "roughly
doubles the tail": the tail is overstated by one to two points, not twofold.
What stands in both columns: near-certainties understated by about 15 points
and the favourite by about 10, with the market (69.5% on the favourite) close
to the truth.

Two consequences worth stating before anyone builds on these numbers again. Any
EV screen over them points the wrong way twice, refusing the favourites the
model is right about and flagging the tail where it is most wrong; the 2026
boards went 27 from 287 on 3-vote value picks, -67.9% ROI, while blindly backing
the model's own top pick returned -5.8%. And the same compression is why
`Exp_Votes` under-predicts every one of the actual top ten (Daicos 39.6 against
47) where the 3-2-1 board does not, which is the first real evidence that the
within-game fit above is the right call.

Recalibrate against `backtest_game_level.csv` and validate on the 207 games of
2026 before any probability from this model is published or staked again.

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

## Injury data

**Nothing else in this repo records WHY a player did not play.** Every other
file records who took the field, so a count of players used, or of changes week
to week, cannot tell a hamstring from a form drop. `data_injury/` is the only
source that can, built from the AFL's weekly "Medical room: The full AFL injury
list" articles by `scripts/fetch_injury_lists.py` then
`scripts/build_injury_ladder.py`. 2026 on; there is no back catalogue here.

**The two measures disagree, and it is not a rounding difference.** Hawthorn
used 40 players in 2026, equal third most in the league, and lost 126 games to
injury, third fewest: that gap is rotation. Sydney used 36, equal fifth fewest,
and lost 231 games, fifth most. Do not use a selection count as an injury proxy
in either direction.

**A game counts as missed only if the player was listed AND did not play.** 686
of 2026's 3,760 entries read "Test" as the estimated return and 265 of those
players played. The published list is not a list of absentees, and counting it
alone rewards clubs that report their doubtfuls diligently.

**`Experience_missed` is confounded by list age, and must be published as an
experience figure rather than as a hardest-hit figure.** Games missed runs
r = -0.602 against 2026 wins (p = 0.008); weighting each missed game by the
player's career games takes that to r = -0.039 (p = 0.88). North Melbourne top
the experience ladder, having lost Jackson Archer (26 career games), Toby Pink
(37) and George Wardlaw (52), and finished 14th. Brisbane and Sydney sit near
the bottom of it and finished 3rd and 2nd. It is the measure the newspaper
injury ladders use and it answers "how much experience was missing", nothing
more.

**Article IDs are per season and cannot be derived.** `afl.com.au` resolves
`/news/<id>/<slug>` by ID and **ignores the slug**: a wrong ID serves the home
page with HTTP **200**, and a real ID under a wrong slug serves that ID's
article. So the round in the URL proves nothing, every page is verified against
its own `<title>`, and the 25 IDs for 2026 were each found by searching the
exact headline. A new season means a new `ARTICLE_IDS` block, found the same
way; there is no working news search API on the site.

**Club comes from the strap image before each table, never from table order**,
and the naming changed three times across 2026: `carlton.jpeg`, then
`..._Straps-Badge-Refresh_CARL_FA-1x.jpg`, then the clubs' Indigenous names in
Sir Doug Nicholls Round (`kuwarna`, `walyalup`, `narrm`, `yartapuulti`,
`euro-yroke`, `waalitj`). An unresolved filename **raises** rather than falling
through to the previous club, and the resolved 18-club sequence is asserted
against alphabetical order on every page. Both guards were earned: matching only
`.jpg|.png` missed Carlton's `.jpeg` and handed Carlton's and Collingwood's
tables to Brisbane, and Round 10's `kuwarna_2026.jpg` would have filed
Adelaide's list under Brisbane.

**An unmatched name is the EXPECTED case here, which inverts the usual rule.**
The stats archive only holds players who played, so a season-ending injury makes
a player invisible to it: Tom Green reads "Knee / Season" every week of 2026 and
appears in no row of `afltables_2026.csv`. `features.resolve_feed_names` runs
first and whatever it leaves is checked against the club's own season roster by
surname, accepted only when exactly one roster player has that surname and the
first names pass `first_names_compatible` or `first_names_aliased`. In 2026 that
separated 22 real variants from 99 genuine never-played cases and correctly
refused West Coast's "Tylah Williams" against a roster holding Bailey and Jack
Williams. Dropping that roster hop is not cosmetic: it counts "Dan Curtin" as
missing the rounds Daniel Curtin played, and gives him no career.

## Historical claims: default scope is ALL TIME

**Charlie's rule (1 October 2026): every "most / first / last time" stat is
checked all time, from the VFL's first season in 1897, by default.** Narrow it
to the AFL era (1990 on) or another window only when Charlie asks, or when the
all-time version is too broad to be interesting, and then say which window in
the claim itself. Never let a data file's start year set the scope silently:
the repo's per-game archive starts in 1965, and a ranking built on it alone
truncates careers (Doug Wade carried 834 career goals to North Melbourne in
1973, the 1965-on data reads 626) and misses earlier cases outright (Charlie
Dibbs, 216 games, to Geelong in 1936).

Sources that reach 1897, all off AFLTables, no token needed:

- **`afltables.com/afl/stats/<season>.html`**: every player, per club, per
  season: GM, GL, and BR (votes, 1984 on). Key players by the **player link
  href** (`players/G/Gary_Ablett1.html`), never by name: it is unique, so
  namesakes and father-son pairs (the two Gary Abletts, the two Herbie
  Matthews) stay apart. GM and GL **include finals**. All 130 seasons fetch in
  a few minutes at a 0.5s delay.
- **`afltables.com/afl/stats/teams/<club>/<season>_gbg.html`**: per-round
  goals (and other stats), with finals as `SF`/`PF`/`GF` columns, so a
  home-and-away-only figure (the Coleman count) is the sum of the `R<n>`
  columns. Needed whenever finals would change a ranking.
- **`afltables.com/afl/stats/players/<key>`**: date of birth, for any age
  qualifier.
- **Pre-1984 Brownlow votes**: `data_history/brownlow_seasons_1924_1983.csv`,
  season totals only (see the next section, including the doubled 1976-77
  pool).

Three things the all-time data does not do for you: a mid-season move
shows as two clubs in one season with no order; the stats pages cannot tell
a trade from free agency or a delisted pick-up ("changed clubs" is the honest
claim); and the Fitzroy to Brisbane Lions merger in 1997 reads as a move.

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

**The site needs no action.** From 2027 the Live Tracker is the Next.js page
`/live-tracker`, which flips itself from the model board to the live count off
the feed's own status field, with no cold start to worry about. If asked
whether the count is live, `python scripts/count_night.py status` answers from
that same feed (repointed 29 September 2026; on the night of the 2026 count it
read the award endpoint and wrongly said PREDICTOR throughout).

## Count night and the Live Tracker

**READ THIS FIRST: the award endpoint NEVER carried the live count on 21
September 2026, and everything below it in this section was written on the
assumption that it would.** Five rounds into the broadcast it was still
byte-identical to the predictor snapshot taken on 10 September, while the AFL's
own live tracker page showed the real votes. It stayed that way all night. The
snapshot comparison is therefore not a way of telling the predictor from the
count: it is a way of telling the predictor from itself, and it answers
PREDICTOR forever.

**The live votes are on a different host, found by sniffing what the AFL's own
live tracker page requests:**

```
https://api.afl.com.au/cfs/afl/bfawards/season/{seasonProviderId}
https://api.afl.com.au/cfs/afl/bfawards/leaderboard/season/{seasonProviderId}
```

`CD_S2026014` is 2026's; `bfawards_feed.season_ids()` now looks both ids up by
season name, so a new season needs no constant. It needs the same `x-media-mis-token` that
`fetch_match_chains.py` mints (`POST /cfs/afl/WMCTok`, with `Origin`, `Referer`
and an explicit `Content-Length: 0`), and it returns **401** without one.

**It carries an explicit `status` field ("LIVE").** That is the thing the award
endpoint has never had and the whole reason the snapshot design existed. Prefer
it over any before-picture comparison.

**`scripts/bfawards_feed.py` is the adapter, and it returns rows in the award
endpoint's shape**, so `count_night.digest` and `count_tweets.build_context`
work unchanged. Three things in it are load-bearing:

- **`roster=True` merges the award endpoint's full player list underneath the
  live votes, with `totalVotes` zeroed.** The live feed carries vote-getters and
  nobody else. Several things downstream ask a question about a player BECAUSE
  he polled nothing, and the snub block is one: it wants the model's first pick
  in a game to have no votes, and it cannot tell "polled zero" from "absent from
  the payload". Without the merge it silently drafts nothing, which is exactly
  what happened for the first eleven rounds of the 2026 count. Two real snubs
  (rounds 1 and 4) were lost live and only recovered by replay.
- **The award endpoint's ROSTER and ids stay valid even when its votes are
  stale**, so it remains the authority on identity. Club and player ids map by
  id, never by name, and an unmapped one raises.
- **`roster=False` skips the 21-page award walk** for the Live Tracker, which
  refetches every 60 seconds and bridges on name plus club.

**What is repointed and what is not, as of 29 September 2026:**

| Reads the live feed | Still reads the stale award endpoint |
|---|---|
| `count_tweets._read_feed` | `count_night.py` `snapshot`, `fetch`, `classify` (legacy) |
| `count_slip.py` | |
| `count_night.py` `status`, `rounds` | |
| the Next.js `/api/tracker` route | |
| `dashboard.fetch_live_brownlow_data` (falls back; app retired) | |

Everything below this block is the 2026 pre-count design. Keep it for the
fallback path, which `dashboard.py` still uses when the live feed is
unreachable, and do not trust its central claim.

`aflapi.afl.com.au/afl/v2/compseasons/{id}/award/brownlow`.
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

**Retired with the app, 29 September 2026: `.github/workflows/keepalive.yml`
and `scripts/keepalive.py` are deleted.** For the record, the job drove a real
browser. A curl ping cannot do this job: Streamlit
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

**The Streamlit app is retired (29 September 2026).** `dashboard.py` stops after
`st.set_page_config` with a "we've moved" screen that sends an old `?page=`
deep link to its chachingbrownlow.com path, unless `CC_STREAMLIT_LIVE=1` is set.
The file stays because `calibration.py` and `sb_3vote_board.py` lift functions
out of it by AST and the parity scripts render it headless. Everything below
describes the retired app.

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
