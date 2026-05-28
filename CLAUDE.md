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
- **MAE**: 0.0904 (v1: 0.0954, v2: 0.0910, v3: 0.0902)
- **Feature count**: 93 total

**Feature groups:**
1. **Base** (28): raw stats (Kicks, Disposals, Goals, Clearances, etc.) + engineered ratios (`Kick_to_HB_ratio`, `Contested_rate`, `Disposal_efficiency`, `Score_Involvements`, `Impact_Score`) + game context (Margin, Is_Win, Coaches_Votes)
2. **Wheelo** (18): `RatingPoints`, `ExpVotes`, per-quarter ratings (`Rating_Q1`–`Q4`), equity components, ground ball gets, Supercoach, `TimeOnGround`, `DisposalEfficiency` + `Rating_Q4_premium`, `Best_quarter_rating`
3. **Relative game** (~44): per-stat rank/percentile/z-score within each game (`{stat}_game_rank`, `_game_pct`, `_game_z`); BOG and Top3 flags for disposals, coaches votes, impact, rating
4. **Form/Momentum** (3): `late_form_ewm` (EWMA span=5 of prior rounds — no lookahead), `momentum_cv`, `momentum_disp` (last-6 vs first-6 game averages)

**Prediction outputs** (per game): `P_1`, `P_2`, `P_3`, `Poll_Prob` (P_1+P_2+P_3), `Exp_Votes` (weighted expected value).

**Season projection**: Monte Carlo (10,000 simulations) over completed rounds → 10th/90th percentile floor/ceiling.

## Dashboard pages

| Nav group | Pages |
|---|---|
| Overview | Landing (home), Home (season summary) |
| Players | Leaderboard, Player Profile, Player Comparison |
| Analysis | Live Tracker, Coaches Votes, Game Analysis, Model Insights, Model Comparison |
| Betting | Betting Edge, Stat Filter |
| BH Overview | Betting Hub Dashboard |
| BH Strategy | Bet Tracker, Cha Ching Tips, Trends & Analysis |

Navigation is implemented as **six horizontal `st.selectbox` dropdowns** (not `st.sidebar` or `st.tabs`). Page state is held in `st.session_state["page"]`.

Betting Hub pages are rendered via `betting_hub.render_page(page_name)` — the module is imported at top of `dashboard.py`.

## CSS design system

CSS lives in **one large `st.markdown()` block** at the top of `dashboard.py` (lines ~20–390) and a `BH_CSS` string constant in `betting_hub.py`. All Streamlit widget overrides use `!important`.

**Earthy colour palette — never change these:**
```
Background:    #faf7f2
Primary green: #2d5016
Light green:   #4a7a28
Tan/brown:     #8b6f47
Card bg:       #f0ece4
Gold (betting):#c9a84c
Light gold:    #e8c96d
Border:        #ddd5c5
Body text:     #2c2c2c
```

**Key CSS patterns:**
- Cards use layered box-shadow: `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04)`
- Hover lifts: `transform: translateY(-2px)` + heavier shadow
- Section headers (`.section-header`, `.trend-header`): 10px / 800 weight / 2px letter-spacing / `::before` full-height green or gold vertical bar
- Metric labels: 10px / 700 / 1px letter-spacing
- Anti-aliasing: `* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }`
- Custom scrollbar: 6px, `#cfc4b0` thumb, `#8b6f47` on hover
- Streamlit toolbar hidden: `[data-testid="stToolbar"] { display: none !important; }`

## Betting Hub data model

Bets stored in `data_betting/bets.csv` with columns:
`bet_id, date, match, market_type, selection, bookmaker, odds, stake, result, profit_loss, is_cha_ching, cha_ching_criteria, notes`

**Cha Ching tip** = bet flagged by ≥3 checklist items (role change, player in/out, EV positive, line movement, confirmed team selection, custom note). Threshold `CC_THRESHOLD = 3` in `betting_hub.py`.

Bookmakers tracked: Sportsbet, TAB, Betfair, Ladbrokes, Neds, PointsBet, Unibet.
Market types: Disposals O/U, Goals O/U, Kicks O/U, Handballs O/U, Marks O/U, Match Result, Line.

## Key decisions & constraints

- **Finals excluded**: Rounds with string labels (QF/EF/SF/PF/GF) are coerced to NaN and dropped in both training and prediction. Max H&A round detected dynamically per season (2023 and prior seasons had 24 rounds; current code handles any count).
- **No lookahead in form**: `late_form_ewm` uses `.shift(1)` before the EWMA so current-round data is never included.
- **Same-name disambiguation**: Players sharing a name but on different teams get `Name (Team)` appended.
- **Wheelo merge key**: Player + Team + Season + Round (team required to disambiguate e.g. two players named "Bailey Williams").
- **Model retrain**: Only needed at start of season or when feature set changes. Predictions (`predict_2026.py`) run weekly after each round.
- **Odds scraper**: Uses `undetected-chromedriver` (headless Chrome) to bypass Cloudflare on Oddschecker. Fragile — may need `--headless=new` flag updates if site changes.
