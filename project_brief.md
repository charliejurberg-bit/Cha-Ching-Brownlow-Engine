# Cha Ching — Project Brief
> Paste this once at the start of each Claude session. Do not paste full source files.
> Regenerated from actual repo state. Locate code by function name, never by line number.

## Project overview
AFL Brownlow predictor + betting research tool. Streamlit dashboard deployed on
Streamlit Cloud from GitHub (`charliejurberg-bit/Cha-Ching-Brownlow-Engine`).
Persistence via Supabase. Live since Round 10 2026.
Location: `C:\Users\charl\Python\brownlow_engine\`

**STRATEGY:** Free public launch targeting AFL betting forums, early August 2026.
Build a timestamped public track record through Brownlow night (late Sept), which
is the launch milestone. Monetisation later via bookmaker affiliate links — no
paywall, no paid tips. Betting Hub is PRIVATE/personal; the public product is the
Brownlow section only.

## Tech stack
- **Python 3.13**, Streamlit (dark theme), XGBoost, pandas, numpy, scikit-learn, plotly, requests
- **Supabase** — cloud persistence for bets, Cha Ching tips, Polls-a-Vote watchlist, player props (source of truth; local CSV fallback)
- **Playwright** — live Betfair + ESPN prediction fetch inside `dashboard.py`
- **undetected_chromedriver** — Oddschecker multi-bookmaker scraper (`scraper_odds.py`, local only)
- Data sources: fitzRoy (AFL stats via R), Wheelo ratings, Oddschecker, Betfair, ESPN, AFL Predictor API
- **Model v4.0** — MAE 0.0904, top-10 accuracy ~86%, exact medallist in top-3 ~50%. Trained on 2015–2025 H&A rounds. Round count varies by season: 2024+ seasons add an Opening Round (Opening Round + 24 rounds), so their AFLTables `Round_num` runs one ahead — see `_display_round` / `_OPENING_ROUND_FROM = 2024` in dashboard.py.
- `requirements.txt`: streamlit, pandas, plotly, xgboost, requests, numpy, scikit-learn, supabase, openpyxl

## File structure
```
brownlow_engine/
├── dashboard.py              # Main app — all Brownlow pages + hub router + global CSS
├── betting_hub.py            # Betting Hub module — 5 pages, imported by dashboard.py
├── theme.py                  # Shared design tokens — inject_global_theme() used by both files
├── brownlow_model.py         # XGBoost model training (v4.0) — once per season
├── predict_2026.py           # In-season predictions — run weekly after each round
├── update.py                 # One-click update: R stats → coaches → odds → consensus → predict
├── backtest.py               # 10-season out-of-sample backtest
│
│  # Scrapers / data fetch
├── scraper_odds.py           # Oddschecker multi-bookie odds (undetected_chromedriver)
├── scraper_betfair.py        # Betfair Brownlow consensus (JSON API)
├── scraper_espn.py           # ESPN Brownlow consensus
├── scraper_afl.py            # AFL Predictor Brownlow votes (award API)
├── scraper_stats.py          # Squiggle API player stats
├── scraper_wheelo.py         # Wheelo ratings scraper
├── update_wheelo_2026.py     # Update 2026 Wheelo ratings
├── fetch_wheelo_historical.py# Historical Wheelo fetch
├── data_pull.py              # Historical data fetcher (fitzRoy/R)
│
│  # Data directories
├── data_2026/                # Live season data (18 files): afltables_2026.csv, coaches_votes_2026.csv,
│                             #   bookmaker_odds.csv, best_odds.csv, betfair/espn/afl_predictor *.csv (+ _prev),
│                             #   wheelo_brownlow_predictions.csv, fetch_stats_2026.R, fetch_coaches.R
├── data_wheelo/              # Wheelo ratings 2015–2026 + wheelo_all_seasons.csv (15 files)
├── data_betting/             # Betting Hub local fallback CSVs (bets, tips, polls, props) (4 files)
├── predictions/              # Model artifacts + output CSVs — tracked in git (55 files); Streamlit
│                             #   Cloud loads these at runtime and can't regenerate them on deploy
│                             #   model.pkl, features.pkl, label_encoder.pkl, rank_stats.pkl,
│                             #   wheelo_features.pkl, form_features.pkl, season_YYYY.csv,
│                             #   game_level_YYYY.csv, season_projection_2026.csv
├── page_modules_wip/         # Extracted page modules (page_*.py) — dead half-refactor; renamed from pages/ (see anomaly note below)
├── .streamlit/config.toml    # Dark theme (Midnight Turf colours)
└── requirements.txt
```

**Repo anomalies**
- `pages/` renamed to `page_modules_wip/`. Streamlit auto-discovers a `pages/` directory
  as multipage-app pages; `pages/page_player_profile.py` (and 11 sibling stubs) contained
  non-UTF-8 bytes (cp1252 `0x97` em-dash), so Streamlit hit `SyntaxError: invalid or missing
  encoding declaration` before first render → blank page for anonymous visitors on Streamlit
  Cloud. The directory is a dead half-refactor (nothing imports it); renaming removes it from
  auto-discovery while preserving the code and git history. The 12 files were also converted to UTF-8.

## Page structure

### Brownlow section (dashboard.py) — the public product
```python
_NAV_BROWNLOW = {
    "Overview": ["Leaderboard", "Live Tracker"],
    "Players":  ["Player Profile", "Player Comparison"],
    "Analysis": ["Stat Filter", "Game Analysis", "Model Comparison"],
}
```

### Betting Hub section — PRIVATE/personal
```python
_NAV_BETTING = {
    "BH Overview":  ["Performance", "Predictions", "Bet Tracker"],
    "BH Strategy":  ["Cha Ching Tips", "Trends & Analysis", "Polls a Vote"],
}
_BH_PAGES = {'Performance', 'Predictions', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis', 'Polls a Vote'}
```
> `_NAV_BROWNLOW`, `_NAV_BETTING` and `_BH_PAGES` are all defined in **dashboard.py**.
> The `Predictions` page is rendered inline in dashboard.py; every other BH page routes
> through `betting_hub.render_page(page)`. A hub toggle (`_render_hub_tabs()`) switches the
> nav rail between the Brownlow and Betting sections.

## Key functions — dashboard.py
| Function | Purpose |
|---|---|
| `inject_global_css()` | Midnight Turf global CSS injection |
| `apply_chart_theme(fig)` | Apply MT dark palette to a Plotly figure |
| `render_banner()` | Top banner (hub toggle + mode label) |
| `_read_data_range()` / `_read_backtest_range()` | Detect training / backtest year range from CSV |
| `_fix_team_names(df)` | Normalise legacy team names (e.g. Footscray → Western Bulldogs) |
| `_player_id_map()` | Map players to fitzRoy IDs for disambiguation |
| `_disambiguate_players(df)` | Append `(Team)` to same-name players |
| `load_season(season)` / `load_game(season)` | Load season- / game-level predictions CSV |
| `load_importance()` / `load_backtest()` | Load feature-importance / backtest CSV |
| `load_season_projection()` | Load Monte Carlo floor/ceiling projection |
| `load_all_historical()` | Load all historical game-level CSVs |
| `load_game_career()` / `load_season_career()` | Career-spanning game / season loaders |
| `_efficiency_from_df(df)` | Compute poll-DNA efficiency stats from a frame |
| `compute_player_efficiency(season)` / `..._career()` | Win/loss/disposal poll-rate DNA |
| `load_best_odds()` | Load Oddschecker best-odds CSV |
| `form_guide_dots(season, n_rounds=3)` | Recent-form dots for leaderboard |
| `fetch_live_brownlow_data()` | Live tracker from AFL public API |
| `_pw_get_html(url, ...)` | Playwright helper — fetch JS-rendered page |
| `_save_with_backup(df, csv_path)` | Save CSV, keep previous as `_prev` |
| `_load_csv_fallback(csv_path, rank_col)` | Load CSV with fallback rank column |
| `_rank_change_html(...)` | Rank-change arrow HTML |
| `_file_ts(path)` | File modification timestamp string |
| `normalise_name(name)` | Fuzzy player-name normalisation |
| `_fetch_betfair_api()` / `fetch_betfair_brownlow()` | Live Betfair votes via JSON API (CSV fallback) |
| `_fetch_espn_live()` / `fetch_espn_brownlow()` | Live ESPN votes via Playwright (CSV fallback) |
| `_round_floats(df)` | Round float columns |
| `_apply_mt_rows(df)` | MT alternating row colours |
| `_style_table(df)` / `_style_leaderboard_table(df)` | MT-styled Stylers |
| `_nav_select(cat_key)` | Nav selectbox on_change handler |
| `_render_hub_tabs()` | Brownlow / Betting hub toggle strip |
| `_render_page_nav()` | Sub-nav page tab strip |
| `_season_changed(page)` | Season selector on_change handler |
| `_assemble_live_tracker(...)` | Build the live tracker view |

## Key functions — betting_hub.py
| Function | Purpose |
|---|---|
| `inject_global_css()` | MT CSS (also called by dashboard.py) |
| `apply_chart_theme(fig)` | MT chart theme |
| `_get_supabase()` / `_supabase_available()` | Supabase client from `st.secrets` + availability check |
| `_sb_records(df)` | DataFrame → Supabase snake_case records |
| `_ensure_dirs()` | Create local data dirs |
| `_load_player_avgs()` | Load player stat averages |
| `_load_watchlist()` / `_save_watchlist(df)` | Polls-a-Vote watchlist load/save (Supabase source of truth) |
| `_save_polls_row()` / `_mark_poll_settled()` / `_delete_poll_row()` | Watchlist row ops |
| `_load_bets()` / `_insert_bet()` / `_save_bets(df)` | Bets ledger (Supabase + CSV fallback) |
| `_load_tips()` / `_save_tip(...)` / `_delete_tip()` / `_save_tip_result(...)` | Cha Ching tips CRUD |
| `_sync_tip_to_bets(...)` | Sync a settled tip into the bets ledger |
| `_load_props()` / `_save_prop(...)` | Player-props cache |
| `_load_user_import()` / `_load_user_import_as_bets()` | User CSV import → bets schema |
| `_compute_pl(odds, stake, result)` | P&L calculation |
| `_betting_stats(df)` | Hit rate / ROI / P&L summary |
| `_fetch_fixtures()` | Upcoming fixtures |
| `_game_key(row)` / `_game_label(row)` | Fixture identifiers |
| `_pl_chart(df)` | Cumulative P&L Plotly figure |
| `_bar_chart(...)` / `_metric_card(...)` / `_pl_tone(v)` | Chart + card helpers |
| `_add_multi_dialog()` / `_checklist_dialog()` / `_open_checklist(...)` | Dialogs |
| `_add_bet_dialog()` / `_import_csv_dialog()` | Add-bet / CSV-import dialogs |
| `render_bh_dashboard()` | Performance page |
| `render_bet_tracker()` | Bet Tracker page |
| `render_cha_ching_tips()` | Cha Ching Tips page (edit lock reads `st.secrets["TIPS_EDIT_PASSWORD"]`, fail-closed) |
| `_render_market_tab(...)` / `_render_manual_props()` | Tips market UI |
| `render_trends_analysis()` | Trends & Analysis page |
| `render_polls_a_vote()` | Polls a Vote watchlist page |
| `render_page(page)` | BH page router (called from dashboard.py) |

## UI theme — Midnight Turf
- **background** `#0a1017`, **surface** `#101a24`, **emerald** `#34d399`,
  **gold** `#f0b429`, **muted red** `#ef7a6d` (betting/loss contexts ONLY — never model errors)
- **Archivo** for display headings, **Sora** for UI text, **DM Mono** for all numerics
- Streamlit `config.toml`: `base=dark`, `primaryColor=#34d399`, `backgroundColor=#0a1017`,
  `secondaryBackgroundColor=#101a24`, `textColor=#e9eef3`

**Laws:**
- Colour encodes information, not decoration.
- Displayed round is **season-aware**: use `_display_round(round_num, season)` (single home
  in `dashboard.py`) at render only — never mutate stored/filtered/joined `Round_num`.
  Seasons ≥ 2024 opened with an Opening Round, so their AFLTables `Round_num` runs 1 ahead
  (subtract 1); 2007–2023 map 1:1. `_display_rounds(df)` is the vectorised form for
  game-level dataframes (uses the df's `Season` column). Live Tracker and betting_hub
  Polls-a-Vote key their models in display-round space via their own `- 1` join logic on
  2026-only data — left as-is (not render sites).
- Animated / JS content must live in `st.iframe(html, height=N)` iframes (raw-HTML
  form; renders a real `<iframe srcdoc=…>`, so JS runs and cross-frame
  `window.parent.document` still resolves). Replaced `components.html()`, which was
  removed after 2026-06-01. Note: `st.iframe` rejects `height=0` — use `height=1`
  for invisible utility iframes and hide the container via CSS.
- Use the marker-div `:has()` pattern for CSS targeting.

## Pre-launch checklist (current priorities, in order)
1. **Blank page for anonymous visitors** — app hangs before first render on Streamlit
   Cloud; suspect a startup network call with no timeout. **CRITICAL.**
2. **Make Betting Hub private** — **DONE.** Session-state gate (`bh_authed`) at the router
   chokepoint in `dashboard.py` (before line 2277), so it covers every `_BH_PAGES` page
   including the inline Predictions block; password checked against `st.secrets["BH_PASSWORD"]`,
   then `st.rerun()`. Cha Ching Tips edit-lock now reads `st.secrets["TIPS_EDIT_PASSWORD"]`.
   Both **fail closed**: a missing secret denies access rather than crashing or falling open.
   Brownlow section untouched. Removes personal P&L, bet history, and tips from the public build.
3. **Responsible gambling footer** on every public page — **DONE.** Helper
   `_render_rg_footer()` in `dashboard.py`, called at the dispatch chokepoint (the
   "Responsible-gambling footer" block at the very end of the file) guarded by
   `if _page not in _BH_PAGES`. Full-bleed Midnight Turf footer (surface `#101a24`,
   muted text, thin top border): 18+ / gamble responsibly, Gambling Help Online
   1800 858 858, "informational not betting advice". Renders on all Brownlow pages
   (Landing included); excluded on `_BH_PAGES` and the password-gate screen (gate
   `st.stop()`s earlier, so it never reaches the footer).
4. **Round 17 vs Round 18 display mismatch** — **DONE.** Root cause: 2024+ seasons open
   with an Opening Round, so AFLTables `Round_num` runs 1 ahead — some render sites applied
   the `−1`, others didn't. Centralised on a single season-aware helper `_display_round(round_num,
   season)` (+ vectorised `_display_rounds(df)`) in `dashboard.py`, used at every live render
   site: banner, Landing hero/stat strip, Predictions, Player Profile (best-round label, career/
   season trajectory chart, game-log table), Game Analysis (selector/header/overline), the
   **Stat Filter "Sample games" table** (the reported bug — was raw), and the 3 Player Comparison
   round-by-round charts. Pre-2024 seasons now map 1:1 (fixes a latent bug where Player Profile
   subtracted 1 unconditionally). Join/keying logic left untouched (Live Tracker `_assemble`,
   betting_hub Polls-a-Vote) — those operate in display space on 2026-only data. Dead `if False:`
   blocks left as-is. Verified in-app: all surfaces read Round 17; historical rows un-offset.
5. **Migrate `st.components.v1.html` to `st.iframe`** — **DONE.** All 7 call sites in
   `dashboard.py` migrated to `st.iframe(html, height=N)` (Landing ticker/hero/stat
   strip; Live Tracker error header, no-data header, live panel; global animated
   counter). Dropped the `scrolling=` arg (no such param; each iframe controls its own
   overflow). Removed both `import streamlit.components.v1` lines. Counter kept `height=1`
   (st.iframe rejects `height=0`); its container is still hidden by the
   `iframe[srcdoc*="_ccAnimated"]` CSS rule, which still matches (st.iframe emits
   `<iframe srcdoc=…>`). Cross-frame `window.parent.document` verified working in-browser.
   `requirements.txt` now pins `streamlit>=1.57` (st.iframe hard dependency).
7. **Rename the Streamlit subdomain** to something clean.
8. **UI cleanup batch:** unsorted League Efficiency Rankings table; duplicate auto-refresh
   checkbox on Live Tracker; loading spinners on Poll Probability + Stat Filter;
   "2015–2026" copy vs 2007 slider; tooltips for jargon (Bolters, CV, ExpV, MAE, 0R).

## Conventions
- Locate code by function name, never line number.
- PowerShell only (`Select-String`, never `grep`).
- One task per session; atomic commits (one concern per commit).
- Stop and report if structure is ambiguous — don't guess.
- Keep `dashboard.py` closed in VS Code during edits; format-on-save off.

## How to ask for help efficiently
- **Never paste full files.** Reference by filename + function name.
- **Paste only the relevant function** (20–50 lines max).
- **For errors:** paste the traceback + the function it points to, nothing else.
- **For UI changes:** describe the page name + paste the render function only.
- **For new features:** state the page, the goal, and any relevant data shape.

## Example efficient prompt
> "In betting_hub.py, `render_bh_dashboard()` is crashing when `_load_bets()` returns an
> empty DataFrame. Here's the function: [paste 20 lines]. Fix it to handle the empty case gracefully."
