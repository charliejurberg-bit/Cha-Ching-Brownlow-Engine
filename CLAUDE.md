# Cha Ching — Brownlow Medal Predictor & Betting Hub

AFL Brownlow Medal predictor plus a betting tracker. XGBoost model (v4.0) trained on 2007–2025 data. Dashboard runs live during the 2026 season.

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

`python update.py` runs the ten step weekly chain (stats, odds, predictions,
drafts, landing artifact). One-off checks tied to a particular round are
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

Background: the root cause does not live in `predict_2026.py`. The zero-source
guard in `features.py` (`ZERO_SOURCE_GUARD_STATS`, applied inside
`build_game_rank_features`) sets the **raw `Coaches_Votes` column** to NaN for a
game whose votes are all zero, not just the derived rank/pct/z triplet, and it
runs before the routing test. An unpublished game therefore reaches the
predicate holding NaN rather than 0, and any NaN-unsafe comparison reads that as
"votes published" and sends the game to the full model, so `model_nocv.pkl`
never engages. Keep that predicate NaN safe in any rewrite.

## Project structure

```
brownlow_engine/
├── dashboard.py          # Main Streamlit app — 7,838 lines. Brownlow pages + hub
│                         #   router + global CSS. NOT all pages: the Betting Hub
│                         #   pages render from betting_hub.py (except Predictions)
├── betting_hub.py        # Betting Hub module, imported by dashboard.py
│
├── brownlow_model.py     # Model training (v4.0) — runs once per season
├── predict_2026.py       # In-season predictor — run after each round
├── update.py             # One-click: stats → odds → predict
│
├── scraper_stats.py      # Pulls player stats from Squiggle API → data_2026/
├── scraper_odds.py       # Scrapes multi-bookie odds from Oddschecker (undetected-chromedriver)
├── scraper_advanced.py   # footywire advanced match stats → data_advanced/. The
│                         #   ONLY source of real Score Involvements. See
│                         #   "Score involvements" below before touching it
├── build_score_involvements.py  # Joins the above onto fitzRoy IDs. Refuses to
│                         #   write below a 98% match rate
├── data_pull.py          # EMPTY, 0 bytes. Not a fetcher. The R paths that do
│                         #   work are fetch_extended_data.R and scripts/build_history.R
├── fetch_extended_data.R # R script for fitzRoy data (coaches votes etc.)
├── backtest.py           # Backtesting harness
│
├── predictions/          # Model artifacts + CSV outputs
│   ├── model.pkl         # Trained XGBClassifier
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

**Season projection**: Monte Carlo (10,000 simulations) over completed rounds → 10th/90th percentile floor/ceiling.

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
  `build_score_involvements.py`. `round_bests.py` already refuses to rank the
  engineered column, and says why in a comment worth reading: a record only
  works as a record when it is the same quantity the rest of the world counts.

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

Consequences worth knowing before this replaces anything: any career-total
format built on the engineered column is measuring a quantity nobody recognises
and cannot be rebuilt honestly from the real stat, because a career total needs
the whole career and the real one starts in 2015.
`drafts/fewest_games_score_involvements_1000.md` and the matching ladder in
`fewest_games.py` are both in that position.

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

CSS lives in **one large `st.markdown()` block** at the top of `dashboard.py` (lines ~20–390) and a `BH_CSS` string constant in `betting_hub.py`. All Streamlit widget overrides use `!important`.

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

**Key CSS patterns:**
- Cards use layered box-shadow: `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04)`
- Hover lifts: `transform: translateY(-2px)` + heavier shadow
- Section headers (`.section-header`, `.trend-header`): 10px / 800 weight / 2px letter-spacing / `::before` full-height green or gold vertical bar
- Metric labels: 10px / 700 / 1px letter-spacing
- Anti-aliasing: `* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }`
- Custom scrollbar: 6px, `#cfc4b0` thumb, `#8b6f47` on hover
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
