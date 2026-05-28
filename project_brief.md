# Cha Ching — Project Brief
> Paste this once at the start of each Claude session. Do not paste full source files.

## Project overview
AFL Brownlow Medal predictor + personal betting tracker. Streamlit dashboard, live since Round 10 2026.
Location: `C:\Users\charl\Python\brownlow_engine\`
Deployed: `https://cha-ching-brownlow-engine-7ns99ajvlasqotmxxbilyp.streamlit.app/`

## Tech stack
- Python 3.13, Streamlit (dark theme), XGBoost, pandas, plotly, requests, numpy, scikit-learn
- Supabase — cloud persistence for bets, tips, polls
- Playwright — Betfair + ESPN scraping (live odds/predictions inside dashboard.py)
- undetected_chromedriver — Oddschecker multi-bookmaker scraper (local only, `scraper_odds.py`)
- Data: FitzRoy (AFL stats via R), Wheelo ratings, Oddschecker, Betfair, ESPN
- Model v4.0 — trained 2007–2025, 23 H&A rounds modelled (dashboard displays R+1 offset, total 24)

## File structure
```
brownlow_engine/
├── dashboard.py              # Main app — 5189 lines — all Brownlow pages + hub router
├── betting_hub.py            # Betting Hub module — 2613 lines — 5 pages, imported by dashboard.py
├── brownlow_model.py         # XGBoost model training — 331 lines
├── predict_2026.py           # 2026 in-season predictions — 265 lines
├── backtest.py               # 10-season backtest — 284 lines
├── scraper_odds.py           # Oddschecker scraper (undetected_chromedriver) — 276 lines
├── scraper_wheelo.py         # Wheelo ratings scraper — 11220 bytes
├── fetch_wheelo_historical.py # Historical Wheelo fetch — 10473 bytes
├── update.py                 # One-click update: stats → odds → predictions — 88 lines
├── merge_wheelo.py           # Merge Wheelo into training data
├── backtest.py               # Out-of-sample accuracy testing
├── data_2026/                # Live season data
│   ├── afltables_2026.csv
│   ├── coaches_votes_2026.csv
│   ├── bookmaker_odds.csv
│   ├── best_odds.csv
│   ├── betfair_predictions.csv / betfair_predictions_prev.csv
│   ├── espn_predictions.csv / espn_predictions_prev.csv
│   ├── historical_model_comparison.csv
│   ├── fetch_stats_2026.R
│   └── fetch_coaches.R
├── data_wheelo/              # Wheelo ratings 2015–2026 + wheelo_all_seasons.csv
├── data_betting/             # Bet tracking CSVs (bets.csv, cha_ching_tips.csv, player_props_cache.csv)
├── predictions/              # Model output CSVs — gitignored, generated locally
│   ├── model.pkl / features.pkl / label_encoder.pkl / rank_stats.pkl
│   ├── wheelo_features.pkl / form_features.pkl
│   ├── season_YYYY.csv / game_level_YYYY.csv (2007–2026)
│   ├── season_projection_2026.csv
│   └── backtest_results.csv / feature_importance.csv
├── .streamlit/config.toml    # Dark theme (Midnight Turf colours)
└── requirements.txt          # streamlit, pandas, plotly, xgboost, requests, numpy, scikit-learn, supabase
```

## Page structure

### Brownlow section (dashboard.py)
Navigation defined at line 1655:
```python
_NAV_BROWNLOW = {
    "Overview": ["Home", "Leaderboard", "Live Tracker"],
    "Players":  ["Player Profile", "Player Comparison"],
    "Analysis": ["Stat Filter", "Coaches Votes", "Game Analysis", "Model Insights", "Model Comparison"],
}
```
Plus a `Landing` page (line 1944) shown on first load. The app also has a hub toggle at line 1865 ("Brownlow Predictor" / "Betting Hub") that switches the nav rail between the two sections.

### Betting Hub section (betting_hub.py, rendered via `betting_hub.render_page()`)
```python
_NAV_BETTING = {
    "BH Overview":  ["BH Dashboard", "Brownlow Betting", "Bet Tracker"],
    "BH Strategy":  ["Cha Ching Tips", "Trends & Analysis", "Polls a Vote"],
}
_BH_PAGES = {'BH Dashboard', 'Brownlow Betting', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis', 'Polls a Vote'}
```
`Brownlow Betting` is rendered inline in dashboard.py (line 2995). All other BH pages call `betting_hub.render_page(_page)`.

## Key functions — dashboard.py
| Function | Line | Purpose |
|---|---|---|
| `inject_global_css()` | 40 | Midnight Turf global CSS injection |
| `apply_chart_theme(fig)` | 372 | Apply MT dark palette to any Plotly figure |
| `render_banner()` | 408 | Top banner (hub toggle + mode label) |
| `_read_data_range()` | 989 | Detect training data year range from CSV |
| `_read_backtest_range()` | 1000 | Detect backtest year range |
| `_fix_team_names(df)` | 1014 | Normalise Footscray → Western Bulldogs |
| `load_season(season)` | 1021 | Load season-level predictions CSV |
| `load_game(season)` | 1026 | Load game-level predictions CSV |
| `load_importance()` | 1031 | Load feature importance CSV |
| `load_backtest()` | 1036 | Load backtest results CSV |
| `load_season_projection()` | 1041 | Load floor/ceiling projection CSV |
| `load_all_historical()` | 1046 | Load all historical game-level CSVs |
| `compute_player_efficiency(season)` | 1057 | Poll DNA stats (win/loss/disposal rates) |
| `load_best_odds()` | 1090 | Load Oddschecker best odds CSV |
| `form_guide_dots(season, n_rounds=3)` | 1095 | Recent form dots for leaderboard |
| `fetch_live_brownlow_data()` | 1121 | Live tracker from AFL public API |
| `_pw_get_html(url, ...)` | 1235 | Playwright helper — fetch JS-rendered page |
| `_save_with_backup(df, csv_path)` | 1292 | Save CSV keeping previous as _prev |
| `_load_csv_fallback(csv_path, rank_col)` | 1301 | Load CSV with fallback rank column |
| `_rank_change_html(csv_path, player, ...)` | 1310 | Render rank-change arrow HTML |
| `_file_ts(path)` | 1332 | File modification timestamp string |
| `normalise_name(name)` | 1346 | Fuzzy player name normalisation |
| `fetch_betfair_brownlow()` | 1363 | Scrape Betfair odds via Playwright |
| `fetch_espn_brownlow()` | 1435 | Scrape ESPN per-game votes via Playwright |
| `_round_floats(df, dp=1)` | 1586 | Round all float columns in a DataFrame |
| `_apply_mt_rows(df)` | 1592 | Apply MT alternating row colours |
| `_style_table(df)` | 1601 | Standard MT-styled Styler |
| `_style_leaderboard_table(df)` | 1614 | Leaderboard Styler with team-colour border |
| `_nav_select(cat_key)` | 1666 | Nav selectbox on_change handler |
| `_season_changed()` | 1895 | Season selector on_change handler |

### Page rendering (inline blocks in dashboard.py)
| Page | Line |
|---|---|
| Landing | 1944 |
| Home | 2038 |
| Leaderboard | 2224 |
| Player Profile | 2340 |
| Coaches Votes | 2677 |
| Game Analysis | 2801 |
| Brownlow Betting | 2995 |
| Stat Filter | 3150 |
| Model Insights | 3493 |
| Player Comparison | 3652 |
| Live Tracker | 4290 |
| Model Comparison | 4653 |

## Key functions — betting_hub.py
| Function | Line | Purpose |
|---|---|---|
| `inject_global_css()` | 53 | MT CSS (also called by dashboard.py) |
| `apply_chart_theme(fig)` | 108 | MT chart theme |
| `_get_supabase()` | 149 | Supabase client from st.secrets |
| `_load_polls()` | 171 | Load Polls a Vote watchlist CSV |
| `_save_polls_row(row)` | 185 | Append a poll row |
| `_mark_poll_settled(idx)` | 192 | Mark poll as settled |
| `_delete_poll_row(idx)` | 199 | Delete a poll entry |
| `_load_bets()` | 206 | Load bets from Supabase (fallback CSV) |
| `_insert_bet(row)` | 224 | Insert single bet to Supabase |
| `_save_bets(df)` | 232 | Upsert full bets DataFrame to Supabase |
| `_load_tips()` | 242 | Load Cha Ching tips CSV |
| `_save_tip(...)` | 260 | Save a new tip |
| `_save_tip_result(tip_id, result)` | 289 | Record tip result |
| `_sync_tip_to_bets(tip_id, tip_row, result, pl)` | 309 | Sync settled tip into bets ledger |
| `_load_props()` | 333 | Load player props cache |
| `_save_prop(...)` | 341 | Save a player prop |
| `_load_user_import()` | 354 | Load user-imported CSV |
| `_load_user_import_as_bets()` | 370 | Convert import CSV to bets schema |
| `_compute_pl(odds, stake, result)` | 422 | P&L calculation |
| `_betting_stats(df)` | 432 | Hit rate, ROI, P&L summary dict |
| `_fetch_fixtures()` | 465 | Fetch upcoming fixtures |
| `_pl_chart(df)` | 797 | Cumulative P&L Plotly figure |
| `_bar_chart(labels, values, title, color)` | 833 | Generic bar chart |
| `_metric_card(label, value, sub, tone)` | 852 | MT metric card HTML |
| `_checklist_dialog()` | 871 | Cha Ching checklist UI dialog |
| `_open_checklist(player, market, game_key, ...)` | 939 | Open checklist for a specific tip |
| `_add_bet_dialog()` | 953 | Add bet dialog |
| `_import_csv_dialog()` | 1024 | CSV import dialog |
| `render_bh_dashboard()` | 1218 | BH Dashboard page |
| `render_bet_tracker()` | 1311 | Bet Tracker page |
| `render_cha_ching_tips()` | 1451 | Cha Ching Tips page |
| `_render_market_tab(game_key, market_type, ...)` | 1800 | Render one market tab in Tips |
| `_render_manual_props()` | 1914 | Manual props entry UI |
| `render_trends_analysis()` | 1941 | Trends & Analysis page |
| `render_polls_a_vote()` | 2232 | Polls a Vote watchlist page |
| `render_page(page)` | 2600 | Page router (called from dashboard.py) |

## UI theme — Midnight Turf
Defined in `dashboard.py` at line 20 (`COLORS` dict):

```python
COLORS = {
    "bg_base":        "#0f1923",   # dark navy — page background
    "bg_surface":     "#152533",   # cards, panels
    "bg_elevated":    "#1e3a4a",   # hover states, elevated cards
    "bg_subtle":      "#1a2d3d",   # subtle backgrounds
    "accent":         "#34d399",   # emerald — primary CTA, positive values
    "accent_dim":     "#1a6b4a",
    "accent_glow":    "rgba(52,211,153,0.12)",
    "gold":           "#f0b429",   # medals, #1 prediction, top bets
    "gold_dim":       "#5c420a",
    "red":            "#e05252",   # losses, negative delta, warnings
    "red_dim":        "#5c1f1f",
    "blue":           "#4a90c4",   # secondary info, model stats
    "text_primary":   "#e8f0f8",   # headings, important numbers
    "text_secondary": "#94a3b8",   # labels, body text
    "text_muted":     "#4a5a6a",   # section headers, disabled
    "border":         "#2a4a5a",   # card borders, dividers
    "border_subtle":  "#1e3040",
}
```

Fonts: Sora (headings/UI), DM Mono (numbers/odds/code) — loaded via Google Fonts in `inject_global_css()`.
Icons: Tabler Icons webfont (`@tabler/icons-webfont`), referenced as CSS classes e.g. `ti-award`, `ti-tags`.
Streamlit theme: `config.toml` sets `base=dark`, `primaryColor=#34d399`, `backgroundColor=#0f1923`.

## Known issues (active)
1. `TOTAL_HA_ROUNDS = 23` in `predict_2026.py` but dashboard uses 24 — projection calc uses 23, display uses 24 (R+1 offset). Keep consistent when editing either file.
2. Plotly chart keys — mostly resolved with explicit `key="chart_NNN"` throughout; new charts must get a unique key.
3. Model Comparison page — pulls from `data_2026/historical_model_comparison.csv`; regenerated by `fill_historical_comparison.py`.

## Current priorities
1. Keep Polls a Vote data persistence solid (Supabase + CSV fallback)
2. Brownlow night live tracker polish (September 2026)
3. Model Comparison — ensure `historical_model_comparison.csv` stays current
4. Player props / Cha Ching Tips market coverage

## How to ask for help efficiently
- **Never paste full files.** Reference by filename + line number.
- **Paste only the relevant function** (20–50 lines max).
- **For errors:** paste the traceback + the function it points to, nothing else.
- **For UI changes:** describe the page name + paste the render function only.
- **For new features:** state the page, the goal, and any relevant data shape.

## Example efficient prompt
> "In betting_hub.py around line 1218, `render_bh_dashboard()` is crashing when `_load_bets()` returns an empty DataFrame. Here's the function: [paste 20 lines]. Fix it to handle the empty case gracefully."
