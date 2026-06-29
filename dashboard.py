"""
Brownlow Medal Prediction Dashboard v4.1
Run: python -m streamlit run dashboard.py
"""

import streamlit as st
import streamlit.components.v1 as _components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re
import subprocess
import sys
import betting_hub
from theme import inject_global_theme
from brownlow_medallists import get_medallists

st.set_page_config(page_title="Cha Ching", layout="wide", initial_sidebar_state="collapsed")

def inject_global_css():
    st.markdown("""
<style>
iframe[title="streamlit_app"] { margin-top: -60px !important; }
</style>
""", unsafe_allow_html=True)
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@400;500;600;700&family=Archivo:wdth,wght@62.5..125,400..900&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">', unsafe_allow_html=True)
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
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaNegative"] {
    color: #e05252 !important;
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
/* ── Subnav tab strip ── */
/* :has() — Chrome/Edge 105+, Safari 15.4+, Firefox 121+ */

/* Row: no equal-width columns, scroll horizontally if needed */
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
  gap: 3px !important;
  align-items: center !important;
  padding: 0 0 4px 0 !important;
  scrollbar-width: none !important;
}
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
  display: none !important;
}

/* Columns: shrink to content width instead of equal division */
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
  flex: 0 0 auto !important;
  width: auto !important;
  min-width: 0 !important;
  padding: 0 !important;
}
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stColumn"] > div,
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlock"],
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stButton"] {
  width: auto !important;
  min-width: 0 !important;
}

/* Buttons: no wrapping, auto width */
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] button {
  white-space: nowrap !important;
  width: auto !important;
  font-size: 10px !important;
  padding: 5px 10px !important;
  min-height: unset !important;
  height: auto !important;
  border-radius: 6px !important;
  letter-spacing: 0.2px !important;
}

/* Active: teal text + subtle teal outline */
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"] {
  background: transparent !important;
  color: #3ecfa0 !important;
  border: 0.5px solid rgba(62,207,160,0.35) !important;
  border-radius: 6px !important;
}

/* Inactive: muted white, no visible border */
.stMarkdown:has(.snav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"] {
  background: transparent !important;
  color: rgba(255,255,255,0.35) !important;
  border: 0.5px solid transparent !important;
  border-radius: 6px !important;
}
</style>
""", unsafe_allow_html=True)

def apply_chart_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Archivo, sans-serif", color="#7e8c99", size=12),
        title_font=dict(family="Archivo, sans-serif", color="#e9eef3", size=14),
        xaxis=dict(
            gridcolor="rgba(140,165,185,.14)",
            linecolor="rgba(140,165,185,.14)",
            tickcolor="rgba(140,165,185,.14)",
            tickfont=dict(color="#7e8c99", size=11),
        ),
        yaxis=dict(
            gridcolor="rgba(140,165,185,.14)",
            linecolor="rgba(140,165,185,.14)",
            tickcolor="rgba(140,165,185,.14)",
            tickfont=dict(color="#7e8c99", size=11),
        ),
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

def render_banner():
    _hub = st.session_state.get("active_hub", "brownlow")
    _sub = ("Through Round {}".format(max_season_rounds - 1) if is_2026
            else "All Seasons" if is_career else f"{selected_season} Season")
    _mode_label = "Brownlow Predictor" if _hub == "brownlow" else "Betting Hub"
    st.markdown(f"""
<div class="cc-banner">
    <svg class="cc-banner-oval" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">
        <ellipse class="cc-oval-boundary" cx="500" cy="300" rx="460" ry="270"/>
        <g class="cc-oval-inner">
            <path d="M500 255 L545 300 L500 345 L455 300 Z"/>
            <circle cx="500" cy="300" r="45"/>
            <circle cx="500" cy="300" r="8"/>
            <path d="M115 95 A235 235 0 0 0 115 505"/>
            <path d="M885 95 A235 235 0 0 1 885 505"/>
            <rect x="40" y="270" width="35" height="60"/>
            <rect x="925" y="270" width="35" height="60"/>
        </g>
    </svg>
    <div class="cc-banner-title"><span class="cha">CHA </span><span class="ching">CHING</span></div>
    <div class="cc-banner-eyebrow{' bh' if _hub != 'brownlow' else ''}">{_mode_label.upper()} &middot; {_sub.upper()}</div>
</div>
""", unsafe_allow_html=True)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Structural ── */
    body { overflow-x: hidden !important; }
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
       stVerticalBlock. Same fix as the landing page (.landing-top-anchor
       rules), scoped to pages that render .cc-banner — landing never does. */
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > style:only-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > link:only-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > link:first-child + style:last-child),
    .stApp:has(.cc-banner) div[data-testid="stElementContainer"]:has(> iframe[srcdoc*="_ccAnimated"]) {
        display: none !important;
    }
    .cc-banner {
        position: relative;
        left: 50%;
        transform: translateX(-50%);
        width: 100vw;
        background: var(--bg);
        border-bottom: 1px solid var(--line);
        padding: 26px 0 18px;
        text-align: center;
        overflow: hidden;
    }
    /* preserveAspectRatio="none": the 1000x600 viewBox stretches to fill
       620px x banner height, so the full boundary ellipse fits the banner
       and cradles the wordmark instead of being clipped to a middle slice. */
    .cc-banner-oval {
        position: absolute;
        top: 6px;
        left: 50%;
        width: 620px;
        max-width: 90%;
        height: calc(100% - 12px);
        transform: translateX(-50%);
        pointer-events: none;
    }
    .cc-banner-oval ellipse,
    .cc-banner-oval path,
    .cc-banner-oval circle,
    .cc-banner-oval rect {
        fill: none;
        stroke-width: 1;
        vector-effect: non-scaling-stroke;
    }
    .cc-banner-oval .cc-oval-boundary { stroke: rgba(126,156,178,.25); }
    .cc-banner-oval .cc-oval-inner *  { stroke: rgba(126,156,178,.14); }
    .cc-banner-title {
        position: relative;
        font-family: 'Archivo', sans-serif;
        font-weight: 900;
        font-variation-settings: 'wdth' 122;
        font-size: 44px;
        line-height: 1;
        white-space: nowrap;
        margin: 0 0 8px 0;
    }
    .cc-banner-title .cha {
        background: linear-gradient(180deg, #ffffff 0%, #9fb3c4 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
    }
    .cc-banner-title .ching {
        background: linear-gradient(120deg, var(--emerald), var(--gold));
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
    }
    .cc-banner-eyebrow {
        position: relative;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 10px;
        letter-spacing: .3em;
        text-transform: uppercase;
        color: var(--emerald);
        margin: 0;
    }
    .cc-banner-eyebrow.bh {
        color: var(--gold);
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
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
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

# ── Animated number counter (JS via iframe → parent DOM) ──────
_components.html("""
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
""", height=0)

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

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
def load_game(season):
    path = f"{PRED_DIR}/game_level_{season}.csv"
    if not os.path.exists(path):
        return None
    return _disambiguate_players(_fix_team_names(pd.read_csv(path)))

@st.cache_data(ttl=300)
def load_importance():
    path = f"{PRED_DIR}/feature_importance.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_backtest():
    path = f"{PRED_DIR}/backtest_results.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data(ttl=300)
def load_season_projection():
    path = f"{PRED_DIR}/season_projection_2026.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

@st.cache_data(ttl=300)
def load_all_historical():
    """Per-game data across every season, with a clean Team column and same-name
    players split into distinct people. (Older season files only carry
    'Playing.for'; 2026 carries 'Team'.)"""
    frames = []
    for season in sorted(AVAILABLE_SEASONS):
        path = f"{PRED_DIR}/game_level_{season}.csv"
        if os.path.exists(path):
            df = _fix_team_names(pd.read_csv(path))
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
    return _disambiguate_players(g)

# Sentinel season value meaning "all seasons combined" (career view).
CAREER = "Career"

@st.cache_data(ttl=300)
def load_game_career():
    """Per-game data across every season (career view)."""
    return load_all_historical()

@st.cache_data(ttl=300)
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

def load_best_odds():
    path = "data_2026/best_odds.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

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

@st.cache_data(ttl=55, show_spinner=False)
def fetch_live_brownlow_data():
    """Fetch Brownlow vote data from AFL public API. Returns a result dict."""
    import requests as _req
    BASE = "https://aflapi.afl.com.au/afl/v2"
    HDRS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.afl.com.au/brownlow-medal/live-tracker",
    }
    _empty = {"df": pd.DataFrame(), "feed": [], "last_round": 0,
              "season_name": "", "is_live": False, "error": None}
    try:
        # Resolve current AFLM season id
        cr = _req.get(f"{BASE}/competitions/1/compseasons?pageSize=5", headers=HDRS, timeout=10)
        cr.raise_for_status()
        seasons = [s for s in cr.json().get("compSeasons", []) if "Premiership" in s.get("name", "")]
        if not seasons:
            return {**_empty, "error": "Could not resolve current AFL season."}
        season = seasons[0]
        season_id, season_name = season["id"], season["name"]

        # Team id → name lookup
        tr = _req.get(f"{BASE}/teams?compSeasonId={season_id}&pageSize=100", headers=HDRS, timeout=10)
        team_map = {}
        if tr.status_code == 200:
            for t in tr.json().get("teams", []):
                team_map[t["id"]] = t.get("name", str(t["id"]))

        # Paginate player data (sorted by totalVotes desc from API)
        all_players = []
        for page in range(5):
            pr = _req.get(
                f"{BASE}/compseasons/{season_id}/award/brownlow?page={page}&pageSize=100",
                headers=HDRS, timeout=10,
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

def _load_csv_fallback(csv_path, rank_col='Rank'):
    """Load a predictions CSV; ensure rank_col exists."""
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if rank_col not in df.columns:
        df[rank_col] = df.index + 1
    return df

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

@st.cache_data(ttl=120, show_spinner=False)
def fetch_betfair_brownlow():
    """Load Betfair predictions from CSV (updated by scraper_betfair.py via Run Update)."""
    def _csv_to_internal(fb):
        return fb.rename(columns={'Total_Votes': 'BF_Votes', 'Rank': 'BF_Rank'}, errors='ignore')
    fb = _load_csv_fallback(_BF_CSV, 'Rank')
    if fb.empty:
        return pd.DataFrame(), "No data — click Run Update to refresh"
    return _csv_to_internal(fb), None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_espn_brownlow():
    """Load ESPN predictions from CSV (updated by scraper_espn.py via Run Update)."""
    def _csv_to_internal(fb):
        return fb.rename(columns={'Total_Votes': 'ESPN_Votes', 'Rank': 'ESPN_Rank'}, errors='ignore')
    fb = _load_csv_fallback(_ESPN_CSV, 'Rank')
    if fb.empty:
        return pd.DataFrame(), "No data — click Run Update to refresh"
    return _csv_to_internal(fb), None


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
_season_page = st.session_state.get('page', 'Landing')
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

# max_season_rounds: highest round number in data (used for slider upper bounds)
# rounds_played: count of distinct rounds (correct display even if rounds start at 0 or skip)
max_season_rounds = int(game_df['Round_num'].max()) if game_df is not None and len(game_df) > 0 else 25
rounds_played = int(game_df['Round_num'].nunique()) if game_df is not None and len(game_df) > 0 else 0

# ── State init + banner ───────────────────────────────────────
if 'active_hub' not in st.session_state:
    st.session_state.active_hub = 'brownlow'
if 'page' not in st.session_state:
    st.session_state.page = 'Landing'

if st.session_state.page != 'Landing':
    render_banner()

_NAV_BROWNLOW = {
    "Overview": ["Leaderboard", "Live Tracker"],
    "Players":  ["Player Profile", "Player Comparison"],
    "Analysis": ["Stat Filter", "Game Analysis", "Model Comparison"],
}
_NAV_BETTING = {
    "BH Overview":  ["Performance", "Predictions", "Bet Tracker"],
    "BH Strategy":  ["Cha Ching Tips", "Trends & Analysis", "Polls a Vote"],
}
_BH_PAGES = {'Performance', 'Predictions', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis', 'Polls a Vote'}

def _nav_select(cat_key):
    val = st.session_state.get(cat_key)
    if val is not None:
        st.session_state.page = val

_hub  = st.session_state.get("active_hub", "brownlow")
_page = st.session_state.page

# ── Page list + icons for current hub ─────────────────────────
_PAGE_ICONS = {
    "Predictions":      "ti-home",
    "Leaderboard":      "ti-award",
    "Player Profile":   "ti-user",
    "Player Comparison":"ti-users",
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

if _hub == "brownlow":
    _snav_pages = [
        "Leaderboard", "Player Profile", "Player Comparison",
        "Stat Filter", "Game Analysis",
        "Model Comparison", "Live Tracker",
    ]
else:
    _snav_pages = ["Performance", "Predictions", "Bet Tracker", "Cha Ching Tips", "Trends & Analysis", "Polls a Vote"]

# ── Nav CSS (injected once before containers) ─────────────────
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css');
/* ── Collapse flex gaps above/between nav rows ─────────────────
   The .cc-banner CSS hides the zero-height injection containers that
   used to add 32px of stacked flex gap above this row, so the hub row
   now sits flush against the banner with no negative pull. */
[data-testid="stLayoutWrapper"]:has(.nav-hub-anchor) {
    margin-top: 0 !important;
}
[data-testid="stLayoutWrapper"]:has(.nav-page-anchor) {
    margin-top: -16px !important;
}

/* ── Hub row container ───────────────────────────────────────── */
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) {
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
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) > :first-child {
    display: none !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stHorizontalBlock"] {
    display: grid !important; grid-template-columns: 1fr 1fr !important;
    gap: 0 !important; padding: 0 !important; align-items: stretch !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stColumn"] {
    width: 100% !important; min-width: 0 !important; padding: 0 !important;
    display: flex !important; flex-direction: column !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stColumn"] > div,
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stElementContainer"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stButton"] {
    width: 100% !important; flex: 1 !important;
}
/* Hide icon marker divs (used for ::before icon injection) */
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"] div.ti { display: none !important; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) button {
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
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) button p,
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) button span {
    color: inherit !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stBaseButton-primary"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="baseButton-primary"] {
    color: var(--emerald) !important; border-bottom-color: var(--emerald) !important;
    font-weight: 600 !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor.bh) [data-testid="stBaseButton-primary"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor.bh) [data-testid="baseButton-primary"] {
    color: var(--gold) !important; border-bottom-color: var(--gold) !important;
}
@media (hover: hover) {
    [data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stVerticalBlock"]:has(> :first-child .nav-hub-anchor) [data-testid="baseButton-secondary"]:hover {
        color: var(--text) !important;
    }
}

/* ── Page strip container ────────────────────────────────────── */
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) {
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
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    gap: 0 !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) > :first-child {
    display: none !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stHorizontalBlock"] {
    display: flex !important; flex-wrap: nowrap !important;
    width: 100% !important; gap: 0 !important;
    padding: 0 !important; align-items: stretch !important;
    scrollbar-width: none !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
    display: none !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"] {
    flex: 1 1 0 !important; min-width: 0 !important; padding: 0 !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"] > div,
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stElementContainer"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stButton"] {
    width: 100% !important; padding: 0 !important; margin: 0 !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) button {
    background: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    color: var(--muted) !important; font-size: 12px !important;
    font-weight: 500 !important; padding: 4px 6px !important;
    border-radius: 0 !important; white-space: nowrap !important;
    box-shadow: none !important; width: 100% !important; min-width: 0 !important;
    line-height: 1.4 !important; text-align: center !important;
    justify-content: center !important; display: flex !important;
    align-items: center !important;
    transition: color 160ms ease-out, border-color 160ms ease-out !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) button p,
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) button span {
    color: inherit !important;
}
/* Page strip icons via ::before — keyed by hidden .ti marker div */
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti) button::before {
    font-family: tabler-icons, sans-serif !important;
    margin-right: 4px; display: inline-block !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-home) button::before                   { content: "\eac1"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-medal) button::before               { content: "\ed79"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-user) button::before                   { content: "\eb4d"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-users) button::before                  { content: "\ebf2"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-adjustments-horizontal) button::before { content: "\ec38"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-award) button::before                  { content: "\ea2c"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-trophy) button::before              { content: "\edd9"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-user-pentagon) button::before       { content: "\\fc4f"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-chart-bar) button::before               { content: "\ea59"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-chart-dots) button::before              { content: "\ee2f"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-brain) button::before                  { content: "\\f59f"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-live-photo) button::before              { content: "\eadf"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-currency-dollar) button::before        { content: "\eb84"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-layout-dashboard) button::before       { content: "\\f02c"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-list-check) button::before             { content: "\eb6a"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-bulb) button::before                   { content: "\ea51"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-trending-up) button::before            { content: "\eb43"; }
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stColumn"]:has(.ti-tags) button::before                  { font-family: tabler-icons, sans-serif !important; content: "\eff7"; }

[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stBaseButton-primary"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="baseButton-primary"] {
    color: var(--text) !important; border-bottom-color: var(--emerald) !important;
    font-weight: 600 !important;
}
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor.bh) [data-testid="stBaseButton-primary"],
[data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor.bh) [data-testid="baseButton-primary"] {
    border-bottom-color: var(--gold) !important;
}
@media (hover: hover) {
    [data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stVerticalBlock"]:has(> :first-child .nav-page-anchor) [data-testid="baseButton-secondary"]:hover {
        color: var(--text) !important;
    }
}

/* ════════════════════════════════════════════════════════════
   LANDING PAGE
   ════════════════════════════════════════════════════════════ */

/* App background + block-container padding, scoped to landing */
.stApp:has(.landing-top-anchor),
.stApp:has(.landing-top-anchor) [data-testid="stAppViewContainer"] {
    background: #0a1017 !important;
}
.stApp:has(.landing-top-anchor) .block-container {
    padding-top: 0 !important;
}

/* Collapse leading gap above hero / ticker: the global CSS/JS-injection
   element containers (style/link tags, the animated-counter iframe, and the
   landing-top-anchor marker itself) are zero-height but each still adds a
   16px flex `gap` in the outer stVerticalBlock. Removing them from layout
   eliminates that stacked gap so the ticker sits flush at the top. */
.stApp:has(.landing-top-anchor) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > style:only-child),
.stApp:has(.landing-top-anchor) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > link:only-child),
.stApp:has(.landing-top-anchor) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > div.landing-top-anchor:only-child),
.stApp:has(.landing-top-anchor) div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > div.cc-ticker-marker:only-child),
.stApp:has(.landing-top-anchor) div[data-testid="stElementContainer"]:has(> iframe[srcdoc*="_ccAnimated"]) {
    display: none !important;
}

/* Ticker bar: kill the top gap and go full-bleed (landing only) */
.stApp:has(.landing-top-anchor) header[data-testid="stHeader"] {
    display: none !important;
}
.stApp:has(.landing-top-anchor) div[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
}
.cc-ticker-marker { display: none; }
div[data-testid="stVerticalBlock"]:has(.cc-ticker-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-ticker-marker)) {
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
div[data-testid="stVerticalBlock"]:has(.cc-ticker-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-ticker-marker)) [data-testid="stElementContainer"] {
    margin: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(.cc-ticker-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-ticker-marker)) iframe {
    display: block !important;
    width: 100% !important;
}

/* Destination panels (marker-div + :has() pattern) */
@keyframes tagDotPulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: .35; }
}
.cc-card-marker { display: none; }
div[data-testid="stVerticalBlock"]:has(.cc-card-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-card-marker)) {
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
    div[data-testid="stVerticalBlock"]:has(.cc-brownlow):not(:has(div[data-testid="stVerticalBlock"] .cc-brownlow)):hover {
        transform: translateY(-4px);
        border-color: rgba(52,211,153,.35) !important;
        box-shadow: 0 12px 32px rgba(52,211,153,.10);
    }
    div[data-testid="stVerticalBlock"]:has(.cc-betting):not(:has(div[data-testid="stVerticalBlock"] .cc-betting)):hover {
        transform: translateY(-4px);
        border-color: rgba(240,180,41,.35) !important;
        box-shadow: 0 12px 32px rgba(240,180,41,.10);
    }
}
div[data-testid="stVerticalBlock"]:has(.cc-card-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-card-marker))::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    z-index: 1;
}
div[data-testid="stVerticalBlock"]:has(.cc-brownlow):not(:has(div[data-testid="stVerticalBlock"] .cc-brownlow))::before { background: linear-gradient(90deg, transparent, #34d399, transparent); }
div[data-testid="stVerticalBlock"]:has(.cc-betting):not(:has(div[data-testid="stVerticalBlock"] .cc-betting))::before { background: linear-gradient(90deg, transparent, #f0b429, transparent); }
div[data-testid="stVerticalBlock"]:has(.cc-card-marker):not(:has(div[data-testid="stVerticalBlock"] .cc-card-marker)) [data-testid="stElementContainer"]:first-child {
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

/* ── Leaderboard page ── */
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
.lb-controls-marker { display: none; }
div[data-testid="stHorizontalBlock"]:has(.lb-controls-marker) label {
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

</style>
""", unsafe_allow_html=True)

# ── Hub toggle row + page strip row ─────────────────────────────
def _render_hub_tabs():
    with st.container():
        _anchor_cls = "nav-hub-anchor bh" if _hub == "betting" else "nav-hub-anchor"
        st.markdown(f'<div class="{_anchor_cls}"></div>', unsafe_allow_html=True)
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
    with st.container():
        _anchor_cls = "nav-page-anchor bh" if _hub == "betting" else "nav-page-anchor"
        st.markdown(f'<div class="{_anchor_cls}"></div>', unsafe_allow_html=True)
        _pcols = st.columns(len(_snav_pages), gap="small")
        for _pc, _sp in zip(_pcols, _snav_pages):
            with _pc:
                _icon_cls = _PAGE_ICONS.get(_sp, '')
                if _icon_cls:
                    st.markdown(f'<div class="ti {_icon_cls}"></div>', unsafe_allow_html=True)
                if st.button(_sp, key=f"nav_{_sp}",
                             type="primary" if _page == _sp else "secondary"):
                    st.session_state.page = _sp
                    st.rerun()

if _page != 'Landing':
    _render_hub_tabs()
    _render_page_nav()

# ── Controls row (season + odds timestamp) ──────────────────
# Only show controls for Brownlow pages, not Betting Hub or Landing
_show_controls = _page not in _BH_PAGES and _page != 'Landing'

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
# LANDING PAGE
# ════════════════════════════════════════════════════════════
if _page == 'Landing':
    st.markdown('<div class="landing-top-anchor"></div>', unsafe_allow_html=True)

    # ── Live context: leader, projections, betting P&L ──
    _land_df = load_season(selected_season)
    _land_leader = "—"
    _land_votes = 0.0
    if _land_df is not None and not _land_df.empty and 'Exp_Total_Votes' in _land_df.columns:
        _land_top = (
            _land_df.groupby("Player_Name")["Exp_Total_Votes"]
            .sum()
            .sort_values(ascending=False)
        )
        if len(_land_top):
            _land_leader = _land_top.index[0]
            _land_votes = float(_land_top.iloc[0])

    try:
        _land_bets = betting_hub._load_bets()
        _land_pl = float(_land_bets["profit_loss"].sum()) if not _land_bets.empty else None
        _land_n = len(_land_bets)
        _land_pending = int((_land_bets["result"] == "Pending").sum()) if not _land_bets.empty else 0
    except Exception:
        _land_bets = pd.DataFrame()
        _land_pl = None
        _land_n = 0
        _land_pending = 0

    _land_pl_val = _land_pl or 0.0
    _pl_str = f"+{_land_pl_val:.2f}u" if _land_pl_val >= 0 else f"-{abs(_land_pl_val):.2f}u"
    _pl_color = "#34d399" if _land_pl_val >= 0 else "#e0625a"
    _land_round = max_season_rounds - 1

    # Latest round's predicted 3-2-1 vote read
    _TEAM_ABBR = {
        "Adelaide": "ADE", "Brisbane Lions": "BRI", "Carlton": "CAR", "Collingwood": "COL",
        "Essendon": "ESS", "Fremantle": "FRE", "Geelong": "GEE", "Gold Coast": "GCS",
        "Greater Western Sydney": "GWS", "GWS": "GWS", "GWS Giants": "GWS", "Hawthorn": "HAW",
        "Melbourne": "MEL", "North Melbourne": "NTH", "Port Adelaide": "PTA", "Richmond": "RIC",
        "St Kilda": "STK", "Sydney": "SYD", "West Coast": "WCE", "Western Bulldogs": "WB",
    }

    def _initial_surname(_name):
        _parts = str(_name).split()
        return f"{_parts[0][0]}. {' '.join(_parts[1:])}" if len(_parts) >= 2 else str(_name)

    _chip_fallback = [
        {"name": "Lachie Neale", "team": "Brisbane Lions", "exp_votes": 2.4},
        {"name": "Kysaiah Pickett", "team": "Melbourne", "exp_votes": 1.8},
        {"name": "Logan Morris", "team": "Brisbane Lions", "exp_votes": 1.3},
    ]
    _chip_players = []
    if game_df is not None and len(game_df):
        _latest_round = game_df['Round_num'].max()
        _latest_df = (
            game_df[game_df['Round_num'] == _latest_round]
            .sort_values('Exp_Votes', ascending=False)
            .head(3)
        )
        for _, _r in _latest_df.iterrows():
            _chip_players.append({
                "name": str(_r.get("Player_Name", "—")),
                "team": str(_r.get("Team", "")),
                "exp_votes": float(_r["Exp_Votes"]) if pd.notna(_r.get("Exp_Votes")) else 0.0,
            })
    # TODO: wire to predictions — fall back to placeholder leaders if the latest round has < 3 players
    for _i in range(len(_chip_players), 3):
        _chip_players.append(_chip_fallback[_i])
    _chip1, _chip2, _chip3 = _chip_players[0], _chip_players[1], _chip_players[2]

    def _chip_stats(_c):
        _abbr = _TEAM_ABBR.get(_c['team'], _c['team'][:3].upper())
        return f"&middot; {_abbr} &middot; {_c['exp_votes']:.1f}"

    # ── Ticker bar ──
    _ticker_bet_items = []
    if not _land_bets.empty and "match" in _land_bets.columns:
        _round_bets = _land_bets[
            _land_bets["match"].astype(str).str.contains(f"Round {_land_round}", na=False)
            & _land_bets["result"].isin(["Win", "Loss"])
        ]
        for _, _b in _round_bets.head(4).iterrows():
            _sel = str(_b["selection"]).upper()
            if _b["result"] == "Win":
                _ticker_bet_items.append(f'<span style="color:#34d399">{_sel} &#10003; WIN</span>')
            else:
                _ticker_bet_items.append(f'{_sel} &#10007; LOSS')
    if not _ticker_bet_items:
        # TODO: wire to live bet results once the current round has settled bets
        _ticker_bet_items = ['<span style="color:#34d399">DUURSMA 16+ DISP &#10003; WIN</span>']

    _ticker_items_html = _ticker_bet_items + [
        f'SEASON P&amp;L <span style="color:{_pl_color}">{_pl_str}</span>',
        f'BROWNLOW LEADER <span style="color:#f0b429">{_initial_surname(_land_leader).upper()} {_land_votes:.1f}</span>',
        'MODEL V4.0 &middot; MAE 0.0904',
    ]
    _ticker_sep = ' &nbsp;&nbsp;&middot;&nbsp;&nbsp; '
    _ticker_segment = (_ticker_sep.join(_ticker_items_html)) + _ticker_sep
    _ticker_html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:transparent;height:40px;overflow:hidden;}
.bar{height:40px;background:#0d141d;border-bottom:1px solid rgba(140,165,185,.14);overflow:hidden;display:flex;align-items:center;}
.ticker-track{
  display:inline-block;
  white-space:nowrap;
  font-family:'IBM Plex Mono',monospace;
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.08em;
  color:#7e8c99;
  padding:11px 0;
  animation:ticker 38s linear infinite;
  will-change:transform;
}
@keyframes ticker{from{transform:translateX(0);}to{transform:translateX(-50%);}}
</style></head><body>
<div class="bar"><div class="ticker-track" id="track">__SEG__</div></div>
<script>
var track = document.getElementById('track');
track.innerHTML += track.innerHTML;
</script>
</body></html>"""
    _ticker_html = _ticker_html.replace("__SEG__", _ticker_segment)
    with st.container():
        st.markdown('<div class="cc-ticker-marker">&#8203;</div>', unsafe_allow_html=True)
        _components.html(_ticker_html, height=40, scrolling=False)

    # ── Hero ──
    _hero_html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62.5..125,400..900&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:transparent;height:440px;overflow:hidden;}
.hero{position:relative;width:100%;height:440px;display:flex;align-items:center;justify-content:center;font-family:'Archivo',sans-serif;}
.oval{position:absolute;top:0;left:0;width:100%;height:100%;opacity:.5;}
.oval ellipse,.oval path,.oval circle,.oval rect{
  fill:none;stroke:rgba(126,156,178,.32);stroke-width:1.1;
  stroke-dasharray:2400;stroke-dashoffset:2400;
  animation:draw 2.4s cubic-bezier(0.23,1,0.32,1) forwards;
}
.g1 *{animation-delay:0s;}
.g2 *{animation-delay:.25s;}
.g3 *{animation-delay:.5s;}
.g4 *{animation-delay:.75s;}
@keyframes draw{to{stroke-dashoffset:0;}}
.content{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;
text-align:center;padding:0 24px;max-width:900px;}
.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.34em;
text-transform:uppercase;color:#34d399;margin-bottom:8px;}
.wordmark{font-family:'Archivo',sans-serif;font-weight:900;font-variation-settings:'wdth' 122;
font-size:clamp(56px,9vw,110px);line-height:.94;white-space:nowrap;margin:0;}
.cha{background:linear-gradient(180deg,#ffffff,#9fb3c4);-webkit-background-clip:text;background-clip:text;color:transparent;}
.ching{background:linear-gradient(120deg,#34d399,#f0b429);-webkit-background-clip:text;background-clip:text;color:transparent;}
.subtitle{font-size:15px;color:#7e8c99;margin:14px 0 26px;}
@keyframes rise{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:translateY(0);}}
.rise{opacity:0;animation:rise 650ms cubic-bezier(0.23,1,0.32,1) forwards;}
.r1{animation-delay:.2s;}
.r2{animation-delay:.32s;}
.r3{animation-delay:.44s;}
.chips-label{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:700;letter-spacing:.18em;
text-transform:uppercase;color:#7e8c99;margin-bottom:10px;opacity:0;animation:fade 400ms ease-out .4s forwards;}
.chips{display:flex;gap:10px;flex-wrap:nowrap;justify-content:center;margin-top:0;max-width:100%;}
.chip{display:flex;align-items:center;gap:8px;background:#101a24;border:1px solid rgba(140,165,185,.14);
border-radius:999px;padding:10px 18px 10px 10px;opacity:0;animation:chipIn 500ms ease-out forwards;white-space:nowrap;}
@keyframes chipIn{from{opacity:0;transform:translateY(10px) scale(.97);}to{opacity:1;transform:translateY(0) scale(1);}}
@keyframes chipInDim{from{opacity:0;transform:translateY(10px) scale(.97);}to{opacity:.85;transform:translateY(0) scale(1);}}
.chip-1{animation-delay:1.5s;}
.chip-2{animation-delay:1.0s;animation-name:chipInDim;}
.chip-3{animation-delay:.6s;animation-name:chipInDim;}
.badge{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:6px;
font-family:'Archivo',sans-serif;font-weight:800;font-size:14px;flex-shrink:0;}
.badge-1{background:#34d399;color:#0a1017;}
.badge-2{background:#3a4753;color:#e9eef3;}
.badge-3{background:#1c2530;color:#7e8c99;}
.chip-name{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#e9eef3;}
.chip-stats{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#7e8c99;}
@media (max-width:700px){
  .chips{flex-wrap:wrap;}
  .chip{white-space:normal;}
}
@media (prefers-reduced-motion: reduce){
  .oval ellipse,.oval path,.oval circle,.oval rect{animation:none;stroke-dashoffset:0;}
  .rise,.chip{animation:fade 400ms ease-out forwards;}
}
@keyframes fade{from{opacity:0;}to{opacity:1;}}
</style></head><body>
<div class="hero">
  <svg class="oval" viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid meet">
    <g class="g1"><ellipse cx="500" cy="300" rx="460" ry="270"/></g>
    <g class="g2">
      <path d="M500 255 L545 300 L500 345 L455 300 Z"/>
      <circle cx="500" cy="300" r="45"/>
      <circle cx="500" cy="300" r="8"/>
    </g>
    <g class="g3">
      <path d="M115 95 A235 235 0 0 0 115 505"/>
      <path d="M885 95 A235 235 0 0 1 885 505"/>
    </g>
    <g class="g4">
      <rect x="40" y="270" width="35" height="60"/>
      <rect x="925" y="270" width="35" height="60"/>
    </g>
  </svg>
  <div class="content">
    <div class="eyebrow rise r1">BROWNLOW PREDICTOR &middot; THROUGH ROUND __ROUND__</div>
    <h1 class="wordmark rise r2"><span class="cha">CHA</span> <span class="ching">CHING</span></h1>
    <p class="subtitle rise r3">One model. Two games: the medal count, and the money.</p>
    <div class="chips-label">ROUND __ROUND__ &middot; MOST LIKELY TO POLL</div>
    <div class="chips">
      <div class="chip chip-1"><span class="badge badge-1">1</span><span class="chip-name">__NAME1__</span><span class="chip-stats">__STATS1__</span></div>
      <div class="chip chip-2"><span class="badge badge-2">2</span><span class="chip-name">__NAME2__</span><span class="chip-stats">__STATS2__</span></div>
      <div class="chip chip-3"><span class="badge badge-3">3</span><span class="chip-name">__NAME3__</span><span class="chip-stats">__STATS3__</span></div>
    </div>
  </div>
</div>
</body></html>"""
    _hero_html = (
        _hero_html
        .replace("__ROUND__", str(_land_round))
        .replace("__NAME1__", _initial_surname(_chip1["name"])).replace("__STATS1__", _chip_stats(_chip1))
        .replace("__NAME2__", _initial_surname(_chip2["name"])).replace("__STATS2__", _chip_stats(_chip2))
        .replace("__NAME3__", _initial_surname(_chip3["name"])).replace("__STATS3__", _chip_stats(_chip3))
    )
    _components.html(_hero_html, height=440, scrolling=False)

    # ── Stat strip ──
    _stat_html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62.5..125,400..900&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:transparent;height:110px;overflow:hidden;font-family:'IBM Plex Mono',monospace;}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;height:110px;max-width:1180px;margin:0 auto;background:rgba(140,165,185,.14);}
.cell{background:#0a1017;padding:26px 30px;display:flex;flex-direction:column;justify-content:center;gap:8px;}
.label{font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:#7e8c99;}
.value{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:28px;color:#e9eef3;letter-spacing:.02em;}
.value.leader{color:#34d399;}
.value.pl{color:#f0b429;}
</style></head><body>
<div class="grid">
  <div class="cell"><div class="label">Round</div><div class="value">__ROUND__</div></div>
  <div class="cell"><div class="label">Current Leader</div><div class="value leader">__LEADER__</div></div>
  <div class="cell"><div class="label">Predicted Votes</div><div class="value" id="votes">0.0</div></div>
  <div class="cell"><div class="label">Betting P&amp;L</div><div class="value pl" id="pl">__PL_FALLBACK__</div></div>
</div>
<script>
var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var votesTarget = __VOTES__;
var plTarget = __PL_ABS__;
var plPrefix = "__PL_PREFIX__";
function easeOut(p){ return 1 - Math.pow(1 - p, 4); }
function animate(el, target, formatter, duration, delay){
  if(reduced){ el.textContent = formatter(target); return; }
  setTimeout(function(){
    var start = null;
    function step(ts){
      if(!start) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      el.textContent = formatter(target * easeOut(p));
      if(p < 1) requestAnimationFrame(step);
      else el.textContent = formatter(target);
    }
    requestAnimationFrame(step);
  }, delay);
}
animate(document.getElementById('votes'), votesTarget, function(v){ return v.toFixed(1); }, 1400, 700);
animate(document.getElementById('pl'), plTarget, function(v){ return plPrefix + v.toFixed(2) + 'u'; }, 1400, 700);
</script>
</body></html>"""
    _stat_html = (
        _stat_html
        .replace("__ROUND__", str(_land_round))
        .replace("__LEADER__", str(_land_leader))
        .replace("__VOTES__", f"{_land_votes:.4f}")
        .replace("__PL_ABS__", f"{abs(_land_pl_val):.4f}")
        .replace("__PL_PREFIX__", "+" if _land_pl_val >= 0 else "-")
        .replace("__PL_FALLBACK__", _pl_str)
    )
    _components.html(_stat_html, height=110, scrolling=False)

    # ── Destination panels ──
    _lc1, _lc2 = st.columns(2, gap="medium")
    with _lc1:
        with st.container(key="card_brownlow"):
            st.markdown(f"""
<div class="cc-card-marker cc-brownlow">&#8203;</div>
<div class="dest-content">
  <span class="dest-tag bw">Prediction Engine</span>
  <h2>Brownlow Medal</h2>
  <div class="dest-desc">Live leaderboard, player profiles, game-by-game vote modelling and where the market has it wrong.</div>
  <div class="dest-data-row">
    <div><span class="dr-label">Leader</span><span class="dr-value">{_land_leader}</span></div>
    <div><span class="dr-label">Proj. Votes</span><span class="dr-value">{_land_votes:.1f}</span></div>
    <div><span class="dr-label">Top-10 Acc.</span><span class="dr-value">86%</span></div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Open Leaderboard", type="primary", key="land_bw"):
                st.session_state["active_hub"] = "brownlow"
                st.session_state.page = 'Leaderboard'
                st.rerun()
    with _lc2:
        with st.container(key="card_betting"):
            st.markdown(f"""
<div class="cc-card-marker cc-betting">&#8203;</div>
<div class="dest-content">
  <span class="dest-tag bh">Live Tracking</span>
  <h2>Betting Hub</h2>
  <div class="dest-desc">Track bets, log P&amp;L, flag Cha Ching tips and analyse hit rates and ROI across markets.</div>
  <div class="dest-data-row">
    <div><span class="dr-label">Season</span><span class="dr-value">{_land_n} bets</span></div>
    <div><span class="dr-label">P&amp;L</span><span class="dr-value" style="color:var(--gold)">{_pl_str}</span></div>
    <div><span class="dr-label">Fade Hit Rate</span><span class="dr-value">8/8</span></div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Open Betting Hub", key="land_bh"):
                st.session_state["active_hub"] = "betting"
                st.session_state.page = 'Performance'
                st.rerun()

# ════════════════════════════════════════════════════════════
# BETTING HUB pages
# ════════════════════════════════════════════════════════════
elif _page in _BH_PAGES and _page != 'Predictions':
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
        CURRENT_ROUND = max_season_rounds - 1

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
    <span style="color:var(--text);font-weight:600;">MAE 0.09</span> &nbsp;·&nbsp;
    <span style="color:var(--text);font-weight:600;">86% top-10 accuracy</span>
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
            '<div class="hh-stat"><div class="hh-stat-val">86%</div><div class="hh-stat-lab">Top-10 acc.</div></div>'
            '<div class="hh-stat"><div class="hh-stat-val">0.09</div><div class="hh-stat-lab">MAE</div></div>'
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
            ("🎯", "Cha Ching Tips", "Curated betting tips",  "#e05252"),
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
    _cc1, _cc2 = st.columns([5, 1])
    with _cc1:
        st.markdown('<div class="lb-controls-marker"></div>', unsafe_allow_html=True)
        search = st.text_input("SEARCH PLAYER", "")
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

    display = predictions.copy()
    if search:
        display = display[display['Player_Name'].str.contains(search, case=False, na=False)]
    display = display.head(show_n).copy()
    display.insert(0, 'Rank', range(1, len(display) + 1))
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

    if is_2026:
        _heads = [('Rank', 'lft'), ('Player', 'lft'), ('GP', ''), ('Form', 'lft'), ('Exp Votes', '')]
        if has_fc:
            _heads.append(('Floor–Ceiling', 'lft'))
        _heads += [('Poll %', ''), ('3V Games', '')]
        if has_odds:
            _heads += [('Best Odds', 'grp-start'), ('Mkt %', '')]
    else:
        _heads = [('Rank', 'lft'), ('Player', 'lft'), ('GP', ''), ('Exp Votes', ''),
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

    st.markdown(
        f'<div class="lb-table"><style>{_LB_TBL_CSS}</style>'
        f'<div class="lb-tbl-wrap"><table class="lb-tbl">'
        f'<thead><tr>{_ths}</tr></thead><tbody>{"".join(_rows)}</tbody>'
        f'</table></div></div>',
        unsafe_allow_html=True,
    )
    if is_2026 and _fg:
        st.caption("Form (last 3 rounds): emerald = predicted to poll (≥30%) · grey = quiet · faint = did not play")

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

        _tab_prof, _tab_dna = st.tabs(["Profile", "DNA"])

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
                        _best_round_lbl = f"{int(_best['Season'])} R{int(_best['Round_num']) - 1}"
                    else:
                        _best_round_lbl = f"R{int(_best['Round_num']) - 1}"
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
    <div class="pp-item"><div class="pp-val">{_avg_votes:.2f}</div><div class="pp-lbl">Avg Votes</div></div>
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
                    _rounds_order = (player_games['Round_num'].astype(int) - 1).tolist()
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
                    _x = (player_games['Round_num'] - 1)
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
                st.plotly_chart(fig, width='stretch', key="chart_003")

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
                st.plotly_chart(fig2, width='stretch', key="chart_004")

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
                # Display AFL round (AFLTables Round_num runs 1 ahead) — display only, order unchanged
                _log_disp['Rnd'] = _log_disp['Rnd'] - 1
                if is_career:
                    _log_disp['Season'] = _log_disp['Season'].astype(int)
                for col in _log_disp.select_dtypes(include='float').columns:
                    _log_disp[col] = _log_disp[col].round(1)
                st.dataframe(_style_table(_log_disp), width='stretch', hide_index=True)

        # ── DNA tab ───────────────────────────────────────────
        with _tab_dna:
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

                    # ── Right: disposal-threshold finding (slider-driven) ──
                    with dna_r:
                        st.markdown('<div class="dna-mini-head">Disposal Threshold</div>', unsafe_allow_html=True)
                        thr = st.slider("Min disposals", 10, 40, 30, key="dna_disp_thresh")
                        if has_votes:
                            subset = player_games_dna[player_games_dna['Disposals'] >= thr]
                            n_sub = len(subset)
                            n_tot = len(player_games_dna)
                            if n_sub == 0:
                                st.markdown(
                                    f'<div class="dna-find-val">—</div>'
                                    f'<div class="dna-find-sub">no games at {thr}+ disposals</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                pr  = (subset['Brownlow.Votes'] > 0).mean()
                                av  = subset['Brownlow.Votes'].mean()
                                tvr = (subset['Brownlow.Votes'] == 3).mean()
                                _ln = selected_player.split()[-1]
                                if pr == 1.0:
                                    _s = f"When {_ln} reaches {thr} touches he polls every time"
                                    _s += " — and every one was a 3-vote game." if tvr == 1.0 else f" — averaging {av:.2f} votes."
                                else:
                                    _s = f"At {thr}+ disposals {_ln} polls {pr * 100:.0f}% of the time, averaging {av:.2f} votes."
                                st.markdown(f"""
<div>
  <div class="dna-find-val">{_rate(pr, n_sub)}</div>
  <div class="dna-find-cap">poll rate at {thr}+ disposals</div>
  <div class="dna-find-sentence">{_s}</div>
  <div class="dna-find-strip">
    <div class="dfs"><div class="dfs-v">{n_sub} of {n_tot}</div><div class="dfs-l">Games</div></div>
    <div class="dfs"><div class="dfs-v">{av:.2f}</div><div class="dfs-l">Avg Votes</div></div>
    <div class="dfs"><div class="dfs-v">{_rate(tvr, n_sub)}</div><div class="dfs-l">3-Vote Rate</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="dna-find-sub">No actual-vote data for this season.</div>',
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

                st.markdown('<div class="section-header" style="margin-top:8px">League Efficiency Rankings</div>', unsafe_allow_html=True)
                # Career spans many seasons, so allow a higher minimum-games filter
                # (separate key avoids a stored value falling outside the season range).
                if is_career:
                    _mg_max = max(int(efficiency['Games'].max()), 1)
                    min_g = st.slider("Minimum games", 1, _mg_max, min(50, _mg_max), key="dna_min_g_career")
                else:
                    min_g = st.slider("Minimum games", 1, max_season_rounds, min(10, max_season_rounds), key="dna_min_g")
                sort_by = st.selectbox("Sort by", ['Poll_Rate', 'Win_Poll_Rate', 'HD_Poll_Rate', 'Three_Vote_Rate'],
                                       format_func=lambda x: {
                                           'Poll_Rate': 'Overall Poll Rate', 'Win_Poll_Rate': 'Win Poll Rate',
                                           'HD_Poll_Rate': '30+ Disposal Poll Rate', 'Three_Vote_Rate': '3-Vote Rate',
                                       }[x], key="dna_sort")
                eff_display = efficiency[efficiency['Games'] >= min_g].copy()
                eff_display = eff_display.sort_values(sort_by, ascending=False).head(30)
                eff_display.insert(0, 'Rank', range(1, len(eff_display) + 1))

                # Custom HTML table (Leaderboard convention). Null rule via _rate:
                # 30+ % shows "—" when the player has no 30+ games (HD_Games NaN/0),
                # "0.0%" only when defined-but-zero. Sort logic above is untouched.
                _rows = ""
                for _, rr in eff_display.iterrows():
                    _rows += (
                        '<tr>'
                        f'<td class="lft lb-rank">{int(rr["Rank"])}</td>'
                        f'<td class="lft lb-pname">{rr["Player_Name"]}</td>'
                        f'<td>{int(rr["Games"])}</td>'
                        f'<td class="key">{_rate(rr["Poll_Rate"])}</td>'
                        f'<td>{_rate(rr["Win_Poll_Rate"])}</td>'
                        f'<td>{_rate(rr["Loss_Poll_Rate"])}</td>'
                        f'<td>{_rate(rr["HD_Poll_Rate"], rr.get("HD_Games"))}</td>'
                        f'<td>{_rate(rr["Three_Vote_Rate"])}</td>'
                        f'<td>{rr["Avg_Disposals"]:.1f}</td>'
                        '</tr>'
                    )
                st.markdown(f"""
<style>
.dna-rank .lb-tbl-wrap{{overflow-x:auto;}}
.dna-rank table{{width:100%;border-collapse:collapse;font-family:'IBM Plex Mono',monospace;}}
.dna-rank th{{font-size:10px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--hairline-strong);text-align:right;white-space:nowrap;}}
.dna-rank th.lft{{text-align:left;}}
.dna-rank td{{font-size:13px;padding:8px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;color:var(--steel);}}
.dna-rank td.lft{{text-align:left;}}
.dna-rank td.key{{color:var(--text);font-weight:600;}}
.dna-rank td.lb-rank{{color:var(--text);font-weight:600;width:40px;}}
.dna-rank td.lb-pname{{font-family:'Archivo',sans-serif;font-size:14px;font-weight:600;color:var(--text);}}
.dna-rank tr:hover td{{background:rgba(255,255,255,.02);}}
</style>
<div class="dna-rank"><div class="lb-tbl-wrap"><table>
<thead><tr>
<th class="lft">Rank</th><th class="lft">Player</th><th>Games</th>
<th>Poll %</th><th>Win %</th><th>Loss %</th><th>30+ %</th><th>3V %</th><th>Avg Disp</th>
</tr></thead>
<tbody>{_rows}</tbody>
</table></div></div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PLAYER DNA — merged into Player Profile
# ════════════════════════════════════════════════════════════
if False:  # merged into Player Profile
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#e9eef3;margin:0">Player DNA — {selected_season}</h2>'
        f'<p style="color:var(--muted);margin:4px 0 0 0">Player-specific polling efficiency and tendencies</p></div>',
        unsafe_allow_html=True,
    )

    efficiency = compute_player_efficiency(selected_season)
    if efficiency is None:
        st.error("No game-level data found.")
    else:
        players = sorted(predictions['Player_Name'].tolist())
        selected_player_dna = st.selectbox("Select player", players, key="dna_player")

        if selected_player_dna:
            eff_row = efficiency[efficiency['Player_Name'] == selected_player_dna]
            if not eff_row.empty:
                e = eff_row.iloc[0]
                st.markdown('<div class="section-header">Polling DNA</div>', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f'<div class="dna-card"><div class="dna-label">Overall Poll Rate</div><div class="dna-value">{e["Poll_Rate"] * 100:.1f}%</div><div class="dna-sub">Polled in {e["Poll_Rate"] * e["Games"]:.0f} of {e["Games"]:.0f} games</div></div>', unsafe_allow_html=True)
                with c2:
                    wr = e.get('Win_Poll_Rate', 0)
                    st.markdown(f'<div class="dna-card"><div class="dna-label">Poll Rate in Wins</div><div class="dna-value">{wr * 100:.1f}%</div><div class="dna-sub">Avg {e.get("Win_Avg_Votes", 0):.2f} votes per win</div></div>', unsafe_allow_html=True)
                with c3:
                    lr = e.get('Loss_Poll_Rate', 0)
                    st.markdown(f'<div class="dna-card"><div class="dna-label">Poll Rate in Losses</div><div class="dna-value">{lr * 100:.1f}%</div><div class="dna-sub">Win/loss gap: {(wr - lr) * 100:.1f}pts</div></div>', unsafe_allow_html=True)
                with c4:
                    hd = e.get('HD_Poll_Rate', 0)
                    hd_g = e.get('HD_Games', 0)
                    st.markdown(f'<div class="dna-card"><div class="dna-label">30+ Disposal Poll Rate</div><div class="dna-value">{hd * 100:.1f}%</div><div class="dna-sub">{hd_g:.0f} games with 30+ disposals</div></div>', unsafe_allow_html=True)

                if game_df is not None:
                    player_games = game_df[game_df['Player_Name'] == selected_player_dna].copy()
                    if not player_games.empty and 'Brownlow.Votes' in player_games.columns:
                        st.markdown('<div class="section-header">Vote Distribution</div>', unsafe_allow_html=True)
                        vote_counts = player_games['Brownlow.Votes'].value_counts().sort_index()
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.markdown(f"""
| Votes | Games | Rate |
|-------|-------|------|
| 3 | {int(vote_counts.get(3, 0))} | {vote_counts.get(3, 0) / len(player_games) * 100:.1f}% |
| 2 | {int(vote_counts.get(2, 0))} | {vote_counts.get(2, 0) / len(player_games) * 100:.1f}% |
| 1 | {int(vote_counts.get(1, 0))} | {vote_counts.get(1, 0) / len(player_games) * 100:.1f}% |
| 0 | {int(vote_counts.get(0, 0))} | {vote_counts.get(0, 0) / len(player_games) * 100:.1f}% |
""")
                        with c2:
                            fig_pie = go.Figure(go.Pie(
                                labels=['3 votes', '2 votes', '1 vote', '0 votes'],
                                values=[vote_counts.get(3, 0), vote_counts.get(2, 0),
                                        vote_counts.get(1, 0), vote_counts.get(0, 0)],
                                marker_colors=['#7e8c99', '#34d399', '#f0b429', '#0d141d'],
                                hole=0.4,
                            ))
                            fig_pie.update_layout(
                                plot_bgcolor='#101a24', paper_bgcolor='#101a24',
                                font_color='#e9eef3', margin=dict(t=10, b=10),
                                showlegend=True, height=250,
                                legend=dict(orientation='h', y=-0.1),
                            )
                            fig_pie = apply_chart_theme(fig_pie)
                            st.plotly_chart(fig_pie, width='stretch', key="chart_006")

                        st.markdown('<div class="section-header">Disposal Threshold Analysis</div>', unsafe_allow_html=True)
                        thresh_data = []
                        for t in [15, 20, 25, 28, 30, 33, 35]:
                            subset = player_games[player_games['Disposals'] >= t]
                            if len(subset) >= 2:
                                thresh_data.append({
                                    'Min Disposals': t, 'Games': len(subset),
                                    'Poll Rate': f"{(subset['Brownlow.Votes'] > 0).mean() * 100:.1f}%",
                                    'Avg Votes': f"{subset['Brownlow.Votes'].mean():.2f}",
                                    '3-vote Rate': f"{(subset['Brownlow.Votes'] == 3).mean() * 100:.1f}%",
                                })
                        if thresh_data:
                            st.dataframe(pd.DataFrame(thresh_data), width='stretch', hide_index=True)

        st.markdown('<div class="section-header">League Efficiency Rankings</div>', unsafe_allow_html=True)
        min_g = st.slider("Minimum games", 1, max_season_rounds, min(10, max_season_rounds), key="dna_min_g")
        sort_by = st.selectbox("Sort by", ['Poll_Rate', 'Win_Poll_Rate', 'HD_Poll_Rate', 'Three_Vote_Rate'],
                               format_func=lambda x: {
                                   'Poll_Rate': 'Overall Poll Rate', 'Win_Poll_Rate': 'Win Poll Rate',
                                   'HD_Poll_Rate': '30+ Disposal Poll Rate', 'Three_Vote_Rate': '3-Vote Rate',
                               }[x], key="dna_sort")
        eff_display = efficiency[efficiency['Games'] >= min_g].copy()
        eff_display = eff_display.sort_values(sort_by, ascending=False).head(30)
        eff_display['Poll %'] = (eff_display['Poll_Rate'] * 100).round(1)
        eff_display['Win Poll %'] = (eff_display['Win_Poll_Rate'] * 100).round(1)
        eff_display['Loss Poll %'] = (eff_display['Loss_Poll_Rate'] * 100).round(1)
        eff_display['30+ Poll %'] = (eff_display['HD_Poll_Rate'] * 100).round(1)
        eff_display['3v Rate %'] = (eff_display['Three_Vote_Rate'] * 100).round(1)
        eff_display.insert(0, 'Rank', range(1, len(eff_display) + 1))
        _dna_disp = eff_display[['Rank', 'Player_Name', 'Games', 'Poll %', 'Win Poll %',
                         'Loss Poll %', '30+ Poll %', '3v Rate %', 'Avg_Disposals']].rename(
            columns={'Player_Name': 'Player', 'Avg_Disposals': 'Avg Disp'})
        for col in _dna_disp.select_dtypes(include='float').columns:
            _dna_disp[col] = _dna_disp[col].round(1)
        st.dataframe(
            _style_table(_dna_disp),
            width='stretch', hide_index=True,
        )

# ════════════════════════════════════════════════════════════
# GAME ANALYSIS
# ════════════════════════════════════════════════════════════
if _page == 'Game Analysis':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:var(--text);margin:0">Game Analysis — {selected_season}</h2>'
        f'<p style="color:var(--muted);margin:4px 0 0 0">Round-by-round match predictions · poll probability breakdown</p></div>',
        unsafe_allow_html=True,
    )
    _ga_rbr_tab, _ga_pp_tab = st.tabs(["Round by Round", "Poll Probability"])

    # ── Round by Round tab ────────────────────────────────────
    with _ga_rbr_tab:
        # theme.py gives [data-testid="stTabs"] a --surface (#101a24) fill +
        # border, which reads as a raised card. Neutralise it for this page only
        # via :has(.ga-flush) — the marker below sits INSIDE the tabs so the
        # selector matches. The tab-strip hairline and active-tab emerald
        # underline live on [role="tablist"]/[role="tab"] and are untouched.
        st.markdown(
            '<style>[data-testid="stTabs"]:has(.ga-flush){'
            'background:transparent !important;border:none !important;'
            'box-shadow:none !important;}</style>'
            '<span class="ga-flush" style="display:none"></span>',
            unsafe_allow_html=True,
        )
        rr = load_game(2026)
        if rr is None:
            st.error("No 2026 game-level predictions found. Run predict_2026.py first.")
        else:
            rr = rr.copy()
            rr['Match'] = rr['Home.team'] + ' vs ' + rr['Away.team']
            available_rounds = sorted(rr['Round_num'].dropna().unique().astype(int).tolist())

            sel_col, info_col = st.columns([2, 5])
            with sel_col:
                selected_round = st.selectbox(
                    "Select Round", available_rounds,
                    format_func=lambda r: f"Round {r - 1}",
                    index=max(0, len(available_rounds) - 1),
                    key="rbr_round",
                )
            rnd = rr[rr['Round_num'] == selected_round].copy()
            with info_col:
                st.markdown(
                    f'<div style="line-height:38px;color:var(--muted);font-size:14px;">'
                    f'Round {selected_round - 1} &nbsp;·&nbsp; {rnd["Match"].nunique()} matches &nbsp;·&nbsp; {len(rnd)} players'
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
                expand_key = f"rr_expand_{selected_round}_{game_idx}"
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
                    f'<div class="ga-overline">GAME {game_idx + 1} · ROUND {selected_round - 1}</div>'
                    f'<div class="ga-result">{result_html}</div>'
                    f'<div class="ga-rule"></div>'
                    f'<div class="ga-section-label">PREDICTED VOTES'
                    f'<span class="ga-hint">model expectation · 3-2-1</span></div>'
                    f'{podium_html}'
                    f'<table class="ga-table"><thead><tr>'
                    f'<th class="ga-l">Player</th><th>Exp Votes</th><th>P(3)</th><th>Disp</th>'
                    f'<th>Cont.</th><th>Clr</th><th>Goals</th><th>Coaches</th>'
                    f'</tr></thead><tbody>{"".join(rows_html)}</tbody></table>'
                    f'<div class="ga-legend">heat = expected votes &nbsp;·&nbsp; gold = coaches votes '
                    f'&nbsp;·&nbsp; shaded rows = predicted 3-2-1</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if n_total > 10:
                    _exp_lbl = "↑ Show less" if show_all else f"↓ Show all {n_total} players  (+{n_total - 10} more)"
                    if st.button(_exp_lbl, key=f"rr_btn_{selected_round}_{game_idx}"):
                        st.session_state[expand_key] = not show_all
                        st.rerun()

    # ── Poll Probability tab ──────────────────────────────────
    with _ga_pp_tab:
        c1, c2 = st.columns([2, 1])
        with c1: min_games_pp = st.slider("Min games played", 1, max_season_rounds, min(10, max_season_rounds), key="pp_ming")
        with c2: top_n_pp = st.selectbox("Show top N", [20, 30, 50], index=0, key="pp_topn")

        filtered_pp = predictions[predictions['Games'] >= min_games_pp].head(top_n_pp).copy()
        filtered_pp['P3%'] = (filtered_pp['Exp_3vote_games'] / filtered_pp['Games'] * 100).round(1)
        filtered_pp['P2%'] = (filtered_pp['Exp_2vote_games'] / filtered_pp['Games'] * 100).round(1)
        filtered_pp['P1%'] = (filtered_pp['Exp_1vote_games'] / filtered_pp['Games'] * 100).round(1)

        fig5 = go.Figure()
        fig5.add_trace(go.Bar(name='P(3 votes)', x=filtered_pp['Player_Name'], y=filtered_pp['P3%'], marker_color='#f0b429'))
        fig5.add_trace(go.Bar(name='P(2 votes)', x=filtered_pp['Player_Name'], y=filtered_pp['P2%'], marker_color='#34d399'))
        fig5.add_trace(go.Bar(name='P(1 vote)', x=filtered_pp['Player_Name'], y=filtered_pp['P1%'], marker_color='#4a90c4'))
        fig5 = apply_chart_theme(fig5)
        fig5.update_layout(
            barmode='stack', yaxis_title='Probability (%)',
            xaxis_tickangle=-35, legend=dict(orientation='h', y=1.05),
            margin=dict(t=20, b=120),
        )
        st.plotly_chart(fig5, width='stretch', key="ga_pp_fig5")

# ════════════════════════════════════════════════════════════
# STAT FILTER
# ════════════════════════════════════════════════════════════
if _page == 'Stat Filter':
    # ── 1. Header — no box ────────────────────────────────────
    st.markdown(
        '<div style="margin:2px 0 16px">'
        '<div style="font-size:10px;font-weight:700;letter-spacing:2px;'
        'text-transform:uppercase;color:#7e8c99">Stat Filter</div>'
        '<h1 style="font-family:\'Archivo\',sans-serif;font-size:34px;font-weight:800;'
        'color:#e9eef3;margin:4px 0 2px;line-height:1.05">Threshold to votes</h1>'
        '<div style="color:#7e8c99;font-size:13px">How historical Brownlow polling '
        'responds as you raise a stat threshold · 2015–2026</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    hist = load_all_historical()
    if hist is None:
        st.error("No historical game-level data found. Run brownlow_model.py first.")
    else:
        hist = hist[hist['Brownlow.Votes'].notna()].copy()

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
        # constraint can be dropped for the threshold sweep. The final `mask`
        # is identical to the previous single-expression version.
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

        mask = _base_mask.copy()
        for _lab, _col, _val, _mn, _mx in _stat_sliders:
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
                if _col != active_col:
                    _sweep_mask &= (hist[_col] >= _val)
            _sweep_base = hist[_sweep_mask]

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

            # Vote pool (pre-2026 only), reused for the breakdown strip.
            vote_data = filtered_sf[filtered_sf['Season'] < 2026]
            n3 = int((vote_data['Brownlow.Votes'] == 3).sum())
            n2 = int((vote_data['Brownlow.Votes'] == 2).sum())
            n1 = int((vote_data['Brownlow.Votes'] == 1).sum())
            n0 = int((vote_data['Brownlow.Votes'] == 0).sum())
            vote_total = len(vote_data)

            if (filtered_sf['Season'] == 2026).any():
                _n26 = int((filtered_sf['Season'] == 2026).sum())
                st.markdown(
                    f'<div style="color:#7e8c99;font-size:12px;margin:2px 0 6px">'
                    f'{_n26:,} of these are 2026 games — votes not yet assigned, so all '
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
                st.plotly_chart(fig_sweep, width='stretch', key="sf_sweep_chart")
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
                '<div style="display:grid;grid-template-columns:repeat(4,1fr);margin:18px 0 4px">' +
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
            for col in _sf_disp.select_dtypes(include='float').columns:
                _sf_disp[col] = _sf_disp[col].round(1)
            st.markdown(
                f'<div style="margin:22px 0 6px;font-size:10px;font-weight:700;letter-spacing:1.5px;'
                f'text-transform:uppercase;color:#7e8c99">Sample games '
                f'<span style="font-weight:400;letter-spacing:0;text-transform:none">— showing '
                f'{len(_sf_disp):,} of {total:,} matching</span></div>',
                unsafe_allow_html=True,
            )
            st.dataframe(_quiet_sf_table(_sf_disp), width='stretch', hide_index=True)

# ════════════════════════════════════════════════════════════
# ROUND BY ROUND
# ════════════════════════════════════════════════════════════
if False:  # merged into Game Analysis
    rr = load_game(2026)
    if rr is None:
        st.error("No 2026 game-level predictions found. Run predict_2026.py first.")
    else:
        rr = rr.copy()
        rr['Match'] = rr['Home.team'] + ' vs ' + rr['Away.team']
        available_rounds = sorted(rr['Round_num'].dropna().unique().astype(int).tolist())

        sel_col, info_col = st.columns([2, 5])
        with sel_col:
            selected_round = st.selectbox(
                "Select Round", available_rounds,
                format_func=lambda r: f"Round {r}",
                index=max(0, len(available_rounds) - 1),
                key="rbr_round",
            )
        rnd = rr[rr['Round_num'] == selected_round].copy()
        with info_col:
            st.markdown(
                f'<div style="line-height:38px;color:var(--muted);font-size:14px;">'
                f'Round {selected_round} &nbsp;·&nbsp; {rnd["Match"].nunique()} matches &nbsp;·&nbsp; {len(rnd)} players'
                f'</div>',
                unsafe_allow_html=True,
            )

        def _style_game_table(df):
            max_p3v = df['P(3v) %'].max() if len(df) > 0 and df['P(3v) %'].max() > 0 else 1.0
            def _cell(row):
                i = row.name
                if i == 0: base = 'background-color: rgba(240,180,41,0.22); font-weight:700;'
                elif i == 1: base = 'background-color: rgba(140,165,185,0.15); font-weight:700;'
                elif i == 2: base = 'background-color: rgba(52,211,153,0.12); font-weight:700;'
                elif i % 2 == 0: base = 'background-color: #0d141d;'
                else: base = 'background-color: #101a24;'
                result = []
                for col in df.columns:
                    if col == 'P(3v) %' and i >= 3:
                        v = row[col]
                        norm = v / max_p3v if max_p3v > 0 else 0.0
                        a = 0.08 + norm * 0.45
                        result.append(f'background-color: rgba(52,211,153,{a:.2f});')
                    else:
                        result.append(base)
                return result
            return df.style.apply(_cell, axis=1)

        GAME_COLOURS = ['#34d399', '#e63946', '#7e8c99', '#f0b429', '#4a90d9', '#e07b39', '#6c3483', '#1a6e8c', '#7d6608', '#b03a2e']
        game_order = rnd.drop_duplicates('Match')[['Match', 'Home.team', 'Away.team', 'Home.score', 'Away.score']].reset_index(drop=True)
        col_cfg = {
            'Player': st.column_config.TextColumn('Player'),
            'Team': st.column_config.TextColumn('Team', width='small'),
            'Rank': st.column_config.NumberColumn('Rank', width='small'),
            'Votes (exp)': st.column_config.NumberColumn('Votes (exp)', format='%.1f'),
            'P(3v) %': st.column_config.NumberColumn('P(3v) %', format='%.1f'),
            'P(2v) %': st.column_config.NumberColumn('P(2v) %', format='%.1f'),
            'Coaches V': st.column_config.NumberColumn('Coaches V', format='%.1f'),
            'Disposals': st.column_config.NumberColumn('Disposals', width='small'),
            'Cont. Poss': st.column_config.NumberColumn('Cont. Poss', width='small'),
            'Clearances': st.column_config.NumberColumn('Clearances', width='small'),
            'Goals': st.column_config.NumberColumn('Goals', width='small'),
        }

        for game_idx, game_row in game_order.iterrows():
            match = game_row['Match']
            home = game_row['Home.team']
            away = game_row['Away.team']
            colour = GAME_COLOURS[game_idx % len(GAME_COLOURS)]
            try:
                home_score = int(float(game_row['Home.score']))
                away_score = int(float(game_row['Away.score']))
                score_str = f"{home_score} – {away_score}"
                if home_score > away_score:
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{home}</span><span style='color:var(--muted);font-size:18px'> def. {away}</span>"
                elif away_score > home_score:
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{away}</span><span style='color:var(--muted);font-size:18px'> def. {home}</span>"
                else:
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{home} drew {away}</span>"
                score_html = f"<span style='color:{colour};font-size:17px;font-weight:600'>&nbsp;&nbsp;{score_str}</span>"
                header_body = f"{result_html}{score_html}"
            except (ValueError, TypeError):
                header_body = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{match}</span>"

            st.markdown(
                f'<div style="border-left:6px solid {colour};padding:16px 22px;background:var(--surface);'
                f'border-radius:0 8px 8px 0;margin:36px 0 8px 0;box-shadow:0 1px 4px rgba(0,0,0,0.24);'
                f'border:1px solid var(--line);border-left:6px solid {colour};">'
                f'<div style="color:{colour};font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px">'
                f'Game {game_idx + 1} &nbsp;·&nbsp; Round {selected_round}</div>'
                f'<div>{header_body}</div></div>',
                unsafe_allow_html=True,
            )

            gp = rnd[rnd['Match'] == match].copy().sort_values('Exp_Votes', ascending=False).reset_index(drop=True)
            gp['Rank'] = range(1, len(gp) + 1)
            disp = pd.DataFrame({
                'Player': gp['Player_Name'], 'Team': gp['Team'], 'Rank': gp['Rank'].astype(int),
                'Votes (exp)': gp['Exp_Votes'].round(1),
                'P(3v) %': (gp['P_3'] * 100).round(1), 'P(2v) %': (gp['P_2'] * 100).round(1),
                'Coaches V': pd.to_numeric(gp['Coaches_Votes'], errors='coerce').fillna(0).round(1),
                'Disposals': pd.to_numeric(gp['Disposals'], errors='coerce').fillna(0).astype(int),
                'Cont. Poss': pd.to_numeric(gp.get('Contested.Possessions', gp.get('ContPoss', pd.Series([0]*len(gp)))), errors='coerce').fillna(0).astype(int),
                'Clearances': pd.to_numeric(gp['Clearances'], errors='coerce').fillna(0).astype(int),
                'Goals': pd.to_numeric(gp['Goals'], errors='coerce').fillna(0).astype(int),
            })
            for col in disp.select_dtypes(include='float').columns:
                disp[col] = disp[col].round(1)
            n_total = len(disp)
            expand_key = f"rr_expand_{selected_round}_{game_idx}"
            if expand_key not in st.session_state:
                st.session_state[expand_key] = False
            show_all = st.session_state[expand_key]
            disp_view = disp if show_all else disp.head(10)
            row_height = min(len(disp_view) * 35 + 38, 780)
            st.dataframe(_style_game_table(disp_view), width='stretch', hide_index=True,
                         height=row_height, column_config=col_cfg)
            if n_total > 10:
                remaining_rbr = n_total - 10
                label = "Show less" if show_all else f"Show all {n_total} players (+{remaining_rbr} more)"
                if st.button(label, key=f"rr_btn_{selected_round}_{game_idx}"):
                    st.session_state[expand_key] = not show_all
                    st.rerun()

# ════════════════════════════════════════════════════════════
# SEASON PROJECTION
# ════════════════════════════════════════════════════════════
if False:  # merged into Betting Edge
    st.markdown(
        '<div class="title-bar"><h2 style="color:#e9eef3;margin:0">2026 Season Projection</h2>'
        '<p style="color:var(--muted);margin:4px 0 0 0">Actual votes to date + model-projected remaining rounds</p></div>',
        unsafe_allow_html=True,
    )
    proj = load_season_projection()
    if proj is None:
        st.error("No season projection found. Run predict_2026.py first.")
    else:
        rounds_played = max_season_rounds
        remaining_sp = int(proj['Remaining_Rounds'].iloc[0])
        total_rounds_sp = rounds_played + remaining_sp
        leader_sp = proj.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Rounds Played</div><div class="metric-value">{rounds_played - 1}</div><div class="metric-sub">of {total_rounds_sp - 1} H&A rounds</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Remaining Rounds</div><div class="metric-value">{remaining_sp}</div><div class="metric-sub">to be projected</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Projected Leader</div><div class="metric-value" style="font-size:18px">{leader_sp["Player"]}</div><div class="metric-sub">{leader_sp["Season_Total_Projected"]:.1f} projected votes</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Per Game (Leader)</div><div class="metric-value">{leader_sp["Avg_Predicted_Per_Game"]:.2f}</div><div class="metric-sub">expected votes per game</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-header">Top 30 — Projected Season Total</div>', unsafe_allow_html=True)
        top30_sp = proj.head(30).copy()
        top30_sp['Exp_Total_Votes'] = (top30_sp['Avg_Predicted_Per_Game'] * top30_sp['Games_Played']).round(1)
        err_upper = (top30_sp['Ceiling_Projection'] - top30_sp['Exp_Total_Votes']).clip(lower=0)
        err_lower = (top30_sp['Exp_Total_Votes'] - top30_sp['Floor_Projection']).clip(lower=0)

        fig_proj = go.Figure()
        fig_proj.add_trace(go.Bar(
            name='Expected (played rounds)', x=top30_sp['Player'], y=top30_sp['Exp_Total_Votes'],
            marker_color='#34d399', opacity=0.9,
            error_y=dict(type='data', array=err_upper.tolist(), arrayminus=err_lower.tolist(),
                         visible=True, color='rgba(52,211,153,0.55)', thickness=1.5, width=4),
            hovertemplate='<b>%{x}</b><br>Expected so far: %{y:.1f}<br>'
                          'Floor: ' + top30_sp['Floor_Projection'].round(1).astype(str) + '<br>'
                          'Ceiling: ' + top30_sp['Ceiling_Projection'].round(1).astype(str) + '<extra></extra>',
        ))
        fig_proj.add_trace(go.Bar(
            name='Projected Remaining', x=top30_sp['Player'], y=top30_sp['Projected_Remaining'],
            marker_color='#7e8c99', opacity=0.9,
            hovertemplate='<b>%{x}</b><br>Projected remaining: %{y:.1f}<extra></extra>',
        ))
        fig_proj.update_layout(
            barmode='stack', plot_bgcolor='#101a24', paper_bgcolor='#101a24', font_color='#e9eef3',
            yaxis=dict(title='Votes', gridcolor='#ede8df'), xaxis=dict(tickangle=-35),
            legend=dict(orientation='h', y=1.08, bgcolor='rgba(0,0,0,0)'),
            margin=dict(t=20, b=130), height=480,
        )
        fig_proj = apply_chart_theme(fig_proj)
        st.plotly_chart(fig_proj, width='stretch', key="chart_014")
        st.caption("Green = Expected votes from played rounds (error bars = 10th–90th percentile)   Brown = Projected votes for remaining rounds")

        st.markdown('<div class="section-header">Full Season Projection Table</div>', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1: search_proj = st.text_input("Search player", "", key="proj_search")
        with col2: show_n_proj = st.selectbox("Show", [30, 50, 100, 200], index=0, key="proj_show")
        display_proj = proj.copy()
        if search_proj:
            display_proj = display_proj[display_proj['Player'].str.contains(search_proj, case=False)]
        display_proj = display_proj.head(show_n_proj).copy()
        display_proj.insert(0, 'Rank', range(1, len(display_proj) + 1))
        display_proj['Avg/Game'] = display_proj['Avg_Predicted_Per_Game'].round(2)
        display_proj['Projected'] = display_proj['Projected_Remaining'].round(1)
        display_proj['Season Total'] = display_proj['Season_Total_Projected'].round(1)
        display_proj['Floor'] = display_proj['Floor_Projection'].round(1)
        display_proj['Ceiling'] = display_proj['Ceiling_Projection'].round(1)
        _sp_disp = display_proj[['Rank', 'Player', 'Team', 'Games_Played', 'Actual_Votes',
                      'Avg/Game', 'Remaining_Rounds', 'Projected', 'Floor', 'Ceiling', 'Season Total']].rename(
            columns={'Games_Played': 'Games', 'Remaining_Rounds': 'Rounds Left', 'Actual_Votes': 'Actual'})
        for col in _sp_disp.select_dtypes(include='float').columns:
            _sp_disp[col] = _sp_disp[col].round(1)
        st.dataframe(_style_table(_sp_disp), width='stretch', hide_index=True)

# ════════════════════════════════════════════════════════════
# PLAYER COMPARISON
# ════════════════════════════════════════════════════════════
if _page == 'Player Comparison':
    _cmp_players = sorted(predictions['Player_Name'].tolist())
    _cmp_proj = load_season_projection()
    _cmp_odds = load_best_odds()

    _def1 = predictions.iloc[0]['Player_Name'] if len(predictions) > 0 else _cmp_players[0]
    _def2 = predictions.iloc[1]['Player_Name'] if len(predictions) > 1 else _cmp_players[1]

    # The matchup header sits at the very top but needs the chosen players —
    # reserve its slot now, then fill it once the selectboxes below resolve.
    _hdr_slot = st.container()

    _sel_col1, _sel_col2 = st.columns(2)
    with _sel_col1:
        _p1 = st.selectbox("Player 1", _cmp_players,
                           index=_cmp_players.index(_def1), key="cmp_p1")
    with _sel_col2:
        _p2 = st.selectbox("Player 2", _cmp_players,
                           index=_cmp_players.index(_def2), key="cmp_p2")

    def _cmp_player_data(name):
        row = predictions[predictions['Player_Name'] == name]
        if row.empty:
            return None
        r = row.iloc[0]
        d = {
            'name': name,
            'team': r['Team'],
            'exp_votes': round(float(r['Exp_Total_Votes']), 1),
            'poll_pct': round(float(r['Avg_Poll_Prob']) * 100, 1),
            'three_vote_games': round(float(r['Exp_3vote_games']), 1),
            'floor': None, 'ceiling': None,
            'best_odds': None, 'market_pct': None,
        }
        if _cmp_proj is not None and 'Floor_Projection' in _cmp_proj.columns:
            pr = _cmp_proj[_cmp_proj['Player'] == name]
            if not pr.empty:
                d['floor'] = round(float(pr.iloc[0]['Floor_Projection']), 1)
                d['ceiling'] = round(float(pr.iloc[0]['Ceiling_Projection']), 1)
        if _cmp_odds is not None and len(_cmp_odds) > 0:
            ow = _cmp_odds[_cmp_odds['player'] == name]
            if not ow.empty:
                v = ow.iloc[0]['best_odds']
                d['best_odds'] = round(float(v), 1) if pd.notna(v) else None
                v2 = ow.iloc[0]['implied_prob']
                d['market_pct'] = round(float(v2), 1) if pd.notna(v2) else None
        return d

    _d1 = _cmp_player_data(_p1)
    _d2 = _cmp_player_data(_p2)

    # ── 1. Matchup header — no bordered box, hero exp-votes per player ──
    with _hdr_slot:
        _kick = (f'<div style="font-size:10px;font-weight:700;letter-spacing:2px;'
                 f'text-transform:uppercase;color:#7e8c99;margin-bottom:14px">'
                 f'Player Comparison · {selected_season}</div>')
        if _d1 and _d2 and _p1 != _p2:
            _hi1 = _d1['exp_votes'] >= _d2['exp_votes']
            _hc1 = '#34d399' if _hi1 else '#e9eef3'
            _hc2 = '#34d399' if not _hi1 else '#e9eef3'

            def _hero_side(d, hc, align):
                return (
                    f'<div style="text-align:{align}">'
                    f'<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;'
                    f'text-transform:uppercase;color:#7e8c99">{d["team"]}</div>'
                    f'<div style="font-family:\'Archivo\',sans-serif;font-size:32px;font-weight:800;'
                    f'color:#e9eef3;line-height:1.12;margin:2px 0 10px">{d["name"]}</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:40px;font-weight:600;'
                    f'color:{hc};line-height:1">{d["exp_votes"]:.1f}</div>'
                    f'<div style="font-size:9px;font-weight:700;letter-spacing:1.5px;'
                    f'text-transform:uppercase;color:#7e8c99;margin-top:2px">exp votes</div>'
                    f'</div>'
                )

            st.markdown(
                _kick +
                '<div style="display:grid;grid-template-columns:1fr auto 1fr;'
                'align-items:center;gap:24px;margin-bottom:18px">' +
                _hero_side(_d1, _hc1, 'right') +
                '<div style="font-family:\'Archivo\',sans-serif;font-size:22px;font-weight:800;'
                'letter-spacing:2px;color:#7e8c99">VS</div>' +
                _hero_side(_d2, _hc2, 'left') +
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(_kick, unsafe_allow_html=True)

    if _p1 == _p2:
        st.warning("Select two different players to compare.")
    elif _d1 and _d2:
        _tab_so, _tab_h2h = st.tabs(["Season Overview", "Head to Head Betting"])

        # ── Season Overview tab ───────────────────────────────
        with _tab_so:
            _f_num  = lambda v: f"{v:.1f}"
            _f_pct  = lambda v: f"{v:.1f}%"
            _f_odds = lambda v: f"${v:.1f}"

            def _grp_header(title):
                return (f'<div style="display:flex;align-items:center;gap:10px;margin:22px 0 8px">'
                        f'<div style="font-size:10px;font-weight:700;letter-spacing:2px;'
                        f'text-transform:uppercase;color:#7e8c99;white-space:nowrap">{title}</div>'
                        f'<div style="flex:1;height:1px;background:rgba(140,165,185,.14)"></div></div>')

            def _tot_row(label, v1, v2, fmt, lower_wins=False):
                # Leader = higher value, except Best odds where lower wins. Bar
                # widths are each player's value as a share of the pair's max
                # (weighting inverted for odds so the favourite reads longest).
                if v1 is None or v2 is None:
                    s1 = fmt(v1) if v1 is not None else "—"
                    s2 = fmt(v2) if v2 is not None else "—"
                    w1 = w2 = 0.0
                    lead1 = lead2 = False
                else:
                    lead1 = (v1 <= v2) if lower_wins else (v1 >= v2)
                    lead2 = not lead1
                    if lower_wins:
                        ww1 = 1.0 / v1 if v1 else 0.0
                        ww2 = 1.0 / v2 if v2 else 0.0
                    else:
                        ww1, ww2 = (v1 or 0.0), (v2 or 0.0)
                    _mx = max(ww1, ww2) or 1.0
                    w1 = ww1 / _mx * 100.0
                    w2 = ww2 / _mx * 100.0
                    s1, s2 = fmt(v1), fmt(v2)
                _vc1 = '#34d399' if lead1 else '#7e8c99'
                _vc2 = '#34d399' if lead2 else '#7e8c99'
                _vw1 = '600' if lead1 else '400'
                _vw2 = '600' if lead2 else '400'
                _bb1 = '#34d399' if lead1 else 'rgba(126,140,153,0.45)'
                _bb2 = '#34d399' if lead2 else 'rgba(126,140,153,0.45)'
                return (
                    f'<div style="margin:11px 0 0">'
                    f'<div style="text-align:center;font-size:9px;font-weight:700;letter-spacing:1.5px;'
                    f'text-transform:uppercase;color:#7e8c99;margin-bottom:4px">{label}</div>'
                    f'<div style="display:grid;grid-template-columns:56px 1fr 1px 1fr 56px;'
                    f'align-items:center;gap:8px">'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;text-align:right;'
                    f'color:{_vc1};font-weight:{_vw1}">{s1}</div>'
                    f'<div style="display:flex;justify-content:flex-end">'
                    f'<div style="width:{w1:.1f}%;height:8px;border-radius:4px;background:{_bb1}"></div></div>'
                    f'<div style="width:1px;height:20px;background:rgba(140,165,185,.14)"></div>'
                    f'<div style="display:flex;justify-content:flex-start">'
                    f'<div style="width:{w2:.1f}%;height:8px;border-radius:4px;background:{_bb2}"></div></div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;text-align:left;'
                    f'color:{_vc2};font-weight:{_vw2}">{s2}</div>'
                    f'</div></div>'
                )

            # ── 4. Tale of the tape (one HTML block) ──────────────
            # theme.py gives [data-testid="stTabs"] a --surface (#101a24) fill +
            # border, which reads as a raised card. Neutralise it for this page
            # only via :has(.pc-flush) so the tabs sit flush on the app bg. The
            # tab-strip hairline and active-tab emerald underline live on
            # [role="tablist"]/[role="tab"] and are untouched.
            _html = (
                '<style>'
                '[data-testid="stTabs"]:has(.pc-flush){'
                'background:transparent !important;border:none !important;'
                'box-shadow:none !important;}'
                '</style>'
                '<div class="pc-flush" style="margin-top:2px">'
            )
            _html += _grp_header('Vote Projection')
            _html += _tot_row('Expected Votes', _d1['exp_votes'], _d2['exp_votes'], _f_num)
            _html += _tot_row('Floor', _d1['floor'], _d2['floor'], _f_num)
            _html += _tot_row('Ceiling', _d1['ceiling'], _d2['ceiling'], _f_num)
            _html += _tot_row('Poll %', _d1['poll_pct'], _d2['poll_pct'], _f_pct)
            _html += _tot_row('3-Vote Games', _d1['three_vote_games'], _d2['three_vote_games'], _f_num)

            # Per-game Form — same stats the radar fed, same labels.
            _radar_candidates = [
                ('Disposals',              'Disposals'),
                ('Contested.Possessions',  'Cont. Poss'),
                ('Clearances',             'Clearances'),
                ('Tackles',                'Tackles'),
                ('Inside.50s',             'Inside 50s'),
                ('Coaches_Votes',          'Coaches Votes'),
            ]
            _radar_pairs = []
            if game_df is not None:
                _radar_pairs = [(s, l) for s, l in _radar_candidates if s in game_df.columns]
            if _radar_pairs:
                _r_stats = [s for s, _ in _radar_pairs]
                _g1_mean = game_df[game_df['Player_Name'] == _p1][_r_stats].mean()
                _g2_mean = game_df[game_df['Player_Name'] == _p2][_r_stats].mean()
                _html += _grp_header('Per-game Form')
                for _s, _lab in _radar_pairs:
                    _m1 = float(_g1_mean.get(_s)) if pd.notna(_g1_mean.get(_s)) else None
                    _m2 = float(_g2_mean.get(_s)) if pd.notna(_g2_mean.get(_s)) else None
                    _html += _tot_row(_lab, _m1, _m2, _f_num)

            _html += _grp_header('Market')
            _html += _tot_row('Best Odds', _d1['best_odds'], _d2['best_odds'], _f_odds, lower_wins=True)
            _html += _tot_row('MVP %', _d1['market_pct'], _d2['market_pct'], _f_pct)

            # ── 5. Projected range bars (inline SVG, same HTML block) ──
            _rvals = [x for x in [_d1['floor'], _d1['ceiling'], _d1['exp_votes'],
                                  _d2['floor'], _d2['ceiling'], _d2['exp_votes']] if x is not None]
            if len(_rvals) >= 2:
                _xmin, _xmax = min(_rvals), max(_rvals)
                _span = (_xmax - _xmin) or 1.0

                def _xp(v):
                    return 70.0 + (v - _xmin) / _span * 860.0

                _rows_svg = ''
                for _rd, _rcol, _by in [(_d1, '#34d399', 56), (_d2, 'rgba(126,140,153,0.55)', 118)]:
                    _rows_svg += (f'<text x="70" y="{_by-16}" font-family="Archivo,sans-serif" '
                                  f'font-size="12" font-weight="700" fill="#e9eef3">{_rd["name"]}</text>')
                    _rows_svg += (f'<line x1="70" y1="{_by}" x2="930" y2="{_by}" '
                                  f'stroke="rgba(140,165,185,.14)" stroke-width="1" />')
                    if _rd['floor'] is not None and _rd['ceiling'] is not None:
                        _x0, _x1 = _xp(_rd['floor']), _xp(_rd['ceiling'])
                        _rows_svg += (f'<rect x="{_x0:.1f}" y="{_by-6}" width="{max(_x1-_x0,2):.1f}" '
                                      f'height="12" rx="6" fill="{_rcol}" />')
                        _rows_svg += (f'<text x="{_x0-8:.1f}" y="{_by+4}" text-anchor="end" '
                                      f'font-family="IBM Plex Mono,monospace" font-size="11" '
                                      f'fill="#7e8c99">{_rd["floor"]:.1f}</text>')
                        _rows_svg += (f'<text x="{_x1+8:.1f}" y="{_by+4}" text-anchor="start" '
                                      f'font-family="IBM Plex Mono,monospace" font-size="11" '
                                      f'fill="#7e8c99">{_rd["ceiling"]:.1f}</text>')
                    if _rd['exp_votes'] is not None:
                        _xe = _xp(_rd['exp_votes'])
                        _rows_svg += (f'<line x1="{_xe:.1f}" y1="{_by-10}" x2="{_xe:.1f}" y2="{_by+10}" '
                                      f'stroke="#ffffff" stroke-width="2" />')
                _html += _grp_header('Projected Range')
                _html += (f'<svg viewBox="0 0 1000 150" width="100%" '
                          f'preserveAspectRatio="xMidYMid meet" style="display:block;margin-top:4px">'
                          f'{_rows_svg}</svg>')

            _html += '</div>'
            st.markdown(_html, unsafe_allow_html=True)

            # ── 6. Round by round — predicted votes (plotly) ──────
            if game_df is not None:
                _g1 = game_df[game_df['Player_Name'] == _p1].sort_values('Round_num')
                _g2 = game_df[game_df['Player_Name'] == _p2].sort_values('Round_num')
                if not _g1.empty or not _g2.empty:
                    st.markdown(_grp_header('Round by Round — Predicted Votes'), unsafe_allow_html=True)
                    _fig_rbr = go.Figure()
                    if not _g1.empty:
                        _fig_rbr.add_trace(go.Scatter(
                            x=_g1['Round_num'], y=_g1['Exp_Votes'].round(1),
                            name=_p1, mode='lines+markers',
                            line=dict(color='#34d399', width=2.5),
                            marker=dict(size=7, color='#34d399'),
                            hovertemplate='<b>' + _p1 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    if not _g2.empty:
                        _fig_rbr.add_trace(go.Scatter(
                            x=_g2['Round_num'], y=_g2['Exp_Votes'].round(1),
                            name=_p2, mode='lines+markers',
                            line=dict(color='rgba(126,140,153,0.55)', width=2.5),
                            marker=dict(size=7, color='rgba(126,140,153,0.55)'),
                            hovertemplate='<b>' + _p2 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    _fig_rbr = apply_chart_theme(_fig_rbr)
                    _fig_rbr.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(title='Round', dtick=1, showgrid=False, zeroline=False),
                        yaxis=dict(title='Predicted Votes', rangemode='tozero',
                                   gridcolor='rgba(140,165,185,.14)', zeroline=False),
                        legend=dict(orientation='h', y=1.1),
                        margin=dict(t=20, b=40), height=300, hovermode='x unified',
                    )
                    st.plotly_chart(_fig_rbr, width='stretch', key="cmp_so_rbr")

        # ── Head to Head Betting tab ──────────────────────────
        with _tab_h2h:
            _total_exp = _d1['exp_votes'] + _d2['exp_votes']
            _ma = round(_d1['exp_votes'] / _total_exp * 100, 1) if _total_exp > 0 else 50.0
            _mb = round(100.0 - _ma, 1)
            _has_mkt = _d1['market_pct'] is not None and _d2['market_pct'] is not None
            if _has_mkt:
                _mkt_sum = _d1['market_pct'] + _d2['market_pct']
                _mkta = round(_d1['market_pct'] / _mkt_sum * 100, 1) if _mkt_sum > 0 else 50.0
                _mktb = round(100.0 - _mkta, 1)
            else:
                _mkta = _mktb = None
            _edge_a = round(_ma - _mkta, 1) if _has_mkt else None

            st.markdown('<div class="section-header">Model Probability</div>', unsafe_allow_html=True)
            _h2h_ca, _h2h_cb = st.columns(2)
            for _col, _d, _colour, _mpct in [(_h2h_ca, _d1, '#34d399', _ma), (_h2h_cb, _d2, 'var(--muted)', _mb)]:
                with _col:
                    _fs = f"{_d['floor']}" if _d['floor'] is not None else "—"
                    _cs = f"{_d['ceiling']}" if _d['ceiling'] is not None else "—"
                    st.markdown(
                        f'<div style="background:var(--surface);border:1px solid var(--line);border-top:3px solid {_colour};'
                        f'border-radius:8px;padding:16px 20px;margin:4px 0;">'
                        f'<div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">{_d["team"]}</div>'
                        f'<div style="font-size:22px;font-weight:800;color:var(--text);margin:3px 0 12px 0">{_d["name"]}</div>'
                        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px 14px;">'
                        f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Exp Votes</div>'
                        f'<div style="font-size:22px;font-weight:800;color:{_colour}">{_d["exp_votes"]}</div></div>'
                        f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Floor</div>'
                        f'<div style="font-size:22px;font-weight:800;color:{_colour}">{_fs}</div></div>'
                        f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Ceiling</div>'
                        f'<div style="font-size:22px;font-weight:800;color:{_colour}">{_cs}</div></div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
            st.markdown(
                f'<div style="margin:18px 0 6px 0;display:flex;border-radius:6px;overflow:hidden;height:44px;'
                f'box-shadow:0 1px 4px rgba(0,0,0,0.10);">'
                f'<div style="width:{_ma}%;background:#34d399;display:flex;align-items:center;justify-content:center;">'
                f'<span style="color:#fff;font-weight:800;font-size:17px">{_ma}%</span></div>'
                f'<div style="width:{_mb}%;background:var(--muted);display:flex;align-items:center;justify-content:center;">'
                f'<span style="color:#fff;font-weight:800;font-size:17px">{_mb}%</span></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px;">'
                f'<span>{_p1}</span><span>{_p2}</span></div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="section-header">Market Implied Probability</div>', unsafe_allow_html=True)
            if _has_mkt:
                st.markdown(
                    f'<div style="margin:12px 0 6px 0;display:flex;border-radius:6px;overflow:hidden;height:44px;">'
                    f'<div style="width:{_mkta}%;background:#4a90c4;display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:var(--text);font-weight:800;font-size:17px">{_mkta}%</span></div>'
                    f'<div style="width:{_mktb}%;background:var(--surface-2);display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:var(--muted);font-weight:800;font-size:17px">{_mktb}%</span></div>'
                    f'</div>'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px;">'
                    f'<span>{_p1} &nbsp;${_d1["best_odds"]}</span><span>{_p2} &nbsp;${_d2["best_odds"]}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                _missing = [n for n, d in [(_p1, _d1), (_p2, _d2)] if d['market_pct'] is None]
                st.info(f"Market odds not available for: {', '.join(_missing)}")

            st.markdown('<div class="section-header">Edge Indicator</div>', unsafe_allow_html=True)
            if _edge_a is not None:
                _favoured = _p1 if _ma >= _mb else _p2
                _edge_val = round(_ma - _mkta, 1) if _ma >= _mb else round(_mb - _mktb, 1)
                _edge_abs = abs(_edge_val)
                if _edge_val > 5:
                    _ebg, _ebord, _elabel = 'rgba(52,211,153,0.08)', '#34d399', 'MODEL EDGE'
                    _emsg = (f"The model gives <strong>{_favoured}</strong> a <strong>+{_edge_abs}%</strong> "
                             f"edge over market implied. Model: {_ma if _favoured == _p1 else _mb}% &nbsp;·&nbsp; "
                             f"Market: {_mkta if _favoured == _p1 else _mktb}%")
                elif _edge_val < -5:
                    _ebg, _ebord, _elabel = 'rgba(74,144,196,0.08)', '#4a90c4', 'MARKET FAVOURS'
                    _mkt_fav = _p2 if _favoured == _p1 else _p1
                    _emsg = (f"Market prices <strong>{_mkt_fav}</strong> <strong>{_edge_abs}%</strong> higher "
                             f"than the model suggests. Model: {_ma if _favoured == _p1 else _mb}% &nbsp;·&nbsp; "
                             f"Market: {_mkta if _favoured == _p1 else _mktb}%")
                else:
                    _ebg, _ebord, _elabel = '#101a24', '#7e8c99', 'NEUTRAL'
                    _emsg = (f"Model and market broadly agree — difference is only "
                             f"<strong>{_edge_abs}%</strong>. No clear edge either way.")
                st.markdown(
                    f'<div style="background:{_ebg};border:1px solid {_ebord};'
                    f'border-radius:8px;padding:16px 22px;margin:8px 0;">'
                    f'<div style="font-size:11px;font-weight:800;letter-spacing:2.5px;text-transform:uppercase;'
                    f'color:{_ebord};margin-bottom:6px">{_elabel}</div>'
                    f'<div style="font-size:14px;color:var(--text);line-height:1.8">{_emsg}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Market odds required for edge calculation.")

            if game_df is not None:
                st.markdown('<div class="section-header">Round by Round — Predicted Votes</div>', unsafe_allow_html=True)
                _hg1 = game_df[game_df['Player_Name'] == _p1].sort_values('Round_num')
                _hg2 = game_df[game_df['Player_Name'] == _p2].sort_values('Round_num')
                if not _hg1.empty or not _hg2.empty:
                    _fig_h2h_rbr = go.Figure()
                    if not _hg1.empty:
                        _fig_h2h_rbr.add_trace(go.Scatter(
                            x=_hg1['Round_num'], y=_hg1['Exp_Votes'].round(1),
                            name=_p1, mode='lines+markers',
                            line=dict(color='#34d399', width=2.5), marker=dict(size=7, color='#34d399'),
                            hovertemplate='<b>' + _p1 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    if not _hg2.empty:
                        _fig_h2h_rbr.add_trace(go.Scatter(
                            x=_hg2['Round_num'], y=_hg2['Exp_Votes'].round(1),
                            name=_p2, mode='lines+markers',
                            line=dict(color='#7e8c99', width=2.5), marker=dict(size=7, color='#7e8c99'),
                            hovertemplate='<b>' + _p2 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    _fig_h2h_rbr = apply_chart_theme(_fig_h2h_rbr)
                    _fig_h2h_rbr.update_layout(
                        xaxis=dict(title='Round', dtick=1),
                        yaxis=dict(title='Predicted Votes', rangemode='tozero'),
                        legend=dict(orientation='h', y=1.1),
                        margin=dict(t=20, b=40), height=300, hovermode='x unified',
                    )
                    st.plotly_chart(_fig_h2h_rbr, width='stretch', key="chart_020")

            st.markdown('<div class="section-header">Verdict</div>', unsafe_allow_html=True)
            _vfav  = _p1 if _ma >= _mb else _p2
            _vund  = _p2 if _ma >= _mb else _p1
            _vfav_d = _d1 if _ma >= _mb else _d2
            _vund_d = _d2 if _ma >= _mb else _d1
            _vfav_pct = _ma if _ma >= _mb else _mb
            _vdiff_exp = round(abs(_d1['exp_votes'] - _d2['exp_votes']), 1)
            _vc2 = '#34d399' if _ma >= _mb else 'var(--muted)'
            _bet_line = ""
            if _edge_a is not None:
                _v_edge = round(_ma - _mkta, 1) if _ma >= _mb else round(_mb - _mktb, 1)
                _vfav_odds = _d1['best_odds'] if _ma >= _mb else _d2['best_odds']
                if _v_edge > 5 and _vfav_odds is not None:
                    _bet_line = (f" At ${_vfav_odds}, {_vfav.split()[0]} represents value — "
                                 f"model is {_v_edge}% more confident than the market.")
                elif _v_edge < -5:
                    _bet_line = " Market is pricing this matchup differently to the model — proceed with caution."
                else:
                    _bet_line = " Odds fairly reflect the model's assessment — no strong betting edge here."
            _floor_note = ""
            if _vfav_d['floor'] is not None and _vund_d['ceiling'] is not None:
                if _vfav_d['floor'] > _vund_d['ceiling']:
                    _floor_note = (f" Even at floor, {_vfav.split()[0]} ({_vfav_d['floor']}) "
                                   f"exceeds {_vund.split()[0]}'s ceiling ({_vund_d['ceiling']}).")
            st.markdown(
                f'<div style="background:var(--surface);border:1px solid var(--line);border-top:3px solid {_vc2};'
                f'border-radius:8px;padding:20px 24px;margin:6px 0;">'
                f'<div style="font-size:14px;color:var(--text);line-height:2;">'
                f'The model picks <strong style="color:{_vc2};font-size:16px">{_vfav}</strong> with a '
                f'<strong>{_vfav_pct}%</strong> probability of outpolling {_vund} '
                f'({_d1["exp_votes"]} vs {_d2["exp_votes"]} expected votes, gap of {_vdiff_exp}).'
                f'{_bet_line}{_floor_note}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# ════════════════════════════════════════════════════════════
# HEAD TO HEAD
# ════════════════════════════════════════════════════════════
if False:  # merged into Player Comparison
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#e9eef3;margin:0">Head to Head — {selected_season}</h2>'
        f'<p style="color:var(--muted);margin:4px 0 0 0">Model probability vs market implied probability</p></div>',
        unsafe_allow_html=True,
    )

    if predictions is None or len(predictions) == 0:
        st.error("No predictions found. Run predict_2026.py first.")
    else:
        _h2h_players = sorted(predictions['Player_Name'].tolist())
        _h2h_proj    = load_season_projection()
        _h2h_odds    = load_best_odds()

        _h2h_def1 = predictions.iloc[0]['Player_Name'] if len(predictions) > 0 else _h2h_players[0]
        _h2h_def2 = predictions.iloc[1]['Player_Name'] if len(predictions) > 1 else _h2h_players[1]

        # ── Player selectors ─────────────────────────────────
        _h2h_c1, _h2h_vs, _h2h_c2 = st.columns([5, 1, 5])
        with _h2h_c1:
            _ha = st.selectbox("Player A", _h2h_players,
                               index=_h2h_players.index(_h2h_def1), key="h2h_a")
        with _h2h_vs:
            st.markdown(
                '<div style="display:flex;align-items:center;justify-content:center;height:100%;'
                'padding-top:28px;font-size:28px;font-weight:900;color:var(--muted);letter-spacing:2px">VS</div>',
                unsafe_allow_html=True,
            )
        with _h2h_c2:
            _hb = st.selectbox("Player B", _h2h_players,
                               index=_h2h_players.index(_h2h_def2), key="h2h_b")

        if _ha == _hb:
            st.warning("Select two different players to compare.")
        else:
            # ── Gather data for each player ───────────────────
            def _h2h_data(name):
                row = predictions[predictions['Player_Name'] == name]
                if row.empty:
                    return None
                r = row.iloc[0]
                d = {
                    'name':  name,
                    'team':  r['Team'],
                    'exp':   round(float(r['Exp_Total_Votes']), 1),
                    'floor': None, 'ceiling': None,
                    'odds':  None, 'mkt_raw': None,
                }
                if _h2h_proj is not None and 'Floor_Projection' in _h2h_proj.columns:
                    pr = _h2h_proj[_h2h_proj['Player'] == name]
                    if not pr.empty:
                        d['floor']   = round(float(pr.iloc[0]['Floor_Projection']), 1)
                        d['ceiling'] = round(float(pr.iloc[0]['Ceiling_Projection']), 1)
                if _h2h_odds is not None and len(_h2h_odds) > 0:
                    ow = _h2h_odds[_h2h_odds['player'] == name]
                    if not ow.empty:
                        v = ow.iloc[0]['best_odds']
                        d['odds'] = round(float(v), 1) if pd.notna(v) else None
                        v2 = ow.iloc[0]['implied_prob']
                        d['mkt_raw'] = round(float(v2), 1) if pd.notna(v2) else None
                return d

            _da = _h2h_data(_ha)
            _db = _h2h_data(_hb)

            if _da is None or _db is None:
                st.error("Could not find data for one or both players.")
            else:
                # ── Model probability ─────────────────────────
                _total_exp = _da['exp'] + _db['exp']
                _ma = round(_da['exp'] / _total_exp * 100, 1) if _total_exp > 0 else 50.0
                _mb = round(100.0 - _ma, 1)

                # ── Market implied probability (normalised) ───
                _has_mkt = _da['mkt_raw'] is not None and _db['mkt_raw'] is not None
                if _has_mkt:
                    _mkt_sum = _da['mkt_raw'] + _db['mkt_raw']
                    _mkta = round(_da['mkt_raw'] / _mkt_sum * 100, 1) if _mkt_sum > 0 else 50.0
                    _mktb = round(100.0 - _mkta, 1)
                else:
                    _mkta = _mktb = None

                # ── Edge ─────────────────────────────────────
                _edge_a = round(_ma - _mkta, 1) if _has_mkt else None

                # ── Player summary cards ──────────────────────
                st.markdown('<div class="section-header">Model Probability</div>', unsafe_allow_html=True)

                _card_a, _card_b = st.columns(2)
                for _col, _d, _colour, _model_pct in [
                    (_card_a, _da, '#34d399', _ma),
                    (_card_b, _db, 'var(--muted)', _mb),
                ]:
                    with _col:
                        floor_s = f"{_d['floor']}" if _d['floor'] is not None else "—"
                        ceil_s  = f"{_d['ceiling']}" if _d['ceiling'] is not None else "—"
                        st.markdown(
                            f'<div style="background:var(--surface);border:1px solid var(--line);border-left:5px solid {_colour};'
                            f'border-radius:8px;padding:16px 20px;margin:4px 0;box-shadow:0 2px 8px rgba(0,0,0,0.24);">'
                            f'<div style="font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:600;letter-spacing:0.8px">{_d["team"]}</div>'
                            f'<div style="font-size:22px;font-weight:800;color:var(--text);margin:3px 0 12px 0;line-height:1.1">{_d["name"]}</div>'
                            f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px 14px;">'
                            f'<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Exp Votes</div>'
                            f'<div style="font-size:22px;font-weight:800;color:{_colour}">{_d["exp"]}</div></div>'
                            f'<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Floor</div>'
                            f'<div style="font-size:22px;font-weight:800;color:{_colour}">{floor_s}</div></div>'
                            f'<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Ceiling</div>'
                            f'<div style="font-size:22px;font-weight:800;color:{_colour}">{ceil_s}</div></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

                # ── Model split bar ───────────────────────────
                st.markdown(
                    f'<div style="margin:18px 0 6px 0;display:flex;border-radius:6px;overflow:hidden;height:44px;'
                    f'box-shadow:0 1px 4px rgba(0,0,0,0.10);">'
                    f'<div style="width:{_ma}%;background:#34d399;display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:#fff;font-weight:800;font-size:17px">{_ma}%</span></div>'
                    f'<div style="width:{_mb}%;background:var(--muted);display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:#fff;font-weight:800;font-size:17px">{_mb}%</span></div>'
                    f'</div>'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#6c6c6c;margin-bottom:4px;">'
                    f'<span>{_ha}</span><span>{_hb}</span></div>',
                    unsafe_allow_html=True,
                )

                # ── Market implied bar ────────────────────────
                st.markdown('<div class="section-header">Market Implied Probability</div>', unsafe_allow_html=True)
                if _has_mkt:
                    st.markdown(
                        f'<div style="margin:12px 0 6px 0;display:flex;border-radius:6px;overflow:hidden;height:44px;'
                        f'box-shadow:0 1px 4px rgba(0,0,0,0.10);">'
                        f'<div style="width:{_mkta}%;background:#5a7a9a;display:flex;align-items:center;justify-content:center;">'
                        f'<span style="color:#fff;font-weight:800;font-size:17px">{_mkta}%</span></div>'
                        f'<div style="width:{_mktb}%;background:#a07850;display:flex;align-items:center;justify-content:center;">'
                        f'<span style="color:#fff;font-weight:800;font-size:17px">{_mktb}%</span></div>'
                        f'</div>'
                        f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#6c6c6c;margin-bottom:4px;">'
                        f'<span>{_ha} &nbsp;${_da["odds"]}</span><span>{_hb} &nbsp;${_db["odds"]}</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    _missing = []
                    if _da['mkt_raw'] is None: _missing.append(_ha)
                    if _db['mkt_raw'] is None: _missing.append(_hb)
                    st.info(f"Market odds not available for: {', '.join(_missing)}")

                # ── Edge indicator ────────────────────────────
                st.markdown('<div class="section-header">Edge Indicator</div>', unsafe_allow_html=True)
                if _edge_a is not None:
                    _favoured = _ha if _ma >= _mb else _hb
                    _edge_abs = abs(_edge_a) if _ma >= _mb else abs(round(_mb - _mktb, 1))
                    _edge_val = round(_ma - _mkta, 1) if _ma >= _mb else round(_mb - _mktb, 1)
                    if _edge_val > 5:
                        _edge_bg    = '#eaf2e8'
                        _edge_bord  = '#34d399'
                        _edge_label = 'MODEL EDGE'
                        _edge_msg   = (f"The model gives <strong>{_favoured}</strong> a "
                                       f"<strong>+{_edge_abs}%</strong> edge over market implied probability. "
                                       f"Model: {_ma if _favoured == _ha else _mb}% &nbsp;·&nbsp; "
                                       f"Market: {_mkta if _favoured == _ha else _mktb}%")
                    elif _edge_val < -5:
                        _edge_bg    = '#f5ede3'
                        _edge_bord  = 'var(--muted)'
                        _edge_label = 'MARKET FAVOURS'
                        _mkt_fav    = _hb if _favoured == _ha else _ha
                        _edge_msg   = (f"Market prices <strong>{_mkt_fav}</strong> "
                                       f"<strong>{_edge_abs}%</strong> higher than the model suggests. "
                                       f"Model: {_ma if _favoured == _ha else _mb}% &nbsp;·&nbsp; "
                                       f"Market: {_mkta if _favoured == _ha else _mktb}%")
                    else:
                        _edge_bg    = 'var(--surface)'
                        _edge_bord  = '#7e8c99'
                        _edge_label = 'NEUTRAL'
                        _edge_msg   = (f"Model and market broadly agree — difference is only "
                                       f"<strong>{_edge_abs}%</strong>. No clear edge either way.")
                    st.markdown(
                        f'<div style="background:{_edge_bg};border:1px solid var(--line);border-left:6px solid {_edge_bord};'
                        f'border-radius:8px;padding:16px 22px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.24);">'
                        f'<div style="font-size:11px;font-weight:800;letter-spacing:2.5px;text-transform:uppercase;'
                        f'color:{_edge_bord};margin-bottom:6px">{_edge_label}</div>'
                        f'<div style="font-size:14px;color:var(--text);line-height:1.8">{_edge_msg}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("Market odds required for edge calculation.")

                # ── Round by round ────────────────────────────
                if game_df is not None:
                    st.markdown('<div class="section-header">Round by Round — Predicted Votes</div>', unsafe_allow_html=True)
                    _hg1 = game_df[game_df['Player_Name'] == _ha].sort_values('Round_num')
                    _hg2 = game_df[game_df['Player_Name'] == _hb].sort_values('Round_num')
                    if not _hg1.empty or not _hg2.empty:
                        _fig_h2h = go.Figure()
                        if not _hg1.empty:
                            _fig_h2h.add_trace(go.Scatter(
                                x=_hg1['Round_num'], y=_hg1['Exp_Votes'].round(1),
                                name=_ha, mode='lines+markers',
                                line=dict(color='#34d399', width=2.5),
                                marker=dict(size=7, color='#34d399'),
                                hovertemplate='<b>' + _ha + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        if not _hg2.empty:
                            _fig_h2h.add_trace(go.Scatter(
                                x=_hg2['Round_num'], y=_hg2['Exp_Votes'].round(1),
                                name=_hb, mode='lines+markers',
                                line=dict(color='#7e8c99', width=2.5),
                                marker=dict(size=7, color='#7e8c99'),
                                hovertemplate='<b>' + _hb + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        _fig_h2h.update_layout(
                            plot_bgcolor='#101a24', paper_bgcolor='#101a24', font_color='#e9eef3',
                            xaxis=dict(title='Round', dtick=1, gridcolor='#ede8df'),
                            yaxis=dict(title='Predicted Votes', gridcolor='#ede8df', rangemode='tozero'),
                            legend=dict(orientation='h', y=1.1, bgcolor='rgba(0,0,0,0)'),
                            margin=dict(t=20, b=40),
                            height=300,
                            hovermode='x unified',
                        )
                        _fig_h2h = apply_chart_theme(_fig_h2h)
                        st.plotly_chart(_fig_h2h, width='stretch', key="chart_021")

                # ── Verdict ───────────────────────────────────
                st.markdown('<div class="section-header">Verdict</div>', unsafe_allow_html=True)
                _vfav  = _ha if _ma >= _mb else _hb
                _vund  = _hb if _ma >= _mb else _ha
                _vfav_d = _da if _ma >= _mb else _db
                _vund_d = _db if _ma >= _mb else _da
                _vfav_pct = _ma if _ma >= _mb else _mb
                _vdiff_exp = round(abs(_da['exp'] - _db['exp']), 1)
                _vc2   = '#34d399' if _ma >= _mb else 'var(--muted)'

                _bet_line = ""
                if _edge_a is not None:
                    _v_edge_val = round(_ma - _mkta, 1) if _ma >= _mb else round(_mb - _mktb, 1)
                    _vfav_odds  = _da['odds'] if _ma >= _mb else _db['odds']
                    if _v_edge_val > 5 and _vfav_odds is not None:
                        _bet_line = (f" At ${_vfav_odds}, {_vfav.split()[0]} represents value — "
                                     f"model is {_v_edge_val}% more confident than the market.")
                    elif _v_edge_val < -5:
                        _bet_line = f" Market is pricing this matchup differently to the model — proceed with caution."
                    else:
                        _bet_line = f" Odds fairly reflect the model's assessment — no strong betting edge here."

                _floor_note = ""
                if _vfav_d['floor'] is not None and _vund_d['ceiling'] is not None:
                    if _vfav_d['floor'] > _vund_d['ceiling']:
                        _floor_note = (f" Even at floor, {_vfav.split()[0]} ({_vfav_d['floor']}) "
                                       f"exceeds {_vund.split()[0]}'s ceiling ({_vund_d['ceiling']}).")

                st.markdown(
                    f'<div style="background:var(--surface);border:1px solid var(--line);border-left:5px solid {_vc2};'
                    f'border-radius:8px;padding:20px 24px;margin:6px 0;box-shadow:0 2px 8px rgba(0,0,0,0.24);">'
                    f'<div style="font-size:14px;color:var(--text);line-height:2;">'
                    f'The model picks <strong style="color:{_vc2};font-size:16px">{_vfav}</strong> with a '
                    f'<strong>{_vfav_pct}%</strong> probability of outpolling {_vund} '
                    f'({_da["exp"]} vs {_db["exp"]} expected votes, gap of {_vdiff_exp}).'
                    f'{_bet_line}{_floor_note}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

# ══════════════════════════════════════════════════════════════
# LIVE TRACKER
# ════════════════════════════════════════════════════════════
def _assemble_live_tracker(lt, game_df, watchlist):
    """Assemble every value the Live Tracker renders from, off (a) live AFL vote
    data, (b) the model's per-round Exp_Votes / Poll_Prob, and (c) the persisted
    watchlist. Rounds are AFL display numbering (0 = Opening Round); the model's
    Round_num is AFLTables numbering, so display = Round_num - 1.

    Dicts are keyed by normalise_name(player) throughout. Returns:
      totals, prev_totals, round_votes, model_to_date, model_remaining,
      projection, delta, team, name, model_pollers (display_round -> {norm names}),
      watch_next (next-round watchlist chips), recon (hit / blanked / bolter).
    """
    df = lt.get("df", pd.DataFrame())
    last_round = int(lt.get("last_round", 0) or 0)
    asm = {
        "last_round": last_round, "next_round": last_round + 1,
        "totals": {}, "prev_totals": {}, "round_votes": {},
        "model_to_date": {}, "model_remaining": {}, "projection": {}, "delta": {},
        "team": {}, "name": {}, "model_pollers": {},
        "watch_next": [], "recon": {"hit": [], "blanked": [], "bolter": []},
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
            for _, r in game_df.iterrows():
                try:
                    dr = int(r["Round_num"]) - 1          # AFLTables -> display round
                    ev = float(r["Exp_Votes"])
                except (TypeError, ValueError):
                    continue
                if pd.isna(ev):
                    continue
                nn = normalise_name(r[pcol])
                if dr <= last_round:                       # counted (incl. OR) -> pace
                    asm["model_to_date"][nn] = asm["model_to_date"].get(nn, 0.0) + ev
                elif dr <= 24:                             # future rounds -> remaining
                    asm["model_remaining"][nn] = asm["model_remaining"].get(nn, 0.0) + ev
            # projected pollers = top-3 Poll_Prob within each game (the project's
            # established per-game convention; matches the votes-feed marker set)
            gkeys = [c for c in ("Round_num", "Home.team", "Away.team") if c in game_df.columns]
            grpkeys = gkeys if len(gkeys) > 1 else ["Round_num"]
            for gk, grp in game_df.groupby(grpkeys):
                rn = int(gk[0]) if isinstance(gk, tuple) else int(gk)
                names = {normalise_name(n) for n in grp.nlargest(3, "Poll_Prob")[pcol]}
                asm["model_pollers"].setdefault(rn - 1, set()).update(names)

    # ── projection + vs-model delta (apples-to-apples through last_round) ──────
    for nn, tot in asm["totals"].items():
        asm["projection"][nn] = tot + asm["model_remaining"].get(nn, 0.0)
        asm["delta"][nn] = tot - asm["model_to_date"].get(nn, 0.0)

    # ── watchlist: next-round card + last-round reconciliation ────────────────
    def _rounds_of(s):
        out = set()
        for t in str(s).split(","):
            t = t.strip()
            if t.lstrip("-").isdigit():
                out.add(int(t))
        return out

    next_pollers = asm["model_pollers"].get(last_round + 1, set())
    watched_next, watched_last = set(), set()
    if watchlist is not None and not watchlist.empty:
        for _, w in watchlist.iterrows():
            if bool(w.get("Settled", False)):
                continue
            wn = normalise_name(w.get("Player", ""))
            rounds = _rounds_of(w.get("My_Rounds", ""))
            if last_round < 24 and (last_round + 1) in rounds:
                watched_next.add(wn)
                asm["watch_next"].append({
                    "name": w.get("Player", ""), "team": w.get("Team", ""),
                    "badge": "both" if wn in next_pollers else "you",
                })
            if last_round > 0 and last_round in rounds:
                watched_last.add(wn)
                polled = asm["round_votes"].get(wn, {}).get(last_round, 0)
                rec = {"name": w.get("Player", ""), "team": w.get("Team", ""), "votes": polled}
                asm["recon"]["hit" if polled >= 1 else "blanked"].append(rec)

    # model-only projected pollers for the next round (suggestions you're not on)
    if last_round < 24:
        for nn in next_pollers:
            if nn not in watched_next:
                asm["watch_next"].append({
                    "name": asm["name"].get(nn, nn), "team": asm["team"].get(nn, ""),
                    "badge": "model",
                })

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

    import streamlit.components.v1 as _stc
    _lt_auto = False  # set in the utility line below; init so refresh guard is safe

    # ── 1. Header (no box) — the LIVE pill pulses (@keyframes), so it is
    #    rendered through a components.html iframe (Streamlit strips keyframes
    #    from st.markdown). ─────────────────────────────────────
    _pill_txt = "LIVE" if _lt_live else "OFF-SEASON"
    _pill_col = "#34d399" if _lt_live else "#7e8c99"
    _hdr_html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&family=IBM+Plex+Mono:wght@600;800&display=swap" rel="stylesheet">
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
    _stc.html(_hdr_html, height=54)

    if _lt_err:
        st.error(f"Could not fetch AFL tracker data: {_lt_err}")
        if st.button("Retry", key="lt_retry"):
            st.cache_data.clear()
            st.rerun()
    elif not _lt_live:
        # Off-season friendly message + still show AFL predictor data if available
        st.info(
            "Count night hasn't started yet — showing AFL's own Brownlow predictor data "
            "for the current season. This page will update automatically on count night."
        )
        if _lt_df.empty:
            st.stop()
    else:
        pass  # live — fall through to content

    if not _lt_df.empty:
        _leader = _lt_df.iloc[0]
        _leader_total = int(_leader["Total_Votes"])
        _second_total = int(_lt_df.iloc[1]["Total_Votes"]) if len(_lt_df) > 1 else 0
        _margin = _leader_total - _second_total

        # Single assembly off live data + model per-round Exp_Votes/Poll_Prob +
        # the persisted watchlist. Everything below renders from _asm.
        _asm = _assemble_live_tracker(_lt, load_game(2026), betting_hub._load_watchlist())
        _leader_nn = normalise_name(_leader["Player"])
        _leader_pace = _asm["delta"].get(_leader_nn)

        # ── 2. Count-progress bar (replaces the four stat cards) ──
        _rounds_total = 24
        _n_counted = max(0, min(int(_lt_last), _rounds_total))
        _pct = _n_counted / _rounds_total * 100
        st.markdown(
            f'<div style="margin:12px 0 8px">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#7e8c99;'
            f'font-family:\'IBM Plex Mono\',monospace;margin-bottom:5px">'
            f'<span style="text-transform:uppercase;letter-spacing:.12em">Count progress</span>'
            f'<span>Round {_n_counted} of {_rounds_total} counted</span></div>'
            f'<div style="height:4px;border-radius:2px;background:rgba(140,165,185,.14)">'
            f'<div style="height:4px;border-radius:2px;width:{_pct:.1f}%;background:#34d399"></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # ── 3. Race hero (replaces the rest of the cards) ─────
        _chasers = [(_lt_df.iloc[_i]["Player"], int(_lt_df.iloc[_i]["Total_Votes"]))
                    for _i in (1, 2) if len(_lt_df) > _i]
        _chaser_line = '  ·  '.join(f'{_n} {_v}' for _n, _v in _chasers) or '—'
        _pace_html = ''
        if _leader_pace is not None:
            _pc = '#34d399' if _leader_pace >= 0 else '#f87171'
            _ps = f'+{_leader_pace:.1f}' if _leader_pace >= 0 else f'−{abs(_leader_pace):.1f}'
            _pace_html = (f' &nbsp;·&nbsp; <span style="color:{_pc};font-weight:700">'
                          f'{_ps} vs model pace</span>')
        st.markdown(
            f'<div style="display:flex;align-items:flex-end;justify-content:space-between;'
            f'gap:24px;flex-wrap:wrap;margin:6px 0 2px">'
            f'<div><div style="font-family:\'Archivo\',sans-serif;font-size:40px;font-weight:800;'
            f'color:#e9eef3;line-height:1.02">{_leader["Player"]}</div>'
            f'<div style="font-size:13px;color:#7e8c99;margin-top:5px">{_leader["Team"]}</div></div>'
            f'<div style="display:flex;gap:38px">'
            f'<div style="text-align:right"><div style="font-size:10px;font-weight:700;'
            f'letter-spacing:1.5px;text-transform:uppercase;color:#7e8c99">Votes</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:42px;font-weight:600;'
            f'color:#34d399;line-height:1">{_leader_total}</div></div>'
            f'<div style="text-align:right"><div style="font-size:10px;font-weight:700;'
            f'letter-spacing:1.5px;text-transform:uppercase;color:#7e8c99">Lead</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:42px;font-weight:600;'
            f'color:#e9eef3;line-height:1">+{_margin}</div></div>'
            f'</div></div>'
            f'<div style="font-size:12px;color:#7e8c99;margin:2px 0 12px">Chasing &nbsp;{_chaser_line}{_pace_html}</div>',
            unsafe_allow_html=True,
        )

        # ── 4. Utility line: auto-refresh, last-fetched, source link ──
        _ua, _ub = st.columns([1.25, 4])
        with _ua:
            _lt_auto = st.checkbox("Auto-refresh 60s", value=False, key="lt_auto_refresh")
        with _ub:
            st.markdown(
                f'<div style="font-size:11px;color:#7e8c99;margin-top:9px;'
                f'font-family:\'IBM Plex Mono\',monospace">'
                f'Last fetched {_time.strftime("%H:%M:%S")} &nbsp;·&nbsp; '
                f'{"Live count" if _count_night else "Prediction mode"} &nbsp;·&nbsp; '
                f'<a href="https://www.afl.com.au/brownlow-medal/live-tracker" target="_blank" '
                f'style="color:#34d399;text-decoration:none">AFL.com.au ↗</a></div>',
                unsafe_allow_html=True,
            )

        # ── Watchlist card — "Watching · Round {next}" ──────────────────────
        # Persisted watchlist targets for the next round, each badged against the
        # model's projected pollers for that round (both / you / model). Hidden
        # once the season is complete (last_round == 24).
        if _asm["last_round"] < 24:
            _nextr = _asm["next_round"]
            _badge_col = {'both': '#f0b429', 'model': '#34d399', 'you': '#4a90c4'}
            _picks = [_w for _w in _asm["watch_next"] if _w["badge"] in ('both', 'you')]
            _model_only = sorted(
                (_w for _w in _asm["watch_next"] if _w["badge"] == 'model'),
                key=lambda _w: -_asm["projection"].get(normalise_name(_w["name"]), 0.0),
            )[:6]
            _chips_src = _picks + _model_only
            if _chips_src:
                _chips = ''
                for _w in _chips_src:
                    _bc = _badge_col.get(_w["badge"], '#7e8c99')
                    _chips += (
                        f'<span style="display:inline-flex;align-items:center;gap:7px;'
                        f'background:rgba(140,165,185,.08);border:1px solid rgba(140,165,185,.16);'
                        f'border-radius:999px;padding:6px 12px;margin:0 8px 8px 0">'
                        f'<span style="width:8px;height:8px;border-radius:50%;background:{_bc}"></span>'
                        f'<span style="font-size:13px;color:#e9eef3">{_w["name"]}</span>'
                        f'<span style="font-size:11px;color:#7e8c99">{_w["team"]}</span></span>'
                    )
                _chips_body = _chips
            else:
                _chips_body = ('<div style="font-size:13px;color:#7e8c99;padding:4px 0">'
                               f'No targets or projected pollers for Round {_nextr}.</div>')
            _wl_legend = (
                '<div style="display:flex;gap:16px;font-size:11px;color:#7e8c99;margin-top:4px;'
                'font-family:\'IBM Plex Mono\',monospace">'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                'background:#f0b429;vertical-align:middle;margin-right:5px"></span>you + model</span>'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                'background:#4a90c4;vertical-align:middle;margin-right:5px"></span>you</span>'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                'background:#34d399;vertical-align:middle;margin-right:5px"></span>model</span></div>'
            )
            st.markdown(
                f'<div style="background:rgba(140,165,185,.05);border:1px solid rgba(140,165,185,.14);'
                f'border-radius:12px;padding:16px 18px;margin:14px 0 6px">'
                f'<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
                f'color:#7e8c99;margin-bottom:12px">Watching '
                f'<span style="color:#34d399">· Round {_nextr}</span></div>'
                f'<div>{_chips_body}</div>{_wl_legend}</div>',
                unsafe_allow_html=True,
            )

        # Previous-round standings for movement arrows — derived from each
        # player's per-round history (Round_Votes). Omitted if no history.
        _prev_rank = {}
        if int(_lt_last) > 0:
            _prev_tot, _have_hist = {}, False
            for _, _r in _lt_df.iterrows():
                _rv = _r.get('Round_Votes', {})
                if isinstance(_rv, dict) and _rv:
                    _have_hist = True
                    _prev_tot[_r['Player']] = sum(int(_p) for _rd, _p in _rv.items()
                                                  if int(_rd) < int(_lt_last))
                else:
                    _prev_tot[_r['Player']] = 0
            if _have_hist:
                _order = sorted(_prev_tot, key=lambda _p: -_prev_tot[_p])
                _prev_rank = {_p: _i + 1 for _i, _p in enumerate(_order)}

        # Structured vote drops per round (rebuilt from Round_Votes).
        _drops_by_round = {}
        for _, _r in _lt_df.iterrows():
            _rv = _r.get('Round_Votes', {})
            if isinstance(_rv, dict):
                for _rd, _pts in _rv.items():
                    if _pts:
                        _drops_by_round.setdefault(int(_rd), []).append(
                            (_r['Player'], _r['Team'], int(_pts)))

        # Per-game projected pollers (Cha Ching, the only per-game source) =
        # top-3 Poll_Prob within each game. Keyed by AFL round (= game Round_num
        # − 1, per the project's round-offset convention). None ⇒ unavailable.
        _proj_pollers = {}
        _lt_game = load_game(2026)
        if _lt_game is not None and {'Poll_Prob', 'Round_num'} <= set(_lt_game.columns):
            _gpcol = next((_c for _c in ('Player', 'Player_Name') if _c in _lt_game.columns), None)
            if _gpcol:
                _gkeys = [_c for _c in ('Round_num', 'Home.team', 'Away.team') if _c in _lt_game.columns]
                _grpkeys = _gkeys if len(_gkeys) > 1 else ['Round_num']
                for _gk, _grp in _lt_game.groupby(_grpkeys):
                    _rn = int(_gk[0]) if isinstance(_gk, tuple) else int(_gk)
                    _names = {normalise_name(_n) for _n in _grp.nlargest(3, 'Poll_Prob')[_gpcol]}
                    _proj_pollers.setdefault(_rn - 1, set()).update(_names)

        # ── 5. Two-column layout ──────────────────────────────
        _lb_col, _feed_col = st.columns([3, 2])

        # ── 6. Running leaderboard — top 10, actual vs model ──
        with _lb_col:
            st.markdown(
                '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
                'color:#7e8c99;margin:2px 0 8px">Running leaderboard '
                '<span style="font-weight:400;letter-spacing:0;text-transform:none">— top 10, actual vs model</span></div>'
                '<div style="display:flex;gap:18px;font-size:11px;color:#7e8c99;margin:0 0 10px;'
                'font-family:\'IBM Plex Mono\',monospace">'
                '<span><span style="display:inline-block;width:16px;height:5px;border-radius:3px;'
                'background:#34d399;vertical-align:middle;margin-right:5px"></span>actual votes</span>'
                '<span><span style="display:inline-block;width:2px;height:11px;background:#f0b429;'
                'vertical-align:middle;margin-right:6px"></span>model projection</span>'
                '</div>',
                unsafe_allow_html=True,
            )

            _lt_show = _lt_df[_lt_df["Total_Votes"] > 0].head(10)
            if _lt_show.empty:
                _lt_show = _lt_df.head(10)

            # Shared bullet scale spans both actual votes and the model projection.
            _lb_vals = []
            for _, _r in _lt_show.iterrows():
                _a = int(_r["Total_Votes"])
                _lb_vals.append(_a)
                _lb_vals.append(_asm["projection"].get(normalise_name(_r["Player"]), _a))
            _lb_max = max(_lb_vals + [1])

            def _lbx(v):
                return max(0.0, min(100.0, v / _lb_max * 100.0))

            _rows_html = ''
            for _i, (_, _row) in enumerate(_lt_show.iterrows()):
                _nm, _tm = _row["Player"], _row["Team"]
                _actual = int(_row["Total_Votes"])
                _rank = int(_row["Rank"])
                _nn = normalise_name(_nm)
                _proj = _asm["projection"].get(_nn, _actual)
                _d = _asm["delta"].get(_nn)

                # movement arrow (omitted when no prior standings)
                _arrow = ''
                if _prev_rank:
                    _pr = _prev_rank.get(_nm)
                    if _pr is not None and _pr != _rank:
                        _mv = _pr - _rank
                        if _mv > 0:
                            _arrow = f'<span style="color:#34d399;font-size:11px;margin-left:6px">▲{_mv}</span>'
                        else:
                            _arrow = f'<span style="color:#f87171;font-size:11px;margin-left:6px">▼{abs(_mv)}</span>'

                # vs-model delta chip (emerald ahead of pace, muted red behind)
                if _d is None:
                    _chip = '<span style="color:#7e8c99">—</span>'
                else:
                    _chipc = '#34d399' if _d >= 0.05 else ('#f87171' if _d <= -0.05 else '#7e8c99')
                    _ds = f'+{_d:.1f}' if _d >= 0 else f'−{abs(_d):.1f}'
                    _chip = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;'
                             f'color:{_chipc}">{_ds}</span>')

                # projection number (steel; the gold lives on the bar tick)
                _projcell = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;'
                             f'color:#9fb0bf">{_proj:.0f}</span>')

                # bullet: emerald actual fill + gold model-projection tick
                _bullet = (
                    f'<div style="position:relative;height:16px">'
                    f'<div style="position:absolute;top:50%;height:1px;width:100%;'
                    f'background:rgba(140,165,185,.14);transform:translateY(-50%)"></div>'
                    f'<div style="position:absolute;top:50%;height:5px;left:0;width:{_lbx(_actual):.1f}%;'
                    f'background:#34d399;border-radius:3px;transform:translateY(-50%)"></div>'
                    f'<div style="position:absolute;top:1px;height:14px;width:2px;left:{_lbx(_proj):.1f}%;'
                    f'background:#f0b429;transform:translateX(-1px)"></div>'
                    f'</div>'
                )

                _lead = (_i == 0)
                _nsz, _nw, _nc = ('17px', '800', '#34d399') if _lead else ('14px', '600', '#e9eef3')
                _vsz = '20px' if _lead else '15px'
                _rows_html += (
                    f'<div style="display:grid;grid-template-columns:24px 1.7fr 44px 50px 46px 2fr;'
                    f'align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(140,165,185,.14)">'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:#7e8c99;'
                    f'text-align:right">{_rank}</div>'
                    f'<div><span style="font-family:\'Archivo\',sans-serif;font-size:{_nsz};font-weight:{_nw};'
                    f'color:{_nc}">{_nm}</span>{_arrow}'
                    f'<div style="font-size:11px;color:#7e8c99">{_tm}</div></div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:{_vsz};font-weight:600;'
                    f'color:{_nc};text-align:right">{_actual}</div>'
                    f'<div style="text-align:right">{_chip}</div>'
                    f'<div style="text-align:right">{_projcell}</div>'
                    f'<div>{_bullet}</div>'
                    f'</div>'
                )
            st.markdown(f'<div>{_rows_html}</div>', unsafe_allow_html=True)

        # ── 7. Reconciliation + latest-votes feed ─────────────
        with _feed_col:
            # Reconciliation for the last counted round: bolters (polled, unwatched),
            # hits (watched & polled), blanks (watched & 0). Hidden before any count.
            _rl = _asm["last_round"]
            if _rl > 0:
                _rlab = 'Opening Round' if _rl == 0 else f'Round {_rl}'

                def _recon_group(title, items, color, icon, show_votes):
                    if not items:
                        _body = '<div style="font-size:12px;color:#7e8c99;padding:3px 0">—</div>'
                    else:
                        _body = ''
                        for _it in items[:6]:
                            _v = ''
                            if show_votes and _it.get("votes"):
                                _v = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                                      f'color:{color};margin-left:6px">{_it["votes"]}</span>')
                            _body += (f'<div style="font-size:12px;color:#e9eef3;padding:2px 0">'
                                      f'{_it["name"]}<span style="color:#7e8c99"> · {_it["team"]}</span>{_v}</div>')
                    return (f'<div style="margin-bottom:12px">'
                            f'<div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
                            f'color:{color};margin-bottom:4px">{icon} {title}</div>{_body}</div>')

                st.markdown(
                    '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
                    'color:#7e8c99;margin:2px 0 10px">Reconciliation '
                    f'<span style="font-weight:400;letter-spacing:0;text-transform:none">— {_rlab}</span></div>'
                    + _recon_group('Bolters', _asm["recon"]["bolter"], '#f0b429', '⚡', True)
                    + _recon_group('Hit', _asm["recon"]["hit"], '#34d399', '✓', True)
                    + _recon_group('Blanked', _asm["recon"]["blanked"], '#f87171', '✗', False),
                    unsafe_allow_html=True,
                )

            st.markdown(
                '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
                'color:#7e8c99;margin:2px 0 8px">Latest votes '
                '<span style="font-weight:400;letter-spacing:0;text-transform:none">— called vs surprise</span></div>',
                unsafe_allow_html=True,
            )
            _rounds_sorted = sorted(_drops_by_round.keys(), reverse=True)[:6]
            if not _rounds_sorted:
                st.markdown('<div style="color:#7e8c99;font-size:13px;padding:10px 0">'
                            'No votes announced yet.</div>', unsafe_allow_html=True)
            else:
                _feed_html = ''
                _newest_done = False
                for _ri, _rnum in enumerate(_rounds_sorted):
                    _drops = sorted(_drops_by_round[_rnum], key=lambda _x: -_x[2])
                    _rlabel = 'Opening Round' if _rnum == 0 else f'Round {_rnum}'
                    _proj_set = _proj_pollers.get(_rnum)  # None ⇒ unavailable
                    if _proj_set is not None:
                        _called = sum(1 for (_pn, _, _) in _drops if normalise_name(_pn) in _proj_set)
                        _tally = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;'
                                  f'color:#7e8c99">models called {_called} of {len(_drops)}</span>')
                    else:
                        _tally = ''
                    _feed_html += (
                        f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                        f'margin:{"14px" if _ri else "0"} 0 6px;padding-bottom:5px;'
                        f'border-bottom:1px solid rgba(140,165,185,.14)">'
                        f'<span style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;'
                        f'color:#e9eef3">{_rlabel}</span>{_tally}</div>'
                    )
                    for _di, (_pn, _pt, _pv) in enumerate(_drops):
                        if _proj_set is None:
                            _mark = '<span style="display:inline-block;width:14px"></span>'
                        elif normalise_name(_pn) in _proj_set:
                            _mark = '<span style="color:#34d399;width:14px;display:inline-block">✓</span>'
                        else:
                            _mark = '<span style="color:#f0b429;width:14px;display:inline-block">✗</span>'
                        if _pv == 3:
                            _pill = ('<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                                     'font-weight:700;background:#34d399;color:#0a1017;border-radius:4px;'
                                     'padding:1px 7px">3</span>')
                        elif _pv == 2:
                            _pill = ('<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                                     'font-weight:700;border:1px solid #34d399;color:#34d399;border-radius:4px;'
                                     'padding:1px 6px">2</span>')
                        else:
                            _pill = ('<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                                     'font-weight:700;border:1px solid #7e8c99;color:#7e8c99;border-radius:4px;'
                                     'padding:1px 6px">1</span>')
                        # Most-recent drop: static emerald glow dot (non-keyframe
                        # fallback — st.markdown strips @keyframes).
                        _pulse = ''
                        if not _newest_done and _ri == 0 and _di == 0:
                            _pulse = ('<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
                                      'background:#34d399;box-shadow:0 0 0 3px rgba(52,211,153,.25);'
                                      'margin-left:7px;vertical-align:middle"></span>')
                            _newest_done = True
                        _feed_html += (
                            f'<div style="display:grid;grid-template-columns:18px 1fr auto;align-items:center;'
                            f'gap:9px;padding:6px 0;border-bottom:1px solid rgba(140,165,185,.07)">'
                            f'{_mark}'
                            f'<div><span style="font-size:13px;color:#e9eef3">{_pn}</span>{_pulse}'
                            f'<div style="font-size:10px;color:#7e8c99">{_pt}</div></div>'
                            f'{_pill}</div>'
                        )
                st.markdown(_feed_html, unsafe_allow_html=True)

    # ── auto-refresh ─────────────────────────────────────────
    if _lt_auto:
        _time.sleep(60)
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

    _mc_tab1, _mc_tab2, _mc_tab3 = st.tabs(['2026 (Live)', 'Historical (2021–2025)', 'Insights'])

    with _mc_tab2:
        _mc_hist_path = 'data_2026/historical_model_comparison.csv'
        st.markdown(
            '<div class="section-header">Actual Brownlow Winners — Model Predictions (2021–2025)</div>',
            unsafe_allow_html=True,
        )
        if os.path.exists(_mc_hist_path):
            _mc_hist = pd.read_csv(_mc_hist_path)
            for _rc in ['CC_Rank', 'Wheelo_Rank', 'Betfair_Rank', 'ESPN_Rank']:
                if _rc in _mc_hist.columns:
                    _mc_hist[_rc] = pd.to_numeric(_mc_hist[_rc], errors='coerce').astype('Int64')
            _mc_hist_disp = _mc_hist.rename(columns={
                'Actual_Winner': 'Actual Winner',
                'CC_Rank': 'Cha Ching',
                'Wheelo_Rank': 'Wheelo',
                'Betfair_Rank': 'Betfair',
                'ESPN_Rank': 'ESPN',
            })
            _mc_hist_disp = _mc_hist_disp[['Season', 'Actual Winner', 'Cha Ching', 'Wheelo', 'Betfair', 'ESPN']]
            def _hist_rank_fmt(v):
                return '—' if pd.isna(v) else str(int(v))
            def _hist_style(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for col in ['Cha Ching', 'Wheelo', 'Betfair', 'ESPN']:
                    if col not in df.columns:
                        continue
                    styles[col] = df[col].apply(
                        lambda v: 'background-color:rgba(52,211,153,0.18);color:#34d399;font-weight:700'
                        if pd.notna(v) and int(v) <= 3
                        else ('background-color:rgba(240,180,41,0.13);color:#f0b429'
                              if pd.notna(v) and int(v) <= 8 else '')
                    )
                return styles
            _hist_rank_cols = [c for c in ['Cha Ching', 'Wheelo', 'Betfair', 'ESPN'] if c in _mc_hist_disp.columns]
            _hist_fmt = {c: _hist_rank_fmt for c in _hist_rank_cols}
            st.dataframe(
                _mc_hist_disp.style.apply(_hist_style, axis=None).format(_hist_fmt),
                hide_index=True, use_container_width=True,
            )
            st.caption(
                'Green = top-3 prediction  |  Yellow = top-8. '
                'Cha Ching ranks from backtest model. Wheelo ranks from wheeloratings.com PDFs. '
                'Betfair and ESPN ranks sourced manually from archived articles.'
            )
        else:
            st.info('Historical comparison data not available.')

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

        # 1. Cha Ching
        _mc_cc_df = pd.DataFrame()
        _mc_cc_path = "predictions/season_2026.csv"
        if os.path.exists(_mc_cc_path):
            _mc_cc_raw = pd.read_csv(_mc_cc_path)
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

        # 2. AFL Predictor
        _mc_afl_result = fetch_live_brownlow_data()
        _mc_afl_raw = _mc_afl_result.get('df', pd.DataFrame())
        _mc_afl_df = pd.DataFrame()
        if not _mc_afl_raw.empty and 'Total_Votes' in _mc_afl_raw.columns:
            _mc_afl_s = _mc_afl_raw.sort_values('Total_Votes', ascending=False).reset_index(drop=True)
            _mc_afl_s['AFL_Rank'] = _mc_afl_s.index + 1
            _mc_afl_df = _mc_afl_s[['Player', 'Total_Votes', 'AFL_Rank']].rename(
                columns={'Total_Votes': 'AFL_Votes'})
            _mc_afl_df['Player'] = _mc_afl_df['Player'].str.title().str.strip()
        _mc_afl_has_votes = not _mc_afl_df.empty and _mc_afl_df['AFL_Votes'].max() > 0

        # 3. Betfair
        _mc_bf_df, _mc_bf_err = fetch_betfair_brownlow()
        if not _mc_bf_df.empty and 'Player' in _mc_bf_df.columns:
            _mc_bf_df['Player'] = _mc_bf_df['Player'].str.title().str.strip()

        # 4. Wheelo
        _mc_wh_df = pd.DataFrame()
        _mc_wh_path = "data_wheelo/wheelo_2026.csv"
        if os.path.exists(_mc_wh_path):
            _mc_wh_raw = pd.read_csv(_mc_wh_path)
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
            ('Cha Ching',     _mc_cc_df,   'CC_Rank',   _mc_cc_path,  'metric-card-primary'),
            ('AFL Predictor', _mc_afl_df,  'AFL_Rank',  '',           'metric-card'),
            ('Betfair',       _mc_bf_df,   'BF_Rank',   _BF_CSV,      'metric-card'),
            ('Wheelo',        _mc_wh_df,   'WH_Rank',   _mc_wh_path,  'metric-card'),
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
                    f'color:{_c};text-align:right;font-variant-numeric:tabular-nums">{_v}</div></div>')
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
            "<table style=\"width:100%;border-collapse:collapse;font-size:13px;margin-top:4px;"
            "font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums\">"
            + _mc_head + _mc_body + '</table>',
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
                '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:2px">'
                + _tbl_head + _tbl_body + '</table>',
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
            st.plotly_chart(fig_scatter, width='stretch', key='pred_actual_scatter_insights')
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
                                    key="feat_top15_insights")
                else:
                    _n_bars = 25
                    st.plotly_chart(_imp_bar_fig(_imp_sorted.head(_n_bars)), width='stretch',
                                    key="feat_all_insights")
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

# ── Global footer ────────────────────────────────────────────
if _page == 'Landing':
    st.markdown(
        '<div style="border-top:1px solid rgba(140,165,185,.14);margin-top:40px;padding:14px 0;'
        'color:#7e8c99;font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.18em;'
        'text-align:center;text-transform:uppercase;font-weight:500;">'
        f'MODEL V4.0 &nbsp;&nbsp;&middot;&nbsp;&nbsp; DATA {_TRAIN_MIN}–{_TRAIN_MAX} &nbsp;&nbsp;&middot;&nbsp;&nbsp; 93 FEATURES &nbsp;&nbsp;&middot;&nbsp;&nbsp; MAE 0.0904'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div style="border-top:1px solid var(--line);margin-top:40px;padding:14px 0;'
        'color:var(--muted);font-size:10px;letter-spacing:1.2px;text-align:center;'
        'text-transform:uppercase;font-weight:600;">'
        f'Model v4.0 &nbsp;&nbsp;·&nbsp;&nbsp; Data: {_TRAIN_MIN}–{_TRAIN_MAX} &nbsp;&nbsp;·&nbsp;&nbsp; 93 features &nbsp;&nbsp;·&nbsp;&nbsp; MAE 0.0904'
        '</div>',
        unsafe_allow_html=True,
    )