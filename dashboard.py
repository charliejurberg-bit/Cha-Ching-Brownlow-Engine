"""
Brownlow Medal Prediction Dashboard v4.1
Run: python -m streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re
import subprocess
import sys
import betting_hub
import user_auth
import features as feat
from theme import inject_global_theme, PLOTLY_TOUCH_CONFIG
from brownlow_medallists import get_medallists

st.set_page_config(page_title="Cha Ching | AFL Brownlow Medal Predictor", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")

# Every document on the page — the app shell and each srcdoc iframe — must ask
# for this EXACT url. An iframe is a separate document and cannot inherit the
# shell's fonts, but it does share the HTTP cache, so an identical url is served
# from cache while a divergent one silently costs a fresh CSS round-trip and its
# own woff2 set. Keep the shell and the iframes on one constant so they can't
# drift apart. Archivo is the variable font: it covers 400..900, so every static
# weight the iframes ask for renders off the one file the shell already fetched.
_FONTS_HREF = ("https://fonts.googleapis.com/css2?"
               "family=DM+Mono:wght@400;500&"
               "family=Sora:wght@400;500;600;700&"
               "family=Archivo:wdth,wght@62.5..125,400..900&"
               "family=IBM+Plex+Mono:wght@400;500;600&display=swap")

# Tabler icons webfont — backs the nav page-strip glyphs (.ti-* marker divs
# drawn via CSS ::before). Shell-only: no iframe uses it.
#
# Pinned to 2.47.0 ON PURPOSE, and not because 2.x is current — it isn't (3.44.0
# is). This replaces `@tabler/icons-webfont@latest/tabler-icons.min.css`, and
# jsDelivr resolves a versionless path to the newest release that still ships
# that file AT THE PACKAGE ROOT. 3.x moved it to /dist/, so @latest has silently
# been serving 2.47.0 the whole time — the root path 404s on 3.44.0. 2.47.0 is
# byte-identical to what shipped before this pin, and the nav's hardcoded
# codepoints are calibrated against it.
#
# Bumping to 3.x is a separate, visual change: re-verify every codepoint in
# _PAGE_ICONS against the new release before doing it.
_TABLER_HREF = ("https://cdn.jsdelivr.net/npm/"
                "@tabler/icons-webfont@2.47.0/tabler-icons.min.css")

# For iframe heads. A stylesheet <link> still blocks the iframe's first paint —
# it is not async — but the preload scanner finds it immediately, where an
# @import is only discovered once the surrounding <style> has been parsed. The
# preconnects warm gstatic for an iframe whose head parses before the shell's
# own font fetch has opened the connection.
_FONTS_LINKS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                f'<link rel="stylesheet" href="{_FONTS_HREF}">')

def inject_global_css():
    st.markdown("""
<style>
iframe[title="streamlit_app"] { margin-top: -60px !important; }
</style>
""", unsafe_allow_html=True)
    # Both as <link>, up here in the shell head rather than an @import buried in
    # a later <style>: the preload scanner finds a link immediately, where an
    # @import is only discovered once the enclosing stylesheet has been parsed.
    st.markdown(f'<link href="{_FONTS_HREF}" rel="stylesheet">'
                f'<link href="{_TABLER_HREF}" rel="stylesheet">',
                unsafe_allow_html=True)
    st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text);
    font-family: 'Sora', sans-serif;
}
[data-testid="stAppViewContainer"] > .main {
    background-color: var(--bg) !important;
}
[data-testid="block-container"],
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    max-width: 1200px;
}
[data-testid="stSidebar"] {
    background-color: #0d1720 !important;
    border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 500;
    padding: 4px 0 2px 4px;
}
[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    color: var(--muted) !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    transition: background 180ms ease-out, color 180ms ease-out !important;
    width: 100% !important;
    text-align: left !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: var(--surface-2) !important;
    color: var(--text) !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    background: #1a3a2a !important;
    border: 1px solid #34d399 !important;
    color: #34d399 !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    width: 100% !important;
    text-align: left !important;
}
h1, h2, h3, h4 {
    font-family: 'Sora', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.02em;
}
h1 { font-size: 2rem !important; font-weight: 700 !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
h3 { font-size: 1rem !important; font-weight: 500 !important; }
p, li { color: var(--muted); line-height: 1.6; }
code, [data-testid="stCode"] {
    font-family: 'DM Mono', monospace !important;
    background: var(--surface-2) !important;
    color: #34d399 !important;
    border-radius: 4px;
}
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    padding: 16px !important;
}
[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-family: 'Sora', sans-serif !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaPositive"] {
    color: #34d399 !important;
    font-size: 12px !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] th {
    background: var(--surface-2) !important;
    color: var(--muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    border-bottom: 1px solid var(--line) !important;
}
[data-testid="stDataFrame"] td {
    background: var(--surface) !important;
    color: var(--text) !important;
    border-bottom: 1px solid #1e3040 !important;
    font-size: 13px !important;
}
[data-testid="stDataFrame"] tr:hover td {
    background: var(--surface-2) !important;
}
[data-testid="stTable"] {
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    width: 100% !important;
}
[data-testid="stTable"] thead th {
    background: var(--surface-2) !important;
    color: var(--muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    border-bottom: 1px solid var(--line) !important;
    padding: 8px 10px !important;
}
[data-testid="stTable"] td {
    border-bottom: 1px solid #1e3040 !important;
    font-size: 13px !important;
    padding: 6px 10px !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'Sora', sans-serif !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'Sora', sans-serif !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #34d399 !important;
    box-shadow: 0 0 0 3px rgba(52,211,153,0.12) !important;
}
button[kind="primary"],
[data-testid="baseButton-primary"] {
    background: #34d399 !important;
    color: #0a1f14 !important;
    border: none !important;
    font-family: 'Sora', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: transform 160ms cubic-bezier(0.23,1,0.32,1), opacity 160ms !important;
}
button[kind="primary"]:hover { opacity: 0.88 !important; }
button[kind="primary"]:active { transform: scale(0.97) !important; }
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid var(--line) !important;
    gap: 0 !important;
}
[data-testid="stTabs"] [role="tab"] {
    color: var(--muted) !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    border-bottom: 2px solid transparent !important;
    transition: color 150ms ease-out, border-color 150ms ease-out !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #34d399 !important;
    border-bottom-color: #34d399 !important;
    background: transparent !important;
}
hr {
    border: none !important;
    border-top: 1px solid var(--line) !important;
    margin: 1.5rem 0 !important;
}
.js-plotly-plot .plotly .bg { fill: transparent !important; }
.js-plotly-plot { border-radius: 10px !important; overflow: hidden; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }
.section-header {
    font-family: 'Sora', sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4a5a6a;
    padding: 0 0 8px 0;
    border-bottom: 1px solid var(--line);
    margin-bottom: 16px;
}
@keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
    0%,100% { box-shadow: 0 0 0 3px rgba(52,211,153,0.2); }
    50%      { box-shadow: 0 0 0 6px rgba(52,211,153,0.08); }
}
.mt-card { animation: fadeSlideUp 400ms cubic-bezier(0.23,1,0.32,1) both; }
.mt-card:nth-child(1) { animation-delay: 0ms; }
.mt-card:nth-child(2) { animation-delay: 60ms; }
.mt-card:nth-child(3) { animation-delay: 120ms; }
.mt-card:nth-child(4) { animation-delay: 180ms; }
:root {
  /* ── legacy --cc-* aliases, repointed to shared tokens ── */
  --cc-bg:      var(--bg);
  --cc-surface: var(--surface);
  --cc-nav:     var(--surface-2);
  --cc-border:  var(--line);
  --cc-green:   var(--emerald);
  --cc-gold:    var(--gold);
  --cc-primary: var(--emerald);
  --cc-text:    var(--text);
  --cc-muted:   rgba(255,255,255,0.35);
  --cc-hint:    rgba(255,255,255,0.25);

  /* ── Cha Ching design tokens (shared across all pages) ── */
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
.stApp, [data-testid="stAppViewContainer"] {
  background: var(--cc-bg) !important;
}
/* ── Pill toggle buttons (global default) ── */
[data-testid="stBaseButton-primary"] {
  background: var(--emerald) !important;
  color: #062b1d !important;
  border: none !important;
  border-radius: 100px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 7px 20px !important;
  min-height: unset !important;
  height: auto !important;
  line-height: 1.4 !important;
}
[data-testid="stBaseButton-secondary"] {
  background: rgba(255,255,255,0.05) !important;
  color: rgba(255,255,255,0.45) !important;
  border: none !important;
  border-radius: 100px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 7px 20px !important;
  min-height: unset !important;
  height: auto !important;
  line-height: 1.4 !important;
}
</style>
""", unsafe_allow_html=True)

def apply_chart_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Archivo, sans-serif", color="#7e8c99", size=12),
        title_font=dict(family="Archivo, sans-serif", color="#e9eef3", size=14),
        # fixedrange locks each axis against zoom/pan, which on a touch screen is
        # what stops a scrolling finger being captured by the chart instead of
        # scrolling the page. dragmode=False removes the drag interaction that
        # would otherwise pan. Both are figure-level, so every themed chart gets
        # them without touching a single call site — and they survive the
        # update_layout / update_xaxes calls several sites make AFTERWARDS,
        # because Plotly's update is recursive and merges rather than replaces.
        # Hover is untouched: this is deliberately not staticPlot.
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
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(gridcolor="rgba(140,165,185,.14)", tickfont=dict(color="#7e8c99", size=10)),
            angularaxis=dict(gridcolor="rgba(140,165,185,.14)", tickfont=dict(color="#7e8c99", size=11)),
        ),
        margin=dict(l=16, r=16, t=40, b=16),
    )
    # Plotly renders the literal string "undefined" as the title when title_font is
    # set but title.text is not. Force an empty title unless one was set explicitly.
    if not (fig.layout.title and fig.layout.title.text):
        fig.update_layout(title_text="")
    for trace in fig.data:
        if trace.type not in ('heatmap', 'contour', 'choropleth'):
            trace.update(marker_line_width=0)
    return fig

# ── Round display law (single home) ───────────────────────────
# AFLTables numbers every season's rounds from 1. Seasons from 2024 onward open
# with an "Opening Round" (AFL Round 0), so their AFLTables Round_num runs one
# ahead of the real-world AFL round; earlier seasons map 1:1. Convert to the
# displayed round HERE, at render time only — never mutate stored, filtered,
# joined, or sorted Round_num values.
_OPENING_ROUND_FROM = 2024  # first season with an AFL Opening Round

def _display_round(round_num, season):
    """AFLTables Round_num → the AFL round number shown to users (season-aware)."""
    try:
        rn = int(round_num)
        sn = int(season)
    except (TypeError, ValueError):
        return round_num
    return rn - 1 if sn >= _OPENING_ROUND_FROM else rn

def _display_rounds(df):
    """Season-aware display rounds for a game-level df (has Round_num + Season)."""
    if 'Season' in df.columns:
        return [_display_round(rn, sn) for rn, sn in zip(df['Round_num'], df['Season'])]
    return list(df['Round_num'])

@st.dialog("Cha Ching account")
def _auth_dialog():
    """The one sign-in / create-account form in the app.

    A dialog so the banner can offer it from every page without carving a slice
    out of every layout — which is what the two inline expanders this replaces
    were doing, in duplicate.

    Safe with the cookie flow, and the reason is worth stating because it is not
    obvious: st.dialog is implemented as a fragment, and the cookie write is
    flushed by bootstrap_session() at the TOP of the script, outside any
    fragment. A fragment-scoped rerun would skip that and silently lose the
    cookie — the 1e32d87 bug, back again. It does not, because st.rerun()
    defaults to scope='app' and reruns the whole script. Never pass
    scope='fragment' here.

    All this does is call user_auth and stage; the four-branch signup handling
    (confirmation on vs off) is carried over verbatim from the retired forms.
    """
    _t1, _t2 = st.tabs(["Sign in", "Create account"])
    with _t1:
        with st.form("cc_auth_signin", clear_on_submit=True):
            _e = st.text_input("Email", key="cc_user_dlg_in_email")
            _p = st.text_input("Password", type="password", key="cc_user_dlg_in_pw")
            if st.form_submit_button("Sign in", type="primary",
                                     use_container_width=True):
                _ok, _msg = user_auth.sign_in(_e, _p)
                if _ok:
                    st.rerun()
                else:
                    st.error(_msg)
    with _t2:
        with st.form("cc_auth_signup", clear_on_submit=True):
            _e2 = st.text_input("Email", key="cc_user_dlg_up_email")
            _p2 = st.text_input("Password", type="password",
                                key="cc_user_dlg_up_pw",
                                help="At least 8 characters.")
            st.caption("Email is used for sign-in only.")
            if st.form_submit_button("Create account", type="primary",
                                     use_container_width=True):
                _ok, _msg = user_auth.sign_up(_e2, _p2)
                if _ok and not _msg:
                    st.rerun()          # confirmation off — straight in
                elif _ok:
                    st.success(_msg)    # confirmation on — check your email
                else:
                    st.error(_msg)


def _render_account_control(prefix: str):
    """Account chip + Sign out when signed in; Sign in otherwise.

    One implementation, two homes (the interior banner and the landing hero).
    `prefix` only exists because Streamlit needs distinct widget keys — the two
    never render together, but identical keys would be a DuplicateWidgetID
    waiting for the day they do.

    Hidden entirely when the anon key isn't configured: a sign-in button that
    cannot work is worse than no button, the same call auth_available() has
    always been used for.
    """
    _user = user_auth.current_user()
    if not _user and not user_auth.auth_available():
        return

    # One keyed container, not two columns. The chip and the button are a single
    # compact group pinned to the right inset — columns would give each of them a
    # FRACTION of the row and park the chip somewhere near the middle, which is
    # what they did. The CSS turns this container into a right-aligned flex row;
    # keying it means the rule addresses this group and nothing else.
    with st.container(key=f"{prefix}_acct"):
        if _user:
            # Admin wears gold, everyone else emerald — the same signal the hub
            # pill gives, on the one element that is always on screen.
            _admin = bool(st.session_state.get("cc_is_admin"))
            _name = (_user.get("email") or "").split("@")[0] or "account"
            _initial = _name[:1].upper()
            st.markdown(
                f'<div class="ccb-chip{" admin" if _admin else ""}">'
                f'<span class="ccb-av">{_initial}</span>'
                f'<span class="ccb-name">{_name}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # No use_container_width: it is what stretched this to ~300px of
            # mostly empty pill with the label adrift in the middle.
            if st.button("Sign out", key=f"{prefix}_signout"):
                user_auth.sign_out()
                st.rerun()
        else:
            if st.button("Sign in", key=f"{prefix}_signin"):
                _auth_dialog()


def render_banner():
    """Row 1 of every interior page: wordmark left, account control right.

    Columns rather than one st.markdown because the right-hand side has to be
    real st.buttons — they drive reruns, and the dialog opens from one. The hub
    pill is NOT here: it is its own row (see _render_hub_tabs), because
    st.columns wrap is not ours to control and a pill squeezed into this row
    would clip before it wrapped.
    """
    _sub = ("Through Round {}".format(_display_round(max_season_rounds, selected_season)) if is_2026
            else "All Seasons" if is_career else f"{selected_season} Season")
    with st.container(key="ccbanner"):
        _bl, _br = st.columns([6, 4], vertical_alignment="center")
        with _bl:
            # .cc-banner is kept as the marker the leading-gap rules key off —
            # see the :has(.cc-banner) block in the CSS.
            st.markdown(
                '<div class="cc-banner">'
                '<span class="ccb-mark">'
                '<span class="cha">CHA</span><span class="ching">CHING</span>'
                '</span>'
                f'<span class="ccb-stamp">{_sub.upper()}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        with _br:
            _render_account_control("ccb")

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Structural ── */
    /* PROJECT LAW: no overflow-x:hidden at page level. Clipping the root hides
       a sideways overflow instead of fixing it, and takes the content with it.
       Anything too wide gets contained where it lives — a wrapper carrying
       overflow-x:auto (see the Polls a Vote matrix, .lb-tbl-wrap, the Game
       Analysis and Model Comparison tables) or a layout that wraps.
       A `body { overflow-x: hidden !important; }` line sat here and was dead:
       the rule below names `body` too, at the same (0,0,1) specificity and also
       !important, so `visible` won on source order. It read as protection while
       doing nothing. Do not reinstate it. */
    html, body, .stApp, .main,
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"],
    [data-testid="block-container"],
    [data-testid="stVerticalBlock"] { overflow-x: visible !important; }
    [data-testid="stAppViewContainer"]          { padding-top: 0 !important; }
    [data-testid="stHeader"]                    { display: none !important; }
    section[data-testid="stSidebarContent"]     { padding-top: 0 !important; }
    [data-testid="stToolbar"]                   { display: none !important; }
    div[data-testid="stToolbar"]                { display: none !important; }
    [data-testid="collapsedControl"]            { display: none !important; }
    * { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; box-sizing: border-box; }
    .main .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="block-container"] {
        padding-top: 0 !important;
        padding-bottom: 2.5rem;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    @media (max-width: 768px) {
        .main .block-container { padding-left: 0.4rem !important; padding-right: 0.4rem !important; }
    }

    /* ── CHA CHING banner ── */
    /* Collapse the leading gap above the banner: the global CSS/JS-injection
       element containers (style/link tags + the animated-counter iframe) are
       zero-height but each still adds a 16px flex gap in the outer
       stVerticalBlock. Scoped to pages that render .cc-banner. */
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > style:only-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > link:only-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > link:first-child + style:last-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(> iframe[srcdoc*="_ccAnimated"]) {
        display: none !important;
    }
    /* Row 1: wordmark + round stamp. A compact row, so the page itself starts
       near the top. */
    .cc-banner {
        display: flex;
        align-items: baseline;
        gap: 11px;
        white-space: nowrap;
        min-width: 0;
    }
    .ccb-mark {
        font-family: 'Archivo', sans-serif;
        font-weight: 900;
        font-variation-settings: 'wdth' 122;
        font-size: 19px;
        line-height: 1;
        letter-spacing: .01em;
        flex: 0 0 auto;
    }
    /* The gradients are painted on the text itself, so the span must not be
       display:inline-block-with-zero-width — a trailing space between CHA and
       CHING would fall outside both gradients, hence the explicit margin. */
    .ccb-mark .cha {
        background: linear-gradient(180deg, #e9eef3 0%, #8a9aa9 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
        margin-right: .28em;
    }
    .ccb-mark .ching {
        background: linear-gradient(120deg, #34d399 0%, #8ec94a 52%, #f0b429 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
    }
    .ccb-stamp {
        font-family: 'DM Mono', monospace;
        font-size: 10px;
        letter-spacing: .18em;
        text-transform: uppercase;
        color: #5a6a79;
        flex: 0 1 auto;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Account chip */
    .ccb-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        max-width: 100%;
        padding: 3px 12px 3px 3px;
        background: #101a24;
        border: 1px solid #1a2632;
        border-radius: 999px;
    }
    .ccb-av {
        flex: 0 0 auto;
        width: 24px; height: 24px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-family: 'Archivo', sans-serif;
        font-weight: 800;
        font-size: 11px;
        line-height: 1;
        background: #0f3d31;
        color: #34d399;
    }
    .ccb-chip.admin .ccb-av { background: #3d3110; color: #f0b429; }
    .ccb-name {
        font-family: 'Archivo', sans-serif;
        font-size: 12px;
        font-weight: 600;
        color: #b8c4ce;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* Banner row chrome + buttons.
       .stApp .st-key-* scores (0,2,1) and theme.py's `.stButton button` reset is
       (0,1,1) !important — and theme injects AFTER this block, so specificity is
       the only thing winning here, not order. Same lesson as the nav CSS. */
    /* Full-bleed, the same way the hub row and page strip do it: escape the
       centred block container with left:50% + translateX(-50%) + width:100vw.
       The OLD .cc-banner carried this trio and the rebuild dropped it, which is
       why row 1 sat indented while the strip below ran edge to edge.
       padding's 16px matches .st-key-ccnav_page's `padding: 4px 16px`, so both
       rows share one content box and the wordmark lines up with the strip's
       left inset. Change the two together or they drift apart again. */
    .stApp .st-key-ccbanner {
        background: var(--bg) !important;
        position: relative !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 100vw !important;
        min-width: 100vw !important;
        flex-shrink: 0 !important;
        margin-left: 0 !important;
        padding: 10px 16px 9px !important;
        border-bottom: 1px solid var(--line) !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        gap: 0 !important;
    }
    .stApp .st-key-ccbanner [data-testid="stHorizontalBlock"] { gap: 0 !important; }

    /* Row 1 centreline — the wordmark and the account group sit on one axis.
       st.columns(vertical_alignment="center") is the primary mechanism and is
       already passed in render_banner (available since 1.36; present on both
       1.57 local and 1.59 Cloud). It sets the column proto's vertical_alignment,
       which the frontend turns into justify-content on the column's own flex
       container — so it centres each column's CHILDREN inside the column.
       It was not enough on its own, and this is why: Streamlit's markdown block
       carries default paragraph margins, so the wordmark's BOX was taller than
       the text inside it. The column dutifully centred the box; the text sat
       low inside that box, and the account group — whose container we already
       zero the margins on — did not. Making the box honest is the fix; the
       justify-content below is a backstop in case a future Streamlit renders
       vertical_alignment differently.
       Scoped to the two banner containers, so no other page's markdown loses
       its paragraph spacing. */
    .stApp .st-key-ccbanner [data-testid="stMarkdownContainer"],
    .stApp .st-key-ccland [data-testid="stMarkdownContainer"],
    .stApp .st-key-ccbanner [data-testid="stMarkdownContainer"] p,
    .stApp .st-key-ccland [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
        line-height: inherit !important;
    }
    .stApp .st-key-ccbanner [data-testid="stColumn"],
    .stApp .st-key-ccland [data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }
    .stApp .st-key-ccbanner [data-testid="stElementContainer"] {
        margin: 0 !important;
    }

    /* Compare tab — "Track this H2H" (and its "…instead" variant, same button).
       Streamlit's default is a dark grey fill that all but disappears on the MT
       background, so this is the emerald outline treatment.
       Scoped to the keyed container, never a global button selector: the
       Untrack button in the sibling branch is deliberately left default so a
       destructive-ish secondary doesn't compete with the primary action.
       .stApp .st-key-* scores (0,2,1) against theme.py's `.stButton button`
       (0,1,1) !important — and theme injects AFTER this block, so specificity
       is what wins, not order. Same lesson as the banner and nav CSS.
       The bare `button` child is deliberate too: Streamlit's button testids
       (stBaseButton-secondary et al) have moved between releases, but a
       <button> inside the container is stable across 1.57 and 1.59. */
    .stApp .st-key-h2h_track_ctl button {
        background: transparent !important;
        border: 1px solid #34d399 !important;
        box-shadow: none !important;
    }
    .stApp .st-key-h2h_track_ctl button:hover {
        background: rgba(52,211,153,0.10) !important;
        border-color: #34d399 !important;
    }
    .stApp .st-key-h2h_track_ctl button,
    .stApp .st-key-h2h_track_ctl button p {
        color: #34d399 !important;
    }
    /* Same trick the banner needs: the markdown block's default paragraph
       margins make its BOX taller than its text, so vertical_alignment="center"
       centres a box whose text sits low. Zeroing them is what actually puts the
       helper line on the button's centreline. */
    .stApp .st-key-h2h_track_ctl [data-testid="stMarkdownContainer"],
    .stApp .st-key-h2h_track_ctl [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Compare tab — H2H round ledger reflow.
       The desktop grid is an INLINE style on each generated row
       (_H2H_GRID: 46px 1fr 88px 88px 150px + 4x12px gaps), whose fixed tracks
       alone come to 420px — wider than a phone before any text. Inline styles
       sit above every stylesheet rule in the cascade, so !important is the only
       way to override them from here. That is normally a smell; it is
       acceptable because the reach is exactly one generated class and the
       desktop base stays where it is authored, next to the markup it sizes.
       Four columns below the breakpoint: the class chip moves to a second line
       spanning the full row, so p(poll) figures keep their own columns. */
    @media (max-width: 700px) {
        .stApp .h2h-lrow {
            grid-template-columns: 38px 1fr 64px 64px !important;
            gap: 8px !important;
        }
        .stApp .h2h-lrow > :nth-child(5) {
            grid-column: 1 / -1 !important;
            justify-self: start !important;
            text-align: left !important;
            margin-top: 2px !important;
        }
        /* The head row's fifth cell is the "Class" label — redundant once the
           chip sits on its own line, and it would otherwise leave a stray
           heading with nothing under it. */
        .stApp .h2h-lhead > :nth-child(5) { display: none !important; }
    }

    /* The account group: chip immediately left of the button, hard right.
       st.container(key=...) stamps the class on the stVerticalBlock ITSELF, so
       this node is the flex container — no descendant hop needed. A column
       stacks its children vertically by default, hence the explicit row.
       justify-content:flex-end lands the group on the container's right padding
       edge, which is the shared 16px the strip uses. */
    .stApp .st-key-ccb_acct,
    .stApp .st-key-ccl_acct {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-end !important;
        gap: 8px !important;
        width: 100% !important;
    }
    /* Kill the stretch at every level of the chain. The button element alone is
       not enough — Streamlit wraps it in element/wrapper divs that carry their
       own width, and a 100%-wide wrapper stretches the button inside it no
       matter what the button says. flex:0 0 auto stops them growing to fill the
       row as flex items too. Scoped to these two groups, so no other button on
       any page is deflated by it. */
    .stApp .st-key-ccb_acct [data-testid="stElementContainer"],
    .stApp .st-key-ccl_acct [data-testid="stElementContainer"],
    .stApp .st-key-ccb_acct [data-testid="stButton"],
    .stApp .st-key-ccl_acct [data-testid="stButton"],
    .stApp .st-key-ccb_acct [data-testid="stButton"] button,
    .stApp .st-key-ccl_acct [data-testid="stButton"] button {
        width: auto !important;
        min-width: 0 !important;
        flex: 0 0 auto !important;
        margin: 0 !important;
    }

    .stApp .st-key-ccbanner [data-testid="stButton"] button,
    .stApp .st-key-ccland [data-testid="stButton"] button {
        font-family: 'Archivo', sans-serif !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 5px 14px !important;
        min-height: 30px !important;
        border-radius: 999px !important;
        box-shadow: none !important;
        transition: border-color 160ms ease-out, color 160ms ease-out !important;
    }
    .stApp .st-key-ccb_signin button,
    .stApp .st-key-ccl_signin button {
        background: transparent !important;
        border: 1px solid var(--emerald) !important;
        color: var(--emerald) !important;
    }
    .stApp .st-key-ccb_signout button,
    .stApp .st-key-ccl_signout button {
        background: transparent !important;
        border: 1px solid #2a3948 !important;
        color: #7a8a99 !important;
    }
    .stApp .st-key-ccb_signout button:hover,
    .stApp .st-key-ccl_signout button:hover {
        border-color: #3d5062 !important;
        color: #b8c4ce !important;
    }

    /* Row 1 at narrow widths. The old banner had NO media queries — it was
       centred, fixed at 44px, and simply overflowed. Row 1 has to hold a
       wordmark and an account control on one line, so it sheds in order of what
       is least load-bearing: the name first (the avatar still identifies the
       account), then the round stamp (context, recoverable from the page), and
       the wordmark shrinks rather than wraps. Sign in / Sign out stay real text
       buttons at every width — an icon-only auth control is a guess, and
       guessing is worse on a phone than a slightly narrower label. */
    @media (max-width: 640px) {
        .cc-banner { gap: 8px; }
        .ccb-mark { font-size: 16px; }
        .ccb-chip { padding: 3px; gap: 0; }
        .ccb-name { display: none; }
        .stApp .st-key-ccbanner [data-testid="stButton"] button,
        .stApp .st-key-ccland [data-testid="stButton"] button {
            padding: 5px 10px !important;
        }
    }
    @media (max-width: 480px) {
        .ccb-stamp { display: none; }
    }

    /* ── Column stagger ── */
    [data-testid="stColumn"] { animation: columnEnter 0.3s ease both; }
    [data-testid="stColumn"]:nth-child(1) { animation-delay: 0ms; }
    [data-testid="stColumn"]:nth-child(2) { animation-delay: 60ms; }
    [data-testid="stColumn"]:nth-child(3) { animation-delay: 120ms; }
    [data-testid="stColumn"]:nth-child(4) { animation-delay: 180ms; }
    [data-testid="stColumn"]:nth-child(5) { animation-delay: 240ms; }

    /* ── Chart reveal ── */
    [data-testid="stPlotlyChart"] { animation: chartReveal 0.4s ease both; }

    /* ── Skeleton loader (Midnight Turf) ── */
    .sk-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 8px 0;
        overflow: hidden;
    }
    .sk-title, .sk-line, .sk-bar {
        background: linear-gradient(90deg, var(--surface-2) 25%, #243a4a 50%, var(--surface-2) 75%);
        background-size: 200% 100%;
        animation: shimmerSweep 1.4s linear infinite;
        border-radius: 4px;
    }
    .sk-title             { height: 14px; width: 42%; margin-bottom: 14px; }
    .sk-line              { height: 9px;  margin-bottom: 9px; }
    .sk-line.wide         { width: 85%; }
    .sk-line.med          { width: 58%; animation-delay: 0.1s; }
    .sk-line.short        { width: 32%; animation-delay: 0.22s; }
    .sk-bar               { height: 36px; animation-delay: 0.15s; }

    /* ── Quick link cards ── */
    .quick-link-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-top: 2px solid #34d399;
        border-radius: 6px;
        padding: 16px 18px;
        margin: 0;
        min-height: 80px;
        cursor: pointer;
        transition: background 180ms ease-out;
    }
    .quick-link-card:hover { background: var(--surface-2); }
    .quick-link-title { color: #4a5a6a; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 6px 0; }
    .quick-link-desc  { color: var(--muted); font-size: 12px; line-height: 1.55; margin: 0; }

    /* ── Metric cards ── */
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 16px 20px;
        margin: 6px 0;
        transition: background 160ms ease-out;
    }
    .metric-card:hover { background: var(--surface-2); }
    /* Accent-tinted full border; no side stripe */
    .metric-card-primary {
        background: var(--surface);
        border: 1px solid rgba(52,211,153,0.3);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 6px 0;
        transition: background 160ms ease-out, border-color 160ms ease-out;
    }
    .metric-card-primary:hover { background: #1a2f22; border-color: rgba(52,211,153,0.6); }
    /* Gold-tinted full border for leader context */
    .leader-card {
        background: #1a2d1a;
        border: 1px solid rgba(240,180,41,0.25);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 6px 0;
        transition: background 160ms ease-out;
    }
    .leader-card:hover { background: #1f341f; }
    .metric-label    { color: #4a5a6a; font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; }
    .metric-value    { color: #34d399; font-size: 26px; font-weight: 700; margin-top: 2px; line-height: 1.15; }
    .metric-value-lg { color: #34d399; font-size: 32px; font-weight: 700; margin-top: 2px; line-height: 1.1; }
    .metric-sub      { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.4; }

    /* ── Title bar ── */
    .title-bar {
        background: var(--surface);
        border: 1px solid var(--line);
        padding: 18px 24px;
        border-radius: 6px;
        margin-bottom: 22px;
        animation: titleBarEnter 0.28s ease both;
    }
    .title-bar h1 { color: var(--text); font-size: 24px; font-weight: 700; letter-spacing: -0.5px; margin: 0 0 4px 0; line-height: 1.2; }
    .title-bar h2 { color: var(--text); font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin: 0 0 4px 0; line-height: 1.2; }
    .title-bar p  { color: var(--muted); font-size: 13px; font-weight: 500; margin: 0; line-height: 1.55; }

    /* ── Global header ── */
    .global-header {
        padding: 6px 0 12px 0;
        border-bottom: 1px solid var(--line);
        margin-bottom: 0;
        display: flex;
        align-items: baseline;
        gap: 16px;
    }
    .global-header h1       { color: var(--text); font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -0.4px; white-space: nowrap; }
    .global-header .subtitle{ color: #4a5a6a; font-size: 12px; margin: 0; font-weight: 500; }

    /* ── DNA cards ── */
    .dna-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 18px;
        margin: 4px 0;
        transition: background 160ms ease-out;
    }
    .dna-card:hover { background: var(--surface-2); }
    .dna-label { color: #4a5a6a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 2px; }
    .dna-value { color: #34d399; font-size: 22px; font-weight: 700; line-height: 1.2; }
    .dna-sub   { color: var(--muted); font-size: 12px; margin-top: 3px; line-height: 1.4; }

    /* ── Secondary button ── */
    [data-testid="stBaseButton-secondary"] {
        background-color: var(--surface-2) !important;
        color: var(--muted) !important;
        border: 1px solid var(--line) !important;
        font-weight: 600 !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    }
    [data-testid="stBaseButton-secondary"]:hover {
        background-color: #243a4a !important;
        border-color: #34d399 !important;
        color: var(--text) !important;
    }
    [data-testid="stBaseButton-secondary"]:active { background-color: #1a2f3a !important; }

    /* ── Alert / info boxes ── */
    [data-testid="stAlert"] { border-radius: 6px !important; font-size: 13px !important; }

    /* ── Caption ── */
    .stCaption, [data-testid="stCaptionContainer"] { color: #4a5a6a !important; font-size: 11px !important; }

    /* ── Page content fade-in ── */
    .main .block-container > div:nth-child(n+3) { animation: pageEnter 0.22s ease forwards; }

    /* ── Expander ── */
    [data-testid="stExpander"] summary { transition: color 0.15s ease !important; }
    [data-testid="stExpander"] summary:hover { color: #34d399 !important; }
    [data-testid="stExpander"] [data-testid="stVerticalBlock"] { animation: pageEnter 0.2s ease both; }

    /* ── Spinner ── */
    [data-testid="stSpinner"] { opacity: 0; animation: stFadeIn 0.3s ease 0.08s forwards; }

    /* ── Toast (ease-out — no bounce) ── */
    [data-testid="stToast"] { animation: toastIn 0.22s cubic-bezier(0.23,1,0.32,1) forwards; }

    /* ── Selectbox smooth focus ── */
    [data-testid="stSelectbox"] .react-aria-ComboBox > div {
        transition: border-color 0.15s ease, box-shadow 0.2s ease !important;
    }

    /* ── LIVE badge ── */
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #1a3a2a;
        border: 1px solid #34d399;
        color: #34d399;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        padding: 4px 10px 4px 8px;
        border-radius: 4px;
        animation: livePulse 2.2s ease-out infinite;
        vertical-align: middle;
        position: relative;
    }
    .live-badge::before {
        content: '';
        display: inline-block;
        width: 6px; height: 6px;
        background: #34d399;
        border-radius: 50%;
        animation: liveDot 1.4s ease-in-out infinite;
        flex-shrink: 0;
    }
    .live-badge-off {
        display: inline-flex;
        align-items: center;
        background: var(--surface-2);
        border: 1px solid var(--line);
        color: #4a5a6a;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        padding: 4px 10px;
        border-radius: 4px;
        vertical-align: middle;
    }

    /* ── Card entrance ── */
    .metric-card, .metric-card-primary, .leader-card, .dna-card, .quick-link-card {
        animation: cardEntrance 0.32s cubic-bezier(0.22, 0.61, 0.36, 1) both;
    }
    .section-header { animation: sectionReveal 0.22s ease both; }

    /* ── Number pop (ease-out — no bounce) ── */
    .metric-value, .metric-value-lg, .dna-value, .bh-value {
        animation: numberPop 0.35s cubic-bezier(0.23,1,0.32,1) both;
        animation-delay: 0.07s;
    }

    /* ── Game Analysis — match cards ── */
    .game-card {
        border: 1px solid var(--line);
        border-top: 2px solid #34d399;
        border-radius: 10px;
        padding: 20px 26px 18px 24px;
        background: var(--surface);
        margin: 44px 0 0 0;
        animation: gameCardEnter 0.32s cubic-bezier(0.22, 0.61, 0.36, 1) both;
        transition: background 160ms ease-out;
        position: relative;
        overflow: hidden;
    }
    .game-card:hover { background: var(--surface-2); }
    .game-card-eyebrow  { color: #4a5a6a; font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 10px; }
    .game-card-title    { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; line-height: 1.2; }
    .game-winner-name   { color: #34d399; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; }
    .game-loser-name    { color: #4a5a6a; font-size: 16px; font-weight: 500; }
    .score-pill {
        background: #1a3a2a;
        border: 1px solid #34d399;
        color: #34d399;
        font-size: 13px; font-weight: 700;
        padding: 5px 14px; border-radius: 20px;
        letter-spacing: 0.5px; white-space: nowrap; display: inline-block;
    }
    .score-pill.draw { background: var(--line); border-color: var(--muted); color: var(--muted); }

    /* ── Game Analysis — animated rank badges ── */
    .rank-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        font-weight: 900;
        font-size: 12px;
        line-height: 1;
        font-family: 'DM Mono', monospace;
    }
    .rank-badge-1 { background: #f0b429; color: var(--bg); animation: rankGlow1 2.4s ease-in-out infinite; }
    .rank-badge-2 { background: #34d399; color: var(--bg); animation: rankGlow2 2.4s ease-in-out infinite; }
    .rank-badge-3 { background: #4a90c4; color: var(--bg); animation: rankGlow3 2.4s ease-in-out infinite; }
    @keyframes rankGlow1 {
        0%,100% { box-shadow: 0 0 0 0 rgba(240,180,41,0.55); }
        50%     { box-shadow: 0 0 0 7px rgba(240,180,41,0); }
    }
    @keyframes rankGlow2 {
        0%,100% { box-shadow: 0 0 0 0 rgba(52,211,153,0.55); }
        50%     { box-shadow: 0 0 0 7px rgba(52,211,153,0); }
    }
    @keyframes rankGlow3 {
        0%,100% { box-shadow: 0 0 0 0 rgba(74,144,196,0.55); }
        50%     { box-shadow: 0 0 0 7px rgba(74,144,196,0); }
    }

    /* ── DataFrame rank cell ── */
    [data-testid="stDataFrame"] tbody tr:nth-child(1) td:first-child { font-weight: 800 !important; }

    /* ── Animations ── */
    @keyframes orbDrift1 {
        0%   { transform: translate(-8%, -5%) scale(1.0); }
        100% { transform: translate(8%, 5%) scale(1.08); }
    }
    @keyframes orbDrift2 {
        0%   { transform: translate(5%, 8%) scale(1.05); }
        100% { transform: translate(-10%, -4%) scale(0.95); }
    }
    @keyframes orbDrift3 {
        0%   { transform: translate(3%, -10%) scale(0.95); }
        100% { transform: translate(-5%, 8%) scale(1.1); }
    }
    @keyframes columnEnter {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes chartReveal {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes shimmerSweep {
        0%   { background-position: 200% center; }
        100% { background-position: -200% center; }
    }
    @keyframes pageEnter {
        from { opacity: 0; transform: translateY(5px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes stFadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes toastIn {
        from { opacity: 0; transform: translateX(16px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes livePulse {
        0%   { box-shadow: 0 0 0 0 rgba(52,211,153,0.4); }
        65%  { box-shadow: 0 0 0 8px rgba(52,211,153,0); }
        100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
    }
    @keyframes liveDot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%       { opacity: 0.4; transform: scale(0.8); }
    }
    @keyframes cardEntrance {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes sectionReveal {
        from { opacity: 0; transform: translateX(-8px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes titleBarEnter {
        from { opacity: 0; transform: translateY(-6px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes numberPop {
        from { opacity: 0.15; transform: translateY(6px); }
        to   { opacity: 1;    transform: translateY(0); }
    }
    @keyframes gameCardEnter {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Banner / top gap ── */
    .stApp > header { display: none !important; }
    [data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }

</style>
""", unsafe_allow_html=True)

inject_global_css()
inject_global_theme()

# Trade the session cookie for a live cc_user before anything reads it. This has
# to sit ahead of every page body — the Live Tracker and Polls a Vote both branch
# on current_user(), and a page that rendered first would render signed-out and
# then be contradicted. Recovery itself runs once per browser session; on every
# other run this is a session_state lookup.
user_auth.bootstrap_session()

# Admin access, resolved once per run and never re-derived. Every gate below
# reads this or the session key beside it, so there is exactly one place that
# decides who is admin — the property the old password gate had, kept.
#
# The session key exists for betting_hub's render_page backstop. betting_hub
# deliberately does not import user_auth (that module talks to Supabase with the
# anon key + a user JWT; betting_hub uses service_role, and keeping them apart is
# what stops anyone reaching for the wrong client), so a session key is the
# bridge — the same shape the backstop already relied on with bh_authed, and
# still the only key it reads.
_is_admin = user_auth.is_admin()
st.session_state["cc_is_admin"] = _is_admin

# ── Animated number counter (JS via iframe → parent DOM) ──────
st.iframe("""
<script>
(function() {
    function run() {
        var els = window.parent.document.querySelectorAll('.counter[data-target]');
        els.forEach(function(el) {
            if (el._ccAnimated) return;
            el._ccAnimated = true;
            var raw    = el.getAttribute('data-target');
            var fmt    = el.getAttribute('data-format') || '0';
            var end    = parseFloat(raw);
            if (isNaN(end)) return;
            var dur    = 900;
            var start  = performance.now();
            function tick(now) {
                var t    = Math.min((now - start) / dur, 1);
                var ease = 1 - Math.pow(1 - t, 3);
                var val  = end * ease;
                if      (fmt === '2') el.textContent = val.toFixed(2);
                else if (fmt === '1') el.textContent = val.toFixed(1);
                else                  el.textContent = Math.round(val).toLocaleString();
                if (t < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }
    // Fire immediately, and again after Streamlit finishes rendering
    setTimeout(run, 120);
    setTimeout(run, 500);
    setTimeout(run, 1100);
})();
</script>
""", height=1)  # global animated-counter utility (JS reaches parent DOM); st.iframe rejects height=0, container is hidden via the iframe[srcdoc*="_ccAnimated"] CSS rule

# ── Helpers ──────────────────────────────────────────────────
PRED_DIR = "predictions"
AVAILABLE_SEASONS = []
if os.path.exists(PRED_DIR):
    for f in os.listdir(PRED_DIR):
        if f.startswith("season_") and f.endswith(".csv"):
            try:
                AVAILABLE_SEASONS.append(int(f.replace("season_", "").replace(".csv", "")))
            except: pass
AVAILABLE_SEASONS = sorted(AVAILABLE_SEASONS, reverse=True)

# ── Dynamic year bounds (read once from source files) ─────────
@st.cache_data(ttl=3600)
def _read_data_range():
    for path in ("fitzroy_stats_all.csv", "fitzroy_stats_2015_2025.csv"):
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, usecols=['Season'])
                s = sorted(df['Season'].dropna().unique().astype(int))
                return s[0], s[-1]
            except Exception:
                pass
    return 2015, 2025

@st.cache_data(ttl=3600)
def _read_backtest_range():
    path = f"{PRED_DIR}/backtest_results.csv"
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, usecols=['Season'])
            s = sorted(df['Season'].dropna().unique().astype(int))
            return s[0], s[-1]
        except Exception:
            pass
    return 2019, 2025

_TRAIN_MIN, _TRAIN_MAX = _read_data_range()
_BT_MIN, _BT_MAX = _read_backtest_range()

# Canonical team names. Source files mix old/abbreviated labels (fitzRoy uses
# 'GWS'/'Footscray'; older game files use 'Kangaroos'). Collapse them so the
# player-ID join and every Team display agree on one spelling.
_TEAM_ALIASES = {
    'Footscray': 'Western Bulldogs',
    'GWS': 'Greater Western Sydney',
    'Kangaroos': 'North Melbourne',
}

def _fix_team_names(df: pd.DataFrame) -> pd.DataFrame:
    for col in ('Team', 'Playing.for'):
        if col in df.columns:
            df[col] = df[col].replace(_TEAM_ALIASES)
    return df

@st.cache_data(ttl=86400)
def _player_id_map():
    """(Player, Team, Season) -> fitzRoy player ID. fitzRoy's ID is the only
    authoritative identity: it separates two different people who share a name
    (the two Josh Kennedys) AND keeps one person together across a club move
    (Tom Lynch: Gold Coast -> Richmond). Player_Name + Team alone can't do both."""
    for path in ("fitzroy_stats_all.csv", "fitzroy_stats_2015_2025.csv"):
        if os.path.exists(path):
            try:
                src = pd.read_csv(path, usecols=["Player", "Team", "Season", "ID"])
            except Exception:
                continue
            src = _fix_team_names(src).dropna(subset=["Player", "Team", "Season", "ID"])
            src["Season"] = src["Season"].astype(int)
            src = src.drop_duplicates(["Player", "Team", "Season"])
            return {(r.Player, r.Team, r.Season): r.ID for r in src.itertuples(index=False)}
    return {}

def _disambiguate_players(df: pd.DataFrame) -> pd.DataFrame:
    """Split same-name players who are actually different people.

    Two players are the same person only when fitzRoy gives them the same ID.
    Names carried by more than one ID get rewritten to 'Name (Team)', where Team
    is that person's most-recent team — so a single player who changed clubs keeps
    ONE identity while genuinely different people who share a name are pulled apart.
    Names with no clash (and seasons with no ID source, e.g. live 2026) are untouched.
    Keeps the original name in '_base_name' for callers that need to re-aggregate."""
    if 'Player_Name' not in df.columns or 'Season' not in df.columns:
        return df
    team_col = 'Team' if 'Team' in df.columns else ('Playing.for' if 'Playing.for' in df.columns else None)
    if team_col is None:
        return df
    df = df.copy()
    df['_base_name'] = df['Player_Name']
    id_map = _player_id_map()
    if not id_map:
        return df
    seasons = pd.to_numeric(df['Season'], errors='coerce').astype('Int64')
    df['_pid'] = [
        id_map.get((n, t, int(s))) if pd.notna(s) else None
        for n, t, s in zip(df['_base_name'], df[team_col], seasons)
    ]
    nunique_id = df.dropna(subset=['_pid']).groupby('_base_name')['_pid'].nunique()
    collision = set(nunique_id[nunique_id > 1].index)
    if collision:
        sub = df[df['_base_name'].isin(collision)]
        sort_cols = [c for c in ('Season', 'Round_num') if c in sub.columns]
        last_team = (sub.dropna(subset=['_pid']).sort_values(sort_cols)
                        .groupby('_pid')[team_col].last())
        mask = df['_base_name'].isin(collision)
        suffix = df.loc[mask, '_pid'].map(last_team).fillna(df.loc[mask, team_col])
        df.loc[mask, 'Player_Name'] = df.loc[mask, '_base_name'] + ' (' + suffix.astype(str) + ')'
    return df.drop(columns=['_pid'])

@st.cache_data(ttl=3600)
def load_season(season):
    path = f"{PRED_DIR}/season_{season}.csv"
    if not os.path.exists(path):
        return None
    sdf = _fix_team_names(pd.read_csv(path))
    # season_*.csv was aggregated by name alone, so it merges same-name players
    # (e.g. both Josh Kennedys into one 44-game row). Re-split those few players
    # from the disambiguated game-level data; everyone else stays exactly as-is.
    g = load_game(season)
    if g is None or '_base_name' not in g.columns:
        return sdf
    split = set(g.loc[g['Player_Name'] != g['_base_name'], '_base_name'])
    if not split:
        return sdf
    team_col = 'Team' if 'Team' in g.columns else 'Playing.for'
    rebuilt = g[g['_base_name'].isin(split)].groupby('Player_Name').agg(
        Team=(team_col, 'last'), Games=('Round_num', 'count'),
        Actual_Votes=('Brownlow.Votes', 'sum'), Exp_Total_Votes=('Exp_Votes', 'sum'),
        Avg_Poll_Prob=('Poll_Prob', 'mean'), Exp_3vote_games=('P_3', 'sum'),
        Exp_2vote_games=('P_2', 'sum'), Exp_1vote_games=('P_1', 'sum'),
    ).reset_index()
    keep = sdf[~sdf['Player_Name'].isin(split)]
    out = pd.concat([keep, rebuilt], ignore_index=True)
    return out.sort_values('Exp_Total_Votes', ascending=False).reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_game(season):
    path = f"{PRED_DIR}/game_level_{season}.csv"
    if not os.path.exists(path):
        return None
    return _disambiguate_players(_fix_team_names(pd.read_csv(path)))

@st.cache_data(ttl=3600)
def load_importance():
    path = f"{PRED_DIR}/feature_importance.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_backtest():
    path = f"{PRED_DIR}/backtest_results.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data(ttl=3600)
def load_season_projection():
    path = f"{PRED_DIR}/season_projection_2026.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

# Columns the Stat Filter page actually reads. Passed to load_all_historical()
# so that path loads ~17 columns instead of all 166 — the source-level fix for
# the Community Cloud OOM on this page. (The team/identity columns needed by the
# team-name fusion + disambiguation are force-added inside the loader.)
_STAT_FILTER_COLS = (
    'Player_Name', 'Season', 'Round_num', 'Playing.for', 'Team', 'Brownlow.Votes',
    'Is_Win', 'Is_Loss', 'Disposals', 'Goals', 'Kicks', 'Clearances',
    'Contested.Possessions', 'Coaches_Votes', 'Tackles', 'Score_Involvements',
    'RatingPoints', 'Exp_Votes',
)

# Columns the career Player Profile path reads — the union of what the profile
# tab, DNA tab, load_season_career() and compute_player_efficiency_career() touch.
# Passed to load_all_historical() so the career view never materialises the full
# 166-col frame either. Player_Name is deliberately NOT categorised here (see
# below) because the career consumers group by it.
_CAREER_COLS = (
    'Player_Name', 'Season', 'Round_num', 'Team', 'Playing.for', 'Brownlow.Votes',
    'Exp_Votes', 'Poll_Prob', 'P_1', 'P_2', 'P_3', 'Is_Win', 'Is_Loss',
    'Disposals', 'Goals', 'Kicks', 'Clearances', 'Contested.Possessions', 'Coaches_Votes',
)

@st.cache_data(ttl=3600)
def load_all_historical(columns=None, categorize=('Player_Name', 'Playing.for', 'Team', '_base_name')):
    """Per-game data across every season, with a clean Team column and same-name
    players split into distinct people. (Older season files only carry
    'Playing.for'; 2026 carries 'Team'.)

    When `columns` is given (a tuple of names), only those are read from each CSV
    via usecols — a large memory saving for narrow consumers like Stat Filter.
    The identity/team columns the disambiguation + team-name fusion depend on are
    always kept, and only columns actually present in each file are requested
    (older files lack 'Team', 2026 lacks nothing). `Season` is always set by the
    loader. `columns=None` (the default) preserves the full-width behaviour.

    `categorize` names the (present) text columns cast to category dtype — this
    kills most of the pandas-2.x object-string overhead on Cloud and shrinks the
    per-rerun cache_data copy. Only applied when `columns` is given. Callers that
    group by a text column must exclude it: category group keys re-admit unobserved
    categories (spurious rows), so the career loader keeps 'Player_Name' as object."""
    want = None
    if columns is not None:
        want = set(columns) | {'Player_Name', 'Round_num', 'Team', 'Playing.for'}
    frames = []
    for season in sorted(AVAILABLE_SEASONS):
        path = f"{PRED_DIR}/game_level_{season}.csv"
        if os.path.exists(path):
            if want is None:
                df = _fix_team_names(pd.read_csv(path))
            else:
                avail = set(pd.read_csv(path, nrows=0).columns)
                df = _fix_team_names(pd.read_csv(path, usecols=list(want & avail)))
            df['Season'] = season
            frames.append(df)
    if not frames:
        return None
    g = pd.concat(frames, ignore_index=True)
    if 'Playing.for' in g.columns:
        if 'Team' in g.columns:
            g['Team'] = g['Team'].fillna(g['Playing.for'])
        else:
            g['Team'] = g['Playing.for']
    g = _disambiguate_players(g)
    if want is not None:
        for _c in categorize:
            if _c in g.columns:
                g[_c] = g[_c].astype('category')
    return g

# Sentinel season value meaning "all seasons combined" (career view).
CAREER = "Career"

@st.cache_data(ttl=3600)
def load_game_career():
    """Per-game data across every season (career view). Loads only the ~19
    columns the career Player Profile actually reads, and keeps 'Player_Name' as
    object dtype because load_season_career() / compute_player_efficiency_career()
    group by it."""
    return load_all_historical(_CAREER_COLS, categorize=('Playing.for', 'Team', '_base_name'))

@st.cache_data(ttl=3600)
def load_season_career():
    """Career stand-in for a season_*.csv: one row per player (player list +
    most-recent team), used by Player Profile for the picker and identity."""
    g = load_game_career()
    if g is None:
        return None
    g = g.sort_values(['Player_Name', 'Season', 'Round_num'])
    agg = g.groupby('Player_Name').agg(
        Team=('Team', 'last'),
        Games=('Round_num', 'size'),
    ).reset_index()
    ev = g.groupby('Player_Name')['Exp_Votes'].sum().rename('Exp_Total_Votes').reset_index()
    return agg.merge(ev, on='Player_Name', how='left')

def _efficiency_from_df(df):
    overall = df.groupby('Player_Name').agg(
        Games=('Round_num', 'count'),
        Total_Votes=('Brownlow.Votes', 'sum'),
        Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
        Three_Vote_Rate=('Brownlow.Votes', lambda x: (x == 3).mean()),
        Avg_Disposals=('Disposals', 'mean'),
        Avg_Goals=('Goals', 'mean'),
        Avg_Coaches=('Coaches_Votes', 'mean'),
        Win_Rate=('Is_Win', 'mean'),
    ).reset_index()
    hd = df[df['Disposals'] >= 30].groupby('Player_Name').agg(
        HD_Games=('Round_num', 'count'),
        HD_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
        HD_Avg_Votes=('Brownlow.Votes', 'mean'),
    ).reset_index()
    wins = df[df['Is_Win'] == 1].groupby('Player_Name').agg(
        Win_Games=('Round_num', 'count'),
        Win_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
        Win_Avg_Votes=('Brownlow.Votes', 'mean'),
    ).reset_index()
    losses = df[df['Is_Loss'] == 1].groupby('Player_Name').agg(
        Loss_Games=('Round_num', 'count'),
        Loss_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()
    eff = overall.merge(hd, on='Player_Name', how='left')
    eff = eff.merge(wins, on='Player_Name', how='left')
    eff = eff.merge(losses, on='Player_Name', how='left')
    return eff

@st.cache_data
def compute_player_efficiency(season):
    df = load_game(season)
    return _efficiency_from_df(df) if df is not None else None

@st.cache_data
def compute_player_efficiency_career():
    """Polling DNA over a player's whole career. Seasons with no actual votes
    yet (the in-progress 2026 season) are excluded so they don't deflate rates."""
    g = load_game_career()
    if g is None:
        return None
    voted = g.groupby('Season')['Brownlow.Votes'].transform('sum') > 0
    df = g[voted]
    return _efficiency_from_df(df) if not df.empty else None

# Deliberately 300, unlike its sibling loaders. best_odds.csv is the one file
# here that does NOT derive from the weekly predict run — scraper_odds.py can
# rewrite it any time, and an ad-hoc scrape before placing a bet must not sit
# behind an hour-long cache. It's a 6KB read, so there is nothing to win anyway.
@st.cache_data(ttl=300)
def load_best_odds():
    path = "data_2026/best_odds.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

# Model Comparison source files. Paths are module-level because the page also
# renders them as the per-model source label.
_MC_CC_PATH = "predictions/season_2026.csv"
_MC_WH_PUB  = "data_2026/wheelo_brownlow_predictions.csv"
_MC_WH_PATH = "data_wheelo/wheelo_2026.csv"   # legacy fallback

@st.cache_data(ttl=3600)
def _load_model_comparison():
    """Raw frames behind the Model Comparison page. usecols is a callable so a
    file missing an optional column ('Team', or whichever of ExpVotes/
    RatingPoints the legacy file carries) is skipped rather than raising —
    the caller's column probes still decide what's usable."""
    cc = None
    if os.path.exists(_MC_CC_PATH):
        cc = pd.read_csv(_MC_CC_PATH,
                         usecols=lambda c: c in {'Player_Name', 'Team', 'Exp_Total_Votes'})
    wh, wh_src = None, None
    if os.path.exists(_MC_WH_PUB):
        wh = pd.read_csv(_MC_WH_PUB, usecols=lambda c: c in {'Player', 'Votes'})
        wh_src = 'pub'
    elif os.path.exists(_MC_WH_PATH):
        wh = pd.read_csv(_MC_WH_PATH,
                         usecols=lambda c: c in {'Player', 'ExpVotes', 'RatingPoints'})
        wh_src = 'legacy'
    return cc, wh, wh_src

@st.cache_data
def form_guide_dots(season, n_rounds=3):
    """Returns dict: Player_Name -> emoji dot string for last n_rounds (🟢=polled,⚫=no vote,▫=DNP)."""
    df = load_game(season)
    if df is None:
        return {}
    pname_col = 'Player_Name' if 'Player_Name' in df.columns else 'Player'
    poll_col  = 'Poll_Prob'   if 'Poll_Prob'   in df.columns else None
    if poll_col is None:
        return {}
    rounds_avail = sorted(df['Round_num'].unique())
    last_n = rounds_avail[-n_rounds:] if len(rounds_avail) >= n_rounds else rounds_avail
    result = {}
    for player, grp in df.groupby(pname_col):
        dots = []
        for r in last_n:
            rg = grp[grp['Round_num'] == r]
            if rg.empty:
                dots.append('▫')
            elif float(rg[poll_col].iloc[0]) >= 0.30:
                dots.append('🟢')
            else:
                dots.append('⚫')
        result[player] = ''.join(dots)
    return result

# count night: temporarily drop to ~60 and match the sleep.
@st.cache_data(ttl=300, show_spinner="Fetching live votes…")
def fetch_live_brownlow_data():
    """Fetch Brownlow vote data from AFL public API. Returns a result dict."""
    import requests as _req
    BASE = "https://aflapi.afl.com.au/afl/v2"
    # (connect, read) split — a dead host fails in 5s instead of hanging 10s
    # on each of the up-to-7 sequential calls below.
    TMO = (5, 10)
    HDRS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.afl.com.au/brownlow-medal/live-tracker",
    }
    _empty = {"df": pd.DataFrame(), "feed": [], "last_round": 0,
              "season_name": "", "is_live": False, "error": None}
    try:
        # Resolve current AFLM season id
        cr = _req.get(f"{BASE}/competitions/1/compseasons?pageSize=5", headers=HDRS, timeout=TMO)
        cr.raise_for_status()
        seasons = [s for s in cr.json().get("compSeasons", []) if "Premiership" in s.get("name", "")]
        if not seasons:
            return {**_empty, "error": "Could not resolve current AFL season."}
        season = seasons[0]
        season_id, season_name = season["id"], season["name"]

        # Team id → name lookup
        tr = _req.get(f"{BASE}/teams?compSeasonId={season_id}&pageSize=100", headers=HDRS, timeout=TMO)
        team_map = {}
        if tr.status_code == 200:
            for t in tr.json().get("teams", []):
                team_map[t["id"]] = t.get("name", str(t["id"]))

        # Paginate player data (sorted by totalVotes desc from API)
        all_players = []
        for page in range(5):
            pr = _req.get(
                f"{BASE}/compseasons/{season_id}/award/brownlow?page={page}&pageSize=100",
                headers=HDRS, timeout=TMO,
            )
            if pr.status_code != 200:
                break
            batch = pr.json().get("players", [])
            if not batch:
                break
            all_players.extend(batch)
            # Stop early if trailing players have 0 votes — rest will too
            if batch[-1].get("totalVotes", 0) == 0 and page >= 1:
                break

        if not all_players:
            return {**_empty, "error": "AFL API returned no player data."}

        is_live = any(p.get("totalVotes", 0) > 0 for p in all_players)

        # Build per-round feed dict and player rows
        round_feed: dict[int, list] = {}
        rows = []
        for p in all_players:
            name = f"{p['firstName']} {p['surname']}"
            team = team_map.get(p.get("teamId", 0), "Unknown")
            total = p.get("totalVotes", 0)
            rounds_data = p.get("rounds", {})
            round_votes: dict[int, int] = {}
            last_vote_round = None
            for rkey, entries in rounds_data.items():
                rnum = int(rkey)
                for entry in entries:
                    pts = entry.get("points", 0)
                    if pts:
                        round_votes[rnum] = pts
                        if last_vote_round is None or rnum > last_vote_round:
                            last_vote_round = rnum
                        round_feed.setdefault(rnum, []).append((name, team, pts))
            rows.append({
                "Player": name, "Team": team,
                "Total_Votes": total, "Last_Vote_Round": last_vote_round,
                "Round_Votes": round_votes,
            })

        df = (pd.DataFrame(rows)
              .sort_values("Total_Votes", ascending=False)
              .reset_index(drop=True))
        df["Rank"] = range(1, len(df) + 1)

        # Latest-votes feed: top vote-getters from most recent 5 counted rounds
        last_round = max(round_feed.keys()) if round_feed else 0
        feed_items = []
        for rnum in sorted(round_feed.keys(), reverse=True)[:5]:
            rlabel = "OR" if rnum == 0 else f"Rd {rnum}"
            for pname, pteam, pvotes in sorted(round_feed[rnum], key=lambda x: -x[2])[:5]:
                feed_items.append(
                    f"{rlabel} — {pname} ({pteam}) "
                    f"{'★★★' if pvotes==3 else ('★★' if pvotes==2 else '★')}"
                )

        return {
            "df": df, "feed": feed_items, "last_round": last_round,
            "season_name": season_name, "is_live": is_live, "error": None,
        }
    except Exception as exc:
        return {**_empty, "error": str(exc)}


_BF_CSV   = "data_2026/betfair_predictions.csv"
_ESPN_CSV = "data_2026/espn_predictions.csv"
_AFL_CSV  = "data_2026/afl_predictor_predictions.csv"

_PW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_PW_STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
    Object.defineProperty(navigator, 'plugins',    {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages',  {get: () => ['en-AU', 'en']});
    Object.defineProperty(navigator, 'platform',   {get: () => 'Win32'});
    window.chrome = {runtime: {}};
"""

def _pw_get_html(url, *, wait_for=None, scroll=False, extra_sleep_ms=4000, timeout_ms=30000):
    """
    Fetch a JS-rendered page with Playwright (sync). Returns full page HTML or ''.
    wait_for: CSS selector (str) or list of selectors tried in order.
    scroll:   slowly scroll to bottom to trigger lazy-loaded content.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as _PWT
    html = ''
    with sync_playwright() as _pw:
        _browser = _pw.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ],
        )
        _ctx = _browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='en-AU',
            timezone_id='Australia/Melbourne',
            user_agent=_PW_UA,
            extra_http_headers={
                'Accept-Language': 'en-AU,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Upgrade-Insecure-Requests': '1',
            },
        )
        _ctx.add_init_script(_PW_STEALTH_JS)
        _page = _ctx.new_page()
        try:
            _page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            if wait_for:
                _sels = [wait_for] if isinstance(wait_for, str) else wait_for
                for _s in _sels:
                    try:
                        _page.wait_for_selector(_s, timeout=15000)
                        break
                    except _PWT:
                        continue
            _page.wait_for_timeout(extra_sleep_ms)
            if scroll:
                for _pos in range(0, 25000, 600):
                    _page.evaluate(f"window.scrollTo(0, {_pos})")
                    _page.wait_for_timeout(200)
                _page.wait_for_timeout(extra_sleep_ms)
            html = _page.content()
        except Exception:
            pass
        finally:
            _browser.close()
    return html

def _save_with_backup(df, csv_path):
    """Write df to csv_path, backing up the old version to *_prev.csv first."""
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        import shutil
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)

@st.cache_data(ttl=3600, show_spinner=False)
def _aflt_name_reference():
    """AFLTables spelling of every 2026 player, with team and round.

    The target side of the name reconciliation in features.py. Model Comparison
    joins five feeds on player name, and each spells them differently; this is
    the one spelling they are all resolved onto."""
    path = "data_2026/afltables_2026.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    df['Round_num'] = pd.to_numeric(df['Round'], errors='coerce')
    df = df.dropna(subset=['Round_num'])
    df['Player_Name'] = (df['First.name'].str.strip() + ' '
                         + df['Surname'].str.strip())
    return df[['Player_Name', 'Playing.for', 'Round_num']]


def _resolve_feed_names(df, player_col='Player', team_col=None,
                        team_fixes=None, label='feed'):
    """Rewrite a feed's player names into AFLTables spelling.

    Team-scoped where the feed carries a club (layer 2 can then resolve
    Brad/Bradley and Cameron/Cam), layer 1 only where it does not. Round is not
    available on any of these three feeds, so the scope is team+season; the
    2026 sweep found 14 surname collisions at that scope and zero the rule
    would accept, so the uniqueness guard still holds."""
    ref = _aflt_name_reference()
    if ref.empty or df.empty or player_col not in df.columns:
        return df
    if team_col and team_col in df.columns:
        feed = df.copy()
        if team_fixes:
            feed[team_col] = feed[team_col].replace(team_fixes)
        out, _ = feat.resolve_feed_names(
            feed, ref, feed_name_col=player_col, feed_team_col=team_col,
            feed_round_col=None, label=label, verbose=False)
        out[team_col] = df[team_col].values     # keep the feed's own spelling
        return out
    out, _ = feat.resolve_names_simple(
        df, ref['Player_Name'].unique(), player_col, label=label, verbose=False)
    return out


def _load_csv_fallback(csv_path, rank_col='Rank', player_col='Player',
                       team_col=None, team_fixes=None, label='feed'):
    """Load a predictions CSV; ensure rank_col exists, reconcile player names."""
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if rank_col not in df.columns:
        df[rank_col] = df.index + 1
    return _resolve_feed_names(df, player_col=player_col, team_col=team_col,
                               team_fixes=team_fixes, label=label)

def _rank_change_html(csv_path, current_player, player_col='Player'):
    """HTML snippet showing rank change vs previous scrape (▲N / ▼N / empty)."""
    _prev = csv_path.replace('.csv', '_prev.csv')
    if not os.path.exists(_prev):
        return ''
    try:
        _pv = pd.read_csv(_prev)
        if player_col not in _pv.columns:
            return ''
        _idx = _pv.index[_pv[player_col] == current_player].tolist()
        if not _idx:
            return ' <span style="color:var(--muted);font-size:11px">↑ new</span>'
        _prev_rank = _idx[0] + 1
        _delta = _prev_rank - 1
        if _delta > 0:
            return f' <span style="color:#34d399;font-size:11px;font-weight:700">▲{_delta}</span>'
        if _delta < 0:
            return f' <span style="color:#8b1a1a;font-size:11px;font-weight:700">▼{abs(_delta)}</span>'
    except Exception:
        pass
    return ''

def _file_ts(path):
    """Human-readable modification timestamp for a file, or empty string."""
    if not os.path.exists(path):
        return ''
    import datetime as _dtm
    return _dtm.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d %b %H:%M')

_NAME_SUFFIX_RE = re.compile(
    r'\s+(?:Jr\.?|Sr\.?|Snr\.?|II|III|IV|V)$', re.IGNORECASE
)
# All Unicode dash/hyphen variants that appear in scraped sources
# (en-dash &#8211;, em-dash, figure-dash, minus, non-breaking hyphen, etc.)
_UNICODE_DASHES_RE = re.compile(r'[‐‑‒–—―−﹘﹣－]')

def normalise_name(name):
    """Return a match key for cross-model player name joining.

    Applies: title-case → strip → Unicode dashes→hyphen → drop apostrophes →
    hyphens→space → collapse spaces → strip common suffixes (Jr/Sr/II/III/IV).
    """
    if pd.isna(name):
        return ''
    s = str(name).title().strip()
    s = _UNICODE_DASHES_RE.sub('-', s)   # normalise en-dash, em-dash, etc. → hyphen
    s = s.replace("'", '').replace('-', ' ')
    while '  ' in s:
        s = s.replace('  ', ' ')
    s = _NAME_SUFFIX_RE.sub('', s).strip()
    return s

_BF_API_BASE = "https://betfair-data-supplier-prod.herokuapp.com/api"

def _fetch_betfair_api(timeout=20):
    """Pull Betfair's Brownlow predictions straight from the JSON feed that
    powers their on-site predictor widget — no browser, no AG-Grid scraping.

    The widget first reads the active season from /widgets/brownlow/parameters
    then calls /brownlow?year=<season>&widget=brownlow, which returns one row
    per player with a season-total `total` (the exact number Betfair displays).
    Returns DataFrame[Player, Team, Total_Votes, Rank] or empty on failure.
    """
    import requests
    _ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    sess = requests.Session()
    sess.headers.update({"User-Agent": _ua, "Accept": "application/json"})
    year = None
    try:
        _pj = sess.get(f"{_BF_API_BASE}/widgets/brownlow/parameters",
                       params={"name": "general"}, timeout=timeout).json()
        year = _pj.get("year")
    except Exception:
        pass
    if not year:
        import datetime as _dt
        year = str(_dt.date.today().year)
    raw = sess.get(f"{_BF_API_BASE}/brownlow",
                   params={"year": year, "widget": "brownlow"}, timeout=timeout)
    raw.raise_for_status()
    df = pd.DataFrame(raw.json())
    if df.empty or 'name' not in df.columns or 'total' not in df.columns:
        return pd.DataFrame()
    df['Total_Votes'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
    df['Player'] = df['name'].astype(str).str.title().str.strip()
    if 'team' in df.columns:
        df['Team'] = df['team'].apply(
            lambda t: t.get('name', '') if isinstance(t, dict) else '')
    else:
        df['Team'] = ''
    # Stable sort preserves API order on tied totals, matching Betfair's own
    # leaderboard tie-break (e.g. Cripps ranked above Newcombe, both 17.5).
    df = df.sort_values('Total_Votes', ascending=False, kind='stable').reset_index(drop=True)
    df['Rank'] = df.index + 1
    return df[['Player', 'Team', 'Total_Votes', 'Rank']]

def _refresh_betfair_live_to_csv():
    """Pull Betfair's live JSON feed and write it to _BF_CSV.

    The slow path, made opt-in — mirrors _refresh_espn_live_to_csv. It used to
    run inside fetch_betfair_brownlow on the render path; Betfair's API is a
    Heroku-hosted widget backend whose dyno sleeps off-season and cold-wakes in
    ~10s, so whichever visitor hit Model Comparison after the 10-minute cache
    expiry ate that wake before the page drew. Now nothing renders this; a
    signed-in user presses a button.

    Validates the payload is non-empty and well-formed before writing, so a bad
    fetch never overwrites a good CSV. _save_with_backup keeps the *_prev.csv
    that _rank_change_html reads, so the ▲/▼ deltas survive.
    Returns (ok, message)."""
    try:
        live = _fetch_betfair_api()
    except Exception as exc:
        return False, f"Betfair refresh failed: {exc}"
    if live.empty or not {'Player', 'Total_Votes'} <= set(live.columns):
        return False, "Betfair refresh got nothing usable back — leaving the CSV as-is."
    _save_with_backup(live, _BF_CSV)
    return True, f"Betfair refreshed — {len(live)} players."


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_betfair_brownlow():
    """Betfair Brownlow predictions, read from betfair_predictions.csv.

    Betfair's numbers come from a Heroku-hosted widget API whose dyno sleeps
    off-season and cold-wakes in ~10s. That live pull is now off the render path
    (see _refresh_betfair_live_to_csv); this only reads the stored CSV, refreshed
    by scraper_betfair.py (Run Update) or the Model Comparison button. Nothing on
    a render path opens a socket.

    Like ESPN, the column can be arbitrarily old, so the page shows the file's
    mtime as an 'as of' stamp. ttl matches the other file-derived loaders; the
    button clears it explicitly."""
    fb = _load_csv_fallback(_BF_CSV, 'Rank', team_col='Team',
                            team_fixes=feat.BETFAIR_TEAM_FIXES, label='betfair')
    if fb.empty:
        return pd.DataFrame(), "No Betfair data yet — refresh it, or run scraper_betfair.py"
    return fb.rename(columns={'Total_Votes': 'BF_Votes', 'Rank': 'BF_Rank'},
                     errors='ignore'), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_afl_predictor_brownlow():
    """AFL Predictor season totals, read from afl_predictor_predictions.csv.

    Model Comparison is a five-way snapshot, not a live board, so it reads the
    stored CSV that scraper_afl.py writes on Run Update — nothing on this render
    path opens a socket. The live award-API pull (fetch_live_brownlow_data,
    ttl=300) stays on the Live Tracker, where count-night freshness is the whole
    point. Don't merge the two: the ttls encode different jobs.

    Returns DataFrame[Player, Team, Total_Votes, Rank] — the page re-ranks and
    renames it itself, so no rename here. Like ESPN and Betfair the column can be
    arbitrarily old, hence the 'as of' stamp on the page."""
    return _load_csv_fallback(_AFL_CSV, 'Rank', team_col='Team',
                              team_fixes=feat.COACHES_TEAM_FIXES,
                              label='afl-predictor')


def _fetch_espn_live():
    """Render ESPN's predictor page and parse it via the same logic as
    scraper_espn.py. ESPN has no JSON feed (votes live in the article body and
    the page sits behind a bot challenge), so a headless browser is required.
    Returns DataFrame[Player, Total_Votes, Rank] or empty on failure.

    NOT for the render path — _pw_get_html alone sits on ~16s of hardcoded waits
    before the browser has even answered. Reached only via
    _refresh_espn_live_to_csv(), behind an explicit button."""
    import scraper_espn
    html = scraper_espn._pw_get_html(
        scraper_espn._ESPN_URL,
        wait_for=['article', 'main', 'body'],
        scroll=True,
        extra_sleep_ms=4000,
    )
    if not html:
        return pd.DataFrame()
    votes, lb_order = scraper_espn._parse_votes(html)
    if not votes:
        return pd.DataFrame()
    df = pd.DataFrame([{'Player': n, 'Total_Votes': v} for n, v in votes.items()])
    # Ties broken by ESPN's own leaderboard order (others → 9999), matching the scraper.
    df['_lb'] = df['Player'].map(lambda n: lb_order.get(n, 9999))
    df = df.sort_values(['Total_Votes', '_lb'], ascending=[False, True])
    df = df.drop(columns='_lb').reset_index(drop=True)
    df['Rank'] = df.index + 1
    return df[['Player', 'Total_Votes', 'Rank']]

def _refresh_espn_live_to_csv():
    """Render ESPN with a headless browser and write the result to _ESPN_CSV.

    The slow path, made opt-in. It used to run inside fetch_espn_brownlow on
    the render path, so whichever visitor happened to arrive after the 15-minute
    cache expiry paid a full Chromium launch — ~20-30s, most of it hardcoded
    waits — before Model Comparison drew anything. Now nothing renders this; a
    signed-in user presses a button.

    _save_with_backup keeps the *_prev.csv that _rank_change_html reads, so the
    ▲/▼ deltas still measure against the previous refresh.
    Returns (ok, message)."""
    try:
        live = _fetch_espn_live()
    except Exception as exc:
        return False, f"ESPN refresh failed: {exc}"
    if live.empty:
        return False, "ESPN refresh got nothing back — the render or the parse failed."
    _save_with_backup(live, _ESPN_CSV)
    return True, f"ESPN refreshed — {len(live)} players."


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_espn_brownlow():
    """ESPN Brownlow predictions, read from espn_predictions.csv.

    ESPN is the only model here with no feed to poll — the votes sit in an
    article body behind a bot challenge — so its numbers are always a stored
    render, refreshed by scraper_espn.py or the Model Comparison button
    (_refresh_espn_live_to_csv). Reading the file is all this does; nothing on
    a render path launches a browser.

    Because the column can therefore be arbitrarily old, the page shows the
    file's mtime as an 'as of' stamp — the honest version of the "visible
    notice" the old docstring promised but never wired up (its error return was
    assigned and dropped).

    ttl matches the other file-derived loaders; the button clears it explicitly."""
    fb = _load_csv_fallback(_ESPN_CSV, 'Rank', label='espn')
    if fb.empty:
        return pd.DataFrame(), "No ESPN data yet — refresh it, or run scraper_espn.py"
    return fb.rename(columns={'Total_Votes': 'ESPN_Votes', 'Rank': 'ESPN_Rank'},
                     errors='ignore'), None


_TABLE_STYLES = [
    {"selector": "thead th", "props": [
        ("background-color", "var(--surface-2)"), ("color", "var(--muted)"),
        ("font-size", "11px"), ("font-weight", "600"),
        ("letter-spacing", "0.08em"), ("text-transform", "uppercase"),
        ("border-bottom", "1px solid var(--line)"), ("padding", "8px 10px"),
    ]},
    {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "var(--surface)")]},
    {"selector": "tbody tr:nth-child(odd)",  "props": [("background-color", "#1a2d3d")]},
    {"selector": "tbody tr:hover",           "props": [("background-color", "var(--surface-2)")]},
    {"selector": "td",                       "props": [
        ("border-bottom", "1px solid #1e3040"), ("padding", "6px 10px"), ("color", "var(--text)"),
    ]},
]


_TEAM_COLOURS = {
    'Collingwood': '#4a4a4a',
    'Geelong': '#1b3a6b',
    'Port Adelaide': '#2e7d7d',
    'Western Bulldogs': '#a33333',
    'Brisbane Lions': '#6b1a2f',
    'Brisbane': '#6b1a2f',
    'Sydney': '#c0392b',
    'Hawthorn': '#8b5e3c',
    'Fremantle': '#6c3483',
    'GWS': '#c06a20',
    'Greater Western Sydney': '#c06a20',
    'Carlton': '#1a3a5c',
    'Melbourne': '#1a3060',
    'Richmond': '#8b7a00',
    'West Coast': '#003087',
    'Adelaide': '#c72c41',
    'Essendon': '#cc0000',
    'St Kilda': '#cc2222',
    'Gold Coast': '#e07000',
    'North Melbourne': '#003fa0',
}


def _round_floats(df: pd.DataFrame, dp: int = 1) -> pd.DataFrame:
    result = df.copy()
    for col in result.select_dtypes(include=['float64', 'float32', 'float']).columns:
        result[col] = result[col].round(dp)
    return result

def _apply_mt_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Alternating MT dark row backgrounds. Required because st.dataframe uses canvas
    rendering — CSS selectors on td/th don't reach inside it; only Styler .apply() does.
    Must use literal hex (not CSS vars): the canvas grid does not resolve var() inside
    inline cell styles, which renders the text invisible."""
    out = pd.DataFrame('', index=df.index, columns=df.columns)
    for i in range(len(df)):
        out.iloc[i] = ('background-color: #101a24; color: #e9eef3;' if i % 2 == 0
                       else 'background-color: #1a2d3d; color: #e9eef3;')
    return out

def _style_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    rounded = _round_floats(df)
    float_fmt = {c: '{:.1f}' for c in rounded.select_dtypes(include=['float64', 'float32', 'float']).columns}
    s = rounded.style.apply(_apply_mt_rows, axis=None).set_table_styles(_TABLE_STYLES)
    if float_fmt:
        s = s.format(float_fmt)
    return s

def _apply_team_border(row):
    team = row.get('Team', '')
    colour = _TEAM_COLOURS.get(team, '#7e8c99')
    return [f'border-left: 3px solid {colour} !important;' if i == 0 else '' for i in range(len(row))]

def _style_leaderboard_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    rounded = _round_floats(df)
    float_fmt = {c: '{:.1f}' for c in rounded.select_dtypes(include=['float64', 'float32', 'float']).columns}
    s = rounded.style.apply(_apply_mt_rows, axis=None).apply(_apply_team_border, axis=1).set_table_styles(_TABLE_STYLES)
    if float_fmt:
        s = s.format(float_fmt)
    return s

# ── Season state init ────────────────────────────────────────
if not AVAILABLE_SEASONS:
    st.error("No predictions found. Run brownlow_model.py first.")
    st.stop()
# Season is remembered per page — changing the year on one page must NOT
# affect any other page. Source of truth is a plain dict keyed by page (a
# normal session_state value, so it survives navigation — unlike a widget
# key, which Streamlit drops on any run where the widget isn't rendered).
DEFAULT_SEASON = AVAILABLE_SEASONS[0]
if 'season_by_page' not in st.session_state:
    st.session_state.season_by_page = {}

# ── URL deep-link (?page=...) ────────────────────────────────
# Applied once, before anything reads `page` below, so an external link can land
# on a specific page. First-run only: after this the in-app nav owns `page`, and
# a stale query param must not yank the user back on every rerun. Whitelisted to
# public Brownlow pages — Betting Hub pages are admin-gated, so a deep link into
# one is ignored and the default stands. st.query_params already URL-decodes, so
# the match is exact by name.
_DEEPLINK_PAGES = {
    'Leaderboard', 'Player Profile', 'Stat Filter', 'Game Analysis',
    'Model Comparison', 'Live Tracker', 'Polls a Vote',
}
if not st.session_state.get('_deeplink_done'):
    st.session_state['_deeplink_done'] = True
    _qp_page = st.query_params.get('page')
    if _qp_page in _DEEPLINK_PAGES:
        st.session_state.page = _qp_page

_season_page = st.session_state.get('page', 'Leaderboard')
selected_season = st.session_state.season_by_page.get(_season_page, DEFAULT_SEASON)
# CAREER is a valid selection (offered only on Player Profile); anything else
# unknown falls back to the default season.
if selected_season != CAREER and selected_season not in AVAILABLE_SEASONS:
    selected_season = DEFAULT_SEASON
is_2026 = (selected_season == 2026)
is_career = (selected_season == CAREER)

# ── Data loading ─────────────────────────────────────────────
if is_career:
    predictions = load_season_career()
    game_df = load_game_career()
else:
    predictions = load_season(selected_season)
    game_df = load_game(selected_season)
importance = load_importance()

if predictions is None:
    st.error(f"No predictions for {selected_season}. Run brownlow_model.py first.")
    st.stop()

# max_season_rounds: highest round number in data (used for slider upper bounds).
# Every page reads this (the banner, Landing, Predictions, the DNA tab), so it
# and the loads above cannot be page-gated.
max_season_rounds = int(game_df['Round_num'].max()) if game_df is not None and len(game_df) > 0 else 25

# ── State init + banner ───────────────────────────────────────
if 'active_hub' not in st.session_state:
    st.session_state.active_hub = 'brownlow'
if 'page' not in st.session_state:
    st.session_state.page = 'Leaderboard'

render_banner()

# Membership here is what the password gate keys off (see the chokepoint below),
# so a page leaves the gate by leaving this set. Polls a Vote did exactly that in
# session 3: it is per-user now, scoped by RLS rather than by this gate, and
# lives in the Brownlow strip.
_BH_PAGES = {'Performance', 'Predictions', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis'}

_hub  = st.session_state.get("active_hub", "brownlow")
_page = st.session_state.page

# ── Page list + icons for current hub ─────────────────────────
_PAGE_ICONS = {
    "Predictions":      "ti-home",
    "Leaderboard":      "ti-award",
    "Player Profile":   "ti-user",
    "Stat Filter":      "ti-adjustments-horizontal",
    "Game Analysis":    "ti-chart-dots",
    "Model Comparison": "ti-chart-bar",
    "Live Tracker":     "ti-live-photo",
    "Performance":      "ti-layout-dashboard",
    "Bet Tracker":      "ti-list-check",
    "Cha Ching Tips":   "ti-bulb",
    "Trends & Analysis":"ti-trending-up",
    "Polls a Vote":     "ti-tags",
}

# The other half of _PAGE_ICONS: that says which icon a page wears, this says
# which glyph the icon is. Codepoints verified against the pinned stylesheet —
# see _TABLER_HREF, and re-verify here if that pin ever moves. Written with a
# doubled backslash so the string carries a real one; \e is not a Python escape
# but \f is, and going through this dict makes the two consistent.
_TI_GLYPHS = {
    "ti-home":                   "\\eac1",
    "ti-award":                  "\\ea2c",
    "ti-user":                   "\\eb4d",
    "ti-adjustments-horizontal": "\\ec38",
    "ti-chart-dots":             "\\ee2f",
    "ti-chart-bar":              "\\ea59",
    "ti-live-photo":             "\\eadf",
    "ti-layout-dashboard":       "\\f02c",
    "ti-list-check":             "\\eb6a",
    "ti-bulb":                   "\\ea51",
    "ti-trending-up":            "\\eb43",
    "ti-tags":                   "\\ef86",
}


def _st_key_class(key):
    """The css class Streamlit puts on a keyed element, for `key`.

    Mirrors the frontend's own sanitiser exactly — `st-key-` + the key trimmed
    with every character outside [a-zA-Z0-9_-] replaced by '-'. So the nav
    button keyed "nav_Player Profile" carries .st-key-nav_Player-Profile, and
    "nav_Trends & Analysis" carries .st-key-nav_Trends---Analysis.
    """
    return "st-key-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(key).strip())


# Page-strip icons. Each nav button is already keyed nav_<Page>, so Streamlit
# has ALREADY put a unique class on its container — the icon does not need a
# marker div, and the rules do not need :has() to find the column. This replaces
# 19 marker-keyed :has() rules (two :has() apiece) with plain class matches.
# Pages absent from _TI_GLYPHS simply get no rule and render iconless, which is
# the documented behaviour for a page with no _PAGE_ICONS entry.
_nav_icon_pairs = [(_p, _TI_GLYPHS[_i]) for _p, _i in _PAGE_ICONS.items()
                   if _i in _TI_GLYPHS]
_nav_icon_css = (
    ",".join(f'.{_st_key_class("nav_" + _p)} button::before'
             for _p, _ in _nav_icon_pairs)
    + "{font-family:tabler-icons,sans-serif !important;margin-right:4px;"
      "display:inline-block !important;}"
    + "".join(f'.{_st_key_class("nav_" + _p)} button::before{{content:"{_g}";}}'
              for _p, _g in _nav_icon_pairs)
)

# Active hub-pill accent. Old CSS carried a base emerald rule plus a
# `.nav-hub-anchor.bh` override to gold; the override only ever touched color +
# border-bottom-color, so it collapses to one rule with the colour chosen here.
# _hub is the single source of truth the .bh marker used to encode, so with the
# marker gone this conditional is that same signal, read in Python.
_hub_accent = "var(--gold)" if _hub == "betting" else "var(--emerald)"
# Same active-accent signal for the page strip's active-tab underline. Kept as a
# separate token so slice 4's rules never touch slice 3's verified hub rule.
_page_accent = _hub_accent

if _hub == "brownlow":
    _snav_pages = [
        "Leaderboard", "Player Profile",
        "Stat Filter", "Game Analysis",
        "Model Comparison", "Live Tracker",
        "Polls a Vote",
    ]
else:
    _snav_pages = ["Performance", "Predictions", "Bet Tracker", "Cha Ching Tips", "Trends & Analysis"]

# ── Nav CSS (injected once before containers) ─────────────────
# The tabler-icons webfont the icon rules depend on is loaded as a pinned <link>
# in inject_global_css — see _TABLER_HREF. __ICON_CSS__ is substituted rather
# than injected as a second st.markdown on purpose: this block must stay a
# single <style> in a single element container, because the banner gap rules
# find these injections via `stMarkdownContainer > style:only-child`.
st.markdown("""
<style>
/* ── Hub row container — keyed via st.container(key="ccnav_hub"). For a plain
   keyed container Streamlit stamps the key class straight onto the stVerticalBlock
   element (data-testid AND st-key- on the same node), NOT a parent wrapper — so
   the st-key-ccnav_hub node IS the block; its children are selected as descendants.
   margin-top:0 keeps the row flush under the banner. No marker div, no :has().

   Every selector is prefixed with .stApp as a specificity bump, NOT for scoping.
   The old marker :has() selectors scored ~(0,3,1); the flat st-key- rewrite is
   (0,1,1), which merely TIES betting_hub's `button[kind="primary"]` reset and
   theme.py's `.stButton button` — both re-injected during a BH page render,
   AFTER this block, so they won ties on source order and the pills fell back to
   default fills. .stApp lifts every rule one class (structural -> (0,2,1),
   accent -> (0,3,0)) so they clear those resets on every page while keeping
   accent above structural. See the session notes / CLAUDE.md. ─────────────── */
.stApp .st-key-ccnav_hub {
    background: var(--bg) !important;
    position: relative !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: 100vw !important;
    min-width: 100vw !important;
    flex-shrink: 0 !important;
    margin-left: 0 !important;
    padding: 0 !important;
    border-bottom: 1px solid var(--line) !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    gap: 0 !important;
}
.stApp .st-key-ccnav_hub [data-testid="stHorizontalBlock"] {
    display: grid !important; grid-template-columns: 1fr 1fr !important;
    gap: 0 !important; padding: 0 !important; align-items: stretch !important;
}
.stApp .st-key-ccnav_hub [data-testid="stColumn"] {
    width: 100% !important; min-width: 0 !important; padding: 0 !important;
    display: flex !important; flex-direction: column !important;
}
.stApp .st-key-ccnav_hub [data-testid="stColumn"] > div,
.stApp .st-key-ccnav_hub [data-testid="stElementContainer"],
.stApp .st-key-ccnav_hub [data-testid="stButton"] {
    width: 100% !important; flex: 1 !important;
}
.stApp .st-key-ccnav_hub button {
    background: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    color: var(--muted) !important; font-size: 13px !important;
    font-weight: 500 !important; padding: 5px 16px !important;
    border-radius: 0 !important; white-space: nowrap !important;
    box-shadow: none !important; line-height: 1.4 !important;
    width: 100% !important; display: flex !important;
    align-items: center !important; justify-content: center !important;
    transition: color 160ms ease-out, border-color 160ms ease-out !important;
}
.stApp .st-key-ccnav_hub button p,
.stApp .st-key-ccnav_hub button span {
    color: inherit !important;
}
/* Active hub pill. This rule OWNS the whole box (bg / border / radius), not just
   the accent — betting_hub's render_bh_dashboard() injects a global
   `div[data-testid="stButton"] button[kind="primary"]` emerald-fill rule at
   (0,2,2), plus a :hover at (0,3,2), during the Performance render. Targeting
   `[data-testid="stButton"] button[kind="primary"]` (the exact element it hits)
   scores (0,4,1) so we beat both, resting and hover, and the pill stays a tab. */
.stApp .st-key-ccnav_hub [data-testid="stButton"] button[kind="primary"] {
    background: transparent !important;
    color: __HUB_ACCENT__ !important;
    border: none !important;
    border-bottom: 2px solid __HUB_ACCENT__ !important;
    border-radius: 0 !important;
    font-weight: 600 !important;
}
@media (hover: hover) {
    .stApp .st-key-ccnav_hub [data-testid="stBaseButton-secondary"]:hover,
    .stApp .st-key-ccnav_hub [data-testid="baseButton-secondary"]:hover {
        color: var(--text) !important;
    }
}

/* ── Page strip container — keyed via st.container(key="ccnav_page"). As with
   the hub row, the key class is stamped on the container's stVerticalBlock
   itself, so the st-key-ccnav_page node IS the block and its children are
   descendants. margin-top:-16px folds in the negative pull the old
   stLayoutWrapper:has(.nav-page-anchor) rule applied, tucking the strip up under
   the hub row's border. .stApp prefix is the same specificity bump as the hub
   row (see above). No marker div, no :has(). ──────────────── */
.stApp .st-key-ccnav_page {
    background: var(--bg) !important;
    position: relative !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: 100vw !important;
    min-width: 100vw !important;
    flex-shrink: 0 !important;
    margin-left: 0 !important;
    padding: 4px 16px !important;
    border-bottom: 1px solid var(--line) !important;
    margin-top: -16px !important;
    margin-bottom: 0 !important;
    gap: 0 !important;
}
.stApp .st-key-ccnav_page [data-testid="stHorizontalBlock"] {
    display: flex !important; flex-wrap: nowrap !important;
    width: 100% !important; gap: 0 !important;
    padding: 0 !important; align-items: stretch !important;
    scrollbar-width: none !important;
}
.stApp .st-key-ccnav_page [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
    display: none !important;
}
.stApp .st-key-ccnav_page [data-testid="stColumn"] {
    flex: 1 1 0 !important; min-width: 0 !important; padding: 0 !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}
.stApp .st-key-ccnav_page [data-testid="stColumn"] > div,
.stApp .st-key-ccnav_page [data-testid="stElementContainer"],
.stApp .st-key-ccnav_page [data-testid="stButton"] {
    width: 100% !important; padding: 0 !important; margin: 0 !important;
}
.stApp .st-key-ccnav_page button {
    background: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    color: var(--muted) !important; font-size: 12px !important;
    font-weight: 500 !important; padding: 4px 6px !important;
    /* 44px is the touch-target floor. The tabs are the primary navigation and
       the only way between pages on a phone, so they get a thumb-sized row
       even though the label is 12px. */
    min-height: 44px !important;
    border-radius: 0 !important; white-space: nowrap !important;
    box-shadow: none !important; width: 100% !important; min-width: 0 !important;
    line-height: 1.4 !important; text-align: center !important;
    justify-content: center !important; display: flex !important;
    align-items: center !important;
    transition: color 160ms ease-out, border-color 160ms ease-out !important;
}
.stApp .st-key-ccnav_page button p,
.stApp .st-key-ccnav_page button span {
    color: inherit !important;
}
/* Narrow: scroll the page strip horizontally instead of shrinking columns to
   equal narrow slices (which makes nowrap labels overflow and overlap). The base
   column rule sets min-width:0, which lets each column collapse below its label
   width (the button's width:100% gives the column no intrinsic width to hold on
   to) — so min-width:max-content is the essential piece here, not just the flex
   change. Verified against the real Streamlit DOM at a 393px viewport.
   Scrollbar is hidden above (scrollbar-width + ::-webkit-scrollbar).

   900px, raised from 640px: the Brownlow strip is seven tabs now (Polls a Vote
   joined it in session 3), and seven nowrap labels do not fit a 900px viewport —
   between 640 and 900 they were being squeezed under their own text rather than
   scrolling. The breakpoint tracks the widest strip, so re-check it if an
   eighth page ever lands. */
@media (max-width: 900px) {
    .stApp .st-key-ccnav_page [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
    }
    .stApp .st-key-ccnav_page [data-testid="stColumn"] {
        flex: 0 0 auto !important; min-width: max-content !important;
    }
}
/* Page strip icons — generated from _PAGE_ICONS x _TI_GLYPHS, keyed off each
   nav button's own st-key- class. No marker divs, no :has(). */
__ICON_CSS__

/* Active tab: accent underline (emerald / gold), folded from the old
   .nav-page-anchor.bh override into __PAGE_ACCENT__. Owns the whole box at
   (0,4,1) for the same reason as the hub pill above — betting_hub's Performance
   render injects a (0,2,2)/(0,3,2) emerald-fill on every primary button, which
   otherwise leaks onto the active tab here. */
.stApp .st-key-ccnav_page [data-testid="stButton"] button[kind="primary"] {
    background: transparent !important;
    color: var(--text) !important;
    border: none !important;
    border-bottom: 2px solid __PAGE_ACCENT__ !important;
    border-radius: 0 !important;
    font-weight: 600 !important;
}
@media (hover: hover) {
    .stApp .st-key-ccnav_page [data-testid="stBaseButton-secondary"]:hover,
    .stApp .st-key-ccnav_page [data-testid="baseButton-secondary"]:hover {
        color: var(--text) !important;
    }
}

/* Ticker bar — keyed via st.container(key="cc_ticker"); .st-key-cc_ticker is the
   block. .stApp prefix is a specificity bump (see the nav block): the old
   marker :has():not(:has()) idiom scored ~(0,4,2) and outranked the global
   `[data-testid="stVerticalBlock"]{overflow-x:visible}` and similar; a bare
   .st-key- would drop below them. */
.stApp .st-key-cc_ticker {
    width: 100vw !important;
    min-width: 100vw !important;
    max-width: 100vw !important;
    flex-shrink: 0 !important;
    position: relative !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
.stApp .st-key-cc_ticker [data-testid="stElementContainer"] {
    margin: 0 !important;
}
.stApp .st-key-cc_ticker iframe {
    display: block !important;
    width: 100% !important;
}

/* Destination panels (marker-div + :has() pattern) */
@keyframes tagDotPulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: .35; }
}
/* Destination cards — keyed via st.container(key="card_brownlow"/"card_betting")
   (the keys already existed; the CSS just moved off the markers onto them).
   .st-key-card_* IS each card's block. .stApp prefix is a specificity bump: the
   old marker idiom scored ~(0,4,2) and had to outrank the global
   `[data-testid="stVerticalBlock"]{overflow-x:visible}` (line ~447) for the
   card's overflow:hidden to hold — a bare .st-key- (0,1,0) would lose that. */
.stApp .st-key-card_brownlow,
.stApp .st-key-card_betting {
    position: relative;
    background: linear-gradient(180deg, #101a24 0%, #0d141d 100%) !important;
    border: 1px solid rgba(140,165,185,.14) !important;
    border-radius: 14px !important;
    overflow: hidden;
    padding: 34px 32px 30px !important;
    min-height: 360px;
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
    transition: transform 220ms cubic-bezier(0.23,1,0.32,1),
                border-color 220ms cubic-bezier(0.23,1,0.32,1),
                box-shadow 220ms cubic-bezier(0.23,1,0.32,1);
}
@media (hover: hover) {
    .stApp .st-key-card_brownlow:hover {
        transform: translateY(-4px);
        border-color: rgba(52,211,153,.35) !important;
        box-shadow: 0 12px 32px rgba(52,211,153,.10);
    }
    .stApp .st-key-card_betting:hover {
        transform: translateY(-4px);
        border-color: rgba(240,180,41,.35) !important;
        box-shadow: 0 12px 32px rgba(240,180,41,.10);
    }
}
.stApp .st-key-card_brownlow::before,
.stApp .st-key-card_betting::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    z-index: 1;
}
.stApp .st-key-card_brownlow::before { background: linear-gradient(90deg, transparent, #34d399, transparent); }
.stApp .st-key-card_betting::before { background: linear-gradient(90deg, transparent, #f0b429, transparent); }
.stApp .st-key-card_brownlow [data-testid="stElementContainer"]:first-child,
.stApp .st-key-card_betting [data-testid="stElementContainer"]:first-child {
    flex: 1 1 auto;
}
.dest-tag {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    padding: 5px 11px;
    border-radius: 99px;
    margin-bottom: 16px;
}
.dest-tag::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    animation: tagDotPulse 2.2s ease-in-out infinite;
}
.dest-tag.bw { background: rgba(52,211,153,0.12); color: #34d399; }
.dest-tag.bh { background: rgba(240,180,41,0.12); color: #f0b429; }
.dest-content h2 {
    font-family: 'Archivo', sans-serif;
    font-weight: 800;
    font-size: 30px;
    color: #e9eef3;
    margin: 0 0 8px;
}
.dest-desc { color: #7e8c99; font-size: 14px; line-height: 1.6; margin-bottom: 18px; max-width: 42ch; }
.dest-data-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 26px;
    border-top: 1px solid rgba(140,165,185,.14);
    padding-top: 18px;
    font-family: 'IBM Plex Mono', monospace;
}
.dest-data-row > div { display: flex; flex-direction: column; gap: 5px; }
.dest-data-row .dr-label { font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: #7e8c99; }
.dest-data-row .dr-value { font-size: 14px; font-weight: 600; color: #e9eef3; }

/* ── Leaderboard page ──
   .lb-header / .lb-title / .lb-subtitle are the shared bare-heading trio;
   Game Analysis uses them too so both pages' titles stay identical. The
   rest of the .lb-* rules below are Leaderboard-only. */
.lb-header { margin-bottom: 18px; }
.lb-title {
    font-family: 'Archivo', sans-serif;
    font-weight: 800;
    font-size: 28px;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.01em;
}
.lb-subtitle { color: var(--muted); font-size: 14px; margin: 6px 0 0 0; }
.lb-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    padding: 5px 11px;
    border-radius: 99px;
    background: var(--emerald-dim);
    color: var(--emerald);
}
.lb-live-pill::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    animation: tagDotPulse 2.2s ease-in-out infinite;
}
.lb-odds-ts {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    text-align: right;
    margin: 0 0 4px 0;
}
.lb-podium-card {
    position: relative;
    background: linear-gradient(180deg, var(--surface) 0%, var(--surface-2) 100%);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 20px 22px;
    margin: 6px 0;
    overflow: hidden;
}
.lb-podium-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
}
.lb-podium-card.lb-rank1::before { background: linear-gradient(90deg, transparent, var(--emerald), transparent); }
.lb-podium-card.lb-rank-other::before { background: linear-gradient(90deg, transparent, rgba(140,165,185,.35), transparent); }
.lb-podium-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 10px;
}
.lb-podium-name {
    font-family: 'Archivo', sans-serif;
    font-weight: 700;
    font-size: 18px;
    color: var(--text);
    margin: 0 0 6px 0;
    line-height: 1.2;
}
.lb-podium-name.lb-rank1-name {
    font-weight: 800;
    font-size: 24px;
    color: var(--emerald);
}
.lb-podium-sub { color: var(--muted); font-size: 12px; line-height: 1.4; }
.lb-section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--muted);
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
    margin-bottom: 16px;
}
/* Full Leaderboard filter row: SEARCH PLAYER / CLUB / SHOW. Scoped off the
   keyed container st.container(key="lb_filters"), which stamps
   .st-key-lb_filters on its own stVerticalBlock (not a parent wrapper), so the
   descendant selector below is correct as written. .stApp is for specificity,
   matching the nav CSS convention.

   This replaced a hidden `.lb-controls-marker` div plus a
   stHorizontalBlock:has(.lb-controls-marker) selector. The marker was not free:
   st.markdown emits its own stElementContainer, which keeps a slot in the
   column's flex flow even at display:none, and the vertical block's 16px gap
   then pushed the text input exactly one gap below the two selectboxes
   (widget top 548px against 532px). Do not put a marker element back in
   one of these columns. */
.stApp .st-key-lb_filters label {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.18em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}

/* Destination buttons */
.st-key-land_bw button,
.st-key-land_bh button {
    width: auto !important;
    display: inline-flex !important;
    align-items: center !important;
    padding: 12px 22px !important;
    border-radius: 9px !important;
    font-family: 'Archivo', sans-serif !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    margin-top: 16px !important;
    transition: filter 150ms ease-out, background-color 150ms ease-out, transform 100ms ease-out !important;
}
.st-key-land_bw button:active,
.st-key-land_bh button:active {
    transform: scale(.97);
}
.st-key-land_bw button::after,
.st-key-land_bh button::after {
    content: "→";
    display: inline-block;
    margin-left: 8px;
    transition: transform 150ms ease-out;
}
.st-key-land_bw button:hover::after,
.st-key-land_bh button:hover::after {
    transform: translateX(3px);
}
.st-key-land_bw button {
    background: #34d399 !important;
    color: #062b1d !important;
    border: none !important;
}
.st-key-land_bw button p,
.st-key-land_bw button span {
    color: #062b1d !important;
    font-weight: 700 !important;
}
.st-key-land_bw button:hover { filter: brightness(1.1); }
.st-key-land_bh button {
    background: #f0b429 !important;
    color: #3a2a05 !important;
    border: none !important;
}
.st-key-land_bh button p,
.st-key-land_bh button span {
    color: #3a2a05 !important;
    font-weight: 700 !important;
}
.st-key-land_bh button:hover { filter: brightness(1.08); }
/* The padlock that sat to the right of this button is gone with the card it
   belonged to: land_bh now opens the public Personalised Tracker, not the
   private Betting Hub, so a lock would advertise a gate that isn't there. The
   flex row it needed went with it. The KEY is deliberately still land_bh —
   ten rules above target it, and renaming for tidiness would churn every one
   of them for no behavioural gain. */

</style>
""".replace("__ICON_CSS__", _nav_icon_css)
   .replace("__HUB_ACCENT__", _hub_accent)
   .replace("__PAGE_ACCENT__", _page_accent), unsafe_allow_html=True)

# ── Hub toggle row + page strip row ─────────────────────────────
def _render_hub_tabs():
    # key=ccnav_hub puts st-key-ccnav_hub on the container's stVerticalBlock; the
    # nav CSS keys off that instead of a hidden .nav-hub-anchor marker + :has().
    with st.container(key="ccnav_hub"):
        _hc1, _hc2 = st.columns(2)
        with _hc1:
            if st.button("Brownlow", key="pill_brownlow",
                         type="primary" if _hub == "brownlow" else "secondary"):
                st.session_state["active_hub"] = "brownlow"
                if st.session_state.page in _BH_PAGES:
                    st.session_state.page = "Leaderboard"
                st.rerun()
        with _hc2:
            if st.button("Betting Hub", key="pill_betting",
                         type="primary" if _hub == "betting" else "secondary"):
                st.session_state["active_hub"] = "betting"
                if st.session_state.page not in _BH_PAGES:
                    st.session_state.page = "Performance"
                st.rerun()

def _render_page_nav():
    # key=ccnav_page puts st-key-ccnav_page on the container's stVerticalBlock
    # (same element as data-testid, per slice 3); the nav CSS keys off it as
    # descendants instead of a hidden .nav-page-anchor marker + :has().
    with st.container(key="ccnav_page"):
        _pcols = st.columns(len(_snav_pages), gap="small")
        for _pc, _sp in zip(_pcols, _snav_pages):
            with _pc:
                # No icon marker div: the button's own key already puts a unique
                # st-key- class on its container, which _nav_icon_css keys off.
                if st.button(_sp, key=f"nav_{_sp}",
                             type="primary" if _page == _sp else "secondary"):
                    st.session_state.page = _sp
                    st.rerun()

# The hub pill is admin-only: every _BH_PAGES page is gated on the admin
# check anyway, so for anyone else it is a switch onto a locked door. It
# stays its OWN row rather than folding into the banner — st.columns wrap is
# not ours to drive, and a pill squeezed into row 1 would clip before it
# wrapped. Admin sees three rows, everyone else two.
if _is_admin:
    _render_hub_tabs()
_render_page_nav()

# ── Controls row (season + odds timestamp) ──────────────────
# Only show controls for Brownlow pages, not Betting Hub
_show_controls = _page not in _BH_PAGES

def _season_changed(page):
    # Persist this page's choice into the durable per-page store.
    st.session_state.season_by_page[page] = st.session_state[f"_ctrl_season::{page}"]

_SEASON_PAGES = {
    'Leaderboard', 'Player Profile', 'Game Analysis',
}

if _show_controls:
    _cc1, _cc2, _cc3 = st.columns([2.5, 1.5, 0.7])
    with _cc2:
        _odds_ctrl = load_best_odds()
        if _odds_ctrl is not None and 'scraped_at' in _odds_ctrl.columns:
            st.markdown(
                f'<div class="lb-odds-ts">Odds: {str(_odds_ctrl["scraped_at"].iloc[0])[:16]}</div>',
                unsafe_allow_html=True,
            )
    with _cc3:
        # Player Profile and Leaderboard render their own Season selector inline
        # (next to the title); every other season page uses this top-right control.
        if _page in _SEASON_PAGES and _page not in ('Player Profile', 'Leaderboard'):
            # Per-page widget key keeps pages independent; on_change mirrors the
            # pick into season_by_page so it survives navigating away and back.
            st.selectbox(
                "Season", AVAILABLE_SEASONS,
                index=AVAILABLE_SEASONS.index(selected_season),
                key=f"_ctrl_season::{_page}",
                on_change=_season_changed,
                args=(_page,),
                label_visibility="collapsed",
            )

# ════════════════════════════════════════════════════════════
# BETTING HUB ACCESS GATE
# Single chokepoint before any page body renders — covers every _BH_PAGES
# page, including the inline Predictions block below. Brownlow pages
# (_page not in _BH_PAGES) never hit this and are visually unchanged.
#
# Access is an admin account now, not a shared password. There is nothing to
# type here any more: a password could be passed on, forwarded, or shoulder-read,
# and it authenticated a STRING rather than a person. The admin check resolves an
# identity Supabase already verified, so the way in is to sign in — which the
# Live Tracker and Polls a Vote already offer — and the way to lose access is to
# sign out. This screen therefore states the fact and stops; it never collects a
# credential of its own.
# ════════════════════════════════════════════════════════════
if _page in _BH_PAGES and not _is_admin:
    _gl, _gc, _gr = st.columns([1, 1.1, 1])
    with _gc:
        st.markdown(
            '<div style="text-align:center;margin:64px 0 18px 0">'
            '<div style="font-size:26px;font-weight:800;color:#e9eef3;'
            'letter-spacing:.5px">Betting Hub</div>'
            '<div style="color:var(--muted);font-size:13px;margin-top:6px">'
            'Private &mdash; this section is not public.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        # A signed-in non-admin is told the same thing as a visitor, deliberately:
        # "wrong account" would confirm that some account does have access, and
        # there is nothing they can do with that but go looking for it.
        if not user_auth.current_user():
            st.markdown(
                '<div style="text-align:center;color:var(--muted);font-size:13px">'
                'Signed-in accounts can track their own Brownlow picks from the '
                '<b>Live Tracker</b> and <b>Polls a Vote</b>.</div>',
                unsafe_allow_html=True,
            )
    st.stop()


# ════════════════════════════════════════════════════════════
# BETTING HUB pages
# ════════════════════════════════════════════════════════════
if _page in _BH_PAGES and _page != 'Predictions':
    betting_hub.render_page(_page)

# ════════════════════════════════════════════════════════════
# HOME (Brownlow overview)
# ════════════════════════════════════════════════════════════
if _page == 'Predictions':
    # Flush the page header + tab strip onto the app bg (#0a1017). theme.py gives
    # .title-bar a --surface fill/border and tints [data-testid="stTabs"] with
    # --surface; neutralise both for THIS page only via the .pred-flush marker so
    # the panels below (Model vs Market table, metric strips) stay boxed.
    st.markdown(
        '<style>'
        '.title-bar:has(.pred-flush){background:transparent !important;border:none !important;'
        'box-shadow:none !important;padding:0 !important;}'
        '[data-testid="stTabs"]:has(.pred-flush){background:transparent !important;'
        'border:none !important;box-shadow:none !important;}'
        '</style>'
        '<div class="title-bar"><span class="pred-flush" style="display:none"></span>'
        '<h2 style="color:#e9eef3;margin:0">Predictions</h2>'
        '<p style="color:var(--muted);margin:4px 0 0 0">2026 season overview · value finder</p></div>',
        unsafe_allow_html=True,
    )
    _home_tab, _vf_tab = st.tabs(["Home", "Value Finder"])

    with _home_tab:
        st.markdown('<span class="pred-flush" style="display:none"></span>', unsafe_allow_html=True)
        SEASON = 2026
        CURRENT_ROUND = _display_round(max_season_rounds, SEASON)

        df = load_season(SEASON)
        odds_df = load_best_odds()

        if df is not None and not df.empty:
            top5 = (
                df.groupby("Player_Name")["Exp_Total_Votes"]
                .sum()
                .reset_index()
                .sort_values("Exp_Total_Votes", ascending=False)
                .head(10)
            )
        else:
            top5 = pd.DataFrame(columns=["Player_Name", "Exp_Total_Votes"])

        leader_name  = top5.iloc[0]["Player_Name"] if len(top5) else "—"
        leader_votes = top5.iloc[0]["Exp_Total_Votes"] if len(top5) else 0

        rounds_remaining = 24 - CURRENT_ROUND
        season_pct = int((CURRENT_ROUND / 24) * 100)

        st.markdown(f"""
<div style="padding:20px 0 12px;animation:fadeSlideUp 500ms cubic-bezier(0.23,1,0.32,1) both;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
    <div style="width:7px;height:7px;border-radius:50%;background:var(--emerald);
                animation:pulse 2s ease-in-out infinite;"></div>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
                 letter-spacing:0.22em;text-transform:uppercase;color:var(--emerald);">
      Live · Round {CURRENT_ROUND}
    </span>
  </div>
  <h1 style="font-family:'Archivo',sans-serif;font-size:2.6rem;font-weight:900;
             color:var(--text);letter-spacing:-0.02em;margin:0 0 8px;line-height:1.05;">
    Cha Ching
  </h1>
  <p style="font-family:'IBM Plex Mono',monospace;color:var(--muted);font-size:12px;
            margin:0;max-width:560px;line-height:1.7;letter-spacing:0.02em;">
    Brownlow Medal predictor · 2026 season · XGBoost v4.0 &nbsp;·&nbsp;
    <span style="color:var(--text);font-weight:600;">MAE 0.095</span>
  </p>
</div>
""", unsafe_allow_html=True)

        st.markdown(f"""
<div style="margin-bottom:18px;animation:fadeSlideUp 500ms 80ms cubic-bezier(0.23,1,0.32,1) both;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
                 letter-spacing:0.18em;text-transform:uppercase;color:var(--muted);">Season progress</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);">
      R{CURRENT_ROUND} of 24 &nbsp;·&nbsp; {rounds_remaining} rounds to go
    </span>
  </div>
  <div style="height:6px;background:var(--hairline-strong);border-radius:3px;overflow:hidden;">
    <div style="height:100%;width:{season_pct}%;background:var(--emerald);border-radius:3px;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Shared lookups (best odds, market rank, team) ──
        _team_map = {}
        if df is not None and not df.empty and "Team" in df.columns:
            _team_map = dict(zip(df["Player_Name"], df["Team"]))

        _odds_best_map, _odds_bookie_map, _market_rank = {}, {}, {}
        if (odds_df is not None and not odds_df.empty
                and "player" in odds_df.columns and "best_odds" in odds_df.columns):
            _od = (odds_df.dropna(subset=["best_odds"])
                          .sort_values("best_odds", ascending=True)
                          .reset_index(drop=True))
            for _mr, _orow in _od.iterrows():
                _pl = _orow["player"]
                _odds_best_map[_pl] = float(_orow["best_odds"])
                _bk = _orow.get("best_bookie")
                _odds_bookie_map[_pl] = str(_bk) if pd.notna(_bk) else ""
                _market_rank[_pl] = int(_mr) + 1

        leader_team = str(_team_map.get(leader_name, "")) if leader_name != "—" else ""
        leader_odds = f"${_odds_best_map[leader_name]:.2f}" if leader_name in _odds_best_map else "—"

        # ── PART 1: hero winner + supporting metadata strip ──
        _HOME_HERO_CSS = """
.home-hero{font-family:'Archivo',sans-serif;margin:6px 0 0 0;animation:fadeSlideUp 500ms 140ms cubic-bezier(0.23,1,0.32,1) both;}
.home-hero .hh-row{display:flex;align-items:flex-start;justify-content:space-between;gap:32px;flex-wrap:wrap;}
.home-hero .hh-main{flex:1 1 320px;min-width:260px;}
.home-hero .hh-overline{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);margin-bottom:12px;}
.home-hero .hh-name{font-size:40px;font-weight:900;line-height:1.02;color:var(--gold);letter-spacing:-.01em;}
.home-hero .hh-meta{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);margin-top:12px;letter-spacing:.02em;}
.home-hero .hh-meta b{color:var(--text);font-weight:600;}
.home-hero .hh-strip{display:flex;align-items:stretch;flex:0 0 auto;}
.home-hero .hh-stat{display:flex;flex-direction:column;justify-content:center;padding:2px 24px;border-left:1px solid var(--line);}
.home-hero .hh-stat:first-child{border-left:none;padding-left:0;}
.home-hero .hh-stat-val{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:var(--text);line-height:1;}
.home-hero .hh-stat-lab{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-top:9px;}
.home-hero .hh-rule{height:1px;background:var(--line);margin:26px 0 0 0;}
"""
        st.markdown(
            f"<style>{_HOME_HERO_CSS}</style>"
            '<div class="home-hero"><div class="hh-row">'
            '<div class="hh-main">'
            '<div class="hh-overline">★ Predicted Winner</div>'
            f'<div class="hh-name">{leader_name}</div>'
            f'<div class="hh-meta">{leader_team} · <b>{leader_votes:.1f}</b> projected votes · <b>{leader_odds}</b> to win</div>'
            '</div>'
            '<div class="hh-strip">'
            '<div class="hh-stat"><div class="hh-stat-val">0.095</div><div class="hh-stat-lab" title="Mean absolute error — average votes the model misses by per player-game">MAE</div></div>'
            f'<div class="hh-stat"><div class="hh-stat-val">{rounds_remaining}</div><div class="hh-stat-lab">Rounds left</div></div>'
            '</div>'
            '</div><div class="hh-rule"></div></div>',
            unsafe_allow_html=True,
        )

        # ── PART 2: Model vs Market panel ──
        _HOME_MM_CSS = """
.home-mm{font-family:'Archivo',sans-serif;margin:22px 0 0 0;animation:fadeSlideUp 500ms 220ms cubic-bezier(0.23,1,0.32,1) both;}
.home-mm .mm-title{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);margin-bottom:14px;}
.home-mm .mm-grid{--mm-cols:34px 1fr 230px 116px 132px;}
.home-mm .mm-head,.home-mm .mm-row{display:grid;grid-template-columns:var(--mm-cols);gap:16px;align-items:center;}
.home-mm .mm-head{padding:0 4px 10px 4px;border-bottom:1px solid var(--hairline-strong);}
.home-mm .mm-head span{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);}
.home-mm .mm-head .r{text-align:right;}
.home-mm .mm-row{min-height:52px;padding:0 4px;border-bottom:1px solid var(--line);}
.home-mm .mm-rank{font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--muted);text-align:center;}
.home-mm .mm-player{display:flex;flex-direction:column;gap:3px;min-width:0;}
.home-mm .mm-name{font-family:'Archivo',sans-serif;font-weight:700;font-size:15px;color:var(--text);line-height:1.1;}
.home-mm .mm-team{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
.home-mm .mm-votes{display:flex;align-items:center;gap:10px;}
.home-mm .mm-track{flex:1;height:6px;background:var(--hairline-strong);border-radius:4px;overflow:hidden;}
.home-mm .mm-fill{height:100%;border-radius:4px;}
.home-mm .mm-vval{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;color:var(--text);min-width:32px;text-align:right;}
.home-mm .mm-odds{display:flex;flex-direction:column;gap:3px;text-align:right;}
.home-mm .mm-oval{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;color:var(--gold);}
.home-mm .mm-obk{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);}
.home-mm .mm-dash{font-family:'IBM Plex Mono',monospace;font-size:14px;color:var(--muted);text-align:right;}
.home-mm .mm-chip{display:inline-flex;align-items:center;font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:4px 10px;border-radius:99px;}
.home-mm .mm-chip.up{background:var(--emerald-dim);color:var(--emerald);}
.home-mm .mm-chip.flat{background:rgba(159,176,191,.12);color:var(--muted);}
.home-mm .mm-foot{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);margin-top:14px;line-height:1.7;letter-spacing:.02em;}
"""
        if not top5.empty:
            _mm_max = top5["Exp_Total_Votes"].max()
            _mm_rows = []
            for _rank, (_, _row) in enumerate(top5.iterrows(), start=1):
                _pname = _row["Player_Name"]
                _proj = float(_row["Exp_Total_Votes"])
                _pct = (_proj / _mm_max * 100) if _mm_max > 0 else 0
                _fill = "var(--emerald)" if _rank <= 3 else "var(--emerald-pack)"
                _team = str(_team_map.get(_pname, ""))
                _team_html = f'<span class="mm-team">{_team}</span>' if _team else ""

                # odds cell
                if _pname in _odds_best_map:
                    _bk = _odds_bookie_map.get(_pname, "")
                    _bk_html = f'<span class="mm-obk">{_bk}</span>' if _bk else ""
                    _odds_html = (f'<div class="mm-odds"><span class="mm-oval">'
                                  f'${_odds_best_map[_pname]:.2f}</span>{_bk_html}</div>')
                else:
                    _odds_html = '<div class="mm-dash">—</div>'

                # edge chip: market_rank − model_rank
                if _pname in _market_rank:
                    _edge = _market_rank[_pname] - _rank
                    if _edge >= 2:
                        _chip = f'<span class="mm-chip up">▲ +{_edge} value</span>'
                    elif _edge <= -2:
                        _chip = '<span class="mm-chip flat">▼ market</span>'
                    else:
                        _chip = '<span class="mm-chip flat">in line</span>'
                else:
                    _chip = ""  # no odds → skip edge chip

                _mm_rows.append(
                    '<div class="mm-row">'
                    f'<div class="mm-rank">{_rank}</div>'
                    f'<div class="mm-player"><span class="mm-name">{_pname}</span>{_team_html}</div>'
                    '<div class="mm-votes"><div class="mm-track">'
                    f'<div class="mm-fill" style="width:{_pct:.1f}%;background:{_fill};"></div></div>'
                    f'<span class="mm-vval">{_proj:.1f}</span></div>'
                    f'{_odds_html}'
                    f'<div class="mm-edge">{_chip}</div>'
                    '</div>'
                )
            st.markdown(
                f"<style>{_HOME_MM_CSS}</style>"
                '<div class="home-mm">'
                '<div class="mm-title">Model vs Market — Top 10</div>'
                '<div class="mm-grid">'
                '<div class="mm-head">'
                '<span style="text-align:center;">#</span><span>Player</span>'
                '<span>Projected Votes</span><span class="r">Best Odds</span><span>Model Edge</span>'
                '</div>'
                + "".join(_mm_rows)
                + '</div>'
                '<div class="mm-foot">'
                '▲ value — model rates higher than the market (potentially underpriced) &nbsp;·&nbsp; '
                '▼ market — market rates shorter than the model &nbsp;·&nbsp; '
                'in line — model and market agree'
                '</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        st.markdown("""
<div style="font-size:11px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;
            color:#4a5a6a;padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:14px;">
  Quick navigation
</div>""", unsafe_allow_html=True)

        nav_items = [
            ("📊", "Leaderboard",    "Full season rankings",  "#34d399"),
            ("👤", "Player Profile", "Deep dive any player",  "#4a90c4"),
            ("💰", "Value Finder",   "Model vs market odds",  "#f0b429"),
            ("🎯", "Cha Ching Tips", "Curated betting tips",  "#34d399"),
        ]
        cols = st.columns(4)
        for col, (icon, title, desc, color) in zip(cols, nav_items):
            with col:
                st.markdown(f"""
<div style="background:var(--surface);border:1px solid var(--line);border-radius:10px;
            padding:14px 16px;
            animation:fadeSlideUp 400ms 380ms cubic-bezier(0.23,1,0.32,1) both;
            transition:background 180ms ease-out,border-color 180ms ease-out;"
     onmouseover="this.style.background='var(--line)';this.style.borderColor='{color}'"
     onmouseout="this.style.background='var(--surface)';this.style.borderColor='var(--line)'">
  <div style="font-size:20px;margin-bottom:8px;">{icon}</div>
  <div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:3px;
              font-family:'Sora',sans-serif;">{title}</div>
  <div style="font-size:11px;color:#4a5a6a;">{desc}</div>
</div>""", unsafe_allow_html=True)

    with _vf_tab:
        top30_vf = predictions.head(30).copy()
        top30_vf['Model_Win_Prob'] = (top30_vf['Exp_Total_Votes'] / top30_vf['Exp_Total_Votes'].sum() * 100).round(1)
        scraped_odds = load_best_odds()

        if scraped_odds is not None and len(scraped_odds) > 0:
            st.success(f"{len(scraped_odds)} odds loaded from bookmakers")
            vtab1, vtab2 = st.tabs(["Auto Odds", "Manual Entry"])
        else:
            st.info("No scraped odds. Enter manually below.")
            vtab1, vtab2 = None, st.container()

        odds_data = []
        if vtab1 is not None:
            with vtab1:
                merged = top30_vf.merge(scraped_odds, left_on='Player_Name', right_on='player', how='left')
                merged['Bookie_Odds'] = merged['best_odds'].fillna(999)
                merged['Implied %'] = (100 / merged['Bookie_Odds']).round(1)
                merged['Edge %'] = (merged['Model_Win_Prob'] - merged['Implied %']).round(1)
                merged['Flag'] = merged['Edge %'].apply(
                    lambda e: 'Strong Value' if e > 5 else ('Value' if e > 2 else ('Watch' if e > 0 else 'Lay'))
                )
                merged = merged.sort_values('Edge %', ascending=False)
                _vf_disp = merged[['Player_Name', 'Team', 'Model_Win_Prob', 'Bookie_Odds', 'Implied %', 'Edge %', 'Flag']].rename(
                    columns={'Player_Name': 'Player', 'Model_Win_Prob': 'Model %', 'Bookie_Odds': 'Best Odds'})
                for col in _vf_disp.select_dtypes(include='float').columns:
                    _vf_disp[col] = _vf_disp[col].round(1)
                st.dataframe(_style_table(_vf_disp), width='stretch', hide_index=True)
                value_plays = merged[merged['Edge %'] > 2]
                if not value_plays.empty:
                    st.markdown('<div class="section-header">Value Plays</div>', unsafe_allow_html=True)
                    for _, row in value_plays.iterrows():
                        st.success(f"**{row['Player_Name']}** — Model: {row['Model_Win_Prob']:.1f}% | Bookie: {row['Implied %']:.1f}% | Edge: +{row['Edge %']:.1f}% | Odds: ${row['Bookie_Odds']:.1f}")

        manual_container = vtab2 if vtab1 is not None else vtab2
        with manual_container:
            st.markdown("Enter decimal odds for each player:")
            mcols = st.columns(3)
            for i, (_, row) in enumerate(top30_vf.iterrows()):
                with mcols[i % 3]:
                    default = float(max(2.0, round(100 / max(row['Model_Win_Prob'], 0.5), 1)))
                    odds = st.number_input(
                        f"{row['Player_Name']} ({row['Team']})",
                        min_value=1.01, max_value=1001.0, value=default, step=0.5,
                        key=f"be_odds_{i}",
                    )
                    odds_data.append({
                        'Player': row['Player_Name'], 'Team': row['Team'],
                        'Exp Votes': round(row['Exp_Total_Votes'], 1),
                        'Model %': row['Model_Win_Prob'],
                        'Odds': odds, 'Implied %': round(100 / odds, 1),
                    })
            if odds_data:
                odf = pd.DataFrame(odds_data)
                odf['Edge %'] = (odf['Model %'] - odf['Implied %']).round(1)
                odf['Flag'] = odf['Edge %'].apply(
                    lambda e: 'Strong Value' if e > 5 else ('Value' if e > 2 else ('Watch' if e > 0 else 'Lay'))
                )
                odf = odf.sort_values('Edge %', ascending=False)
                st.markdown('<div class="section-header">EV Analysis</div>', unsafe_allow_html=True)
                for col in odf.select_dtypes(include='float').columns:
                    odf[col] = odf[col].round(1)
                st.dataframe(_style_table(odf), width='stretch', hide_index=True)
                value = odf[odf['Edge %'] > 2]
                if not value.empty:
                    st.markdown('<div class="section-header">Value Plays</div>', unsafe_allow_html=True)
                    for _, row in value.iterrows():
                        st.success(f"**{row['Player']}** — Model: {row['Model %']:.1f}% | Bookie: {row['Implied %']:.1f}% | Edge: +{row['Edge %']:.1f}%")

# ════════════════════════════════════════════════════════════
# LEADERBOARD
# ════════════════════════════════════════════════════════════
if _page == 'Leaderboard':
    _lb_live_html = ' <span class="lb-live-pill">LIVE</span>' if is_2026 else ""
    _lbh_main, _lbh_season = st.columns([4, 1], vertical_alignment="bottom")
    with _lbh_main:
        st.markdown(
            f'<div class="lb-header">'
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            f'<h2 class="lb-title">{selected_season} Brownlow Leaderboard</h2>'
            f'{_lb_live_html}'
            f'</div>'
            f'<p class="lb-subtitle">'
            f'{"Projected votes through current round" if is_2026 else "Model predicted vs actual results"}'
            f'</p></div>',
            unsafe_allow_html=True,
        )
    with _lbh_season:
        # Season picker sits inline with the title (per-page key mirrors the
        # choice into season_by_page via _season_changed, like the other pages).
        st.selectbox(
            "Season", AVAILABLE_SEASONS,
            index=AVAILABLE_SEASONS.index(selected_season),
            key=f"_ctrl_season::{_page}",
            on_change=_season_changed,
            args=(_page,),
            label_visibility="collapsed",
        )

    # ── Shared data: projection, odds, form, bar domain, helpers ──
    _proj_floor, _proj_ceiling, has_fc = {}, {}, False
    if is_2026:
        _proj = load_season_projection()
        if _proj is not None and 'Floor_Projection' in _proj.columns:
            _proj_floor   = dict(zip(_proj['Player'], _proj['Floor_Projection']))
            _proj_ceiling = dict(zip(_proj['Player'], _proj['Ceiling_Projection']))
            has_fc = len(_proj_ceiling) > 0

    _odds_best, _odds_impl, has_odds = {}, {}, False
    if is_2026:
        _odds = load_best_odds()
        if _odds is not None and len(_odds) > 0:
            _odds_best = dict(zip(_odds['player'], _odds['best_odds']))
            _odds_impl = dict(zip(_odds['player'], _odds['implied_prob']))
            has_odds = True

    _fg = form_guide_dots(selected_season, n_rounds=3) if is_2026 else {}

    if has_fc:
        _ceil_vals = [float(v) for v in _proj_ceiling.values() if pd.notna(v)]
        _max_ceil = max(_ceil_vals) if _ceil_vals else 1.0
    else:
        _max_ceil = float(predictions['Exp_Total_Votes'].max() or 1.0)
    if _max_ceil <= 0:
        _max_ceil = 1.0

    _LB_ABBR = {
        "Adelaide": "ADEL", "Brisbane Lions": "BRIS", "Carlton": "CARL",
        "Collingwood": "COLL", "Essendon": "ESSE", "Fremantle": "FREO",
        "Geelong": "GEEL", "Gold Coast": "GCFC", "Greater Western Sydney": "GWS",
        "GWS": "GWS", "GWS Giants": "GWS", "Hawthorn": "HAWK", "Melbourne": "MELB",
        "North Melbourne": "NMFC", "Port Adelaide": "PORT", "Richmond": "RICH",
        "St Kilda": "STK", "Sydney": "SYD", "West Coast": "WCE",
        "Western Bulldogs": "WBD",
    }
    def _lb_abbr(t):
        return _LB_ABBR.get(str(t), str(t)[:4].upper())

    def _form_html(s):
        _m = {'🟢': 'lb-dot-on', '⚫': 'lb-dot-mid', '▫': 'lb-dot-off'}
        _d = ''.join(f'<span class="lb-dot {_m.get(ch, "lb-dot-off")}"></span>' for ch in str(s))
        return f'<span class="lb-form">{_d}</span>'

    def _lb_bar(floor, ceiling, exp, mini=False, labels=False):
        mc = _max_ceil if _max_ceil > 0 else 1.0
        fl = 0.0 if pd.isna(floor) else float(floor)
        ex = 0.0 if pd.isna(exp) else float(exp)
        ce = ex if pd.isna(ceiling) else float(ceiling)
        left  = max(0.0, min(100.0, fl / mc * 100))
        right = max(0.0, min(100.0, ce / mc * 100))
        width = max(0.6, right - left)
        mark  = max(0.0, min(100.0, ex / mc * 100))
        cls = 'lb-bar mini' if mini else 'lb-bar'
        track = (f'<div class="lb-track"><div class="lb-fill" style="left:{left:.2f}%;width:{width:.2f}%"></div>'
                 f'<div class="lb-marker" style="left:{mark:.2f}%"></div></div>')
        if labels:
            return (f'<div class="{cls}"><div class="lb-bar-wrap">'
                    f'<span class="lb-bar-lo">{fl:.0f}</span>{track}'
                    f'<span class="lb-bar-hi">{ce:.0f}</span></div></div>')
        return f'<div class="{cls}">{track}</div>'

    def _lb_fc_bar(floor, ceiling, exp, max_ceil):
        """Floor–Ceiling cell bar on a SHARED domain [0, max_ceil].
        Dark track + emerald segment + emerald dot marker; floor/ceiling
        labels sit under the segment ends, not the cell edges."""
        mc = float(max_ceil) if max_ceil and max_ceil > 0 else 1.0
        fl = 0.0 if pd.isna(floor) else float(floor)
        ex = 0.0 if pd.isna(exp) else float(exp)
        ce = ex if pd.isna(ceiling) else float(ceiling)
        left  = max(0.0, min(100.0, fl / mc * 100))
        right = max(0.0, min(100.0, ce / mc * 100))
        width = max(0.0, right - left)
        mark  = max(0.0, min(100.0, ex / mc * 100))
        return (
            f'<div class="lb-fc"><div class="lb-fc-track">'
            f'<div class="lb-fc-seg" style="left:{left:.2f}%;width:{width:.2f}%"></div>'
            f'<div class="lb-fc-dot" style="left:{mark:.2f}%"></div></div>'
            f'<div class="lb-fc-labels">'
            f'<span class="lb-fc-lo" style="left:{left:.2f}%">{fl:.0f}</span>'
            f'<span class="lb-fc-hi" style="left:{right:.2f}%">{ce:.0f}</span>'
            f'</div></div>'
        )

    _LB_BAR_CSS_TMPL = """
SCOPE .lb-bar{width:100%;}
SCOPE .lb-track{position:relative;height:6px;background:var(--hairline-strong);border-radius:4px;}
SCOPE .lb-bar.mini .lb-track{height:4px;}
SCOPE .lb-fill{position:absolute;top:0;height:100%;background:var(--emerald-track);border-radius:4px;}
SCOPE .lb-marker{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;background:var(--emerald);transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--bg);}
SCOPE .lb-bar-wrap{display:flex;align-items:center;gap:8px;}
SCOPE .lb-bar-wrap .lb-track{flex:1;}
SCOPE .lb-bar-lo,SCOPE .lb-bar-hi{font-size:10px;color:var(--muted);min-width:20px;font-family:'IBM Plex Mono',monospace;}
SCOPE .lb-bar-lo{text-align:right;}
"""
    def _bar_css(scope):
        return _LB_BAR_CSS_TMPL.replace('SCOPE', scope)

    _LB_SPOT_CSS = ("""
.lb-spotlight{font-family:'Archivo',sans-serif;margin:6px 0 26px 0;}
.lb-spotlight .lb-hero{display:flex;align-items:flex-start;justify-content:space-between;gap:32px;flex-wrap:wrap;}
.lb-spotlight .lb-hero-main{flex:1 1 280px;min-width:240px;}
.lb-spotlight .lb-hero-overline{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);margin-bottom:10px;}
.lb-spotlight .lb-hero-name{font-size:42px;font-weight:900;line-height:1.02;color:var(--emerald);letter-spacing:-.01em;}
.lb-spotlight .lb-hero-meta{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);margin-top:10px;}
.lb-spotlight .lb-hero-proj{flex:0 0 300px;max-width:340px;}
.lb-spotlight .lb-proj-label{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
.lb-spotlight .lb-proj-value{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:600;color:var(--text);line-height:1;margin-bottom:14px;}
.lb-spotlight .lb-hero-rule{height:1px;background:var(--line);margin:22px 0 18px 0;}
.lb-spotlight .lb-chasers{display:grid;grid-template-columns:1fr 1fr;gap:30px;}
.lb-spotlight .lb-chaser-top{display:flex;align-items:center;gap:9px;margin-bottom:5px;}
.lb-spotlight .lb-badge{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;background:rgba(159,176,191,.16);color:var(--steel);border:1px solid var(--hairline-strong);flex:none;}
.lb-spotlight .lb-chaser-name{font-size:17px;font-weight:700;color:var(--text);}
.lb-spotlight .lb-chaser-meta{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-bottom:9px;}
""" + _bar_css('.lb-spotlight')).replace('\n', '')

    # ── PART 1: leader spotlight ──
    top3 = predictions.head(min(3, len(predictions)))
    _r1 = top3.iloc[0]
    _n1 = str(_r1['Player_Name']); _t1 = str(_r1['Team'])
    _g1 = int(_r1['Games']) if pd.notna(_r1['Games']) else 0
    _p1 = float(_r1['Avg_Poll_Prob']) * 100 if pd.notna(_r1['Avg_Poll_Prob']) else 0.0
    _e1 = float(_r1['Exp_Total_Votes'])
    _hero_bar = (_lb_bar(_proj_floor.get(_n1, 0), _proj_ceiling.get(_n1, _e1), _e1)
                 if has_fc else _lb_bar(0, _e1, _e1))
    _proj_lbl = "PROJECTED VOTES" if is_2026 else "EXPECTED VOTES"

    _chasers = ''
    for _i in (1, 2):
        if _i < len(top3):
            _rr = top3.iloc[_i]
            _nm = str(_rr['Player_Name']); _tm = str(_rr['Team']); _ex = float(_rr['Exp_Total_Votes'])
            _bar = (_lb_bar(_proj_floor.get(_nm, 0), _proj_ceiling.get(_nm, _ex), _ex, mini=True)
                    if has_fc else _lb_bar(0, _ex, _ex, mini=True))
            _chasers += (
                f'<div class="lb-chaser">'
                f'<div class="lb-chaser-top"><span class="lb-badge">{_i + 1}</span>'
                f'<span class="lb-chaser-name">{_nm}</span></div>'
                f'<div class="lb-chaser-meta">{_tm} · {_ex:.1f} exp</div>'
                f'{_bar}</div>'
            )

    st.markdown(
        f'<div class="lb-spotlight"><style>{_LB_SPOT_CSS}</style>'
        f'<div class="lb-hero">'
        f'<div class="lb-hero-main">'
        f'<div class="lb-hero-overline">★ #1 PREDICTED</div>'
        f'<div class="lb-hero-name">{_n1}</div>'
        f'<div class="lb-hero-meta">{_t1} · {_g1} games · {_p1:.0f}% poll rate</div>'
        f'</div>'
        f'<div class="lb-hero-proj">'
        f'<div class="lb-proj-label">{_proj_lbl}</div>'
        f'<div class="lb-proj-value">{_e1:.1f}</div>'
        f'{_hero_bar}'
        f'</div></div>'
        f'<div class="lb-hero-rule"></div>'
        f'<div class="lb-chasers">{_chasers}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="lb-section-label">Full Leaderboard</div>', unsafe_allow_html=True)
    # Keyed container, so the label treatment is scoped by .st-key-lb_filters
    # instead of a marker div inside the first column. The marker cost a 16px
    # misalignment: see the .st-key-lb_filters rule in the CSS block for the
    # measurement. Column ratios are unchanged.
    with st.container(key="lb_filters"):
        _cc1, _cc_team, _cc2 = st.columns([4, 1.4, 1])
        with _cc1:
            search = st.text_input("SEARCH PLAYER", "")
        with _cc_team:
            # Club list comes from the loaded frame, never a hardcoded eighteen.
            # The competition has not always had eighteen clubs and this page
            # serves every season in AVAILABLE_SEASONS: 2007 and 2010 hold
            # sixteen, 2011 seventeen once Gold Coast enter, eighteen only from
            # 2012. A fixed list would offer four clubs that did not exist on a
            # 2007 leaderboard. _fix_team_names has already run in load_season,
            # so the values here are canonical (Kangaroos read as North
            # Melbourne, Footscray as Western Bulldogs) and match _LB_ABBR's keys.
            _team_opts = ['All'] + sorted(predictions['Team'].dropna().astype(str).unique())
            team_pick = st.selectbox("CLUB", _team_opts, index=0)
        with _cc2:
            show_n = st.selectbox("SHOW", [20, 50, 100, 200], index=0)

    # ── Round-on-round movement (2026 only) ──────────────────
    _move_map = {}
    if is_2026 and game_df is not None:
        _max_rnd = int(game_df['Round_num'].max())
        _cur_rnd_votes = (
            game_df[game_df['Round_num'] == _max_rnd]
            .groupby('Player_Name')['Exp_Votes'].sum()
        )
        _all = predictions[['Player_Name', 'Exp_Total_Votes']].copy()
        _all['Prev_Total'] = _all['Exp_Total_Votes'] - _all['Player_Name'].map(_cur_rnd_votes).fillna(0)
        _all['Curr_Rank'] = range(1, len(_all) + 1)
        _prev_ranks = _all.sort_values('Prev_Total', ascending=False).reset_index(drop=True)
        _prev_ranks['Prev_Rank'] = range(1, len(_prev_ranks) + 1)
        _merged = _all.merge(_prev_ranks[['Player_Name', 'Prev_Rank']], on='Player_Name')
        _merged['Move'] = _merged['Prev_Rank'] - _merged['Curr_Rank']
        _move_map = dict(zip(_merged['Player_Name'], _merged['Move']))

    # Rank is positional over the FULL leaderboard and is assigned BEFORE the
    # search filter and Show N, so a searched player carries their real standing
    # through instead of being renumbered from 1. No sort here: predictions
    # already arrives sorted descending on Exp_Total_Votes.
    display = predictions.copy()
    display.insert(0, 'Rank', range(1, len(display) + 1))
    # Club position is assigned over the WHOLE club, alongside Rank and before
    # either filter, for exactly the reason Rank is: searching "daicos" inside
    # Collingwood must leave Josh on his real club position of 3, not renumber
    # him to 2 because the man above him was filtered out. predictions arrives
    # sorted descending on Exp_Total_Votes and nothing here re-sorts, so a
    # per-club running count is the club order.
    display.insert(1, 'ClubRank', display.groupby('Team', sort=False).cumcount() + 1)
    if search:
        display = display[display['Player_Name'].str.contains(search, case=False, na=False)]
    if team_pick != 'All':
        display = display[display['Team'].astype(str) == team_pick]
    display = display.head(show_n).copy()

    # Empty result gets a message instead of an empty table. NOT st.stop():
    # this block is followed by the responsible-gambling footer, which the guard
    # at the foot of the page renders for every non-Betting-Hub page, and
    # stopping here would silently drop it. The table emission below is guarded
    # instead, so the rest of the page still renders.
    _lb_rows_exist = not display.empty
    if not _lb_rows_exist:
        _bits = []
        if team_pick != 'All':
            _bits.append(f'{team_pick}')
        if search:
            _bits.append(f'a name matching "{search}"')
        st.info(
            f"No {selected_season} players found for {' with '.join(_bits)}."
            if _bits else f"No {selected_season} players to show."
        )
    _max_exp = float(display['Exp_Total_Votes'].max()) if len(display) else 1.0
    if _max_exp <= 0:
        _max_exp = 1.0

    # Shared Floor–Ceiling bar domain = max ceiling across the rows CURRENTLY
    # displayed (after search + Show N), recomputed each render so bars rescale.
    if is_2026 and has_fc:
        _disp_ceils = [_proj_ceiling.get(p) for p in display['Player_Name']]
        _disp_ceils = [float(c) for c in _disp_ceils if c is not None and pd.notna(c)]
        _tbl_maxceil = max(_disp_ceils) if _disp_ceils else 1.0
    else:
        _tbl_maxceil = 1.0

    # ── PART 3: full leaderboard table ──
    _LB_TBL_CSS = ("""
.lb-table .lb-tbl-wrap{overflow-x:auto;}
.lb-table .lb-tbl{width:100%;border-collapse:collapse;font-family:'IBM Plex Mono',monospace;}
.lb-table .lb-tbl th{font-size:10px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--hairline-strong);text-align:right;white-space:nowrap;}
.lb-table .lb-tbl th.lft{text-align:left;}
.lb-table .lb-tbl td{font-size:13px;padding:8px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;color:var(--steel);}
.lb-table .lb-tbl td.lft{text-align:left;}
.lb-table .lb-tbl th.grp-start,.lb-table .lb-tbl td.grp-start{border-left:1px solid var(--hairline-strong);}
.lb-table .lb-tbl tr.lb-leader{background:rgba(52,211,153,.04);}
.lb-table .lb-rank{color:var(--text);font-weight:600;}
.lb-table .lb-clubrank{color:var(--muted);font-weight:600;}
.lb-table .lb-up{color:var(--emerald);font-size:10px;margin-left:4px;}
.lb-table .lb-down{color:#f87171;font-size:10px;margin-left:4px;}
.lb-table .lb-exp{font-weight:700;color:var(--text);}
.lb-table .lb-pname{font-family:'Archivo',sans-serif;font-size:14px;font-weight:600;color:var(--text);}
.lb-table .lb-ttag{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-left:7px;}
.lb-table .lb-form{display:inline-flex;gap:3px;align-items:center;}
.lb-table .lb-dot{width:7px;height:7px;border-radius:50%;display:inline-block;}
.lb-table .lb-dot-on{background:var(--emerald);}
.lb-table .lb-dot-mid{background:rgba(52,211,153,.45);}
.lb-table .lb-dot-off{background:var(--muted);opacity:.4;}
.lb-table .lb-tbl td.fc-cell{min-width:160px;}
.lb-table .lb-fc{width:100%;}
.lb-table .lb-fc-track{position:relative;height:6px;background:var(--surface-2);border:1px solid var(--hairline-strong);border-radius:999px;box-sizing:border-box;}
.lb-table .lb-fc-seg{position:absolute;top:0;height:100%;background:var(--emerald-track);border-radius:999px;}
.lb-table .lb-fc-dot{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;background:var(--emerald);transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--bg);}
.lb-table .lb-fc-labels{position:relative;height:12px;margin-top:4px;}
.lb-table .lb-fc-lo,.lb-table .lb-fc-hi{position:absolute;top:0;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);transform:translateX(-50%);white-space:nowrap;}
""").replace('\n', '')

    # The club-position column exists only while a club is selected. On "All" it
    # would be identical to Rank, so it is dropped rather than duplicated.
    _show_club_rank = team_pick != 'All'
    _rank_heads = [('Rank', 'lft')] + ([('#', 'lft')] if _show_club_rank else [])
    if is_2026:
        _heads = _rank_heads + [('Player', 'lft'), ('GP', ''), ('Form', 'lft'), ('Exp Votes', '')]
        if has_fc:
            _heads.append(('Floor–Ceiling', 'lft'))
        _heads += [('Poll %', ''), ('3V Games', '')]
        if has_odds:
            _heads += [('Best Odds', 'grp-start'), ('Mkt %', '')]
    else:
        _heads = _rank_heads + [('Player', 'lft'), ('GP', ''), ('Exp Votes', ''),
                                ('Actual', ''), ('Diff', ''), ('Poll %', ''), ('3V Games', '')]

    def _th(lbl, cls):
        return f'<th class="{cls}">{lbl}</th>' if cls else f'<th>{lbl}</th>'
    _ths = ''.join(_th(_l, _c) for _l, _c in _heads)

    _rows = []
    for _, _row in display.iterrows():
        _name = str(_row['Player_Name']); _team = str(_row['Team'])
        _rank = int(_row['Rank'])
        _exp  = float(_row['Exp_Total_Votes'])
        _poll = float(_row['Avg_Poll_Prob']) * 100 if pd.notna(_row['Avg_Poll_Prob']) else 0.0
        _gp   = int(_row['Games']) if pd.notna(_row['Games']) else 0
        _tvg  = float(_row['Exp_3vote_games']) if pd.notna(_row['Exp_3vote_games']) else 0.0
        _mv = _move_map.get(_name, 0) if _move_map else 0
        if _mv and _mv > 0:
            _arrow = f'<span class="lb-up">▲{int(_mv)}</span>'
        elif _mv and _mv < 0:
            _arrow = f'<span class="lb-down">▼{int(abs(_mv))}</span>'
        else:
            _arrow = ''
        _a = 0.22 * (_exp / _max_exp)
        _cells = [
            f'<td class="lft"><span class="lb-rank">{_rank}</span>{_arrow}</td>',
        ]
        if _show_club_rank:
            _cells.append(
                f'<td class="lft"><span class="lb-clubrank">{int(_row["ClubRank"])}</span></td>')
        _cells += [
            f'<td class="lft"><span class="lb-pname">{_name}</span><span class="lb-ttag">{_lb_abbr(_team)}</span></td>',
            f'<td>{_gp}</td>',
        ]
        if is_2026:
            _cells.append(f'<td class="lft">{_form_html(_fg.get(_name, "▫▫▫"))}</td>')
        _cells.append(f'<td class="lb-exp" style="background:rgba(52,211,153,{_a:.3f})">{_exp:.1f}</td>')
        if is_2026 and has_fc:
            _fl = _proj_floor.get(_name, float("nan")); _ce = _proj_ceiling.get(_name, float("nan"))
            _cells.append(f'<td class="lft fc-cell">{_lb_fc_bar(_fl, _ce, _exp, _tbl_maxceil)}</td>')
        if not is_2026:
            _act = int(_row['Actual_Votes']) if pd.notna(_row['Actual_Votes']) else 0
            _cells.append(f'<td>{_act}</td>')
            _cells.append(f'<td>{(_exp - _act):+.1f}</td>')
        _cells.append(f'<td>{_poll:.1f}%</td>')
        _cells.append(f'<td>{_tvg:.1f}</td>')
        if is_2026 and has_odds:
            _bo = _odds_best.get(_name); _mk = _odds_impl.get(_name)
            _bo_s = f'${float(_bo):.1f}' if _bo is not None and pd.notna(_bo) else '—'
            _mk_s = f'{float(_mk):.0f}%' if _mk is not None and pd.notna(_mk) else '—'
            _cells.append(f'<td class="grp-start">{_bo_s}</td>')
            _cells.append(f'<td>{_mk_s}</td>')
        _tr_cls = ' class="lb-leader"' if _rank == 1 else ''
        _rows.append(f'<tr{_tr_cls}>{"".join(_cells)}</tr>')

    if _lb_rows_exist:
        st.markdown(
            f'<div class="lb-table"><style>{_LB_TBL_CSS}</style>'
            f'<div class="lb-tbl-wrap"><table class="lb-tbl">'
            f'<thead><tr>{_ths}</tr></thead><tbody>{"".join(_rows)}</tbody>'
            f'</table></div></div>',
            unsafe_allow_html=True,
        )
    if is_2026 and _fg and _lb_rows_exist:
        st.caption("Form (last 3 rounds): emerald = predicted to poll (≥30%) · grey = quiet · faint = did not play")

# ── H2H votes (Compare tab) ──────────────────────────────────
# Poll_Prob at or above which a player counts as "likely to poll" in a round.
# 0.35 sits just above the Form-guide dot threshold (0.30) so the ledger flags
# genuine swing rounds rather than every mildly live game.
H2H_POLL_LIKELY = 0.35
# Rounds shown in the ledger before the rest move into the "All rounds" expander.
H2H_LEDGER_ROWS = 8
# Swing chips in the Live Tracker panel before the rest collapse into "+N".
# Three, not five, because the chips now carry the beneficiary's name: a long
# one ("R19 BONTEMPELLI", ~93px at 9px DM Mono) fits three to a row in Zone 3's
# .85fr rail at 1280-1500px, and five would wrap to a second row. Shrinking the
# font below 9px instead was rejected — it is already the smallest type here.
H2H_LIVE_CHIPS = 3


# The four helpers below are module level because BOTH the Compare tab and the
# Live Tracker's H2H panel need them, and the tracker runs on a page where the
# Player Profile block never executes. They are pure: no session state, no
# frames captured, nothing Streamlit-aware.

def _h2h_num(row, col):
    """A numeric cell as float, with an absent row or NaN reading as 0.0."""
    if row is None:
        return 0.0
    _x = row.get(col)
    return float(_x) if pd.notna(_x) else 0.0


def _h2h_pmf(row):
    """Vote pmf over {0,1,2,3} from P_1/P_2/P_3. An absent row is a certain 0,
    which is what a DNP or bye round means — those rows never exist upstream."""
    if row is None:
        return np.array([1.0, 0.0, 0.0, 0.0])
    _p1 = _h2h_num(row, 'P_1')
    _p2 = _h2h_num(row, 'P_2')
    _p3 = _h2h_num(row, 'P_3')
    return np.array([max(0.0, 1.0 - _p1 - _p2 - _p3), _p1, _p2, _p3])


def _h2h_total_dist(rmap, axis, certain=None):
    """Exact season-total distribution: convolve the per-round pmfs.

    No simulation — 3 votes x ~23 rounds is a tiny support. `axis` is the round
    axis to fold over (the union of both players' rounds), passed in rather than
    closed over so the Live Tracker can supply its own.

    `certain` optionally maps a round to a known vote count, replacing that
    round's model pmf with a point mass. The tracker uses it for rounds the
    count has already reached; the Compare tab leaves it None.
    """
    _d = np.array([1.0])
    for _rn in axis:
        if certain is not None and _rn in certain:
            _pt = np.zeros(4)
            _pt[max(0, min(3, int(certain[_rn])))] = 1.0
            _d = np.convolve(_d, _pt)
        else:
            _d = np.convolve(_d, _h2h_pmf(rmap.get(_rn)))
    return _d


def _h2h_short_pair(n1, n2):
    """Shortest labels that still tell these two players apart.

    A bare surname reads best, but two different players can share one —
    upstream only appends '(Team)' for genuine fitzRoy-ID collisions, so
    'Ryan' v 'Ryan' is reachable with plain names. Widen both labels together,
    only as far as needed: surname, then initial + surname, then the full given
    name. Shared initials are why the third rung exists (Luke / Liam Ryan)."""
    def _base(_n):
        return str(_n).split(' (')[0].strip()

    def _sur(_n):
        _b = _base(_n)
        return _b.split()[-1] if _b else str(_n)

    def _init(_n):
        _p = _base(_n).split()
        return f"{_p[0][0]}. {_p[-1]}" if len(_p) > 1 else _sur(_n)

    for _form in (_sur, _init, _base):
        _a, _b = _form(n1), _form(n2)
        if _a != _b:
            return _a, _b
    # Identical full names — only reachable in the disambiguated 'Name (Team)'
    # form, where the suffix is the differentiator.
    return str(n1), str(n2)


def _h2h_classify(same_game, pp1, pp2, s1, s2):
    """One round's (kind, owner, label). pp is None exactly when that player
    did not play. Owner is 1, 2 or None, and is what the chip colours read —
    never the label, which two players sharing a surname would make ambiguous.
    """
    if same_game:
        return 'SAME GAME', None, 'SAME GAME'

    _hot1 = pp1 is not None and pp1 >= H2H_POLL_LIKELY
    _hot2 = pp2 is not None and pp2 >= H2H_POLL_LIKELY

    if pp1 is None or pp2 is None:
        _live = _hot2 if pp1 is None else _hot1
        _who  = s2 if pp1 is None else s1
        if _live:
            return 'FREE', (2 if pp1 is None else 1), f'FREE &rarr; {_who}'
        return 'DEAD', None, 'DEAD'
    if _hot1 and _hot2:
        return 'CONTESTED', None, 'CONTESTED'
    if _hot1:
        return 'SWING', 1, f'SWING &rarr; {s1}'
    if _hot2:
        return 'SWING', 2, f'SWING &rarr; {s2}'
    return 'DEAD', None, 'DEAD'

# ════════════════════════════════════════════════════════════
# PLAYER PROFILE
# ════════════════════════════════════════════════════════════
if _page == 'Player Profile':
    if game_df is None:
        st.error("No game-level data found.")
    else:
        efficiency = compute_player_efficiency_career() if is_career else compute_player_efficiency(selected_season)
        players = sorted(predictions['Player_Name'].tolist())
        _pp_psel, _pp_ssel = st.columns([4, 1])
        with _pp_psel:
            selected_player = st.selectbox("Select player", players, key="profile_player")
        with _pp_ssel:
            # Season selector sits next to the player name (per-page state).
            # Player Profile alone offers "Career" — the whole-career view.
            _pp_season_opts = [CAREER] + AVAILABLE_SEASONS
            st.selectbox(
                "Season", _pp_season_opts,
                index=_pp_season_opts.index(selected_season),
                key=f"_ctrl_season::{_page}",
                on_change=_season_changed,
                args=(_page,),
            )

        _tab_prof, _tab_dna, _tab_compare = st.tabs(["Profile", "DNA", "Compare"])

        # ── Profile tab ───────────────────────────────────────
        with _tab_prof:
            player_games = game_df[game_df['Player_Name'] == selected_player].copy()
            # Career view spans many seasons → order chronologically; a single
            # season just orders by round.
            _sort_keys = ['Season', 'Round_num'] if is_career else ['Round_num']
            player_games = player_games.sort_values(_sort_keys)
            pred_row = predictions[predictions['Player_Name'] == selected_player]

            if not pred_row.empty:
                row = pred_row.iloc[0]

                # Strip stats computed from the player's real per-round columns
                _games = len(player_games)
                if _games:
                    _avg_votes = player_games['Exp_Votes'].mean()
                    _avg_poll = player_games['Poll_Prob'].mean() * 100
                    _best = player_games.loc[player_games['Poll_Prob'].idxmax()]
                    if is_career:
                        _best_round_lbl = f"{int(_best['Season'])} R{_display_round(_best['Round_num'], _best['Season'])}"
                    else:
                        _best_round_lbl = f"R{_display_round(_best['Round_num'], selected_season)}"
                else:
                    _avg_votes = 0.0
                    _avg_poll = 0.0
                    _best_round_lbl = "—"
                if is_career:
                    _n_seasons = int(player_games['Season'].nunique())
                    _meta_str = f'{row["Team"]} · Career · {_n_seasons} seasons'
                else:
                    _meta_str = f'{row["Team"]} · {selected_season} season'

                st.markdown(f"""
<style>
/* Player Profile sits flush on the app background — neutralise the global
   stTabs surface panel (theme.py) for this page only, keyed off .pp-identity. */
[data-testid="stTabs"]:has(.pp-identity) {{
    background:transparent !important;
    border:none !important;
}}
.pp-identity {{
    display:flex; justify-content:space-between; align-items:flex-end;
    gap:24px; flex-wrap:wrap;
    border-bottom:1px solid var(--line);
    padding:4px 0 18px; margin-bottom:18px;
}}
.pp-identity .pp-name {{
    font-family:'Archivo',sans-serif; font-size:42px; font-weight:900;
    line-height:1; letter-spacing:-.02em; color:var(--text); margin:0;
}}
.pp-identity .pp-meta {{
    font-family:'IBM Plex Mono',monospace; font-size:12px;
    letter-spacing:.04em; color:var(--steel); margin-top:12px;
}}
.pp-strip {{ display:flex; align-items:stretch; }}
.pp-strip .pp-item {{ padding:0 18px; text-align:right; }}
.pp-strip .pp-item:first-child {{ padding-left:0; }}
.pp-strip .pp-item:last-child {{ padding-right:0; }}
.pp-strip .pp-item + .pp-item {{ border-left:1px solid var(--hairline-strong); }}
.pp-strip .pp-val {{
    font-family:'IBM Plex Mono',monospace; font-size:22px; font-weight:600;
    line-height:1.1; color:var(--steel);
}}
.pp-strip .pp-item.pp-head .pp-val {{ color:var(--text); }}
.pp-strip .pp-lbl {{
    font-family:'IBM Plex Mono',monospace; font-size:9px; font-weight:500;
    letter-spacing:.16em; text-transform:uppercase; color:var(--muted); margin-top:6px;
}}
</style>
<div class="pp-identity">
  <div class="pp-id-left">
    <div class="pp-name">{selected_player}</div>
    <div class="pp-meta">{_meta_str}</div>
  </div>
  <div class="pp-strip">
    <div class="pp-item pp-head"><div class="pp-val">{_games}</div><div class="pp-lbl">Games</div></div>
    <div class="pp-item"><div class="pp-val">{_avg_votes:.2f}</div><div class="pp-lbl">Avg exp votes</div></div>
    <div class="pp-item"><div class="pp-val">{_best_round_lbl}</div><div class="pp-lbl">Best Round</div></div>
    <div class="pp-item"><div class="pp-val">{_avg_poll:.1f}%</div><div class="pp-lbl">Avg Poll</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

            if not player_games.empty:
                # Colour bars off the player's own poll-probability distribution:
                # strongest rounds emerald, mid rounds emerald_pack, low faint steel.
                _poll_pct = (player_games['Poll_Prob'] * 100)
                _pmax = _poll_pct.max()
                _pmed = _poll_pct.median()

                def _vote_color(v):
                    if _pmax <= 0:
                        return 'rgba(159,176,191,.22)'
                    if v >= 0.6 * _pmax:
                        return '#34d399'
                    if v >= _pmed:
                        return 'rgba(52,211,153,.45)'
                    return 'rgba(159,176,191,.22)'

                _vote_colors = [_vote_color(v) for v in _poll_pct]

                # X-axis differs by mode: a single season uses the AFL round
                # number; career uses a chronological game index with season
                # labels on the axis and Season·Round in the tooltip.
                if is_career:
                    _x = list(range(len(player_games)))
                    _seasons_order = player_games['Season'].astype(int).tolist()
                    _rounds_order = _display_rounds(player_games)
                    _seen = {}
                    for _i, _s in enumerate(_seasons_order):
                        _seen.setdefault(_s, _i)
                    _xaxis_cfg = dict(title='Season', tickmode='array',
                                      tickvals=list(_seen.values()),
                                      ticktext=[str(s) for s in _seen])
                    _customdata = list(zip(_seasons_order, _rounds_order))
                    _hover_pp = 'Season %{customdata[0]} · R%{customdata[1]}<br>Poll %{y:.1f}%<extra></extra>'
                    _hover_stat = 'Season %{customdata[0]} · R%{customdata[1]}<br>%{y}<extra></extra>'
                    _traj_caption = 'poll probability across career'
                    _avg_word = 'career'
                else:
                    _x = _display_rounds(player_games)
                    _xaxis_cfg = dict(title='Round', dtick=1)
                    _customdata = None
                    _hover_pp = 'Round %{x}<br>Poll %{y:.1f}%<extra></extra>'
                    _hover_stat = 'Round %{x}<br>%{y}<extra></extra>'
                    _traj_caption = 'poll probability by round'
                    _avg_word = 'season'

                st.markdown(
                    '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                    'font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--steel);'
                    'border-bottom:1px solid var(--line);padding-bottom:8px;margin:8px 0 16px;'
                    'display:flex;align-items:baseline;gap:12px;">VOTE TRAJECTORY'
                    '<span style="font-size:9px;font-weight:400;letter-spacing:.04em;'
                    f'text-transform:none;color:var(--muted);">{_traj_caption}</span></div>',
                    unsafe_allow_html=True,
                )

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=_x, y=_poll_pct.round(1),
                    name='Poll Probability %', marker_color=_vote_colors,
                    customdata=_customdata,
                    hovertemplate=_hover_pp,
                ))
                fig.update_layout(
                    xaxis=_xaxis_cfg,
                    yaxis=dict(title='Poll Probability (%)', rangemode='tozero'),
                    showlegend=False, margin=dict(t=20, b=40), bargap=0.35,
                    hovermode='x unified',
                )
                fig = apply_chart_theme(fig)
                fig.update_xaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
                fig.update_yaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
                st.plotly_chart(fig, width='stretch', key="chart_003", config=PLOTLY_TOUCH_CONFIG)

                st.markdown(
                    '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                    'font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--steel);'
                    'border-bottom:1px solid var(--line);padding-bottom:8px;margin:8px 0 16px;'
                    f'display:flex;align-items:baseline;gap:12px;">{"STAT OVER CAREER" if is_career else "STAT BY ROUND"}'
                    '<span style="font-size:9px;font-weight:400;letter-spacing:.04em;'
                    'text-transform:none;color:var(--muted);">colour marks above-average games</span></div>',
                    unsafe_allow_html=True,
                )
                stat_choice = st.selectbox("Stat to show",
                    ['Disposals', 'Coaches_Votes', 'Goals', 'Contested.Possessions', 'Clearances', 'Kicks'],
                    key="profile_stat")

                # Average of the selected stat (career or season); colour bars above/below it.
                _stat_series = player_games[stat_choice]
                _stat_avg = _stat_series.mean()
                _stat_colors = ['#34d399' if v >= _stat_avg else 'rgba(159,176,191,.22)' for v in _stat_series]

                st.markdown(
                    '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:9px;'
                    'letter-spacing:.08em;color:var(--muted);display:flex;gap:18px;margin:2px 0 12px;">'
                    '<span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;'
                    'background:#34d399;margin-right:6px;vertical-align:middle;"></span>above average</span>'
                    '<span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;'
                    'background:rgba(159,176,191,.22);margin-right:6px;vertical-align:middle;"></span>below average</span>'
                    '<span><span style="display:inline-block;width:14px;height:0;border-top:2px dashed #f0b429;'
                    f'margin-right:6px;vertical-align:middle;"></span>{_avg_word} average</span></div>',
                    unsafe_allow_html=True,
                )

                _stat_label = stat_choice.replace('.', ' ').replace('_', ' ')
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=_x, y=_stat_series,
                    name=_stat_label, marker_color=_stat_colors,
                    customdata=_customdata,
                    hovertemplate=_hover_stat,
                ))
                fig2.add_hline(
                    y=_stat_avg, line=dict(color='#f0b429', width=1.5, dash='dash'),
                    annotation_text=f"avg {_stat_avg:.1f}", annotation_position="top left",
                    annotation_font=dict(family="IBM Plex Mono, monospace", color="#f0b429", size=10),
                )
                fig2.update_layout(
                    xaxis=_xaxis_cfg,
                    yaxis=dict(title=_stat_label, rangemode='tozero'),
                    showlegend=False, margin=dict(t=20, b=40), bargap=0.35,
                    hovermode='x unified',
                )
                fig2 = apply_chart_theme(fig2)
                fig2.update_xaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
                fig2.update_yaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
                st.plotly_chart(fig2, width='stretch', key="chart_004", config=PLOTLY_TOUCH_CONFIG)

                st.markdown('<div class="section-header">Game Log</div>', unsafe_allow_html=True)
                log = player_games.copy()
                log['Result'] = log['Is_Win'].map({1: 'W', 0: 'L'})
                log['Poll%'] = (log['Poll_Prob'] * 100).round(1).astype(str) + '%'
                log['ExpV'] = log['Exp_Votes'].round(2)
                log['P(3)'] = (log['P_3'] * 100).round(1).astype(str) + '%'
                log['P(2)'] = (log['P_2'] * 100).round(1).astype(str) + '%'
                log['P(1)'] = (log['P_1'] * 100).round(1).astype(str) + '%'
                display_cols = (['Season'] if is_career else []) + [
                    'Round_num', 'Result', 'Disposals', 'Goals',
                    'Contested.Possessions', 'Clearances', 'Coaches_Votes']
                # Career mixes voted seasons with the in-progress one; show actual
                # votes whenever the column carries them (hidden only for a lone 2026).
                if (is_career or not is_2026) and 'Brownlow.Votes' in log.columns:
                    display_cols.append('Brownlow.Votes')
                display_cols += ['ExpV', 'Poll%', 'P(3)', 'P(2)', 'P(1)']
                available = [c for c in display_cols if c in log.columns]
                log_display = log[available].rename(columns={
                    'Round_num': 'Rnd', 'Contested.Possessions': 'ContPoss',
                    'Coaches_Votes': 'CV', 'Brownlow.Votes': 'BV',
                })
                _sort_cols = ['Season', 'Rnd'] if is_career else ['Rnd']
                _log_disp = log_display.sort_values(_sort_cols).copy()
                # Display AFL round (season-aware) — display only, sort order unchanged
                if is_career:
                    _log_disp['Rnd'] = [_display_round(r, s) for r, s in zip(_log_disp['Rnd'], _log_disp['Season'])]
                else:
                    _log_disp['Rnd'] = _log_disp['Rnd'].apply(lambda r: _display_round(r, selected_season))
                if is_career:
                    _log_disp['Season'] = _log_disp['Season'].astype(int)
                for col in _log_disp.select_dtypes(include='float').columns:
                    _log_disp[col] = _log_disp[col].round(1)
                st.dataframe(_style_table(_log_disp), width='stretch', hide_index=True)
                st.caption("CV = coaches votes · ExpV = expected votes")

        # ── DNA tab ───────────────────────────────────────────
        @st.fragment
        def _render_dna_tab(selected_player, game_df, efficiency, is_career, max_season_rounds):
            if efficiency is None:
                st.error("No game-level data found.")
            else:
                eff_row = efficiency[efficiency['Player_Name'] == selected_player]

                # ── Presentation-only formatting guard (kills "nan%") ──
                # Undefined (no qualifying games / NaN denominator) → "—";
                # defined-but-zero → "0.0%". Underlying maths untouched.
                def _rate(val, denom=None):
                    if denom is not None and (pd.isna(denom) or denom == 0):
                        return "—"
                    if pd.isna(val):
                        return "—"
                    return f"{val * 100:.1f}%"

                if not eff_row.empty:
                    e = eff_row.iloc[0]

                    player_games_dna = game_df[game_df['Player_Name'] == selected_player].copy()
                    # Career polling stats only count seasons whose votes are in;
                    # drop the in-progress season so it doesn't dilute the rates.
                    if is_career and 'Season' in player_games_dna.columns:
                        _voted_seasons = (game_df.groupby('Season')['Brownlow.Votes']
                                          .sum().loc[lambda s: s > 0].index)
                        player_games_dna = player_games_dna[player_games_dna['Season'].isin(_voted_seasons)]
                    has_votes = (not player_games_dna.empty) and ('Brownlow.Votes' in player_games_dna.columns)

                    games_total = int(e["Games"]) if not pd.isna(e["Games"]) else 0
                    poll_rate   = e["Poll_Rate"]
                    polled_n    = int(round((0 if pd.isna(poll_rate) else poll_rate) * games_total))
                    wr   = e.get('Win_Poll_Rate', float('nan'))
                    lr   = e.get('Loss_Poll_Rate', float('nan'))
                    hd   = e.get('HD_Poll_Rate', float('nan'))
                    hd_g = e.get('HD_Games', float('nan'))
                    hd_g_int = 0 if pd.isna(hd_g) else int(hd_g)
                    wr_w = 0.0 if pd.isna(wr) else max(0.0, min(100.0, wr * 100))
                    lr_w = 0.0 if pd.isna(lr) else max(0.0, min(100.0, lr * 100))

                    # Lopsided win/loss insight, generated from the actual split.
                    _insight = ""
                    if not pd.isna(poll_rate) and poll_rate > 0:
                        polled_wins   = (not pd.isna(wr)) and wr > 0
                        polled_losses = (not pd.isna(lr)) and lr > 0
                        if polled_wins and (not pd.isna(lr)) and lr == 0:
                            _insight = "Every vote came in a win — a clean win-dependency."
                        elif polled_losses and (not pd.isna(wr)) and wr == 0:
                            _insight = "Every vote came in a loss — polls regardless of the result."
                    _insight_html = f'<div class="dna-insight">{_insight}</div>' if _insight else ''

                    st.markdown("""
<style>
.dna-poll-val{font-family:'IBM Plex Mono',monospace;font-size:38px;font-weight:600;color:var(--emerald);line-height:1;}
.dna-poll-sub{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:8px;letter-spacing:.03em;}
.dna-split{margin-top:22px;display:flex;flex-direction:column;gap:14px;}
.dna-split-lbl{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--steel);margin-bottom:6px;}
.dna-split-lbl b{color:var(--text);font-weight:600;}
.dna-track{height:8px;background:var(--muted-fill);border-radius:4px;overflow:hidden;}
.dna-fill{height:100%;border-radius:4px;}
.dna-fill.win{background:var(--emerald);}
.dna-fill.loss{background:var(--emerald-pack);}
.dna-insight{font-family:'IBM Plex Mono',monospace;font-size:11px;font-style:italic;color:var(--gold);margin-top:16px;line-height:1.4;}
.dna-readout{display:flex;align-items:baseline;gap:12px;margin-top:20px;padding-top:16px;border-top:1px solid var(--line);}
.dna-readout-lbl{font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;letter-spacing:.16em;color:var(--muted);}
.dna-readout-val{font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:600;color:var(--text);margin-left:auto;}
.dna-readout-note{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.dna-mini-head{font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;letter-spacing:.16em;color:var(--muted);margin-bottom:2px;}
.dna-find-val{font-family:'IBM Plex Mono',monospace;font-size:38px;font-weight:600;color:var(--gold);line-height:1;}
.dna-find-cap{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:6px;letter-spacing:.03em;}
.dna-find-sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);margin-top:8px;}
.dna-find-sentence{font-family:'Archivo',sans-serif;font-size:13px;color:var(--text);margin-top:14px;line-height:1.5;max-width:46ch;}
.dna-find-strip{display:flex;margin-top:18px;}
.dna-find-strip .dfs{padding:0 16px;}
.dna-find-strip .dfs:first-child{padding-left:0;}
.dna-find-strip .dfs + .dfs{border-left:1px solid var(--hairline-strong);}
.dfs-v{font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:var(--steel);}
.dfs-l{font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin-top:5px;}
.dna-vbar{display:flex;height:30px;border-radius:6px;overflow:hidden;background:var(--muted-fill);}
.dna-vbar > div{height:100%;}
.dna-vleg{display:flex;flex-wrap:wrap;gap:18px;margin-top:12px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--steel);}
.dna-vleg .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:7px;vertical-align:middle;}
.dna-vins{font-family:'IBM Plex Mono',monospace;font-size:11px;font-style:italic;color:var(--gold);margin-top:12px;}
</style>
""", unsafe_allow_html=True)

                    st.markdown('<div class="section-header">Polling DNA</div>', unsafe_allow_html=True)

                    # Minimum-games filter now feeds only the personal rank chip below.
                    # Career spans many seasons, so allow a higher minimum (separate key
                    # avoids a stored value falling outside the season range).
                    if is_career:
                        _mg_max = max(int(efficiency['Games'].max()), 1)
                        min_g = st.slider("Minimum games", 1, _mg_max, min(50, _mg_max), key="dna_min_g_career")
                    else:
                        min_g = st.slider("Minimum games", 1, max_season_rounds, min(10, max_season_rounds), key="dna_min_g")

                    # Personal poll-efficiency rank among all players clearing min_g,
                    # ranked by overall poll rate (the old table's default sort column).
                    _qual = (efficiency[efficiency['Games'] >= min_g]
                             .sort_values('Poll_Rate', ascending=False).reset_index(drop=True))
                    _n_qual = len(_qual)
                    _pos = _qual.index[_qual['Player_Name'] == selected_player]
                    if len(_pos):
                        _rank = int(_pos[0]) + 1
                        st.markdown(
                            '<div style="margin:4px 0 18px"><span style="display:inline-block;'
                            'background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.35);'
                            "color:#34d399;font-family:'Sora',sans-serif;font-size:11px;font-weight:600;"
                            'letter-spacing:.02em;padding:4px 13px;border-radius:999px;">Poll efficiency: '
                            f'<b style="font-family:\'DM Mono\',monospace;font-weight:500">#{_rank}</b> of '
                            f'<b style="font-family:\'DM Mono\',monospace;font-weight:500">{_n_qual}</b> qualified'
                            '</span></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div style="margin:4px 0 18px"><span style="display:inline-block;'
                            'background:rgba(159,176,191,.08);border:1px solid var(--hairline-strong);'
                            "color:var(--muted);font-family:'Sora',sans-serif;font-size:11px;font-weight:600;"
                            'letter-spacing:.02em;padding:4px 13px;border-radius:999px;">'
                            f'Poll efficiency: — (below {min_g} game minimum)</span></div>',
                            unsafe_allow_html=True,
                        )

                    dna_l, dna_r = st.columns(2)

                    # ── Left: poll rate headline + win/loss split + 30+ readout ──
                    with dna_l:
                        st.markdown(f"""
<div>
  <div class="dna-poll-val">{_rate(poll_rate)}</div>
  <div class="dna-poll-sub">overall poll rate · polled in {polled_n} of {games_total} games</div>
  <div class="dna-split">
    <div>
      <div class="dna-split-lbl">In wins <b>{_rate(wr)}</b></div>
      <div class="dna-track"><div class="dna-fill win" style="width:{wr_w:.1f}%"></div></div>
    </div>
    <div>
      <div class="dna-split-lbl">In losses <b>{_rate(lr)}</b></div>
      <div class="dna-track"><div class="dna-fill loss" style="width:{lr_w:.1f}%"></div></div>
    </div>
  </div>
  {_insight_html}
  <div class="dna-readout">
    <span class="dna-readout-lbl">30+ disposal poll rate</span>
    <span class="dna-readout-val">{_rate(hd, hd_g)}</span>
    <span class="dna-readout-note">{hd_g_int} games</span>
  </div>
</div>
""", unsafe_allow_html=True)

                    # ── Right: stat-selectable threshold finder ──
                    with dna_r:
                        # (display label) -> (column, slider min, max, default). All three
                        # columns are in game_df / _CAREER_COLS, so career is covered too.
                        _THRESH_STATS = {
                            'Disposals':     ('Disposals',     10, 50, 20),
                            'Goals':         ('Goals',          0, 10,  2),
                            'Coaches Votes': ('Coaches_Votes',  0, 10,  5),
                        }
                        _tstat = st.selectbox("Threshold stat", list(_THRESH_STATS.keys()),
                                              index=0, key="dna_thresh_stat")
                        _tcol, _tmin, _tmax, _tdef = _THRESH_STATS[_tstat]
                        _tnoun = _tstat.lower()
                        st.markdown(f'<div class="dna-mini-head">{_tstat} Threshold</div>', unsafe_allow_html=True)
                        # Per-stat key so switching stats never carries a stale out-of-range value.
                        thr = st.slider(f"Min {_tnoun}", _tmin, _tmax, _tdef, 1, key=f"dna_thresh::{_tstat}")
                        if has_votes and _tcol in player_games_dna.columns:
                            subset = player_games_dna[player_games_dna[_tcol] >= thr]
                            n_sub = len(subset)
                            n_tot = len(player_games_dna)
                            if n_sub == 0:
                                st.markdown(
                                    f'<div class="dna-find-val">—</div>'
                                    f'<div class="dna-find-sub">no games at {thr}+ {_tnoun}</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                pr  = (subset['Brownlow.Votes'] > 0).mean()
                                av  = subset['Brownlow.Votes'].mean()
                                tvr = (subset['Brownlow.Votes'] == 3).mean()
                                _ln = selected_player.split()[-1]
                                if pr == 1.0:
                                    _s = f"When {_ln} reaches {thr}+ {_tnoun} he polls every time"
                                    _s += " — and every one was a 3-vote game." if tvr == 1.0 else f" — averaging {av:.2f} votes."
                                else:
                                    _s = f"At {thr}+ {_tnoun} {_ln} polls {pr * 100:.0f}% of the time, averaging {av:.2f} votes."
                                st.markdown(f"""
<div>
  <div class="dna-find-val">{_rate(pr, n_sub)}</div>
  <div class="dna-find-cap">poll rate at {thr}+ {_tnoun}</div>
  <div class="dna-find-sentence">{_s}</div>
  <div class="dna-find-strip">
    <div class="dfs"><div class="dfs-v">{n_sub} of {n_tot}</div><div class="dfs-l">Games</div></div>
    <div class="dfs"><div class="dfs-v">{av:.2f}</div><div class="dfs-l">Avg votes polled</div></div>
    <div class="dfs"><div class="dfs-v">{_rate(tvr, n_sub)}</div><div class="dfs-l">3-Vote Rate</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
                        elif not has_votes:
                            st.markdown('<div class="dna-find-sub">No actual-vote data for this season.</div>',
                                        unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="dna-find-sub">{_tstat} not available for this player.</div>',
                                        unsafe_allow_html=True)

                    # ── Vote distribution: one horizontal stacked bar ──
                    if has_votes:
                        vc = player_games_dna['Brownlow.Votes'].value_counts()
                        n3, n2, n1, n0 = int(vc.get(3, 0)), int(vc.get(2, 0)), int(vc.get(1, 0)), int(vc.get(0, 0))
                        tot = len(player_games_dna)
                        def _w(n): return (n / tot * 100) if tot else 0
                        polled = n3 + n2 + n1
                        _vins = ""
                        if polled > 0 and n3 == polled:
                            _vins = f"Every time {selected_player.split()[-1]} polled, it was a 3-vote game."
                        _vins_html = f'<div class="dna-vins">{_vins}</div>' if _vins else ''
                        st.markdown(
                            '<div class="section-header" style="margin-top:8px">Vote Distribution</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"""
<div class="dna-vbar">
  <div style="width:{_w(n3):.1f}%;background:var(--gold)"></div>
  <div style="width:{_w(n2):.1f}%;background:var(--emerald-pack)"></div>
  <div style="width:{_w(n1):.1f}%;background:rgba(159,176,191,.55)"></div>
  <div style="width:{_w(n0):.1f}%;background:var(--muted-fill)"></div>
</div>
<div class="dna-vleg">
  <span><span class="sw" style="background:var(--gold)"></span>3 votes · {n3}</span>
  <span><span class="sw" style="background:var(--emerald-pack)"></span>2 votes · {n2}</span>
  <span><span class="sw" style="background:rgba(159,176,191,.55)"></span>1 vote · {n1}</span>
  <span><span class="sw" style="background:var(--muted-fill)"></span>0 votes · {n0}</span>
</div>
{_vins_html}
""", unsafe_allow_html=True)

        with _tab_dna:
            _render_dna_tab(selected_player, game_df, efficiency, is_career, max_season_rounds)

        # ── Compare tab ───────────────────────────────────────
        with _tab_compare:
            # Compare is season-based: career predictions lack Avg_Poll_Prob and the
            # career game frame lacks Tackles/Inside.50s, so NO comparison logic may
            # run in career mode — this guard renders a notice and nothing else.
            if is_career:
                st.markdown(
                    '<div style="background:var(--surface);border-radius:10px;padding:40px 24px;'
                    'text-align:center;margin-top:6px">'
                    '<div style="font-family:\'Archivo\',sans-serif;font-size:18px;font-weight:800;'
                    'color:var(--text)">Comparison is season-based</div>'
                    '<div style="font-family:\'Sora\',sans-serif;font-size:13px;color:var(--muted);'
                    'margin:8px auto 0;max-width:56ch;line-height:1.6">'
                    'Pick a season from the selector above to compare '
                    f'<span style="color:#34d399">{selected_player}</span> against another player — '
                    'projections and market odds are per-season only</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                _cmp_pool = [p for p in sorted(predictions['Player_Name'].tolist())
                             if p != selected_player]
                if not _cmp_pool:
                    st.info("No other players available to compare.")
                else:
                    # Reused cmp_p2 widget state can hold a value outside the current
                    # pool (Player 1 itself, or a pick from another season) — reset it
                    # before the widget instantiates so Streamlit never errors on it.
                    if st.session_state.get("cmp_p2") not in _cmp_pool:
                        st.session_state["cmp_p2"] = _cmp_pool[0]

                    _cc_l, _cc_m, _cc_r = st.columns([2, 1, 2])
                    with _cc_l:
                        st.markdown(
                            '<div style="padding-top:4px">'
                            '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;'
                            'text-transform:uppercase;color:var(--muted)">Player 1 · From Profile</div>'
                            '<div style="font-family:\'Archivo\',sans-serif;font-size:22px;font-weight:800;'
                            f'color:var(--text);line-height:1.15;margin-top:3px">{selected_player}</div>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    with _cc_m:
                        st.markdown(
                            '<div style="text-align:center;font-family:\'Archivo\',sans-serif;'
                            'font-size:18px;font-weight:800;color:var(--muted);padding-top:22px">VS</div>',
                            unsafe_allow_html=True,
                        )
                    with _cc_r:
                        _cp2 = st.selectbox("Player 2", _cmp_pool, key="cmp_p2")
                    _cp1 = selected_player

                    _cg1 = game_df[game_df['Player_Name'] == _cp1]
                    _cg2 = game_df[game_df['Player_Name'] == _cp2]

                    def _cmp_pred(name, col):
                        _r = predictions[predictions['Player_Name'] == name]
                        if _r.empty or col not in predictions.columns:
                            return None
                        _v = _r.iloc[0][col]
                        return float(_v) if pd.notna(_v) else None

                    def _cmp_mean(g, col):
                        if col not in g.columns or g.empty:
                            return None
                        _m = g[col].mean()
                        return float(_m) if pd.notna(_m) else None

                    def _cmp_header(title):
                        return ('<div style="display:flex;align-items:center;gap:12px;margin:26px 0 10px">'
                                '<div style="font-family:\'Archivo\',sans-serif;font-size:15px;font-weight:700;'
                                f'color:var(--text);white-space:nowrap">{title}</div>'
                                '<div style="flex:1;height:1px;background:var(--line)"></div></div>')

                    _fmt_mean = lambda v: f"{v:.1f}"
                    _fmt_prob = lambda v: f"{v:.3f}"
                    _fmt_int  = lambda v: f"{int(round(v))}"

                    def _mirror_row(label, v1, v2, fmt):
                        # Leader (higher wins for every stat here) shows emerald; compare
                        # on raw values so display rounding never invents a false lead.
                        s1 = fmt(v1) if v1 is not None else "—"
                        s2 = fmt(v2) if v2 is not None else "—"
                        _both = v1 is not None and v2 is not None
                        _c1 = '#34d399' if (_both and v1 > v2) else 'var(--text)'
                        _c2 = '#34d399' if (_both and v2 > v1) else 'var(--text)'
                        return (
                            '<div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;'
                            'gap:16px;padding:10px 0;border-bottom:1px solid rgba(233,238,243,0.08)">'
                            f'<div style="font-family:\'DM Mono\',monospace;font-size:16px;text-align:right;'
                            f'color:{_c1}">{s1}</div>'
                            '<div style="font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'
                            f'color:var(--muted);text-align:center;min-width:132px">{label}</div>'
                            f'<div style="font-family:\'DM Mono\',monospace;font-size:16px;text-align:left;'
                            f'color:{_c2}">{s2}</div></div>'
                        )

                    # ── Season overview (mirror rows) ──
                    st.markdown(_cmp_header('Season overview'), unsafe_allow_html=True)
                    _so = ''
                    if 'Exp_Total_Votes' in predictions.columns:
                        _so += _mirror_row('Exp. Total Votes', _cmp_pred(_cp1, 'Exp_Total_Votes'),
                                           _cmp_pred(_cp2, 'Exp_Total_Votes'), _fmt_int)
                    if 'Avg_Poll_Prob' in predictions.columns:
                        _so += _mirror_row('Avg Poll Prob', _cmp_pred(_cp1, 'Avg_Poll_Prob'),
                                           _cmp_pred(_cp2, 'Avg_Poll_Prob'), _fmt_prob)
                    for _lbl, _col in [
                        ('Disposals / game', 'Disposals'),
                        ('Contested / game', 'Contested.Possessions'),
                        ('Clearances / game', 'Clearances'),
                        ('Tackles / game', 'Tackles'),
                        ('Goals / game', 'Goals'),
                        ('Score involvements / game', 'Score_Involvements'),
                    ]:
                        if _col in game_df.columns:
                            _so += _mirror_row(_lbl, _cmp_mean(_cg1, _col), _cmp_mean(_cg2, _col), _fmt_mean)
                    if 'Coaches_Votes' in game_df.columns:
                        _so += _mirror_row('Games with coaches votes',
                                           float(int((_cg1['Coaches_Votes'] > 0).sum())),
                                           float(int((_cg2['Coaches_Votes'] > 0).sum())), _fmt_int)
                        _so += _mirror_row('Total coaches votes',
                                           float(_cg1['Coaches_Votes'].sum()),
                                           float(_cg2['Coaches_Votes'].sum()), _fmt_int)
                    st.markdown(f'<div>{_so}</div>', unsafe_allow_html=True)

                    # ── Round by round (predicted-votes overlay) ──
                    st.markdown(_cmp_header('Round by round'), unsafe_allow_html=True)
                    _rg1 = _cg1.sort_values('Round_num')
                    _rg2 = _cg2.sort_values('Round_num')
                    if _rg1.empty and _rg2.empty:
                        st.caption("No round-by-round data for this season.")
                    else:
                        _fig_cmp = go.Figure()
                        if not _rg1.empty:
                            _fig_cmp.add_trace(go.Scatter(
                                x=_display_rounds(_rg1), y=_rg1['Exp_Votes'].round(1),
                                name=_cp1, mode='lines+markers',
                                line=dict(color='#34d399', width=2.5), marker=dict(size=7, color='#34d399'),
                                hovertemplate='<b>' + _cp1 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        if not _rg2.empty:
                            _fig_cmp.add_trace(go.Scatter(
                                x=_display_rounds(_rg2), y=_rg2['Exp_Votes'].round(1),
                                name=_cp2, mode='lines+markers',
                                line=dict(color='#f0b429', width=2.5), marker=dict(size=7, color='#f0b429'),
                                hovertemplate='<b>' + _cp2 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        _fig_cmp = apply_chart_theme(_fig_cmp)
                        _fig_cmp.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            xaxis=dict(title='Round', dtick=1, showgrid=False, zeroline=False),
                            yaxis=dict(title='Predicted Votes', rangemode='tozero',
                                       gridcolor='rgba(140,165,185,.14)', zeroline=False),
                            legend=dict(orientation='h', y=1.1),
                            margin=dict(t=20, b=40), height=300, hovermode='x unified',
                        )
                        st.plotly_chart(_fig_cmp, width='stretch', key="chart_020", config=PLOTLY_TOUCH_CONFIG)

                    # ── Model vs market ──
                    # Two different quantities, shown side by side and deliberately NOT
                    # differenced. _mod1 is a share of the pair's expected VOTES; _mkt1 is
                    # a conditional WIN probability renormalised over the pair. Subtracting
                    # one from the other does not measure an edge, so none is derived or
                    # displayed. Odds via load_best_odds(); projections aren't surfaced
                    # here, so load_season_projection() is unused.
                    st.markdown(_cmp_header('Model vs market'), unsafe_allow_html=True)
                    _cmp_odds = load_best_odds()
                    _e1 = _cmp_pred(_cp1, 'Exp_Total_Votes') or 0.0
                    _e2 = _cmp_pred(_cp2, 'Exp_Total_Votes') or 0.0
                    _etot = _e1 + _e2
                    _mod1 = round(_e1 / _etot * 100, 1) if _etot > 0 else 50.0
                    _mod2 = round(100.0 - _mod1, 1)

                    def _odds_for(name):
                        _bo = _mi = None
                        if _cmp_odds is not None and len(_cmp_odds):
                            _ow = _cmp_odds[_cmp_odds['player'] == name]
                            if not _ow.empty:
                                _v = _ow.iloc[0]['best_odds']
                                _bo = float(_v) if pd.notna(_v) else None
                                _v2 = _ow.iloc[0]['implied_prob']
                                _mi = float(_v2) if pd.notna(_v2) else None
                        return _bo, _mi
                    _bo1, _mi1 = _odds_for(_cp1)
                    _bo2, _mi2 = _odds_for(_cp2)
                    _has_mkt = _mi1 is not None and _mi2 is not None
                    if _has_mkt:
                        _msum = _mi1 + _mi2
                        _mkt1 = round(_mi1 / _msum * 100, 1) if _msum > 0 else 50.0
                        _mkt2 = round(100.0 - _mkt1, 1)
                    else:
                        _mkt1 = _mkt2 = None

                    def _edge_card(name, model_pct, best_odds, mkt_pct):
                        def _cell(lbl, val, col='var(--text)'):
                            return ('<div style="display:flex;justify-content:space-between;align-items:baseline;'
                                    'padding:7px 0;border-bottom:1px solid rgba(233,238,243,0.06)">'
                                    f'<span style="font-size:11px;color:var(--muted)">{lbl}</span>'
                                    '<span style="font-family:\'DM Mono\',monospace;font-size:14px;'
                                    f'color:{col}">{val}</span></div>')
                        _mp = f"{model_pct:.1f}%" if model_pct is not None else "—"
                        _bo = f"${best_odds:.1f}" if best_odds is not None else "—"
                        _mv = f"{mkt_pct:.1f}%" if mkt_pct is not None else "—"
                        return (
                            '<div style="background:var(--surface);border:1px solid var(--line);'
                            'border-radius:8px;padding:16px 18px">'
                            '<div style="font-family:\'Archivo\',sans-serif;font-size:16px;font-weight:800;'
                            f'color:var(--text);margin-bottom:8px">{name}</div>'
                            + _cell('Model vote share', _mp)
                            + _cell('Best odds', _bo)
                            + _cell('Market win share', _mv)
                            + '</div>'
                        )
                    _me1, _me2 = st.columns(2)
                    with _me1:
                        st.markdown(_edge_card(_cp1, _mod1, _bo1, _mkt1), unsafe_allow_html=True)
                    with _me2:
                        st.markdown(_edge_card(_cp2, _mod2, _bo2, _mkt2), unsafe_allow_html=True)

                    # ── H2H votes ─────────────────────────────────────
                    # Season-only: the career frame has no P_1/P_2/P_3, so this
                    # sits inside the non-career branch and is column-guarded.
                    _h2h_need = ('Round_num', 'P_1', 'P_2', 'P_3', 'Poll_Prob', 'Exp_Votes')
                    if all(_c in game_df.columns for _c in _h2h_need):

                        def _h2h_rounds(g):
                            """Round_num -> row. DNP/bye rounds are absent rows upstream,
                            so a missing key IS the did-not-play signal."""
                            _out = {}
                            for _, _r in g.iterrows():
                                try:
                                    _out[int(_r['Round_num'])] = _r
                                except (TypeError, ValueError):
                                    continue
                            return _out

                        _h2h_r1, _h2h_r2 = _h2h_rounds(_cg1), _h2h_rounds(_cg2)
                        _h2h_axis = sorted(set(_h2h_r1) | set(_h2h_r2))

                        if _h2h_axis:
                            # _h2h_num / _h2h_pmf / _h2h_total_dist / _h2h_short_pair /
                            # _h2h_classify are module level — the Live Tracker's H2H
                            # panel shares them and cannot see this block.
                            _h2h_d1 = _h2h_total_dist(_h2h_r1, _h2h_axis)
                            _h2h_d2 = _h2h_total_dist(_h2h_r2, _h2h_axis)

                            # Joint over (P1 total, P2 total) assuming independence. This is a
                            # v1 approximation: in rounds where both play the SAME game the two
                            # totals are negatively coupled (the 3/2/1 votes on offer are shared,
                            # so both cannot take 3), which independence slightly over-disperses.
                            # Those rounds are flagged SAME GAME in the ledger below.
                            _h2h_m = np.outer(_h2h_d1, _h2h_d2)
                            _h2h_w1 = float(np.tril(_h2h_m, -1).sum())   # P1 total > P2 total
                            _h2h_tie = float(np.trace(_h2h_m))
                            _h2h_w2 = float(np.triu(_h2h_m, 1).sum())

                            _h2h_e1 = sum(_h2h_num(_h2h_r1.get(_rn), 'Exp_Votes') for _rn in _h2h_axis)
                            _h2h_e2 = sum(_h2h_num(_h2h_r2.get(_rn), 'Exp_Votes') for _rn in _h2h_axis)
                            _h2h_marg = _h2h_e1 - _h2h_e2

                            # Full team name -> abbreviation, straight off the frame.
                            _h2h_abbr = {}
                            if 'Playing.for' in game_df.columns and 'Team' in game_df.columns:
                                for _f, _a in zip(game_df['Playing.for'], game_df['Team']):
                                    if pd.notna(_f) and pd.notna(_a):
                                        _h2h_abbr.setdefault(str(_f), str(_a))

                            def _h2h_opp(row):
                                """Opponent abbreviation, from Home.team/Away.team + Home.Away."""
                                if row is None:
                                    return None
                                _ha = str(row.get('Home.Away') or '').strip().lower()
                                _side = row.get('Away.team') if _ha == 'home' else row.get('Home.team')
                                if pd.isna(_side):
                                    return None
                                return _h2h_abbr.get(str(_side), str(_side))

                            def _h2h_fixture(row):
                                """The whole fixture, abbreviated — used for shared-game rounds."""
                                if row is None:
                                    return '—'
                                _h, _a = row.get('Home.team'), row.get('Away.team')
                                if pd.isna(_h) or pd.isna(_a):
                                    return '—'
                                return (f"{_h2h_abbr.get(str(_h), str(_h))} v "
                                        f"{_h2h_abbr.get(str(_a), str(_a))}")

                            _h2h_s1, _h2h_s2 = _h2h_short_pair(_cp1, _cp2)
                            _h2h_recs = []
                            for _rn in _h2h_axis:
                                _row1, _row2 = _h2h_r1.get(_rn), _h2h_r2.get(_rn)
                                _dnp1, _dnp2 = _row1 is None, _row2 is None
                                _pp1 = None if _dnp1 else _h2h_num(_row1, 'Poll_Prob')
                                _pp2 = None if _dnp2 else _h2h_num(_row2, 'Poll_Prob')
                                _g1 = None if _dnp1 else _row1.get('Game_ID')
                                _g2 = None if _dnp2 else _row2.get('Game_ID')
                                _same = (not _dnp1 and not _dnp2 and pd.notna(_g1)
                                         and pd.notna(_g2) and _g1 == _g2)

                                # Classification is module level (_h2h_classify) so the Live
                                # Tracker panel classifies remaining rounds the same way.
                                # Rendering reads kind/owner, never the label — two players
                                # sharing a surname would make the label ambiguous.
                                _kind, _owner, _cls = _h2h_classify(
                                    _same, _pp1, _pp2, _h2h_s1, _h2h_s2)
                                if _same:
                                    _matchup = _h2h_fixture(_row1)
                                else:
                                    _o1, _o2 = _h2h_opp(_row1), _h2h_opp(_row2)
                                    _parts = [f"v {_o}" for _o in (_o1, _o2) if _o]
                                    _matchup = ' / '.join(_parts) if _parts else '—'

                                _h2h_recs.append({
                                    'rn': _rn, 'matchup': _matchup, 'cls': _cls,
                                    'kind': _kind, 'owner': _owner,
                                    'pp1': _pp1, 'pp2': _pp2,
                                    # Swing impact: how lopsided the round is between the two.
                                    'impact': abs((_pp1 or 0.0) - (_pp2 or 0.0)),
                                })

                            _h2h_recs.sort(key=lambda _r: _r['impact'], reverse=True)

                            # ── chrome ──
                            _h2h_last = _display_round(max(_h2h_axis), selected_season)

                            def _h2h_fig(label, value, colour):
                                return (
                                    '<div style="flex:1">'
                                    '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;'
                                    'text-transform:uppercase;color:var(--muted)">'
                                    f'{label}</div>'
                                    '<div style="font-family:\'DM Mono\',monospace;font-size:26px;'
                                    f'font-weight:500;color:{colour};margin-top:4px">{value}</div></div>'
                                )

                            _h2h_pct = lambda _v: f"{_v * 100:.0f}%"
                            # Header and stamp render on their own so the tracked-pair
                            # control can sit directly beneath them, above the figures.
                            st.markdown(
                                _cmp_header('Head to head votes')
                                + '<div style="display:flex;align-items:baseline;justify-content:space-between;'
                                  'margin:-4px 0 10px">'
                                  '<div style="font-family:\'DM Mono\',monospace;font-size:11px;'
                                  'letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)">'
                                  f'Through round {_h2h_last}</div></div>',
                                unsafe_allow_html=True,
                            )

                            # ── tracked pair ──────────────────────────────
                            # Saved so the Live Tracker can surface this pair during
                            # the count. One pair per user per season: saving a new
                            # one overwrites, which the upsert does in a single
                            # statement (see 06_h2h_pairs.sql).
                            _h2h_user = user_auth.current_user()
                            _h2h_uid  = _h2h_user.get("id") if _h2h_user else None

                            def _h2h_pid(g):
                                """This player's fitzRoy ID, or None when the frame has
                                none. Arrives as a float ('13054.0'), so normalise to a
                                bare integer string before it is stored or compared."""
                                if 'ID' not in g.columns or g.empty:
                                    return None
                                for _v in g['ID']:
                                    if pd.notna(_v):
                                        try:
                                            return str(int(float(_v)))
                                        except (TypeError, ValueError):
                                            return str(_v)
                                return None

                            _h2h_pid1, _h2h_pid2 = _h2h_pid(_cg1), _h2h_pid(_cg2)

                            def _h2h_is_saved(saved):
                                """Order-insensitive match against the saved pair.

                                fitzRoy IDs win when both sides carry them: display
                                names pick up a '(Team)' suffix only in seasons where
                                they collide, so a pair saved one season can come back
                                spelled differently the next. Names are the fallback
                                for frames with no ID source."""
                                if not saved:
                                    return False
                                _sid1, _sid2 = saved.get('player1_id'), saved.get('player2_id')
                                if _sid1 and _sid2 and _h2h_pid1 and _h2h_pid2:
                                    return ({str(_sid1), str(_sid2)}
                                            == {str(_h2h_pid1), str(_h2h_pid2)})
                                return ({str(saved.get('player1')), str(saved.get('player2'))}
                                        == {str(_cp1), str(_cp2)})

                            if _h2h_uid:
                                _h2h_saved = user_auth.load_h2h_pair(_h2h_uid, selected_season)
                                if _h2h_is_saved(_h2h_saved):
                                    st.markdown(
                                        '<div style="font-family:\'DM Mono\',monospace;font-size:11px;'
                                        'letter-spacing:1.5px;text-transform:uppercase;color:#f0b429;'
                                        'margin-bottom:6px">&#9733; Tracked for live count</div>',
                                        unsafe_allow_html=True,
                                    )
                                    if st.button("Untrack", key="h2h_untrack"):
                                        _h2h_ok, _h2h_msg = user_auth.clear_h2h_pair(selected_season)
                                        if _h2h_ok:
                                            # Default scope: st.rerun() must rerun the whole
                                            # script so bootstrap_session() flushes the cookie
                                            # at the top. Never scope='fragment' — see
                                            # _auth_dialog for the bug that causes.
                                            st.rerun()
                                        else:
                                            st.error(_h2h_msg)
                                else:
                                    _h2h_btn = ("Track this H2H instead" if _h2h_saved
                                                else "Track this H2H")
                                    if _h2h_saved:
                                        # A different pair is tracked. Say which, so
                                        # "instead" has a referent. Rendered OUTSIDE the
                                        # keyed container below: that container zeroes
                                        # markdown margins to hold the helper text on the
                                        # button's centreline, which would leave this line
                                        # jammed against the button row.
                                        _sv_l1, _sv_l2 = _h2h_short_pair(
                                            str(_h2h_saved.get('player1') or ''),
                                            str(_h2h_saved.get('player2') or ''),
                                        )
                                        st.markdown(
                                            '<div style="font-family:\'DM Mono\',monospace;'
                                            'font-size:11px;color:#8a9aa9;margin-bottom:7px">'
                                            '<span style="color:#f0b429">&#9733;</span> '
                                            f'TRACKED: {_sv_l1} v {_sv_l2}</div>',
                                            unsafe_allow_html=True,
                                        )
                                    # Keyed container so the emerald button CSS has
                                    # something to scope to. Only this branch is wrapped
                                    # — the Untrack button above stays default on purpose.
                                    with st.container(key="h2h_track_ctl"):
                                        _h2h_bc, _h2h_hc = st.columns(
                                            [2, 5], vertical_alignment="center")
                                        with _h2h_bc:
                                            _h2h_go = st.button(_h2h_btn, key="h2h_track")
                                        with _h2h_hc:
                                            st.markdown(
                                                '<div style="font-family:\'Sora\',sans-serif;'
                                                'font-size:12px;color:#8a9aa9">'
                                                'Shows in the Live Tracker during the count.'
                                                '</div>',
                                                unsafe_allow_html=True,
                                            )
                                    if _h2h_go:
                                        _h2h_ok, _h2h_msg = user_auth.save_h2h_pair(
                                            _cp1, _cp2, selected_season,
                                            _h2h_pid1, _h2h_pid2,
                                        )
                                        if _h2h_ok:
                                            st.rerun()
                                        else:
                                            st.error(_h2h_msg)
                            else:
                                st.markdown(
                                    '<div style="font-family:\'Sora\',sans-serif;font-size:12px;'
                                    'color:var(--muted);margin-bottom:6px">'
                                    'Sign in to track this head-to-head on the live tracker.</div>',
                                    unsafe_allow_html=True,
                                )

                            st.markdown(
                                '<div style="display:flex;flex-wrap:wrap;gap:18px;margin:14px 0 18px">'
                                + _h2h_fig(f'Projected · {_h2h_s1}', f"{_h2h_e1:.1f}", '#34d399')
                                + _h2h_fig('Projected margin',
                                           f"{'+' if _h2h_marg >= 0 else '−'}{abs(_h2h_marg):.1f}", '#f0b429')
                                + _h2h_fig(f'Projected · {_h2h_s2}', f"{_h2h_e2:.1f}", '#e9eef3')
                                + '</div>'
                                # Win-probability bar. The P2 segment is a dark MT fill, so the
                                # track carries a hairline to keep it legible on --surface.
                                + '<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;'
                                  'border:1px solid var(--line)">'
                                + f'<div style="width:{_h2h_w1 * 100:.2f}%;background:#34d399"></div>'
                                + f'<div style="width:{_h2h_tie * 100:.2f}%;background:#5a6b7a"></div>'
                                + f'<div style="width:{_h2h_w2 * 100:.2f}%;background:#1a2632"></div>'
                                + '</div>'
                                + '<div style="display:flex;justify-content:space-between;'
                                  'font-family:\'DM Mono\',monospace;font-size:11px;margin-top:7px">'
                                + f'<span style="color:#34d399">{_h2h_s1} {_h2h_pct(_h2h_w1)}</span>'
                                + f'<span style="color:#5a6b7a">TIE {_h2h_pct(_h2h_tie)}</span>'
                                + f'<span style="color:#e9eef3">{_h2h_s2} {_h2h_pct(_h2h_w2)}</span>'
                                + '</div>',
                                unsafe_allow_html=True,
                            )

                            # ── round ledger ──
                            _H2H_CHIP = {
                                'SAME GAME': 'background:#3d3110;color:#f0b429',
                                # Owned rounds (SWING or FREE) take the beneficiary's scheme.
                                'OWNER1':    'background:#0f3d31;color:#34d399',
                                'OWNER2':    'background:var(--surface);color:#e9eef3;'
                                             'box-shadow:inset 0 0 0 1px var(--line)',
                                # Not in the brief's chip set — both players live in separate
                                # games needs its own read, and gold/emerald are taken. Steel
                                # keeps it inside the MT palette and out of the colour law.
                                'CONTESTED': 'background:rgba(159,176,191,.10);color:#9fb0bf',
                                'DEAD':      'background:var(--surface);color:#5a6b7a',
                            }

                            def _h2h_chip_style(rec):
                                """Chip styling from the record's own kind/owner fields.

                                Never inspects the label: two players sharing a surname
                                (different people, so no '(Team)' suffix is added upstream)
                                would make any name-matching on the label ambiguous."""
                                if rec['kind'] == 'SAME GAME':
                                    return _H2H_CHIP['SAME GAME']
                                if rec['owner'] is not None:
                                    return _H2H_CHIP['OWNER1' if rec['owner'] == 1 else 'OWNER2']
                                return _H2H_CHIP.get(rec['kind'], _H2H_CHIP['DEAD'])

                            _H2H_GRID = ('display:grid;grid-template-columns:46px 1fr 88px 88px 150px;'
                                         'gap:12px;align-items:center')

                            def _h2h_pp_cell(val, is_p1):
                                if val is None:
                                    return ('<span style="font-family:\'DM Mono\',monospace;font-size:13px;'
                                            'color:#5a6b7a">DNP</span>')
                                _hot = val >= H2H_POLL_LIKELY
                                _c = ('#34d399' if is_p1 else '#e9eef3') if _hot else '#5a6b7a'
                                return ('<span style="font-family:\'DM Mono\',monospace;font-size:13px;'
                                        f'color:{_c}">{val:.2f}</span>')

                            def _h2h_row_html(rec):
                                _chip = _h2h_chip_style(rec)
                                return (
                                    f'<div class="h2h-lrow" style="{_H2H_GRID};padding:9px 0;'
                                    'border-bottom:1px solid rgba(233,238,243,0.06)">'
                                    '<span style="font-family:\'DM Mono\',monospace;font-size:12px;'
                                    f'color:var(--muted)">R{_display_round(rec["rn"], selected_season)}</span>'
                                    '<span style="font-family:\'Sora\',sans-serif;font-size:12px;'
                                    f'color:var(--text)">{rec["matchup"]}</span>'
                                    + _h2h_pp_cell(rec['pp1'], True)
                                    + _h2h_pp_cell(rec['pp2'], False)
                                    + '<span style="font-family:\'DM Mono\',monospace;font-size:9.5px;'
                                      'font-weight:500;letter-spacing:.06em;padding:3px 9px;border-radius:10px;'
                                      f'text-align:center;{_chip}">{rec["cls"]}</span>'
                                    '</div>'
                                )

                            _h2h_head = (
                                f'<div class="h2h-lrow h2h-lhead" style="{_H2H_GRID};padding:0 0 7px;'
                                'border-bottom:1px solid var(--line);font-size:9.5px;font-weight:700;'
                                'letter-spacing:.12em;text-transform:uppercase;color:var(--muted)">'
                                '<span>Rd</span><span>Matchup</span>'
                                f'<span>{_h2h_s1} p(poll)</span><span>{_h2h_s2} p(poll)</span>'
                                '<span style="text-align:center">Class</span></div>'
                            )

                            st.markdown(
                                _cmp_header('Round ledger')
                                + _h2h_head
                                + ''.join(_h2h_row_html(_r) for _r in _h2h_recs[:H2H_LEDGER_ROWS]),
                                unsafe_allow_html=True,
                            )
                            _h2h_rest = _h2h_recs[H2H_LEDGER_ROWS:]
                            if _h2h_rest:
                                with st.expander("All rounds", expanded=False):
                                    st.markdown(
                                        _h2h_head
                                        + ''.join(_h2h_row_html(_r) for _r in _h2h_rest),
                                        unsafe_allow_html=True,
                                    )

# ════════════════════════════════════════════════════════════
# GAME ANALYSIS
# ════════════════════════════════════════════════════════════
if _page == 'Game Analysis':
    st.markdown(
        f'<div class="lb-header"><h2 class="lb-title">Game Analysis — {selected_season}</h2>'
        f'<p class="lb-subtitle">Round-by-round match predictions</p></div>',
        unsafe_allow_html=True,
    )
    _ga_rbr_tab = st.container()

    # ── Round by Round ────────────────────────────────────────
    with _ga_rbr_tab:
        rr = load_game(selected_season)
        if rr is None:
            st.error(
                f"No {selected_season} game-level predictions found "
                f"(predictions/game_level_{selected_season}.csv). "
                "Run predict_2026.py for the current season, or brownlow_model.py "
                "to rebuild the historical files."
            )
        else:
            rr = rr.copy()
            rr['Match'] = rr['Home.team'] + ' vs ' + rr['Away.team']
            available_rounds = sorted(rr['Round_num'].dropna().unique().astype(int).tolist())

            sel_col, info_col = st.columns([2, 5])
            with sel_col:
                selected_round = st.selectbox(
                    "Select Round", available_rounds,
                    format_func=lambda r: f"Round {_display_round(r, selected_season)}",
                    index=max(0, len(available_rounds) - 1),
                    # Season-scoped: an unscoped key made Streamlit carry the old
                    # round across a season switch, so picking 2020 (18 rounds)
                    # after 2015 (23) kept a round the new season does not have.
                    key=f"rbr_round::{selected_season}",
                )
            rnd = rr[rr['Round_num'] == selected_round].copy()
            with info_col:
                st.markdown(
                    f'<div style="line-height:38px;color:var(--muted);font-size:14px;">'
                    f'Round {_display_round(selected_round, selected_season)} &nbsp;·&nbsp; {rnd["Match"].nunique()} matches &nbsp;·&nbsp; {len(rnd)} players'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Team tag abbreviations for the breakdown table / podium meta line
            _GA_ABBR = {
                "Adelaide": "ADEL", "Brisbane Lions": "BRIS", "Carlton": "CARL",
                "Collingwood": "COLL", "Essendon": "ESSE", "Fremantle": "FREO",
                "Geelong": "GEEL", "Gold Coast": "GCFC", "Greater Western Sydney": "GWS",
                "GWS": "GWS", "GWS Giants": "GWS", "Hawthorn": "HAWK", "Melbourne": "MELB",
                "North Melbourne": "NMFC", "Port Adelaide": "PORT", "Richmond": "RICH",
                "St Kilda": "STK", "Sydney": "SYD", "West Coast": "WCE",
                "Western Bulldogs": "WBD",
            }
            def _ga_abbr(team):
                return _GA_ABBR.get(str(team), str(team)[:4].upper())

            # Scoped style block — emitted inside each .ga-game wrapper so it can't leak.
            _GA_CSS = """
.ga-game{font-family:'Archivo',sans-serif;margin:0 0 40px 0;padding:0 24px;}
.ga-game .ga-overline{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--muted);margin-bottom:9px;}
.ga-game .ga-result{display:flex;align-items:baseline;flex-wrap:wrap;gap:10px;}
.ga-game .ga-win-name{font-size:30px;font-weight:800;color:var(--emerald);line-height:1;}
.ga-game .ga-win-score{font-family:'IBM Plex Mono',monospace;font-size:30px;color:var(--text);line-height:1;}
.ga-game .ga-def{font-size:13px;color:var(--muted);}
.ga-game .ga-lose-name{font-size:20px;font-weight:600;color:var(--muted);line-height:1;}
.ga-game .ga-lose-score{font-family:'IBM Plex Mono',monospace;font-size:20px;color:var(--muted);line-height:1;}
.ga-game .ga-margin{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;color:var(--emerald);
  background:var(--emerald-dim);padding:3px 11px;border-radius:999px;align-self:center;}
.ga-game .ga-rule{height:1px;background:var(--line);margin:16px 0 22px 0;}
.ga-game .ga-section-label{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--muted);margin-bottom:11px;}
.ga-game .ga-hint{color:var(--muted);opacity:.55;letter-spacing:.12em;margin-left:9px;}
.ga-game .ga-podium{display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid var(--line);
  border-radius:14px;overflow:hidden;}
.ga-game .ga-seat{padding:16px 18px;border-left:1px solid var(--line);
  transition:background-color .25s var(--ease-out);}
.ga-game .ga-seat:first-child{border-left:none;}
.ga-game .ga-seat:hover{background-color:rgba(159,176,191,.05);}
.ga-game .ga-seat-3{background:linear-gradient(180deg,var(--gold-dim),transparent);}
.ga-game .ga-badge{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;
  justify-content:center;font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:600;margin-bottom:11px;}
.ga-game .ga-badge-3{background:var(--gold);color:var(--bg);}
.ga-game .ga-badge-2{background:var(--emerald);color:var(--bg);}
.ga-game .ga-badge-1{background:rgba(159,176,191,.16);color:var(--steel);border:1px solid var(--hairline-strong);}
.ga-game .ga-seat-name{font-size:16px;font-weight:700;color:var(--text);margin-bottom:4px;}
.ga-game .ga-seat-meta{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.ga-game .ga-table{width:100%;border-collapse:collapse;margin-top:24px;}
.ga-game .ga-table th{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);text-align:right;padding:8px 10px;border-bottom:1px solid var(--hairline-strong);}
.ga-game .ga-table th.ga-l{text-align:left;}
.ga-game .ga-table td{font-family:'IBM Plex Mono',monospace;font-size:13px;text-align:right;color:var(--steel);
  padding:7px 10px;border-bottom:1px solid var(--line);}
.ga-game .ga-table td.ga-player{text-align:left;}
.ga-game .ga-row-pred{background:rgba(52,211,153,.035);}
.ga-game .ga-row-pred td{color:var(--text);}
.ga-game .ga-zero{color:var(--muted);opacity:.45;}
.ga-game .ga-coach{color:var(--gold);}
.ga-game .ga-player-wrap{display:flex;align-items:center;gap:9px;}
.ga-game .ga-tbadge{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;
  justify-content:center;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;flex:none;}
.ga-game .ga-tbadge-3{background:var(--gold);color:var(--bg);}
.ga-game .ga-tbadge-2{background:var(--emerald);color:var(--bg);}
.ga-game .ga-tbadge-1{background:rgba(159,176,191,.16);color:var(--steel);border:1px solid var(--hairline-strong);}
.ga-game .ga-tbadge-empty{background:transparent;}
.ga-game .ga-pname{font-family:'Archivo',sans-serif;font-size:14px;font-weight:600;color:var(--text);}
.ga-game .ga-ttag{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.ga-game .ga-legend{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.08em;
  color:var(--muted);opacity:.7;margin-top:13px;}
"""

            def _ga_num(val, pct=False, coach=False):
                """One numeric breakdown cell as an inner <span>; zeros muted, coaches gold."""
                try:
                    v = float(val)
                except (TypeError, ValueError):
                    v = 0.0
                is_zero = round(v, 2) == 0.0
                if pct:
                    txt = f"{int(round(v))}%"
                elif float(v).is_integer():
                    txt = f"{int(round(v))}"
                else:
                    txt = f"{v:.2f}"
                cls = []
                if coach and not is_zero:
                    cls.append("ga-coach")
                if is_zero:
                    cls.append("ga-zero")
                cls_attr = f' class="{" ".join(cls)}"' if cls else ""
                return f"<span{cls_attr}>{txt}</span>"

            def _ga_vote_badge(i):
                """3/2/1 badge for the player cell; empty spacer for non vote-getters."""
                alloc = {0: 3, 1: 2, 2: 1}.get(i)
                if alloc is None:
                    return '<span class="ga-tbadge ga-tbadge-empty"></span>'
                return f'<span class="ga-tbadge ga-tbadge-{alloc}">{alloc}</span>'

            game_order = rnd.drop_duplicates('Match')[['Match', 'Home.team', 'Away.team', 'Home.score', 'Away.score']].reset_index(drop=True)

            for game_idx, game_row in game_order.iterrows():
                match = game_row['Match']
                home  = game_row['Home.team']
                away  = game_row['Away.team']

                # ── PART 1: result header — winner ordered by score, not stored home/away
                try:
                    home_score = int(float(game_row['Home.score']))
                    away_score = int(float(game_row['Away.score']))
                    if home_score == away_score:
                        result_html = (
                            f'<span class="ga-lose-name" style="color:var(--text)">{home}</span>'
                            f'<span class="ga-lose-score" style="color:var(--text)">{home_score}</span>'
                            f'<span class="ga-def">drew</span>'
                            f'<span class="ga-lose-name" style="color:var(--text)">{away}</span>'
                            f'<span class="ga-lose-score" style="color:var(--text)">{away_score}</span>'
                        )
                    else:
                        if home_score > away_score:
                            win_n, win_s, lose_n, lose_s = home, home_score, away, away_score
                        else:
                            win_n, win_s, lose_n, lose_s = away, away_score, home, home_score
                        result_html = (
                            f'<span class="ga-win-name">{win_n}</span>'
                            f'<span class="ga-win-score">{win_s}</span>'
                            f'<span class="ga-def">def.</span>'
                            f'<span class="ga-lose-name">{lose_n}</span>'
                            f'<span class="ga-lose-score">{lose_s}</span>'
                            f'<span class="ga-margin">+{abs(home_score - away_score)}</span>'
                        )
                except (ValueError, TypeError):
                    result_html = f'<span class="ga-win-name">{match}</span>'

                # ── per-game data (sorted by expected votes, descending)
                gp = rnd[rnd['Match'] == match].copy().sort_values('Exp_Votes', ascending=False).reset_index(drop=True)
                _cont = pd.to_numeric(
                    gp.get('Contested.Possessions', gp.get('ContPoss', pd.Series([0] * len(gp)))),
                    errors='coerce').fillna(0).astype(int).tolist()
                names = gp['Player_Name'].astype(str).tolist()
                teams = gp['Team'].astype(str).tolist()
                exps  = pd.to_numeric(gp['Exp_Votes'], errors='coerce').fillna(0.0).tolist()
                p3s   = (pd.to_numeric(gp['P_3'], errors='coerce').fillna(0.0) * 100).tolist()
                dsps  = pd.to_numeric(gp['Disposals'], errors='coerce').fillna(0).astype(int).tolist()
                clrs  = pd.to_numeric(gp['Clearances'], errors='coerce').fillna(0).astype(int).tolist()
                gls   = pd.to_numeric(gp['Goals'], errors='coerce').fillna(0).astype(int).tolist()
                cvs   = pd.to_numeric(gp['Coaches_Votes'], errors='coerce').fillna(0).round().astype(int).tolist()
                max_exp = max(exps) if exps else 0.0

                n_total    = len(gp)
                # Season-scoped too: game_idx is positional within a round, so
                # without the season the expanded state leaked onto whatever
                # game happened to sit at the same index in the new season.
                expand_key = f"rr_expand::{selected_season}_{selected_round}_{game_idx}"
                if expand_key not in st.session_state:
                    st.session_state[expand_key] = False
                show_all = st.session_state[expand_key]
                n_view   = n_total if show_all else min(10, n_total)

                # ── PART 2: predicted-votes podium (top 3 by expected votes)
                seats = []
                for i in range(min(3, n_total)):
                    alloc = {0: 3, 1: 2, 2: 1}[i]
                    seat_cls = "ga-seat ga-seat-3" if i == 0 else "ga-seat"
                    seats.append(
                        f'<div class="{seat_cls}">'
                        f'<div class="ga-badge ga-badge-{alloc}">{alloc}</div>'
                        f'<div class="ga-seat-name">{names[i]}</div>'
                        f'<div class="ga-seat-meta">{exps[i]:.2f} exp · {int(round(p3s[i]))}% for 3 · {dsps[i]} disp</div>'
                        f'</div>'
                    )
                podium_html = '<div class="ga-podium">' + ''.join(seats) + '</div>'

                # ── PART 3: full breakdown table (heatmap on Exp Votes only)
                rows_html = []
                for i in range(n_view):
                    a = 0.22 * (exps[i] / max_exp) if max_exp > 0 else 0.0
                    exp_cls = ' class="ga-zero"' if round(exps[i], 2) == 0.0 else ''
                    tr_cls  = ' class="ga-row-pred"' if i < 3 else ''
                    player_td = (
                        f'<td class="ga-player"><span class="ga-player-wrap">{_ga_vote_badge(i)}'
                        f'<span class="ga-pname">{names[i]}</span>'
                        f'<span class="ga-ttag">{_ga_abbr(teams[i])}</span></span></td>'
                    )
                    rows_html.append(
                        f'<tr{tr_cls}>{player_td}'
                        f'<td style="background:rgba(52,211,153,{a:.3f})"><span{exp_cls}>{exps[i]:.2f}</span></td>'
                        f'<td>{_ga_num(p3s[i], pct=True)}</td>'
                        f'<td>{_ga_num(dsps[i])}</td>'
                        f'<td>{_ga_num(_cont[i])}</td>'
                        f'<td>{_ga_num(clrs[i])}</td>'
                        f'<td>{_ga_num(gls[i])}</td>'
                        f'<td>{_ga_num(cvs[i], coach=True)}</td></tr>'
                    )

                st.markdown(
                    f'<div class="ga-game"><style>{_GA_CSS}</style>'
                    f'<div class="ga-overline">GAME {game_idx + 1} · ROUND {_display_round(selected_round, selected_season)}</div>'
                    f'<div class="ga-result">{result_html}</div>'
                    f'<div class="ga-rule"></div>'
                    f'<div class="ga-section-label">PREDICTED VOTES'
                    f'<span class="ga-hint">model expectation · 3-2-1</span></div>'
                    f'{podium_html}'
                    # Eight mono columns come to ~440px of min-content, so on a
                    # phone the table used to widen the page instead of itself.
                    # Contained scroll, the Polls a Vote matrix pattern — never
                    # overflow-x:hidden at page level (project law).
                    f'<div style="overflow-x:auto">'
                    f'<table class="ga-table"><thead><tr>'
                    f'<th class="ga-l">Player</th><th>Exp Votes</th><th>P(3)</th><th>Disp</th>'
                    f'<th>Cont.</th><th>Clr</th><th>Goals</th><th>Coaches</th>'
                    f'</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>'
                    f'<div class="ga-legend">heat = expected votes &nbsp;·&nbsp; gold = coaches votes '
                    f'&nbsp;·&nbsp; shaded rows = predicted 3-2-1</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if n_total > 10:
                    _exp_lbl = "↑ Show less" if show_all else f"↓ Show all {n_total} players  (+{n_total - 10} more)"
                    if st.button(_exp_lbl, key=f"rr_btn::{selected_season}_{selected_round}_{game_idx}"):
                        st.session_state[expand_key] = not show_all
                        st.rerun()


# ════════════════════════════════════════════════════════════
# STAT FILTER
# ════════════════════════════════════════════════════════════
# Sample-games placeholder for a Votes cell with no vote assigned yet (2026).
# Deliberately not the "—" used elsewhere in the app.
_SF_NO_VOTES = '-'


@st.fragment
def _render_stat_filter():
    # ── 1. Header — no box ────────────────────────────────────
    st.markdown(
        '<div style="margin:2px 0 16px">'
        '<div style="font-size:10px;font-weight:700;letter-spacing:2px;'
        'text-transform:uppercase;color:#7e8c99">Stat Filter</div>'
        '<h1 style="font-family:\'Archivo\',sans-serif;font-size:34px;font-weight:800;'
        'color:#e9eef3;margin:4px 0 2px;line-height:1.05">Threshold to votes</h1>'
        '<div style="color:#7e8c99;font-size:13px">How historical Brownlow polling '
        'responds as you raise a stat threshold · 2007–2026</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.spinner("Loading historical games…"):
        hist = load_all_historical(_STAT_FILTER_COLS)
    if hist is None:
        st.error("No historical game-level data found. Run brownlow_model.py first.")
    else:
        # (No Brownlow.Votes NaN exist in any game_level file — 2026 votes are
        # 0-filled — so the old notna()+copy() dropped zero rows and only cost a
        # full-frame copy per rerun. Downstream 'Season < 2026' guards already
        # keep unassigned 2026 votes out of every rate.)

        # ── 2. Filters — flush, no panel. Widgets + logic unchanged ──
        all_players_sf = sorted(hist['Player_Name'].dropna().unique().tolist())
        selected_players_sf = st.multiselect("Player (leave blank for all)", all_players_sf, default=[], placeholder="All players", key="sf_players")

        col1, col2, col3 = st.columns(3)
        with col1:
            result_filter = st.radio("Game result", ["Either", "Win only", "Loss only"], horizontal=True, key="sf_result")
            min_disp = st.slider("Min disposals", 0, 50, 0, 1, key="sf_disp")
            min_goals = st.slider("Min goals", 0, 10, 0, 1, key="sf_goals")
            min_kicks = st.slider("Min kicks", 0, 40, 0, 1, key="sf_kicks")
        with col2:
            min_clearances = st.slider("Min clearances", 0, 15, 0, 1, key="sf_clear")
            min_contested = st.slider("Min contested possessions", 0, 25, 0, 1, key="sf_cont")
            min_coaches = st.slider("Min coaches votes", 0, 10, 0, 1, key="sf_cv")
            min_tackles = st.slider("Min tackles", 0, 12, 0, 1, key="sf_tack")
        with col3:
            min_score_inv = st.slider("Min score involvements", 0, 15, 0, 1, key="sf_si")
            has_rating = 'RatingPoints' in hist.columns
            min_rating = st.slider("Min Wheelo rating pts", 0, 100, 0, 1, key="sf_rating") if has_rating else 0
            season_range = st.slider("Season range", int(hist['Season'].min()), int(hist['Season'].max()),
                                     (int(hist['Season'].min()), int(hist['Season'].max())), key="sf_seasons")

        # Assemble the filter mask from components so the active stat's own
        # constraint can be dropped for the threshold sweep.
        _base_mask = (
            (hist['Season'] >= season_range[0]) & (hist['Season'] <= season_range[1]) &
            (hist['Player_Name'].isin(selected_players_sf) if selected_players_sf else pd.Series(True, index=hist.index))
        )
        if result_filter == "Win only": _base_mask &= (hist['Is_Win'] == 1)
        elif result_filter == "Loss only": _base_mask &= (hist['Is_Loss'] == 1)

        # (label, column, current value, slider min, slider max)
        _stat_sliders = [
            ('Disposals', 'Disposals', min_disp, 0, 50),
            ('Goals', 'Goals', min_goals, 0, 10),
            ('Kicks', 'Kicks', min_kicks, 0, 40),
            ('Clearances', 'Clearances', min_clearances, 0, 15),
            ('Contested possessions', 'Contested.Possessions', min_contested, 0, 25),
            ('Coaches votes', 'Coaches_Votes', min_coaches, 0, 10),
            ('Tackles', 'Tackles', min_tackles, 0, 12),
            ('Score involvements', 'Score_Involvements', min_score_inv, 0, 15),
        ]
        if has_rating:
            _stat_sliders.append(('Wheelo rating pts', 'RatingPoints', min_rating, 0, 100))

        # A slider still at its minimum is "no constraint", so skip the column
        # rather than comparing against it. `NaN >= 0` is False, so the old
        # unconditional comparison quietly dropped every row missing a stat even
        # when the user had asked for nothing: RatingPoints is null for all of
        # 2007–2014, so the default view lost those eight seasons entirely (and
        # Coaches_Votes nulls cost ~2.3k more rows). Above the minimum the
        # comparison is applied as before, NaN rows included in what it drops.
        mask = _base_mask.copy()
        for _lab, _col, _val, _mn, _mx in _stat_sliders:
            if _val > _mn:
                mask &= (hist[_col] >= _val)

        filtered_sf = hist[mask]
        total = len(filtered_sf)

        if total == 0:
            st.warning("No games match these filters.")
        else:
            # ── 3. Active stat — slider with the highest fraction-of-range
            #    currently engaged; fall back to disposals if none set above min.
            _engaged = [
                (_lab, _col, _val, _mn, _mx, (_val - _mn) / (_mx - _mn) if _mx > _mn else 0.0)
                for _lab, _col, _val, _mn, _mx in _stat_sliders if _val > _mn
            ]
            if _engaged:
                _engaged.sort(key=lambda r: r[5], reverse=True)
                active_label, active_col, active_val, active_min, active_max = _engaged[0][:5]
            else:
                active_label, active_col, active_val, active_min, active_max = _stat_sliders[0][:5]

            # ── 4. Threshold sweep — same poll/3-vote/avg formulas as the old
            #    disposal table, with the active stat's own min filter dropped so
            #    the full sweep shows. Votes only exist pre-2026.
            _sweep_mask = _base_mask & (hist['Season'] < 2026)
            for _lab, _col, _val, _mn, _mx in _stat_sliders:
                if _col != active_col and _val > _mn:
                    _sweep_mask &= (hist[_col] >= _val)
            # Only the stat columns (any may be the active one) + votes are read
            # from _sweep_base below — carry just those, not the full frame.
            _sweep_cols = [_c for _l, _c, _v, _m, _x in _stat_sliders] + ['Brownlow.Votes']
            _sweep_base = hist.loc[_sweep_mask, _sweep_cols]

            def _threshold_sweep(df, col, thresholds):
                """Poll rate, 3-vote rate and avg votes at each threshold of `col`.
                Identical formulas to the original disposal table (≥5-game guard)."""
                rows = []
                for t in thresholds:
                    sub = df[df[col] >= t]
                    if len(sub) >= 5:
                        v = sub['Brownlow.Votes']
                        rows.append({
                            'threshold': t, 'games': int(len(sub)),
                            'poll_rate': (v > 0).mean() * 100,
                            'three_rate': (v == 3).mean() * 100,
                            'avg_votes': v.mean(),
                        })
                return rows

            _thresholds = list(range(int(active_min), int(active_max) + 1))
            sweep = _threshold_sweep(_sweep_base, active_col, _thresholds)

            # Current-threshold position (same formulas) + zero-threshold baseline.
            _cur_sub = _sweep_base[_sweep_base[active_col] >= active_val]
            _cur_v = _cur_sub['Brownlow.Votes']
            cur_games = int(len(_cur_sub))
            cur_poll = (_cur_v > 0).mean() * 100 if cur_games > 0 else 0.0
            cur_three = (_cur_v == 3).mean() * 100 if cur_games > 0 else 0.0
            cur_avg = _cur_v.mean() if cur_games > 0 else 0.0
            base_poll = sweep[0]['poll_rate'] if sweep else cur_poll
            base_three = sweep[0]['three_rate'] if sweep else cur_three

            # Vote pool (pre-2026 only), reused for the breakdown strip. Only the
            # votes column is counted below, so carry just that.
            vote_data = filtered_sf.loc[filtered_sf['Season'] < 2026, ['Brownlow.Votes']]
            n3 = int((vote_data['Brownlow.Votes'] == 3).sum())
            n2 = int((vote_data['Brownlow.Votes'] == 2).sum())
            n1 = int((vote_data['Brownlow.Votes'] == 1).sum())
            n0 = int((vote_data['Brownlow.Votes'] == 0).sum())
            vote_total = len(vote_data)

            if (filtered_sf['Season'] == 2026).any():
                _n26 = int((filtered_sf['Season'] == 2026).sum())
                st.markdown(
                    f'<div style="color:#7e8c99;font-size:12px;margin:2px 0 6px">'
                    f'{_n26:,} of these are 2026 games. Votes not yet assigned, so all '
                    f'rates below use {season_range[0]}–2025.</div>',
                    unsafe_allow_html=True,
                )

            # ── 5. Hero chart — poll rate by threshold ────────────
            st.markdown(
                f'<div style="margin:14px 0 0">'
                f'<div style="font-family:\'Archivo\',sans-serif;font-size:18px;font-weight:700;'
                f'color:#e9eef3">Poll rate rises with {active_label.lower()}</div>'
                f'<div style="color:#7e8c99;font-size:12px;margin-top:2px">'
                f'tracking your active filter, set to {active_val}</div></div>',
                unsafe_allow_html=True,
            )
            if sweep:
                _tx     = [r['threshold'] for r in sweep]
                _poll   = [r['poll_rate'] for r in sweep]
                _three  = [r['three_rate'] for r in sweep]
                fig_sweep = go.Figure()
                fig_sweep.add_trace(go.Scatter(
                    x=_tx, y=_poll, name='Poll rate', mode='lines',
                    line=dict(color='#34d399', width=2.5),
                    fill='tozeroy', fillcolor='rgba(52,211,153,0.10)',
                    hovertemplate='≥%{x}<br>%{y:.1f}% poll<extra></extra>',
                ))
                fig_sweep.add_trace(go.Scatter(
                    x=_tx, y=_three, name='3-vote rate', mode='lines',
                    line=dict(color='#f0b429', width=2),
                    hovertemplate='≥%{x}<br>%{y:.1f}% 3-vote<extra></extra>',
                ))
                fig_sweep.add_vline(x=active_val, line=dict(color='#7e8c99', width=1, dash='dash'))
                fig_sweep.add_trace(go.Scatter(
                    x=[active_val], y=[cur_poll], mode='markers+text',
                    marker=dict(color='#34d399', size=11),
                    text=[f"{cur_poll:.1f}%"], textposition='top center',
                    textfont=dict(color='#34d399', size=12, family='IBM Plex Mono'),
                    showlegend=False, hoverinfo='skip',
                ))
                fig_sweep = apply_chart_theme(fig_sweep)
                fig_sweep.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(title=active_label, showgrid=False, zeroline=False),
                    yaxis=dict(title='%', rangemode='tozero',
                               gridcolor='rgba(140,165,185,.14)', zeroline=False),
                    legend=dict(orientation='h', y=1.14),
                    margin=dict(t=20, b=40), height=320, hovermode='x unified',
                )
                st.plotly_chart(fig_sweep, width='stretch', key="sf_sweep_chart", config=PLOTLY_TOUCH_CONFIG)
            else:
                st.markdown('<div style="color:#7e8c99;font-size:13px;margin:8px 0">'
                            'Not enough games to draw a threshold curve.</div>',
                            unsafe_allow_html=True)

            # ── 6. Current-position readout — 4-col strip, hairline rules ──
            def _readout_cell(label, value, value_colour, sub, first=False):
                _pad = 'padding:0 20px 0 0' if first else 'padding:0 20px'
                _bord = '' if first else 'border-left:1px solid rgba(140,165,185,.14)'
                _sub = (f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                        f'color:#7e8c99;text-align:right;margin-top:3px">{sub}</div>') if sub else ''
                return (
                    f'<div style="{_pad};{_bord}">'
                    f'<div style="font-size:10px;font-weight:700;letter-spacing:1.2px;'
                    f'text-transform:uppercase;color:#7e8c99">{label}</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:25px;font-weight:600;'
                    f'color:{value_colour};text-align:right;line-height:1.2">{value}</div>{_sub}</div>'
                )

            st.markdown(
                # auto-fit + minmax, not repeat(4,1fr): a 1fr track is minmax(auto,1fr)
            # and cannot shrink below its own min-content, so four readouts with
            # sub-captions ("vs 12.3% at zero") forced the page wider than a phone
            # rather than wrapping. auto-fit reflows to 2x2 then a single column
            # with no breakpoint to maintain.
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));'
            'margin:18px 0 4px">' +
                _readout_cell('Matching games', f'{cur_games:,}', '#e9eef3',
                              f'≥ {active_val} {active_label.lower()}', first=True) +
                _readout_cell('Poll rate', f'{cur_poll:.1f}%', '#34d399',
                              f'vs {base_poll:.1f}% at zero') +
                _readout_cell('3-vote rate', f'{cur_three:.1f}%', '#e9eef3',
                              f'vs {base_three:.1f}% at zero') +
                _readout_cell('Avg votes / game', f'{cur_avg:.3f}', '#e9eef3', '') +
                '</div>',
                unsafe_allow_html=True,
            )

            # ── 7. Vote breakdown — collapsed inline metadata strip ──
            def _vb(value, label):
                return (f'<span style="margin-right:24px">'
                        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:15px;'
                        f'color:#e9eef3">{value:,}</span> '
                        f'<span style="font-size:11px;color:#7e8c99">{label}</span></span>')
            st.markdown(
                '<div style="margin:16px 0 4px;padding-top:13px;'
                'border-top:1px solid rgba(140,165,185,.14)">'
                '<span style="font-size:10px;font-weight:700;letter-spacing:1.2px;'
                'text-transform:uppercase;color:#7e8c99;margin-right:18px">Vote breakdown</span>' +
                _vb(n3, '3-vote') + _vb(n2, '2-vote') + _vb(n1, '1-vote') +
                _vb(n0, '0-vote') + _vb(vote_total, 'pool') +
                '</div>',
                unsafe_allow_html=True,
            )

            # ── 8. Sample games — de-emphasised quiet table footer ──
            def _quiet_sf_table(df):
                rounded = _round_floats(df)
                float_fmt = {c: '{:.1f}' for c in rounded.select_dtypes(include=['float64', 'float32', 'float']).columns}
                def _cells(d):
                    out = pd.DataFrame('background-color:#0a1017; color:#7e8c99;', index=d.index, columns=d.columns)
                    if 'Player' in d.columns:
                        out['Player'] = 'background-color:#0a1017; color:#e9eef3;'
                    if 'Result' in d.columns:
                        out['Result'] = ['background-color:#0a1017; color:#34d399;' if v == 'W'
                                         else 'background-color:#0a1017; color:#7e8c99;' for v in d['Result']]
                    return out
                s = rounded.style.apply(_cells, axis=None).set_table_styles(_TABLE_STYLES)
                if float_fmt:
                    s = s.format(float_fmt)
                return s

            show_cols_sf = ['Season', 'Round_num', 'Player_Name', 'Playing.for',
                            'Disposals', 'Goals', 'Clearances', 'Contested.Possessions',
                            'Coaches_Votes', 'Is_Win', 'Brownlow.Votes']
            available_sf = [c for c in show_cols_sf if c in filtered_sf.columns]
            sample_sf = filtered_sf[available_sf].copy()
            sample_sf['Is_Win'] = sample_sf['Is_Win'].map({1: 'W', 0: 'L'})
            sample_sf = sample_sf.rename(columns={'Round_num': 'Rnd', 'Player_Name': 'Player',
                                                   'Playing.for': 'Team', 'Contested.Possessions': 'ContPoss',
                                                   'Coaches_Votes': 'CV', 'Is_Win': 'Result', 'Brownlow.Votes': 'Votes'})
            _sf_disp = sample_sf.sort_values(['Season', 'Rnd'], ascending=[False, False]).head(200).copy()
            # Display AFL round (season-aware) — display only, sort order unchanged
            _sf_disp['Rnd'] = [_display_round(r, s) for r, s in zip(_sf_disp['Rnd'], _sf_disp['Season'])]
            for col in _sf_disp.select_dtypes(include='float').columns:
                _sf_disp[col] = _sf_disp[col].round(1)
            # 2026 votes are 0-filled, not awarded, so a bare 0.0 here reads as
            # "did not poll". Blank those cells only; the rows stay (they still
            # show the stat line that matched) and every rate above already
            # drops them. Pre-formatted to the same '{:.1f}' the float path in
            # _quiet_sf_table would have applied, because the mixed column is
            # object dtype and no longer picked up by that formatter.
            if 'Votes' in _sf_disp.columns:
                _sf_disp['Votes'] = [
                    _SF_NO_VOTES if s == 2026 or pd.isna(v) else f'{v:.1f}'
                    for v, s in zip(_sf_disp['Votes'], _sf_disp['Season'])
                ]
            # Two bases on one line, so both get named. cur_games is the same
            # pre-2026 count the readout strip calls "Matching games" (`total`
            # counted 2026 in and put two different numbers behind the same
            # word). The 2026 rows are on screen but carry no votes, so they get
            # their own clause instead of being folded into either figure or
            # dropped from both: _shown_sf + _shown26_sf is exactly the row
            # count, so anyone counting rows on screen lands on a number the
            # caption shows. Sort is Season-descending, so the 2026 rows are the
            # ones the 200-row cap keeps.
            _shown_sf = int((_sf_disp['Season'] < 2026).sum())
            _shown26_sf = len(_sf_disp) - _shown_sf
            _pending_sf = (f', plus {_shown26_sf:,} from 2026 pending votes'
                           if _shown26_sf else '')
            st.markdown(
                f'<div style="margin:22px 0 6px;font-size:10px;font-weight:700;letter-spacing:1.5px;'
                f'text-transform:uppercase;color:#7e8c99">Sample games '
                f'<span style="font-weight:400;letter-spacing:0;text-transform:none">— showing '
                f'{_shown_sf:,} of {cur_games:,} matching{_pending_sf}</span></div>',
                unsafe_allow_html=True,
            )
            st.dataframe(_quiet_sf_table(_sf_disp), width='stretch', hide_index=True)
            st.caption("CV = coaches votes")


if _page == 'Stat Filter':
    _render_stat_filter()

# ══════════════════════════════════════════════════════════════
# LIVE TRACKER
# ════════════════════════════════════════════════════════════
def _rounds_of(s):
    """Parse a My_Rounds string ("0,3,7") to a set of display rounds.

    Display convention on both sides — "0" is Opening Round, and the values are
    compared straight against last_round / _disp_round, which are already
    offset. Do NOT apply the Round_num − 1 law here; it is already applied.

    One definition for the assembler and the render, which each carried an
    identical private copy before.
    """
    out = set()
    for t in str(s).split(","):
        t = t.strip()
        if t.lstrip("-").isdigit():
            out.add(int(t))
    return out


def _assemble_live_tracker(lt, game_df, watchlist):
    """Assemble every value the Live Tracker renders from, off (a) live AFL vote
    data, (b) the model's per-round Exp_Votes / Poll_Prob, and (c) the persisted
    watchlist. Rounds are AFL display numbering (0 = Opening Round); the model's
    Round_num is AFLTables numbering, so display = Round_num - 1.

    Dicts are keyed by normalise_name(player) throughout. Returns:
      totals, prev_totals, round_votes, model_to_date, model_remaining,
      projection, delta, team, name, model_pollers (display_round -> {norm names}),
      recon (hit / blanked / bolter),
      round_exp / round_pp (display_round -> {norm name -> value}),
      game_name / game_team (norm name -> model-frame name / team).

    round_exp, round_pp, game_name and game_team exist for the page rather than
    for this function: the render used to rebuild them in a second walk of the
    same game frame. They are produced here so the frame is touched once.
    """
    df = lt.get("df", pd.DataFrame())
    last_round = int(lt.get("last_round", 0) or 0)
    asm = {
        "last_round": last_round, "next_round": last_round + 1,
        # Carried through so consumers don't recompute it off the feed. It is
        # what disambiguates last_round == 0: that value means "nothing counted"
        # when is_live is False and "Opening Round counted" when it is True.
        "is_live": bool(lt.get("is_live", False)),
        "totals": {}, "prev_totals": {}, "round_votes": {},
        "model_to_date": {}, "model_remaining": {}, "projection": {}, "delta": {},
        "team": {}, "name": {}, "model_pollers": {},
        "round_exp": {}, "round_pp": {}, "game_name": {}, "game_team": {},
        "recon": {"hit": [], "blanked": [], "bolter": []},
    }
    if df is None or df.empty:
        return asm

    # ── actual cumulative totals + per-round history (live data) ──────────────
    for _, r in df.iterrows():
        p = r.get("Player", "")
        nn = normalise_name(p)
        asm["name"][nn] = p
        asm["team"][nn] = r.get("Team", "")
        asm["totals"][nn] = int(r.get("Total_Votes", 0) or 0)
        rv = r.get("Round_Votes", {})
        rv = {int(k): int(v) for k, v in rv.items()} if isinstance(rv, dict) else {}
        asm["round_votes"][nn] = rv
        asm["prev_totals"][nn] = sum(v for k, v in rv.items() if k < last_round)

    # ── model per-round signal: Exp_Votes (pace/projection) + Poll_Prob (pollers)
    if (game_df is not None and not getattr(game_df, "empty", True)
            and {"Exp_Votes", "Poll_Prob", "Round_num"} <= set(game_df.columns)):
        pcol = next((c for c in ("Player", "Player_Name") if c in game_df.columns), None)
        if pcol:
            # One pass over the ~7k-row game frame feeds every dict below.
            # normalise_name runs once per DISTINCT name (~600) through a lookup
            # instead of once per row per consumer.
            _raw = game_df[pcol]
            _lut = {v: normalise_name(v) for v in _raw.dropna().unique()}
            # A null name isn't in the lookup and maps to '' — which is what
            # normalise_name(NaN) returns, so null-named rows keep colliding on
            # the '' key exactly as they did row-by-row.
            _nn = _raw.map(_lut).fillna('')
            _rn = pd.to_numeric(game_df["Round_num"], errors="coerce")
            _ev = pd.to_numeric(game_df["Exp_Votes"], errors="coerce")
            _pp = pd.to_numeric(game_df["Poll_Prob"], errors="coerce")
            # Drop the rows the old int()/float() raised on: a Round_num that
            # won't convert (finals labels) or a non-numeric Exp_Votes. A genuine
            # NaN Exp_Votes is NOT a raise, so those rows stay — they still
            # register a name/team and a Poll_Prob, just no Exp_Votes.
            _keep = _rn.notna() & ~(_ev.isna() & game_df["Exp_Votes"].notna())
            _w = pd.DataFrame({"nn": _nn, "raw": _raw, "rn": _rn, "ev": _ev, "pp": _pp})
            if "Team" in game_df.columns:
                _w["team"] = game_df["Team"]
            _w = _w[_keep].copy()
            # trunc, not round: the old code went through int(), which truncates
            _w["dr"] = np.trunc(_w["rn"]).astype("int64") - 1   # AFLTables -> display

            _m = _w[_w["ev"].notna()]
            _tod = _m[_m["dr"] <= last_round]                   # counted (incl. OR) -> pace
            _rem = _m[(_m["dr"] > last_round) & (_m["dr"] <= 24)]   # future -> remaining
            asm["model_to_date"] = _tod.groupby("nn")["ev"].sum().to_dict()
            asm["model_remaining"] = _rem.groupby("nn")["ev"].sum().to_dict()

            # display round -> {norm name -> value}. dict(zip(...)) keeps
            # last-wins on a duplicate (round, player), matching the old
            # row-by-row assignment; the key is only created for a non-empty
            # group, matching the old setdefault.
            for _d, _s in _m.groupby("dr"):
                asm["round_exp"][int(_d)] = dict(zip(_s["nn"], _s["ev"]))
            for _d, _s in _w[_w["pp"].notna()].groupby("dr"):
                asm["round_pp"][int(_d)] = dict(zip(_s["nn"], _s["pp"]))

            # first-wins on name/team, matching the old setdefault
            _first = _w.drop_duplicates("nn")
            asm["game_name"] = dict(zip(_first["nn"], _first["raw"]))
            if "team" in _w.columns:
                asm["game_team"] = dict(zip(_first["nn"], _first["team"]))

            # projected pollers = top-3 Poll_Prob within each game (the project's
            # established per-game convention; matches the votes-feed marker set).
            # nlargest stays: its tie-break is first-occurrence, and a
            # sort_values/head rewrite would not reproduce that on ties.
            gkeys = [c for c in ("Round_num", "Home.team", "Away.team") if c in game_df.columns]
            grpkeys = gkeys if len(gkeys) > 1 else ["Round_num"]
            _psrc = game_df[grpkeys + ["Poll_Prob"]].copy()
            _psrc["_nn"] = _nn
            for gk, grp in _psrc.groupby(grpkeys):
                rn = int(gk[0]) if isinstance(gk, tuple) else int(gk)
                names = set(grp.nlargest(3, "Poll_Prob")["_nn"])
                asm["model_pollers"].setdefault(rn - 1, set()).update(names)

    # ── projection + vs-model delta (apples-to-apples through last_round) ──────
    for nn, tot in asm["totals"].items():
        asm["projection"][nn] = tot + asm["model_remaining"].get(nn, 0.0)
        asm["delta"][nn] = tot - asm["model_to_date"].get(nn, 0.0)

    # ── watchlist: last-round reconciliation ──────────────────────────────────
    # `watchlist` is the caller's poll picks (Player / Team / My_Rounds /
    # Settled), or None when nobody is signed in.
    #
    # Settled rows are skipped: a settled pick is a closed position, not a
    # standing call on a round.
    watched_last = set()
    if watchlist is not None and not watchlist.empty:
        for _, w in watchlist.iterrows():
            if bool(w.get("Settled", False)):
                continue
            wn = normalise_name(w.get("Player", ""))
            rounds = _rounds_of(w.get("My_Rounds", ""))
            if last_round > 0 and last_round in rounds:
                watched_last.add(wn)
                polled = asm["round_votes"].get(wn, {}).get(last_round, 0)
                rec = {"name": w.get("Player", ""), "team": w.get("Team", ""), "votes": polled}
                asm["recon"]["hit" if polled >= 1 else "blanked"].append(rec)

    # bolters = polled >=2 in last_round but never on the watchlist for it
    if last_round > 0:
        for nn, rv in asm["round_votes"].items():
            pts = rv.get(last_round, 0)
            if pts >= 2 and nn not in watched_last:
                asm["recon"]["bolter"].append({
                    "name": asm["name"].get(nn, nn), "team": asm["team"].get(nn, ""),
                    "votes": pts,
                })

    return asm


if _page == 'Live Tracker':
    import time as _time
    from datetime import datetime as _dt
    _count_night = _dt.now() >= _dt(2026, 9, 21)

    # ── fetch ────────────────────────────────────────────────
    _lt = fetch_live_brownlow_data()
    _lt_err  = _lt.get("error")
    _lt_df   = _lt.get("df", pd.DataFrame())
    _lt_feed = _lt.get("feed", [])
    _lt_last = _lt.get("last_round", 0)
    _lt_sn   = _lt.get("season_name", "")
    _lt_live = _lt.get("is_live", False)

    _lt_auto = False  # set in the utility line below; init so refresh guard is safe

    # ── named constants (single source for the reconciliation thresholds) ──
    BOLTER_MIN_VOTES = 2      # actual round votes ≥ this to count as a poll
    BOLTER_MODEL_MAX = 0.8    # model Exp_Votes below this = "nobody saw it coming"
    MISSED_MODEL_MIN = 1.0    # model Exp_Votes ≥ this and blanked = a real model miss
    MODEL_TOPN_ROUND = 5      # model's top-N by Exp_Votes for a given round
    MODEL_VOTE_FLOOR = 0.2    # project convention: ignore projected votes ≤ this (noise)
    UPCOMING_LEAD    = 2      # surface a watchlist target this many rounds ahead
    # (_LT_IFRAME_H = 880 was here. Removed, not left defined-but-unused: the
    # render passes height='content' so the frame sizes to its own document.)
    # This page is single-season by design — it has no Season control and is not
    # in _SEASON_PAGES, so `selected_season` is not its source of truth. One
    # constant feeds both the model frame and the public watchlist's season
    # column, so the two can never drift apart.
    _LT_SEASON       = 2026

    # Small fallback header for the error / no-data states only. The live panel
    # folds its own topbar (title + LIVE pill) into the single redesign iframe.
    _pill_txt = "LIVE" if _lt_live else "OFF-SEASON"
    _pill_col = "#34d399" if _lt_live else "#7e8c99"
    _hdr_html = f"""<!doctype html><html><head><meta charset="utf-8">
{_FONTS_LINKS}
<style>
  *{{margin:0;box-sizing:border-box}}
  body{{background:#0a1017;font-family:'Archivo',sans-serif;-webkit-font-smoothing:antialiased}}
  .wrap{{display:flex;align-items:center;justify-content:space-between;gap:16px}}
  .l{{display:flex;align-items:center;gap:14px}}
  h1{{font-size:34px;font-weight:800;letter-spacing:-.01em;line-height:1;color:#e9eef3}}
  .pill{{display:inline-flex;align-items:center;gap:7px;background:rgba(52,211,153,.12);
    color:{_pill_col};font-size:11px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;
    padding:5px 11px;border-radius:999px;font-family:'IBM Plex Mono',monospace}}
  .dot{{width:7px;height:7px;border-radius:50%;background:{_pill_col}}}
  .live .dot{{animation:pulse 1.4s ease-in-out infinite}}
  @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.3;transform:scale(.65)}}}}
  .comp{{color:#7e8c99;font-size:13px;font-family:'IBM Plex Mono',monospace;text-align:right}}
</style></head><body><div class="wrap">
  <div class="l"><h1>Live Tracker</h1>
    <span class="pill {'live' if _lt_live else ''}"><span class="dot"></span>{_pill_txt}</span></div>
  <div class="comp">{_lt_sn}</div>
</div></body></html>"""

    if _lt_err:
        st.iframe(_hdr_html, height=54)
        st.error(f"Could not fetch AFL tracker data: {_lt_err}")
        if st.button("Retry", key="lt_retry"):
            st.cache_data.clear()
            st.rerun()
    elif _lt_df.empty:
        st.iframe(_hdr_html, height=54)
        st.info(
            "Count night hasn't started yet — showing AFL's own Brownlow predictor data "
            "for the current season. This page will update automatically on count night."
        )
    else:
        if not _lt_live:
            st.info(
                "Count night hasn't started yet — showing AFL's own Brownlow predictor data "
                "for the current season. This page will update automatically on count night."
            )

        # ── shared assembly: live votes + model per-round signal + watchlist ──
        # A signed-in user's own poll picks are the watchlist, and the only
        # source there is. The private poll_watchlist that used to win here is
        # retired; everything downstream (Zone 1 recon, Zone 3 upcoming, the dot
        # legend, the 3-column grid) consumes this frame unchanged.
        #
        # An anonymous visitor gets no fetch at all — not a fetch-then-hide — and
        # the panels it feeds are dropped below, so the tracker renders as if the
        # feature doesn't exist.
        _cc_user = user_auth.current_user()
        _cc_uid  = _cc_user.get("id") if _cc_user else None
        _wl = user_auth.load_poll_picks(_cc_uid, _LT_SEASON) if _cc_uid else None
        # "A watchlist source exists". An empty frame is still a source: an
        # account with no picks owns the panel and sees it empty.
        _wl_visible = _wl is not None

        _lt_game = load_game(_LT_SEASON)
        _asm     = _assemble_live_tracker(_lt, _lt_game, _wl)

        # ── Public account watchlist ────────────────────────────────────────
        # The ★ set below and the poll picks feeding Zone 1/3 above are separate
        # on purpose and neither feeds the other: a ★ says "watching this player
        # all season", a pick says "backing him in round N". They are different
        # claims, the ★ set is capped at 30 by a DB trigger that picks have no
        # equivalent of, and merging them would quietly widen the "My watchlist
        # only" filter to players nobody starred.
        #
        # (_cc_user is read at the source selection above — it picks the frame.)
        if _cc_user and "cc_user_watchlist" not in st.session_state:
            user_auth.load_watchlist(_LT_SEASON)
        _cc_picks = set(st.session_state.get("cc_user_watchlist", set()))
        # Options come from the frame the tracker already loaded — no extra read.
        _cc_opts  = (sorted(_lt_game["Player_Name"].dropna().unique().tolist())
                     if _lt_game is not None and "Player_Name" in _lt_game.columns
                     else [])
        # The leaderboard's names come from the AFL feed; picks are stored as
        # model-frame names. normalise_name bridges the two — the same bridge
        # _assemble_live_tracker uses for the private watchlist.
        _cc_watch_nn = {normalise_name(p) for p in _cc_picks}
        # The toggle widget renders below the iframe, but the HTML above needs
        # its state, so read the stored value now. Streamlit keeps a widget's
        # value between runs and reruns on change, so this is never stale by
        # more than the rerun that is already happening.
        _cc_only = bool(_cc_user) and bool(
            st.session_state.get("cc_user_only", False))

        _disp_round = int(_asm["last_round"])     # AFL display round (already offset)
        _next_round = _disp_round + 1
        _round_lbl  = "Opening Round" if _disp_round == 0 else f"Round {_disp_round}"
        _race_rstr  = "OR" if _disp_round == 0 else f"R{_disp_round}"

        # team abbreviations (mirror of the leaderboard map; scoped per-branch)
        _LT_ABBR = {
            "Adelaide": "ADEL", "Brisbane Lions": "BRIS", "Brisbane": "BRIS",
            "Carlton": "CARL", "Collingwood": "COLL", "Essendon": "ESSE",
            "Fremantle": "FREO", "Geelong": "GEEL", "Gold Coast": "GCFC",
            "Greater Western Sydney": "GWS", "GWS": "GWS", "GWS Giants": "GWS",
            "Hawthorn": "HAWK", "Melbourne": "MELB", "North Melbourne": "NMFC",
            "Port Adelaide": "PORT", "Richmond": "RICH", "St Kilda": "STK",
            "Sydney": "SYD", "West Coast": "WCE", "Western Bulldogs": "WBD",
        }
        def _abbr(t):
            return _LT_ABBR.get(str(t), str(t)[:4].upper())

        # Per-round model signal keyed by AFL display round (= Round_num - 1).
        # Built in _assemble_live_tracker off the same single pass that produces
        # the pace/projection dicts — this page walked the 7k-row game frame a
        # second time to rebuild exactly these four.
        _round_exp = _asm["round_exp"]
        _round_pp  = _asm["round_pp"]
        _game_name = _asm["game_name"]
        _game_team = _asm["game_team"]

        def _model_topn(dr):
            _d = _round_exp.get(dr, {})
            return set(sorted(_d, key=lambda k: -_d[k])[:MODEL_TOPN_ROUND])

        # name / team resolution across live df, watchlist, and model game file
        _wl_name, _wl_team = {}, {}
        if _wl is not None and not _wl.empty:
            for _, _w in _wl.iterrows():
                _wn = normalise_name(_w.get("Player", ""))
                _wl_name[_wn] = _w.get("Player", "")
                _wl_team[_wn] = _w.get("Team", "")
        def _name_of(nn):
            return _asm["name"].get(nn) or _wl_name.get(nn) or _game_name.get(nn) or nn
        def _team_of(nn):
            return _asm["team"].get(nn) or _wl_team.get(nn) or _game_team.get(nn) or ""

        # watchlist "card" per display round (unsettled rows only).
        # _rounds_of is the module-level one now — this block carried a private
        # copy identical to the assembler's.
        _card_by_round = {}
        if _wl is not None and not _wl.empty:
            for _, _w in _wl.iterrows():
                if bool(_w.get("Settled", False)):
                    continue
                _wn = normalise_name(_w.get("Player", ""))
                for _R in _rounds_of(_w.get("My_Rounds", "")):
                    _card_by_round.setdefault(_R, set()).add(_wn)
        _your_card = _card_by_round.get(_disp_round, set())

        # ── leader race band ──────────────────────────────────
        _leader     = _lt_df.iloc[0]
        _leader_nm  = _leader["Player"]
        _leader_tm  = _leader["Team"]
        _leader_nn  = normalise_name(_leader_nm)
        _leader_tot = int(_leader["Total_Votes"])
        _second     = _lt_df.iloc[1] if len(_lt_df) > 1 else None
        _third      = _lt_df.iloc[2] if len(_lt_df) > 2 else None
        _second_tot = int(_second["Total_Votes"]) if _second is not None else 0
        _clear      = _leader_tot - _second_tot
        _leader_pace = _asm["delta"].get(_leader_nn)

        _chase_bits = []
        for _cr in (_second, _third):
            if _cr is not None and int(_cr["Total_Votes"]) > 0:
                _chase_bits.append((_cr["Player"], int(_cr["Total_Votes"])))
        if _chase_bits:
            _names_html = " &amp; ".join(f"<b>{_n}</b>" for _n, _ in _chase_bits)
            _gap = _chase_bits[0][1] - _leader_tot
            _gap_txt = f"(−{abs(_gap)})" if _gap < 0 else "(level)"
            _chase_html = (f'Chasing: {_names_html}, on {_chase_bits[0][1]} '
                           f'<span class="gap">{_gap_txt}</span>')
        else:
            _chase_html = '<span style="color:var(--muted2)">No chasers yet</span>'

        if _leader_pace is None:
            _pace_html = ""
        elif _leader_pace >= 0:
            _pace_html = f'<span class="pace">+{_leader_pace:.1f} vs model pace</span>'
        else:
            _pace_html = (f'<span style="color:var(--muted);font-family:var(--mono);'
                          f'font-weight:600">−{abs(_leader_pace):.1f} vs model pace</span>')
        _sub_html = _leader_tm + (f" &nbsp;·&nbsp; {_pace_html}" if _pace_html else "")

        # ── Zone 1: last counted round reconciliation ─────────
        def _av(nn):
            return int(_asm["round_votes"].get(nn, {}).get(_disp_round, 0))
        def _evr(nn):
            return float(_round_exp.get(_disp_round, {}).get(nn, 0.0))
        _topn1 = _model_topn(_disp_round)
        _cands = set(_your_card) | set(_topn1)
        for _nn, _rv in _asm["round_votes"].items():
            if _rv.get(_disp_round, 0):
                _cands.add(_nn)
        _bolters, _landed, _missed = [], [], []
        for _nn in _cands:
            _a = _av(_nn); _e = _evr(_nn)
            _oncard = _nn in _your_card
            _intopn = _nn in _topn1
            if _a >= BOLTER_MIN_VOTES and _e < BOLTER_MODEL_MAX and not _oncard:
                _bolters.append((_nn, _a, _e))
            elif _a > 0 and (_oncard or _intopn):
                _dot = "both" if (_oncard and _intopn) else ("you" if _oncard else "model")
                _landed.append((_nn, _a, _dot))
            elif _a == 0 and (_oncard or (_intopn and _e >= MISSED_MODEL_MIN)):
                _missed.append((_nn, _e, _oncard))
        _bolters.sort(key=lambda x: (-x[1], -x[2]))
        _landed.sort(key=lambda x: -x[1])
        _missed.sort(key=lambda x: -x[1])
        _bolters, _landed, _missed = _bolters[:6], _landed[:6], _missed[:6]

        # right-header tally: how many polled players the model's top-3 called
        _proj_set = _asm["model_pollers"].get(_disp_round)
        _polled_nns = [nn for nn, rv in _asm["round_votes"].items() if rv.get(_disp_round, 0)]
        _total_polled = len(_polled_nns)
        if _proj_set is not None and _total_polled:
            _called = sum(1 for nn in _polled_nns if nn in _proj_set)
            _z1_tally = f"{_called} of {_total_polled} called"
        else:
            _z1_tally = f"{_total_polled} polled" if _total_polled else ""

        def _vcls(v):
            return "v3" if v == 3 else ("v2" if v == 2 else ("v0" if v == 0 else ""))
        def _vtxt(v):
            return f"+{v}" if v > 0 else "0"
        def _rrow(dot, name, mexp, vhtml):
            _m = f'<span class="mexp">{mexp}</span>' if mexp else ""
            return (f'<div class="rrow"><span class="dot {dot}"></span>'
                    f'<span class="pl">{name}</span>{_m}{vhtml}</div>')

        _z1 = (f'<div class="recon-h bolt"><span title="Players polling well above model expectation">⚡ Bolters</span>'
               f'<span class="ct">polled, nobody called it · {len(_bolters)}</span></div>')
        if _bolters:
            for _nn, _a, _e in _bolters:
                _z1 += _rrow("none", _name_of(_nn), f"model {_e:.1f}",
                             f'<span class="vn {_vcls(_a)}">{_vtxt(_a)}</span>')
        else:
            _z1 += '<div class="empty">No bolters this round.</div>'

        _z1 += (f'<div class="recon-h hit" style="margin-top:16px;"><span>✓ Landed</span>'
                f'<span class="ct">polled, called by you or model · {len(_landed)}</span></div>')
        if _landed:
            for _nn, _a, _dot in _landed:
                _z1 += _rrow(_dot, _name_of(_nn), "",
                             f'<span class="vn {_vcls(_a)}">{_vtxt(_a)}</span>')
        else:
            _z1 += '<div class="empty">Nothing landed yet.</div>'

        _z1 += (f'<div class="recon-h cold" style="margin-top:16px;"><span>○ Missed</span>'
                f'<span class="ct">called, blanked · {len(_missed)}</span></div>')
        if _missed:
            for _nn, _e, _oncard in _missed:
                if _oncard:
                    _z1 += _rrow("you", _name_of(_nn), "your pick",
                                 '<span class="vn v0">0</span>')
                else:
                    _z1 += _rrow("model", _name_of(_nn), f"exp {_e:.1f}",
                                 '<span class="vn v0">0</span>')
        else:
            _z1 += '<div class="empty">No misses — every call polled.</div>'

        # ── Zone 2: cumulative leaderboard top 10 ─────────────
        # "My watchlist only" narrows the pool BEFORE the top-10 cut, so it
        # shows the user's best ten — not the field's best ten intersected with
        # their picks, which would usually be empty.
        _cc_pool = _lt_df
        if _cc_only and _cc_watch_nn:
            _cc_pool = _lt_df[_lt_df["Player"].map(
                lambda _p: normalise_name(_p) in _cc_watch_nn)]
        _show = _cc_pool[_cc_pool["Total_Votes"] > 0].head(10)
        if _show.empty:
            _show = _cc_pool.head(10)

        if _show.empty:
            # Only reachable with the filter on. The unfiltered field is never
            # empty here — the _lt_df.empty branch above already returned — so
            # this needs no equivalent for anonymous visitors.
            _z2 = ('<div class="empty">No one on your watchlist is in the '
                   'count yet.</div>')
        else:
            _lead_votes = max(1, int(_show.iloc[0]["Total_Votes"]))
            _lead_proj  = max(1.0, float(_asm["projection"].get(
                normalise_name(_show.iloc[0]["Player"]), _lead_votes)))

            # Rank movement stays measured against the FULL field: a watched
            # player's ▲/▼ means their move up the Brownlow, not up a filtered
            # subset of it.
            _prev_rank = {}
            if _disp_round > 0:
                _prev_tot, _have_hist = {}, False
                for _, _r in _lt_df.iterrows():
                    _rv = _asm["round_votes"].get(normalise_name(_r["Player"]), {})
                    if _rv:
                        _have_hist = True
                    _prev_tot[_r["Player"]] = sum(int(p) for rd, p in _rv.items() if int(rd) < _disp_round)
                if _have_hist:
                    _order = sorted(_prev_tot, key=lambda p: -_prev_tot[p])
                    _prev_rank = {p: i + 1 for i, p in enumerate(_order)}

            _z2 = ""
            for _i, (_, _r) in enumerate(_show.iterrows()):
                _nm = _r["Player"]; _tm = _r["Team"]; _nn = normalise_name(_nm)
                _act = int(_r["Total_Votes"]); _rank = int(_r["Rank"])
                _proj = _asm["projection"].get(_nn, _act)
                _d = _asm["delta"].get(_nn)
                _arr = '<span class="arr same">–</span>'
                if _prev_rank:
                    _pr = _prev_rank.get(_nm)
                    if _pr is not None and _pr != _rank:
                        _mv = _pr - _rank
                        _arr = (f'<span class="arr up">▲{_mv}</span>' if _mv > 0
                                else f'<span class="arr down">▼{abs(_mv)}</span>')
                if _d is None:
                    _dl = '<span class="lb-d">–</span>'
                elif _d >= 0:
                    _dl = f'<span class="lb-d pos">+{_d:.1f}</span>'
                else:
                    _dl = f'<span class="lb-d neg">−{abs(_d):.1f}</span>'
                _bw = max(0.0, min(100.0, _act / _lead_votes * 100))
                _pjx = max(0.0, min(100.0, _proj / _lead_proj * 100))
                _lead_cls = " lead" if _i == 0 else ""
                _star = '★' if _nn in _cc_watch_nn else ''
                _z2 += (
                    f'<div class="lb-row{_lead_cls}">'
                    f'<div class="lb-main"><span class="lb-star">{_star}</span>'
                    f'<span class="lb-rank">{_rank}</span>'
                    f'<span class="lb-nm">{_nm} <span class="tm">{_abbr(_tm)}</span> {_arr}</span>'
                    f'<span class="lb-v">{_act}</span>{_dl}'
                    f'<span class="lb-p">proj {_proj:.0f}</span></div>'
                    f'<div class="lb-bul"><div class="bf" style="width:{_bw:.0f}%"></div>'
                    f'<div class="pj" style="left:{_pjx:.0f}%"></div></div></div>'
                )

        # ── Zone 3: upcoming watchlist targets (forward rail) ──
        _up = []
        if _disp_round < 24 and _wl is not None and not _wl.empty:
            for _, _w in _wl.iterrows():
                if bool(_w.get("Settled", False)):
                    continue
                _wn = normalise_name(_w.get("Player", ""))
                _rv = _asm["round_votes"].get(_wn, {})
                if any(int(v) > 0 for v in _rv.values()):    # suppression: already polled
                    continue
                for _R in sorted(_rounds_of(_w.get("My_Rounds", ""))):
                    if (_R - UPCOMING_LEAD) <= _disp_round and _R > _disp_round:
                        _pp = _round_pp.get(_R, {}).get(_wn)
                        _pptxt = f"{_pp * 100:.0f}%" if _pp is not None else "pick"
                        _gold = _wn in _model_topn(_R)
                        _up.append((_R, _w.get("Player", ""), _pptxt, "both" if _gold else "you"))
        _up.sort(key=lambda x: (x[0], x[1]))
        _z3 = ""
        if _up:
            for _R, _nm, _pptxt, _dot in _up[:10]:
                _z3 += (f'<div class="up-row"><span class="dot {_dot}"></span>'
                        f'<span class="pl">{_nm}</span>'
                        f'<span class="up-rd">→ R{_R}</span>'
                        f'<span class="up-pp">{_pptxt}</span></div>')
        else:
            _z3 += f'<div class="empty">Nothing backed in the next {UPCOMING_LEAD} rounds.</div>'
        _z3 += ('<div class="up-note">Each drops the moment they poll. '
                "Blank when nothing's backed in range.</div>")
        _z3 += ('<div class="dotkey" style="margin-top:14px;">'
                '<span><span class="dot both"></span>you + model</span>'
                '<span><span class="dot you"></span>you</span></div>')

        # ── topbar display values ──
        _mode_txt = "Live count" if _count_night else "Prediction"
        _fetched  = _time.strftime("%H:%M:%S")
        _live_pill = ('<span class="live">LIVE</span>' if _lt_live else
                      '<span class="live" style="color:var(--muted);border-color:var(--hair2)">OFF-SEASON</span>')
        _pct = max(0.0, min(100.0, _disp_round / 24 * 100))

        # ── CSS: mockup tokens + structure verbatim (standalone votes-feed
        #    rules dropped per the redesign; .mexp retained — used by .rrow). ──
        # Fonts come from _FONTS_LINKS in the head, not an @import here — see
        # the constant at the top of this file for why the url must match the
        # shell's byte for byte.
        _LT_CSS = """<style>
  :root{
    --bg:#0a1017; --surface:#101a24; --surface2:#0d141d;
    --hair:rgba(140,165,185,.13); --hair2:rgba(140,165,185,.22);
    --emerald:#34d399; --gold:#f0b429; --red:#ef7a6d; --blue:#7fb0e0;
    --ink:#e7eef5; --muted:#8ca5b9; --muted2:#5e7589;
    --mono:'IBM Plex Mono',monospace; --disp:'Archivo',sans-serif;
  }
  *{box-sizing:border-box;margin:0;}
  html,body{height:100%;}
  body{background:var(--bg);color:var(--ink);font-family:var(--disp);-webkit-font-smoothing:antialiased;
    min-height:100vh;display:flex;flex-direction:column;overflow-y:auto;padding:18px 26px 16px;gap:0;}
  .mono{font-family:var(--mono);}

  /* ---- topbar ---- */
  .topbar{display:flex;align-items:baseline;justify-content:space-between;gap:18px;padding-bottom:12px;}
  .tl{display:flex;align-items:center;gap:14px;}
  .tl h1{font-size:24px;font-weight:900;letter-spacing:-.03em;}
  .live{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;
    color:var(--emerald);border:1px solid rgba(52,211,153,.3);border-radius:999px;padding:3px 9px;letter-spacing:.1em;}
  .live::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--emerald);}
  .tr{display:flex;align-items:center;gap:20px;font-family:var(--mono);font-size:11.5px;color:var(--muted2);letter-spacing:.03em;}
  .tr b{color:var(--muted);font-weight:500;}
  .tr a{color:var(--emerald);text-decoration:none;}

  /* ---- progress ---- */
  .prog{display:flex;align-items:center;gap:16px;padding:0 0 16px;}
  .prog .lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted2);white-space:nowrap;}
  .prog .track{flex:1;height:4px;background:var(--hair);border-radius:2px;overflow:hidden;}
  .prog .fill{height:100%;width:66.6%;background:linear-gradient(90deg,var(--emerald),var(--gold));}
  .prog .rd{font-family:var(--mono);font-size:12px;color:var(--ink);font-weight:600;white-space:nowrap;}

  /* ---- leader race band ---- */
  .race{display:grid;grid-template-columns:1fr auto auto;gap:36px;align-items:center;
    padding:20px 0 18px;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);}
  .race .eyebrow{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted2);margin-bottom:6px;}
  .race .name{font-size:clamp(38px,4.6vw,62px);font-weight:900;letter-spacing:-.035em;line-height:.92;}
  .race .sub{margin-top:8px;font-size:13.5px;color:var(--muted);}
  .race .sub .pace{color:var(--emerald);font-family:var(--mono);font-weight:600;}
  .race .chase{margin-top:10px;font-family:var(--mono);font-size:12px;color:var(--muted2);}
  .race .chase b{color:var(--ink);font-weight:600;}
  .race .chase .gap{color:var(--gold);}
  .stat{text-align:right;}
  .stat .v{font-family:var(--mono);font-weight:600;font-size:clamp(34px,4vw,50px);line-height:1;letter-spacing:-.02em;}
  .stat .v.em{color:var(--emerald);} .stat .v.gd{color:var(--gold);}
  .stat .k{font-family:var(--mono);font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted2);margin-top:8px;}

  /* ---- zones ---- */
  .zones{flex:1;min-height:0;display:grid;grid-template-columns:1.25fr 1.05fr .85fr;gap:0;}
  .zone{min-height:0;display:flex;flex-direction:column;padding:18px 26px;}
  .zone + .zone{border-left:1px solid var(--hair);}
  .zone:first-child{padding-left:0;} .zone:last-child{padding-right:0;}
  .ztitle{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted2);
    display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px;}
  .ztitle .rd{color:var(--gold);}

  /* watchlist chips */
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;}
  .chip{display:flex;flex-direction:column;gap:3px;border:1px solid var(--hair2);border-radius:9px;padding:8px 11px;min-width:0;}
  .chip .top{display:flex;align-items:center;gap:6px;}
  .dot{width:7px;height:7px;border-radius:50%;flex:none;}
  .dot.both{background:var(--gold);} .dot.model{background:var(--emerald);} .dot.you{background:var(--blue);}
  .dot.none{background:transparent;border:1px solid var(--muted2);}

  /* dot key */
  .dotkey{display:flex;flex-wrap:wrap;gap:12px;font-family:var(--mono);font-size:9.5px;color:var(--muted2);margin-bottom:16px;letter-spacing:.03em;}
  .dotkey span{display:flex;align-items:center;gap:5px;}

  /* unified reconciliation rows */
  .rrow{display:flex;align-items:center;gap:9px;padding:7px 0;border-bottom:1px solid var(--hair);font-size:13.5px;}
  .rrow:last-child{border-bottom:none;}
  .rrow .pl{flex:1;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .rrow .vn{font-family:var(--mono);font-weight:600;font-size:13px;}

  /* upcoming rail */
  .up-row{display:flex;align-items:center;gap:9px;padding:9px 0;border-bottom:1px solid var(--hair);font-size:13.5px;}
  .up-row .pl{flex:1;font-weight:500;}
  .up-rd{font-family:var(--mono);font-size:11px;color:var(--gold);}
  .up-pp{font-family:var(--mono);font-size:10.5px;color:var(--muted2);min-width:34px;text-align:right;}
  .up-note{font-family:var(--mono);font-size:10.5px;color:var(--muted2);opacity:.8;line-height:1.5;margin-top:12px;}
  .chip .nm{font-weight:600;font-size:13px;white-space:nowrap;}
  .chip .mt{font-family:var(--mono);font-size:10.5px;color:var(--muted2);}
  .legend{display:flex;gap:13px;font-family:var(--mono);font-size:9.5px;color:var(--muted2);margin-top:4px;letter-spacing:.03em;}
  .legend span{display:flex;align-items:center;gap:5px;}

  .divider{height:1px;background:var(--hair);margin:16px 0 14px;}

  /* reconciliation */
  .recon-row{margin-bottom:13px;}
  .recon-h{font-family:var(--mono);font-size:11px;letter-spacing:.04em;display:flex;align-items:center;gap:7px;margin-bottom:7px;}
  .recon-h .ct{color:var(--muted2);}
  .recon-h.bolt{color:var(--gold);} .recon-h.hit{color:var(--emerald);} .recon-h.blank{color:var(--red);}
  .recon-h.cold{color:var(--muted);}
  .names{display:flex;flex-wrap:wrap;gap:5px 10px;font-size:13px;}
  .names .pn{display:inline-flex;align-items:baseline;gap:5px;color:var(--ink);}
  .names .pn .vv{font-family:var(--mono);font-weight:600;font-size:11.5px;}
  .v3{color:var(--gold);} .v2{color:var(--emerald);} .v0{color:var(--muted2);}
  .empty{font-family:var(--mono);font-size:11.5px;color:var(--muted2);}

  /* leaderboard */
  .lb{display:flex;flex-direction:column;}
  .lb-row{padding:9px 0;border-bottom:1px solid var(--hair);}
  .lb-row:last-child{border-bottom:none;}
  .lb-main{display:grid;grid-template-columns:11px 18px 1fr auto auto auto;gap:10px;align-items:baseline;}
  /* Leading star cell. Always rendered, empty for unwatched players, so the
     rank column stays on one axis whether or not anyone is signed in. */
  .lb-star{font-size:10px;line-height:1;color:var(--gold);}
  .lb-rank{font-family:var(--mono);font-size:12px;color:var(--muted2);}
  .lb-nm{font-weight:600;font-size:14px;letter-spacing:-.01em;display:flex;align-items:center;gap:6px;}
  .lb-nm .tm{font-family:var(--mono);font-size:10px;color:var(--muted2);font-weight:400;}
  .arr{font-family:var(--mono);font-size:9px;font-weight:600;}
  .up{color:var(--emerald);} .down{color:var(--red);} .same{color:var(--muted2);opacity:.4;}
  .lb-v{font-family:var(--mono);font-weight:600;font-size:15px;text-align:right;min-width:26px;}
  .lb-d{font-family:var(--mono);font-weight:600;font-size:11.5px;text-align:right;min-width:38px;}
  .lb-d.pos{color:var(--emerald);} .lb-d.neg{color:var(--red);}
  .lb-p{font-family:var(--mono);font-size:10.5px;color:var(--muted2);text-align:right;min-width:48px;}
  .lb-bul{height:3px;background:var(--hair);border-radius:2px;position:relative;margin-top:7px;}
  .lb-bul .bf{height:100%;background:var(--muted);border-radius:2px;}
  .lb-row.lead .lb-bul .bf{background:var(--emerald);}
  .lb-bul .pj{position:absolute;top:-3px;width:2px;height:9px;background:var(--gold);}

  .mexp{font-family:var(--mono);font-size:9.5px;color:var(--muted2);opacity:.65;margin-right:12px;white-space:nowrap;}

  /* Tablet: three rails become two, Zone 3 spans the pair underneath.
     Lower-bounded at 701px so it cannot reach the phone block below. Without
     that bound BOTH rules match at 390px and only source order separates them —
     the same ordering hazard the nav CSS carries (see CLAUDE.md), and here it
     bites harder because _zones_css is concatenated AFTER _LT_CSS and would
     silently win on the anonymous path. Bounding the range means the phone
     block is the single source of truth below 700px on both paths. */
  @media(min-width:701px) and (max-width:1080px){.zones{grid-template-columns:1fr 1fr;}.zone:nth-child(3){grid-column:1/3;border-left:none;border-top:1px solid var(--hair);padding-top:16px;}body{overflow:auto;}}

  /* Phone: stack everything in one column.
     Two properties do the real work. .zones drops flex:1 so its height stops
     being "whatever the topbar/race band left over" and becomes content-driven,
     and .zone regains its min-content floor (min-height:0 is what let a zone box
     be shorter than its own content, so the surplus painted over the next row
     instead of growing it). display:block on .zones makes the grid-template
     columns inert, so neither 1080 rule nor _zones_css's base rule can reassert
     a multi-column layout here.
     The leaderboard gets a contained horizontal scroll rather than bleeding: its
     .lb-main floors (11+18+26+38+48 plus five 10px gaps, before the name) come
     to ~280px, which is far wider than a phone cell. */
  @media(max-width:700px){
    html,body{height:auto;}
    body{display:block;min-height:0;overflow:visible;padding:14px 16px;}
    .zones{display:block;flex:none;min-height:0;}
    .zone{min-height:auto;padding:16px 0;}
    .zone:first-child{padding-left:0;} .zone:last-child{padding-right:0;}
    .zone + .zone{border-left:none;border-top:1px solid var(--hair);}
    .zone:nth-child(3){grid-column:auto;padding-top:16px;}
    .lb{overflow-x:auto;-webkit-overflow-scrolling:touch;}
    .lb-main{min-width:280px;}
    .race{grid-template-columns:1fr;gap:14px;}
    .stat{text-align:left;}
  }
</style>"""

        # Watchlist-fed chrome. With no watchlist the "you"/"both" dots can never
        # appear, so the legend drops them; Zone 3 is entirely watchlist, so it
        # is omitted and the zone grid collapses to two columns rather than
        # leaving an empty rail. _zones_css is emitted after _LT_CSS, so equal
        # specificity lets it win without !important — which matters, because
        # !important here would also override the narrow-width media query.
        _z1_dotkey = (
            '<div class="dotkey">'
            + ('<span><span class="dot both"></span>you + model</span>'
               '<span><span class="dot you"></span>you</span>' if _wl_visible else '')
            + '<span><span class="dot model"></span>model</span>'
              '<span><span class="dot none"></span>nobody</span></div>'
        )
        # ── tracked H2H panel (rendered inside Zone 3) ────────
        # Display-only: this iframe is self-contained and cannot call back into
        # Streamlit, so the pair is managed from the Compare tab.
        #
        # Keyed on _LT_SEASON rather than the app-wide selected_season: the
        # tracker is always the live 2026 count, so a pair saved against another
        # season correctly does not surface here.
        #
        # It lives inside _z3_zone so neither grid-template-columns declaration
        # nor the 1080px media rule has to change. That ties it to Zone 3, which
        # is sound: Zone 3 renders whenever a watchlist SOURCE exists, an empty
        # frame counts as a source, and both it and a saved pair require sign-in
        # — so a signed-in user with a pair always has Zone 3.
        _h2h_panel = ''
        _h2h_pair = user_auth.load_h2h_pair(_cc_uid, _LT_SEASON) if _cc_uid else None
        if _h2h_pair:
            # fitzRoy ID -> current model-frame name. Preferred over the stored
            # name because a name only carries its '(Team)' suffix in seasons
            # where it collides, so the stored string can be stale.
            _h2h_id2name = {}
            if _lt_game is not None and 'ID' in _lt_game.columns:
                for _i, _n in zip(_lt_game['ID'], _lt_game['Player_Name']):
                    if pd.notna(_i) and pd.notna(_n):
                        try:
                            _h2h_id2name.setdefault(str(int(float(_i))), _n)
                        except (TypeError, ValueError):
                            continue

            def _h2h_resolve(nm, pid):
                _d = _h2h_id2name.get(str(pid)) if pid else None
                _d = _d or str(nm or '')
                return _d, normalise_name(_d)

            _hA_nm, _hA_nn = _h2h_resolve(_h2h_pair.get('player1'),
                                          _h2h_pair.get('player1_id'))
            _hB_nm, _hB_nn = _h2h_resolve(_h2h_pair.get('player2'),
                                          _h2h_pair.get('player2_id'))
            _hA_lbl, _hB_lbl = _h2h_short_pair(_hA_nm, _hB_nm)
            _hA_in = _hA_nn in _asm["totals"]
            _hB_in = _hB_nn in _asm["totals"]
            _hA_tot = int(_asm["totals"].get(_hA_nn, 0))
            _hB_tot = int(_asm["totals"].get(_hB_nn, 0))

            # Counted rounds. last_round == 0 is ambiguous on its own — nothing
            # counted, or Opening Round counted — so is_live decides, carried
            # through from the feed by the assembler.
            _h2h_counted = (set(range(0, int(_asm["last_round"]) + 1))
                            if _asm.get("is_live") else set())

            # ROUND NUMBERING: live rounds are AFL display numbering (0 = Opening
            # Round); the model frame's Round_num is AFLTables numbering, and
            # display = Round_num - 1 (see _assemble_live_tracker's docstring).
            # That is a JOIN KEY here, not a label, so the conversion happens
            # once, on the way in — every round value below is already display.
            def _h2h_model_rows(disp_name):
                _out = {}
                if _lt_game is None or not disp_name:
                    return _out
                for _, _r in _lt_game[_lt_game['Player_Name'] == disp_name].iterrows():
                    try:
                        _out[int(_r['Round_num']) - 1] = _r
                    except (TypeError, ValueError):
                        continue
                return _out

            _hA_rows, _hB_rows = _h2h_model_rows(_hA_nm), _h2h_model_rows(_hB_nm)
            _hA_rv = _asm["round_votes"].get(_hA_nn, {})
            _hB_rv = _asm["round_votes"].get(_hB_nn, {})

            _h2h_score = (
                '<div style="display:flex;align-items:baseline;justify-content:space-between;'
                'margin-top:9px">'
                + f'<span style="font-family:var(--mono);font-size:12px;'
                  f'color:{"#34d399" if _hA_tot >= _hB_tot else "#e9eef3"}">'
                  f'{_hA_lbl} {_hA_tot if _hA_in else "—"}</span>'
                + f'<span style="font-family:var(--mono);font-size:12px;'
                  f'color:{"#34d399" if _hB_tot >= _hA_tot else "#e9eef3"}">'
                  f'{_hB_tot if _hB_in else "—"} {_hB_lbl}</span>'
                + '</div>'
            )
            _h2h_margin = abs(_hA_tot - _hB_tot)
            _h2h_score += (
                '<div style="font-family:var(--mono);font-size:10px;text-align:center;'
                f'color:{"#34d399" if _h2h_margin else "#8a9aa9"};margin-top:2px">'
                f'{("+" + str(_h2h_margin)) if _h2h_margin else "LEVEL"}</div>'
            )
            if not (_hA_in and _hB_in):
                _h2h_score += ('<div class="empty" style="margin-top:4px">'
                               'not in count feed</div>')

            _h2h_body = ''
            # No model frame -> live totals only: no pmf, so no bar and no chips.
            if _lt_game is not None:
                _h2h_axis = sorted(set(_hA_rows) | set(_hB_rows) | _h2h_counted)
                # round_votes records only NON-ZERO votes, so an absent round is
                # normally "no votes OR not yet counted". Inside a COUNTED round
                # it does mean zero, because counted-ness asserts it — this is
                # the one place absence is read as a certain 0.
                _hA_cert = {_r: int(_hA_rv.get(_r, 0))
                            for _r in _h2h_axis if _r in _h2h_counted}
                _hB_cert = {_r: int(_hB_rv.get(_r, 0))
                            for _r in _h2h_axis if _r in _h2h_counted}
                _hA_d = _h2h_total_dist(_hA_rows, _h2h_axis, certain=_hA_cert)
                _hB_d = _h2h_total_dist(_hB_rows, _h2h_axis, certain=_hB_cert)
                _h2h_j = np.outer(_hA_d, _hB_d)
                _hA_w = float(np.tril(_h2h_j, -1).sum())
                _h2h_tie = float(np.trace(_h2h_j))
                _hB_w = float(np.triu(_h2h_j, 1).sum())

                _h2h_body += (
                    '<div style="display:flex;height:7px;border-radius:4px;overflow:hidden;'
                    'border:1px solid rgba(140,165,185,.14);margin-top:10px">'
                    f'<div style="width:{_hA_w * 100:.2f}%;background:#34d399"></div>'
                    f'<div style="width:{_h2h_tie * 100:.2f}%;background:#5a6b7a"></div>'
                    f'<div style="width:{_hB_w * 100:.2f}%;background:#1a2632"></div>'
                    '</div>'
                    '<div style="display:flex;justify-content:space-between;'
                    'font-family:var(--mono);font-size:9.5px;margin-top:4px">'
                    f'<span style="color:#34d399">LIVE WIN {_hA_w * 100:.0f}%</span>'
                    f'<span style="color:#8a9aa9">TIE {_h2h_tie * 100:.0f}%</span>'
                    f'<span style="color:#e9eef3">{_hB_w * 100:.0f}%</span>'
                    '</div>'
                )

                # Remaining swing rounds: uncounted only, same thresholds as the
                # Compare tab. Rounds here are already display numbers.
                _h2h_chips = []
                for _r in _h2h_axis:
                    if _r in _h2h_counted:
                        continue
                    _ra, _rb = _hA_rows.get(_r), _hB_rows.get(_r)
                    _pa = None if _ra is None else _h2h_num(_ra, 'Poll_Prob')
                    _pb = None if _rb is None else _h2h_num(_rb, 'Poll_Prob')
                    _sg = (_ra is not None and _rb is not None
                           and pd.notna(_ra.get('Game_ID'))
                           and _ra.get('Game_ID') == _rb.get('Game_ID'))
                    _k, _o, _ = _h2h_classify(_sg, _pa, _pb, _hA_lbl, _hB_lbl)
                    if _k in ('SAME GAME', 'SWING', 'FREE'):
                        _h2h_chips.append((_r, _k, _o))
                if _h2h_chips:
                    # gap applies on both axes, so a wrapped second row keeps the
                    # same 4px rhythm as the first; align-items keeps chips of
                    # differing label length on one baseline within a row.
                    _h2h_body += ('<div style="display:flex;flex-wrap:wrap;gap:4px;'
                                  'align-items:center;margin-top:9px">')
                    for _r, _k, _o in _h2h_chips[:H2H_LIVE_CHIPS]:
                        if _k == 'SAME GAME':
                            _cs = 'background:#3d3110;color:#f0b429'
                            # No beneficiary: the round is contested between them.
                            _ctxt = 'SAME GAME'
                        elif _o == 1:
                            _cs = 'background:#0f3d31;color:#34d399'
                            _ctxt = _hA_lbl.upper()
                        else:
                            _cs = ('background:#101a24;color:#e9eef3;'
                                   'box-shadow:inset 0 0 0 1px rgba(140,165,185,.14)')
                            _ctxt = _hB_lbl.upper()
                        _h2h_body += ('<span style="font-family:var(--mono);font-size:9px;'
                                      'padding:2px 6px;border-radius:8px;white-space:nowrap;'
                                      f'{_cs}">R{_r} {_ctxt}</span>')
                    if len(_h2h_chips) > H2H_LIVE_CHIPS:
                        _h2h_body += ('<span style="font-family:var(--mono);font-size:9px;'
                                      'padding:2px 6px;color:#8a9aa9">'
                                      f'+{len(_h2h_chips) - H2H_LIVE_CHIPS}</span>')
                    _h2h_body += '</div>'

            # Most recent counted round where either polled.
            _h2h_hits = [(_r, _hA_lbl, _v) for _r, _v in _hA_rv.items()
                         if _v and _r in _h2h_counted]
            _h2h_hits += [(_r, _hB_lbl, _v) for _r, _v in _hB_rv.items()
                          if _v and _r in _h2h_counted]
            if _h2h_hits:
                _lr = max(_r for _r, _, _ in _h2h_hits)
                _lw = [(_n, _v) for _r, _n, _v in _h2h_hits if _r == _lr]
                _lt_txt = ' · '.join(f'{_n} +{int(_v)}' for _n, _v in _lw)
                _h2h_body += ('<div style="font-family:var(--mono);font-size:9.5px;'
                              'color:#8a9aa9;margin-top:8px">'
                              f'LAST: R{_lr} — {_lt_txt}</div>')

            _h2h_panel = (
                '<div style="border-top:1px solid rgba(140,165,185,.14);'
                'margin-top:16px;padding-top:12px">'
                '<div class="ztitle"><span>My H2H · live</span></div>'
                + _h2h_score + _h2h_body
                + '</div>'
            )

        if _wl_visible:
            _z3_zone = (
                '<div class="zone">'
                '<div class="ztitle"><span>Upcoming targets</span>'
                f'<span>next {UPCOMING_LEAD} rounds</span></div>'
                f'{_z3}'
                f'{_h2h_panel}'
                '</div>'
            )
            _zones_css = ''
        else:
            _z3_zone   = ''
            # Lower-bounded at 701px for the same reason as _LT_CSS's tablet
            # rule: this string is concatenated AFTER _LT_CSS, so an unbounded
            # max-width:1080px would match at phone widths too and — at equal
            # (0,1,0) specificity — win on source order, quietly reinstating two
            # columns on a 390px screen for anonymous visitors only. Bounding it
            # leaves _LT_CSS's max-width:700px block as the one authority below
            # 700 on both paths. Same ordering hazard as the nav CSS (CLAUDE.md).
            _zones_css = ('<style>.zones{grid-template-columns:1.25fr 1.05fr;}'
                          '@media(min-width:701px) and (max-width:1080px)'
                          '{.zones{grid-template-columns:1fr 1fr;}}'
                          '</style>')

        _body = f'''<body>
  <div class="topbar">
    <div class="tl"><h1>Live Tracker</h1>{_live_pill}</div>
    <div class="tr">
      <span>Fetched <b>{_fetched}</b></span>
      <span>Mode <b>{_mode_txt}</b></span>
      <span>Source <a href="https://www.afl.com.au/brownlow-medal/live-tracker" target="_blank">AFL.com.au ↗</a></span>
    </div>
  </div>

  <div class="prog">
    <span class="lbl">Count progress</span>
    <div class="track"><div class="fill" style="width:{_pct:.1f}%"></div></div>
    <span class="rd">Round {_disp_round} of 24 counted</span>
  </div>

  <div class="race">
    <div>
      <div class="eyebrow">Leading the count</div>
      <div class="name">{_leader_nm}</div>
      <div class="sub">{_sub_html}</div>
      <div class="chase">{_chase_html}</div>
    </div>
    <div class="stat"><div class="v em">{_leader_tot}</div><div class="k">votes · {_race_rstr}</div></div>
    <div class="stat"><div class="v gd">+{_clear}</div><div class="k">clear</div></div>
  </div>

  <div class="zones">
    <div class="zone">
      <div class="ztitle"><span>{_round_lbl} · what happened</span><span>{_z1_tally}</span></div>
      {_z1_dotkey}
      {_z1}
    </div>

    <div class="zone">
      <div class="ztitle"><span>Leaderboard · top 10</span><span>votes / vs model / proj</span></div>
      <div class="lb">{_z2}</div>
    </div>

    {_z3_zone}
  </div>
</body>'''

        _full_html = ('<!doctype html><html><head><meta charset="utf-8">'
                      '<meta name="viewport" content="width=device-width, initial-scale=1">'
                      + _FONTS_LINKS + _LT_CSS + _zones_css + '</head>' + _body + '</html>')
        # height='content' rather than a fixed pixel count. The frame is srcdoc,
        # so it is same-origin and Streamlit can measure the document; a fixed
        # height cannot work here because the stacked phone layout is far taller
        # than the desktop one and the iframe cannot call back to renegotiate.
        # Letting it size to content is what hands scrolling back to the page
        # instead of leaving a scrollbar nested inside the frame.
        #
        # This pairs with the max-width:700px block, which sets html,body to
        # height:auto and min-height:0. Above that breakpoint body keeps
        # height:100% / min-height:100vh, so the desktop frame still measures a
        # viewport-height panel and .zones{flex:1} still has something to stretch
        # against — the single-viewport look _LT_IFRAME_H used to pin.
        st.iframe(_full_html, height='content')

        # ── Public account panel ────────────────────────────────────────────
        # Every control lives out here because the tracker is one self-contained
        # iframe and cannot call back into Streamlit. Hidden entirely when the
        # anon key isn't configured — a sign-in box that cannot work is worse
        # than no sign-in box.
        # The ★ watchlist only — signing in and out is the banner's job now, and
        # this expander no longer offers either. A visitor sees nothing here
        # because there is no watchlist to edit until they have an account; the
        # banner is where they get one.
        if _cc_user:
            with st.expander("Your watchlist", expanded=False):
                # Intersect with the current options: a player who has left
                # the season would otherwise be a default that isn't in
                # options, which Streamlit rejects outright.
                _cc_default = sorted(_cc_picks & set(_cc_opts))
                _cc_sel = st.multiselect(
                    "Players you expect to poll",
                    options=_cc_opts,
                    default=_cc_default,
                    max_selections=user_auth.WATCHLIST_MAX,
                    key="cc_user_picks",
                    placeholder="Add players you expect to poll…",
                    label_visibility="collapsed",
                )
                st.caption(
                    f"{len(_cc_sel)}/{user_auth.WATCHLIST_MAX} players · "
                    "shown as ★ on the leaderboard."
                )
                _cc_b1, _ = st.columns([1, 5])
                with _cc_b1:
                    # Disabled when there is nothing to save. A save cannot
                    # be "in flight" across renders — the script is
                    # synchronous — so the real double-submit guard is the
                    # cooldown inside save_watchlist().
                    if st.button("Save", key="cc_user_save", type="primary",
                                 use_container_width=True,
                                 disabled=(set(_cc_sel) == _cc_picks)):
                        _cc_ok, _cc_msg = user_auth.save_watchlist(
                            _cc_sel, _LT_SEASON)
                        if _cc_ok:
                            st.toast("Watchlist saved.")
                            st.rerun()
                        elif _cc_msg:
                            st.error(_cc_msg)

        # Tracker controls. The watchlist filter only exists for a signed-in
        # public user; when it isn't rendered Streamlit drops cc_user_only from
        # session state, which is exactly right — a signed-out visitor has no
        # filter state to remember.
        _lt_c1, _lt_c2 = st.columns([1, 3])
        with _lt_c1:
            _lt_auto = st.checkbox("Auto-refresh 5 min", value=False,
                                   key="lt_auto_refresh")
        with _lt_c2:
            if _cc_user and _cc_watch_nn:
                # No value= — session state is the source of truth, and toggling
                # reruns the page, which is what feeds _cc_only at the top.
                st.toggle("My watchlist only", key="cc_user_only")

    # ── auto-refresh ─────────────────────────────────────────
    # Matches the fetch_live_brownlow_data ttl, so each refresh lands on an
    # expired cache and actually pulls new votes. Move both together.
    if _lt_auto:
        _time.sleep(300)
        st.rerun()

# ════════════════════════════════════════════════════════════
# MODEL COMPARISON
# ════════════════════════════════════════════════════════════
if _page == 'Model Comparison':
    # ── 1. Header — no box ────────────────────────────────────
    st.markdown(
        '<div style="margin:2px 0 16px">'
        '<div style="font-size:10px;font-weight:700;letter-spacing:2px;'
        'text-transform:uppercase;color:#7e8c99">Model Comparison · 2026</div>'
        '<h1 style="font-family:\'Archivo\',sans-serif;font-size:34px;font-weight:800;'
        'color:#e9eef3;margin:4px 0 0;line-height:1.05">Five models, one view</h1>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Load all five data sources ────────────────────────────

    _mc_tab1, _mc_tab3 = st.tabs(['2026 (Live)', 'Insights'])

    with _mc_tab1:
        # theme.py tints [data-testid="stTabs"] with --surface; neutralise it for
        # this page only via :has(.mc-flush) so the content sits flush on
        # #0a1017. Tab-strip hairline + active underline are untouched.
        st.markdown(
            '<style>[data-testid="stTabs"]:has(.mc-flush){'
            'background:transparent !important;border:none !important;'
            'box-shadow:none !important;}</style>'
            '<span class="mc-flush" style="display:none"></span>',
            unsafe_allow_html=True,
        )

        _mc_cc_raw, _mc_wh_raw, _mc_wh_src = _load_model_comparison()

        # 1. Cha Ching
        _mc_cc_df = pd.DataFrame()
        if _mc_cc_raw is not None:
            _mc_cc_raw = _mc_cc_raw.sort_values('Exp_Total_Votes', ascending=False).reset_index(drop=True)
            _mc_cc_raw['CC_Rank'] = _mc_cc_raw.index + 1
            _cols_cc = ['Player_Name', 'Exp_Total_Votes', 'CC_Rank']
            if 'Team' in _mc_cc_raw.columns:
                _cols_cc.insert(1, 'Team')
            _mc_cc_df = _mc_cc_raw[_cols_cc].rename(
                columns={'Player_Name': 'Player', 'Exp_Total_Votes': 'CC_Votes'})
            _mc_cc_df['Player'] = _mc_cc_df['Player'].str.title().str.strip()
        _mc_cc_team = dict(zip(_mc_cc_df['Player'], _mc_cc_df['Team'])) \
            if 'Team' in _mc_cc_df.columns else {}

        # 2. AFL Predictor — CSV-primary, refreshed by scraper_afl.py on Run
        #    Update. The live API read lives on the Live Tracker, not here.
        _mc_afl_raw = fetch_afl_predictor_brownlow()
        _mc_afl_df = pd.DataFrame()
        if not _mc_afl_raw.empty and 'Total_Votes' in _mc_afl_raw.columns:
            _mc_afl_s = _mc_afl_raw.sort_values('Total_Votes', ascending=False).reset_index(drop=True)
            _mc_afl_s['AFL_Rank'] = _mc_afl_s.index + 1
            _mc_afl_df = _mc_afl_s[['Player', 'Total_Votes', 'AFL_Rank']].rename(
                columns={'Total_Votes': 'AFL_Votes'})
            _mc_afl_df['Player'] = _mc_afl_df['Player'].str.title().str.strip()
        _mc_afl_has_votes = not _mc_afl_df.empty and _mc_afl_df['AFL_Votes'].max() > 0

        # 3. Betfair — CSV-primary now (live pull is behind the refresh button
        #    below); the second return is unused, so it's discarded.
        _mc_bf_df, _ = fetch_betfair_brownlow()
        if not _mc_bf_df.empty and 'Player' in _mc_bf_df.columns:
            _mc_bf_df['Player'] = _mc_bf_df['Player'].str.title().str.strip()

        # 4. Wheelo — Wheelo's OWN published Brownlow predictions, summed per
        #    player. wheeloratings.com builds its leaderboard from the per-game
        #    'Votes' column in wheelo-brownlow-predictions.csv; summing it here
        #    reproduces that published leaderboard exactly (e.g. Heeney rank 7,
        #    not 5). Refreshed weekly by update_wheelo_2026.py via Run Update.
        #    Falls back to the match-stats ExpVotes sum only if the published
        #    file is absent — that is a different metric and undercounts because
        #    our match-stats scrape is missing rounds for some players.
        _mc_wh_df = pd.DataFrame()
        if _mc_wh_src == 'pub':
            if {'Player', 'Votes'} <= set(_mc_wh_raw.columns):
                _mc_wh_agg = (
                    _mc_wh_raw.groupby('Player')['Votes'].sum()
                    .reset_index().sort_values('Votes', ascending=False).reset_index(drop=True)
                )
                _mc_wh_agg['WH_Rank'] = _mc_wh_agg.index + 1
                _mc_wh_df = _mc_wh_agg.rename(columns={'Votes': 'WH_Votes'})
                _mc_wh_df['Player'] = _mc_wh_df['Player'].str.title().str.strip()
        elif _mc_wh_src == 'legacy':
            _mc_wh_col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in _mc_wh_raw.columns), None)
            if _mc_wh_col:
                _mc_wh_agg = (
                    _mc_wh_raw.groupby('Player')[_mc_wh_col].sum()
                    .reset_index().sort_values(_mc_wh_col, ascending=False).reset_index(drop=True)
                )
                _mc_wh_agg['WH_Rank'] = _mc_wh_agg.index + 1
                _mc_wh_df = _mc_wh_agg.rename(columns={_mc_wh_col: 'WH_Votes'})
                _mc_wh_df['Player'] = _mc_wh_df['Player'].str.title().str.strip()

        # 5. ESPN
        _mc_espn_df, _mc_espn_err = fetch_espn_brownlow()
        if not _mc_espn_df.empty and 'Player' in _mc_espn_df.columns:
            _mc_espn_df['Player'] = _mc_espn_df['Player'].str.title().str.strip()

        # ── Normalise names → _match_key on every model df ─────────
        for _ndf in [_mc_cc_df, _mc_afl_df, _mc_bf_df, _mc_wh_df, _mc_espn_df]:
            if not _ndf.empty and 'Player' in _ndf.columns:
                _ndf['_match_key'] = _ndf['Player'].apply(normalise_name)

        # Canonical display name: CC → AFL → BF → WH → ESPN (highest priority last)
        _mc_canonical: dict = {}
        for _ndf in [_mc_espn_df, _mc_wh_df, _mc_bf_df, _mc_afl_df, _mc_cc_df]:
            if not _ndf.empty and '_match_key' in _ndf.columns:
                for _, _nr in _ndf.iterrows():
                    _mc_canonical[_nr['_match_key']] = _nr['Player']

        # CC team lookup keyed by match_key (used by heatmap)
        _mc_cc_team = (
            dict(zip(_mc_cc_df['_match_key'], _mc_cc_df['Team']))
            if '_match_key' in _mc_cc_df.columns and 'Team' in _mc_cc_df.columns else {}
        )

        # ── Mismatch detection: top-25 players in only one model ───
        _MC_TOP_N = 25
        _mc_keys_per_model: list = []
        for _, _ndf, _, _, _ in [
            ('CC', _mc_cc_df, None, None, None),
            ('AFL', _mc_afl_df, None, None, None),
            ('BF', _mc_bf_df, None, None, None),
            ('WH', _mc_wh_df, None, None, None),
            ('ESPN', _mc_espn_df, None, None, None),
        ]:
            if not _ndf.empty and '_match_key' in _ndf.columns:
                _mc_keys_per_model.append(set(_ndf.head(_MC_TOP_N)['_match_key']))
            else:
                _mc_keys_per_model.append(set())
        _mc_all_keys = set().union(*_mc_keys_per_model)
        _mc_single_keys = {
            k for k in _mc_all_keys
            if sum(1 for ks in _mc_keys_per_model if k in ks) == 1
        }
        # Flag pairs of single-model keys that share first AND last word (likely same player)
        _mc_mismatch_pairs: list = []
        _mc_single_list = sorted(_mc_single_keys)
        for _i, _k1 in enumerate(_mc_single_list):
            _w1 = _k1.split()
            for _k2 in _mc_single_list[_i + 1:]:
                _w2 = _k2.split()
                if not _w1 or not _w2:
                    continue
                # Same first+last name OR one key's words are a subset of the other's
                _same_ends = _w1[0] == _w2[0] and _w1[-1] == _w2[-1]
                _subset = (set(_w1) <= set(_w2) and len(_w1) >= 2) or \
                          (set(_w2) <= set(_w1) and len(_w2) >= 2)
                if _same_ends or _subset:
                    _mc_mismatch_pairs.append(
                        (_mc_canonical.get(_k1, _k1), _mc_canonical.get(_k2, _k2))
                    )
        if _mc_mismatch_pairs:
            print("\n[Model Comparison] Possible name mismatches "
                  "(appear in only one model's top-25, but look like the same player):")
            for _ma, _mb in _mc_mismatch_pairs:
                print(f"  '{_ma}'  vs  '{_mb}'")
        else:
            print("\n[Model Comparison] No obvious name mismatches detected in top-25.")

        # ── Model registry ─────────────────────────────────────────
        _MC_MODELS = [
            ('Cha Ching',     _mc_cc_df,   'CC_Rank',   _MC_CC_PATH,  'metric-card-primary'),
            ('AFL Predictor', _mc_afl_df,  'AFL_Rank',  '',           'metric-card'),
            ('Betfair',       _mc_bf_df,   'BF_Rank',   _BF_CSV,      'metric-card'),
            ('Wheelo',        _mc_wh_df,   'WH_Rank',   _MC_WH_PATH,  'metric-card'),
            ('ESPN',          _mc_espn_df, 'ESPN_Rank',  _ESPN_CSV,    'metric-card'),
        ]
        # (Five model cards, summary cards, heatmap and scatter removed — the
        #  redesign renders a consensus headline, metadata strip and one
        #  consensus table below, after _pc_df is built.)

        # ── Player-centric consensus table ────────────────────────
        _MC_SEN = 40  # sentinel rank for "not in model's data"

        def _mc_lookup(df, match_key, rank_col):
            """Look up a player's rank by normalised match_key."""
            if df.empty or '_match_key' not in df.columns:
                return None
            _r = df[df['_match_key'] == match_key]
            return int(_r.iloc[0][rank_col]) if not _r.empty else None

        # Gather unique match keys from top 20 of each model
        _mc_all_keys_top20: set = set()
        for _, _mdf, _, _, _ in _MC_MODELS:
            if not _mdf.empty and '_match_key' in _mdf.columns:
                _mc_all_keys_top20.update(_mdf.head(20)['_match_key'].tolist())

        _pc_rows = []
        for _mk in _mc_all_keys_top20:
            _r_cc   = _mc_lookup(_mc_cc_df,   _mk, 'CC_Rank')
            _r_afl  = _mc_lookup(_mc_afl_df,  _mk, 'AFL_Rank')
            _r_bf   = _mc_lookup(_mc_bf_df,   _mk, 'BF_Rank')
            _r_wh   = _mc_lookup(_mc_wh_df,   _mk, 'WH_Rank')
            _r_espn = _mc_lookup(_mc_espn_df, _mk, 'ESPN_Rank')
            _avail  = [r for r in [_r_cc, _r_afl, _r_bf, _r_wh, _r_espn] if r is not None]
            _cons   = round(sum(_avail) / len(_avail), 1) if _avail else float(_MC_SEN)
            # Canonical display name: CC → AFL → BF → WH → ESPN
            _display = _mc_canonical.get(_mk, _mk)
            _pc_rows.append({'Player': _display, '_mk': _mk, '_cons': _cons,
                             '_cc': _r_cc, '_afl': _r_afl, '_bf': _r_bf,
                             '_wh': _r_wh, '_espn': _r_espn})

        _pc_df = (pd.DataFrame(_pc_rows)
                  .sort_values('_cons').reset_index(drop=True).head(25))
        _pc_df.insert(0, 'Consensus', range(1, len(_pc_df) + 1))

        def _rk(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return '—'
            return str(int(v))

        def _rk_valid(v):
            """True if v is a non-null, non-NaN rank value."""
            return v is not None and not (isinstance(v, float) and pd.isna(v))

        # ── Edge: how much higher Cha Ching ranks a player than the mean of
        #    the other four models. Positive = Cha Ching bullish. Derived from
        #    the same _pc_df ranks — no rank is re-sourced or recomputed.
        def _edge_for(row):
            cc = row['_cc']
            if not _rk_valid(cc):
                return None
            others = [row[c] for c in ('_afl', '_bf', '_wh', '_espn') if _rk_valid(row[c])]
            if not others:
                return None
            return int(round(sum(others) / len(others) - cc))
        _pc_df['_edge'] = _pc_df.apply(_edge_for, axis=1)

        # ── Summary counts (same logic the old summary cards used) ──
        _avail_models = [(_mdf, _mrc) for _, _mdf, _mrc, _, _ in _MC_MODELS if not _mdf.empty]
        _n_models = len(_avail_models)
        def _in_top10(df, match_key, rc):
            r = _mc_lookup(df, match_key, rc)
            return r is not None and r <= 10
        _all_agree_count = sum(
            1 for _, row in _pc_df[_pc_df['Consensus'] <= 10].iterrows()
            if all(_in_top10(df, row['_mk'], rc) for df, rc in _avail_models)
        )
        _agree_thr = max(3, _n_models - 1)
        _3of_agree_count = sum(
            1 for _, row in _pc_df[_pc_df['Consensus'] <= 10].iterrows()
            if sum(_in_top10(df, row['_mk'], rc) for df, rc in _avail_models) >= _agree_thr
        )
        # Cha Ching outliers = players whose edge magnitude is >= 5.
        _cc_outlier_count = int((_pc_df['_edge'].dropna().abs() >= 5).sum())

        # ── 2. Consensus headline (replaces the five model cards) ──
        _top = _pc_df.iloc[0]
        _top_ranks = [('Cha Ching', _top['_cc']), ('AFL', _top['_afl']),
                      ('Betfair', _top['_bf']), ('Wheelo', _top['_wh']), ('ESPN', _top['_espn'])]
        _n_top1 = sum(1 for _, r in _top_ranks if _rk_valid(r) and int(r) == 1)
        _agree_tag = ('unanimous across all five models' if _n_top1 == 5
                      else f'tops {_n_top1} of 5 models')
        st.markdown(
            f'<div style="margin:2px 0 12px;font-size:15px;color:#7e8c99">Consensus #1: '
            f'<span style="color:#34d399;font-weight:700;font-size:19px">{_top["Player"]}</span>'
            f'<span style="font-size:12px;color:#7e8c99"> · {_agree_tag}</span></div>',
            unsafe_allow_html=True,
        )

        def _agree_cell(label, rank, first=False):
            _v = _rk(rank)
            _c = '#34d399' if (_rk_valid(rank) and int(rank) == 1) else ('#7e8c99' if _v == '—' else '#e9eef3')
            _bd = '' if first else 'border-left:1px solid rgba(140,165,185,.14)'
            return (f'<div style="{_bd};padding:8px 16px">'
                    f'<div style="font-size:9px;font-weight:700;letter-spacing:1.2px;'
                    f'text-transform:uppercase;color:#7e8c99">{label}</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:18px;font-weight:600;'
                    f'color:{_c};text-align:left;font-variant-numeric:tabular-nums">{_v}</div></div>')
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(5,1fr);margin:0 0 22px;'
            'border-top:1px solid rgba(140,165,185,.14);border-bottom:1px solid rgba(140,165,185,.14)">' +
            ''.join(_agree_cell(_l, _r, _i == 0) for _i, (_l, _r) in enumerate(_top_ranks)) +
            '</div>',
            unsafe_allow_html=True,
        )

        # ── 4. Metadata strip (replaces the three summary cards) ──
        def _meta_cell(label, value, value_colour, sub, first=False):
            _pad = 'padding:0 22px 0 0' if first else 'padding:0 22px'
            _bd = '' if first else 'border-left:1px solid rgba(140,165,185,.14)'
            return (f'<div style="{_pad};{_bd}">'
                    f'<div style="font-size:10px;font-weight:700;letter-spacing:1.2px;'
                    f'text-transform:uppercase;color:#7e8c99">{label}</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:25px;font-weight:600;'
                    f'color:{value_colour};text-align:right;line-height:1.2;'
                    f'font-variant-numeric:tabular-nums">{value}</div>'
                    f'<div style="font-size:11px;color:#7e8c99;text-align:right;margin-top:3px">{sub}</div></div>')
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(3,1fr);margin:0 0 8px">' +
            _meta_cell('Full consensus', _all_agree_count, '#e9eef3',
                       'top 10 in every available model', first=True) +
            _meta_cell('Strong consensus', _3of_agree_count, '#e9eef3',
                       f'top 10 in at least {_agree_thr} models') +
            _meta_cell('Cha Ching outliers', _cc_outlier_count, '#34d399',
                       'edge of 5+ vs the field') +
            '</div>',
            unsafe_allow_html=True,
        )

        # ── 4a. AFL Predictor source freshness ──
        # No refresh button by design: the cadence is Run Update (scraper_afl.py),
        # and the live award-API read stays on the Live Tracker. This is a stamp
        # only, so the column can't go silently old without saying so.
        _afl_ts = _file_ts(_AFL_CSV)
        st.markdown(
            '<div style="font-size:11px;color:#7e8c99;margin:2px 0 10px">'
            f'AFL Predictor column · {"as of " + _afl_ts if _afl_ts else "never fetched"}'
            ' — a stored pull, not live (the Live Tracker reads the API direct).</div>',
            unsafe_allow_html=True,
        )

        # ── 4b. ESPN source freshness + opt-in refresh ──
        # Every column here is stored rather than live-read, so any of them can
        # be silently old — hence the stamps. ESPN's is a browser render, which
        # is why it also gets a refresh button (Betfair's is at 4c). The refresh
        # itself is ~20-30s of headless Chromium and is signed-in only: an
        # anonymous visitor must never be able to spawn a browser on the server.
        if _mc_espn_msg := st.session_state.pop("mc_espn_msg", None):
            st.success(_mc_espn_msg)
        _espn_ts = _file_ts(_ESPN_CSV)
        _espn_cap = (
            '<div style="font-size:11px;color:#7e8c99;margin:2px 0 10px">'
            f'ESPN column · {"as of " + _espn_ts if _espn_ts else "never fetched"}'
            ' — a stored render, not a live pull (ESPN publishes no feed).</div>'
        )
        if _is_admin:
            _es1, _es2 = st.columns([4, 1])
            _es1.markdown(_espn_cap, unsafe_allow_html=True)
            if _es2.button("Refresh ESPN", key="mc_espn_refresh",
                           help="Renders espn.com in a headless browser. Takes ~30s."):
                with st.spinner("Rendering ESPN — this takes ~30s…"):
                    _espn_ok, _espn_msg = _refresh_espn_live_to_csv()
                if _espn_ok:
                    # The frame above was already built from the old csv, so the
                    # rerun is what actually redraws the table.
                    fetch_espn_brownlow.clear()
                    st.session_state["mc_espn_msg"] = _espn_msg
                    st.rerun()
                else:
                    st.error(_espn_msg)
        else:
            st.markdown(_espn_cap, unsafe_allow_html=True)

        # ── 4c. Betfair source freshness + opt-in refresh ──
        # Same treatment as ESPN: Betfair's widget API is a Heroku backend whose
        # dyno sleeps off-season (~10s cold-wake), so it's a stored CSV read on
        # render now, with the live pull behind this signed-in button.
        if _mc_bf_msg := st.session_state.pop("mc_bf_msg", None):
            st.success(_mc_bf_msg)
        _bf_ts = _file_ts(_BF_CSV)
        _bf_cap = (
            '<div style="font-size:11px;color:#7e8c99;margin:2px 0 10px">'
            f'Betfair column · {"as of " + _bf_ts if _bf_ts else "never fetched"}'
            ' — a stored pull, not live (their API sleeps off-season).</div>'
        )
        if _is_admin:
            _bf1, _bf2 = st.columns([4, 1])
            _bf1.markdown(_bf_cap, unsafe_allow_html=True)
            if _bf2.button("Refresh Betfair", key="mc_bf_refresh",
                           help="Pulls Betfair's live JSON feed. Takes ~10s if their API is cold."):
                with st.spinner("Pulling Betfair — this can take ~10s…"):
                    _bf_ok, _bf_msg = _refresh_betfair_live_to_csv()
                if _bf_ok:
                    # The frame above was built from the old csv, so the rerun is
                    # what redraws the table.
                    fetch_betfair_brownlow.clear()
                    st.session_state["mc_bf_msg"] = _bf_msg
                    st.rerun()
                else:
                    st.error(_bf_msg)
        else:
            st.markdown(_bf_cap, unsafe_allow_html=True)

        # ── 5. Consensus ranking table (replaces table + heatmap + scatter) ──
        st.markdown(
            '<div style="margin:18px 0 4px;font-size:10px;font-weight:700;letter-spacing:1.5px;'
            'text-transform:uppercase;color:#7e8c99">Consensus ranking — top 25</div>',
            unsafe_allow_html=True,
        )

        def _mc_cell(v, colour):
            _t = _rk(v)
            _c = '#7e8c99' if _t == '—' else colour
            return (f'<td style="text-align:right;padding:7px 12px;color:{_c};'
                    f'border-bottom:1px solid rgba(140,165,185,.14)">{_t}</td>')

        _mc_th = ('text-align:right;padding:8px 12px;font-size:10px;letter-spacing:.12em;'
                  'text-transform:uppercase;border-bottom:1px solid rgba(140,165,185,.22)')
        _mc_head = (
            '<tr>'
            f'<th style="{_mc_th};color:#7e8c99">#</th>'
            f'<th style="{_mc_th};color:#7e8c99;text-align:left">Player</th>'
            f'<th style="{_mc_th};color:#34d399">Cha Ching</th>'
            + ''.join(f'<th style="{_mc_th};color:#7e8c99">{_h}</th>'
                      for _h in ('AFL', 'Betfair', 'Wheelo', 'ESPN'))
            + f'<th style="{_mc_th};color:#7e8c99">Edge</th>'
            '</tr>'
        )

        _mc_body = ''
        for _, _r in _pc_df.iterrows():
            _e = _r['_edge']
            if _e is None or (isinstance(_e, float) and pd.isna(_e)):
                _row_bg = ''
                _edge_html = '<span style="color:#7e8c99">—</span>'
            else:
                _ev = int(_e)
                if _ev >= 5:
                    _row_bg = 'background:rgba(52,211,153,0.07)'
                    _edge_html = f'<span style="color:#34d399;font-weight:600">value +{_ev}</span>'
                elif _ev <= -5:
                    _row_bg = 'background:rgba(240,180,41,0.07)'
                    _edge_html = f'<span style="color:#f0b429;font-weight:600">fade −{abs(_ev)}</span>'
                else:
                    _row_bg = ''
                    _edge_html = f'<span style="color:#7e8c99">±{abs(_ev)}</span>'
            _tc = _TEAM_COLOURS.get(_mc_cc_team.get(_r['_mk'], ''), '#7e8c99')
            _dot = (f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                    f'background:{_tc};margin-right:9px;vertical-align:middle"></span>')
            _mc_body += (
                f'<tr style="{_row_bg}">'
                f'<td style="text-align:right;padding:7px 12px;color:#7e8c99;'
                f'border-bottom:1px solid rgba(140,165,185,.14)">{_r["Consensus"]}</td>'
                f'<td style="text-align:left;padding:7px 12px;color:#e9eef3;'
                f'font-family:\'Archivo\',sans-serif;border-bottom:1px solid rgba(140,165,185,.14)">'
                f'{_dot}{_r["Player"]}</td>'
                + _mc_cell(_r['_cc'], '#34d399')
                + _mc_cell(_r['_afl'], '#e9eef3')
                + _mc_cell(_r['_bf'], '#e9eef3')
                + _mc_cell(_r['_wh'], '#e9eef3')
                + _mc_cell(_r['_espn'], '#e9eef3')
                + f'<td style="text-align:right;padding:7px 12px;'
                  f'border-bottom:1px solid rgba(140,165,185,.14)">{_edge_html}</td>'
                + '</tr>'
            )

        st.markdown(
            # Eight columns (# / Player / Cha Ching / AFL / Betfair / Wheelo /
            # ESPN / Edge). width:100% is only a PREFERRED width — min-content
            # wins, so on a phone this widened the page rather than itself.
            # Contained scroll, the Polls a Vote matrix pattern.
            '<div style="overflow-x:auto">'
            "<table style=\"width:100%;border-collapse:collapse;font-size:13px;margin-top:4px;"
            "font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums\">"
            + _mc_head + _mc_body + '</table></div>',
            unsafe_allow_html=True,
        )
        st.caption('Edge = mean of the other four models’ ranks minus Cha Ching’s rank. '
                   'Positive (emerald) = Cha Ching higher than the field; negative (gold) = lower.')

        # (Summary cards, rank heatmap and CC-vs-AFL scatter removed — folded
        #  into the consensus headline, metadata strip and table above.)

    with _mc_tab3:
        # ── Header: one muted context line (boxed title + stacked banners removed) ──
        st.markdown(
            '<div style="margin:2px 0 20px;font-size:13px;color:#7e8c99">'
            f'Feature importance and out-of-sample accuracy · XGBoost v4.0 · walk-forward back-test · {_BT_MIN}–{_BT_MAX}'
            '</div>',
            unsafe_allow_html=True,
        )

        bt = load_backtest()
        if bt is None:
            st.error("No backtest results found. Run backtest.py first.")
        else:
            # ── Backtest aggregation ──
            # Actual winner comes from the canonical medallist list (get_medallists),
            # NOT from vote totals in the data: a name-only max-vote derivation collides
            # same-name players (the two Josh Kennedys, two Scott Thompsons) and reports
            # the wrong winner for 2012/2014/2015. Each medallist is matched back to a
            # single player row by name AND team. 2012 is a joint medal (Mitchell &
            # Cotchin); a season counts as a top-N hit if EITHER winner ranks within N,
            # and "Pred. Rank" is the better (lower) of the two. The avg vote error does
            # not depend on the winner, so it is unchanged.
            rows_bt = []
            for season in sorted(bt['Season'].unique()):
                s = bt[bt['Season'] == season]
                top10_pred = s[s['Rank_Predicted'] <= 10].copy()
                avg_err = (top10_pred['Predicted_Votes'] - top10_pred['Actual_Votes']).abs().mean()

                medallists = get_medallists(season)
                winner_names = [nm for nm, _tm in medallists] or ['?']
                # Predicted rank of each medallist, matched on name AND team.
                winner_ranks = []
                for _nm, _tm in medallists:
                    _row = s[(s['Player'] == _nm) & (s['Team'] == _tm)]
                    if not _row.empty:
                        winner_ranks.append(int(_row['Rank_Predicted'].iloc[0]))
                # Better (lower) predicted rank; em-dash sentinel if no medallist matched.
                pred_rank = min(winner_ranks) if winner_ranks else '?'
                rows_bt.append({
                    'Season': int(season),
                    'Actual Winner': ' & '.join(winner_names),
                    'Pred. Rank': pred_rank,
                    'In Top 3': any(r <= 3 for r in winner_ranks),
                    'In Top 5': any(r <= 5 for r in winner_ranks),
                    'In Top 10': any(r <= 10 for r in winner_ranks),
                    'Avg Error Top 10': round(avg_err, 1),
                })
            acc_df = pd.DataFrame(rows_bt)
            n_seasons = len(acc_df)
            top3_acc = acc_df['In Top 3'].sum()
            top5_acc = acc_df['In Top 5'].sum()
            top10_acc = acc_df['In Top 10'].sum()
            avg_err_total = acc_df['Avg Error Top 10'].mean()

            def _ins_label(txt):
                st.markdown(
                    f'<div style="margin:30px 0 12px;font-size:10px;font-weight:700;letter-spacing:1.5px;'
                    f'text-transform:uppercase;color:#7e8c99">{txt}</div>',
                    unsafe_allow_html=True,
                )

            # ── 1. Accuracy funnel + avg vote error (replaces 4 stat cards + 3 labels) ──
            _ins_label('How accurate is the model')

            def _funnel_bar(label, count, total):
                pct = (count / total * 100) if total else 0
                return (
                    '<div style="display:grid;grid-template-columns:112px 1fr 58px;align-items:center;'
                    'gap:14px;margin:0 0 14px">'
                    f'<div style="font-size:12px;color:#7e8c99">{label}</div>'
                    '<div style="background:rgba(140,165,185,.08);border-radius:4px;height:32px">'
                    f'<div style="height:100%;width:{pct:.0f}%;background:#34d399;border-radius:4px;'
                    'display:flex;align-items:center;justify-content:flex-end;padding-right:11px;'
                    'box-sizing:border-box">'
                    f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;font-weight:700;'
                    f'color:#0a1017">{pct:.0f}%</span>'
                    '</div></div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;color:#7e8c99;'
                    f'text-align:right">{count}/{total}</div>'
                    '</div>'
                )

            _funnel_html = (
                _funnel_bar('Top 10', top10_acc, n_seasons)
                + _funnel_bar('Top 5', top5_acc, n_seasons)
                + _funnel_bar('Winner in top 3', top3_acc, n_seasons)
            )
            st.markdown(
                '<div style="display:grid;grid-template-columns:1.7fr 1fr;gap:34px;align-items:center;'
                'margin:6px 0 4px">'
                f'<div>{_funnel_html}</div>'
                '<div style="border-left:1px solid rgba(140,165,185,.14);padding-left:26px">'
                '<div style="font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;'
                'color:#7e8c99">avg vote error · top 10</div>'
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:46px;font-weight:600;'
                f'color:#e9eef3;line-height:1.15">{avg_err_total:.1f}</div>'
                '<div style="font-size:12px;color:#7e8c99;margin-top:8px;line-height:1.5">'
                'Strong on the field, modest on the outright — the predicted top 10 is ranked tightly, '
                'but pinning the exact medallist past the podium is closer to a coin-flip.</div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # ── 2. Season-by-season table (replaces old table + winner-rank bar chart) ──
            _ins_label('Season by season')
            _acc_sorted = acc_df.sort_values('Season', ascending=False)
            _th = ('padding:8px 12px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
                   'color:#7e8c99;border-bottom:1px solid rgba(140,165,185,.22)')
            _tbl_head = (
                '<tr>'
                f'<th style="{_th};text-align:left">Season</th>'
                f'<th style="{_th};text-align:left">Actual winner</th>'
                f'<th style="{_th};text-align:right">Predicted rank</th>'
                f'<th style="{_th};text-align:right">Avg error</th>'
                '</tr>'
            )
            _tbl_body = ''
            for _, _r in _acc_sorted.iterrows():
                _rank = _r['Pred. Rank']
                _is_num = isinstance(_rank, (int, float)) and not (isinstance(_rank, float) and pd.isna(_rank))
                _outside = _is_num and _rank > 10
                _row_bg = 'background:rgba(240,180,41,0.06)' if _outside else ''
                if _is_num:
                    _rk = int(_rank)
                    _rc = '#34d399' if _rk <= 3 else ('#e9eef3' if _rk <= 10 else '#f0b429')
                    _rank_disp = f'#{_rk}'
                else:
                    _rc = '#7e8c99'
                    _rank_disp = '—'
                _err = _r['Avg Error Top 10']
                _td = 'padding:7px 12px;border-bottom:1px solid rgba(140,165,185,.14)'
                _tbl_body += (
                    f'<tr style="{_row_bg}">'
                    f'<td style="{_td};color:#e9eef3;font-family:\'IBM Plex Mono\',monospace">{int(_r["Season"])}</td>'
                    f'<td style="{_td};color:#e9eef3">{_r["Actual Winner"]}</td>'
                    f'<td style="{_td};text-align:right;font-family:\'IBM Plex Mono\',monospace;'
                    f'color:{_rc};font-weight:600">{_rank_disp}</td>'
                    f'<td style="{_td};text-align:right;font-family:\'IBM Plex Mono\',monospace;'
                    f'color:#7e8c99">{_err:.1f}</td>'
                    '</tr>'
                )
            st.markdown(
                # Same containment as the model-vs-market table above.
                '<div style="overflow-x:auto">'
                '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:2px">'
                + _tbl_head + _tbl_body + '</table></div>',
                unsafe_allow_html=True,
            )
            st.caption('Predicted rank of the actual medallist. Emerald = top 3 · gold = outside top 10 '
                       '(row tinted) · plain = 4–10.')

            # ── 3. Predicted vs actual scatter (kept, restyled) ──
            _ins_label('Predicted vs actual votes — top 10 predicted')
            seasons_avail = sorted(bt['Season'].unique().astype(int).tolist())
            sel_s = st.selectbox("Season", seasons_avail, index=len(seasons_avail) - 1,
                                 key='acc_season_insights')
            s_data = bt[(bt['Season'] == sel_s) & (bt['Rank_Predicted'] <= 10)].copy().sort_values('Rank_Predicted')
            # Gold-highlight the canonical medallist(s) matched on name AND team — not the
            # data's max-vote row, which collides same-name players (see get_medallists).
            _sel_medallists = {(nm, tm) for nm, tm in get_medallists(sel_s)}
            _is_medallist = [(row['Player'], row['Team']) in _sel_medallists for _, row in s_data.iterrows()]
            fig_scatter = go.Figure()
            _sc_colors = ['#f0b429' if _m else '#34d399' for _m in _is_medallist]
            _sc_sizes = [16 if _m else 11 for _m in _is_medallist]
            fig_scatter.add_trace(go.Scatter(
                x=s_data['Actual_Votes'], y=s_data['Predicted_Votes'],
                mode='markers+text', marker=dict(size=_sc_sizes, color=_sc_colors),
                text=s_data['Player'], textposition='top center',
                textfont=dict(family="IBM Plex Mono, monospace", size=10, color='#e9eef3'),
                hovertemplate='<b>%{text}</b><br>Actual: %{x}<br>Predicted: %{y:.1f}<extra></extra>',
            ))
            max_v = max(s_data['Actual_Votes'].max(), s_data['Predicted_Votes'].max()) + 5
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_v], y=[0, max_v], mode='lines',
                line=dict(color='rgba(140,165,185,0.35)', dash='dash', width=1),
                showlegend=False, hoverinfo='skip',
            ))
            fig_scatter = apply_chart_theme(fig_scatter)
            fig_scatter.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title='Actual votes', range=[0, max_v]),
                yaxis=dict(title='Predicted votes', range=[0, max_v]),
                margin=dict(t=20, b=40), height=440, showlegend=False,
            )
            fig_scatter.update_xaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
            fig_scatter.update_yaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
            st.plotly_chart(fig_scatter, width='stretch', key='pred_actual_scatter_insights', config=PLOTLY_TOUCH_CONFIG)
            st.caption('Gold = actual winner · emerald = other top-10 predicted · dashed line = perfect prediction')

            # ── 4. Feature importance ──
            _ins_label('What drives Brownlow votes')
            if importance is None:
                st.error("Run brownlow_model.py first.")
            else:
                imp = importance.copy()
                imp['Importance %'] = (imp['Importance'] * 100).round(2)
                _imp_sorted = imp.sort_values('Importance %', ascending=False).reset_index(drop=True)
                _top_feat = _imp_sorted.iloc[0]['Feature']
                _top_pct = _imp_sorted.iloc[0]['Importance %']
                st.markdown(
                    '<div style="font-size:14px;color:#e9eef3;margin:0 0 14px">'
                    f'<span style="color:#34d399;font-weight:700">{_top_feat}</span> is the single strongest '
                    f'signal — <span style="font-family:\'IBM Plex Mono\',monospace">{_top_pct:.1f}%</span> '
                    'of total feature importance.</div>',
                    unsafe_allow_html=True,
                )

                def _imp_bar_fig(df_disp, n_emph=4):
                    d = df_disp.copy().reset_index(drop=True)
                    d['rank'] = range(1, len(d) + 1)
                    d = d.sort_values('Importance %', ascending=True)
                    colors = ['#34d399' if rk <= n_emph else 'rgba(52,211,153,0.4)' for rk in d['rank']]
                    fig = go.Figure(go.Bar(
                        x=d['Importance %'], y=d['Feature'], orientation='h',
                        marker=dict(color=colors),
                        text=[f"{v:.1f}%" for v in d['Importance %']],
                        textposition='outside',
                        textfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11),
                        hovertemplate='%{y}: %{x:.2f}%<extra></extra>',
                    ))
                    fig = apply_chart_theme(fig)
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(title='Importance (%)'),
                        margin=dict(l=210, r=44, t=10, b=16),
                        height=max(300, 26 * len(d)),
                    )
                    fig.update_xaxes(tickfont=dict(family="IBM Plex Mono, monospace", color="#7e8c99", size=11))
                    return fig

                _show_all = st.toggle("All features", value=False, key="show_all_feats_insights")
                if not _show_all:
                    st.plotly_chart(_imp_bar_fig(_imp_sorted.head(15)), width='stretch',
                                    key="feat_top15_insights",
                                    config=PLOTLY_TOUCH_CONFIG)
                else:
                    _n_bars = 25
                    st.plotly_chart(_imp_bar_fig(_imp_sorted.head(_n_bars)), width='stretch',
                                    key="feat_all_insights",
                                    config=PLOTLY_TOUCH_CONFIG)
                    _rest = _imp_sorted.iloc[_n_bars:].reset_index(drop=True)
                    if not _rest.empty:
                        _cells = ''
                        for _i, _rr in _rest.iterrows():
                            _cells += (
                                '<div style="display:flex;justify-content:space-between;gap:10px;'
                                'border-bottom:1px solid rgba(140,165,185,.08);padding:3px 0">'
                                f'<span><span style="color:#7e8c99">{_n_bars + _i + 1}.</span> '
                                f'<span style="color:#e9eef3">{_rr["Feature"]}</span></span>'
                                f'<span style="font-family:\'IBM Plex Mono\',monospace;color:#7e8c99">'
                                f'{_rr["Importance %"]:.1f}%</span>'
                                '</div>'
                            )
                        st.markdown(
                            '<div style="margin-top:10px;font-size:11px;display:grid;'
                            'grid-template-columns:1fr 1fr;gap:0 32px">' + _cells + '</div>',
                            unsafe_allow_html=True,
                        )

                with st.expander("What changed in v4.0", expanded=False):
                    st.markdown(
                        "**Late-season form** (`late_form_ewm`) — EWMA (span=5) of expected votes over the "
                        "prior 5 rounds; recent rounds weighted higher. Uses Wheelo ExpVotes where available, "
                        "otherwise Coaches Votes.\n\n"
                        "**Season momentum** (`momentum_cv`, `momentum_disp`) — average coaches votes and "
                        "disposals in the last 6 games minus the first 6. Positive = improving, negative = "
                        "declining.\n\n"
                        "**Late-season game weighting** — the last 5 rounds of each season receive 2× sample "
                        "weight during training."
                    )

def _render_rg_footer():
    """Full-bleed responsible-gambling footer, Midnight Turf styling.

    Rendered only on public (Brownlow) pages — every page NOT in _BH_PAGES.
    Static HTML, no JS/iframe. Called once at the dispatch chokepoint below.
    """
    st.markdown(
        '<div style="background:#101a24;border-top:1px solid rgba(140,165,185,.14);'
        'margin-left:calc(-50vw + 50%);margin-right:calc(-50vw + 50%);width:100vw;'
        'margin-top:32px;padding:16px 20px;color:#7e8c99;'
        'font-family:\'IBM Plex Mono\',monospace;font-size:11px;line-height:1.7;'
        'text-align:center;">'
        '<div style="letter-spacing:.18em;text-transform:uppercase;font-weight:600;'
        'color:#8ca5b9;">18+ &nbsp;&middot;&nbsp; Gamble responsibly</div>'
        '<div style="margin-top:4px;">Gambling Help Online &nbsp;&middot;&nbsp; '
        '1800 858 858 &nbsp;&middot;&nbsp; gamblinghelponline.org.au</div>'
        '<div style="margin-top:6px;max-width:640px;margin-left:auto;margin-right:auto;'
        'font-size:10px;color:#5f6f7d;">'
        'Cha Ching provides statistical analysis for informational and entertainment '
        'purposes only. It is not betting advice.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ════════════════════════════════════════════════════════════
# POLLS A VOTE
# ════════════════════════════════════════════════════════════
# Moved out of the Betting Hub in session 3. It was private-by-gate: the page
# read poll_watchlist through betting_hub's service_role client with no filter,
# and only _BH_PAGES membership kept Charlie's rows off a public screen. It is
# per-user now — user_poll_picks, read with the caller's JWT so RLS does the
# scoping — which is what makes it safe to render outside that gate.
#
# The season is pinned rather than taken from `selected_season`, exactly as the
# Live Tracker pins _LT_SEASON: this page has no Season control and is not in
# _SEASON_PAGES. One constant feeds the picks' season column, and it matches the
# 2026 model frame the consensus loaders below read.
_PAV_SEASON = 2026


def render_polls_a_vote(season: int):
    """Per-user Polls-a-Vote picks, for `season`.

    Lived in betting_hub behind the _BH_PAGES password until session 3. It is a
    public Brownlow page now: the consensus machinery below is shared and
    file-derived, and the only per-user data — the picks themselves — comes from
    user_poll_picks via user_auth, where RLS scopes it to the caller. Nothing
    here may reach for betting_hub's service_role client; it bypasses RLS and
    would serve one viewer's rows to every other.

    The BH stylesheet still owns .pav-* — the page carries its own look across
    rather than forking it, so _inject_css stays betting_hub's.
    """
    betting_hub._inject_css()
    # STEP 1 — masthead flushed onto #0a1017 via the innermost .pav-flush marker;
    # .pav-page marker scopes the field/button restyles below (no global override).
    st.markdown(
        '<span class="pav-page" style="display:none"></span>'
        '<div class="title-bar"><span class="pav-flush" style="display:none"></span>'
        '<h2 style="color:var(--text);margin:0">Polls a Vote Watchlist</h2>'
        '<p style="color:var(--muted);margin:4px 0 0 0">'
        'Track your "polls a vote" targets — five models, round by round</p></div>',
        unsafe_allow_html=True,
    )

    # ── Who is asking ─────────────────────────────────────────────────────────
    # The only identity this page knows. Admin is not consulted either — this is
    # a public page, and being the admin grants no claim on someone's picks.
    _pav_user = user_auth.current_user()
    _pav_uid  = _pav_user.get("id") if _pav_user else None

    # ── Data + consensus helpers (loaded once, used by matrix, cards, form) ─────
    # Picks are the only per-user data here. A visitor triggers no fetch at all —
    # not a fetch-then-hide — and gets the empty frame the zones below already
    # have empty states for. Everything after this line is shared, file-derived
    # and identical for every viewer.
    polls = (user_auth.load_poll_picks(_pav_uid, season) if _pav_uid
             else user_auth._empty_poll_picks())

    # ── Consensus reads are for signed-in users only ───────────────────────────
    # Every read below answers one question: "in the rounds you called, which
    # models tip this player?" With no picks there is nothing to ask it about,
    # and no zone a visitor sees touches the answers — the matrix, the cards and
    # the add form are all behind `_pav_user is None` branches. So the whole
    # consensus layer is nine uncached pd.read_csv calls that a visitor pays for
    # and never sees. This page went public in session 3; before that only one
    # signed-in person ever paid it.
    #
    # ANY LOADER ADDED BELOW MUST CARRY THIS GUARD. The reads degrade to the
    # empty defaults already initialised for them (that is the missing-file
    # path), so gating is just a missing file the page already knows how to
    # survive — no new failure mode, and the visitor's render is unchanged.
    _pav_load = bool(_pav_uid)

    # One cached read for all three of this page's game-frame needs. It replaces
    # three raw usecols reads of the same 8.7 MB / 166-column file — one for the
    # grid, one for the add-form player list, one for the add-form round lookup —
    # which re-parsed it from disk on EVERY rerun, including every checkbox tick
    # in the add form. Measured: 3 narrow parses ~290ms per rerun against ~15ms
    # for cache_data's frame copy.
    #
    # load_game is the same file behind @st.cache_data(ttl=3600) and is keyed by
    # season, so this shares the entry the Live Tracker and Leaderboard already
    # warm — usually no disk read at all. It returns None on a missing file,
    # which is exactly the degradation the os.path.exists guards gave us: every
    # consumer below already treats "no frame" as its empty default.
    #
    # Called ONCE and sliced. cache_data hands back a copy per call, so three
    # calls would be three copies of an 11 MB frame.
    _pav_game = load_game(season) if _pav_load else None

    _gdf = None  # per-round Poll_Prob source for the grid (the gold numbers)
    if _pav_game is not None:
        try:
            _gdf = _pav_game[['Player', 'Team', 'Round_num', 'Poll_Prob']]
        except Exception:
            # A missing column raises here where usecols used to — same outcome,
            # _gdf stays None and the grid degrades as it always has.
            pass

    # Current round anchor — latest round present in the predictions source (NOT
    # hardcoded). Matrix column index = Round_num - 1 (same convention as
    # _model_top3 and the round labels OR..R24). Degrades to None if unavailable.
    _cur_idx = None
    if _gdf is not None and not _gdf.empty and 'Round_num' in _gdf.columns:
        try:
            _cur_idx = int(_gdf['Round_num'].max()) - 1
        except Exception:
            _cur_idx = None

    # Player list for the Add form dropdown
    _pav_all_players: list[str] = []
    _pav_player_team: dict[str, str] = {}
    if _pav_game is not None:
        try:
            _pav_plist = _pav_game[['Player', 'Team']].dropna(subset=['Player'])
            _pav_player_team = (
                _pav_plist.drop_duplicates('Player').set_index('Player')['Team'].to_dict()
            )
            _pav_all_players = sorted(_pav_player_team.keys())
        except Exception:
            pass

    import re as _re
    _NAME_SUFFIX_RE = _re.compile(r'\s+(Jr\.?|Sr\.?|II|III|IV)$', _re.IGNORECASE)

    def _norm(name) -> str:
        """Join key for the five-way consensus. One definition, in features.py,
        shared with the Wheelo and coaches merges in predict_2026.py.

        The local version this replaces title-cased and stripped apostrophes,
        hyphens and suffixes, so it already collapsed McKay/Mckay and
        O'Sullivan/OSullivan. It did not handle periods, accents or a middle
        initial, so Wheelo's "Bailey J. Williams" keyed to nobody. Used only as
        a dict key, never displayed."""
        return feat.normalise_name(name)

    # ── Cross-model consensus thresholds (named) ───────────────────────────────
    CC_ROUND_THRESH     = 0.35   # Cha Ching: round Poll_Prob >= this = tips that round
    WHEELO_ROUND_THRESH = 0.5    # Wheelo: round ExpVotes >= this = tips that round
    BF_ROUND_THRESH     = 1.0    # Betfair: round vote >= 1 = tipped to poll that round
    AFL_ROUND_THRESH    = 1.0    # AFL Predictor: round vote >= 1 = tipped to poll that round
    ESPN_ROUND_THRESH   = 0.5    # ESPN: round vote >= 0.5 = tips (ESPN's min published spread value)
    CC_SEASON_THRESH    = 0.35   # Cha Ching: season max Poll_Prob "on the radar"
    WH_SEASON_THRESH    = 0.65   # Wheelo: season sum "on the radar"

    _con_max_prob:  dict[str, float] = {}
    _con_afl:       dict[str, float] | None = None
    _con_wheelo:    dict[str, float] = {}
    _con_bf:   dict[str, float] | None = None
    _con_espn: dict[str, float] | None = None
    # Round-level lookups (display/AFL round convention: 0 = Opening Round).
    _con_cc_round: dict[str, dict[int, float]] = {}            # CC per-round Poll_Prob
    _con_wheelo_round: dict[str, dict[int, float]] = {}        # Wheelo per-round ExpVotes
    _con_bf_round: dict[str, dict[int, float]] | None = None   # Betfair per-round votes
    _con_afl_round: dict[str, dict[int, float]] | None = None  # AFL Predictor per-round votes
    _con_espn_round: dict[str, dict[int, float]] | None = None  # ESPN per-round votes
    _espn_rounds_covered: set[int] = set()                     # rounds ESPN published (any game)
    try:
        # 1. Cha Ching: max Poll_Prob per player (season) + per-round (verdict).
        #    Round key = Round_num - 1 (display/AFL convention).
        if _gdf is not None:
            for _cp, _cg in _gdf.groupby('Player'):
                _ck = _norm(_cp)
                _con_max_prob[_ck] = float(_cg['Poll_Prob'].max())
                _con_cc_round[_ck] = {
                    int(_rr['Round_num']) - 1: float(_rr['Poll_Prob'])
                    for _, _rr in _cg.iterrows()
                }
        # 2. AFL Predictor — season totals (radar) from scraper_afl.py (the
        #    official AFL award API). Previously this slot read season_2026.csv,
        #    which is Cha Ching's OWN output — a mislabel that double-counted Cha
        #    Ching. Now it's real AFL data.
        _afl_csv = "data_2026/afl_predictor_predictions.csv"
        if _pav_load and os.path.exists(_afl_csv):
            _afldf = pd.read_csv(_afl_csv)
            if 'Total_Votes' in _afldf.columns:
                _con_afl = {_norm(r['Player']): float(r['Total_Votes'] or 0)
                            for _, r in _afldf.iterrows()}
        # 2b. AFL Predictor — per-round votes (verdict) from afl_predictor_round_votes.csv.
        #     Rounds are AFL/display convention, matching My_Rounds and the others.
        _afl_round_csv = "data_2026/afl_predictor_round_votes.csv"
        if _pav_load and os.path.exists(_afl_round_csv):
            _aflr = pd.read_csv(_afl_round_csv)
            if {'Player', 'Round', 'Vote'} <= set(_aflr.columns):
                _con_afl_round = {}
                for _, _rr in _aflr.iterrows():
                    _con_afl_round.setdefault(_norm(_rr['Player']), {})[
                        int(_rr['Round'])] = float(_rr['Vote'] or 0)
        # 3. Wheelo: season sum (radar) + per-round ExpVotes (verdict).
        #    Round key = Round - 1 (wheelo_2026.csv Round is AFLTables convention,
        #    same +1 as CC). NaN ExpVotes rounds are skipped → NA, not disagree.
        _wh26 = "data_wheelo/wheelo_2026.csv"
        if _pav_load and os.path.exists(_wh26):
            _whdf = pd.read_csv(_wh26)
            _wh_col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in _whdf.columns), None)
            if _wh_col:
                for _wp, _wg in _whdf.groupby('Player'):
                    _con_wheelo[_norm(_wp)] = float(_wg[_wh_col].sum())
            if 'ExpVotes' in _whdf.columns and 'Round' in _whdf.columns:
                for _wp, _wg in _whdf.groupby('Player'):
                    _wk = _norm(_wp)
                    for _, _wr in _wg.iterrows():
                        if pd.isna(_wr['ExpVotes']) or pd.isna(_wr['Round']):
                            continue
                        _con_wheelo_round.setdefault(_wk, {})[
                            int(_wr['Round']) - 1] = float(_wr['ExpVotes'])
        # 4. Betfair — season totals (radar) from the cached CSV.
        _bf_csv = "data_2026/betfair_predictions.csv"
        if _pav_load and os.path.exists(_bf_csv):
            _bfdf = pd.read_csv(_bf_csv)
            if 'Total_Votes' in _bfdf.columns:
                _con_bf = {_norm(r['Player']): float(r['Total_Votes'] or 0)
                           for _, r in _bfdf.iterrows()}
        # 4b. Betfair — per-round votes (round verdict) from betfair_round_votes.csv,
        #     written by scraper_betfair.py from the same JSON feed. Rounds are
        #     AFL/display convention, matching My_Rounds and CC Round_num-1.
        _bf_round_csv = "data_2026/betfair_round_votes.csv"
        if _pav_load and os.path.exists(_bf_round_csv):
            _bfr = pd.read_csv(_bf_round_csv)
            if {'Player', 'Round', 'Vote'} <= set(_bfr.columns):
                _con_bf_round = {}
                for _, _rr in _bfr.iterrows():
                    _con_bf_round.setdefault(_norm(_rr['Player']), {})[
                        int(_rr['Round'])] = float(_rr['Vote'] or 0)
        # 5. ESPN — season totals (radar) from the cached CSV.
        _espn_csv = "data_2026/espn_predictions.csv"
        if _pav_load and os.path.exists(_espn_csv):
            _espndf = pd.read_csv(_espn_csv)
            if 'Total_Votes' in _espndf.columns:
                _con_espn = {_norm(r['Player']): float(r['Total_Votes'] or 0)
                             for _, r in _espndf.iterrows()}
        # 5b. ESPN — per-round votes (verdict) from espn_round_votes.csv, written by
        #     scraper_espn.py. Rounds are AFL/display convention (0 = Opening Round),
        #     matching the others. ESPN names only vote-getters, so absence in a
        #     covered round is disagreement, not silence — _espn_rounds_covered records
        #     which rounds ESPN published so a missing player reads TIPS_OTHER, not NA.
        _espn_round_csv = "data_2026/espn_round_votes.csv"
        if _pav_load and os.path.exists(_espn_round_csv):
            _espnr = pd.read_csv(_espn_round_csv)
            if {'Player', 'Round', 'Vote'} <= set(_espnr.columns):
                _con_espn_round = {}
                for _, _rr in _espnr.iterrows():
                    _rnd = int(_rr['Round'])
                    _con_espn_round.setdefault(_norm(_rr['Player']), {})[
                        _rnd] = float(_rr['Vote'] or 0)
                    _espn_rounds_covered.add(_rnd)
    except Exception:
        pass

    def _consensus_score(player: str) -> tuple[int, int]:
        key = _norm(player)
        agree, total = 0, 0
        if _con_max_prob:
            total += 1
            if _con_max_prob.get(key, 0) >= CC_SEASON_THRESH:
                agree += 1
        if _con_afl is not None:
            total += 1
            if _con_afl.get(key, 0) > 0:
                agree += 1
        if _con_wheelo:
            total += 1
            if _con_wheelo.get(key, 0) >= WH_SEASON_THRESH:
                agree += 1
        if _con_bf is not None:
            total += 1
            if _con_bf.get(key, 0) > 0:
                agree += 1
        if _con_espn is not None:
            total += 1
            if _con_espn.get(key, 0) > 0:
                agree += 1
        return agree, total

    # ── Round-aware verdict ────────────────────────────────────────────────────
    # For the picked round(s), classify each model: TIPS (tips him that round),
    # TIPS_OTHER (covers that game but he's not tipped — real disagreement), or
    # NA (no round-level data / season-only → shown as "—", never counted).
    # All five sources are now round-capable.
    _ROUND_MODELS = ['Cha Ching', 'Betfair', 'Wheelo', 'AFL Predictor', 'ESPN']

    def _verdict_from(rounds_for: dict[int, float] | None, picked: set[int],
                      thresh: float) -> str:
        if rounds_for is None:
            return 'NA'
        covered = [r for r in picked if r in rounds_for]
        if not covered:
            return 'NA'
        if any(rounds_for[r] >= thresh for r in covered):
            return 'TIPS'
        return 'TIPS_OTHER'

    def _verdict_espn(key: str, picked: set[int]) -> str:
        # ESPN prose names only vote-getters, so it can't emit "played, 0 votes"
        # rows the way AFL Predictor does. Coverage is therefore judged at the
        # round level: if ESPN published a picked round, a player named >= thresh
        # there TIPS, and a player absent from it is disagreement (TIPS_OTHER),
        # not silence. A round ESPN never published stays NA.
        if _con_espn_round is None:
            return 'NA'
        covered = picked & _espn_rounds_covered
        if not covered:
            return 'NA'
        player_rounds = _con_espn_round.get(key, {})
        if any(player_rounds.get(r, 0) >= ESPN_ROUND_THRESH for r in covered):
            return 'TIPS'
        return 'TIPS_OTHER'

    def _round_states(player: str, rounds: set[int]) -> dict[str, str]:
        key = _norm(player)
        return {
            'Cha Ching': _verdict_from(_con_cc_round.get(key), rounds, CC_ROUND_THRESH),
            'Betfair': _verdict_from(
                None if _con_bf_round is None else _con_bf_round.get(key, {}),
                rounds, BF_ROUND_THRESH),
            'Wheelo': _verdict_from(_con_wheelo_round.get(key), rounds, WHEELO_ROUND_THRESH),
            'AFL Predictor': _verdict_from(
                None if _con_afl_round is None else _con_afl_round.get(key, {}),
                rounds, AFL_ROUND_THRESH),
            'ESPN': _verdict_espn(key, rounds),
        }

    def _model_top3(player: str) -> list[int]:
        if _gdf is None:
            return []
        sub = _gdf[_gdf['Player'].str.lower() == player.lower()]
        if sub.empty:
            return []
        # Top 3 by projected poll prob, then drop near-zero rounds (>0.2 only) so
        # bye/DNP rounds never pad the list. May leave 3, 1, or 0 rounds; order
        # stays highest-first. Single source → matrix dots, card chips, and the
        # AGREE overlap count all consume this filtered list consistently.
        top = sub.nlargest(3, 'Poll_Prob')
        top = top[top['Poll_Prob'] > 0.2]
        return (top['Round_num'].astype(int) - 1).tolist()

    def _parse_rounds(raw: str) -> set[int]:
        rounds = set()
        for t in str(raw).split(','):
            t = t.strip()
            if t.lstrip('-').isdigit():
                rounds.add(int(t))
        return rounds

    _rl = lambda r: 'OR' if r == 0 else f'R{r}'

    # ── STEP 2 — Round Matrix (hero, flush) ────────────────────────────────────
    st.markdown(
        '<div class="pav-secthead"><span class="t">Round Matrix</span>'
        '<span class="pav-key"><b style="color:#f0b429">★</b> you + model'
        ' &nbsp; <b style="color:#34d399">★</b> your pick'
        ' &nbsp; <b style="color:var(--muted)">·</b> model only</span></div>',
        unsafe_allow_html=True,
    )

    if _pav_user is None:
        st.markdown('<div class="pav-empty">Sign in to track your own targets — '
                    'the button is top right.</div>',
                    unsafe_allow_html=True)
    elif polls.empty:
        st.markdown('<div class="pav-empty">No targets yet — add one below.</div>',
                    unsafe_allow_html=True)
    else:
        _rnd_labels_m = ['OR'] + [str(i) for i in range(1, 25)]
        _header = '<th class="pl">Player</th>'
        for _ci, _lbl in enumerate(_rnd_labels_m):
            _w = 'background:rgba(52,211,153,.10);' if _ci == _cur_idx else ''
            _header += f'<th style="{_w}">{_lbl}</th>'

        _rows_html = ''
        for _, row in polls.iterrows():
            player    = str(row['Player'])
            team      = str(row['Team'])
            my_rounds = _parse_rounds(row['My_Rounds'])
            model_set = set(_model_top3(player))
            settled   = bool(row.get('Settled', False))
            _op       = 'opacity:.45;' if settled else ''
            cells = (f'<td class="pl"><span class="nm">{player}</span><br>'
                     f'<span class="tm">{team}</span></td>')
            for rn in range(25):
                # Current-round wash anchors "now"; encoding bg layers on top.
                _w = 'background:rgba(52,211,153,.08);' if rn == _cur_idx else ''
                # TODO(suppression): no round-suppression logic exists in this
                # codebase yet (no "Brownlow.Votes>0 in a prior round" rule). When
                # it lands, grey/blank suppressed (player, round) cells here.
                in_m, in_mod = rn in my_rounds, rn in model_set
                if in_m and in_mod:
                    cells += f'<td style="{_w}background:rgba(240,180,41,.16);color:#f0b429">★</td>'
                elif in_m:
                    cells += f'<td style="{_w}color:#34d399">★</td>'
                elif in_mod:
                    cells += f'<td style="{_w}color:var(--muted)">·</td>'
                else:
                    cells += f'<td style="{_w}"></td>'
            _rows_html += f'<tr style="{_op}">{cells}</tr>'

        st.markdown(
            f'<div style="overflow-x:auto">'
            f'<table class="pav-matrix">'
            f'<thead><tr>{_header}</tr></thead>'
            f'<tbody>{_rows_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

    # ── STEP 3 — Active Watchlist monitoring cards ─────────────────────────────
    st.markdown('<div class="pav-secthead"><span class="t">Active Watchlist</span></div>',
                unsafe_allow_html=True)

    if _pav_user is None:
        st.markdown('<div class="pav-empty">Your picks appear here once you sign in.</div>',
                    unsafe_allow_html=True)
    elif polls.empty:
        st.markdown('<div class="pav-empty">No targets yet.</div>', unsafe_allow_html=True)

    for idx, row in polls.iterrows():
        player    = str(row['Player'])
        team      = str(row['Team'])
        my_rounds = _parse_rounds(row['My_Rounds'])
        top3      = _model_top3(player)
        settled   = bool(row.get('Settled', False))

        # Gold headline number — Cha Ching's season probability the player polls
        # AT LEAST ONCE: 1 − Π(1 − Poll_Prob_r) over every round he has a row.
        # COMPOUND, not a sum (two 0.2 rounds → 1 − 0.8·0.8 = 36%, not 40%).
        _cc_probs = [_p for _p in _con_cc_round.get(_norm(player), {}).values()
                     if _p == _p]   # drop NaN
        _no_poll = 1.0
        for _p in _cc_probs:
            _no_poll *= (1.0 - min(max(_p, 0.0), 1.0))
        _poll_pct_str = f'{(1.0 - _no_poll) * 100:.0f}%' if _cc_probs else '—'

        # Round-aware verdict (primary headline) — "for this player, in the
        # round(s) you picked, which round-capable models tip him".
        _rstates  = _round_states(player, my_rounds)
        _r_answer = [m for m in _ROUND_MODELS if _rstates[m] != 'NA']
        _r_tips   = [m for m in _r_answer if _rstates[m] == 'TIPS']
        _r_na     = sum(1 for m in _ROUND_MODELS if _rstates[m] == 'NA')
        if not my_rounds:
            _round_head, _round_color = 'No round picked', '#7e8c99'
        elif _r_answer:
            _round_head = f'{len(_r_tips)} of {len(_r_answer)} round-models tip'
            _round_color = '#34d399' if len(_r_tips) == len(_r_answer) else '#f0b429'
        else:
            _round_head, _round_color = 'No round-level model data', '#7e8c99'

        # Per-model strip — TIPS ✓ green, TIPS_OTHER ✗ gold (disagree, never red),
        # NA — muted (silence, must not look like disagreement).
        _glyph = {'TIPS': ('✓', '#34d399'),
                  'TIPS_OTHER': ('✗', '#f0b429'),
                  'NA': ('—', '#5d6b78')}
        _short = {'Cha Ching': 'CC', 'Betfair': 'BF', 'AFL Predictor': 'AFL',
                  'Wheelo': 'WH', 'ESPN': 'ESPN'}
        _strip = '&nbsp;&nbsp;'.join(
            f'<span style="color:{_glyph[_rstates[m]][1]}">'
            f'{_short[m]}&nbsp;{_glyph[_rstates[m]][0]}</span>'
            for m in _ROUND_MODELS
        )

        # Season-level "on the radar" — kept as a separate, quieter indicator.
        _cs_agree, _cs_total = _consensus_score(player)

        my_chips = ''.join(f'<span class="pav-pill-star">★ {_rl(r)}</span>'
                           for r in sorted(my_rounds))
        model_chips = ''.join(f'<span class="pav-pill-dash">{_rl(r)}</span>' for r in top3)
        chips = (my_chips + model_chips) or '<span style="color:var(--muted);font-size:12px">—</span>'

        _op = 'opacity:.55;' if settled else ''
        sbadge = '<span class="sbadge">SETTLED</span>' if settled else ''
        _na_suffix = (f'<span style="color:#7e8c99"> · {_r_na} n/a</span>'
                      if (my_rounds and _r_answer) else '')
        _season_line = (
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;'
            f'color:#7e8c99;margin-top:4px">On the radar (season): '
            f'{_cs_agree}/{_cs_total}</div>' if _cs_total else '')
        con_html = (
            f'<div class="con" style="color:{_round_color}">{_round_head}{_na_suffix}</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
            f'margin-top:4px">{_strip}</div>'
            f'{_season_line}')

        st.markdown(
            f'<div class="pav-card" style="{_op}">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
            f'flex-wrap:wrap;gap:18px">'

            f'<div style="min-width:210px">'
            f'<div class="nm">{player}{sbadge}</div>'
            f'<div class="tm">{team}</div>'
            f'{con_html}'
            f'</div>'

            f'<div style="flex:1;min-width:220px">'
            f'<div class="lbl">My rounds / model top 3</div>'
            f'<div>{chips}</div>'
            f'</div>'

            f'<div style="text-align:center;min-width:70px">'
            f'<div class="agree">{_poll_pct_str}</div>'
            f'<div class="lbl" style="margin-top:5px">Season poll %</div>'
            f'</div>'

            f'</div></div>',
            unsafe_allow_html=True,
        )

        _bcols = st.columns([1, 1, 6])
        if not settled:
            with _bcols[0]:
                st.markdown('<span class="pav-settle-marker" style="display:none"></span>',
                            unsafe_allow_html=True)
                if st.button("Mark settled", key=f"pav_settle_{idx}"):
                    _ok, _msg = user_auth.mark_poll_pick_settled(row['id'])
                    if _ok:
                        st.rerun()
                    elif _msg:
                        st.error(_msg)
        with _bcols[1]:
            st.markdown('<span class="pav-delete-marker" style="display:none"></span>',
                        unsafe_allow_html=True)
            if st.button("Delete", key=f"pav_delete_{idx}"):
                _ok, _msg = user_auth.delete_poll_pick(row['id'])
                if _ok:
                    st.rerun()
                elif _msg:
                    st.error(_msg)

    # ── STEP 4 — Add-target form ──────────────────────────────────────────────
    # Nothing to add a pick to without an account, and the way to get one is the
    # banner's Sign in — this page no longer carries a form of its own.
    if _pav_user is None:
        return

    with st.expander("+ Add a watchlist target", expanded=False):
        # Selectbox outside the form so selection reruns and refreshes the round
        # lookup; the form below keeps the existing checkbox state + submit callback.
        pav_player = st.selectbox("Player name", options=[""] + _pav_all_players, index=0) or ""
        pav_team = _pav_player_team.get(pav_player, "")

        # Per-round Exp_Votes (the gold poll-prob numbers driving which rounds tick)
        _pav_round_votes: dict[int, float] = {}
        # Reuses the frame loaded once at the top rather than re-parsing the CSV.
        # This ran on every rerun of the add form — every checkbox tick — so it
        # was the most expensive of the three reads despite looking the smallest.
        if pav_player.strip() and _pav_game is not None:
            try:
                _lk_match = _pav_game[
                    _pav_game['Player'].str.lower() == pav_player.strip().lower()
                ]
                for _, _lk_r in _lk_match.iterrows():
                    _pav_round_votes[int(_lk_r['Round_num']) - 1] = float(_lk_r['Exp_Votes'])
            except Exception:
                pass

        _form_top3 = set(_model_top3(pav_player)) if pav_player.strip() else set()

        _wl_id = betting_hub._form_instance_id('_pav_row_id')
        with st.form("pav_add_form", clear_on_submit=True):
            st.markdown(
                '<div class="lbl" style="margin:8px 0 6px">Rounds to watch'
                ' &nbsp;·&nbsp; OR = Opening Round'
                ' &nbsp;·&nbsp; <span style="color:#f0b429">gold</span> = high poll prob'
                ' &nbsp;·&nbsp; ◆ = model top 3</div>',
                unsafe_allow_html=True,
            )
            _rnd_labels = ['OR'] + [f'R{i}' for i in range(1, 25)]
            _rnd_checks: dict[int, bool] = {}
            for _ri in range(0, 25, 5):
                _rcols = st.columns(5)
                for _ci in range(5):
                    _rn = _ri + _ci
                    with _rcols[_ci]:
                        ev = _pav_round_votes.get(_rn)
                        base_lbl = _rnd_labels[_rn]
                        if _rn in _form_top3:
                            base_lbl = f'◆ {base_lbl}'
                        lbl = f"**{base_lbl}**" if (ev is not None and ev > 0.35) else base_lbl
                        _rnd_checks[_rn] = st.checkbox(lbl, key=f"pav_rnd_{_rn}")
                        if ev is not None:
                            ev_cls = 'pav-ev-gold' if ev > 0.35 else 'pav-ev-muted'
                            st.markdown(
                                f'<div class="{ev_cls}" style="font-size:12px;margin-top:-10px;'
                                f'padding-left:26px;line-height:1;'
                                f'font-family:\'IBM Plex Mono\',monospace">{ev:.2f}</div>',
                                unsafe_allow_html=True,
                            )

            pav_notes = st.text_input("Notes (optional)")

            if st.form_submit_button("Add to Watchlist", type="primary", use_container_width=True):
                if not pav_player.strip():
                    # Amber for the same reason as the duplicate below: nothing
                    # failed, the form just isn't filled in yet.
                    st.warning("Player name is required.")
                else:
                    _sel = sorted(r for r, chk in _rnd_checks.items() if chk)
                    # save_poll_pick reports the duplicate rather than raising it —
                    # user_poll_picks_active_player is now (user_id, player), so it
                    # can only ever mean this user's own open pick, never another's.
                    # No Odds/Stake keys: this is a watchlist, not a bet log.
                    # save_poll_pick filters this dict against POLL_PICK_COLS
                    # rather than looking keys up, so omitting them drops the
                    # columns from the upsert instead of writing nulls, and both
                    # are nullable in supabase/04. The user_poll_picks.odds and
                    # .stake columns are retained but no longer written or read
                    # anywhere.
                    _ok, _msg = user_auth.save_poll_pick({
                        'id':        _wl_id,
                        'Player':    pav_player.strip(),
                        'Team':      pav_team.strip(),
                        'My_Rounds': ','.join(str(r) for r in _sel),
                        'Notes':     pav_notes.strip(),
                        'Settled':   False,
                    }, season)
                    if _ok:
                        betting_hub._clear_form_instance('_pav_row_id')
                        st.success(f"Added {pav_player.strip()} to watchlist.")
                        st.rerun()
                    elif _msg:
                        # Amber, not red: red is reserved for losses and negative
                        # P&L. The expected failure here is the duplicate guard —
                        # the player is already on the list and the user just edits
                        # it — which is a nudge, not an error.
                        st.warning(_msg)


if _page == 'Polls a Vote':
    render_polls_a_vote(_PAV_SEASON)


# ── Global footer ────────────────────────────────────────────
st.markdown(
    '<div style="border-top:1px solid var(--line);margin-top:40px;padding:14px 0;'
    'color:var(--muted);font-size:10px;letter-spacing:1.2px;text-align:center;'
    'text-transform:uppercase;font-weight:600;">'
    # No accuracy figure here, deliberately. Every MAE on record (v1-v4) was
    # measured with a momentum leak in place, so none is comparable to the
    # others or to the current model, and this footer is public. Do not
    # reinstate MAE, a top-10 hit rate, or any other accuracy number until one
    # has been re-measured against the current model. See CLAUDE.md, "## Model
    # architecture".
    f'Model v4.0 &nbsp;&nbsp;·&nbsp;&nbsp; Data: {_TRAIN_MIN}–{_TRAIN_MAX} &nbsp;&nbsp;·&nbsp;&nbsp; 93 features'
    '</div>',
    unsafe_allow_html=True,
)

# ── Responsible-gambling footer (public/Brownlow pages only) ──
# Reached by every page that renders a body. Betting Hub pages are excluded
# by _BH_PAGES; the password-gate screen st.stop()s earlier and never gets here.
if _page not in _BH_PAGES:
    _render_rg_footer()
