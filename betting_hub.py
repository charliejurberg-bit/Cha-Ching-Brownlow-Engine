"""
betting_hub.py — Cha Ching Betting Hub
Four pages rendered by render_page(page_name) and imported into dashboard.py:
    Performance, Bet Tracker, Cha Ching Tips, Trends & Analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os, json, uuid, time, requests, re, hmac
from datetime import datetime, timedelta, date
from io import StringIO, BytesIO
from theme import inject_global_theme, PLOTLY_TOUCH_CONFIG

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

NEW_CHECKLIST_KEYS = [
    "promo_scan", "dvp_check", "opposition_stats", "stat_split",
    "tagger_risk", "role_cba", "statmate_trends", "value_read",
]

BOOKMAKERS   = ["Sportsbet", "TAB", "Betfair", "Ladbrokes", "Neds", "PointsBet", "Unibet", "Other"]
MARKET_TYPES = ["Disposals O/U", "Goals O/U", "Fantasy Points O/U", "Kicks O/U", "Handballs O/U",
                "Marks O/U", "Match Result", "Line", "Multi", "Other"]
RESULTS      = ["Pending", "Win", "Loss", "Void/Refund"]
CC_THRESHOLD = 3   # checklist items needed to auto-flag a Cha Ching tip

STAT_COL_MAP = {
    "Disposals O/U": "Disposals",
    "Goals O/U":     "Goals",
    "Kicks O/U":     "Kicks",
    "Handballs O/U": "Handballs",
    "Marks O/U":     "Marks",
}

C = dict(
    green='#34d399', lgreen='#1a5c40', gold='#f0b429', lgold='#f5c842',
    brown='#7e8c99', red='#ef7a6d', bg='#101a24', card='#0d141d',
    border='rgba(140,165,185,.14)', text='#e9eef3',
)

def inject_global_css():
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text);
    font-family: 'Sora', sans-serif;
}
[data-testid="stAppViewContainer"] > .main { background-color: var(--bg) !important; }
[data-testid="block-container"] { padding-top: 1.5rem !important; max-width: 1200px; }
[data-testid="stSidebar"] {
    background-color: var(--surface-2) !important;
    border-right: 1px solid var(--line) !important;
}
h1, h2, h3, h4 {
    font-family: 'Sora', sans-serif !important;
    color: var(--text) !important;
}
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    padding: 16px !important;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 11px !important; text-transform: uppercase !important; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'Sora', sans-serif !important; font-weight: 700 !important; }
[data-testid="stDataFrame"] th {
    background: var(--surface-2) !important; color: var(--muted) !important;
    font-size: 11px !important; text-transform: uppercase !important;
}
[data-testid="stDataFrame"] td { background: var(--surface) !important; color: var(--text) !important; }
[data-testid="stDataFrame"] tr:hover td { background: var(--surface-2) !important; }
[data-testid="stSelectbox"] > div > div, [data-testid="stMultiSelect"] > div > div {
    background: var(--surface) !important; border: 1px solid var(--line) !important; color: var(--text) !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    background: var(--surface) !important; border: 1px solid var(--line) !important; color: var(--text) !important;
}
button[kind="primary"], [data-testid="baseButton-primary"] {
    background: var(--emerald) !important; color: #0a1f14 !important;
    border: none !important; font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
}
hr { border: none !important; border-top: 1px solid var(--line) !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }
[data-testid="stAppViewContainer"]      { padding-top: 0 !important; }
[data-testid="stHeader"]                { display: none !important; }
section[data-testid="stSidebarContent"] { padding-top: 0 !important; }
div[data-testid="stToolbar"]            { display: none !important; }
</style>
""", unsafe_allow_html=True)

def apply_chart_theme(fig):
    import plotly.graph_objects as _go
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Archivo, sans-serif", color="#7e8c99", size=12),
        title_font=dict(family="Archivo, sans-serif", color="#e9eef3", size=14),
        # See dashboard.py's apply_chart_theme for the full reasoning: fixedrange
        # stops a touch-screen scroll being captured as a chart zoom/pan, and
        # dragmode=False removes the pan interaction. Kept in step with that copy
        # — the two functions are duplicates and must be edited together.
        xaxis=dict(
            gridcolor="rgba(140,165,185,.14)",
            linecolor="rgba(140,165,185,.14)",
            tickcolor="rgba(140,165,185,.14)",
            tickfont=dict(color="#7e8c99", size=11),
            fixedrange=True,
        ),
        yaxis=dict(
            gridcolor="rgba(140,165,185,.14)",
            linecolor="rgba(140,165,185,.14)",
            tickcolor="rgba(140,165,185,.14)",
            tickfont=dict(color="#7e8c99", size=11),
            fixedrange=True,
        ),
        dragmode=False,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(140,165,185,.14)",
            borderwidth=1,
            font=dict(color="#7e8c99", size=11),
        ),
        margin=dict(l=16, r=16, t=40, b=16),
    )
    # Plotly renders the literal string "undefined" as the title when title_font is
    # set but title.text is not. Force an empty title unless one was set explicitly.
    if not (fig.layout.title and fig.layout.title.text):
        fig.update_layout(title_text="")
    fig.update_traces(marker_line_width=0)
    return fig

# ── Data layer ─────────────────────────────────────────────────────────────────

TIPS_COLS = [
    'tip_id', 'game_key', 'player', 'market_type', 'line',
    'bookmaker', 'odds', 'stake', 'criteria_json', 'is_flagged',
    'notes', 'created_at', 'result', 'profit_loss',
]

PROPS_COLS = [
    'game_key', 'player', 'market_type', 'line',
    'bookmaker', 'odds', 'updated_at',
]

# ── Supabase client ────────────────────────────────────────────────────────────

@st.cache_resource
def _get_supabase():
    """Returns a Supabase client, or None if secrets are missing / connection fails."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["secret_key"]  # server-side: full read/write
        return create_client(url, key)
    except Exception:
        return None


def _supabase_available() -> bool:
    return _get_supabase() is not None


def _form_instance_id(state_key: str) -> str:
    """Stable row id for one form/dialog instance, held in session state.

    Minted on first render, so a double-click or a rerun mid-write reuses the
    same id and the keyed upsert collapses onto one row instead of adding a
    duplicate. Cleared only by _clear_form_instance() after a write is
    confirmed — a failed write deliberately keeps the key so the retry carries
    the same id. That is the whole point.
    """
    if not st.session_state.get(state_key):
        st.session_state[state_key] = str(uuid.uuid4())
    return st.session_state[state_key]


def _clear_form_instance(state_key: str):
    """Drop a form-instance id so the next entry starts a fresh row."""
    st.session_state.pop(state_key, None)


def _is_duplicate_error(e: Exception) -> bool:
    """True for a Postgres unique violation (SQLSTATE 23505) via PostgREST.

    The error shape differs across supabase-py versions, so match on the
    SQLSTATE and the message text rather than on any one attribute.
    """
    s = f"{getattr(e, 'code', '')} {getattr(e, 'message', '')} {e}".lower()
    return '23505' in s or 'duplicate key' in s


def _sb_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame rows to JSON-safe dicts (NaN/NaT → None)."""
    rows = []
    for row in df.to_dict('records'):
        rows.append({
            k: (None if (v is not None and isinstance(v, float) and pd.isna(v)) else v)
            for k, v in row.items()
        })
    return rows


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)  # for user_import.csv only


@st.cache_data(ttl=3600)
def _load_player_avgs() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "data_2026", "afltables_2026.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    avail = [c for c in STAT_COL_MAP.values() if c in df.columns]
    if 'Player' not in df.columns or not avail:
        return pd.DataFrame()
    return df.groupby('Player')[avail].mean().reset_index()


def _empty_bets_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=BETS_COLS)
    df['date']         = pd.to_datetime(df['date'], errors='coerce')
    df['odds']         = pd.to_numeric(df['odds'], errors='coerce')
    df['stake']        = pd.to_numeric(df['stake'], errors='coerce')
    df['profit_loss']  = pd.to_numeric(df['profit_loss'], errors='coerce')
    df['is_cha_ching'] = df['is_cha_ching'].fillna(False).astype(bool)
    return df


@st.cache_data(ttl=60)
def _load_bets() -> pd.DataFrame:
    def _coerce(df):
        for c in BETS_COLS:
            if c not in df.columns:
                df[c] = None
        df['date']         = pd.to_datetime(df['date'], errors='coerce')
        df['odds']         = pd.to_numeric(df['odds'], errors='coerce')
        df['stake']        = pd.to_numeric(df['stake'], errors='coerce')
        df['profit_loss']  = pd.to_numeric(df['profit_loss'], errors='coerce')
        df['is_cha_ching'] = df['is_cha_ching'].fillna(False).astype(bool)
        return df

    frames = []

    # Always load from local CSV first
    if os.path.exists(BETS_CSV):
        try:
            frames.append(_coerce(pd.read_csv(BETS_CSV)))
        except Exception:
            pass

    # Also load from Supabase and merge (deduplicates by bet_id)
    sb = _get_supabase()
    if sb is not None:
        try:
            resp = sb.table("bets").select("*").execute()
            if resp.data:
                frames.append(_coerce(pd.DataFrame(resp.data)))
        except Exception:
            pass

    if not frames:
        return _empty_bets_df()

    combined = pd.concat(frames, ignore_index=True)
    if 'bet_id' in combined.columns:
        combined = combined.drop_duplicates(subset=['bet_id'], keep='first')
    return combined.sort_values('date', ascending=True).reset_index(drop=True)


def _insert_bet(row: dict):
    """Upsert a single bet row into Supabase, keyed on bet_id.

    The caller mints bet_id once per dialog instance, so a resubmit rewrites
    that one row rather than inserting a duplicate.
    """
    if 'date' in row and hasattr(row['date'], 'strftime'):
        row['date'] = row['date'].strftime('%Y-%m-%d')
    row = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in row.items()}
    _get_supabase().table("bets").upsert(row, on_conflict="bet_id").execute()
    _load_bets.clear()


def _save_bets(df: pd.DataFrame):
    """Upsert full DataFrame to Supabase — used for bulk CSV import."""
    df_save = df.copy()
    if 'date' in df_save.columns:
        df_save['date'] = pd.to_datetime(df_save['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    records = _sb_records(df_save)
    if records:
        _get_supabase().table("bets").upsert(records, on_conflict="bet_id").execute()
        _load_bets.clear()


def _empty_tips_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=TIPS_COLS)
    for col in ['odds', 'stake', 'line', 'profit_loss']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in ['result', 'notes', 'bookmaker', 'player', 'market_type', 'game_key']:
        df[col] = df[col].fillna('').astype(str)
    df['is_flagged'] = df['is_flagged'].fillna(False).astype(bool)
    return df


@st.cache_data(ttl=60)
def _load_tips() -> pd.DataFrame:
    def _coerce(df):
        for col in TIPS_COLS:
            if col not in df.columns:
                df[col] = None
        for col in ['odds', 'stake', 'line', 'profit_loss']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        for col in ['result', 'notes', 'bookmaker', 'player', 'market_type', 'game_key']:
            df[col] = df[col].fillna('').astype(str)
        df['is_flagged'] = df['is_flagged'].fillna(False).astype(bool)
        return df

    # Supabase is the source of truth. A successful query is authoritative even
    # when it returns zero rows — only fall back to the CSV on a genuine
    # connection/query failure (no client, or the query raises).
    sb = _get_supabase()
    if sb is not None:
        try:
            resp = sb.table("cha_ching_tips").select("*").execute()
            data = resp.data or []
            return _coerce(pd.DataFrame(data)).reset_index(drop=True)
        except Exception:
            pass

    # Fallback: read the local CSV when Supabase couldn't supply data.
    if os.path.exists(TIPS_CSV):
        try:
            return _coerce(pd.read_csv(TIPS_CSV)).reset_index(drop=True)
        except Exception:
            pass

    return _empty_tips_df()


def _save_tip(game_key: str, player: str, market_type: str,
              criteria: list[str], is_flagged: bool, notes: str = '',
              stake: float = 0.0, odds: float = 0.0, bookmaker: str = '',
              line: float = 0.0, tip_id: str | None = None):
    """Returns None on success, or an error string on failure.

    tip_id is the caller's form-instance id, so a resubmit upserts the same row
    instead of adding a duplicate. It falls back to a fresh uuid4 for callers
    that don't supply one.
    """
    try:
        new_row = {
            'tip_id':        tip_id or str(uuid.uuid4()),
            'game_key':      game_key,
            'player':        player,
            'market_type':   market_type,
            'line':          round(float(line), 1) if line else None,
            'bookmaker':     bookmaker or None,
            'odds':          round(float(odds), 2) if odds else None,
            'stake':         round(float(stake), 2) if stake else 0.0,
            'criteria_json': json.dumps(criteria),
            'is_flagged':    is_flagged,
            'notes':         notes or None,
            'created_at':    datetime.now().isoformat(),
            'result':        '',
            'profit_loss':   None,
        }
        _get_supabase().table("cha_ching_tips").upsert(
            new_row, on_conflict="tip_id").execute()
        _load_tips.clear()
        return None
    except Exception as e:
        import traceback
        return f"{e}\n\n{traceback.format_exc()}"


def _delete_tip(tip_id: str):
    try:
        _get_supabase().table("cha_ching_tips").delete().eq('tip_id', tip_id).execute()
        _load_tips.clear()
        return None
    except Exception as e:
        return str(e)


def _save_tip_result(tip_id: str, result: str):
    df = _load_tips()
    mask = df['tip_id'].astype(str) == str(tip_id)
    pl = 0.0
    if mask.any():
        row   = df[mask].iloc[0]
        odds  = pd.to_numeric(row.get('odds', 0),  errors='coerce') or 0.0
        stake = pd.to_numeric(row.get('stake', 0), errors='coerce') or 0.0
        if result and odds > 1 and stake > 0:
            pl = _compute_pl(float(odds), float(stake), result)
        _get_supabase().table("cha_ching_tips").update({
            'result':      result,
            'profit_loss': pl if result else None,
        }).eq('tip_id', tip_id).execute()
        _load_tips.clear()
        try:
            _sync_tip_to_bets(tip_id, row, result, pl)
        except Exception as e:
            st.error(f"Tip result saved but failed to sync to bet history: {e}")


def _sync_tip_to_bets(tip_id: str, tip_row, result: str, pl: float):
    """Write or remove a settled tip as a CC bet record.

    bet_id is the tip_id, so this was already idempotent by key — but it did it
    as delete-then-insert, which is two statements: a failure between them lost
    the ledger row outright. Upserting rewrites the row in one statement.
    Clearing the result still removes the row, exactly as before.
    """
    sb = _get_supabase()
    if not result:
        sb.table("bets").delete().eq("bet_id", tip_id).execute()
        _load_bets.clear()
        return

    odds  = pd.to_numeric(tip_row.get('odds',  0), errors='coerce') or 0.0
    stake = pd.to_numeric(tip_row.get('stake', 0), errors='coerce') or 0.0
    sb.table("bets").upsert({
        'bet_id':             tip_id,
        'date':               date.today().strftime('%Y-%m-%d'),
        'match':              str(tip_row.get('game_key', '')),
        'market_type':        str(tip_row.get('market_type', '')),
        'selection':          str(tip_row.get('player', '')),
        'bookmaker':          str(tip_row.get('bookmaker', '') or ''),
        'odds':               round(float(odds), 2),
        'stake':              round(float(stake), 2),
        'result':             result,
        'profit_loss':        round(float(pl), 2),
        'is_cha_ching':       True,
        'cha_ching_criteria': str(tip_row.get('criteria_json', '') or ''),
        'notes':              str(tip_row.get('notes', '') or ''),
    }, on_conflict="bet_id").execute()
    _load_bets.clear()


@st.cache_data(ttl=60)
def _load_props() -> pd.DataFrame:
    sb = _get_supabase()
    if sb is None:
        return pd.DataFrame(columns=PROPS_COLS)
    try:
        resp = sb.table("player_props").select("*").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame(columns=PROPS_COLS)
    except Exception:
        return pd.DataFrame(columns=PROPS_COLS)


def _save_prop(game_key: str, player: str, market_type: str,
               line: float, bookmaker: str, odds: float):
    _get_supabase().table("player_props").upsert({
        'game_key':    game_key,
        'player':      player,
        'market_type': market_type,
        'line':        line,
        'bookmaker':   bookmaker,
        'odds':        odds,
        'updated_at':  datetime.now().isoformat(),
    }, on_conflict="game_key,player,market_type").execute()
    _load_props.clear()


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


def _load_user_import_as_bets() -> pd.DataFrame | None:
    """Load user_import.csv and normalise it to the bets schema.

    Only six fields are parsed from the upload — every other column is ignored:
    Date, Bookmaker, Selection, Stake, Odds, Result. Headers are matched
    tolerantly (normalise = strip → lowercase → drop punctuation, then look up
    an alias map). A field falls back to its default ONLY when its column is
    genuinely absent from the upload (Date → None, Result → Pending,
    numerics → NaN). P&L is derived from the parsed odds/stake/result; the
    schema's other fields (match, market_type, notes) are left at defaults.
    """
    raw = _load_user_import()
    if raw is None or raw.empty:
        return None

    # Normalise a header/alias down to alphanumerics (drops spaces, /, punctuation).
    def _norm(s):
        return re.sub(r'[^a-z0-9]+', '', str(s).strip().lower())

    _aliases = {
        'date':      ['date', 'date placed', 'placed', 'day', 'dt'],
        'bookmaker': ['bookie', 'bookmaker', 'book', 'sportsbook', 'agency'],
        'selection': ['bet', 'selection', 'pick', 'player', 'runner'],
        'stake':     ['stake', 'wager', 'bet amount', 'units', 'risk'],
        'odds':      ['odds', 'price', 'decimal odds'],
        'result':    ['result', 'outcome', 'status', 'w/l', 'won', 'won/lost'],
    }
    _alias_lookup = {}
    for _field, _names in _aliases.items():
        for _n in _names:
            _alias_lookup[_norm(_n)] = _field

    # Map incoming columns onto the six fields; first match wins, rest ignored.
    field_col: dict = {}
    for _c in raw.columns:
        _f = _alias_lookup.get(_norm(_c))
        if _f and _f not in field_col:
            field_col[_f] = _c

    def _txt(v, default=''):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        s = str(v).strip()
        return s if s else default

    def _num(v):
        # Strip currency symbols + thousands separators; non-numeric → NaN.
        s = str(v).replace('$', '').replace('£', '').replace('€', '').replace(',', '').strip()
        return pd.to_numeric(s, errors='coerce')

    _result_values = {
        'y': 'Win', 'yes': 'Win', 'w': 'Win', 'win': 'Win', 'won': 'Win',
        'n': 'Loss', 'no': 'Loss', 'l': 'Loss', 'lose': 'Loss', 'lost': 'Loss', 'loss': 'Loss',
        'p': 'Pending', 'push': 'Pending', 'void': 'Pending',
    }

    # Derive a Market from the Bet/Selection text (schema MARKET_TYPES lacks
    # "Single"/"Same Game Multi", but the import stores the derived label as-is).
    def _derive_market(selection: str) -> str:
        s = str(selection).lower()
        if 'single' in s:
            return 'Single'
        if 'sgm' in s or 'same game' in s or 'multi' in s or re.search(r'\d+\s*[- ]?leg', s):
            return 'Multi'
        return 'Single'

    rows = []
    for _, r in raw.iterrows():
        # Date — None only when the column is genuinely absent.
        _date = _txt(r.get(field_col['date']), None) if 'date' in field_col else None
        # Result — value-normalised; Pending when absent / blank / unrecognised.
        if 'result' in field_col:
            result = _result_values.get(str(r.get(field_col['result'], '')).strip().lower(), 'Pending')
        else:
            result = 'Pending'
        # Numerics — NaN when the column is absent or the value isn't numeric.
        odds  = _num(r.get(field_col['odds']))  if 'odds'  in field_col else np.nan
        stake = _num(r.get(field_col['stake'])) if 'stake' in field_col else np.nan
        if not pd.isna(stake):
            stake = abs(stake)
        # Derive P&L from the parsed fields (no profit_loss column is read).
        if result in ('Win', 'Loss') and not pd.isna(odds) and not pd.isna(stake):
            pl = _compute_pl(float(odds), float(stake), result)
        else:
            pl = 0.0
        selection = _txt(r.get(field_col['selection'])) if 'selection' in field_col else ''
        rows.append({
            'bet_id':            str(uuid.uuid4())[:8],
            'date':              _date,
            'match':             '',
            'market_type':       _derive_market(selection) if selection else 'Single',
            'selection':         selection,
            'bookmaker':         _txt(r.get(field_col['bookmaker']), 'Other') if 'bookmaker' in field_col else 'Other',
            'odds':              odds,
            'stake':             stake,
            'result':            result,
            'profit_loss':       pl,
            'is_cha_ching':      False,
            'cha_ching_criteria': '',
            'notes':             '',
        })
    out = pd.DataFrame(rows)
    out['date'] = pd.to_datetime(out['date'], errors='coerce')
    out['odds'] = pd.to_numeric(out['odds'], errors='coerce')
    out['stake'] = pd.to_numeric(out['stake'], errors='coerce')
    out['profit_loss'] = pd.to_numeric(out['profit_loss'], errors='coerce')
    out['is_cha_ching'] = False
    return out


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
                    avg_odds=0.0, avg_stake=0.0, streak=0,
                    cc_bets=0, cc_hits=0, cc_pl=0.0, cc_hit_rate=0.0, cc_roi=0.0)
    settled  = df[df['result'].isin(['Win', 'Loss'])]
    wins     = len(settled[settled['result'] == 'Win'])
    losses   = len(settled[settled['result'] == 'Loss'])
    staked   = df['stake'].fillna(0).sum()
    total_pl = df['profit_loss'].fillna(0).sum()
    roi      = total_pl / staked * 100 if staked > 0 else 0.0
    hit_rate = wins / len(settled) * 100 if len(settled) > 0 else 0.0

    # Simple aggregates over the placed bets (guarded for empties).
    _odds_vals  = df['odds'].where(df['odds'] > 0).dropna()
    avg_odds    = float(_odds_vals.mean()) if len(_odds_vals) else 0.0
    _stake_vals = df['stake'].where(df['stake'] > 0).dropna()
    avg_stake   = float(_stake_vals.mean()) if len(_stake_vals) else 0.0
    # Current streak: length of the latest run of same-result settled bets,
    # signed (+ for a winning run, − for a losing run).
    streak = 0
    if len(settled) > 0:
        _seq = settled.sort_values('date')['result'].tolist()
        _last = _seq[-1]
        _run = 0
        for _r in reversed(_seq):
            if _r == _last:
                _run += 1
            else:
                break
        streak = _run if _last == 'Win' else -_run
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
        avg_odds=avg_odds, avg_stake=avg_stake, streak=streak,
        cc_bets=len(cc), cc_hits=cc_wins,
        cc_pl=cc_pl, cc_hit_rate=cc_hit, cc_roi=cc_roi,
    )


# ── Fixture fetching ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
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
        # Squiggle returns timezone-naive local Australian time (AEST/AEDT = UTC+10/+11).
        # Localise correctly so kickoff comparisons work — using utc=True alone would
        # treat the strings as already UTC and make games appear ~10h later than real kickoff.
        _raw = pd.to_datetime(df['date'], errors='coerce')
        try:
            df['date_parsed'] = _raw.dt.tz_localize('Australia/Melbourne', ambiguous='infer').dt.tz_convert('UTC')
        except Exception:
            df['date_parsed'] = _raw.dt.tz_localize('UTC')
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
    background: var(--surface);
    border: 1px solid var(--line);
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
.landing-desc  { color: var(--muted); font-size: 13px; line-height: 1.6; max-width: 320px; }

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
.nav-pill-brownlow { background: #34d399; color: var(--bg); }
.nav-pill-betting  { background: #f0b429; color: var(--bg); }

/* ── Betting metric cards ── */
.bh-metric {
    background: var(--surface);
    border: 1px solid var(--line);
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
.bh-metric.negative { border-top: 3px solid #ef7a6d; }
.bh-metric.neutral  { border-top: 3px solid #4a5a6a; }
.bh-metric.gold     { border-top: 3px solid #f0b429; }
.bh-label { color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
.bh-value { font-size: 26px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.15; }
.bh-value.pos  { color: #34d399; }
.bh-value.neg  { color: #ef7a6d; }
.bh-value.neu  { color: var(--text); }
.bh-value.gold { color: #f0b429; }
.bh-sub   { color: var(--muted); font-size: 11px; margin-top: 4px; line-height: 1.4; }

/* ── Bet result badges ── */
.bet-win     { background: rgba(52,211,153,0.18);  color: #34d399; border: 1px solid rgba(52,211,153,0.4);  padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-loss    { background: rgba(239,122,109,0.18);   color: #ef7a6d; border: 1px solid rgba(239,122,109,0.4);   padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-pending { background: rgba(240,180,41,0.15);  color: #f0b429; border: 1px solid rgba(240,180,41,0.4);  padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }
.bet-void    { background: rgba(74,90,106,0.25);   color: var(--muted); border: 1px solid var(--line);               padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; display: inline-block; }

/* ── Cha Ching tip badge ── */
.cc-badge {
    background: #f0b429;
    color: var(--bg);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

/* ── Fixture card ── */
.fixture-card {
    background: var(--surface);
    border: 1px solid var(--line);
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
.fixture-teams { font-size: 15px; font-weight: 700; color: var(--text); letter-spacing: -0.2px; }
.fixture-meta  { font-size: 12px; color: var(--muted); margin-top: 3px; line-height: 1.4; }

/* ── Checklist item ── */
.cl-progress { font-size: 13px; color: var(--muted); margin: 8px 0; line-height: 1.5; }

/* ── Anti-aliasing & font rendering ── */
* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }

/* ── Trend section header ── */
.trend-header {
    color: #34d399; font-size: 10px; font-weight: 800;
    letter-spacing: 2px; text-transform: uppercase;
    border-bottom: 1px solid var(--line); padding-bottom: 6px;
    margin: 24px 0 14px 0;
}

/* ── Cha Ching badge pulse on hover ── */
.cc-badge { transition: opacity 0.15s ease, transform 0.15s ease; display: inline-block; }
.cc-badge:hover { opacity: 0.88; transform: scale(1.03); }

/* ── Live tip badge (emerald ghost pill) ── */
@keyframes live-dot-pulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.35; }
}
.live-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(52, 211, 153, 0.08);
    border: 1px solid rgba(52, 211, 153, 0.45);
    color: #34d399;
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 3px 9px;
    border-radius: 999px;
    vertical-align: middle;
    margin-left: 6px;
}
.live-badge.is-live::before {
    content: "";
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #34d399;
    flex-shrink: 0;
    animation: live-dot-pulse 1.6s ease-in-out infinite;
}

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
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 18px 22px;
    margin: 6px 0;
    overflow: hidden;
}
.bh-sk-title, .bh-sk-line {
    background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-2) 50%, var(--surface-2) 75%);
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
    border-bottom: 1px solid var(--line);
    padding-bottom: 6px;
    margin: 24px 0 14px 0;
}

/* ── Polls-a-Vote Exp_Votes numbers ── */
.pav-ev-gold { color:#f0b429 !important; }
.pav-ev-muted { color:var(--muted) !important; }

/* ── Polls-a-Vote round pills ── */
.pav-pill-green { background:rgba(52,211,153,0.18); color:#34d399; border:1px solid rgba(52,211,153,0.4); }
.pav-pill-blue  { background:rgba(74,144,217,0.18); color:#4a90d9; border:1px solid rgba(74,144,217,0.4); }
.pav-pill-grey  { background:rgba(148,163,184,0.12); color:var(--muted); border:1px solid var(--line); }
.pav-pill-green, .pav-pill-blue, .pav-pill-grey {
    padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;
    white-space:nowrap; display:inline-block; margin:2px 1px;
}

/* ── Polls-a-Vote matrix cell ── */
.pav-matrix-both  { background:#1a5c40; color:#34d399; }
.pav-matrix-mine  { background:rgba(74,144,217,0.25); color:#4a90d9; }
.pav-matrix-model { background:rgba(148,163,184,0.1); color:var(--muted); }

/* ── Polls-a-Vote round checkbox grid ── */
[data-testid="stCheckbox"] > label {
    font-size: 12px !important;
    font-weight: 600 !important;
}

/* ── Polls a Vote — Midnight Turf redesign ── */
.title-bar:has(.pav-flush){background:transparent !important;border:none !important;box-shadow:none !important;padding:0 !important;}
.pav-secthead{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:6px;margin:26px 0 14px;}
.pav-secthead .t{color:#34d399;font-size:10px;font-weight:800;letter-spacing:2px;text-transform:uppercase;}
.pav-key{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);letter-spacing:.03em;}
.pav-key b{font-weight:600;}
.pav-empty{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);padding:10px 0;opacity:.7;}
/* matrix — flush table */
.pav-matrix{border-collapse:collapse;width:100%;}
.pav-matrix th{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;color:var(--muted);letter-spacing:.03em;padding:5px 4px;border-bottom:1px solid var(--line);text-align:center;min-width:30px;}
.pav-matrix th.pl{text-align:left;}
.pav-matrix td{font-family:'IBM Plex Mono',monospace;font-size:14px;text-align:center;padding:6px 0;border-bottom:1px solid rgba(140,165,185,.07);min-width:30px;}
.pav-matrix td.pl{text-align:left;white-space:nowrap;padding:6px 16px 6px 0;}
.pav-matrix td.pl .nm{font-family:'Archivo',sans-serif;font-size:13px;font-weight:700;color:var(--text);}
.pav-matrix td.pl .tm{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);}
.pav-matrix tbody tr:hover td{background:rgba(140,165,185,.04);}
/* card — intentional surface panel */
.pav-card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:10px;}
.pav-card .nm{font-family:'Archivo',sans-serif;font-size:15px;font-weight:800;color:var(--text);}
.pav-card .tm{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:2px;}
.pav-card .con{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;margin-top:5px;}
.pav-card .lbl{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}
.pav-card .agree{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:600;color:#f0b429;line-height:1;}
.pav-card .os{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;color:#f0b429;}
.pav-card .sbadge{background:rgba(52,211,153,0.18);color:#34d399;border:1px solid rgba(52,211,153,0.4);padding:1px 8px;border-radius:12px;font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.1em;margin-left:8px;}
.pav-pill-star{background:rgba(52,211,153,0.16);color:#34d399;border:1px solid rgba(52,211,153,0.4);}
.pav-pill-dash{background:transparent;color:var(--muted);border:1px dashed var(--line);}
.pav-pill-star,.pav-pill-dash{padding:2px 9px;border-radius:12px;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;white-space:nowrap;display:inline-block;margin:2px 2px 2px 0;}
/* borderless bottom-border fields inside the Add expander only */
.stApp:has(.pav-page) [data-testid="stExpander"] .react-aria-ComboBox>div,
.stApp:has(.pav-page) [data-testid="stExpander"] [data-testid="stTextInput"] input,
.stApp:has(.pav-page) [data-testid="stExpander"] [data-testid="stNumberInput"] input{
    background:transparent !important;border:none !important;border-bottom:1px solid var(--line) !important;border-radius:0 !important;}
/* quiet mono text-link buttons at card foot (innermost-match scoping) */
.stApp:has(.pav-page) div[data-testid="stVerticalBlock"]:has(.pav-settle-marker):not(:has(div[data-testid="stVerticalBlock"] .pav-settle-marker)) button,
.stApp:has(.pav-page) div[data-testid="stVerticalBlock"]:has(.pav-delete-marker):not(:has(div[data-testid="stVerticalBlock"] .pav-delete-marker)) button{
    background:transparent !important;border:none !important;color:var(--muted) !important;
    font-family:'IBM Plex Mono',monospace !important;font-size:11px !important;font-weight:500 !important;
    letter-spacing:.06em;padding:4px 0 !important;min-height:unset !important;box-shadow:none !important;}
.stApp:has(.pav-page) div[data-testid="stVerticalBlock"]:has(.pav-settle-marker):not(:has(div[data-testid="stVerticalBlock"] .pav-settle-marker)) button:hover{color:#34d399 !important;}
.stApp:has(.pav-page) div[data-testid="stVerticalBlock"]:has(.pav-delete-marker):not(:has(div[data-testid="stVerticalBlock"] .pav-delete-marker)) button:hover{color:#ef7a6d !important;}

</style>
"""


def _inject_css():
    inject_global_theme()
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
        xaxis=dict(gridcolor='rgba(140,165,185,.14)', showgrid=True, title=''),
        yaxis=dict(gridcolor='rgba(140,165,185,.14)', showgrid=True, zeroline=False, title='Units'),
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
        xaxis=dict(gridcolor='rgba(140,165,185,.14)'),
        yaxis=dict(gridcolor='rgba(140,165,185,.14)', zeroline=True, zerolinecolor=C['border']),
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


# ── Add Multi Tip dialog ───────────────────────────────────────────────────────

@st.dialog("Add Multi Tip", width="large")
def _add_multi_dialog():
    st.caption("Enter each leg on its own line, or comma-separated (e.g. Daicos 29.5+ disp / Oliver BTTS)")
    legs_text = st.text_area("Legs", height=80, placeholder="Daicos 29.5+ Disposals\nOliver 25.5+ Disposals\nNeale BTTS")
    games_text = st.text_input("Games (optional)", placeholder="e.g. GWS v Melbourne / Cats v Lions")

    col1, col2 = st.columns(2)
    with col1:
        bookmaker = st.selectbox("Bookmaker", BOOKMAKERS)
        odds  = st.number_input("Combined odds (decimal)", min_value=1.01, max_value=500.0,
                                value=3.0, step=0.05, format="%.2f")
    with col2:
        stake = st.number_input("Stake (units)", min_value=0.01, max_value=1000.0,
                                value=1.0, step=0.5, format="%.2f")
        bet_date = st.date_input("Date", value=date.today())

    st.markdown('<hr style="margin:8px 0">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:var(--muted);font-weight:600;letter-spacing:0.8px;'
                'text-transform:uppercase;margin-bottom:6px">CHA CHING CHECKLIST</div>',
                unsafe_allow_html=True)

    pfx    = "_multi_cl_"
    ticked = 0
    for item_key, item_label in CHECKLIST_ITEMS:
        sk = f"{pfx}{item_key}"
        if st.checkbox(item_label, value=st.session_state.get(sk, False), key=sk):
            ticked += 1

    is_flagged = ticked >= CC_THRESHOLD
    if is_flagged:
        st.success(f"**Cha Ching!** {ticked}/6 criteria met — will be auto-flagged")
    else:
        st.info(f"{ticked}/6 criteria met — tick {CC_THRESHOLD - ticked} more to auto-flag")

    notes = st.text_area("Notes", height=60, placeholder="Any extra context...")

    ca, cb = st.columns(2)
    with ca:
        if st.button("Save Multi Tip", type="primary", use_container_width=True):
            if not legs_text.strip():
                st.error("Enter at least one leg.")
            else:
                player_label = legs_text.strip().replace("\n", " / ")
                game_key     = games_text.strip() or "Multi"
                criteria     = [k for k, _ in CHECKLIST_ITEMS if st.session_state.get(f"{pfx}{k}", False)]
                err = _save_tip(
                    game_key, player_label, "Multi",
                    criteria, is_flagged, notes,
                    stake=float(stake), odds=float(odds), bookmaker=bookmaker,
                    tip_id=_form_instance_id('_multi_tip_id'),
                )
                if err is None:
                    _clear_form_instance('_multi_tip_id')
                    for item_key, _ in CHECKLIST_ITEMS:
                        st.session_state.pop(f"{pfx}{item_key}", None)
                    st.toast(f"Multi tip saved — {'Cha Ching flagged!' if is_flagged else 'not yet flagged'}")
                    st.rerun()
                else:
                    st.error(f"Save failed — {err}")
    with cb:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# ── Checklist dialog ───────────────────────────────────────────────────────────

@st.dialog("Cha Ching Checklist", width="large")
def _checklist_dialog():
    player_orig = st.session_state.get('_cl_player', '')
    market_orig = st.session_state.get('_cl_market', '')
    game_key    = st.session_state.get('_cl_game', '')
    odds_orig   = float(st.session_state.get('_cl_odds', 0.0) or 0.0)
    bookmaker   = str(st.session_state.get('_cl_bookmaker', ''))
    line_orig   = float(st.session_state.get('_cl_line', 0.0) or 0.0)
    pfx         = f"_clv_{game_key}_{player_orig}_{market_orig}_"

    # ── Header inputs ──────────────────────────────────────────────────────────
    h1, h2, h3 = st.columns([2, 2, 1])
    with h1:
        player = st.text_input(
            "Player",
            value=player_orig,
            key=f"{pfx}h_player",
            placeholder="e.g. Nick Daicos",
        )
    with h2:
        line_sfx     = f" {line_orig:.1f}" if line_orig > 0 else ""
        market_line  = st.text_input(
            "Market / Line",
            value=f"{market_orig}{line_sfx}".strip(),
            key=f"{pfx}h_market_line",
            placeholder="e.g. Disposals O/U 29.5",
        )
    with h3:
        odds_default = odds_orig if odds_orig > 1.01 else 2.0
        odds_val = st.number_input(
            "Odds",
            min_value=1.01, max_value=100.0,
            value=odds_default,
            step=0.05, format="%.2f",
            key=f"{pfx}h_odds",
        )

    # ── Progress indicator ─────────────────────────────────────────────────────
    ticked = sum(1 for k in NEW_CHECKLIST_KEYS
                 if st.session_state.get(f"{pfx}{k}_chk", False))
    total  = len(NEW_CHECKLIST_KEYS)
    pct    = ticked / total
    bar_col  = C["green"] if ticked >= CC_THRESHOLD else C["gold"]
    msg_col  = C["green"] if ticked >= CC_THRESHOLD else C["gold"]
    prog_msg = f"{ticked}/{total} criteria checked"

    st.markdown(
        f'<div style="margin:8px 0 4px;font-size:12px;font-weight:600;color:{msg_col}">'
        f'{prog_msg}</div>'
        f'<div style="background:{C["border"]};border-radius:4px;height:6px">'
        f'<div style="background:{bar_col};height:6px;width:{pct * 100:.0f}%;'
        f'border-radius:4px"></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr style="margin:10px 0 4px">', unsafe_allow_html=True)

    # ── Helpers ────────────────────────────────────────────────────────────────
    _SIGS = ["—", "Positive", "Neutral", "Negative"]

    def _row(key, label, sig_opts=None):
        opts    = sig_opts or _SIGS
        sk_chk  = f"{pfx}{key}_chk"
        sk_sig  = f"{pfx}{key}_sig"
        sk_note = f"{pfx}{key}_note"
        checked = st.checkbox(label, value=st.session_state.get(sk_chk, False), key=sk_chk)
        if checked:
            c1, c2 = st.columns([1, 2])
            with c1:
                cur = st.session_state.get(sk_sig, opts[0])
                st.selectbox("signal", opts,
                             index=opts.index(cur) if cur in opts else 0,
                             key=sk_sig, label_visibility="collapsed")
            with c2:
                st.text_input("notes", value=st.session_state.get(sk_note, ''),
                              key=sk_note, placeholder="Notes…",
                              label_visibility="collapsed")

    def _hdr(title):
        st.markdown(
            f'<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;'
            f'text-transform:uppercase;color:{C["gold"]};'
            f'border-left:3px solid {C["gold"]};padding-left:8px;margin:12px 0 4px">'
            f'{title}</div>',
            unsafe_allow_html=True,
        )

    # ── Market & Promo ─────────────────────────────────────────────────────────
    _hdr("Market & Promo")
    _row("promo_scan", "Promo / odds scan (bookie, promo type, line, odds)")

    # ── Matchup ────────────────────────────────────────────────────────────────
    _hdr("Matchup")
    _row("dvp_check",        "DVP check",
         ["—", "Favourable", "Neutral", "Tough"])
    _row("opposition_stats", "Opposition allowed stats via Wheelo",
         ["—", "Favourable", "Neutral", "Tough"])
    _row("stat_split",       "Stat split check — contested vs uncontested suits matchup (AFL.com)")
    _row("tagger_risk",      "Tagger risk",
         ["—", "No risk", "Possible", "Likely tagged"])
    _row("role_cba",         "Role / CBA % (mids only)",
         ["—", "High", "Moderate", "Low", "Changed"])

    # ── Player Form ────────────────────────────────────────────────────────────
    _hdr("Player Form")
    _row("statmate_trends", "Statmate trends — hitrate last 5/10, venue, opponent, home/away")
    _row("value_read",      "Value read",
         ["—", "Value", "Fair", "Overpriced"])

    # ── Reasoning & Fault Check ────────────────────────────────────────────────
    _hdr("Reasoning & Fault Check")

    sk_reasoning = f"{pfx}reasoning"
    st.text_area(
        "Walk me through your reasoning for this pick",
        value=st.session_state.get(sk_reasoning, ''),
        key=sk_reasoning,
        height=80,
        placeholder="What makes this a good bet?",
    )

    rc1, rc2 = st.columns(2)
    with rc1:
        role_opts = ["Coach confirmed", "Named position", "Inference", "Gut feel"]
        sk_role   = f"{pfx}role_certainty"
        cur_role  = st.session_state.get(sk_role, role_opts[0])
        st.selectbox("Role certainty", role_opts,
                     index=role_opts.index(cur_role) if cur_role in role_opts else 0,
                     key=sk_role)
    with rc2:
        sk_absorb = f"{pfx}absorb"
        st.text_input("Who else could absorb this role?",
                      value=st.session_state.get(sk_absorb, ''),
                      key=sk_absorb,
                      placeholder="e.g. Brayshaw if Petracca out")

    sk_zero = f"{pfx}zero_sum"
    st.toggle(
        "Zero-sum risk — two picks depending on the same vacancy",
        value=st.session_state.get(sk_zero, False),
        key=sk_zero,
    )

    sk_weather = f"{pfx}weather"
    st.text_input("Weather check",
                  value=st.session_state.get(sk_weather, ''),
                  key=sk_weather,
                  placeholder="e.g. Fine, 22 °C, slight wind")

    # ── Verdict ────────────────────────────────────────────────────────────────
    _hdr("Verdict")

    sk_decision = f"{pfx}decision"
    decision    = st.session_state.get(sk_decision)
    d1, d2, d3  = st.columns(3)
    with d1:
        if st.button("✓  Take it", use_container_width=True, key=f"{pfx}btn_take"):
            st.session_state[sk_decision] = "Take it"
            st.rerun()
    with d2:
        if st.button("~  Unsure", use_container_width=True, key=f"{pfx}btn_unsure"):
            st.session_state[sk_decision] = "Unsure"
            st.rerun()
    with d3:
        if st.button("✕  Pass", use_container_width=True, key=f"{pfx}btn_pass"):
            st.session_state[sk_decision] = "Pass"
            st.rerun()

    if decision:
        dec_color = (C["green"] if decision == "Take it"
                     else C["gold"] if decision == "Unsure"
                     else C["red"])
        st.markdown(
            f'<div style="text-align:center;font-size:13px;font-weight:600;'
            f'color:{dec_color};margin:4px 0 0">→ {decision}</div>',
            unsafe_allow_html=True,
        )

    sk_final_notes = f"{pfx}final_notes"
    final_notes = st.text_area(
        "Final reasoning notes",
        value=st.session_state.get(sk_final_notes, ''),
        key=sk_final_notes,
        height=60,
        placeholder="Any final thoughts...",
    )

    st.markdown('<hr style="margin:10px 0 8px">', unsafe_allow_html=True)

    # ── Stake / save ───────────────────────────────────────────────────────────
    s1, s2 = st.columns(2)
    with s1:
        stake = st.number_input(
            "Unit size",
            min_value=0.0, max_value=100.0,
            value=float(st.session_state.get(f'{pfx}stake', 1.0)),
            step=0.5, format='%.2f',
            key=f'{pfx}stake',
        )
    with s2:
        odds_disp  = f"{odds_val:.2f}" if odds_val > 1 else "—"
        bookie_str = f" ({bookmaker})" if bookmaker else ""
        st.markdown(
            f'<div style="margin-top:28px;font-family:DM Mono,monospace;'
            f'font-size:14px;color:{C["gold"]};font-weight:700">'
            f'{odds_disp}{bookie_str}</div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Tip", type="primary", use_container_width=True):
            criteria = [k for k in NEW_CHECKLIST_KEYS
                        if st.session_state.get(f"{pfx}{k}_chk", False)]

            parts = [s for s in [
                final_notes,
                f"Reasoning: {st.session_state.get(sk_reasoning, '')}" if st.session_state.get(sk_reasoning) else '',
                f"Decision: {decision}" if decision else '',
            ] if s]
            combined = " | ".join(parts)

            h_player = st.session_state.get(f"{pfx}h_player", player_orig) or player_orig
            h_odds   = float(st.session_state.get(f"{pfx}h_odds", odds_orig))

            is_flagged = decision == "Take it"
            err = _save_tip(
                game_key, h_player, market_orig, criteria,
                is_flagged, combined,
                stake=float(stake), odds=h_odds, bookmaker=bookmaker, line=line_orig,
                tip_id=_form_instance_id('_cl_tip_id'),
            )
            if err is None:
                _clear_form_instance('_cl_tip_id')
                st.session_state['_cl_open'] = False
                st.toast(f"Tip saved — {'Cha Ching flagged!' if is_flagged else 'not flagged'}")
                st.rerun()
            else:
                st.error(f"**Save failed** — {err}")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state['_cl_open'] = False
            st.rerun()


def _open_checklist(player: str, market: str, game_key: str,
                    odds: float = 0.0, bookmaker: str = '', line: float = 0.0):
    st.session_state['_cl_player']    = player
    st.session_state['_cl_market']    = market
    st.session_state['_cl_game']      = game_key
    st.session_state['_cl_odds']      = odds
    st.session_state['_cl_bookmaker'] = bookmaker
    st.session_state['_cl_line']      = line
    st.session_state['_cl_open']      = True


# ── Add Bet dialog ─────────────────────────────────────────────────────────────

@st.dialog("Add New Bet", width="large")
def _add_bet_dialog():
    _bet_id = _form_instance_id('_bet_form_id')
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
                'bet_id':           _bet_id,
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
            _insert_bet(new_row)
            # Only reached when the write didn't raise — a failure keeps the id
            # so a retry reuses it and upserts the same row.
            _clear_form_instance('_bet_form_id')
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
    elif _has('DATE', 'MATCH', 'SELECTION', 'BOOKMAKER', 'ODDS', 'STAKE', 'RESULT', 'PROFIT_LOSS'):
        fmt = 'native'
    elif _has('DATE', 'EVENT', 'SELECTION', 'STAKE') or _has('DATE', 'MATCH', 'SELECTION', 'STAKE'):
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

    def _remap_native(df):
        df = df.copy()
        df.columns = [c.upper() for c in df.columns]
        result_map = {'WON': 'Win', 'WIN': 'Win', 'LOST': 'Loss', 'LOSS': 'Loss',
                      'PENDING': 'Pending', 'VOID': 'Void/Refund', 'VOID/REFUND': 'Void/Refund'}
        rows = []
        for _, r in df.iterrows():
            raw_result = str(r.get('RESULT', 'Pending')).strip().upper()
            result = result_map.get(raw_result, 'Pending')
            pl = pd.to_numeric(r.get('PROFIT_LOSS', 0), errors='coerce')
            pl = float(pl) if not pd.isna(pl) else 0.0
            rows.append({
                'bet_id': str(uuid.uuid4())[:8],
                'date': str(r.get('DATE', date.today().strftime('%Y-%m-%d'))),
                'match': str(r.get('MATCH', '')),
                'market_type': str(r.get('MARKET_TYPE', r.get('MARKET', 'Other'))),
                'selection': str(r.get('SELECTION', '')),
                'bookmaker': str(r.get('BOOKMAKER', 'Other')),
                'odds': round(float(pd.to_numeric(r.get('ODDS', 2), errors='coerce') or 2.0), 2),
                'stake': round(abs(float(pd.to_numeric(r.get('STAKE', 0), errors='coerce') or 0)), 2),
                'result': result,
                'profit_loss': round(pl, 2),
                'is_cha_ching': False,
                'cha_ching_criteria': '',
                'notes': str(r.get('NOTES', '')),
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
        elif fmt == 'native':
            mapped = _remap_native(raw)
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


# ── Page 1: Performance ────────────────────────────────────────────────────────

def render_bh_dashboard():
    _inject_css()
    # Primary buttons on this page: emerald fill, dark text.
    st.markdown(
        '<style>'
        'div[data-testid="stButton"] button[kind="primary"]{'
        'background:#34d399 !important;color:#0a1017 !important;border:none !important;'
        'font-weight:700 !important;border-radius:8px !important;}'
        'div[data-testid="stButton"] button[kind="primary"]:hover{'
        'background:#2bbe89 !important;color:#0a1017 !important;}'
        '</style>',
        unsafe_allow_html=True,
    )

    bets = _load_bets()
    s    = _betting_stats(bets)

    # ── 1. Header (no box) ────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;'
        'color:#7e8c99">Betting Hub</div>'
        '<h1 style="font-family:\'Sora\',sans-serif;font-size:34px;font-weight:800;color:#e9eef3;'
        'margin:2px 0 0;line-height:1.05">Dashboard</h1>'
        '<div style="font-size:13px;color:#7e8c99;margin-top:4px">'
        'P&amp;L, hit rate and recent bets at a glance</div>',
        unsafe_allow_html=True,
    )

    if bets.empty:
        st.info("No bets logged yet. Use the Bet Tracker to add your first bet.")
        return

    pl   = s['total_pl']
    roi  = s['roi']
    n_settled = s['wins'] + s['losses']
    _pos = '#34d399'; _neg = '#ef7a6d'; _mut = '#7e8c99'
    pl_col  = _pos if pl > 0 else (_neg if pl < 0 else _mut)
    roi_col = _pos if roi > 0 else (_neg if roi < 0 else _mut)

    # ── 2. Hero: net P&L + ROI | cumulative chart ─────────────────────────────
    _hero_l, _hero_r = st.columns([1, 2])
    with _hero_l:
        st.markdown(
            '<div style="display:flex;flex-direction:column;justify-content:center;min-height:260px">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:50px;font-weight:600;'
            f'color:{pl_col};line-height:1">{pl:+.2f}u</div>'
            '<div style="font-size:11px;color:#7e8c99;text-transform:uppercase;letter-spacing:1px;'
            f'margin-top:8px">net profit · {n_settled} bets settled</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:24px;font-weight:600;'
            f'color:{roi_col};margin-top:18px">{roi:+.1f}%</div>'
            '<div style="font-size:10px;color:#7e8c99;text-transform:uppercase;letter-spacing:1px;'
            'margin-top:2px">return on investment</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with _hero_r:
        settled_chart = bets[bets['result'].isin(['Win', 'Loss'])].copy()
        _bh_pl_fig = apply_chart_theme(_pl_chart(settled_chart))
        _bh_pl_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 height=260, margin=dict(l=48, r=12, t=10, b=30))
        _bh_pl_fig.update_xaxes(tickfont=dict(family='IBM Plex Mono, monospace', color='#7e8c99', size=11))
        _bh_pl_fig.update_yaxes(tickfont=dict(family='IBM Plex Mono, monospace', color='#7e8c99', size=11))
        st.plotly_chart(_bh_pl_fig, use_container_width=True, key='bh_pl_chart', config=PLOTLY_TOUCH_CONFIG)

    # ── 3. Metadata strip (hit rate · avg odds · avg stake · streak) ──────────
    def _strip_cell(value, sub, first=False, value_color='#e9eef3'):
        bd  = '' if first else 'border-left:1px solid rgba(140,165,185,.14)'
        pad = 'padding:0 22px 0 0' if first else 'padding:0 22px'
        return (
            f'<div style="{pad};{bd}">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:24px;font-weight:600;'
            f'color:{value_color};text-align:right">{value}</div>'
            f'<div style="font-size:10px;color:#7e8c99;text-transform:uppercase;letter-spacing:1px;'
            f'text-align:right;margin-top:4px">{sub}</div>'
            '</div>'
        )
    _streak = s['streak']
    _streak_col = _pos if _streak > 0 else (_neg if _streak < 0 else _mut)
    _streak_txt = f'{_streak:+d}' if _streak != 0 else '0'
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);margin:18px 0 4px">'
        + _strip_cell(f"{s['hit_rate']:.1f}%", f"hit rate · {s['wins']}–{s['losses']}", first=True)
        + _strip_cell(f"{s['avg_odds']:.2f}", "avg odds")
        + _strip_cell(f"{s['avg_stake']:.2f}u", "avg stake")
        + _strip_cell(_streak_txt, "current streak", value_color=_streak_col)
        + '</div>',
        unsafe_allow_html=True,
    )

    # ── 4. All vs Cha Ching (conditional) ─────────────────────────────────────
    settled = bets[bets['result'].isin(['Win', 'Loss'])]
    non_cc_settled = settled[settled['is_cha_ching'] != True]
    if len(settled) > 0:
        if non_cc_settled.empty:
            st.markdown(
                '<div style="margin:22px 0 4px;font-size:13px;color:#7e8c99">All '
                f'{len(settled)} settled bets are '
                '<span style="color:#f0b429;font-weight:700">Cha Ching</span> tips.</div>',
                unsafe_allow_html=True,
            )
        else:
            cc_s   = _betting_stats(bets[bets['is_cha_ching'] == True])
            rest_s = _betting_stats(bets[bets['is_cha_ching'] != True])

            def _cmp_col(title, title_color, cs, first=False):
                bd  = '' if first else 'border-left:1px solid rgba(140,165,185,.14)'
                pad = 'padding:0 28px 0 0' if first else 'padding:0 28px'

                def _line(lbl, val, col):
                    return (
                        '<div style="display:flex;justify-content:space-between;align-items:baseline;'
                        'padding:6px 0;border-bottom:1px solid rgba(140,165,185,.08)">'
                        f'<span style="font-size:11px;color:#7e8c99;text-transform:uppercase;'
                        f'letter-spacing:.5px">{lbl}</span>'
                        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:15px;'
                        f'color:{col}">{val}</span></div>'
                    )
                _plc  = _pos if cs['total_pl'] > 0 else (_neg if cs['total_pl'] < 0 else _mut)
                _roic = _pos if cs['roi'] > 0 else (_neg if cs['roi'] < 0 else _mut)
                return (
                    f'<div style="{pad};{bd}">'
                    f'<div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
                    f'color:{title_color};margin-bottom:6px">{title}</div>'
                    + _line('P&amp;L', f"{cs['total_pl']:+.2f}u", _plc)
                    + _line('ROI', f"{cs['roi']:+.1f}%", _roic)
                    + _line('Hit rate', f"{cs['hit_rate']:.1f}%", '#e9eef3')
                    + '</div>'
                )
            st.markdown(
                '<div style="margin:22px 0 4px;display:grid;grid-template-columns:1fr 1fr">'
                + _cmp_col('Cha Ching tips', '#f0b429', cc_s, first=True)
                + _cmp_col('Other bets', '#7e8c99', rest_s)
                + '</div>',
                unsafe_allow_html=True,
            )

    # ── 5. Recent bets ────────────────────────────────────────────────────────
    _hdr_col, _tog_col = st.columns([3, 1])
    with _hdr_col:
        st.markdown(
            '<div style="margin:30px 0 8px;font-size:10px;font-weight:700;letter-spacing:1.5px;'
            'text-transform:uppercase;color:#7e8c99">Recent bets</div>',
            unsafe_allow_html=True,
        )
    _show_all = st.session_state.get('_bh_show_all_bets', False)
    with _tog_col:
        _lbl = "Show less" if _show_all else f"Show all ({len(bets)})"
        if st.button(_lbl, key='_bh_tog_bets', use_container_width=True):
            st.session_state['_bh_show_all_bets'] = not _show_all
            st.rerun()

    recent = bets.sort_values('date', ascending=False)
    if not _show_all:
        recent = recent.head(10)

    # CC badge inverts: shown only when non-CC bets exist anywhere, and only on CC rows.
    _any_non_cc = bool((bets['is_cha_ching'] != True).any())

    def _result_pill(result):
        if result == 'Win':
            _c, _bg = '#34d399', 'rgba(52,211,153,0.14)'
        elif result == 'Loss':
            _c, _bg = '#ef7a6d', 'rgba(239,122,109,0.14)'
        else:
            _c, _bg = '#7e8c99', 'rgba(140,165,185,0.10)'
        return (f'<span style="display:inline-block;padding:2px 9px;border-radius:10px;font-size:10px;'
                f'font-weight:700;color:{_c};background:{_bg}">{result}</span>')

    _th = ('padding:7px 10px;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
           'color:#7e8c99;border-bottom:1px solid rgba(140,165,185,.22)')
    _td = 'padding:8px 10px;border-bottom:1px solid rgba(140,165,185,.14)'
    _head = (
        '<tr>'
        f'<th style="{_th};text-align:left">Date</th>'
        f'<th style="{_th};text-align:left">Selection</th>'
        f'<th style="{_th};text-align:right">Bookmaker</th>'
        f'<th style="{_th};text-align:right">Odds</th>'
        f'<th style="{_th};text-align:right">Result</th>'
        f'<th style="{_th};text-align:right">P&amp;L</th>'
        '</tr>'
    )
    _rows = ''
    for _, row in recent.iterrows():
        result = str(row.get('result', 'Pending'))
        pl_v = row.get('profit_loss', 0) or 0
        pl_c = _pos if pl_v > 0 else (_neg if pl_v < 0 else _mut)
        date_str = pd.Timestamp(row['date']).strftime('%d %b') if pd.notna(row.get('date')) else '—'
        odds_val = row.get('odds', 0) or 0
        odds_str = f'{float(odds_val):.2f}' if float(odds_val) > 0 else '—'
        sel = str(row.get('selection', '—'))[:48]
        cc_badge = ''
        if _any_non_cc and row.get('is_cha_ching'):
            cc_badge = ('<span style="color:#f0b429;background:rgba(240,180,41,0.14);font-size:9px;'
                        'font-weight:700;border-radius:3px;padding:1px 5px;margin-left:7px">CC</span>')
        _rows += (
            '<tr>'
            f'<td style="{_td};font-family:\'IBM Plex Mono\',monospace;color:#7e8c99;font-size:12px">{date_str}</td>'
            f'<td style="{_td};color:#e9eef3">{sel}{cc_badge}</td>'
            f'<td style="{_td};text-align:right;color:#7e8c99;font-size:12px">{str(row.get("bookmaker",""))}</td>'
            f'<td style="{_td};text-align:right;font-family:\'IBM Plex Mono\',monospace;color:#e9eef3">{odds_str}</td>'
            f'<td style="{_td};text-align:right">{_result_pill(result)}</td>'
            f'<td style="{_td};text-align:right;font-family:\'IBM Plex Mono\',monospace;font-weight:600;'
            f'color:{pl_c}">{pl_v:+.2f}u</td>'
            '</tr>'
        )
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        + _head + _rows + '</table>',
        unsafe_allow_html=True,
    )


# ── Page 2: Bet Tracker ────────────────────────────────────────────────────────

def render_bet_tracker():
    _inject_css()
    st.markdown(
        '<div class="title-bar"><h2 style="color:var(--text);margin:0">Bet Tracker</h2>'
        '<p style="color:var(--muted);margin:4px 0 0 0">'
        'Your imported betting history — filters, stats, full table</p></div>',
        unsafe_allow_html=True,
    )

    raw = _load_user_import()

    # ── Empty state: no import yet ────────────────────────────────────────────
    if raw is None or raw.empty:
        st.info("Upload your betting history to get started.")
        uploaded = st.file_uploader(
            "Choose a CSV or Excel file",
            type=['csv', 'xlsx'],
            key='bt_upload_main',
            label_visibility='collapsed',
        )
        if uploaded is not None:
            try:
                if uploaded.name.endswith('.xlsx'):
                    df_up = pd.read_excel(BytesIO(uploaded.read()))
                else:
                    df_up = pd.read_csv(uploaded)
                _ensure_dirs()
                df_up.to_csv(USER_IMPORT_CSV, index=False)
                st.rerun()
            except Exception as e:
                st.error(f"Could not read file: {e}")
        return

    # ── Import exists: normalise ──────────────────────────────────────────────
    bets = _load_user_import_as_bets()
    if bets is None or bets.empty:
        st.warning("Import file exists but could not be parsed. Try re-uploading.")
        if st.button("🗑️ Delete Import", key='bt_delete_err'):
            _delete_user_import()
            st.rerun()
        return

    # ── Delete button ─────────────────────────────────────────────────────────
    col_del, _ = st.columns([1, 7])
    with col_del:
        if st.button("🗑️ Delete Import", key='bt_delete', type='secondary'):
            _delete_user_import()
            st.rerun()

    # ── Filters ───────────────────────────────────────────────────────────────
    _bt_filter_section(bets)


@st.fragment
def _bt_filter_section(bets):
    st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        all_markets = ['All'] + sorted(bets['market_type'].dropna().unique().tolist())
        mkt_filter = st.selectbox("Market", all_markets, index=0, key='bt_mkt')
    with fc2:
        all_books = ['All'] + sorted(bets['bookmaker'].dropna().unique().tolist())
        bk_filter = st.selectbox("Bookmaker", all_books, index=0, key='bt_bk')
    with fc3:
        res_filter = st.selectbox("Result", ['All'] + RESULTS, index=0, key='bt_res')
    with fc4:
        if pd.notna(bets['date']).any():
            min_d = bets['date'].dropna().min().date()
            max_d = bets['date'].dropna().max().date()
            date_range = st.date_input("Date range", (min_d, max_d))
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
    if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        try:
            filt = filt[
                (filt['date'].dt.date >= date_range[0]) &
                (filt['date'].dt.date <= date_range[1])
            ]
        except Exception:
            pass
    filt = filt.sort_values('date', ascending=False).reset_index(drop=True)

    # ── Stats strip ───────────────────────────────────────────────────────────
    fs = _betting_stats(filt)
    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
    for col, lbl, val in [
        (sc1, "Bets",     str(fs['total_bets'])),
        (sc2, "P&L",      f"{fs['total_pl']:+.2f}u"),
        (sc3, "ROI",      f"{fs['roi']:+.1f}%"),
        (sc4, "Hit Rate", f"{fs['hit_rate']:.1f}%"),
        (sc5, "W/L",      f"{fs['wins']}W / {fs['losses']}L"),
        (sc6, "Pending",  str(fs['pending'])),
    ]:
        col.metric(lbl, val)

    # ── Bet table ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Bets</div>', unsafe_allow_html=True)
    if filt.empty:
        st.info("No bets match the current filters.")
        return

    display = filt[[
        'date', 'match', 'market_type', 'selection', 'bookmaker',
        'odds', 'stake', 'result', 'profit_loss', 'notes'
    ]].copy()
    display['date']        = display['date'].dt.strftime('%d %b %Y')
    display['odds']        = display['odds'].round(2)
    display['stake']       = display['stake'].round(2)
    display['profit_loss'] = display['profit_loss'].round(2)
    display.columns = ['Date', 'Match', 'Market', 'Selection', 'Bookmaker',
                       'Odds', 'Stake', 'Result', 'P&L', 'Notes']

    def _style_bets(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Result'] == 'Win':
                styles.loc[i, 'P&L'] = 'color: #34d399; font-weight: 700'
            elif row['Result'] == 'Loss':
                styles.loc[i, 'P&L'] = 'color: #ef7a6d; font-weight: 700'
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


# ── Page 3: Cha Ching Tips ─────────────────────────────────────────────────────

def render_cha_ching_tips():
    _inject_css()

    # ── Midnight Turf flush styles — page-scoped via .cc-tips-marker so other
    #    betting-hub pages (Performance / Bet Tracker / Trends) keep their boxes ──
    st.markdown("""
<span class="cc-tips-marker" style="display:none"></span>
<style>
/* record strip */
.stApp:has(.cc-tips-marker) .cc-rec-strip{display:flex;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:4px 0 24px}
.stApp:has(.cc-tips-marker) .cc-rec-cell{flex:1;padding:13px 20px;border-left:1px solid var(--line)}
.stApp:has(.cc-tips-marker) .cc-rec-cell:first-child{border-left:none;padding-left:0}
.stApp:has(.cc-tips-marker) .cc-rec-num{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:var(--text);line-height:1}
.stApp:has(.cc-tips-marker) .cc-rec-num.pos{color:var(--emerald)}
.stApp:has(.cc-tips-marker) .cc-rec-num.neg{color:#ef7a6d}
.stApp:has(.cc-tips-marker) .cc-rec-lbl{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:7px}
/* masthead header (flush, no box) */
.stApp:has(.cc-tips-marker) .cc-kicker{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}
.stApp:has(.cc-tips-marker) .cc-title{font-family:'Archivo',sans-serif;font-size:30px;font-weight:800;color:var(--text);margin:2px 0 0;line-height:1.05}
.stApp:has(.cc-tips-marker) .cc-sub{font-size:13px;color:var(--muted);margin-top:4px}
/* lock outline button (top-right of masthead) */
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-lock-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-lock-marker)) button{
  background:transparent !important;border:1px solid var(--line) !important;color:var(--muted) !important;
  font-family:'IBM Plex Mono',monospace !important;text-transform:uppercase !important;letter-spacing:.12em !important;
  font-weight:600 !important;box-shadow:none !important}
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-lock-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-lock-marker)) button:hover{
  border-color:var(--muted) !important;color:var(--text) !important}
/* filters: borderless controls with a single bottom rule, emerald on focus */
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-filters-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-filters-marker)) div[data-testid="stSelectbox"]>div>div,
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-filters-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-filters-marker)) [data-testid="stDateInput"] input{
  background:transparent !important;border:none !important;border-bottom:1px solid var(--line) !important;border-radius:0 !important;box-shadow:none !important}
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-filters-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-filters-marker)) div[data-testid="stSelectbox"]>div>div:focus-within,
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-filters-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-filters-marker)) [data-testid="stDateInput"] input:focus{
  border-bottom-color:var(--emerald) !important}
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-filters-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-filters-marker)) label{
  font-family:'IBM Plex Mono',monospace !important;font-size:10px !important;letter-spacing:.14em !important;
  text-transform:uppercase !important;color:var(--muted) !important}
/* bet-history table (flush) */
.stApp:has(.cc-tips-marker) table.cc-hist{width:100%;border-collapse:collapse;font-size:13px;margin-top:2px}
.stApp:has(.cc-tips-marker) table.cc-hist th{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
.stApp:has(.cc-tips-marker) table.cc-hist th.r{text-align:right}
.stApp:has(.cc-tips-marker) table.cc-hist td{padding:9px 10px;border-bottom:1px solid rgba(140,165,185,.07);color:var(--text);vertical-align:top}
.stApp:has(.cc-tips-marker) table.cc-hist tbody tr:hover{background:rgba(140,165,185,.05)}
.stApp:has(.cc-tips-marker) table.cc-hist td.num{font-family:'IBM Plex Mono',monospace;text-align:right;white-space:nowrap}
.stApp:has(.cc-tips-marker) table.cc-hist td.dt{font-family:'IBM Plex Mono',monospace;color:var(--muted);white-space:nowrap}
.stApp:has(.cc-tips-marker) table.cc-hist .meta{font-size:11px;color:var(--muted);margin-top:3px;font-family:'IBM Plex Mono',monospace;letter-spacing:.04em}
.stApp:has(.cc-tips-marker) table.cc-hist .pos{color:var(--emerald);font-weight:600}
.stApp:has(.cc-tips-marker) table.cc-hist .neg{color:#ef7a6d;font-weight:600}
.stApp:has(.cc-tips-marker) table.cc-hist .star{color:var(--gold);text-align:center}
/* add multi (primary emerald) + manual link */
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-addmulti-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-addmulti-marker)) button{
  background:var(--emerald) !important;color:#0a1017 !important;border:none !important;
  font-family:'IBM Plex Mono',monospace !important;text-transform:uppercase !important;letter-spacing:.1em !important;font-weight:700 !important}
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-manuallink-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-manuallink-marker)) button{
  background:transparent !important;border:none !important;color:var(--muted) !important;box-shadow:none !important;
  font-family:'IBM Plex Mono',monospace !important;text-transform:uppercase !important;letter-spacing:.1em !important;font-weight:600 !important}
.stApp:has(.cc-tips-marker) div[data-testid="stVerticalBlock"]:has(.cc-manuallink-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-manuallink-marker)) button:hover{
  color:var(--text) !important;text-decoration:underline !important}
/* disclosure expanders (Settled / Pending Multis) — flush, hairline top rule.
   Scoped to expanders that directly contain their marker, so nested add-props
   expanders elsewhere keep their box. */
.stApp:has(.cc-tips-marker) [data-testid="stExpander"]:has(.cc-disc-marker){
  background:transparent !important;border:none !important;border-top:1px solid var(--line) !important;border-radius:0 !important;box-shadow:none !important}
/* fixtures — flush list, hairline rules, no card */
.stApp:has(.cc-tips-marker) [data-testid="stExpander"]:has(.cc-fixtures-marker){
  background:transparent !important;border:none !important;border-top:1px solid var(--line) !important;border-radius:0 !important;box-shadow:none !important}
.stApp:has(.cc-tips-marker) .cc-empty{font-size:13px;color:var(--muted);padding:10px 0}
</style>
""", unsafe_allow_html=True)

    # ── Auth gate ─────────────────────────────────────────────────────────────
    editable = st.session_state.get('_cc_authed', False)
    # Edit-lock password comes from secrets. FAIL CLOSED: if the secret is
    # missing (or there is no secrets file), _correct_pw stays None so no
    # entered password can ever match — the panel stays read-only, no crash.
    try:
        _correct_pw = st.secrets["TIPS_EDIT_PASSWORD"]
    except Exception:
        _correct_pw = None

    title_col, lock_col = st.columns([6, 1])
    with title_col:
        st.markdown(
            '<div class="cc-title">Cha Ching Tips</div>'
            '<div class="cc-sub">Upcoming fixtures · Player prop markets · Cha Ching checklist</div>',
            unsafe_allow_html=True,
        )
    with lock_col:
        st.markdown('<span class="cc-lock-marker" style="display:none"></span>'
                    '<div style="height:6px"></div>', unsafe_allow_html=True)
        if editable:
            if st.button('Lock', key='_cc_lock', use_container_width=True):
                st.session_state['_cc_authed'] = False
                st.rerun()
        else:
            if st.button('Edit', key='_cc_unlock_btn', use_container_width=True):
                st.session_state['_cc_pw_open'] = True

    if st.session_state.get('_cc_pw_open') and not editable:
        pw_col, _ = st.columns([2, 5])
        with pw_col:
            with st.form('_cc_pw_form', clear_on_submit=True):
                pw = st.text_input('Password', type='password', label_visibility='collapsed',
                                   placeholder='Enter password...')
                if st.form_submit_button('Unlock', use_container_width=True):
                    # The None check is load-bearing, not belt-and-braces:
                    # str(None) == 'None', so without it, typing "None" would
                    # unlock the panel whenever the secret is missing.
                    if _correct_pw is not None and hmac.compare_digest(
                            str(pw), str(_correct_pw)):
                        st.session_state['_cc_authed'] = True
                        st.session_state['_cc_pw_open'] = False
                        st.rerun()
                    else:
                        st.error('Incorrect password')

    # ── Load fixtures + tips once (Pending Tips renders up top; Live/Settled and
    #    Upcoming Games render at the bottom from the same data) ────────────────
    with st.spinner("Loading fixtures..."):
        fixtures = _fetch_fixtures()
    props_df = _load_props()
    _now_utc = pd.Timestamp.now(tz='UTC')
    upcoming_keys = set()
    for _, _g in fixtures.iterrows():
        _dp = _g.get('date_parsed')
        if pd.notna(_dp) and pd.Timestamp(_dp) > _now_utc:
            upcoming_keys.add(_game_key(_g))
    tips_df = _load_tips()
    if 'result' not in tips_df.columns:
        tips_df['result'] = ''
    flagged_all = tips_df[tips_df['is_flagged'] == True].copy() if not tips_df.empty else pd.DataFrame()
    if not flagged_all.empty:
        flagged_all['result'] = flagged_all['result'].fillna('')
        flagged_all = flagged_all.drop_duplicates(subset=['tip_id'])

    # Tip-card renderer (used by Pending Multis up top + Live/Unsettled below)
    def _render_tip_card(tip, label_badge: str = 'LIVE', badge_class: str = 'live-badge is-live'):
        tip_id    = str(tip['tip_id'])
        player    = str(tip.get('player', ''))
        gkey      = str(tip.get('game_key', ''))
        mtype     = str(tip.get('market_type', ''))
        line_raw  = pd.to_numeric(tip.get('line', ''), errors='coerce')
        odds_raw  = pd.to_numeric(tip.get('odds', ''), errors='coerce')
        stake_raw = pd.to_numeric(tip.get('stake', ''), errors='coerce')
        bookie    = str(tip.get('bookmaker', '') or '')
        bet_parts = []
        if not pd.isna(line_raw):
            bet_parts.append(f"O/U {line_raw:.1f}")
        if not pd.isna(odds_raw) and odds_raw > 1:
            bet_parts.append(f"@ {odds_raw:.2f}")
        if bookie:
            bet_parts.append(f"({bookie})")
        if not pd.isna(stake_raw) and stake_raw > 0:
            bet_parts.append(f"— {stake_raw:.2f}u")
        bet_detail = '&nbsp;&nbsp;'.join(bet_parts)
        card_col, btn_col = st.columns([3, 2])
        with card_col:
            st.markdown(
                f'<div style="background:var(--surface);border:1px solid var(--line);border-radius:10px;'
                f'padding:12px 16px;margin-bottom:4px">'
                f'<div style="display:flex;align-items:center;gap:0;margin-bottom:4px">'
                f'<span style="font-weight:700;color:var(--text);font-size:14px">{player}</span>'
                f'<span class="{badge_class}">{label_badge}</span></div>'
                f'<div style="font-size:12px;color:var(--muted);margin-bottom:2px">{gkey}'
                f'&nbsp;&nbsp;·&nbsp;&nbsp;{mtype}</div>'
                + (f'<div style="font-size:12px;font-family:DM Mono,monospace;color:#f0b429">'
                   f'{bet_detail}</div>' if bet_detail else '')
                + f'</div>',
                unsafe_allow_html=True,
            )
        if editable:
            with btn_col:
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button('✅ Win', key=f'tip_win_{tip_id}', use_container_width=True):
                        _save_tip_result(tip_id, 'Win')
                        st.toast('Tip settled as Win — synced to Bet History', icon='✅')
                        st.rerun()
                with b2:
                    if st.button('❌ Loss', key=f'tip_loss_{tip_id}', use_container_width=True):
                        _save_tip_result(tip_id, 'Loss')
                        st.toast('Tip settled as Loss — synced to Bet History', icon='❌')
                        st.rerun()
                with b3:
                    if st.button('↩️ Void', key=f'tip_void_{tip_id}', use_container_width=True):
                        _save_tip_result(tip_id, 'Void/Refund')
                        st.toast('Tip voided — synced to Bet History', icon='↩️')
                        st.rerun()
                with b4:
                    if st.button('🗑', key=f'tip_del_{tip_id}', use_container_width=True,
                                 help='Delete this tip'):
                        _delete_tip(tip_id)
                        st.toast('Tip deleted', icon='🗑')
                        st.rerun()

    # ── Pending Tips (upcoming games) — surfaced at the very top ───────────────
    pending_tips = flagged_all[
        flagged_all['game_key'].isin(upcoming_keys) &
        (flagged_all['market_type'].fillna('') != 'Multi')
    ] if not flagged_all.empty else pd.DataFrame()
    if not pending_tips.empty:
        st.markdown('<div class="section-header">Pending Tips</div>', unsafe_allow_html=True)
        for _, tip in pending_tips.iterrows():
            tip_id    = str(tip['tip_id'])
            player    = str(tip.get('player', ''))
            gkey      = str(tip.get('game_key', ''))
            mtype     = str(tip.get('market_type', ''))
            line_raw  = pd.to_numeric(tip.get('line', ''), errors='coerce')
            odds_raw  = pd.to_numeric(tip.get('odds', ''), errors='coerce')
            stake_raw = pd.to_numeric(tip.get('stake', ''), errors='coerce')
            bookie    = str(tip.get('bookmaker', '') or '')
            bet_parts = []
            if not pd.isna(line_raw):
                bet_parts.append(f"O/U {line_raw:.1f}")
            if not pd.isna(odds_raw) and odds_raw > 1:
                bet_parts.append(f"@ {odds_raw:.2f}")
            if bookie:
                bet_parts.append(f"({bookie})")
            if not pd.isna(stake_raw) and stake_raw > 0:
                bet_parts.append(f"— {stake_raw:.2f}u")
            bet_detail = '&nbsp;&nbsp;'.join(bet_parts)
            card_col, btn_col = st.columns([3, 1])
            with card_col:
                st.markdown(
                    f'<div style="background:var(--surface);border:1px solid var(--line);border-radius:10px;'
                    f'padding:12px 16px;margin-bottom:4px">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                    f'<span style="font-weight:700;color:var(--text);font-size:14px">{player}</span>'
                    f'<span style="font-size:10px;font-weight:700;background:{C["gold"]}22;'
                    f'color:{C["gold"]};border:1px solid {C["gold"]}55;border-radius:4px;'
                    f'padding:1px 6px;letter-spacing:0.5px">PENDING</span></div>'
                    f'<div style="font-size:12px;color:var(--muted);margin-bottom:2px">'
                    f'{gkey}&nbsp;&nbsp;·&nbsp;&nbsp;{mtype}</div>'
                    + (f'<div style="font-size:12px;font-family:DM Mono,monospace;color:{C["gold"]}">'
                       f'{bet_detail}</div>' if bet_detail else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )
            if editable:
                with btn_col:
                    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
                    if st.button('🗑 Delete', key=f'tip_del_{tip_id}', use_container_width=True):
                        _delete_tip(tip_id)
                        st.toast('Tip deleted', icon='🗑')
                        st.rerun()

    # ── Pending Multis — surfaced at the top alongside Pending Tips ────────────
    pending_multis = tips_df[
        (tips_df['market_type'] == 'Multi') &
        (tips_df['result'].fillna('') == '')
    ].drop_duplicates(subset=['tip_id']).copy() if not tips_df.empty else pd.DataFrame()
    if not pending_multis.empty:
        st.markdown('<div class="section-header">Pending Multis</div>', unsafe_allow_html=True)
        for _, tip in pending_multis.iterrows():
            _render_tip_card(tip, label_badge='🎯 MULTI', badge_class='live-badge')

    # ── Historical CC bets ────────────────────────────────────────────────────
    cc_bets = _load_bets()
    cc_bets = cc_bets[cc_bets['is_cha_ching'] == True].copy()

    @st.fragment
    def _cc_history_section(cc_bets):
        st.markdown('<div class="section-header">Cha Ching Bet History</div>', unsafe_allow_html=True)

        # Filters (flush, single inline row) — scoped via .cc-filters-marker
        with st.container():
            st.markdown('<span class="cc-filters-marker" style="display:none"></span>',
                        unsafe_allow_html=True)
            cf1, cf2, cf3, cf4 = st.columns(4)
            with cf1:
                cc_markets = ['All'] + sorted(cc_bets['market_type'].dropna().unique().tolist())
                cc_mkt = st.selectbox("Market", cc_markets, index=0, key='cc_hist_mkt')
            with cf2:
                cc_books = ['All'] + sorted(cc_bets['bookmaker'].dropna().unique().tolist())
                cc_bk = st.selectbox("Bookmaker", cc_books, index=0, key='cc_hist_bk')
            with cf3:
                cc_res = st.selectbox("Result", ['All'] + RESULTS, index=0, key='cc_hist_res')
            with cf4:
                if pd.notna(cc_bets['date']).any():
                    cc_min_d = cc_bets['date'].dropna().min().date()
                    cc_max_d = cc_bets['date'].dropna().max().date()
                    cc_dr = st.date_input("Date range", (cc_min_d, cc_max_d))
                else:
                    cc_dr = None

        cc_filt = cc_bets.copy()
        if cc_mkt != 'All':
            cc_filt = cc_filt[cc_filt['market_type'] == cc_mkt]
        if cc_bk != 'All':
            cc_filt = cc_filt[cc_filt['bookmaker'] == cc_bk]
        if cc_res != 'All':
            cc_filt = cc_filt[cc_filt['result'] == cc_res]
        if cc_dr and isinstance(cc_dr, (tuple, list)) and len(cc_dr) == 2:
            try:
                cc_filt = cc_filt[
                    (cc_filt['date'].dt.date >= cc_dr[0]) &
                    (cc_filt['date'].dt.date <= cc_dr[1])
                ]
            except Exception:
                pass
        cc_filt = cc_filt.sort_values('date', ascending=False).reset_index(drop=True)

        # ── Record strip (flush, no cards) — Pending dropped; only P&L / ROI tinted ──
        fs = _betting_stats(cc_filt)
        if fs:
            _pl = fs.get('total_pl', 0.0)
            _roi = fs.get('roi', 0.0)
            _pl_cls = 'pos' if _pl > 0 else ('neg' if _pl < 0 else '')
            _roi_cls = 'pos' if _roi > 0 else ('neg' if _roi < 0 else '')
            _rec_cells = [
                ('', f"{fs.get('total_bets', 0)}", 'CC Bets'),
                (_pl_cls, f"{_pl:+.2f}u", 'P&L'),
                (_roi_cls, f"{_roi:+.1f}%", 'ROI'),
                ('', f"{fs.get('hit_rate', 0.0):.1f}%", 'Hit Rate'),
                ('', f"{fs.get('wins', 0)}–{fs.get('losses', 0)}", 'Record'),
            ]
            st.markdown(
                '<div class="cc-rec-strip">' + ''.join(
                    f'<div class="cc-rec-cell"><div class="cc-rec-num {c}">{v}</div>'
                    f'<div class="cc-rec-lbl">{l}</div></div>'
                    for c, v, l in _rec_cells
                ) + '</div>',
                unsafe_allow_html=True,
            )

        # ── Bet history table (flush HTML; Market folded under Match; P&L only colour) ──
        if not cc_filt.empty:
            _cc_total = len(cc_filt)
            _cc_show_all = st.session_state.get('_cc_hist_show_all', False)
            _view = cc_filt if _cc_show_all else cc_filt.head(20)  # latest 20 by default
            _rows_html = ''
            for _, r in _view.iterrows():
                _dt = r['date'].strftime('%d %b %Y') if pd.notna(r.get('date')) else '—'
                _match = str(r.get('match', '') or '')
                _market = str(r.get('market_type', '') or '')
                _sel = str(r.get('selection', '') or '')
                _book = str(r.get('bookmaker', '') or '')
                _odds = r.get('odds', None)
                _odds_s = f"{float(_odds):.2f}" if pd.notna(_odds) else '—'
                _stake = r.get('stake', None)
                _stake_s = f"{float(_stake):.2f}" if pd.notna(_stake) else '—'
                _res = str(r.get('result', '') or '')
                _res_cls = 'pos' if _res == 'Win' else ('neg' if _res == 'Loss' else '')
                _res_s = f'<span class="{_res_cls}">{_res.upper()}</span>' if _res else '—'
                _pl_v = r.get('profit_loss', None)
                if pd.notna(_pl_v):
                    _plc = 'pos' if float(_pl_v) > 0 else ('neg' if float(_pl_v) < 0 else '')
                    _pl_s = f'<span class="{_plc}">{float(_pl_v):+.2f}</span>'
                else:
                    _pl_s = '—'
                _meta = f'<div class="meta">{_market}</div>' if _market else ''
                _rows_html += (
                    '<tr>'
                    f'<td class="dt">{_dt}</td>'
                    f'<td>{_match}{_meta}</td>'
                    f'<td>{_sel}</td>'
                    f'<td>{_book}</td>'
                    f'<td class="num">{_odds_s}</td>'
                    f'<td class="num">{_stake_s}</td>'
                    f'<td class="num">{_res_s}</td>'
                    f'<td class="num">{_pl_s}</td>'
                    '</tr>'
                )
            st.markdown(
                '<table class="cc-hist"><thead><tr>'
                '<th>Date</th><th>Match</th><th>Selection</th><th>Bookmaker</th>'
                '<th class="r">Odds</th><th class="r">Stake</th>'
                '<th class="r">Result</th><th class="r">P&amp;L</th>'
                '</tr></thead><tbody>' + _rows_html + '</tbody></table>',
                unsafe_allow_html=True,
            )
            if _cc_total > 20:
                _mt1, _ = st.columns([2, 5])
                with _mt1:
                    st.markdown('<span class="cc-manuallink-marker" style="display:none"></span>',
                                unsafe_allow_html=True)
                    _more_lbl = "Show latest 20" if _cc_show_all else f"Show all ({_cc_total})"
                    if st.button(_more_lbl, key='_cc_hist_toggle', use_container_width=True):
                        st.session_state['_cc_hist_show_all'] = not _cc_show_all
                        st.rerun()
        else:
            st.markdown('<div class="cc-empty">No Cha Ching bets match the current filters.</div>',
                        unsafe_allow_html=True)

        st.divider()

    if not cc_bets.empty:
        _cc_history_section(cc_bets)

    # ── Flagged-tips banner (upcoming only); fixtures/tips already loaded above ─
    flagged  = tips_df[
        (tips_df['is_flagged'] == True) &
        (tips_df['game_key'].isin(upcoming_keys))
    ] if not tips_df.empty else pd.DataFrame()
    if not flagged.empty:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#f0b429,#f5c542);'
            f'border-radius:8px;padding:12px 16px;margin-bottom:16px">'
            f'<span style="font-weight:800;font-size:13px;color:#0a1017">CHA CHING TIPS FLAGGED: {len(flagged)}</span>'
            f'<span style="font-size:12px;color:#3a2d08;margin-left:8px">'
            + ' &nbsp;·&nbsp; '.join(f"{r['player']} ({r['market_type']})" for _, r in flagged.head(4).iterrows())
            + ('…' if len(flagged) > 4 else '')
            + f'</span></div>',
            unsafe_allow_html=True,
        )

    # ── Add Multi Tip (primary) + Add game manually (text link) ───────────────
    if editable:
        _am1, _am2, _ = st.columns([2, 2, 3])
        with _am1:
            st.markdown('<span class="cc-addmulti-marker" style="display:none"></span>',
                        unsafe_allow_html=True)
            if st.button("+ Add Multi Tip", use_container_width=True):
                _add_multi_dialog()
        with _am2:
            if not fixtures.empty:
                st.markdown('<span class="cc-manuallink-marker" style="display:none"></span>',
                            unsafe_allow_html=True)
                if st.button("+ Add game manually", use_container_width=True, key='_cc_manual_link'):
                    st.session_state['_cc_manual_add_open'] = \
                        not st.session_state.get('_cc_manual_add_open', False)

    # ── Live & Settled flagged tips (flagged_all already computed up top) ──────
    if flagged_all.empty:
        st.caption("No Cha Ching tips flagged yet — use the checklist in Upcoming Games below to create one.")
    else:
        all_live     = flagged_all[~flagged_all['game_key'].isin(upcoming_keys) & (flagged_all['result'] == '') & (flagged_all['market_type'].fillna('') != 'Multi')]
        settled_tips = flagged_all[~flagged_all['game_key'].isin(upcoming_keys) & (flagged_all['result'] != '')]

        # Split unsettled into recent-live vs stale (>48h since created_at)
        _cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(hours=48)
        _ages   = pd.to_datetime(all_live['created_at'].fillna(''), errors='coerce', utc=True)
        live_tips      = all_live[_ages.isna() | (_ages >= _cutoff)]
        unsettled_tips = all_live[_ages.notna() & (_ages < _cutoff)]

        # ── Pending Tips + Pending Multis render at the very top (see above) ────

        # ── Live ──────────────────────────────────────────────────────────────
        if not live_tips.empty:
            st.markdown('<div class="section-header">Live Tips</div>', unsafe_allow_html=True)
            for _, tip in live_tips.iterrows():
                _render_tip_card(tip)

        # ── Unsettled (stale — >48h, no result) ───────────────────────────────
        if not unsettled_tips.empty:
            with st.expander(f"Unsettled Tips ({len(unsettled_tips)}) — awaiting result", expanded=False):
                st.markdown('<span class="cc-disc-marker" style="display:none"></span>', unsafe_allow_html=True)
                for _, tip in unsettled_tips.iterrows():
                    _render_tip_card(tip, label_badge='⏳ UNSETTLED', badge_class='live-badge')

        # ── Settled ───────────────────────────────────────────────────────────
        if not settled_tips.empty:
            with st.expander(f"Settled Tips ({len(settled_tips)})", expanded=False):
                st.markdown('<span class="cc-disc-marker" style="display:none"></span>', unsafe_allow_html=True)
                result_styles = {
                    'Win':         ('✅ Win',  '#34d399', 'rgba(52,211,153,0.12)'),
                    'Loss':        ('❌ Loss', '#ef7a6d', 'rgba(239,122,109,0.12)'),
                    'Void/Refund': ('↩️ Void', '#7e8c99', 'rgba(74,90,106,0.15)'),
                }
                for _, tip in settled_tips.sort_values('game_key').iterrows():
                    tip_id = str(tip['tip_id'])
                    player = str(tip.get('player', ''))
                    gkey   = str(tip.get('game_key', ''))
                    mtype  = str(tip.get('market_type', ''))
                    result = str(tip.get('result', ''))
                    pl_raw = pd.to_numeric(tip.get('profit_loss', ''), errors='coerce')
                    pl_str = f" &nbsp;{pl_raw:+.2f}u" if not pd.isna(pl_raw) and pl_raw != 0 else ''
                    label, color, bg = result_styles.get(result, (result, '#7e8c99', 'rgba(74,90,106,0.15)'))
                    st.markdown(
                        f'<div style="background:{bg};border:1px solid {color}33;border-radius:10px;'
                        f'padding:10px 16px;margin-bottom:6px;display:flex;align-items:center;'
                        f'justify-content:space-between">'
                        f'<div><span style="font-weight:700;color:var(--text)">{player}</span>'
                        f'<span style="font-size:12px;color:var(--muted);margin-left:10px">'
                        f'{gkey} &nbsp;·&nbsp; {mtype}</span></div>'
                        f'<span style="font-weight:800;color:{color};font-size:13px">'
                        f'{label}{pl_str}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if editable:
                        sc1, sc2 = st.columns([2, 1])
                        with sc1:
                            if st.button('Clear result', key=f'tip_clear_{tip_id}',
                                         type='secondary', use_container_width=True):
                                _save_tip_result(tip_id, '')
                                st.rerun()
                        with sc2:
                            if st.button('🗑 Delete', key=f'tip_del_{tip_id}',
                                         use_container_width=True):
                                _delete_tip(tip_id)
                                st.toast('Tip deleted', icon='🗑')
                                st.rerun()

        # ── Pending Multis render at the very top (see above) ───────────────────

    # ── Upcoming games ────────────────────────────────────────────────────────
    if fixtures.empty:
        st.markdown(
            '<div class="section-header">Upcoming · Next 7 days</div>'
            '<div class="cc-empty">No upcoming fixtures.</div>',
            unsafe_allow_html=True,
        )
        st.caption("Squiggle API: https://api.squiggle.com.au")
        _render_manual_props()
        return

    # ── Manual game entry — edit mode only ───────────────────────────────────
    if '_manual_games' not in st.session_state:
        st.session_state['_manual_games'] = []
    if '_mg_n' not in st.session_state:
        st.session_state['_mg_n'] = 0

    if editable and st.session_state.get('_cc_manual_add_open'):
        st.markdown('<div class="section-header">Add Game Manually</div>', unsafe_allow_html=True)
        _n = st.session_state['_mg_n']
        mg1, mg2, mg3, mg4 = st.columns([1.5, 2, 2, 1])
        with mg1:
            mg_round = st.text_input("Round", placeholder="Round 11", key=f'mg_round_{_n}')
        with mg2:
            mg_home  = st.text_input("Home team", placeholder="Richmond", key=f'mg_home_{_n}')
        with mg3:
            mg_away  = st.text_input("Away team", placeholder="Essendon", key=f'mg_away_{_n}')
        with mg4:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Add", key='mg_add', use_container_width=True):
                r = mg_round.strip()
                h = mg_home.strip()
                a = mg_away.strip()
                if r and h and a:
                    new_gkey = f"{r} {h} v {a}"
                    existing = [g['gkey'] for g in st.session_state['_manual_games']]
                    if new_gkey not in existing:
                        st.session_state['_manual_games'].append({'roundname': r, 'hteam': h, 'ateam': a, 'gkey': new_gkey})
                    st.session_state['_mg_n'] += 1
                    st.rerun()
                else:
                    st.warning("Fill in all three fields.")

    # Render manually added games
    if st.session_state['_manual_games']:
        st.markdown('<div class="section-header">Manual Games</div>', unsafe_allow_html=True)
        for mg in st.session_state['_manual_games']:
            mgkey = mg['gkey']
            col_exp, col_del = st.columns([9, 1])
            with col_exp:
                with st.expander(f"**{mgkey}**", expanded=True):
                    tab_disp, tab_goals, tab_fpts = st.tabs(["Disposals", "Goals", "Fantasy Points"])
                    for tab, mtype in [(tab_disp, "Disposals O/U"), (tab_goals, "Goals O/U"), (tab_fpts, "Fantasy Points O/U")]:
                        with tab:
                            _render_market_tab(mgkey, mtype, props_df, tips_df, editable=editable)
            with col_del:
                if editable:
                    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                    if st.button("✕", key=f'mg_del_{mgkey}', help="Remove this game"):
                        st.session_state['_manual_games'] = [g for g in st.session_state['_manual_games'] if g['gkey'] != mgkey]
                        st.rerun()

    st.markdown('<div class="section-header">Upcoming · Next 7 days</div>',
                unsafe_allow_html=True)

    for _, game in fixtures.iterrows():
        gkey  = _game_key(game)
        rname = str(game.get('roundname', '') or '')
        home  = str(game.get('hteam', '?'))
        away  = str(game.get('ateam', '?'))
        _dt   = game.get('date_parsed')
        _kick = ''
        if pd.notna(_dt):
            try:
                _kick = pd.Timestamp(_dt).strftime('%a %d %b · %H:%M')
            except Exception:
                _kick = ''
        # NOTE: Streamlit expander summaries render markdown only (no HTML/colour/
        # flex), so the emerald round chip + right-aligned kickoff can't live in the
        # label; the round is emphasised in mono-ish bold and the time runs inline.
        _fx_label = (f"**{rname}**  ·  " if rname else "") + f"{home} v {away}" + \
                    (f"  ·  {_kick}" if _kick else "")

        with st.expander(_fx_label):
            st.markdown('<span class="cc-fixtures-marker" style="display:none"></span>',
                        unsafe_allow_html=True)
            tab_disp, tab_goals, tab_fpts = st.tabs(["Disposals", "Goals", "Fantasy Points"])

            for tab, mtype in [(tab_disp, "Disposals O/U"), (tab_goals, "Goals O/U"), (tab_fpts, "Fantasy Points O/U")]:
                with tab:
                    _render_market_tab(gkey, mtype, props_df, tips_df, editable=editable)


def _render_market_tab(game_key: str, market_type: str, props_df: pd.DataFrame,
                       tips_df: pd.DataFrame, editable: bool = True):
    """Render a market tab for a game."""
    game_props = props_df[
        (props_df['game_key'] == game_key) &
        (props_df['market_type'] == market_type)
    ] if not props_df.empty else pd.DataFrame()

    if not game_props.empty:
        # Show existing props
        st.caption(f"Updated: {game_props['updated_at'].max()}")

        stat_col   = STAT_COL_MAP.get(market_type)
        plyr_avgs  = _load_player_avgs() if stat_col else pd.DataFrame()

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

            edge_html = '—'
            if stat_col and not plyr_avgs.empty:
                pmatch = plyr_avgs[plyr_avgs['Player'] == player]
                if not pmatch.empty:
                    avg  = pmatch[stat_col].iloc[0]
                    diff = avg - float(line)
                    clr  = '#34d399' if diff >= 0 else '#ef7a6d'
                    edge_html = (
                        f'<span style="color:var(--muted)">avg {avg:.1f}</span>'
                        f'&nbsp;<span style="color:{clr};font-weight:700">'
                        f'({diff:+.1f})</span>'
                    )

            rows_html += (
                f'<tr>'
                f'<td style="padding:6px 10px;font-weight:600">{player}{cc_html}</td>'
                f'<td style="padding:6px 10px;text-align:center">{line:.1f}</td>'
                f'<td style="padding:6px 10px;text-align:center">{bookie}</td>'
                f'<td style="padding:6px 10px;text-align:center;font-weight:700">{odds:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:center">{impl:.1f}%</td>'
                f'<td style="padding:6px 10px;text-align:center">{edge_html}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f'<thead><tr style="background:#34d399;color:var(--text)">'
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
        # Checklist buttons per player — edit mode only
        if editable:
            player_list = game_props['player'].tolist()
            if player_list:
                st.markdown('<div style="font-size:11px;color:var(--muted);font-weight:600;letter-spacing:0.8px;text-transform:uppercase;margin:8px 0 4px 0">CHECKLIST</div>', unsafe_allow_html=True)
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
                        p_row     = game_props[game_props['player'] == player]
                        p_odds    = float(p_row['odds'].iloc[0]) if not p_row.empty else 0.0
                        p_bookie  = str(p_row['bookmaker'].iloc[0]) if not p_row.empty else ''
                        p_line    = float(p_row['line'].iloc[0]) if not p_row.empty else 0.0
                        if st.button(label, key=f"cl_{game_key}_{market_type}_{player}",
                                     type=btn_type, use_container_width=True):
                            _open_checklist(player, market_type, game_key,
                                            odds=p_odds, bookmaker=p_bookie, line=p_line)

            if (st.session_state.get('_cl_open', False) and
                    st.session_state.get('_cl_game') == game_key and
                    st.session_state.get('_cl_market') == market_type):
                _checklist_dialog()

    else:
        st.caption(f"No {market_type} props loaded for this game.")

    # ── Add / Edit Props — edit mode only ────────────────────────────────────
    if not editable:
        return
    with st.expander(f"Add {market_type} props for this game"):
        with st.form(key=f"add_props_{game_key}_{market_type}"):
            st.markdown(f"**Enter player line and odds for {market_type}**")
            pc1, pc2, pc3, pc4 = st.columns([3, 1.5, 2, 1.5])
            with pc1:
                p_player = st.text_input("Player name", key=f"pp_{game_key}_{market_type}_player")
            with pc2:
                _line_max = 200.0 if market_type == "Fantasy Points O/U" else 99.5
                _line_val = 100.5 if market_type == "Fantasy Points O/U" else 29.5
                p_line = st.number_input("Line", min_value=0.5, max_value=_line_max,
                                         value=_line_val, step=0.5, format='%.1f',
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
    # Midnight Turf flush styles — page-scoped via .tr-page (and the innermost
    # .tr-flush marker on the masthead) so other BH panels stay boxed. Flush the
    # masthead onto #0a1017 and turn the upload row into a flush dashed
    # drop-target with a mono label. No @keyframes here — page needs no motion.
    st.markdown(
        '<style>'
        '.title-bar:has(.tr-flush){background:transparent !important;border:none !important;'
        'box-shadow:none !important;padding:0 !important;}'
        '.stApp:has(.tr-page) [data-testid="stFileUploaderDropzone"]{'
        'background:transparent !important;border:1px dashed var(--line) !important;'
        'box-shadow:none !important;border-radius:0 !important;}'
        '.stApp:has(.tr-page) [data-testid="stFileUploaderDropzoneInstructions"]{'
        "font-family:'IBM Plex Mono',monospace !important;color:var(--muted) !important;"
        'letter-spacing:.04em;}'
        '</style>'
        '<span class="tr-page" style="display:none"></span>'
        '<div class="title-bar"><span class="tr-flush" style="display:none"></span>'
        '<h2 style="color:var(--text);margin:0">Trends &amp; Analysis</h2>'
        '<p style="color:var(--muted);margin:4px 0 0 0">'
        'Hit rate, ROI and P&L across markets, bookmakers and odds ranges</p></div>',
        unsafe_allow_html=True,
    )

    # ── My Spreadsheet ─────────────────────────────────────────────────────
    st.markdown('<div class="trend-header">My Spreadsheet</div>', unsafe_allow_html=True)
    _imported_check = _load_user_import()
    if _imported_check is not None:
        _strip_hdr, _strip_btn = st.columns([5, 1])
        with _strip_hdr:
            st.markdown(
                f'<div style="font-size:12px;color:var(--muted);padding:6px 0">'
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
    with st.expander("Upload your own betting spreadsheet (.csv or .xlsx)", expanded=(_imported_check is not None)):
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
                f'<div style="font-size:12px;color:var(--muted);margin:4px 0 10px 0">'
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

    # Midnight Turf colour-encoding tokens (page-local; match the shared theme).
    EMERALD, RED, GOLD = '#34d399', '#ef7a6d', '#f0b429'
    BREAKEVEN_HIT = 50.0  # hit-rate breakeven for colour-by-performance
    _empty = ('<div style="color:var(--muted);font-size:13px;'
              'font-family:\'IBM Plex Mono\',monospace;padding:10px 0">No data yet.</div>')

    # ── ROI by market — the page's primary colour-encoded element ───────────
    # One diverging horizontal bar per market (best at top); colour encodes sign.
    st.markdown('<div class="trend-header">ROI by Market</div>', unsafe_allow_html=True)
    if {'market_type', 'stake', 'profit_loss'}.issubset(bets.columns) and not bets.empty:
        mkt_roi = bets.groupby('market_type').apply(
            lambda g: pd.Series({
                'roi': g['profit_loss'].sum() / g['stake'].sum() * 100 if g['stake'].sum() > 0 else 0
            })
        ).reset_index()
        mkt_roi = mkt_roi[mkt_roi['market_type'].astype(str).str.strip() != '']
    else:
        mkt_roi = pd.DataFrame(columns=['market_type', 'roi'])

    if not mkt_roi.empty:
        # Ascending sort → highest ROI lands at the TOP of the horizontal axis.
        mkt_roi = mkt_roi.sort_values('roi', ascending=True)
        _mk = mkt_roi['market_type'].astype(str).tolist()
        _rv = mkt_roi['roi'].tolist()
        fig = go.Figure(go.Bar(
            x=_rv, y=_mk, orientation='h',
            marker_color=[EMERALD if v >= 0 else RED for v in _rv],
            text=[f'{v:+.1f}%' for v in _rv],
            textposition='outside',
            textfont=dict(family='IBM Plex Mono, monospace', size=12, color=C['text']),
            cliponaxis=False,
            hovertemplate='%{y}: %{x:+.1f}%<extra></extra>',
        ))
        fig.add_vline(x=0, line_width=1, line_color=C['border'])
        fig.update_layout(height=max(220, 44 * len(_rv) + 60), showlegend=False)
        fig = apply_chart_theme(fig)
        fig.update_layout(margin=dict(l=10, r=64, t=8, b=24))
        fig.update_yaxes(automargin=True)
        fig.update_xaxes(automargin=True)
        st.plotly_chart(fig, use_container_width=True, key='tr_mkt_roi', config=PLOTLY_TOUCH_CONFIG)
    else:
        st.markdown(_empty, unsafe_allow_html=True)

    # ── Bookmaker hit rate + ROI by odds range (quiet two-up) ──────────────
    st.markdown('<div class="trend-header">Bookmaker &amp; Odds Performance</div>',
                unsafe_allow_html=True)
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        if 'bookmaker' in settled.columns and not settled.empty:
            # Normalise casing for grouping only (merges e.g. PointsBet/Pointsbet);
            # canonicalise against BOOKMAKERS so display names stay branded. The
            # stored data is untouched — this is render-local.
            _bk_canon = {b.lower(): b for b in BOOKMAKERS}
            bk = settled.copy()
            bk['_bk'] = bk['bookmaker'].astype(str).str.strip().apply(
                lambda x: _bk_canon.get(x.lower(), x.title()))
            bk_grp = bk.groupby('_bk').agg(win=('win', 'sum'),
                                           total=('win', 'count')).reset_index()
            bk_grp['hit_rate'] = bk_grp['win'] / bk_grp['total'] * 100
            bk_grp = bk_grp.sort_values('hit_rate', ascending=True)
        else:
            bk_grp = pd.DataFrame(columns=['_bk', 'hit_rate'])
        if not bk_grp.empty:
            fig = _bar_chart(
                bk_grp['_bk'].tolist(), bk_grp['hit_rate'].tolist(),
                'Hit Rate by Bookmaker (%)',
                color=[EMERALD if h >= BREAKEVEN_HIT else RED for h in bk_grp['hit_rate']],
            )
            fig.update_layout(height=260)
            fig = apply_chart_theme(fig)
            st.plotly_chart(fig, use_container_width=True, key='tr_bk_hit', config=PLOTLY_TOUCH_CONFIG)
        else:
            st.markdown(_empty, unsafe_allow_html=True)

    with r2c2:
        def _odds_band(o):
            if o < 1.5:   return '<1.50'
            if o < 2.0:   return '1.50-2.00'
            if o < 3.0:   return '2.00-3.00'
            if o < 5.0:   return '3.00-5.00'
            return '5.00+'
        if {'odds', 'stake', 'profit_loss'}.issubset(bets.columns) and not bets.empty:
            bets_o = bets.copy()
            bets_o['odds_band'] = bets_o['odds'].apply(_odds_band)
            ods_roi = bets_o.groupby('odds_band').apply(
                lambda g: pd.Series({'roi': g['profit_loss'].sum() / g['stake'].sum() * 100
                                     if g['stake'].sum() > 0 else 0})
            ).reset_index()
            order = ['<1.50', '1.50-2.00', '2.00-3.00', '3.00-5.00', '5.00+']
            ods_roi['odds_band'] = pd.Categorical(ods_roi['odds_band'], categories=order, ordered=True)
            ods_roi = ods_roi.sort_values('odds_band')
        else:
            ods_roi = pd.DataFrame(columns=['odds_band', 'roi'])
        if not ods_roi.empty:
            fig = _bar_chart(
                ods_roi['odds_band'].astype(str).tolist(), ods_roi['roi'].tolist(),
                'ROI by Odds Range (%)',
                color=[EMERALD if v >= 0 else RED for v in ods_roi['roi']],
            )
            fig.update_layout(height=260)
            fig = apply_chart_theme(fig)
            st.plotly_chart(fig, use_container_width=True, key='tr_ods_roi', config=PLOTLY_TOUCH_CONFIG)
        else:
            st.markdown(_empty, unsafe_allow_html=True)

    # ── Monthly P&L (time-shape no table carries; recoloured by sign) ──────
    st.markdown('<div class="trend-header">Monthly P&amp;L</div>', unsafe_allow_html=True)
    if {'date', 'profit_loss'}.issubset(bets.columns) and not bets['date'].dropna().empty:
        bets_m = bets.dropna(subset=['date']).copy()
        bets_m['month'] = bets_m['date'].dt.to_period('M').astype(str)
        monthly = bets_m.groupby('month')['profit_loss'].sum().reset_index()
        monthly = monthly.sort_values('month')
    else:
        monthly = pd.DataFrame(columns=['month', 'profit_loss'])
    if not monthly.empty:
        fig = _bar_chart(
            monthly['month'].tolist(), monthly['profit_loss'].tolist(),
            'Monthly P&L (units)',
            color=[EMERALD if v >= 0 else RED for v in monthly['profit_loss']],
        )
        fig.update_layout(height=300)
        fig = apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key='tr_monthly', config=PLOTLY_TOUCH_CONFIG)
    else:
        st.markdown(_empty, unsafe_allow_html=True)

    # ── Cha Ching vs non-CC — only when at least one non-CC bet exists ─────
    if 'is_cha_ching' in bets.columns and bool((bets['is_cha_ching'] != True).any()):
        st.markdown('<div class="trend-header">Cha Ching Tips vs All Bets</div>',
                    unsafe_allow_html=True)
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
            fig = _bar_chart(
                ['Cha Ching', 'Non-CC'], [cc_hit, non_hit],
                'Hit Rate Comparison (%)',
                color=[GOLD, EMERALD if non_hit >= BREAKEVEN_HIT else RED],
            )
            fig.update_layout(height=280)
            fig = apply_chart_theme(fig)
            st.plotly_chart(fig, use_container_width=True, key='tr_cc_hit', config=PLOTLY_TOUCH_CONFIG)
        with rc2:
            fig = _bar_chart(
                ['Cha Ching', 'Non-CC'], [cc_roi, non_roi],
                'ROI Comparison (%)',
                color=[GOLD if cc_roi >= 0 else RED, EMERALD if non_roi >= 0 else RED],
            )
            fig.update_layout(height=280)
            fig = apply_chart_theme(fig)
            st.plotly_chart(fig, use_container_width=True, key='tr_cc_roi', config=PLOTLY_TOUCH_CONFIG)


# ── Public dispatch ────────────────────────────────────────────────────────────

def render_page(page: str):
    """Called from dashboard.py for each Betting Hub page.

    The gate in dashboard.py already st.stop()s a non-admin request long before
    this runs. This is a backstop so no future caller can route around it: every
    BH page is gated here too, regardless of how it was reached. It reads the
    same session key the gate sets — there is deliberately only one.

    cc_is_admin, not user_auth.is_admin(): this module talks to Supabase with the
    service_role key, user_auth talks with the anon key and a per-user JWT, and
    they are kept apart so nobody reaches for the wrong client. The session key
    dashboard writes once per run is the bridge — same shape this backstop always
    had, when the key was bh_authed.
    """
    if not st.session_state.get("cc_is_admin"):
        st.stop()
    inject_global_css()
    _ensure_dirs()
    if not _supabase_available():
        st.caption("⚠ Supabase not connected — showing empty data")
    if page == 'Performance':
        render_bh_dashboard()
    elif page == 'Bet Tracker':
        render_bet_tracker()
    elif page == 'Cha Ching Tips':
        render_cha_ching_tips()
    elif page == 'Trends & Analysis':
        render_trends_analysis()
