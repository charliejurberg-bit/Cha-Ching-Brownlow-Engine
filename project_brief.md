# Cha Ching — Project Brief
> Paste this once at the start of each Claude session. Do not paste full source files.

## Project overview
AFL Brownlow Medal predictor + personal betting tracker. Streamlit dashboard, live since Round 10 2026.
Location: `C:\Users\User\Python\brownlow_engine\`

## Tech stack
- Python 3.10, Streamlit, XGBoost, pandas, plotly, requests
- Data: FitzRoy (AFL stats), Wheelo ratings, Oddschecker scraping
- Model v4.0 — MAE 0.0904, trained 2007–2025, top-10 accuracy 86%

## File structure
```
brownlow_engine/
├── dashboard.py          # Main app — 3400 lines — Brownlow section (12 pages)
├── betting_hub.py        # Betting Hub section — 1277 lines (4 pages)
├── brownlow_model.py     # XGBoost model definition
├── predict_2026.py       # 2026 season predictions
├── backtest.py           # 10-season backtest
├── scraper_odds.py       # Oddschecker odds scraper (98 players, 8 bookmakers)
├── fetch_wheelo_historical.py
├── data_2026/            # Season stats
├── data_wheelo/          # Wheelo ratings
├── data_betting/         # Bet tracking CSVs
└── predictions/          # Model output CSVs
```

## Page structure

### Brownlow section (dashboard.py)
Navigation defined at line 1491:
```python
_ALL_NAV = {
    "Overview": ["Home", "Leaderboard", "Live Tracker"],
    "Players":  ["Player Profile", "Player Comparison"],
    "Analysis": ["Stat Filter", "Coaches Votes", "Game Analysis", "Model Insights", "Model Comparison"],
    "Betting":  ["Value Finder", "Season Projection", "Betting Edge"],
}
```
Season-dependent pages (have round/season selector): Leaderboard, Player Profile, Game Analysis, Model Insights, Betting Edge.

### Betting Hub section (betting_hub.py)
```python
_BH_PAGES = {'BH Dashboard', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis'}
```

## Key functions — dashboard.py
| Function | Line | Purpose |
|---|---|---|
| `load_season(season)` | 855 | Load season stats DataFrame |
| `load_game(season)` | 860 | Load game-level data |
| `load_importance()` | 865 | Load feature importance |
| `load_backtest()` | 870 | Load backtest results |
| `load_season_projection()` | 875 | Load floor/ceiling projections |
| `load_all_historical()` | 880 | Load all historical seasons |
| `load_best_odds()` | 924 | Load Oddschecker odds |
| `compute_player_efficiency(season)` | 891 | DNA tab stats |
| `fetch_live_brownlow_data()` | 955 | Live tracker API |
| `fetch_betfair_brownlow()` | 1197 | Scrape Betfair odds |
| `fetch_espn_brownlow()` | 1269 | Scrape ESPN predictions |
| `_style_leaderboard_table(df)` | 1437 | Leaderboard styling |
| `_nav_select(cat_key)` | 1503 | Navigation state |
| `normalise_name(name)` | 1180 | Player name matching |

## Key functions — betting_hub.py
| Function | Line | Purpose |
|---|---|---|
| `_load_bets()` | 67 | Load bets DataFrame from CSV |
| `_save_bets(df)` | 84 | Save bets DataFrame |
| `_load_tips()` | 92 | Load Cha Ching tips |
| `_save_tip(...)` | 100 | Save a tip |
| `_load_props()` | 122 | Load player props |
| `_compute_pl(odds, stake, result)` | 146 | P&L calculation |
| `_betting_stats(df)` | 156 | Hit rate, ROI, P&L summary |
| `_pl_chart(df)` | 494 | Cumulative P&L plotly chart |
| `_checklist_dialog()` | 568 | Cha Ching checklist UI |
| `render_bh_dashboard()` | 853 | Dashboard page renderer |
| `render_bet_tracker()` | 945 | Bet Tracker page renderer |
| `render_cha_ching_tips()` | 1079 | Tips page renderer |
| `render_trends_analysis()` | 1264 | Trends page renderer |
| `render_page(page)` | 1432 | Page router |

## UI theme — Midnight Turf

```python
COLORS = {
    "bg_base":        "#0f1923",   # dark navy — page background
    "bg_surface":     "#152533",   # cards, panels
    "bg_elevated":    "#1e3a4a",   # hover states, elevated cards
    "accent":         "#34d399",   # emerald — primary CTA, positive values
    "gold":           "#f0b429",   # medals, #1 prediction, top bets
    "red":            "#e05252",   # losses, negative delta, warnings
    "blue":           "#4a90c4",   # secondary info, model stats
    "text_primary":   "#e8f0f8",   # headings, important numbers
    "text_secondary": "#94a3b8",   # labels, body text
    "text_muted":     "#4a5a6a",   # section headers, disabled
    "border":         "#2a4a5a",   # card borders, dividers
}
```

Fonts: Sora (headings/UI), DM Mono (numbers/odds/code)
Personality: sharp, premium, data-driven

## Known issues (active)
1. `st.plotly_chart()` duplicate key errors — needs unique `key=` on every chart call
2. Game Analysis page — low visual contrast, needs separation between sections
3. ~~UI feels static~~ — Midnight Turf design system applied (Round 10 2026)

## Current priorities
1. Fix plotly_chart duplicate IDs across dashboard
2. Redesign Game Analysis page
3. Complete Cha Ching checklist criteria
4. Browser-use skill for odds scraping
5. Brownlow night live tracker (September)

## How to ask for help efficiently
- **Never paste full files.** Reference by filename + line number.
- **Paste only the relevant function** (20–50 lines max).
- **For errors:** paste the traceback + the function it points to, nothing else.
- **For UI changes:** describe the page name + paste the render function only.
- **For new features:** state the page, the goal, and any relevant data shape.

## Example efficient prompt
> "In dashboard.py around line 924, `load_best_odds()` is returning an empty DataFrame when the CSV doesn't exist. Here's the function: [paste 15 lines]. Fix it to return an empty DataFrame with the correct columns."
