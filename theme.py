"""
theme.py — Cha Ching shared design tokens

inject_global_theme() is called from both dashboard.py and
betting_hub.render_page() so every page (Brownlow and Betting Hub)
draws from the same :root token set, fonts, and global element styles.
Kept in its own module so dashboard.py (which imports betting_hub) and
betting_hub.py can both import it without a circular dependency.
"""

import streamlit as st


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
  --gold:       #f0b429;
  --gold-dim:   rgba(240,180,41,.12);
  --text:       #e9eef3;
  --muted:      #7e8c99;
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
[data-testid="stTabs"] [data-baseweb="tab"] { color: var(--muted) !important; }
[data-testid="stTabs"] [aria-selected="true"] { color: var(--text) !important; }
.stButton button, button[kind="primary"], button[kind="secondary"] {
    border-radius: 9px !important;
    font-family: 'Archivo', sans-serif !important;
    font-weight: 700 !important;
    padding: 10px 18px !important;
}
</style>
""", unsafe_allow_html=True)
