"""
theme.py — Cha Ching shared design tokens

inject_global_theme() is called from both dashboard.py and
betting_hub.render_page() so every page (Brownlow and Betting Hub)
draws from the same :root token set, fonts, and global element styles.
Kept in its own module so dashboard.py (which imports betting_hub) and
betting_hub.py can both import it without a circular dependency.
"""

import streamlit as st


# Render-time Plotly config, passed at every st.plotly_chart call site.
#
# It lives here because theme.py is the one module BOTH dashboard.py and
# betting_hub.py already import — they each carry their own apply_chart_theme,
# so this is the only shared place a single definition can sit.
#
# It cannot be applied centrally the way the axis lock in apply_chart_theme is:
# `config` is a per-call keyword on st.plotly_chart with no app-wide equivalent
# (keyword-only, default None — checked on 1.57 local and 1.59.2 Cloud). So the
# constant is the single source of truth and each site passes it by name.
#
#   scrollZoom  — the wheel/pinch zoom that hijacks a mobile scroll
#   doubleClick — double-tap autoscale, easy to trigger by accident on touch
#   displayModeBar — the hover toolbar, noise on a phone
#
# NOT staticPlot: that would disable hover, which these charts read out through.
PLOTLY_TOUCH_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
}


def inject_global_theme():
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62.5..125,400..900&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:         #0a1017;
  --surface:    #101a24;
  --surface-2:  #0d141d;
  --line:       rgba(140,165,185,.14);
  --emerald:    #34d399;
  --emerald-dim:rgba(52,211,153,.12);
  --emerald-track:rgba(52,211,153,.22);
  --emerald-pack:rgba(52,211,153,.45);
  --gold:       #f0b429;
  --gold-dim:   rgba(240,180,41,.12);
  --text:       #e9eef3;
  --muted:      #7e8c99;
  --steel:          #9fb0bf;
  --muted-fill:     rgba(159,176,191,.22);
  --hairline-strong:rgba(140,165,185,.22);
  --ease-out:   cubic-bezier(0.23,1,0.32,1);
}
.stApp, html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Archivo', sans-serif !important;
    letter-spacing: -0.01em !important;
    color: var(--text) !important;
}
[data-testid="stDataFrame"] th,
[data-testid="stTable"] th {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 10px !important;
    text-transform: uppercase !important;
    letter-spacing: .22em !important;
    color: var(--muted) !important;
    background: var(--surface-2) !important;
}
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; }
[data-testid="stExpander"],
[data-testid="stTabs"],
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stMultiSelect"] > div > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    color: var(--text) !important;
}
/* Qualified to aria-selected="false": the selected tab's emerald comes from
   Streamlit's own primaryColor and we deliberately leave it alone. */
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="false"] { color: var(--muted) !important; }
[data-testid="stTabs"] [aria-selected="true"] { color: var(--text) !important; }
/* ── Selectbox dropdown panel ──
   Streamlit mounts this as a direct child of <body>, OUTSIDE .stApp, so it
   cannot be reached by any .stApp-scoped rule. Every selector below is keyed
   on the panel's own unique testid (stSelectboxVirtualDropdown) rather than on
   body-level position or the generic [data-testid="portal"] container — that
   generic portal is a SEPARATE body-level div and is where st.dialog (the auth
   dialog) mounts, so these rules provably cannot leak into it. */
[data-testid="stSelectboxVirtualDropdown"] {
    background: var(--surface) !important;
    border: 1px solid #1a2632 !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"] > div {
    background: transparent !important;
    color: var(--text) !important;
    transition: background-color 0.12s ease !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover > div,
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-hovered="true"] > div,
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused="true"] > div {
    background: rgba(52,211,153,0.08) !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] > div {
    background: rgba(52,211,153,0.14) !important;
}
.stButton button, button[kind="primary"], button[kind="secondary"] {
    border-radius: 9px !important;
    font-family: 'Archivo', sans-serif !important;
    font-weight: 700 !important;
    padding: 10px 18px !important;
}
</style>
""", unsafe_allow_html=True)
