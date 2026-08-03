# Cha Ching — Brownlow Medal Predictor & Betting Hub

Personal AFL Brownlow Medal prediction + betting tracker. XGBoost model (v4.0) trained on 2015–2025 data. Dashboard runs live during the 2026 season.

> **Read `project_brief.md` first.** It contains the current page structure, accurate line numbers for every function, the correct file sizes, the Midnight Turf colour tokens, and up-to-date known issues. The sections below cover architecture and constraints that change rarely.

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

## Project structure

```
brownlow_engine/
├── dashboard.py          # Main Streamlit app — 4000+ lines, all pages + CSS
├── betting_hub.py        # Betting Hub module, imported by dashboard.py
│
├── brownlow_model.py     # Model training (v4.0) — runs once per season
├── predict_2026.py       # In-season predictor — run after each round
├── update.py             # One-click: stats → odds → predict
│
├── scraper_stats.py      # Pulls player stats from Squiggle API → data_2026/
├── scraper_odds.py       # Scrapes multi-bookie odds from Oddschecker (undetected-chromedriver)
├── data_pull.py          # Historical data fetcher (fitzRoy / R)
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
├── data_2026/            # Current season raw data
│   ├── afltables_2026.csv    # Player stats (from R/fitzRoy)
│   ├── coaches_votes_2026.csv
│   ├── bookmaker_odds.csv    # Wide: Player | Bookie1 | Bookie2 | …
│   └── best_odds.csv         # Long: player, best_odds, implied_prob, best_bookie
│
├── data_wheelo/          # Wheelo rating data (per-round, per-player)
│   ├── wheelo_all_seasons.csv
│   └── wheelo_2026.csv
│
├── data_betting/         # Betting Hub persistent storage
│   ├── bets.csv          # Bet log (bet_id, date, match, market, selection, odds, result…)
│   └── cha_ching_tips.csv
│
└── fitzroy_stats_all.csv      # Historical stats 2015–2025 (training data)
    coaches_votes_all.csv      # Historical coaches votes 2006–2025
```

## Tech stack

| Layer | Tech |
|---|---|
| Dashboard | Streamlit (wide layout, collapsed sidebar) |
| Charts | Plotly (paper_bgcolor/plot_bgcolor match earthy palette) |
| Model | XGBoost `XGBClassifier` (multiclass: 0/1/2/3 votes) |
| Data — historical | fitzRoy (R package) via `fetch_extended_data.R` |
| Data — live stats | Squiggle API (`api.squiggle.com.au`) |
| Data — odds | Oddschecker scrape via `undetected-chromedriver` + BeautifulSoup |
| Data — coaches votes | fitzRoy `fetch_coaches_votes()` |
| Serialisation | `pickle` for model artifacts |

## Model architecture (v4.0)

- **Algorithm**: `XGBClassifier` — predicts 0/1/2/3 Brownlow votes per player per game
- **Training data**: 2015–2025 H&A rounds only (finals filtered; string-labeled rounds → NaN)
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
2. **Wheelo** (18): `RatingPoints`, `ExpVotes`, per-quarter ratings (`Rating_Q1`–`Q4`), equity components, ground ball gets, Supercoach, `TimeOnGround`, `DisposalEfficiency` + `Rating_Q4_premium`, `Best_quarter_rating`
3. **Relative game** (~44): per-stat rank/percentile/z-score within each game (`{stat}_game_rank`, `_game_pct`, `_game_z`); BOG and Top3 flags for disposals, coaches votes, impact, rating
4. **Form/Momentum** (3): `late_form_ewm` (EWMA span=5 of prior rounds — no lookahead), `momentum_cv`, `momentum_disp` (last-6 vs first-6 game averages)

**Prediction outputs** (per game): `P_1`, `P_2`, `P_3`, `Poll_Prob` (P_1+P_2+P_3), `Exp_Votes` (weighted expected value).

**Season projection**: Monte Carlo (10,000 simulations) over completed rounds → 10th/90th percentile floor/ceiling.

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

- **Round numbering**: from **2024 onward** AFLTables numbers Opening Round as Round 1, so its round numbers run 1 ahead of the AFL's official count (AFLTables Round 12 = AFL Round 11). **The subtraction is conditional on season, not unconditional.** The rule is `rn - 1 if sn >= _OPENING_ROUND_FROM else rn`, with `_OPENING_ROUND_FROM = 2024`; subtracting for a pre-2024 season is wrong. `_display_round` is defined in **three** places, `dashboard.py`, `draft_posts.py` and `streaks.py`, each carrying its own copy of the constant, so changing one means changing all three. Display only: the underlying data and all filtering always use the raw AFLTables `Round_num` value. Total H&A rounds in AFLTables for 2026 = 23 (Rounds 1–23).
- **Finals excluded**: Rounds with string labels (QF/EF/SF/PF/GF) are coerced to NaN and dropped in both training and prediction. Max H&A round detected dynamically per season (2023 and prior seasons had 24 rounds; current code handles any count).
- **No lookahead in form**: `late_form_ewm` uses `.shift(1)` before the EWMA so current-round data is never included.
- **Same-name disambiguation**: Players sharing a name but on different teams get `Name (Team)` appended.
- **Wheelo merge key**: Player + Team + Season + Round (team required to disambiguate e.g. two players named "Bailey Williams").
- **Model retrain**: Only needed at start of season or when feature set changes. Predictions (`predict_2026.py`) run weekly after each round.
- **Odds scraper**: Uses `undetected-chromedriver` (headless Chrome) to bypass Cloudflare on Oddschecker. Fragile — may need `--headless=new` flag updates if site changes.
