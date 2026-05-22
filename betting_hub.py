"""
betting_hub.py — Cha Ching Betting Hub
Four pages rendered by render_page(page_name) and imported into dashboard.py:
    BH Dashboard, Bet Tracker, Cha Ching Tips, Trends & Analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os, json, uuid, time, requests
from datetime import datetime, timedelta, date
from io import StringIO, BytesIO

# ── Constants ──────────────────────────────────────────────────────────────────

DATA_DIR        = "data_betting"
BETS_CSV        = f"{DATA_DIR}/bets.csv"
TIPS_CSV        = f"{DATA_DIR}/cha_ching_tips.csv"
FIXTURES_CSV    = f"{DATA_DIR}/fixtures_cache.csv"
PROPS_CSV       = f"{DATA_DIR}/player_props_cache.csv"
USER_IMPORT_CSV = f"{DATA_DIR}/user_import.csv"

BETS_COLS = [
    'bet_id', 'date', 'match', 'market_type', 'selection',
    'bookmaker', 'odds', 'stake', 'result', 'profit_loss',
    'is_cha_ching', 'cha_ching_criteria', 'notes',
]

CHECKLIST_ITEMS = [
    ("role_change",   "Role change"),
    ("player_in_out", "Player in/out affecting this player"),
    ("ev_positive",   "EV positive vs 2+ bookmakers"),
    ("line_movement", "Line movement in our favour"),
    ("team_selection","Confirmed team selection"),
    ("custom_note",   "Custom note"),
]

BOOKMAKERS   = ["Sportsbet", "TAB", "Betfair", "Ladbrokes", "Neds", "PointsBet", "Unibet", "Other"]
MARKET_TYPES = ["Disposals O/U", "Goals O/U", "Kicks O/U", "Handballs O/U", "Marks O/U",
                "Match Result", "Line", "Other"]
RESULTS      = ["Pending", "Win", "Loss", "Void/Refund"]
CC_THRESHOLD = 3   # checklist items needed to auto-flag a Cha Ching tip

C = dict(
    green='#34d399', lgreen='#1a5c40', gold='#f0b429', lgold='#f5c842',
    brown='#94a3b8', red='#e05252', bg='#152533', card='#1e3a4a',
    border='#2a4a5a', text='#e8f0f8',
)

def inject_global_css():
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1923 !important;
    color: #e8f0f8;
    font-family: 'Sora', sans-serif;
}
[data-testid="stAppViewContainer"] > .main { background-color: #0f1923 !important; }
[data-testid="block-container"] { padding-top: 1.5rem !important; max-width: 1200px; }
[data-testid="stSidebar"] {
    background-color: #0d1720 !important;
    border-right: 1px solid #2a4a5a !important;
}
h1, h2, h3, h4 {
    font-family: 'Sora', sans-serif !important;
    color: #e8f0f8 !important;
}
[data-testid="stMetric"] {
    background: #152533 !important;
    border: 1px solid #2a4a5a !important;
    border-radius: 10px !important;
    padding: 16px !important;
}
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 11px !important; text-transform: uppercase !important; }
[data-testid="stMetricValue"] { color: #e8f0f8 !important; font-family: 'Sora', sans-serif !important; font-weight: 700 !important; }
[data-testid="stDataFrame"] th {
    background: #1e3a4a !important; color: #94a3b8 !important;
    font-size: 11px !important; text-transform: uppercase !important;
}
[data-testid="stDataFrame"] td { background: #152533 !important; color: #e8f0f8 !important; }
[data-testid="stDataFrame"] tr:hover td { background: #1e3a4a !important; }
[data-testid="stSelectbox"] > div > div, [data-testid="stMultiSelect"] > div > div {
    background: #152533 !important; border: 1px solid #2a4a5a !important; color: #e8f0f8 !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    background: #152533 !important; border: 1px solid #2a4a5a !important; color: #e8f0f8 !important;
}
button[kind="primary"], [data-testid="baseButton-primary"] {
    background: #34d399 !important; color: #0a1f14 !important;
    border: none !important; font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
}
hr { border: none !important; border-top: 1px solid #2a4a5a !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1923; }
::-webkit-scrollbar-thumb { background: #2a4a5a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }
</style>
""", unsafe_allow_html=True)

def apply_chart_theme(fig):
    import plotly.graph_objects as _go
    fig.update_layout(
        paper_bgcolor="#152533",
        plot_bgcolor="#152533",
        font=dict(family="Sora, sans-serif", color="#94a3b8", size=12),
        title_font=dict(family="Sora, sans-serif", color="#e8f0f8", size=14),
        xaxis=dict(
            gridcolor="#1e3a4a",
            linecolor="#2a4a5a",
            tickcolor="#2a4a5a",
            tickfont=dict(color="#94a3b8", size=11),
        ),
        yaxis=dict(
            gridcolor="#1e3a4a",
            linecolor="#2a4a5a",
            tickcolor="#2a4a5a",
            tickfont=dict(color="#94a3b8", size=11),
        ),
        legend=dict(
            bgcolor="#1e3a4a",
            bordercolor="#2a4a5a",
            borderwidth=1,
            font=dict(color="#94a3b8", size=11),
        ),
        margin=dict(l=16, r=16, t=40, b=16),
    )
    fig.update_traces(marker_line_width=0)
    return fig

# ── Data layer ─────────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BETS_CSV):
        pd.DataFrame(columns=BETS_COLS).to_csv(BETS_CSV, index=False)
    if not os.path.exists(TIPS_CSV):
        pd.DataFrame(columns=[
            'tip_id', 'game_key', 'player', 'market_type', 'line',
            'bookmaker', 'odds', 'criteria_json', 'is_flagged', 'notes', 'created_at',
        ]).to_csv(TIPS_CSV, index=False)
    if not os.path.exists(PROPS_CSV):
        pd.DataFrame(columns=[
            'game_key', 'player', 'market_type', 'line', 'bookmaker', 'odds', 'updated_at',
        ]).to_csv(PROPS_CSV, index=False)


def _load_bets() -> pd.DataFrame:
    _ensure_dirs()
    try:
        df = pd.read_csv(BETS_CSV)
        for c in BETS_COLS:
            if c not in df.columns:
                df[c] = None
        df['date']        = pd.to_datetime(df['date'], errors='coerce')
        df['odds']        = pd.to_numeric(df['odds'], errors='coerce')
        df['stake']       = pd.to_numeric(df['stake'], errors='coerce')
        df['profit_loss'] = pd.to_numeric(df['profit_loss'], errors='coerce')
        df['is_cha_ching'] = df['is_cha_ching'].fillna(False).astype(bool)
        return df
    except Exception:
        return pd.DataFrame(columns=BETS_COLS)


def _save_bets(df: pd.DataFrame):
    _ensure_dirs()
    df_save = df.copy()
    if 'date' in df_save.columns:
        df_save['date'] = pd.to_datetime(df_save['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df_save.to_csv(BETS_CSV, index=False)


def _load_tips() -> pd.DataFrame:
    _ensure_dirs()
    try:
        return pd.read_csv(TIPS_CSV)
    except Exception:
        return pd.DataFrame()


def _save_tip(game_key: str, player: str, market_type: str,
              criteria: list[str], is_flagged: bool, notes: str = ''):
    _ensure_dirs()
    df = _load_tips()
    tip_id = str(uuid.uuid4())[:8]
    new_row = {
        'tip_id':       tip_id,
        'game_key':     game_key,
        'player':       player,
        'market_type':  market_type,
        'line':         '',
        'bookmaker':    '',
        'odds':         '',
        'criteria_json': json.dumps(criteria),
        'is_flagged':   is_flagged,
        'notes':        notes,
        'created_at':   datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(TIPS_CSV, index=False)


def _load_props() -> pd.DataFrame:
    _ensure_dirs()
    try:
        return pd.read_csv(PROPS_CSV)
    except Exception:
        return pd.DataFrame()


def _load_user_import() -> pd.DataFrame | None:
    """Return the user-imported spreadsheet, or None if not present."""
    if not os.path.exists(USER_IMPORT_CSV):
        return None
    try:
        return pd.read_csv(USER_IMPORT_CSV)
    except Exception:
        return None


def _delete_user_import():
    """Remove the user-imported spreadsheet from disk."""
    if os.path.exists(USER_IMPORT_CSV):
        os.remove(USER_IMPORT_CSV)


def _save_prop(game_key: str, player: str, market_type: str,
               line: float, bookmaker: str, odds: float):
    df = _load_props()
    mask = (df['game_key'] == game_key) & (df['player'] == player) & (df['market_type'] == market_type)
    new_row = {
        'game_key': game_key, 'player': player, 'market_type': market_type,
        'line': line, 'bookmaker': bookmaker, 'odds': odds,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    if mask.any():
        df.loc[mask, list(new_row.keys())] = list(new_row.values())
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(PROPS_CSV, index=False)


def _compute_pl(odds: float, stake: float, result: str) -> float:
    if result == 'Win':
        return round((odds - 1) * stake, 2)
    elif result == 'Loss':
        return round(-stake, 2)
    elif result == 'Void/Refund':
        return 0.0
    return 0.0


def _betting_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return dict(total_bets=0, wins=0, losses=0, pending=0,
                    total_staked=0.0, total_returned=0.0, total_pl=0.0,
                    roi=0.0, hit_rate=0.0,
                    cc_bets=0, cc_hits=0, cc_pl=0.0, cc_hit_rate=0.0, cc_roi=0.0)
    settled  = df[df['result'].isin(['Win', 'Loss'])]
    wins     = len(settled[settled['result'] == 'Win'])
    losses   = len(settled[settled['result'] == 'Loss'])
    staked   = df['stake'].fillna(0).sum()
    total_pl = df['profit_loss'].fillna(0).sum()
    roi      = total_pl / staked * 100 if staked > 0 else 0.0
    hit_rate = wins / len(settled) * 100 if len(settled) > 0 else 0.0
    cc       = df[df['is_cha_ching'] == True]
    cc_set   = cc[cc['result'].isin(['Win', 'Loss'])]
    cc_wins  = len(cc_set[cc_set['result'] == 'Win'])
    cc_st    = cc['stake'].fillna(0).sum()
    cc_pl    = cc['profit_loss'].fillna(0).sum()
    cc_hit   = cc_wins / len(cc_set) * 100 if len(cc_set) > 0 else 0.0
    cc_roi   = cc_pl / cc_st * 100 if cc_st > 0 else 0.0
    return dict(
        total_bets=len(df), wins=wins, losses=losses,
        pending=len(df[df['result'] == 'Pending']),
        total_staked=staked, total_returned=staked + total_pl,
        total_pl=total_pl, roi=roi, hit_rate=hit_rate,
        cc_bets=len(cc), cc_hits=cc_wins,
        cc_pl=cc_pl, cc_hit_rate=cc_hit, cc_roi=cc_roi,
    )


# ── Fixture fetching ───────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_fixtures() -> pd.DataFrame:
    """Fetch upcoming AFL fixtures from Squiggle API, cached 24 hours."""
    try:
        import datetime as _dt
        year = _dt.date.today().year
        resp = requests.get(
            f"https://api.squiggle.com.au/?q=games;year={year}",
            headers={"User-Agent": "ChaChingDashboard/1.0 (contact: charlie.jurberg@gmail.com)"},
            timeout=15,
        )
        data = resp.json()
        games = data.get('games', [])
        if not games:
            return pd.DataFrame()
        df = pd.DataFrame(games)
        df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        now   = pd.Timestamp.now(tz='UTC')
        ahead = now + pd.Timedelta(days=7)
        mask  = (df['date_parsed'] >= now) & (df['date_parsed'] <= ahead)
        if 'complete' in df.columns:
            mask &= (df['complete'] == 0)
        return df[mask].sort_values('date_parsed').reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _game_key(row) -> str:
    return f"{row.get('roundname','R?')} {row.get('hteam','H')} v {row.get('ateam','A')}"


def _game_label(row) -> str:
    dt = row.get('date_parsed')
    date_str = ''
    if pd.notna(dt):
        try:
            date_str = pd.Timestamp(dt).strftime('%a %d %b %H:%M')
        except Exception:
            pass
    return f"{row.get('hteam','?')} v {row.get('ateam','?')} — {date_str}"


# ── CSS ────────────────────────────────────────────────────────────────────────

BH_CSS = """
<style>
/* ── Landing page cards ── */
.landing-card {
    background: #152533;
    border: 1px solid #2a4a5a;
    border-radius: 12px;
    padding: 44px 36px 40px 36px;
    text-align: center;
    cursor: pointer;
    transition: transform 0.22s cubic-bezier(0.23,1,0.32,1), box-shadow 0.22s ease;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    min-height: 240px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    will-change: transform;
}
.landing-card.brownlow { border-top: 3px solid #34d399; }
.landing-card.betting  { border-top: 3px solid #f0b429; }
.landing-card:hover { transform: translateY(-4px); box-shadow: 0 12px 36px rgba(0,0,0,0.4); border-color: #3a6a7a; }
.landing-card:active { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0,0,0,0.25); }
.landing-icon  { font-size: 54px; margin-bottom: 14px; line-height: 1; }
.landing-title { font-size: 28px; font-weight: 900; letter-spacing: -0.5px; margin-bottom: 10px; }
.landing-title.brownlow { color: #34d399; }
.landing-title.betting  { color: #f0b429; }
.landing-desc  { color: #94a3b8; font-size: 13px; line-height: 1.6; max-width: 320px; }

/* ── Nav section pills ── */
.nav-section-pill {
    display: inline-block;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 4px;
    margin-top: 8px;
    white-space: nowrap;
    cursor: pointer;
    transition: opacity 0.15s ease, transform 0.15s ease;
}
.nav-section-pill:hover { opacity: 0.85; transform: translateY(-1px); }
.nav-pill-brownlow { background: #34d399; color: #0f1923; }
.nav-pill-betting  { background: #f0b429; color: #0f1923; }

/* ── Betting metric cards ── */
.bh-metric {
    background: #152533;
    border: 1px solid #2a4a5a;
    border-radius: 8px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15), 0 4px 12px rgba(0,0,0,0.12);
    cursor: default;
    transition: box-shadow 0.18s ease, transform 0.18s ease;
    will-change: transform;
}
.bh-metric:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.2); transform: translateY(-2px); }
.bh-metric.positive { border-top: 3px solid #34d399; }
.bh-metric.negative { border-top: 3px solid #e05252; }
.bh-metric.neutral  { border-top: 3px solid #4a5a6a; }
.bh-metric.gold     { border-top: 3px solid #f0b429; }
.bh-label { color: #94a3b8; font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
.bh-value { font-size: 26px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.15; }
.bh-value.pos  { color: #34d399; }
.bh-value.neg  { color: #e05252; }
.bh-value.neu  { color: #e8f0f8; }
.bh-value.gold { color: #f0b429; }
.bh-sub   { color: #94a3b8; font-size: 11px; margin-top: 4px; line-height: 1.4; }

/* ── Bet result badges ── */
.bet-win     { background: rgba(52,211,153,0.18);  color: #34d399; border: 1px solid rgba(52,211,153,0.4);  padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-loss    { background: rgba(224,82,82,0.18);   color: #e05252; border: 1px solid rgba(224,82,82,0.4);   padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-pending { background: rgba(240,180,41,0.15);  color: #f0b429; border: 1px solid rgba(240,180,41,0.4);  padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-void    { background: rgba(74,90,106,0.25);   color: #94a3b8; border: 1px solid #2a4a5a;               padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }

/* ── Cha Ching tip badge ── */
.cc-badge {
    background: #f0b429;
    color: #0f1923;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

/* ── Fixture card ── */
.fixture-card {
    background: #152533;
    border: 1px solid #2a4a5a;
    border-top: 2px solid #34d399;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.15);
    cursor: default;
    transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
    will-change: transform;
}
.fixture-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.3); transform: translateY(-2px); border-color: #34d399; }
.fixture-teams { font-size: 15px; font-weight: 700; color: #e8f0f8; letter-spacing: -0.2px; }
.fixture-meta  { font-size: 12px; color: #94a3b8; margin-top: 3px; line-height: 1.4; }

/* ── Checklist item ── */
.cl-progress { font-size: 13px; color: #94a3b8; margin: 8px 0; line-height: 1.5; }

/* ── Anti-aliasing & font rendering ── */
* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1923; }
::-webkit-scrollbar-thumb { background: #2a4a5a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }

/* ── Trend section header ── */
.trend-header {
    color: #34d399; font-size: 10px; font-weight: 800;
    letter-spacing: 2px; text-transform: uppercase;
    border-bottom: 1px solid #2a4a5a; padding-bottom: 6px;
    margin: 24px 0 14px 0;
}

/* ── Cha Ching badge pulse on hover ── */
.cc-badge { transition: opacity 0.15s ease, transform 0.15s ease; display: inline-block; }
.cc-badge:hover { opacity: 0.88; transform: scale(1.03); }

/* ── Checklist progress line ── */
.cl-progress { transition: color 0.15s ease; }

/* ── BH page content fade-in ── */
@keyframes bhPageEnter {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── BH column stagger ── */
@keyframes bhColEnter {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
[data-testid="stColumn"] { animation: bhColEnter 0.3s ease both; }
[data-testid="stColumn"]:nth-child(1) { animation-delay: 0ms; }
[data-testid="stColumn"]:nth-child(2) { animation-delay: 60ms; }
[data-testid="stColumn"]:nth-child(3) { animation-delay: 120ms; }
[data-testid="stColumn"]:nth-child(4) { animation-delay: 180ms; }

/* ── BH chart reveal ── */
@keyframes bhChartReveal {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
}
[data-testid="stPlotlyChart"] { animation: bhChartReveal 0.4s ease both; }

/* ── BH skeleton — shimmer ── */
@keyframes bhShimmerSweep {
    0%   { background-position: 200% center; }
    100% { background-position: -200% center; }
}
.bh-sk-card {
    background: #152533;
    border: 1px solid #2a4a5a;
    border-radius: 8px;
    padding: 18px 22px;
    margin: 6px 0;
    overflow: hidden;
}
.bh-sk-title, .bh-sk-line {
    background: linear-gradient(90deg, #1e3a4a 25%, #2a4a5a 50%, #1e3a4a 75%);
    background-size: 200% 100%;
    animation: bhShimmerSweep 1.4s linear infinite;
    border-radius: 4px;
}
.bh-sk-title { height: 13px; width: 40%; margin-bottom: 12px; }
.bh-sk-line  { height: 8px;  margin-bottom: 8px; }
.bh-sk-line.wide  { width: 82%; }
.bh-sk-line.med   { width: 55%; animation-delay: 0.1s; }
.bh-sk-line.short { width: 30%; animation-delay: 0.22s; }

/* ── BH card entrance ── */
@keyframes bhCardEntrance {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.bh-metric {
    animation: bhCardEntrance 0.32s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}

/* ── BH number pop ── */
@keyframes bhNumberPop {
    0%   { opacity: 0.15; transform: translateY(5px) scale(0.92); }
    70%  { transform: translateY(-1px) scale(1.02); }
    100% { opacity: 1;    transform: translateY(0) scale(1); }
}
.bh-value {
    animation: bhNumberPop 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    animation-delay: 0.07s;
}

/* ── Bet row slide-in ── */
@keyframes betRowEnter {
    from { opacity: 0; transform: translateX(-8px); }
    to   { opacity: 1; transform: translateX(0); }
}
.bet-row-enter { animation: betRowEnter 0.22s ease both; }

/* ── BH section header reveal ── */
@keyframes bhSectionReveal {
    from { opacity: 0; transform: translateX(-6px); }
    to   { opacity: 1; transform: translateX(0); }
}
.section-header { animation: bhSectionReveal 0.22s ease both; }

/* ── Cha Ching section header ── */
.cc-section-header {
    color: #f0b429;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 1px solid #2a4a5a;
    padding-bottom: 6px;
    margin: 24px 0 14px 0;
}

</style>
"""


def _inject_css():
    st.markdown(BH_CSS, unsafe_allow_html=True)


# ── Shared chart helpers ───────────────────────────────────────────────────────

def _pl_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty or df['profit_loss'].dropna().empty:
        fig.update_layout(
            paper_bgcolor=C['bg'], plot_bgcolor=C['bg'],
            height=240,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            annotations=[dict(text="No settled bets yet", showarrow=False,
                              font=dict(color=C['brown'], size=14))],
        )
        return fig

    ds = df.sort_values('date').reset_index(drop=True)
    ds['cum_pl'] = ds['profit_loss'].fillna(0).cumsum()

    pos_mask = ds['cum_pl'] >= 0
    fig.add_trace(go.Scatter(
        x=ds['date'], y=ds['cum_pl'],
        mode='lines',
        line=dict(color=C['green'], width=2.5),
        fill='tozeroy',
        fillcolor='rgba(52,211,153,0.08)',
        name='P&L',
        hovertemplate='%{x|%d %b %Y}<br><b>%{y:+.2f} units</b><extra></extra>',
    ))
    fig.add_hline(y=0, line_dash='dot', line_color=C['brown'], line_width=1.2)
    fig.update_layout(
        paper_bgcolor=C['bg'], plot_bgcolor=C['bg'],
        font_color=C['text'], height=260, showlegend=False,
        xaxis=dict(gridcolor='#1e3a4a', showgrid=True, title=''),
        yaxis=dict(gridcolor='#1e3a4a', showgrid=True, zeroline=False, title='Units'),
        margin=dict(l=60, r=20, t=10, b=40),
    )
    return fig


def _bar_chart(labels, values, title, color=None):
    colors = [C['green'] if v >= 0 else C['red'] for v in values] if color is None else color
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[f'{v:.1f}' for v in values],
        textposition='outside',
    ))
    fig.update_layout(
        paper_bgcolor=C['bg'], plot_bgcolor=C['bg'],
        font_color=C['text'], height=280, showlegend=False,
        title=dict(text=title, font=dict(size=12, color=C['brown'])),
        xaxis=dict(gridcolor='#1e3a4a'),
        yaxis=dict(gridcolor='#1e3a4a', zeroline=True, zerolinecolor=C['border']),
        margin=dict(l=50, r=20, t=40, b=60),
    )
    return fig


def _metric_card(label: str, value: str, sub: str = '', tone: str = 'neutral') -> str:
    val_class = {'positive': 'pos', 'negative': 'neg', 'gold': 'gold'}.get(tone, 'neu')
    sub_html = f'<div class="bh-sub">{sub}</div>' if sub else ''
    return (
        f'<div class="bh-metric {tone}">'
        f'<div class="bh-label">{label}</div>'
        f'<div class="bh-value {val_class}">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _pl_tone(v: float) -> str:
    return 'positive' if v > 0 else ('negative' if v < 0 else 'neutral')


# ── Checklist dialog ───────────────────────────────────────────────────────────

@st.dialog("Cha Ching Checklist", width="small")
def _checklist_dialog():
    player     = st.session_state.get('_cl_player', 'Player')
    market     = st.session_state.get('_cl_market', 'Market')
    game_key   = st.session_state.get('_cl_game', '')
    pfx        = f"_clv_{game_key}_{player}_{market}_"

    st.markdown(f'<div style="font-weight:700;font-size:15px;color:{C["green"]};margin-bottom:4px">'
                f'{player}</div>', unsafe_allow_html=True)
    st.caption(f'{market}  ·  {game_key}')
    st.markdown('<hr style="margin:8px 0">', unsafe_allow_html=True)

    ticked = 0
    for item_key, item_label in CHECKLIST_ITEMS:
        sk = f"{pfx}{item_key}"
        checked = st.checkbox(item_label, value=st.session_state.get(sk, False), key=sk)
        if checked:
            ticked += 1

    if ticked >= CC_THRESHOLD:
        st.success(f"**Cha Ching!** {ticked}/6 criteria — auto-flagged as a tip")
    else:
        remaining = CC_THRESHOLD - ticked
        st.info(f"{ticked}/6 criteria met — tick {remaining} more to auto-flag")

    st.markdown('<hr style="margin:8px 0">', unsafe_allow_html=True)
    notes = st.text_area("Notes", value=st.session_state.get(f'{pfx}notes', ''),
                         key=f'{pfx}notes', height=60, placeholder='Any extra context...')

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Tip", type="primary", use_container_width=True):
            criteria = [k for k, _ in CHECKLIST_ITEMS if st.session_state.get(f"{pfx}{k}", False)]
            _save_tip(game_key, player, market, criteria, ticked >= CC_THRESHOLD, notes)
            st.toast(f"Tip saved — {'Cha Ching flagged!' if ticked >= CC_THRESHOLD else 'not yet flagged'}")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


def _open_checklist(player: str, market: str, game_key: str):
    st.session_state['_cl_player']  = player
    st.session_state['_cl_market']  = market
    st.session_state['_cl_game']    = game_key
    _checklist_dialog()


# ── Add Bet dialog ─────────────────────────────────────────────────────────────

@st.dialog("Add New Bet", width="large")
def _add_bet_dialog():
    pre = st.session_state.get('_bet_prefill', {})
    tips_df = _load_tips()
    flagged_tips = tips_df[tips_df['is_flagged'] == True] if not tips_df.empty else pd.DataFrame()

    col1, col2 = st.columns(2)
    with col1:
        bet_date = st.date_input("Date", value=pre.get('date', date.today()))
        match    = st.text_input("Match", value=pre.get('match', ''), placeholder='e.g. GWS v Melbourne')
        market   = st.selectbox("Market", MARKET_TYPES,
                                index=MARKET_TYPES.index(pre.get('market_type', MARKET_TYPES[0])))
        bookmaker = st.selectbox("Bookmaker", BOOKMAKERS,
                                 index=BOOKMAKERS.index(pre.get('bookmaker', BOOKMAKERS[0])))
    with col2:
        selection = st.text_input("Selection", value=pre.get('selection', ''),
                                  placeholder='e.g. Nick Daicos 29.5+ disposals')
        odds  = st.number_input("Odds (decimal)", min_value=1.01, max_value=100.0,
                                value=pre.get('odds', 2.0), step=0.05, format='%.2f')
        stake = st.number_input("Stake (units)", min_value=0.01, max_value=1000.0,
                                value=pre.get('stake', 1.0), step=0.5, format='%.2f')
        result = st.selectbox("Result", RESULTS,
                              index=RESULTS.index(pre.get('result', 'Pending')))

    is_cc = st.checkbox("Cha Ching tip", value=pre.get('is_cha_ching', False))

    if not flagged_tips.empty and not is_cc:
        with st.expander("Pre-fill from flagged Cha Ching tips"):
            for _, row in flagged_tips.head(5).iterrows():
                if st.button(f"{row['player']} — {row['market_type']} ({row['game_key']})",
                             key=f"prefill_{row['tip_id']}"):
                    st.session_state['_bet_prefill'] = {
                        'selection': f"{row['player']} {row['market_type']}",
                        'market_type': row['market_type'],
                        'is_cha_ching': True,
                    }
                    st.rerun()

    notes = st.text_area("Notes", height=60, placeholder='Optional context...')

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Save Bet", type="primary", use_container_width=True):
            pl = _compute_pl(float(odds), float(stake), result) if result != 'Pending' else 0.0
            new_row = {
                'bet_id':           str(uuid.uuid4())[:8],
                'date':             bet_date.strftime('%Y-%m-%d'),
                'match':            match,
                'market_type':      market,
                'selection':        selection,
                'bookmaker':        bookmaker,
                'odds':             round(float(odds), 2),
                'stake':            round(float(stake), 2),
                'result':           result,
                'profit_loss':      pl,
                'is_cha_ching':     is_cc,
                'cha_ching_criteria': '',
                'notes':            notes,
            }
            bets = _load_bets()
            bets = pd.concat([bets, pd.DataFrame([new_row])], ignore_index=True)
            _save_bets(bets)
            st.session_state.pop('_bet_prefill', None)
            st.toast("Bet saved!")
            st.rerun()
    with col_b:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop('_bet_prefill', None)
            st.rerun()


# ── CSV Import dialog ──────────────────────────────────────────────────────────

@st.dialog("Import Bets from CSV", width="large")
def _import_csv_dialog():
    st.caption("Supports Sportsbet and TAB export formats. Other formats will need column mapping.")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV file to continue.")
        if st.button("Cancel"):
            st.rerun()
        return

    try:
        raw = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    st.write(f"**{len(raw)} rows detected.** Column preview:")
    st.dataframe(raw.head(3), use_container_width=True)

    # Auto-detect format
    cols_upper = [c.upper() for c in raw.columns]

    def _has(*keys):
        return all(k in cols_upper for k in keys)

    fmt = 'unknown'
    if _has('PLACED DATE', 'STATUS', 'SELECTION', 'STAKE', 'RETURNS'):
        fmt = 'sportsbet'
    elif _has('DATE', 'EVENT TYPE', 'RACE/EVENT', 'STAKE', 'RETURN'):
        fmt = 'tab'
    elif _has('DATE', 'EVENT', 'SELECTION', 'STAKE'):
        fmt = 'generic'

    st.success(f"Detected format: **{fmt.upper()}**")

    def _remap_sportsbet(df):
        df = df.copy()
        col_map = {c: c.upper() for c in df.columns}
        df.columns = [col_map.get(c, c) for c in df.columns]
        rows = []
        for _, r in df.iterrows():
            placed = str(r.get('PLACED DATE', ''))
            try:
                d = pd.to_datetime(placed, errors='coerce').strftime('%Y-%m-%d')
            except Exception:
                d = date.today().strftime('%Y-%m-%d')
            stake = abs(pd.to_numeric(str(r.get('STAKE', '0')).replace('$', ''), errors='coerce') or 0)
            returns = abs(pd.to_numeric(str(r.get('RETURNS', '0')).replace('$', ''), errors='coerce') or 0)
            status = str(r.get('STATUS', '')).strip().title()
            result = {'Won': 'Win', 'Lost': 'Loss', 'Pending': 'Pending',
                      'Void': 'Void/Refund'}.get(status, 'Pending')
            odds_raw = str(r.get('ODDS', '2'))
            odds = pd.to_numeric(odds_raw, errors='coerce') or 2.0
            pl = _compute_pl(float(odds), float(stake), result) if result != 'Pending' else 0.0
            rows.append({
                'bet_id': str(uuid.uuid4())[:8],
                'date': d,
                'match': str(r.get('EVENT', r.get('SPORT', ''))),
                'market_type': str(r.get('BET TYPE', 'Other')),
                'selection': str(r.get('SELECTION', '')),
                'bookmaker': 'Sportsbet',
                'odds': round(float(odds), 2),
                'stake': round(float(stake), 2),
                'result': result,
                'profit_loss': pl,
                'is_cha_ching': False,
                'cha_ching_criteria': '',
                'notes': str(r.get('BONUS BET', '')),
            })
        return pd.DataFrame(rows)

    def _remap_tab(df):
        df = df.copy()
        col_map = {c: c.upper() for c in df.columns}
        df.columns = [col_map.get(c, c) for c in df.columns]
        rows = []
        for _, r in df.iterrows():
            d = str(r.get('DATE', ''))
            try:
                d = pd.to_datetime(d, dayfirst=True, errors='coerce').strftime('%Y-%m-%d')
            except Exception:
                d = date.today().strftime('%Y-%m-%d')
            stake = abs(pd.to_numeric(str(r.get('STAKE', '0')), errors='coerce') or 0)
            returns = abs(pd.to_numeric(str(r.get('RETURN', str(r.get('RETURNS', '0'))),), errors='coerce') or 0)
            status = str(r.get('RESULT', str(r.get('STATUS', '')))).strip().title()
            result = {'Won': 'Win', 'Win': 'Win', 'Lost': 'Loss', 'Loss': 'Loss',
                      'Void': 'Void/Refund'}.get(status, 'Pending')
            pl = returns - stake if result == 'Win' else (-stake if result == 'Loss' else 0)
            rows.append({
                'bet_id': str(uuid.uuid4())[:8],
                'date': d,
                'match': str(r.get('MEETING/COMPETITION', r.get('EVENT TYPE', ''))),
                'market_type': str(r.get('BET TYPE', 'Other')),
                'selection': str(r.get('SELECTION', '')),
                'bookmaker': 'TAB',
                'odds': round(float(returns / stake) if stake > 0 else 2.0, 2),
                'stake': round(float(stake), 2),
                'result': result,
                'profit_loss': round(float(pl), 2),
                'is_cha_ching': False,
                'cha_ching_criteria': '',
                'notes': '',
            })
        return pd.DataFrame(rows)

    def _remap_generic(df):
        df = df.copy()
        col_map = {c: c.upper() for c in df.columns}
        df.columns = [col_map.get(c, c) for c in df.columns]
        rows = []
        for _, r in df.iterrows():
            stake = abs(pd.to_numeric(str(r.get('STAKE', '1')), errors='coerce') or 1)
            odds  = abs(pd.to_numeric(str(r.get('ODDS', '2')), errors='coerce') or 2)
            status = str(r.get('RESULT', r.get('STATUS', 'Pending'))).strip().title()
            result = {'Won': 'Win', 'Win': 'Win', 'Lost': 'Loss', 'Loss': 'Loss'}.get(status, 'Pending')
            pl = _compute_pl(float(odds), float(stake), result)
            rows.append({
                'bet_id': str(uuid.uuid4())[:8],
                'date': str(r.get('DATE', date.today().strftime('%Y-%m-%d'))),
                'match': str(r.get('EVENT', r.get('MATCH', ''))),
                'market_type': str(r.get('MARKET', r.get('MARKET_TYPE', 'Other'))),
                'selection': str(r.get('SELECTION', '')),
                'bookmaker': str(r.get('BOOKMAKER', 'Other')),
                'odds': round(float(odds), 2),
                'stake': round(float(stake), 2),
                'result': result,
                'profit_loss': round(float(pl), 2),
                'is_cha_ching': False,
                'cha_ching_criteria': '',
                'notes': '',
            })
        return pd.DataFrame(rows)

    try:
        if fmt == 'sportsbet':
            mapped = _remap_sportsbet(raw)
        elif fmt == 'tab':
            mapped = _remap_tab(raw)
        else:
            mapped = _remap_generic(raw)
    except Exception as e:
        st.error(f"Mapping error: {e}")
        return

    st.write(f"**Preview after mapping ({len(mapped)} bets):**")
    st.dataframe(mapped[['date', 'match', 'selection', 'bookmaker', 'odds', 'stake', 'result', 'profit_loss']].head(8),
                 use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(f"Import {len(mapped)} bets", type="primary", use_container_width=True):
            existing = _load_bets()
            combined = pd.concat([existing, mapped], ignore_index=True)
            _save_bets(combined)
            st.toast(f"Imported {len(mapped)} bets!")
            st.rerun()
    with col_b:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# ── Page 1: BH Dashboard ───────────────────────────────────────────────────────

def render_bh_dashboard():
    _inject_css()
    st.markdown(
        '<div class="title-bar"><h2 style="color:#e8f0f8;margin:0">Betting Hub Dashboard</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">P&L summary, hit rates, recent bets</p></div>',
        unsafe_allow_html=True,
    )

    bets = _load_bets()
    s    = _betting_stats(bets)

    # ── Stat row 1: main metrics ──────────────────────────────────────────────
    st.markdown('<div class="section-header">Overall Performance</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    pl_tone = _pl_tone(s['total_pl'])
    for col, label, val, sub, tone in [
        (c1, "Total P&L",    f"{s['total_pl']:+.2f}u", f"{s['total_bets']} bets", pl_tone),
        (c2, "ROI",          f"{s['roi']:+.1f}%",       f"{s['total_staked']:.1f}u staked", _pl_tone(s['roi'])),
        (c3, "Hit Rate",     f"{s['hit_rate']:.1f}%",   f"{s['wins']}W / {s['losses']}L", 'neutral'),
        (c4, "Units Staked", f"{s['total_staked']:.2f}u","", 'neutral'),
        (c5, "Units Returned",f"{s['total_returned']:.2f}u","", _pl_tone(s['total_returned'] - s['total_staked'])),
    ]:
        with col:
            st.markdown(_metric_card(label, val, sub, tone), unsafe_allow_html=True)

    # ── Stat row 2: Cha Ching performance ─────────────────────────────────────
    st.markdown('<div class="section-header">Cha Ching Tips Performance</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, sub, tone in [
        (c1, "CC P&L",    f"{s['cc_pl']:+.2f}u",    f"{s['cc_bets']} CC bets", _pl_tone(s['cc_pl'])),
        (c2, "CC Hit Rate",f"{s['cc_hit_rate']:.1f}%",f"{s['cc_hits']} wins", 'gold'),
        (c3, "CC ROI",    f"{s['cc_roi']:+.1f}%",    "vs CC staked",          _pl_tone(s['cc_roi'])),
        (c4, "All vs CC", f"All {s['hit_rate']:.0f}% / CC {s['cc_hit_rate']:.0f}%","hit rate comparison",'neutral'),
    ]:
        with col:
            st.markdown(_metric_card(label, val, sub, tone), unsafe_allow_html=True)

    # ── P&L Chart ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">P&L Over Time</div>', unsafe_allow_html=True)
    settled = bets[bets['result'].isin(['Win', 'Loss'])].copy()
    _bh_pl_fig = apply_chart_theme(_pl_chart(settled))
    st.plotly_chart(_bh_pl_fig, use_container_width=True, key='bh_pl_chart')

    # ── Recent bets ───────────────────────────────────────────────────────────
    _hdr_col, _tog_col = st.columns([3, 1])
    with _hdr_col:
        st.markdown('<div class="section-header">Recent Bets</div>', unsafe_allow_html=True)
    if bets.empty:
        st.info("No bets logged yet. Use the Bet Tracker to add your first bet.")
    else:
        _show_all = st.session_state.get('_bh_show_all_bets', False)
        with _tog_col:
            _lbl = "Show less" if _show_all else f"Show all ({len(bets)})"
            if st.button(_lbl, key='_bh_tog_bets', use_container_width=True):
                st.session_state['_bh_show_all_bets'] = not _show_all
                st.rerun()
        recent = bets.sort_values('date', ascending=False)
        if not _show_all:
            recent = recent.head(10)
        for _, row in recent.iterrows():
            result = str(row.get('result', 'Pending'))
            badge  = {'Win': 'bet-win', 'Loss': 'bet-loss', 'Pending': 'bet-pending',
                      'Void/Refund': 'bet-void'}.get(result, 'bet-pending')
            cc_html = ' <span class="cc-badge">CC</span>' if row.get('is_cha_ching') else ''
            pl = row.get('profit_loss', 0) or 0
            pl_col = C['green'] if pl > 0 else (C['red'] if pl < 0 else C['brown'])
            date_str = pd.Timestamp(row['date']).strftime('%d %b') if pd.notna(row.get('date')) else '—'
            odds_val = row.get('odds', 0) or 0
            odds_str = f'{float(odds_val):.2f}' if float(odds_val) > 0 else '—'
            st.markdown(
                f'<div class="bet-row-enter" style="display:flex;align-items:center;gap:12px;padding:8px 12px;'
                f'background:{C["bg"]};border:1px solid {C["border"]};border-radius:6px;margin-bottom:4px;'
                f'transition:box-shadow 0.15s ease,transform 0.15s ease;" '
                f'onmouseenter="this.style.transform=\'translateX(3px)\';this.style.boxShadow=\'0 3px 10px rgba(0,0,0,0.07)\'" '
                f'onmouseleave="this.style.transform=\'\';this.style.boxShadow=\'\'">'
                f'<span style="color:{C["brown"]};font-size:12px;min-width:36px">{date_str}</span>'
                f'<span style="flex:1;font-size:13px;font-weight:600;color:{C["text"]}">'
                f'{str(row.get("selection","—"))[:40]}{cc_html}</span>'
                f'<span style="color:{C["brown"]};font-size:12px">{str(row.get("bookmaker",""))}</span>'
                f'<span style="font-size:12px;color:{C["brown"]};min-width:38px;text-align:right">{odds_str}</span>'
                f'<span class="{badge}">{result}</span>'
                f'<span style="font-size:13px;font-weight:700;color:{pl_col};min-width:52px;text-align:right">'
                f'{pl:+.2f}u</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if st.button("Add Bet", type="primary"):
        _add_bet_dialog()


# ── Page 2: Bet Tracker ────────────────────────────────────────────────────────

def render_bet_tracker():
    _inject_css()
    st.markdown(
        '<div class="title-bar"><h2 style="color:#e8f0f8;margin:0">Bet Tracker</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">'
        'Full bet history with filters — log, edit, and import bets</p></div>',
        unsafe_allow_html=True,
    )

    bets = _load_bets()

    # ── Action buttons ────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([1, 1, 6])
    with col_a:
        if st.button("+ Add Bet", type="primary", use_container_width=True):
            _add_bet_dialog()
    with col_b:
        if st.button("Import CSV", use_container_width=True):
            _import_csv_dialog()

    if bets.empty:
        st.info("No bets logged yet. Click **+ Add Bet** to log your first bet, or **Import CSV** to import a bookmaker export.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        all_markets = ['All'] + sorted(bets['market_type'].dropna().unique().tolist())
        mkt_filter  = st.selectbox("Market", all_markets, index=0, key='bt_mkt')
    with fc2:
        all_books = ['All'] + sorted(bets['bookmaker'].dropna().unique().tolist())
        bk_filter = st.selectbox("Bookmaker", all_books, index=0, key='bt_bk')
    with fc3:
        res_filter = st.selectbox("Result", ['All'] + RESULTS, index=0, key='bt_res')
    with fc4:
        cc_filter = st.selectbox("Tips type", ['All', 'Cha Ching only', 'Non-CC only'], index=0, key='bt_cc')
    with fc5:
        if pd.notna(bets['date']).any():
            min_d = bets['date'].dropna().min().date()
            max_d = bets['date'].dropna().max().date()
            date_range = st.date_input("Date range", (min_d, max_d), key='bt_dr')
        else:
            date_range = None

    # Apply filters
    filt = bets.copy()
    if mkt_filter != 'All':
        filt = filt[filt['market_type'] == mkt_filter]
    if bk_filter != 'All':
        filt = filt[filt['bookmaker'] == bk_filter]
    if res_filter != 'All':
        filt = filt[filt['result'] == res_filter]
    if cc_filter == 'Cha Ching only':
        filt = filt[filt['is_cha_ching'] == True]
    elif cc_filter == 'Non-CC only':
        filt = filt[filt['is_cha_ching'] != True]
    if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        try:
            filt = filt[
                (filt['date'].dt.date >= date_range[0]) &
                (filt['date'].dt.date <= date_range[1])
            ]
        except Exception:
            pass

    filt = filt.sort_values('date', ascending=False).reset_index(drop=True)

    # ── Filtered stats strip ─────────────────────────────────────────────────
    fs = _betting_stats(filt)
    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
    for col, lbl, val in [
        (sc1, "Bets",    str(fs['total_bets'])),
        (sc2, "P&L",     f"{fs['total_pl']:+.2f}u"),
        (sc3, "ROI",     f"{fs['roi']:+.1f}%"),
        (sc4, "Hit Rate",f"{fs['hit_rate']:.1f}%"),
        (sc5, "W/L",     f"{fs['wins']}W / {fs['losses']}L"),
        (sc6, "Pending", str(fs['pending'])),
    ]:
        col.metric(lbl, val)

    # ── Bet table ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Bets</div>', unsafe_allow_html=True)
    if filt.empty:
        st.info("No bets match the current filters.")
        return

    # Build display df
    def _result_badge(r):
        badges = {'Win': '✅ Win', 'Loss': '❌ Loss', 'Pending': '⏳ Pending', 'Void/Refund': '↩️ Void'}
        return badges.get(r, r)

    display = filt[[
        'date', 'match', 'market_type', 'selection', 'bookmaker',
        'odds', 'stake', 'result', 'profit_loss', 'is_cha_ching', 'notes'
    ]].copy()
    display['date']       = display['date'].dt.strftime('%d %b %Y')
    display['odds']       = display['odds'].round(2)
    display['stake']      = display['stake'].round(2)
    display['profit_loss']= display['profit_loss'].round(2)
    display['is_cha_ching'] = display['is_cha_ching'].apply(lambda x: '★ CC' if x else '')
    display.columns = ['Date', 'Match', 'Market', 'Selection', 'Bookmaker',
                       'Odds', 'Stake', 'Result', 'P&L', 'CC', 'Notes']

    def _style_bets(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Result'] in ('✅ Win', 'Win'):
                styles.loc[i, 'P&L'] = 'color: #34d399; font-weight: 700'
            elif row['Result'] in ('❌ Loss', 'Loss'):
                styles.loc[i, 'P&L'] = 'color: #c0392b; font-weight: 700'
            if row['CC'] == '★ CC':
                styles.loc[i, 'CC'] = 'color: #c9a84c; font-weight: 800'
        return styles

    st.dataframe(
        display.style.apply(_style_bets, axis=None),
        use_container_width=True,
        hide_index=True,
        height=min(600, 60 + len(display) * 36),
        column_config={
            'Odds':  st.column_config.NumberColumn('Odds',  format='%.2f'),
            'Stake': st.column_config.NumberColumn('Stake', format='%.2f'),
            'P&L':   st.column_config.NumberColumn('P&L',   format='%.2f'),
        },
    )

    # Export filtered
    csv_out = filt.to_csv(index=False)
    st.download_button(
        "Export filtered bets (CSV)",
        data=csv_out,
        file_name=f"bets_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ── Page 3: Cha Ching Tips ─────────────────────────────────────────────────────

def render_cha_ching_tips():
    _inject_css()
    st.markdown(
        '<div class="title-bar">'
        '<h2 style="color:#2c2c2c;margin:0">Cha Ching Tips</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">'
        'Upcoming fixtures · Player prop markets · Cha Ching checklist</p></div>',
        unsafe_allow_html=True,
    )

    # ── Pending/flagged tips banner ───────────────────────────────────────────
    tips_df  = _load_tips()
    flagged  = tips_df[tips_df['is_flagged'] == True] if not tips_df.empty else pd.DataFrame()
    if not flagged.empty:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#c9a84c,#e8c96d);'
            f'border-radius:8px;padding:12px 16px;margin-bottom:16px">'
            f'<span style="font-weight:800;font-size:13px;color:#2c2c2c">CHA CHING TIPS FLAGGED: {len(flagged)}</span>'
            f'<span style="font-size:12px;color:#4a3a1a;margin-left:8px">'
            + ' &nbsp;·&nbsp; '.join(f"{r['player']} ({r['market_type']})" for _, r in flagged.head(4).iterrows())
            + ('…' if len(flagged) > 4 else '')
            + f'</span></div>',
            unsafe_allow_html=True,
        )

    # ── Fixture fetch ─────────────────────────────────────────────────────────
    with st.spinner("Loading fixtures..."):
        fixtures = _fetch_fixtures()

    if fixtures.empty:
        st.warning(
            "Could not load upcoming fixtures from Squiggle API. "
            "The API may be down or there are no games in the next 7 days."
        )
        st.caption("Squiggle API: https://api.squiggle.com.au")
        _render_manual_props()
        return

    props_df = _load_props()

    st.markdown('<div class="section-header">Upcoming Games — Next 7 Days</div>',
                unsafe_allow_html=True)

    for _, game in fixtures.iterrows():
        gkey   = _game_key(game)
        glabel = _game_label(game)
        venue  = str(game.get('venue', ''))
        rname  = str(game.get('roundname', ''))

        with st.expander(f"**{gkey}**  —  {glabel}"):
            tab_disp, tab_goals = st.tabs(["Disposals", "Goals"])

            for tab, mtype in [(tab_disp, "Disposals O/U"), (tab_goals, "Goals O/U")]:
                with tab:
                    _render_market_tab(gkey, mtype, props_df, tips_df)


def _render_market_tab(game_key: str, market_type: str, props_df: pd.DataFrame,
                       tips_df: pd.DataFrame):
    """Render a disposals or goals market tab for a game."""
    game_props = props_df[
        (props_df['game_key'] == game_key) &
        (props_df['market_type'] == market_type)
    ] if not props_df.empty else pd.DataFrame()

    if not game_props.empty:
        # Show existing props
        st.caption(f"Updated: {game_props['updated_at'].max()}")

        rows_html = ''
        for _, row in game_props.iterrows():
            player = str(row.get('player', ''))
            line   = row.get('line', 0)
            bookie = str(row.get('bookmaker', ''))
            odds   = row.get('odds', 0)
            impl   = 100 / float(odds) if float(odds) > 1 else 0
            tip_match = tips_df[
                (tips_df['game_key'] == game_key) &
                (tips_df['player'] == player) &
                (tips_df['market_type'] == market_type)
            ] if not tips_df.empty else pd.DataFrame()
            is_flagged = not tip_match.empty and tip_match['is_flagged'].any()
            cc_html = ' <span class="cc-badge">CC</span>' if is_flagged else ''
            rows_html += (
                f'<tr>'
                f'<td style="padding:6px 10px;font-weight:600">{player}{cc_html}</td>'
                f'<td style="padding:6px 10px;text-align:center">{line:.1f}</td>'
                f'<td style="padding:6px 10px;text-align:center">{bookie}</td>'
                f'<td style="padding:6px 10px;text-align:center;font-weight:700">{odds:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:center">{impl:.1f}%</td>'
                f'<td style="padding:6px 10px;text-align:center">—</td>'
                f'</tr>'
            )

        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f'<thead><tr style="background:#34d399;color:#e8f0f8">'
            f'<th style="padding:7px 10px;text-align:left">Player</th>'
            f'<th style="padding:7px 10px">Line</th>'
            f'<th style="padding:7px 10px">Bookmaker</th>'
            f'<th style="padding:7px 10px">Odds</th>'
            f'<th style="padding:7px 10px">Impl. Prob</th>'
            f'<th style="padding:7px 10px">Model Edge</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )

        st.markdown('')
        # Checklist buttons per player
        player_list = game_props['player'].tolist()
        if player_list:
            st.markdown('<div style="font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;margin:8px 0 4px 0">CHECKLIST</div>', unsafe_allow_html=True)
            btn_cols = st.columns(min(len(player_list), 4))
            for i, player in enumerate(player_list):
                with btn_cols[i % 4]:
                    tip_match = tips_df[
                        (tips_df['game_key'] == game_key) &
                        (tips_df['player'] == player) &
                        (tips_df['market_type'] == market_type)
                    ] if not tips_df.empty else pd.DataFrame()
                    is_flagged = not tip_match.empty and tip_match['is_flagged'].any()
                    label = f"{'★ ' if is_flagged else ''}Checklist: {player.split()[-1]}"
                    btn_type = "primary" if is_flagged else "secondary"
                    if st.button(label, key=f"cl_{game_key}_{market_type}_{player}",
                                 type=btn_type, use_container_width=True):
                        _open_checklist(player, market_type, game_key)

    else:
        st.caption(f"No {market_type} props loaded for this game.")

    # ── Add / Edit Props ─────────────────────────────────────────────────────
    with st.expander(f"Add {market_type} props for this game"):
        with st.form(key=f"add_props_{game_key}_{market_type}"):
            st.markdown(f"**Enter player line and odds for {market_type}**")
            pc1, pc2, pc3, pc4 = st.columns([3, 1.5, 2, 1.5])
            with pc1:
                p_player = st.text_input("Player name", key=f"pp_{game_key}_{market_type}_player")
            with pc2:
                p_line = st.number_input("Line", min_value=0.5, max_value=99.5,
                                         value=29.5, step=0.5, format='%.1f',
                                         key=f"pp_{game_key}_{market_type}_line")
            with pc3:
                p_bookie = st.selectbox("Bookmaker", BOOKMAKERS,
                                        key=f"pp_{game_key}_{market_type}_bookie")
            with pc4:
                p_odds = st.number_input("Odds", min_value=1.01, max_value=20.0,
                                         value=1.90, step=0.05, format='%.2f',
                                         key=f"pp_{game_key}_{market_type}_odds")
            if st.form_submit_button("Save prop"):
                if p_player.strip():
                    _save_prop(game_key, p_player.strip(), market_type,
                               float(p_line), p_bookie, float(p_odds))
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Enter a player name.")


def _render_manual_props():
    """Shown when Squiggle is unavailable — allow manual game entry."""
    st.markdown('<div class="section-header">Manual Prop Entry</div>', unsafe_allow_html=True)
    with st.expander("Add a game manually"):
        with st.form("manual_game_form"):
            game_key_in = st.text_input("Game key", placeholder="e.g. Round 12 GWS v Melbourne")
            mc, mp, ml, mb, mo = st.columns([3, 3, 1.5, 2, 1.5])
            with mc:
                mtype = st.selectbox("Market", MARKET_TYPES, key='manual_mtype')
            with mp:
                player_in = st.text_input("Player", key='manual_player')
            with ml:
                line_in = st.number_input("Line", value=29.5, step=0.5, format='%.1f', key='manual_line')
            with mb:
                book_in = st.selectbox("Bookmaker", BOOKMAKERS, key='manual_book')
            with mo:
                odds_in = st.number_input("Odds", value=1.90, step=0.05, format='%.2f', key='manual_odds')
            if st.form_submit_button("Add"):
                if game_key_in.strip() and player_in.strip():
                    _save_prop(game_key_in.strip(), player_in.strip(), mtype,
                               float(line_in), book_in, float(odds_in))
                    st.toast("Prop saved!")
                    st.rerun()


# ── Page 4: Trends & Analysis ──────────────────────────────────────────────────

def render_trends_analysis():
    _inject_css()
    st.markdown(
        '<div class="title-bar">'
        '<h2 style="color:#2c2c2c;margin:0">Trends &amp; Analysis</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">'
        'Hit rate, ROI, and P&L breakdowns across markets, bookmakers, and odds ranges</p></div>',
        unsafe_allow_html=True,
    )

    # ── My Spreadsheet ─────────────────────────────────────────────────────
    st.markdown('<div class="trend-header">My Spreadsheet</div>', unsafe_allow_html=True)
    _imported_check = _load_user_import()
    if _imported_check is not None:
        _strip_hdr, _strip_btn = st.columns([5, 1])
        with _strip_hdr:
            st.markdown(
                f'<div style="font-size:12px;color:#94a3b8;padding:6px 0">'
                f'<span style="color:#34d399;font-weight:700">✓ Spreadsheet loaded</span>'
                f' &nbsp;·&nbsp; {len(_imported_check):,} rows'
                f' &nbsp;·&nbsp; {len(_imported_check.columns)} columns</div>',
                unsafe_allow_html=True,
            )
        with _strip_btn:
            if st.button("Remove CSV", key='remove_user_import_strip', type='secondary'):
                _delete_user_import()
                st.session_state.pop('_user_import_loaded', None)
                st.rerun()
    with st.expander("Upload your own betting spreadsheet (.csv or .xlsx)", expanded=False):
        _imported = _load_user_import()

        _uploaded = st.file_uploader(
            "Choose file",
            type=['csv', 'xlsx'],
            key='user_spreadsheet_upload',
            label_visibility='collapsed',
        )
        if _uploaded is not None:
            try:
                if _uploaded.name.endswith('.xlsx'):
                    _df_up = pd.read_excel(BytesIO(_uploaded.read()))
                else:
                    _df_up = pd.read_csv(_uploaded)
                _ensure_dirs()
                _df_up.to_csv(USER_IMPORT_CSV, index=False)
                st.success(f"Saved — {len(_df_up):,} rows, {len(_df_up.columns)} columns.")
                st.session_state['_user_import_loaded'] = True
                st.rerun()
            except Exception as _e:
                st.error(f"Could not read file: {_e}")

        if _imported is not None:
            _del_col, _ = st.columns([1, 5])
            with _del_col:
                if st.button("🗑️ Delete My Spreadsheet", key='del_user_import'):
                    _delete_user_import()
                    st.session_state.pop('_user_import_loaded', None)
                    st.rerun()
            st.markdown(
                f'<div style="font-size:12px;color:#94a3b8;margin:4px 0 10px 0">'
                f'{len(_imported):,} rows &nbsp;·&nbsp; {len(_imported.columns)} columns'
                f' &nbsp;·&nbsp; <span style="color:#34d399">saved locally</span></div>',
                unsafe_allow_html=True,
            )
            # ── Comparison strip: user data vs Cha Ching bets ──────────────
            _cc_bets = _load_bets()
            _shared = [c for c in _imported.columns
                       if c.lower().replace(' ', '_') in
                       {'profit_loss', 'p&l', 'pl', 'stake', 'odds', 'result'}]
            if _shared:
                _imp_num = _imported.select_dtypes(include='number')
                _cc_num  = _cc_bets.select_dtypes(include='number')
                _cmp_cols = st.columns(2)
                with _cmp_cols[0]:
                    st.markdown(
                        '<div style="font-size:11px;font-weight:700;color:#34d399;'
                        'letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">'
                        'My Spreadsheet</div>',
                        unsafe_allow_html=True,
                    )
                    _disp_imp = _imported.copy()
                    for _c in _disp_imp.select_dtypes(include='float').columns:
                        _disp_imp[_c] = _disp_imp[_c].round(2)
                    st.dataframe(_disp_imp, use_container_width=True,
                                 hide_index=True, height=320)
                with _cmp_cols[1]:
                    st.markdown(
                        '<div style="font-size:11px;font-weight:700;color:#f0b429;'
                        'letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">'
                        'Cha Ching Bets</div>',
                        unsafe_allow_html=True,
                    )
                    _disp_cc = _cc_bets[['date', 'selection', 'market_type', 'odds',
                                         'stake', 'result', 'profit_loss']].copy()
                    _disp_cc['date'] = _disp_cc['date'].dt.strftime('%d %b %Y')
                    for _c in ['odds', 'stake', 'profit_loss']:
                        _disp_cc[_c] = _disp_cc[_c].round(2)
                    st.dataframe(_disp_cc, use_container_width=True,
                                 hide_index=True, height=320,
                                 column_config={
                                     'odds':        st.column_config.NumberColumn('Odds',   format='%.2f'),
                                     'stake':       st.column_config.NumberColumn('Stake',  format='%.2f'),
                                     'profit_loss': st.column_config.NumberColumn('P&L',    format='%.2f'),
                                 })
            else:
                _disp_imp = _imported.copy()
                for _c in _disp_imp.select_dtypes(include='float').columns:
                    _disp_imp[_c] = _disp_imp[_c].round(2)
                st.dataframe(_disp_imp, use_container_width=True, hide_index=True, height=320)
        else:
            st.markdown(
                '<div style="color:#4a5a6a;font-size:13px;padding:10px 0">'
                'No spreadsheet uploaded yet. Upload a .csv or .xlsx to compare '
                'your data alongside Cha Ching bets.</div>',
                unsafe_allow_html=True,
            )

    bets = _load_bets()
    if bets.empty or bets['result'].isin(['Win', 'Loss']).sum() < 2:
        st.info("Log at least 2 settled bets to see Trends & Analysis.")
        return

    settled = bets[bets['result'].isin(['Win', 'Loss'])].copy()
    settled['win'] = (settled['result'] == 'Win').astype(int)

    # ── Row 1: Hit rate by market + ROI by market ──────────────────────────
    st.markdown('<div class="trend-header">Hit Rate &amp; ROI by Market</div>', unsafe_allow_html=True)
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        mkt_grp = settled.groupby('market_type').agg(
            win=('win', 'sum'), total=('win', 'count')
        ).reset_index()
        mkt_grp['hit_rate'] = mkt_grp['win'] / mkt_grp['total'] * 100
        mkt_grp = mkt_grp.sort_values('hit_rate', ascending=True)
        fig = _bar_chart(
            mkt_grp['market_type'].tolist(),
            mkt_grp['hit_rate'].tolist(),
            'Hit Rate by Market (%)',
            color=[C['green']] * len(mkt_grp),
        )
        fig.update_layout(height=300)
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_mkt_hit')

    with r1c2:
        mkt_roi = bets.groupby('market_type').apply(
            lambda g: pd.Series({
                'roi': g['profit_loss'].sum() / g['stake'].sum() * 100 if g['stake'].sum() > 0 else 0
            })
        ).reset_index()
        mkt_roi = mkt_roi.sort_values('roi', ascending=True)
        fig = _bar_chart(mkt_roi['market_type'].tolist(), mkt_roi['roi'].tolist(), 'ROI by Market (%)')
        fig.update_layout(height=300)
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_mkt_roi')

    # ── Row 2: Hit rate by bookmaker + ROI by odds range ───────────────────
    st.markdown('<div class="trend-header">Bookmaker Performance &amp; Odds Analysis</div>',
                unsafe_allow_html=True)
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        bk_grp = settled.groupby('bookmaker').agg(win=('win', 'sum'), total=('win', 'count')).reset_index()
        bk_grp['hit_rate'] = bk_grp['win'] / bk_grp['total'] * 100
        fig = _bar_chart(bk_grp['bookmaker'].tolist(), bk_grp['hit_rate'].tolist(),
                         'Hit Rate by Bookmaker (%)', color=[C['green']] * len(bk_grp))
        fig.update_layout(height=300)
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_bk_hit')

    with r2c2:
        def _odds_band(o):
            if o < 1.5:   return '<1.50'
            if o < 2.0:   return '1.50-2.00'
            if o < 3.0:   return '2.00-3.00'
            if o < 5.0:   return '3.00-5.00'
            return '5.00+'
        bets_o = bets.copy()
        bets_o['odds_band'] = bets_o['odds'].apply(_odds_band)
        ods_roi = bets_o.groupby('odds_band').apply(
            lambda g: pd.Series({'roi': g['profit_loss'].sum() / g['stake'].sum() * 100
                                 if g['stake'].sum() > 0 else 0})
        ).reset_index()
        order = ['<1.50', '1.50-2.00', '2.00-3.00', '3.00-5.00', '5.00+']
        ods_roi['odds_band'] = pd.Categorical(ods_roi['odds_band'], categories=order, ordered=True)
        ods_roi = ods_roi.sort_values('odds_band')
        fig = _bar_chart(ods_roi['odds_band'].tolist(), ods_roi['roi'].tolist(), 'ROI by Odds Range (%)')
        fig.update_layout(height=300)
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_ods_roi')

    # ── Monthly P&L ────────────────────────────────────────────────────────
    st.markdown('<div class="trend-header">Monthly P&amp;L</div>', unsafe_allow_html=True)
    bets_m = bets.copy()
    bets_m['month'] = bets_m['date'].dt.to_period('M').astype(str)
    monthly = bets_m.groupby('month')['profit_loss'].sum().reset_index()
    monthly = monthly.sort_values('month')
    fig = _bar_chart(monthly['month'].tolist(), monthly['profit_loss'].tolist(), 'Monthly P&L (units)')
    fig.update_layout(height=300)
    fig = apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True, key='tr_monthly')

    # ── Cha Ching vs non-CC comparison ────────────────────────────────────
    st.markdown('<div class="trend-header">Cha Ching Tips vs All Bets</div>', unsafe_allow_html=True)
    cc_s   = settled[settled['is_cha_ching'] == True]
    non_s  = settled[settled['is_cha_ching'] != True]
    cc_hit  = cc_s['win'].mean() * 100  if len(cc_s) > 0  else 0
    non_hit = non_s['win'].mean() * 100 if len(non_s) > 0 else 0
    cc_all  = bets[bets['is_cha_ching'] == True]
    non_all = bets[bets['is_cha_ching'] != True]
    cc_roi  = cc_all['profit_loss'].sum() / cc_all['stake'].sum() * 100 if cc_all['stake'].sum() > 0 else 0
    non_roi = non_all['profit_loss'].sum() / non_all['stake'].sum() * 100 if non_all['stake'].sum() > 0 else 0

    rc1, rc2 = st.columns(2)
    with rc1:
        fig = go.Figure(go.Bar(
            x=['Cha Ching', 'Non-CC'],
            y=[cc_hit, non_hit],
            marker_color=[C['gold'], C['brown']],
            text=[f'{cc_hit:.1f}%', f'{non_hit:.1f}%'],
            textposition='outside',
        ))
        fig.update_layout(
            paper_bgcolor=C['bg'], plot_bgcolor=C['bg'], font_color=C['text'],
            height=280, showlegend=False,
            title=dict(text='Hit Rate Comparison (%)', font=dict(size=12, color=C['brown'])),
            yaxis=dict(gridcolor='#ede8df'),
            margin=dict(l=50, r=20, t=40, b=40),
        )
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_cc_hit')

    with rc2:
        fig = go.Figure(go.Bar(
            x=['Cha Ching', 'Non-CC'],
            y=[cc_roi, non_roi],
            marker_color=[C['gold'] if cc_roi >= 0 else C['red'],
                          C['green'] if non_roi >= 0 else C['red']],
            text=[f'{cc_roi:+.1f}%', f'{non_roi:+.1f}%'],
            textposition='outside',
        ))
        fig.update_layout(
            paper_bgcolor=C['bg'], plot_bgcolor=C['bg'], font_color=C['text'],
            height=280, showlegend=False,
            title=dict(text='ROI Comparison (%)', font=dict(size=12, color=C['brown'])),
            yaxis=dict(gridcolor='#ede8df', zeroline=True, zerolinecolor=C['border']),
            margin=dict(l=50, r=20, t=40, b=40),
        )
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_cc_roi')

    # ── Best / Worst performing markets (table) ────────────────────────────
    st.markdown('<div class="trend-header">Best &amp; Worst Markets</div>', unsafe_allow_html=True)
    mkt_full = bets.groupby('market_type').apply(lambda g: pd.Series({
        'Bets':     len(g),
        'W':        int(g[g['result'] == 'Win']['result'].count()),
        'L':        int(g[g['result'] == 'Loss']['result'].count()),
        'Hit %':    round(g[g['result'] == 'Win']['result'].count() /
                          max(1, g['result'].isin(['Win','Loss']).sum()) * 100, 1),
        'Staked':   round(g['stake'].fillna(0).sum(), 2),
        'P&L':      round(g['profit_loss'].fillna(0).sum(), 2),
        'ROI %':    round(g['profit_loss'].fillna(0).sum() /
                          max(0.01, g['stake'].fillna(0).sum()) * 100, 1),
    })).reset_index()
    mkt_full = mkt_full.sort_values('P&L', ascending=False)

    def _style_pl(v):
        try:
            return f'color: {C["green"]}; font-weight:700' if float(v) >= 0 else f'color: {C["red"]}; font-weight:700'
        except Exception:
            return ''

    st.dataframe(
        mkt_full.style.applymap(_style_pl, subset=['P&L', 'ROI %']),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Bets':   st.column_config.NumberColumn('Bets',   format='%d'),
            'W':      st.column_config.NumberColumn('W',      format='%d'),
            'L':      st.column_config.NumberColumn('L',      format='%d'),
            'Hit %':  st.column_config.NumberColumn('Hit %',  format='%.2f'),
            'Staked': st.column_config.NumberColumn('Staked', format='%.2f'),
            'P&L':    st.column_config.NumberColumn('P&L',    format='%.2f'),
            'ROI %':  st.column_config.NumberColumn('ROI %',  format='%.2f'),
        },
    )


# ── Public dispatch ────────────────────────────────────────────────────────────

def render_page(page: str):
    """Called from dashboard.py for each Betting Hub page."""
    inject_global_css()
    _ensure_dirs()
    if page == 'BH Dashboard':
        render_bh_dashboard()
    elif page == 'Bet Tracker':
        render_bet_tracker()
    elif page == 'Cha Ching Tips':
        render_cha_ching_tips()
    elif page == 'Trends & Analysis':
        render_trends_analysis()
