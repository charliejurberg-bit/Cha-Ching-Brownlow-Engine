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

st.set_page_config(page_title="Cha Ching", layout="wide", initial_sidebar_state="collapsed")

COLORS = {
    "bg_base":        "#0f1923",
    "bg_surface":     "#152533",
    "bg_elevated":    "#1e3a4a",
    "bg_subtle":      "#1a2d3d",
    "accent":         "#34d399",
    "accent_dim":     "#1a6b4a",
    "accent_glow":    "rgba(52,211,153,0.12)",
    "gold":           "#f0b429",
    "gold_dim":       "#5c420a",
    "red":            "#e05252",
    "red_dim":        "#5c1f1f",
    "blue":           "#4a90c4",
    "text_primary":   "#e8f0f8",
    "text_secondary": "#94a3b8",
    "text_muted":     "#4a5a6a",
    "border":         "#2a4a5a",
    "border_subtle":  "#1e3040",
}

def inject_global_css():
    st.markdown("""
<style>
iframe[title="streamlit_app"] { margin-top: -60px !important; }
</style>
""", unsafe_allow_html=True)
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@400;500;600;700&display=swap" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1923 !important;
    color: #e8f0f8;
    font-family: 'Sora', sans-serif;
}
[data-testid="stAppViewContainer"] > .main {
    background-color: #0f1923 !important;
}
[data-testid="block-container"],
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    max-width: 1200px;
}
[data-testid="stSidebar"] {
    background-color: #0d1720 !important;
    border-right: 1px solid #2a4a5a !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    color: #94a3b8;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 500;
    padding: 4px 0 2px 4px;
}
[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    color: #94a3b8 !important;
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
    background: #1e3a4a !important;
    color: #e8f0f8 !important;
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
    color: #e8f0f8 !important;
    letter-spacing: -0.02em;
}
h1 { font-size: 2rem !important; font-weight: 700 !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
h3 { font-size: 1rem !important; font-weight: 500 !important; }
p, li { color: #94a3b8; line-height: 1.6; }
code, [data-testid="stCode"] {
    font-family: 'DM Mono', monospace !important;
    background: #1e3a4a !important;
    color: #34d399 !important;
    border-radius: 4px;
}
[data-testid="stMetric"] {
    background: #152533 !important;
    border: 1px solid #2a4a5a !important;
    border-radius: 10px !important;
    padding: 16px !important;
}
[data-testid="stMetricLabel"] {
    color: #94a3b8 !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    color: #e8f0f8 !important;
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
    border: 1px solid #2a4a5a !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] th {
    background: #1e3a4a !important;
    color: #94a3b8 !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    border-bottom: 1px solid #2a4a5a !important;
}
[data-testid="stDataFrame"] td {
    background: #152533 !important;
    color: #e8f0f8 !important;
    border-bottom: 1px solid #1e3040 !important;
    font-size: 13px !important;
}
[data-testid="stDataFrame"] tr:hover td {
    background: #1e3a4a !important;
}
[data-testid="stTable"] {
    border: 1px solid #2a4a5a !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    width: 100% !important;
}
[data-testid="stTable"] thead th {
    background: #1e3a4a !important;
    color: #94a3b8 !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    border-bottom: 1px solid #2a4a5a !important;
    padding: 8px 10px !important;
}
[data-testid="stTable"] td {
    border-bottom: 1px solid #1e3040 !important;
    font-size: 13px !important;
    padding: 6px 10px !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #152533 !important;
    border: 1px solid #2a4a5a !important;
    border-radius: 8px !important;
    color: #e8f0f8 !important;
    font-family: 'Sora', sans-serif !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: #152533 !important;
    border: 1px solid #2a4a5a !important;
    border-radius: 8px !important;
    color: #e8f0f8 !important;
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
    border-bottom: 1px solid #2a4a5a !important;
    gap: 0 !important;
}
[data-testid="stTabs"] [role="tab"] {
    color: #94a3b8 !important;
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
    border-top: 1px solid #2a4a5a !important;
    margin: 1.5rem 0 !important;
}
.js-plotly-plot .plotly .bg { fill: #152533 !important; }
.js-plotly-plot { border-radius: 10px !important; overflow: hidden; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1923; }
::-webkit-scrollbar-thumb { background: #2a4a5a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #34d399; }
.section-header {
    font-family: 'Sora', sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4a5a6a;
    padding: 0 0 8px 0;
    border-bottom: 1px solid #2a4a5a;
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
  --cc-bg:      #0b1520;
  --cc-surface: #0f2035;
  --cc-nav:     #0d1c2b;
  --cc-border:  rgba(255,255,255,0.07);
  --cc-green:   #3ecfa0;
  --cc-gold:    #f5c542;
  --cc-primary: #2d5016;
  --cc-text:    #ffffff;
  --cc-muted:   rgba(255,255,255,0.35);
  --cc-hint:    rgba(255,255,255,0.25);
}
.stApp, [data-testid="stAppViewContainer"] {
  background: var(--cc-bg) !important;
}
/* ── Pill toggle buttons (global default) ── */
[data-testid="stBaseButton-primary"] {
  background: #2d5016 !important;
  color: #ffffff !important;
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
        polar=dict(
            bgcolor="#152533",
            radialaxis=dict(gridcolor="#1e3a4a", tickfont=dict(color="#94a3b8", size=10)),
            angularaxis=dict(gridcolor="#1e3a4a", tickfont=dict(color="#94a3b8", size=11)),
        ),
        margin=dict(l=16, r=16, t=40, b=16),
    )
    fig.update_traces(marker_line_width=0)
    return fig

def render_banner():
    _hub = st.session_state.get("active_hub", "brownlow")
    _sub = f"Through Round {max_season_rounds - 1}" if is_2026 else f"{selected_season} Season"
    _mode_label = "Brownlow Predictor" if _hub == "brownlow" else "Betting Hub"
    st.markdown(f"""
<div class="cha-ching-banner">
    <span class="cha-ching-deco" style="top:-12px;left:1%">&#9000;</span>
    <span class="cha-ching-deco" style="top:6px;left:18%;font-size:60px">&#9651;</span>
    <span class="cha-ching-deco" style="top:-8px;right:3%">&#9677;</span>
    <span class="cha-ching-deco" style="bottom:-20px;left:8%;font-size:70px">&#11042;</span>
    <span class="cha-ching-deco" style="top:2px;left:44%;font-size:54px">&#9733;</span>
    <span class="cha-ching-deco" style="bottom:-16px;right:9%;font-size:66px">&#9670;</span>
    <span class="cha-ching-deco" style="top:10px;right:22%;font-size:58px">&#9685;</span>
    <div class="cha-ching-title">CHA CHING</div>
    <div class="cha-ching-sub">{_mode_label} &nbsp;&middot;&nbsp; {_sub}</div>
</div>
""", unsafe_allow_html=True)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Structural ── */
    body { overflow-x: hidden !important; }
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

    /* ── Nav dropdown bar ── */
    .nav-anchor + div[data-testid="stHorizontalBlock"] {
        background: #0d1720 !important;
        padding: 2px 8px 6px 8px !important;
        border-bottom: 1px solid #2a4a5a !important;
        margin-bottom: 20px !important;
        border-radius: 0 0 8px 8px !important;
    }
    .nav-anchor + div[data-testid="stHorizontalBlock"] label {
        color: #4a5a6a !important;
        font-size: 10px !important;
        font-weight: 600 !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
    }

    /* ── CHA CHING banner ── */
    .cha-ching-banner {
        position: relative;
        left: 50%;
        width: 100vw;
        margin-left: -50vw;
        margin-top: -200px;
        overflow: hidden;
        background: linear-gradient(
            135deg,
            #0f1923 0%, #152533 25%, #1e3a4a 50%, #152533 75%, #0f1923 100%
        );
        background-size: 300% 300%;
        animation: bannerShift 10s ease infinite;
        height: 420px;
        padding: 200px 48px 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 0;
        border-bottom: 1px solid #2a4a5a;
        text-align: center;
    }
    .cha-ching-banner::before {
        content: '';
        position: absolute;
        inset: 0;
        background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg stroke='%23ffffff' stroke-width='0.5' opacity='0.05'%3E%3Cline x1='0' y1='60' x2='60' y2='0'/%3E%3Cline x1='30' y1='60' x2='60' y2='30'/%3E%3Cline x1='0' y1='30' x2='30' y2='0'/%3E%3C/g%3E%3C/svg%3E");
        pointer-events: none;
    }
    .cha-ching-deco {
        position: absolute;
        color: #ffffff;
        font-size: 80px;
        opacity: 0.05;
        pointer-events: none;
        user-select: none;
        line-height: 1;
    }
    /* Solid color — gradient text is banned */
    .cha-ching-title {
        position: relative;
        font-size: 108px;
        font-weight: 900;
        letter-spacing: -4px;
        margin: 0 0 18px 0;
        line-height: 1;
        color: #e8f0f8;
    }
    .cha-ching-sub {
        position: relative;
        color: #34d399;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 6px;
        text-transform: uppercase;
        margin: 0;
        opacity: 0.9;
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
        background: #152533;
        border: 1px solid #2a4a5a;
        border-radius: 8px;
        padding: 20px 24px;
        margin: 8px 0;
        overflow: hidden;
    }
    .sk-title, .sk-line, .sk-bar {
        background: linear-gradient(90deg, #1e3a4a 25%, #243a4a 50%, #1e3a4a 75%);
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
        background: #152533;
        border: 1px solid #2a4a5a;
        border-top: 2px solid #34d399;
        border-radius: 6px;
        padding: 16px 18px;
        margin: 0;
        min-height: 80px;
        cursor: pointer;
        transition: background 180ms ease-out;
    }
    .quick-link-card:hover { background: #1e3a4a; }
    .quick-link-title { color: #4a5a6a; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 6px 0; }
    .quick-link-desc  { color: #94a3b8; font-size: 12px; line-height: 1.55; margin: 0; }

    /* ── Metric cards ── */
    .metric-card {
        background: #152533;
        border: 1px solid #2a4a5a;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 6px 0;
        transition: background 160ms ease-out;
    }
    .metric-card:hover { background: #1e3a4a; }
    /* Accent-tinted full border; no side stripe */
    .metric-card-primary {
        background: #152533;
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
    .metric-sub      { color: #94a3b8; font-size: 12px; margin-top: 4px; line-height: 1.4; }

    /* ── Title bar ── */
    .title-bar {
        background: #152533;
        border: 1px solid #2a4a5a;
        padding: 18px 24px;
        border-radius: 6px;
        margin-bottom: 22px;
        animation: titleBarEnter 0.28s ease both;
    }
    .title-bar h1 { color: #e8f0f8; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; margin: 0 0 4px 0; line-height: 1.2; }
    .title-bar h2 { color: #e8f0f8; font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin: 0 0 4px 0; line-height: 1.2; }
    .title-bar p  { color: #94a3b8; font-size: 13px; font-weight: 500; margin: 0; line-height: 1.55; }

    /* ── Global header ── */
    .global-header {
        padding: 6px 0 12px 0;
        border-bottom: 1px solid #2a4a5a;
        margin-bottom: 0;
        display: flex;
        align-items: baseline;
        gap: 16px;
    }
    .global-header h1       { color: #e8f0f8; font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -0.4px; white-space: nowrap; }
    .global-header .subtitle{ color: #4a5a6a; font-size: 12px; margin: 0; font-weight: 500; }

    /* ── DNA cards ── */
    .dna-card {
        background: #152533;
        border: 1px solid #2a4a5a;
        border-radius: 8px;
        padding: 14px 18px;
        margin: 4px 0;
        transition: background 160ms ease-out;
    }
    .dna-card:hover { background: #1e3a4a; }
    .dna-label { color: #4a5a6a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 2px; }
    .dna-value { color: #34d399; font-size: 22px; font-weight: 700; line-height: 1.2; }
    .dna-sub   { color: #94a3b8; font-size: 12px; margin-top: 3px; line-height: 1.4; }

    /* ── Landing page ── */
    .land-ribbon {
        display: flex;
        background: #152533;
        border: 1px solid #2a4a5a;
        border-radius: 8px;
        margin: 12px 0 24px;
        overflow: hidden;
    }
    .land-stat {
        flex: 1;
        padding: 14px 20px;
        border-right: 1px solid #2a4a5a;
    }
    .land-stat:last-child { border-right: none; }
    .land-stat-label {
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #4a5a6a;
        margin-bottom: 3px;
    }
    .land-stat-value {
        font-size: 16px;
        font-weight: 700;
        color: #e8f0f8;
        font-family: 'DM Mono', monospace;
        letter-spacing: -0.3px;
    }
    .land-tile {
        background: #152533;
        border: 1px solid #2a4a5a;
        border-radius: 10px;
        padding: 28px 24px 24px;
        margin-bottom: 10px;
        transition: background 200ms ease-out;
    }
    .land-tile:hover { background: #1a2d3d; }
    .land-tile.bw { border-top: 3px solid #34d399; }
    .land-tile.bh { border-top: 3px solid #f0b429; }
    .land-tile-icon { font-size: 40px; line-height: 1; margin-bottom: 14px; }
    .land-tile-name { font-size: 20px; font-weight: 800; letter-spacing: -0.4px; margin-bottom: 8px; }
    .land-tile-name.bw { color: #34d399; }
    .land-tile-name.bh { color: #f0b429; }
    .land-tile-desc { color: #94a3b8; font-size: 13px; line-height: 1.6; margin-bottom: 16px; }
    .land-tile-preview {
        display: flex;
        align-items: baseline;
        gap: 6px;
        padding: 9px 12px;
        background: #1e3a4a;
        border-radius: 6px;
    }
    .land-tile-preview.gold { background: rgba(240,180,41,0.07); }
    .land-preview-label {
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #4a5a6a;
    }
    .land-preview-val {
        font-size: 14px;
        font-weight: 700;
        color: #e8f0f8;
        font-family: 'DM Mono', monospace;
    }

    /* ── Secondary button ── */
    [data-testid="stBaseButton-secondary"] {
        background-color: #1e3a4a !important;
        color: #94a3b8 !important;
        border: 1px solid #2a4a5a !important;
        font-weight: 600 !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    }
    [data-testid="stBaseButton-secondary"]:hover {
        background-color: #243a4a !important;
        border-color: #34d399 !important;
        color: #e8f0f8 !important;
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
        background: #1e3a4a;
        border: 1px solid #2a4a5a;
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
        border: 1px solid #2a4a5a;
        border-top: 2px solid #34d399;
        border-radius: 10px;
        padding: 20px 26px 18px 24px;
        background: #152533;
        margin: 44px 0 0 0;
        animation: gameCardEnter 0.32s cubic-bezier(0.22, 0.61, 0.36, 1) both;
        transition: background 160ms ease-out;
        position: relative;
        overflow: hidden;
    }
    .game-card:hover { background: #1e3a4a; }
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
    .score-pill.draw { background: #1e3a4a; border-color: #94a3b8; color: #94a3b8; }

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
    .rank-badge-1 { background: #f0b429; color: #0f1923; animation: rankGlow1 2.4s ease-in-out infinite; }
    .rank-badge-2 { background: #34d399; color: #0f1923; animation: rankGlow2 2.4s ease-in-out infinite; }
    .rank-badge-3 { background: #4a90c4; color: #0f1923; animation: rankGlow3 2.4s ease-in-out infinite; }
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
    @keyframes bannerShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
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

def _fix_team_names(df: pd.DataFrame) -> pd.DataFrame:
    for col in ('Team', 'Playing.for'):
        if col in df.columns:
            df[col] = df[col].replace('Footscray', 'Western Bulldogs')
    return df

@st.cache_data
def load_season(season):
    path = f"{PRED_DIR}/season_{season}.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

@st.cache_data
def load_game(season):
    path = f"{PRED_DIR}/game_level_{season}.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

@st.cache_data
def load_importance():
    path = f"{PRED_DIR}/feature_importance.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_backtest():
    path = f"{PRED_DIR}/backtest_results.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_season_projection():
    path = f"{PRED_DIR}/season_projection_2026.csv"
    return _fix_team_names(pd.read_csv(path)) if os.path.exists(path) else None

@st.cache_data
def load_all_historical():
    frames = []
    for season in sorted(AVAILABLE_SEASONS):
        path = f"{PRED_DIR}/game_level_{season}.csv"
        if os.path.exists(path):
            df = _fix_team_names(pd.read_csv(path))
            df['Season'] = season
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else None

@st.cache_data
def compute_player_efficiency(season):
    df = load_game(season)
    if df is None:
        return None
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
            return ' <span style="color:#94a3b8;font-size:11px">↑ new</span>'
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

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_betfair_brownlow():
    """Scrape Betfair Brownlow predictor. Tries plain requests first (fast); falls back to
    Playwright if the page needs JS rendering. Returns (df, error_str).
    Page has per-game tables: col 0 = player name, col 1 = vote value.
    Saves to data_2026/betfair_predictions.csv. Returns BF_Votes / BF_Rank columns."""
    _BF_URL = 'https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/'

    def _csv_to_internal(fb):
        return fb.rename(columns={'Total_Votes': 'BF_Votes', 'Rank': 'BF_Rank'}, errors='ignore')

    def _parse_html(html_text):
        from io import StringIO as _SIO
        _raw = pd.read_html(_SIO(html_text))
        if not _raw:
            raise ValueError('No tables found on page')
        _combined = pd.concat(_raw, ignore_index=True)
        _combined.columns = ['Player', 'Votes']
        _combined = _combined.dropna(subset=['Votes'])
        _combined['Votes'] = pd.to_numeric(_combined['Votes'], errors='coerce')
        _combined = _combined.dropna(subset=['Votes'])
        _combined['Player'] = _combined['Player'].astype(str).str.title().str.strip()
        # Rows without a space are match codes (e.g. 'Bl'), not player names
        _combined = _combined[_combined['Player'].str.contains(' ', na=False)]
        _agg = (
            _combined.groupby('Player', as_index=False)['Votes'].sum()
            .sort_values('Votes', ascending=False).reset_index(drop=True)
        )
        if _agg.empty:
            raise ValueError('No vote rows after filtering')
        _df = _agg.rename(columns={'Votes': 'Total_Votes'})
        _df['Rank'] = _df.index + 1
        return _df

    # ── Attempt 1: plain requests (fast, works when page is server-rendered) ──
    try:
        import requests as _req
        _resp = _req.get(
            _BF_URL,
            headers={
                'User-Agent': _PW_UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-AU,en;q=0.9',
                'Referer': 'https://www.betfair.com.au/',
            },
            timeout=20,
        )
        _resp.raise_for_status()
        _df = _parse_html(_resp.text)
        _save_with_backup(_df, _BF_CSV)
        return _csv_to_internal(_df), None
    except Exception:
        pass

    # ── Attempt 2: Playwright (handles JS-rendered content) ──────────────────
    try:
        _html = _pw_get_html(
            _BF_URL,
            wait_for=['table', 'article', 'main'],
            extra_sleep_ms=4000,
        )
        if not _html:
            raise ValueError('Playwright returned empty page')
        _df = _parse_html(_html)
        _save_with_backup(_df, _BF_CSV)
        return _csv_to_internal(_df), None
    except Exception as _exc:
        _fb = _csv_to_internal(_load_csv_fallback(_BF_CSV, 'Rank'))
        _msg = f"Scrape failed; using cached: {str(_exc)[:80]}"
        return (_fb, _msg) if not _fb.empty else (pd.DataFrame(), str(_exc))


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_espn_brownlow():
    """Scrape ESPN Brownlow per-game votes using Playwright (scroll to reveal lazy sections).
    Saves to data_2026/espn_predictions.csv. Returns (df, error_str).
    Internal DataFrame uses ESPN_Votes / ESPN_Rank columns.
    """
    _ESPN_URL = (
        "https://www.espn.com.au/afl/story/_/page/POINTSBET20242/"
        "afl-2026-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
    )
    _ESPN_DEBUG = "espn_debug.html"

    def _csv_to_internal(fb):
        return fb.rename(columns={'Total_Votes': 'ESPN_Votes', 'Rank': 'ESPN_Rank'}, errors='ignore')

    try:
        from bs4 import BeautifulSoup as _BS

        # scroll=True reveals the lazy-loaded per-game vote sections
        _html = _pw_get_html(
            _ESPN_URL,
            wait_for=['article', 'main', 'body'],
            scroll=True,
            extra_sleep_ms=6000,
        )
        if not _html:
            raise ValueError('Playwright returned empty page')

        # Save raw HTML on first run for structure inspection
        if not os.path.exists(_ESPN_DEBUG):
            with open(_ESPN_DEBUG, 'w', encoding='utf-8') as _f:
                _f.write(_html)
            print(f"[ESPN] Saved raw HTML to {_ESPN_DEBUG}")

        _soup = _BS(_html, "html.parser")
        _text = _soup.get_text(" ", strip=True)
        _votes: dict = {}  # player_name → cumulative votes across all games

        # Strategy A: per-game text pattern "N - Player Name (TEAM)"
        # e.g. "3 - Nick Daicos (COLL)", "2.5 - Marcus Bontempelli (WB)"
        _vote_re = re.compile(
            r"(\d+\.?\d*)\s*[-–—]\s*"
            r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)"
            r"\s*\([A-Z]{1,4}\)",
        )
        for _m in _vote_re.finditer(_text):
            try:
                _val = float(_m.group(1))
            except ValueError:
                continue
            if not (0 < _val <= 3):
                continue
            _name = _m.group(2).title().strip()
            _votes[_name] = _votes.get(_name, 0) + _val

        # Strategy B: pd.read_html table scan — detect per-round vote columns
        # (numeric, all non-null values in [0, 3]; pre-totalled Votes column exceeds 3)
        if not _votes:
            from io import StringIO as _SIO
            try:
                _raw_tables = pd.read_html(_SIO(_html))
            except Exception:
                _raw_tables = []
            for _tdf in _raw_tables:
                _tdf.columns = [str(c).strip().upper() for c in _tdf.columns]
                if 'PLAYER' not in _tdf.columns:
                    continue
                _vote_cols = []
                for _c in _tdf.columns:
                    if _c in ('PLAYER', 'TEAM', 'VOTES'):
                        continue
                    _num = pd.to_numeric(_tdf[_c], errors='coerce')
                    _valid = _num.dropna()
                    if len(_valid) > 0 and float(_valid.max()) <= 3.0 and float(_valid.min()) >= 0.0:
                        _vote_cols.append(_c)
                if not _vote_cols:
                    continue
                _tdf_v = _tdf[['PLAYER'] + _vote_cols].copy()
                for _c in _vote_cols:
                    _tdf_v[_c] = pd.to_numeric(_tdf_v[_c], errors='coerce').fillna(0)
                _tdf_v['_total'] = _tdf_v[_vote_cols].sum(axis=1)
                for _, _row in _tdf_v.iterrows():
                    _player = str(_row['PLAYER']).title().strip()
                    if not _player or _player in ('Nan', '') or _row['_total'] <= 0:
                        continue
                    _votes[_player] = _votes.get(_player, 0) + float(_row['_total'])

        if not _votes:
            _fb = _csv_to_internal(_load_csv_fallback(_ESPN_CSV, 'Rank'))
            return (_fb, "No vote data found on ESPN page; using cached CSV") if not _fb.empty \
                else (pd.DataFrame(), "No vote data found on ESPN page")

        _df = (
            pd.DataFrame([{"Player": _n, "Total_Votes": _v} for _n, _v in _votes.items()])
            .sort_values("Total_Votes", ascending=False)
            .reset_index(drop=True)
        )
        _df["Rank"] = _df.index + 1
        _save_with_backup(_df, _ESPN_CSV)

        print("\n[ESPN] Top 20:")
        for _, _r in _df.head(20).iterrows():
            print(f"  {int(_r['Rank']):<3} {_r['Player']:<30} {_r['Total_Votes']:.1f}")

        return _csv_to_internal(_df), None

    except Exception as _exc:
        _fb = _csv_to_internal(_load_csv_fallback(_ESPN_CSV, 'Rank'))
        _msg = f"Scrape failed; using cached: {str(_exc)[:80]}"
        return (_fb, _msg) if not _fb.empty else (pd.DataFrame(), str(_exc))


_TABLE_STYLES = [
    {"selector": "thead th", "props": [
        ("background-color", "#1e3a4a"), ("color", "#94a3b8"),
        ("font-size", "11px"), ("font-weight", "600"),
        ("letter-spacing", "0.08em"), ("text-transform", "uppercase"),
        ("border-bottom", "1px solid #2a4a5a"), ("padding", "8px 10px"),
    ]},
    {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#152533")]},
    {"selector": "tbody tr:nth-child(odd)",  "props": [("background-color", "#1a2d3d")]},
    {"selector": "tbody tr:hover",           "props": [("background-color", "#1e3a4a")]},
    {"selector": "td",                       "props": [
        ("border-bottom", "1px solid #1e3040"), ("padding", "6px 10px"), ("color", "#e8f0f8"),
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
    rendering — CSS selectors on td/th don't reach inside it; only Styler .apply() does."""
    out = pd.DataFrame('', index=df.index, columns=df.columns)
    for i in range(len(df)):
        out.iloc[i] = ('background-color: #152533; color: #e8f0f8;' if i % 2 == 0
                       else 'background-color: #1a2d3d; color: #e8f0f8;')
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
    colour = _TEAM_COLOURS.get(team, '#2a4a5a')
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
if 'selected_season' not in st.session_state:
    st.session_state.selected_season = AVAILABLE_SEASONS[0]
if st.session_state.selected_season not in AVAILABLE_SEASONS:
    st.session_state.selected_season = AVAILABLE_SEASONS[0]
selected_season = st.session_state.selected_season
is_2026 = (selected_season == 2026)

# ── Data loading ─────────────────────────────────────────────
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

render_banner()

_NAV_BROWNLOW = {
    "Overview": ["Home", "Leaderboard", "Live Tracker"],
    "Players":  ["Player Profile", "Player Comparison"],
    "Analysis": ["Stat Filter", "Coaches Votes", "Game Analysis", "Model Insights", "Model Comparison"],
    "Betting":  ["Betting Edge"],
}
_NAV_BETTING = {
    "BH Overview":  ["BH Dashboard", "Bet Tracker"],
    "BH Strategy":  ["Cha Ching Tips", "Trends & Analysis"],
}
_BH_PAGES = {'BH Dashboard', 'Bet Tracker', 'Cha Ching Tips', 'Trends & Analysis'}

def _nav_select(cat_key):
    val = st.session_state.get(cat_key)
    if val is not None:
        st.session_state.page = val

_hub  = st.session_state.get("active_hub", "brownlow")
_page = st.session_state.page

# ── Page list + icons for current hub ─────────────────────────
_PAGE_ICONS = {
    "Home": "🏠", "Leaderboard": "🏅", "Player Profile": "👤",
    "Player Comparison": "⚖️", "Stat Filter": "🔍", "Coaches Votes": "📋",
    "Game Analysis": "🎯", "Model Insights": "🧠", "Model Comparison": "📊",
    "Live Tracker": "📡", "Betting Edge": "💡",
    "BH Dashboard": "📈", "Bet Tracker": "📒",
    "Cha Ching Tips": "🎰", "Trends & Analysis": "📉",
}

if _hub == "brownlow":
    _snav_pages = [
        "Home", "Leaderboard", "Player Profile", "Player Comparison",
        "Stat Filter", "Coaches Votes", "Game Analysis",
        "Model Insights", "Model Comparison", "Live Tracker", "Betting Edge",
    ]
else:
    _snav_pages = ["BH Dashboard", "Bet Tracker", "Cha Ching Tips", "Trends & Analysis"]

# ── Build hub pill HTML ────────────────────────────────────────
# data-navhub attribute is read by the iframe click-handler below.
_hub_pill_html = ""
for _hkey, _hlabel in [("brownlow", "🏆 Brownlow"), ("betting", "💰 Betting Hub")]:
    _ha = _hub == _hkey
    _hp_style = (
        "background:#2d5016;color:#ffffff;font-weight:600;"
        if _ha else
        "background:transparent;color:rgba(255,255,255,0.45);font-weight:500;"
    )
    _hub_pill_html += (
        f'<span data-navhub="{_hkey}" style="cursor:pointer;white-space:nowrap;'
        f'padding:5px 16px;border-radius:6px;font-size:13px;border:none;{_hp_style}">'
        f'<span style="pointer-events:none">{_hlabel}</span></span>'
    )

# ── Build page strip HTML ──────────────────────────────────────
_page_strip_html = ""
for _sp in _snav_pages:
    _ap = _page == _sp
    _icon = _PAGE_ICONS.get(_sp, "·")
    _ps_style = (
        "color:#3ecfa0;border:0.5px solid rgba(62,207,160,0.25);background:rgba(62,207,160,0.07);font-weight:600;"
        if _ap else
        "color:rgba(255,255,255,0.4);border:0.5px solid transparent;background:transparent;font-weight:500;"
    )
    _page_strip_html += (
        f'<span data-navpage="{_sp}" style="cursor:pointer;white-space:nowrap;'
        f'padding:4px 10px;border-radius:5px;font-size:12px;'
        f'display:inline-flex;align-items:center;gap:5px;{_ps_style}">'
        f'<span style="font-size:11px;line-height:1;pointer-events:none">{_icon}</span>'
        f'<span style="pointer-events:none">{_sp}</span></span>'
    )

# ── Render combined nav (two rows) ─────────────────────────────
# CSS pushes the hidden text-input container off-screen.
st.markdown(f"""
<style>
[data-testid="stVerticalBlock"]:has(> :first-child .nav-inp-anchor) {{
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    z-index: -9999 !important;
}}
</style>
<div style="background:#0d1c2b;padding:7px 16px;
            position:relative;left:50%;width:100vw;margin-left:-50vw;
            border-bottom:0.5px solid rgba(255,255,255,0.06);
            display:flex;flex-wrap:nowrap;gap:4px;align-items:center;">
  {_hub_pill_html}
</div>
<div style="background:#0d1c2b;padding:6px 16px;
            position:relative;left:50%;width:100vw;margin-left:-50vw;
            border-bottom:0.5px solid rgba(255,255,255,0.08);
            display:flex;flex-wrap:nowrap;gap:3px;align-items:center;overflow-x:auto;">
  {_page_strip_html}
</div>
""", unsafe_allow_html=True)

# ── Navigation trigger: hidden text input ──────────────────────
# The iframe script below sets this input's value + dispatches events to
# trigger Streamlit's onChange, which reruns Python with the new nav command.
with st.container():
    st.markdown('<span class="nav-inp-anchor"></span>', unsafe_allow_html=True)
    _nav_cmd = st.text_input("nav", key="_nav_cmd", value="", label_visibility="collapsed")

if _nav_cmd:
    _cmd_parts = _nav_cmd.split(":", 1)
    if len(_cmd_parts) == 2:
        _cmd_type, _cmd_val = _cmd_parts
        if _cmd_type == "hub":
            st.session_state["active_hub"] = _cmd_val
            if _cmd_val == "betting" and st.session_state.page not in _BH_PAGES:
                st.session_state.page = "BH Dashboard"
            elif _cmd_val == "brownlow" and st.session_state.page in _BH_PAGES:
                st.session_state.page = "Home"
        elif _cmd_type == "page":
            st.session_state.page = _cmd_val
    st.session_state["_nav_cmd"] = ""
    st.rerun()

# ── iframe: nav click handler ──────────────────────────────────
# Runs in its own JS context (bypasses parent-page CSP / React event restrictions).
# Listens for clicks on [data-navhub] / [data-navpage] spans, then sets the hidden
# text input value using the native setter trick that Streamlit's React picks up.
_components.html("""
<script>
(function(){
  function setNav(cmd){
    var pdoc=window.parent.document;
    var a=pdoc.querySelector('.nav-inp-anchor');
    if(!a)return;
    var c=a.closest('[data-testid="stVerticalBlock"]');
    if(!c)return;
    var inp=c.querySelector('input[type="text"]');
    if(!inp)return;
    var setter=Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype,'value').set;
    setter.call(inp,cmd);
    inp.dispatchEvent(new window.parent.Event('input',{bubbles:true}));
    inp.dispatchEvent(new window.parent.KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
  }
  window.parent.document.addEventListener('click',function(e){
    var el=e.target;
    while(el&&el.tagName!=='BODY'){
      if(el.dataset&&el.dataset.navhub){setNav('hub:'+el.dataset.navhub);return;}
      if(el.dataset&&el.dataset.navpage){setNav('page:'+el.dataset.navpage);return;}
      el=el.parentElement;
    }
  });
})();
</script>
""", height=0, scrolling=False)

# ── Controls row (season + odds timestamp + run update) ──────
# Only show controls for Brownlow pages, not Betting Hub or Landing
_show_controls = _page not in _BH_PAGES and _page != 'Landing'

def _season_changed():
    st.session_state.selected_season = st.session_state._ctrl_season

_SEASON_PAGES = {
    'Leaderboard', 'Player Profile', 'Game Analysis', 'Model Insights', 'Betting Edge',
}

if _show_controls:
    _cc1, _cc2, _cc3, _cc4 = st.columns([2.5, 1.5, 0.7, 0.9])
    with _cc2:
        _odds_ctrl = load_best_odds()
        if _odds_ctrl is not None and 'scraped_at' in _odds_ctrl.columns:
            st.caption(f"Odds: {str(_odds_ctrl['scraped_at'].iloc[0])[:16]}")
    with _cc3:
        if _page in _SEASON_PAGES:
            st.selectbox(
                "Season", AVAILABLE_SEASONS,
                index=AVAILABLE_SEASONS.index(selected_season),
                key="_ctrl_season",
                on_change=_season_changed,
                label_visibility="collapsed",
            )
    with _cc4:
        if st.button("Run Update", type="primary", use_container_width=True):
            _skel = st.empty()
            _skel.markdown(
                '<div class="sk-card">'
                '<div class="sk-title"></div>'
                '<div class="sk-line wide"></div>'
                '<div class="sk-line med"></div>'
                '<div class="sk-line short"></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            _upd = subprocess.run([sys.executable, "update.py"],
                                  capture_output=True, text=True, timeout=300)
            _skel.empty()
            st.cache_data.clear()
            if _upd.returncode == 0:
                st.toast("Update complete!")
            else:
                st.toast("Finished with warnings.")
            if _upd.stdout:
                with st.expander("Output log"):
                    st.code(_upd.stdout[-2000:])

# ════════════════════════════════════════════════════════════
# LANDING PAGE
# ════════════════════════════════════════════════════════════
if _page == 'Landing':
    # Live context: compute leader from current season data
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

    # Betting P&L summary
    try:
        _land_bets = betting_hub._load_bets()
        _land_pl = float(_land_bets["profit_loss"].sum()) if not _land_bets.empty else None
        _land_n = len(_land_bets)
    except Exception:
        _land_pl = None
        _land_n = 0

    if _land_pl is not None:
        _pl_str = f"+${_land_pl:.2f}" if _land_pl >= 0 else f"-${abs(_land_pl):.2f}"
    else:
        _pl_str = "—"
    _pl_color = "#34d399" if (_land_pl or 0) >= 0 else "#e05252"

    # Context ribbon
    st.markdown(f"""
<div class="land-ribbon">
  <div class="land-stat">
    <div class="land-stat-label">Round</div>
    <div class="land-stat-value">{max_season_rounds}</div>
  </div>
  <div class="land-stat">
    <div class="land-stat-label">Current Leader</div>
    <div class="land-stat-value" style="color:#34d399">{_land_leader}</div>
  </div>
  <div class="land-stat">
    <div class="land-stat-label">Predicted Votes</div>
    <div class="land-stat-value">{_land_votes:.1f}</div>
  </div>
  <div class="land-stat">
    <div class="land-stat-label">Betting P&amp;L</div>
    <div class="land-stat-value" style="color:{_pl_color}">{_pl_str}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    _lc1, _lc2 = st.columns(2, gap="medium")
    with _lc1:
        st.markdown(f"""
<div class="land-tile bw">
  <div class="land-tile-icon">&#127942;</div>
  <div class="land-tile-name bw">Brownlow Medal</div>
  <div class="land-tile-desc">Live leaderboard, player profiles, model predictions, game-by-game analysis, and betting edge.</div>
  <div class="land-tile-preview">
    <span class="land-preview-label">Leader</span>
    <span class="land-preview-val">{_land_leader}</span>
    <span class="land-preview-label" style="margin-left:10px">Proj. votes</span>
    <span class="land-preview-val">{_land_votes:.1f}</span>
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("Leaderboard →", use_container_width=True, type="primary", key="land_bw"):
            st.session_state.page = 'Leaderboard'
            st.rerun()
    with _lc2:
        _bets_preview = f"{_land_n} bets &nbsp;&middot;&nbsp; {_pl_str}" if _land_n > 0 else "No bets logged yet"
        st.markdown(f"""
<div class="land-tile bh">
  <div class="land-tile-icon">&#128176;</div>
  <div class="land-tile-name bh">Betting Hub</div>
  <div class="land-tile-desc">Track bets, log P&amp;L, flag Cha Ching tips, analyse hit rates and ROI across markets.</div>
  <div class="land-tile-preview gold">
    <span class="land-preview-label">Season</span>
    <span class="land-preview-val">{_bets_preview}</span>
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("Open Betting Hub →", use_container_width=True, key="land_bh"):
            st.session_state.page = 'BH Dashboard'
            st.rerun()

# ════════════════════════════════════════════════════════════
# BETTING HUB pages
# ════════════════════════════════════════════════════════════
elif _page in _BH_PAGES:
    betting_hub.render_page(_page)

# ════════════════════════════════════════════════════════════
# HOME (Brownlow overview)
# ════════════════════════════════════════════════════════════
if _page == 'Home':
    SEASON = 2026
    CURRENT_ROUND = max_season_rounds

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

    leader_odds = "—"
    if odds_df is not None and not odds_df.empty and "player" in odds_df.columns:
        match = odds_df[odds_df["player"] == leader_name]
        if not match.empty:
            num_cols = odds_df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                leader_odds = f"${float(match.iloc[0][num_cols[0]]):.2f}"

    rounds_remaining = 23 - CURRENT_ROUND
    season_pct = int((CURRENT_ROUND / 23) * 100)

    st.markdown(f"""
<div style="padding:20px 0 12px;animation:fadeSlideUp 500ms cubic-bezier(0.23,1,0.32,1) both;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
    <div style="width:8px;height:8px;border-radius:50%;background:#34d399;
                animation:pulse 2s ease-in-out infinite;"></div>
    <span style="font-family:'Sora',sans-serif;font-size:11px;font-weight:500;
                 letter-spacing:0.1em;text-transform:uppercase;color:#34d399;">
      Live · Round {CURRENT_ROUND}
    </span>
  </div>
  <h1 style="font-family:'Sora',sans-serif;font-size:2.6rem;font-weight:700;
             color:#e8f0f8;letter-spacing:-0.03em;margin:0 0 8px;line-height:1.1;">
    Cha Ching
  </h1>
  <p style="color:#94a3b8;font-size:15px;margin:0;max-width:520px;line-height:1.6;">
    Brownlow Medal predictor · 2026 season · XGBoost v4.0 &nbsp;·&nbsp;
    <span style="color:#e8f0f8;font-weight:500;">MAE 0.09</span> &nbsp;·&nbsp;
    <span style="color:#e8f0f8;font-weight:500;">86% top-10 accuracy</span>
  </p>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="margin-bottom:16px;animation:fadeSlideUp 500ms 80ms cubic-bezier(0.23,1,0.32,1) both;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:11px;font-weight:500;letter-spacing:0.08em;
                 text-transform:uppercase;color:#4a5a6a;">Season progress</span>
    <span style="font-size:12px;color:#94a3b8;font-family:'DM Mono',monospace;">
      R{CURRENT_ROUND} of 23 &nbsp;·&nbsp; {rounds_remaining} rounds to go
    </span>
  </div>
  <div style="height:6px;background:#1e3a4a;border-radius:3px;overflow:hidden;">
    <div style="height:100%;width:{season_pct}%;background:#34d399;border-radius:3px;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:16px 0;">
  <div style="background:#0f2035; border:0.5px solid rgba(255,255,255,0.07); border-radius:10px; padding:14px;">
    <div style="font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:rgba(255,255,255,0.3); margin-bottom:8px;">Predicted winner</div>
    <div style="font-size:20px; font-weight:600; color:#f5c542;">{leader_name}</div>
    <div style="font-size:11px; color:rgba(255,255,255,0.3);">{leader_votes:.1f} pred. votes</div>
  </div>
  <div style="background:#0f2035; border:0.5px solid rgba(255,255,255,0.07); border-radius:10px; padding:14px;">
    <div style="font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:rgba(255,255,255,0.3); margin-bottom:8px;">Best odds</div>
    <div style="font-size:20px; font-weight:600; color:#3ecfa0;">{leader_odds}</div>
    <div style="font-size:11px; color:rgba(255,255,255,0.3);">{leader_name} to win</div>
  </div>
  <div style="background:#0f2035; border:0.5px solid rgba(255,255,255,0.07); border-radius:10px; padding:14px;">
    <div style="font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:rgba(255,255,255,0.3); margin-bottom:8px;">Model accuracy</div>
    <div style="font-size:20px; font-weight:600; color:#ffffff;">86%</div>
    <div style="font-size:11px; color:rgba(255,255,255,0.3);">top-10 · MAE 0.09</div>
  </div>
  <div style="background:#0f2035; border:0.5px solid rgba(255,255,255,0.07); border-radius:10px; padding:14px;">
    <div style="font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:rgba(255,255,255,0.3); margin-bottom:8px;">Round</div>
    <div style="font-size:20px; font-weight:600; color:#ffffff;">{CURRENT_ROUND}<span style="font-size:13px; color:rgba(255,255,255,0.3); font-weight:400"> /23</span></div>
    <div style="font-size:11px; color:rgba(255,255,255,0.3);">{rounds_remaining} rounds remaining</div>
  </div>
</div>
""", unsafe_allow_html=True)

    _home_left, _home_right = st.columns([3, 2])

    with _home_left:
        if not top5.empty:
            _top10_rows = []
            _top10_max = top5["Exp_Total_Votes"].max()
            for _rank, (_, _row) in enumerate(top5.iterrows()):
                _pct = int(_row["Exp_Total_Votes"] / _top10_max * 100) if _top10_max > 0 else 0
                _top10_rows.append(
                    f'<div style="display:flex;align-items:center;gap:10px;background:#0f2035;border:0.5px solid rgba(255,255,255,0.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;">'
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.25);width:16px;text-align:center;">{_rank+1}</div>'
                    f'<div style="font-size:13px;font-weight:500;color:#fff;flex:2;">{_row["Player_Name"]}</div>'
                    f'<div style="flex:3;height:4px;background:rgba(255,255,255,0.07);border-radius:100px;overflow:hidden;">'
                    f'<div style="height:4px;background:#2d5016;border-radius:100px;width:{_pct}%;"></div></div>'
                    f'<div style="font-size:13px;font-weight:500;color:#3ecfa0;width:36px;text-align:right;">{_row["Exp_Total_Votes"]:.1f}</div>'
                    f'</div>'
                )
            st.markdown(
                '<div style="margin-top:8px;">'
                '<div style="font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,0.25);margin-bottom:10px;">Top 10 predictions — 2026</div>'
                + "".join(_top10_rows)
                + '</div>',
                unsafe_allow_html=True,
            )

    with _home_right:
        _odds_has_data = (
            odds_df is not None
            and not odds_df.empty
            and "player" in odds_df.columns
            and "best_odds" in odds_df.columns
        )
        if _odds_has_data:
            _odds_top10 = odds_df.nsmallest(10, "best_odds")[["player", "best_odds", "best_bookie"]].copy()
            _odds_rows = []
            for _i, (_, _or) in enumerate(_odds_top10.iterrows()):
                _bookie = str(_or.get("best_bookie", "")) if pd.notna(_or.get("best_bookie")) else ""
                _odds_rows.append(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'background:#0f2035;border:0.5px solid rgba(255,255,255,0.06);border-radius:8px;'
                    f'padding:10px 12px;margin-bottom:6px;">'
                    f'<div style="display:flex;align-items:center;gap:10px;">'
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.25);width:16px;text-align:center;">{_i+1}</div>'
                    f'<div>'
                    f'<div style="font-size:13px;font-weight:500;color:#fff;">{_or["player"]}</div>'
                    f'<div style="font-size:10px;color:rgba(255,255,255,0.3);">{_bookie}</div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="font-size:14px;font-weight:600;color:#f5c542;">${float(_or["best_odds"]):.2f}</div>'
                    f'</div>'
                )
            st.markdown(
                '<div style="margin-top:8px;">'
                '<div style="font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,0.25);margin-bottom:10px;">Market odds — favourites</div>'
                + "".join(_odds_rows)
                + '</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    st.markdown("""
<div style="font-size:11px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;
            color:#4a5a6a;padding-bottom:10px;border-bottom:1px solid #2a4a5a;margin-bottom:14px;">
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
<div style="background:#152533;border:1px solid #2a4a5a;border-radius:10px;
            padding:14px 16px;
            animation:fadeSlideUp 400ms 380ms cubic-bezier(0.23,1,0.32,1) both;
            transition:background 180ms ease-out,border-color 180ms ease-out;"
     onmouseover="this.style.background='#1e3a4a';this.style.borderColor='{color}'"
     onmouseout="this.style.background='#152533';this.style.borderColor='#2a4a5a'">
  <div style="font-size:20px;margin-bottom:8px;">{icon}</div>
  <div style="font-size:13px;font-weight:600;color:#e8f0f8;margin-bottom:3px;
              font-family:'Sora',sans-serif;">{title}</div>
  <div style="font-size:11px;color:#4a5a6a;">{desc}</div>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# LEADERBOARD
# ════════════════════════════════════════════════════════════
if _page == 'Leaderboard':
    _lb_live_html = ' <span class="live-badge">LIVE</span>' if is_2026 else ""
    st.markdown(
        f'<div class="title-bar" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
        f'<div>'
        f'<div style="display:flex;align-items:center;gap:10px">'
        f'<h2 style="color:#e8f0f8;margin:0">{selected_season} Brownlow Leaderboard</h2>'
        f'{_lb_live_html}'
        f'</div>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">'
        f'{"Projected votes through current round" if is_2026 else "Model predicted vs actual results"}'
        f'</p></div></div>',
        unsafe_allow_html=True,
    )

    # Podium: #2 left, #1 centre (larger), #3 right
    top3 = predictions.head(3)
    col_left, col_center, col_right = st.columns([1, 1.3, 1])
    podium_order = [
        (col_left,   1, top3.iloc[1]),
        (col_center, 0, top3.iloc[0]),
        (col_right,  2, top3.iloc[2]),
    ]
    rank_labels = ['#1 Predicted', '#2 Predicted', '#3 Predicted']
    for col, idx, row in podium_order:
        actual_str = "TBC" if is_2026 else f"{int(row['Actual_Votes'])} actual"
        card_class = "metric-card-primary" if idx == 0 else "metric-card"
        value_class = "metric-value-lg" if idx == 0 else "metric-value"
        with col:
            st.markdown(
                f'<div class="{card_class}">'
                f'<div class="metric-label">{rank_labels[idx]}</div>'
                f'<div class="{value_class}">{row["Player_Name"]}</div>'
                f'<div class="metric-sub">{row["Team"]} &nbsp;|&nbsp; {row["Exp_Total_Votes"]:.1f} exp &nbsp;|&nbsp; {actual_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-header">Full Leaderboard</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1: search = st.text_input("Search player", "")
    with col2: show_n = st.selectbox("Show", [20, 50, 100, 200], index=0)

    display = predictions.copy()
    if search:
        display = display[display['Player_Name'].str.contains(search, case=False)]
    display = display.head(show_n).copy()
    display.insert(0, 'Rank', range(1, len(display) + 1))
    display['Poll %'] = (display['Avg_Poll_Prob'] * 100).round(1)
    display['Exp Votes'] = display['Exp_Total_Votes'].round(1)
    display['3-vote games'] = display['Exp_3vote_games'].round(1)

    if is_2026:
        _proj = load_season_projection()
        if _proj is not None and 'Floor_Projection' in _proj.columns:
            display = display.merge(
                _proj[['Player', 'Floor_Projection', 'Ceiling_Projection']],
                left_on='Player_Name', right_on='Player', how='left'
            ).drop(columns=['Player'], errors='ignore')
            display['Floor'] = display['Floor_Projection'].round(1)
            display['Ceiling'] = display['Ceiling_Projection'].round(1)
            has_floor_ceiling = True
        else:
            has_floor_ceiling = False

        _odds = load_best_odds()
        if _odds is not None and len(_odds) > 0:
            display = display.merge(
                _odds[['player', 'best_odds', 'implied_prob', 'best_bookie']],
                left_on='Player_Name', right_on='player', how='left'
            )
            display['Best Odds'] = display['best_odds'].apply(lambda x: f"${x:.1f}" if pd.notna(x) else "—")
            display['Mkt %'] = display['implied_prob'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "—")
            base = ['Rank', 'Player_Name', 'Team', 'Games', 'Exp Votes', 'Poll %', '3-vote games']
            fc = ['Floor', 'Ceiling'] if has_floor_ceiling else []
            cols_show = base[:5] + fc + base[5:] + ['Best Odds', 'Mkt %']
        else:
            base = ['Rank', 'Player_Name', 'Team', 'Games', 'Exp Votes', 'Poll %', '3-vote games']
            fc = ['Floor', 'Ceiling'] if has_floor_ceiling else []
            cols_show = base[:5] + fc + base[5:]
    else:
        display['Actual'] = display['Actual_Votes'].astype(int)
        display['Diff'] = (display['Exp Votes'] - display['Actual']).round(1)
        cols_show = ['Rank', 'Player_Name', 'Team', 'Games', 'Actual', 'Exp Votes', 'Diff', 'Poll %', '3-vote games']

    # ── Form guide (2026 only) ────────────────────────────────
    if is_2026:
        _fg = form_guide_dots(selected_season, n_rounds=3)
        if _fg:
            display['Form'] = display['Player_Name'].map(_fg).fillna('▫▫▫')
            _fg_idx = cols_show.index('Games') + 1 if 'Games' in cols_show else 3
            cols_show = cols_show[:_fg_idx] + ['Form'] + cols_show[_fg_idx:]

    _lb_disp = display[cols_show].rename(columns={'Player_Name': 'Player'})
    for col in _lb_disp.select_dtypes(include='float').columns:
        _lb_disp[col] = _lb_disp[col].round(1)
    st.dataframe(_style_leaderboard_table(_lb_disp), width='stretch', hide_index=True)
    if is_2026 and _fg:
        st.caption("Form: 🟢 predicted to poll (≥30% chance) · ⚫ not predicted · ▫ did not play — last 3 rounds")

    st.markdown(f'<div class="section-header">{"Projected — Top 20" if is_2026 else "Expected vs Actual — Top 20"}</div>', unsafe_allow_html=True)
    chart = predictions.head(20).copy()
    fig = go.Figure()
    if not is_2026:
        fig.add_trace(go.Bar(name='Actual', x=chart['Player_Name'], y=chart['Actual_Votes'],
                             marker_color='#adb5bd', opacity=0.7))
    fig.add_trace(go.Bar(name='Model Expected', x=chart['Player_Name'],
                         y=chart['Exp_Total_Votes'].round(1), marker_color='#34d399', opacity=0.9))
    fig = apply_chart_theme(fig)
    fig.update_layout(barmode='group', legend=dict(orientation='h', y=1.1),
                      xaxis_tickangle=-35, margin=dict(t=20, b=120))
    st.plotly_chart(fig, width='stretch', key="chart_002")

# ════════════════════════════════════════════════════════════
# PLAYER PROFILE
# ════════════════════════════════════════════════════════════
if _page == 'Player Profile':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Player Profile — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Round by round breakdown · vote probability · polling DNA</p></div>',
        unsafe_allow_html=True,
    )

    if game_df is None:
        st.error("No game-level data found.")
    else:
        efficiency = compute_player_efficiency(selected_season)
        players = sorted(predictions['Player_Name'].tolist())
        selected_player = st.selectbox("Select player", players, key="profile_player")

        _tab_prof, _tab_dna = st.tabs(["Profile", "DNA"])

        # ── Profile tab ───────────────────────────────────────
        with _tab_prof:
            player_games = game_df[game_df['Player_Name'] == selected_player].copy().sort_values('Round_num')
            pred_row = predictions[predictions['Player_Name'] == selected_player]

            if not pred_row.empty:
                row = pred_row.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Team</div><div class="metric-value" style="font-size:18px">{row["Team"]}</div></div>', unsafe_allow_html=True)
                with c2:
                    val = int(row["Actual_Votes"]) if not is_2026 else int(row["Games"])
                    lbl = "Actual Votes" if not is_2026 else "Games Played"
                    st.markdown(f'<div class="metric-card"><div class="metric-label">{lbl}</div><div class="metric-value">{val}</div></div>', unsafe_allow_html=True)
                with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">{"Model Expected" if not is_2026 else "Projected Total"}</div><div class="metric-value">{row["Exp_Total_Votes"]:.1f}</div></div>', unsafe_allow_html=True)
                with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Poll Prob</div><div class="metric-value">{row["Avg_Poll_Prob"] * 100:.1f}%</div></div>', unsafe_allow_html=True)

            if not player_games.empty:
                st.markdown('<div class="section-header">Round by Round — Votes and Poll Probability</div>', unsafe_allow_html=True)
                fig = make_subplots(specs=[[{"secondary_y": True}]])

                if not is_2026 and 'Brownlow.Votes' in player_games.columns:
                    colors = []
                    for v in player_games['Brownlow.Votes']:
                        if v == 3: colors.append('#94a3b8')
                        elif v == 2: colors.append('#34d399')
                        elif v == 1: colors.append('#6b7c3a')
                        else: colors.append('#ddd5c5')
                    fig.add_trace(go.Bar(
                        x=player_games['Round_num'], y=player_games['Brownlow.Votes'],
                        name='Actual Votes', marker_color=colors, opacity=0.85,
                        text=player_games['Brownlow.Votes'].apply(lambda v: str(int(v)) if v > 0 else ''),
                        textposition='outside',
                    ), secondary_y=False)

                fig.add_trace(go.Scatter(
                    x=player_games['Round_num'], y=player_games['Exp_Votes'].round(2),
                    name='Expected Votes', mode='lines+markers',
                    line=dict(color='#94a3b8', width=2, dash='dot'), marker=dict(size=6),
                ), secondary_y=False)

                fig.add_trace(go.Scatter(
                    x=player_games['Round_num'], y=(player_games['Poll_Prob'] * 100).round(1),
                    name='Poll Probability %', mode='lines+markers',
                    line=dict(color='#e63946', width=2), marker=dict(size=7),
                    fill='tozeroy', fillcolor='rgba(230,57,70,0.07)',
                ), secondary_y=True)

                fig.update_layout(
                    plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                    xaxis=dict(title='Round', dtick=1, gridcolor='#ede8df'),
                    legend=dict(orientation='h', y=1.12, bgcolor='rgba(0,0,0,0)'),
                    margin=dict(t=40, b=40), hovermode='x unified',
                )
                fig.update_yaxes(title_text="Votes", secondary_y=False, range=[0, 4], gridcolor='#ede8df')
                fig.update_yaxes(title_text="Poll Probability (%)", secondary_y=True, range=[0, 105], gridcolor='rgba(0,0,0,0)')
                fig = apply_chart_theme(fig)
                st.plotly_chart(fig, width='stretch', key="chart_003")

                st.markdown('<div class="section-header">Stat Context by Round</div>', unsafe_allow_html=True)
                stat_choice = st.selectbox("Stat to overlay",
                    ['Disposals', 'Coaches_Votes', 'Goals', 'Contested.Possessions', 'Clearances', 'Kicks'],
                    key="profile_stat")

                fig2 = go.Figure()
                bar_colors = ['#34d399' if w else '#e63946' for w in player_games['Is_Win'].fillna(0).astype(int)]
                fig2.add_trace(go.Bar(
                    x=player_games['Round_num'], y=player_games[stat_choice],
                    name=stat_choice.replace('.', ' ').replace('_', ' '),
                    marker_color=bar_colors, opacity=0.85,
                    text=player_games[stat_choice].astype(int), textposition='outside',
                ))
                fig2.add_trace(go.Scatter(
                    x=player_games['Round_num'], y=(player_games['Poll_Prob'] * 100).round(1),
                    name='Poll Probability %', mode='lines+markers',
                    line=dict(color='#e63946', width=2), yaxis='y2',
                ))
                fig2.update_layout(
                    plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                    xaxis=dict(title='Round', dtick=1, gridcolor='#ede8df'),
                    yaxis=dict(title=stat_choice.replace('.', ' '), gridcolor='#ede8df'),
                    yaxis2=dict(title='Poll %', overlaying='y', side='right', range=[0, 105], gridcolor='rgba(0,0,0,0)'),
                    legend=dict(orientation='h', y=1.12, bgcolor='rgba(0,0,0,0)'),
                    margin=dict(t=40, b=40), hovermode='x unified',
                )
                st.caption("Green = Win   Red = Loss")
                fig2 = apply_chart_theme(fig2)
                st.plotly_chart(fig2, width='stretch', key="chart_004")

                st.markdown('<div class="section-header">Game Log</div>', unsafe_allow_html=True)
                log = player_games.copy()
                log['Result'] = log['Is_Win'].map({1: 'W', 0: 'L'})
                log['Poll%'] = (log['Poll_Prob'] * 100).round(1).astype(str) + '%'
                log['ExpV'] = log['Exp_Votes'].round(2)
                log['P(3)'] = (log['P_3'] * 100).round(1).astype(str) + '%'
                log['P(2)'] = (log['P_2'] * 100).round(1).astype(str) + '%'
                log['P(1)'] = (log['P_1'] * 100).round(1).astype(str) + '%'
                display_cols = ['Round_num', 'Result', 'Disposals', 'Goals',
                                'Contested.Possessions', 'Clearances', 'Coaches_Votes']
                if not is_2026 and 'Brownlow.Votes' in log.columns:
                    display_cols.append('Brownlow.Votes')
                display_cols += ['ExpV', 'Poll%', 'P(3)', 'P(2)', 'P(1)']
                available = [c for c in display_cols if c in log.columns]
                log_display = log[available].rename(columns={
                    'Round_num': 'Rnd', 'Contested.Possessions': 'ContPoss',
                    'Coaches_Votes': 'CV', 'Brownlow.Votes': 'BV',
                })
                _log_disp = log_display.sort_values('Rnd').copy()
                for col in _log_disp.select_dtypes(include='float').columns:
                    _log_disp[col] = _log_disp[col].round(1)
                st.dataframe(_style_table(_log_disp), width='stretch', hide_index=True)

        # ── DNA tab ───────────────────────────────────────────
        with _tab_dna:
            if efficiency is None:
                st.error("No game-level data found.")
            else:
                eff_row = efficiency[efficiency['Player_Name'] == selected_player]
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

                    player_games_dna = game_df[game_df['Player_Name'] == selected_player].copy()
                    if not player_games_dna.empty and 'Brownlow.Votes' in player_games_dna.columns:
                        st.markdown('<div class="section-header">Vote Distribution</div>', unsafe_allow_html=True)
                        vote_counts = player_games_dna['Brownlow.Votes'].value_counts().sort_index()
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.markdown(f"""
| Votes | Games | Rate |
|-------|-------|------|
| 3 | {int(vote_counts.get(3, 0))} | {vote_counts.get(3, 0) / len(player_games_dna) * 100:.1f}% |
| 2 | {int(vote_counts.get(2, 0))} | {vote_counts.get(2, 0) / len(player_games_dna) * 100:.1f}% |
| 1 | {int(vote_counts.get(1, 0))} | {vote_counts.get(1, 0) / len(player_games_dna) * 100:.1f}% |
| 0 | {int(vote_counts.get(0, 0))} | {vote_counts.get(0, 0) / len(player_games_dna) * 100:.1f}% |
""")
                        with c2:
                            fig_pie = go.Figure(go.Pie(
                                labels=['3 votes', '2 votes', '1 vote', '0 votes'],
                                values=[vote_counts.get(3, 0), vote_counts.get(2, 0),
                                        vote_counts.get(1, 0), vote_counts.get(0, 0)],
                                marker_colors=['#94a3b8', '#34d399', '#6b7c3a', '#ddd5c5'],
                                hole=0.4,
                            ))
                            fig_pie.update_layout(
                                plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8',
                                font_color='#2c2c2c', margin=dict(t=10, b=10),
                                showlegend=True, height=250,
                                legend=dict(orientation='h', y=-0.1),
                            )
                            fig_pie = apply_chart_theme(fig_pie)
                            st.plotly_chart(fig_pie, width='stretch', key="chart_005")

                        st.markdown('<div class="section-header">Disposal Threshold Analysis</div>', unsafe_allow_html=True)
                        thresh_data = []
                        for t in [15, 20, 25, 28, 30, 33, 35]:
                            subset = player_games_dna[player_games_dna['Disposals'] >= t]
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
                st.dataframe(_style_table(_dna_disp), width='stretch', hide_index=True)

# ════════════════════════════════════════════════════════════
# PLAYER DNA — merged into Player Profile
# ════════════════════════════════════════════════════════════
if False:  # merged into Player Profile
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Player DNA — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Player-specific polling efficiency and tendencies</p></div>',
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
                                marker_colors=['#94a3b8', '#34d399', '#6b7c3a', '#ddd5c5'],
                                hole=0.4,
                            ))
                            fig_pie.update_layout(
                                plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8',
                                font_color='#2c2c2c', margin=dict(t=10, b=10),
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
# MODEL INSIGHTS
# ════════════════════════════════════════════════════════════
if _page == 'Model Insights':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Model Insights</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Feature importance · XGBoost v4.0 · Out-of-sample accuracy {_BT_MIN}–{_BT_MAX}</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-header">What Drives Brownlow Votes?</div>', unsafe_allow_html=True)

    if importance is None:
        st.error("Run brownlow_model.py first.")
    else:
        imp = importance.copy()
        imp['Importance %'] = (imp['Importance'] * 100).round(2)
        tab_all, tab_top = st.tabs(["All Features", "Top 20"])
        with tab_top:
            top20 = imp.head(20).sort_values('Importance %', ascending=True)
            fig3 = go.Figure(go.Bar(x=top20['Importance %'], y=top20['Feature'], orientation='h',
                                    marker=dict(color=top20['Importance %'],
                                                colorscale=[[0, '#1e3a4a'], [1, '#34d399']],
                                                showscale=False)))
            fig3 = apply_chart_theme(fig3)
            fig3.update_layout(xaxis_title='Importance (%)', height=500, margin=dict(l=220, r=16, t=20, b=16))
            st.plotly_chart(fig3, width='stretch', key="chart_007")
        with tab_all:
            all_imp = imp.sort_values('Importance %', ascending=True)
            fig4 = go.Figure(go.Bar(x=all_imp['Importance %'], y=all_imp['Feature'], orientation='h',
                                    marker=dict(color=all_imp['Importance %'],
                                                colorscale=[[0, '#1e3a4a'], [1, '#34d399']],
                                                showscale=False)))
            fig4 = apply_chart_theme(fig4)
            fig4.update_layout(xaxis_title='Importance (%)', height=1400, margin=dict(l=250, r=16, t=20, b=16))
            st.plotly_chart(fig4, width='stretch', key="chart_008")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Top signals:**\n- Coaches Votes (raw + relative z-score)\n- Top 3 coaches votes flag\n- Disposals relative to game\n- Impact Score relative to game\n- Is_Loss / Is_Win / Margin")
        with c2:
            st.markdown("**v4.0 improvements:**\n- Late-season form: rolling EWMA (span=5) of prior 5 rounds\n- Season momentum: last-6 vs first-6 avg\n- Late-season game weighting: last 5 rounds = 2× sample weight")

# ════════════════════════════════════════════════════════════
# COACHES VOTES
# ════════════════════════════════════════════════════════════
if _page == 'Coaches Votes':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Coaches Votes — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Coaches award votes compared to Brownlow polling</p></div>',
        unsafe_allow_html=True,
    )

    if game_df is None:
        st.error("No game-level data found.")
    else:
        cv_df = game_df.copy()
        has_cv = 'Coaches_Votes' in cv_df.columns and cv_df['Coaches_Votes'].sum() > 0

        if not has_cv:
            st.info("Coaches votes data not available for this season.")
        else:
            # ── Season leaderboard ───────────────────────────
            st.markdown('<div class="section-header">Season Coaches Votes Leaderboard</div>', unsafe_allow_html=True)

            cv_totals = cv_df.groupby('Player_Name').agg(
                Team=('Playing.for', 'last'),
                Games=('Round_num', 'count'),
                Total_CV=('Coaches_Votes', 'sum'),
                Avg_CV=('Coaches_Votes', 'mean'),
                Max_CV=('Coaches_Votes', 'max'),
                CV_Poll_Rate=('Coaches_Votes', lambda x: (x > 0).mean()),
            ).reset_index().sort_values('Total_CV', ascending=False).reset_index(drop=True)
            cv_totals.insert(0, 'Rank', range(1, len(cv_totals) + 1))
            cv_totals['Avg CV'] = cv_totals['Avg_CV'].round(2)
            cv_totals['CV Poll %'] = (cv_totals['CV_Poll_Rate'] * 100).round(1)

            col1, col2 = st.columns([3, 1])
            with col1: cv_search = st.text_input("Search player", "", key="cv_search")
            with col2: cv_show = st.selectbox("Show", [20, 50, 100], index=0, key="cv_show")

            cv_display = cv_totals.copy()
            if cv_search:
                cv_display = cv_display[cv_display['Player_Name'].str.contains(cv_search, case=False)]
            cv_display = cv_display.head(cv_show)
            _cv_disp = cv_display[['Rank', 'Player_Name', 'Team', 'Games', 'Total_CV', 'Avg CV', 'Max_CV', 'CV Poll %']].rename(
                columns={'Player_Name': 'Player', 'Total_CV': 'Total', 'Max_CV': 'Best Game'})
            for col in _cv_disp.select_dtypes(include='float').columns:
                _cv_disp[col] = _cv_disp[col].round(1)
            st.dataframe(_style_table(_cv_disp), width='stretch', hide_index=True)

            # ── Top 20 bar chart ─────────────────────────────
            st.markdown('<div class="section-header">Top 20 by Total Coaches Votes</div>', unsafe_allow_html=True)
            top20_cv = cv_totals.head(20)
            fig_cv = go.Figure(go.Bar(
                x=top20_cv['Player_Name'], y=top20_cv['Total_CV'],
                marker_color='#34d399', opacity=0.9,
                text=top20_cv['Total_CV'].astype(int), textposition='outside',
            ))
            fig_cv.update_layout(
                plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                yaxis=dict(title='Total Coaches Votes', gridcolor='#ede8df'),
                xaxis_tickangle=-35, margin=dict(t=20, b=120),
            )
            fig_cv = apply_chart_theme(fig_cv)
            st.plotly_chart(fig_cv, width='stretch', key="chart_009")

            # ── Coaches votes vs Brownlow correlation ────────
            if 'Brownlow.Votes' in cv_df.columns and cv_df['Brownlow.Votes'].notna().any():
                st.markdown('<div class="section-header">Coaches Votes vs Brownlow Votes — Game Level</div>', unsafe_allow_html=True)

                min_cv_games = st.slider("Min games for correlation view", 5, max_season_rounds, min(8, max_season_rounds), key="cv_min_g")
                eligible = cv_totals[cv_totals['Games'] >= min_cv_games]['Player_Name'].tolist()
                cv_corr = cv_df[cv_df['Player_Name'].isin(eligible)].copy()

                # Jitter to reduce overplotting
                jitter = np.random.default_rng(42).uniform(-0.15, 0.15, size=len(cv_corr))
                fig_scatter = go.Figure(go.Scatter(
                    x=cv_corr['Coaches_Votes'] + jitter,
                    y=cv_corr['Brownlow.Votes'],
                    mode='markers',
                    marker=dict(color='#34d399', size=5, opacity=0.35),
                    text=cv_corr['Player_Name'],
                    hovertemplate='<b>%{text}</b><br>Coaches V: %{x:.0f}<br>Brownlow V: %{y}<extra></extra>',
                ))
                corr_val = cv_corr[['Coaches_Votes', 'Brownlow.Votes']].corr().iloc[0, 1]
                fig_scatter.update_layout(
                    plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                    xaxis=dict(title='Coaches Votes', gridcolor='#ede8df'),
                    yaxis=dict(title='Brownlow Votes', gridcolor='#ede8df', dtick=1),
                    margin=dict(t=20, b=40), height=380,
                )
                fig_scatter = apply_chart_theme(fig_scatter)
                st.plotly_chart(fig_scatter, width='stretch', key="chart_010")
                st.caption(f"Pearson correlation: {corr_val:.2f}   (game-level, {len(cv_corr):,} observations)")

            # ── Per-player coaches votes round by round ──────
            st.markdown('<div class="section-header">Player Round by Round</div>', unsafe_allow_html=True)
            cv_players = sorted(cv_totals.head(50)['Player_Name'].tolist())
            sel_cv_player = st.selectbox("Select player", cv_players, key="cv_player")
            if sel_cv_player:
                p_cv = cv_df[cv_df['Player_Name'] == sel_cv_player].sort_values('Round_num')
                if not p_cv.empty:
                    fig_cv_p = go.Figure()
                    bar_col = ['#34d399' if w else '#e63946' for w in p_cv['Is_Win'].fillna(0).astype(int)]
                    fig_cv_p.add_trace(go.Bar(
                        x=p_cv['Round_num'], y=p_cv['Coaches_Votes'],
                        name='Coaches Votes', marker_color=bar_col, opacity=0.85,
                        text=p_cv['Coaches_Votes'].astype(int), textposition='outside',
                    ))
                    if 'Brownlow.Votes' in p_cv.columns:
                        fig_cv_p.add_trace(go.Scatter(
                            x=p_cv['Round_num'], y=p_cv['Brownlow.Votes'],
                            name='Brownlow Votes', mode='lines+markers',
                            line=dict(color='#94a3b8', width=2, dash='dot'), marker=dict(size=7),
                        ))
                    fig_cv_p.update_layout(
                        plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                        xaxis=dict(title='Round', dtick=1, gridcolor='#ede8df'),
                        yaxis=dict(title='Votes', gridcolor='#ede8df'),
                        legend=dict(orientation='h', y=1.1, bgcolor='rgba(0,0,0,0)'),
                        margin=dict(t=30, b=40),
                    )
                    st.caption("Green = Win   Red = Loss")
                    fig_cv_p = apply_chart_theme(fig_cv_p)
                    st.plotly_chart(fig_cv_p, width='stretch', key="chart_011")

# ════════════════════════════════════════════════════════════
# GAME ANALYSIS
# ════════════════════════════════════════════════════════════
if _page == 'Game Analysis':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#e8f0f8;margin:0">Game Analysis — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Round-by-round match predictions · poll probability breakdown</p></div>',
        unsafe_allow_html=True,
    )
    _ga_rbr_tab, _ga_pp_tab = st.tabs(["Round by Round", "Poll Probability"])

    # ── Round by Round tab ────────────────────────────────────
    with _ga_rbr_tab:
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
                    f'<div style="line-height:38px;color:#94a3b8;font-size:14px;">'
                    f'Round {selected_round - 1} &nbsp;·&nbsp; {rnd["Match"].nunique()} matches &nbsp;·&nbsp; {len(rnd)} players'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            def _style_game_table(df, winner_team=None):
                max_p3v = pd.to_numeric(df['P(3v) %'], errors='coerce').max() if len(df) > 0 else 1.0
                max_p3v = max_p3v if max_p3v > 0 else 1.0
                # Rank cell: neon number glow only — row box-shadow handled by _top3_row
                _rank_cell = {
                    0: ('color:#f0b429!important;font-weight:900!important;text-align:center!important;'
                        'text-shadow:0 0 6px rgba(240,180,41,1),0 0 18px rgba(240,180,41,0.65)!important;'),
                    1: ('color:#34d399!important;font-weight:900!important;text-align:center!important;'
                        'text-shadow:0 0 6px rgba(52,211,153,1),0 0 18px rgba(52,211,153,0.65)!important;'),
                    2: ('color:#4a90c4!important;font-weight:900!important;text-align:center!important;'
                        'text-shadow:0 0 6px rgba(74,144,196,1),0 0 18px rgba(74,144,196,0.65)!important;'),
                }
                # Top-3 rows: subtle tint + neon inset border glow on every cell
                _top3_row = {
                    0: ('background-color:rgba(240,180,41,0.07)!important;color:#e8f0f8!important;font-weight:700!important;'
                        'box-shadow:inset 0 0 0 1px rgba(240,180,41,0.65),0 0 8px rgba(240,180,41,0.22)!important;'),
                    1: ('background-color:rgba(52,211,153,0.06)!important;color:#e8f0f8!important;font-weight:700!important;'
                        'box-shadow:inset 0 0 0 1px rgba(52,211,153,0.65),0 0 8px rgba(52,211,153,0.22)!important;'),
                    2: ('background-color:rgba(74,144,196,0.06)!important;color:#e8f0f8!important;font-weight:700!important;'
                        'box-shadow:inset 0 0 0 1px rgba(74,144,196,0.65),0 0 8px rgba(74,144,196,0.22)!important;'),
                }
                def _cell(row):
                    i = row.name
                    if i in _top3_row:
                        base = _top3_row[i]
                    else:
                        base = ('background-color:#152533!important;color:#e8f0f8!important;'
                                if i % 2 == 0 else
                                'background-color:#1a2d3d!important;color:#e8f0f8!important;')
                    result = []
                    for col in df.columns:
                        if col == 'Rank' and i in _rank_cell:
                            result.append(base + _rank_cell[i])
                        elif col == 'Rank':
                            result.append(base + 'text-align:center!important;')
                        elif col == 'P(3v) %' and i >= 3:
                            v = float(row[col]) if row[col] != '' else 0.0
                            norm = v / max_p3v if max_p3v > 0 else 0.0
                            a = 0.07 + norm * 0.40
                            result.append(f'background-color:rgba(52,211,153,{a:.2f})!important;color:#e8f0f8!important;')
                        else:
                            result.append(base)
                    return result
                return df.style.apply(_cell, axis=1).format({
                    'Votes (exp)': '{:.2f}',
                    'P(3v) %':    '{:.2f}',
                    'P(2v) %':    '{:.2f}',
                    'Coaches V':  '{:.2f}',
                })

            game_order = rnd.drop_duplicates('Match')[['Match', 'Home.team', 'Away.team', 'Home.score', 'Away.score']].reset_index(drop=True)
            col_cfg = {
                'Player': st.column_config.TextColumn('Player'),
                'Team': st.column_config.TextColumn('Team', width='small'),
                'Rank': st.column_config.NumberColumn('Rank', width='small'),
                'Votes (exp)': st.column_config.NumberColumn('Votes (exp)', format='%.2f'),
                'P(3v) %': st.column_config.NumberColumn('P(3v) %', format='%.2f'),
                'P(2v) %': st.column_config.NumberColumn('P(2v) %', format='%.2f'),
                'Coaches V': st.column_config.NumberColumn('Coaches V', format='%.2f'),
                'Disposals': st.column_config.NumberColumn('Disposals', width='small'),
                'Cont. Poss': st.column_config.NumberColumn('Cont. Poss', width='small'),
                'Clearances': st.column_config.NumberColumn('Clearances', width='small'),
                'Goals': st.column_config.NumberColumn('Goals', width='small'),
            }

            for game_idx, game_row in game_order.iterrows():
                match = game_row['Match']
                home  = game_row['Home.team']
                away  = game_row['Away.team']
                winner_team = None
                try:
                    home_score = int(float(game_row['Home.score']))
                    away_score = int(float(game_row['Away.score']))
                    score_str = f"{home_score} – {away_score}"
                    if home_score > away_score:
                        winner_team = home
                        result_html = (
                            f'<span class="game-winner-name">{home}</span>'
                            f'<span class="game-loser-name"> def. {away}</span>'
                        )
                        score_pill = f'<span class="score-pill">{score_str}</span>'
                    elif away_score > home_score:
                        winner_team = away
                        result_html = (
                            f'<span class="game-winner-name">{away}</span>'
                            f'<span class="game-loser-name"> def. {home}</span>'
                        )
                        score_pill = f'<span class="score-pill">{score_str}</span>'
                    else:
                        result_html = f'<span class="game-winner-name">{home} drew {away}</span>'
                        score_pill = f'<span class="score-pill draw">{score_str}</span>'
                except (ValueError, TypeError):
                    result_html = f'<span class="game-winner-name">{match}</span>'
                    score_pill  = ''

                _delay = f'{game_idx * 0.07:.2f}'
                st.markdown(
                    f'<div class="game-card" style="animation-delay:{_delay}s">'
                    f'<div class="game-card-eyebrow">Game {game_idx + 1} &nbsp;·&nbsp; Round {selected_round - 1}</div>'
                    f'<div class="game-card-title">{result_html}{score_pill}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                gp = rnd[rnd['Match'] == match].copy().sort_values('Exp_Votes', ascending=False).reset_index(drop=True)
                gp['Rank'] = range(1, len(gp) + 1)
                disp = pd.DataFrame({
                    'Player':     gp['Player_Name'],
                    'Team':       gp['Team'],
                    'Rank':       gp['Rank'].astype(int),
                    'Votes (exp)': gp['Exp_Votes'].round(2),
                    'P(3v) %':   (gp['P_3'] * 100).round(2),
                    'P(2v) %':   (gp['P_2'] * 100).round(2),
                    'Coaches V': pd.to_numeric(gp['Coaches_Votes'], errors='coerce').fillna(0).round(2),
                    'Disposals': pd.to_numeric(gp['Disposals'], errors='coerce').fillna(0).astype(int),
                    'Cont. Poss': pd.to_numeric(gp.get('Contested.Possessions', gp.get('ContPoss', pd.Series([0]*len(gp)))), errors='coerce').fillna(0).astype(int),
                    'Clearances': pd.to_numeric(gp['Clearances'], errors='coerce').fillna(0).astype(int),
                    'Goals':     pd.to_numeric(gp['Goals'], errors='coerce').fillna(0).astype(int),
                }).reset_index(drop=True)
                n_total    = len(disp)
                expand_key = f"rr_expand_{selected_round}_{game_idx}"
                if expand_key not in st.session_state:
                    st.session_state[expand_key] = False
                show_all  = st.session_state[expand_key]
                disp_view = disp if show_all else disp.head(10)
                st.table(_style_game_table(disp_view, winner_team=winner_team))
                if n_total > 10:
                    remaining_rbr = n_total - 10
                    _exp_lbl = "↑ Show less" if show_all else f"↓ Show all {n_total} players  (+{remaining_rbr} more)"
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
# BETTING EDGE
# ════════════════════════════════════════════════════════════
if _page == 'Betting Edge':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Betting Edge — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Season projection with floor/ceiling · EV analysis against bookmaker odds</p></div>',
        unsafe_allow_html=True,
    )
    _be_sp_tab, _be_vf_tab = st.tabs(["Season Projection", "Value Finder"])

    with _be_sp_tab:
        proj = load_season_projection()
        if proj is None:
            st.error("No season projection found. Run predict_2026.py first.")
        else:
            _be_rounds_played = int(proj['Games_Played'].max())
            _be_remaining = int(proj['Remaining_Rounds'].iloc[0])
            _be_total_rounds = _be_rounds_played + _be_remaining
            _be_leader = proj.iloc[0]

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Rounds Played</div><div class="metric-value">{_be_rounds_played}</div><div class="metric-sub">of {_be_total_rounds} H&A rounds</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Remaining Rounds</div><div class="metric-value">{_be_remaining}</div><div class="metric-sub">to be projected</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Projected Leader</div><div class="metric-value" style="font-size:18px">{_be_leader["Player"]}</div><div class="metric-sub">{_be_leader["Season_Total_Projected"]:.1f} projected votes</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Per Game (Leader)</div><div class="metric-value">{_be_leader["Avg_Predicted_Per_Game"]:.2f}</div><div class="metric-sub">expected votes per game</div></div>', unsafe_allow_html=True)

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
                             visible=True, color='rgba(45,80,22,0.55)', thickness=1.5, width=4),
                hovertemplate='<b>%{x}</b><br>Expected so far: %{y:.1f}<br>'
                              'Floor: ' + top30_sp['Floor_Projection'].round(1).astype(str) + '<br>'
                              'Ceiling: ' + top30_sp['Ceiling_Projection'].round(1).astype(str) + '<extra></extra>',
            ))
            fig_proj.add_trace(go.Bar(
                name='Projected Remaining', x=top30_sp['Player'], y=top30_sp['Projected_Remaining'],
                marker_color='#94a3b8', opacity=0.9,
                hovertemplate='<b>%{x}</b><br>Projected remaining: %{y:.1f}<extra></extra>',
            ))
            fig_proj.update_layout(
                barmode='stack', plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                yaxis=dict(title='Votes', gridcolor='#ede8df'), xaxis=dict(tickangle=-35),
                legend=dict(orientation='h', y=1.08, bgcolor='rgba(0,0,0,0)'),
                margin=dict(t=20, b=130), height=480,
            )
            fig_proj = apply_chart_theme(fig_proj)
            st.plotly_chart(fig_proj, width='stretch', key="chart_012")
            st.caption("Green = Expected votes from played rounds (error bars = 10th–90th percentile)   Brown = Projected votes for remaining rounds")

            st.markdown('<div class="section-header">Full Season Projection Table</div>', unsafe_allow_html=True)
            _be_col1, _be_col2 = st.columns([3, 1])
            with _be_col1: _be_search = st.text_input("Search player", "", key="be_proj_search")
            with _be_col2: _be_show_n = st.selectbox("Show", [30, 50, 100, 200], index=0, key="be_proj_show")
            display_proj = proj.copy()
            if _be_search:
                display_proj = display_proj[display_proj['Player'].str.contains(_be_search, case=False)]
            display_proj = display_proj.head(_be_show_n).copy()
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

    with _be_vf_tab:
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
# STAT FILTER
# ════════════════════════════════════════════════════════════
if _page == 'Stat Filter':
    st.markdown(
        '<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Stat Filter</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">Set thresholds and see historical poll rates — 2015–2026</p></div>',
        unsafe_allow_html=True,
    )
    hist = load_all_historical()
    if hist is None:
        st.error("No historical game-level data found. Run brownlow_model.py first.")
    else:
        hist = hist[hist['Brownlow.Votes'].notna()].copy()
        st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)
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

        mask = (
            (hist['Season'] >= season_range[0]) & (hist['Season'] <= season_range[1]) &
            (hist['Player_Name'].isin(selected_players_sf) if selected_players_sf else pd.Series(True, index=hist.index)) &
            (hist['Disposals'] >= min_disp) & (hist['Goals'] >= min_goals) &
            (hist['Kicks'] >= min_kicks) & (hist['Clearances'] >= min_clearances) &
            (hist['Contested.Possessions'] >= min_contested) & (hist['Coaches_Votes'] >= min_coaches) &
            (hist['Tackles'] >= min_tackles) & (hist['Score_Involvements'] >= min_score_inv)
        )
        if has_rating: mask &= (hist['RatingPoints'] >= min_rating)
        if result_filter == "Win only": mask &= (hist['Is_Win'] == 1)
        elif result_filter == "Loss only": mask &= (hist['Is_Loss'] == 1)

        filtered_sf = hist[mask]
        total = len(filtered_sf)
        st.markdown('<div class="section-header">Results</div>', unsafe_allow_html=True)

        if total == 0:
            st.warning("No games match these filters.")
        else:
            has_2026 = season_range[1] >= 2026 and (filtered_sf['Season'] == 2026).any()
            if has_2026:
                n_2026_games = int((filtered_sf['Season'] == 2026).sum())
                max_rnd_2026 = int(filtered_sf[filtered_sf['Season'] == 2026]['Round_num'].max())
                st.info(f"2026 data included — {n_2026_games:,} games through Round {max_rnd_2026} (Brownlow votes not yet assigned). Poll rates from {season_range[0]}–2025 only.")
                vote_data = filtered_sf[filtered_sf['Season'] < 2026]
            else:
                vote_data = filtered_sf

            n3 = (vote_data['Brownlow.Votes'] == 3).sum()
            n2 = (vote_data['Brownlow.Votes'] == 2).sum()
            n1 = (vote_data['Brownlow.Votes'] == 1).sum()
            n0 = (vote_data['Brownlow.Votes'] == 0).sum()
            vote_total = len(vote_data)
            poll_rate = (vote_data['Brownlow.Votes'] > 0).mean() if vote_total > 0 else 0
            avg_votes = vote_data['Brownlow.Votes'].mean() if vote_total > 0 else 0
            player_sub = f"{len(selected_players_sf)} players" if selected_players_sf else "All players"

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Matching Games</div><div class="metric-value">{total:,}</div><div class="metric-sub">{season_range[0]}–{season_range[1]} · {player_sub}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Poll Rate</div><div class="metric-value">{poll_rate * 100:.1f}%</div><div class="metric-sub">Any votes</div></div>', unsafe_allow_html=True)
            with c3:
                if vote_total > 0: st.markdown(f'<div class="metric-card"><div class="metric-label">3-Vote Rate</div><div class="metric-value">{n3 / vote_total * 100:.1f}%</div><div class="metric-sub">{n3:,} games</div></div>', unsafe_allow_html=True)
            with c4:
                if vote_total > 0: st.markdown(f'<div class="metric-card"><div class="metric-label">2-Vote Rate</div><div class="metric-value">{n2 / vote_total * 100:.1f}%</div><div class="metric-sub">{n2:,} games</div></div>', unsafe_allow_html=True)
            with c5: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Votes</div><div class="metric-value">{avg_votes:.3f}</div><div class="metric-sub">per game</div></div>', unsafe_allow_html=True)

            col_chart, col_table = st.columns([2, 1])
            with col_chart:
                if vote_total > 0:
                    fig_bar = go.Figure(go.Bar(
                        x=['3 votes', '2 votes', '1 vote', '0 votes'],
                        y=[n3 / vote_total * 100, n2 / vote_total * 100, n1 / vote_total * 100, n0 / vote_total * 100],
                        marker_color=['#94a3b8', '#34d399', '#6b7c3a', '#ddd5c5'],
                        text=[f"{v:.1f}%" for v in [n3 / vote_total * 100, n2 / vote_total * 100, n1 / vote_total * 100, n0 / vote_total * 100]],
                        textposition='outside',
                    ))
                    fig_bar.update_layout(
                        plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
                        yaxis=dict(title='% of games', gridcolor='#ede8df', range=[0, max(n0 / vote_total * 100 * 1.1, 10)]),
                        xaxis=dict(gridcolor='#ede8df'), margin=dict(t=20, b=20), height=300, showlegend=False,
                    )
                    fig_bar = apply_chart_theme(fig_bar)
                    st.plotly_chart(fig_bar, width='stretch', key="chart_013")
            with col_table:
                st.markdown("**Vote breakdown**")
                if vote_total > 0:
                    st.markdown(f"""
| Votes | Games | Rate |
|-------|------:|-----:|
| 3 | {n3:,} | {n3 / vote_total * 100:.1f}% |
| 2 | {n2:,} | {n2 / vote_total * 100:.1f}% |
| 1 | {n1:,} | {n1 / vote_total * 100:.1f}% |
| 0 | {n0:,} | {n0 / vote_total * 100:.1f}% |
| **Total** | **{vote_total:,}** | |
""")

            st.markdown('<div class="section-header">Threshold Comparison</div>', unsafe_allow_html=True)
            st.caption("Poll rate at each disposal threshold, holding all other filters fixed")
            disp_rows = []
            for t in [0, 15, 20, 25, 28, 30, 33, 35, 38, 40]:
                sub_mask = mask & (hist['Disposals'] >= t) & (hist['Season'] < 2026)
                sub = hist[sub_mask]
                if len(sub) >= 5:
                    disp_rows.append({'Min Disposals': t, 'Games': len(sub),
                                      'Poll Rate': f"{(sub['Brownlow.Votes'] > 0).mean() * 100:.1f}%",
                                      '3-vote Rate': f"{(sub['Brownlow.Votes'] == 3).mean() * 100:.1f}%",
                                      'Avg Votes': f"{sub['Brownlow.Votes'].mean():.3f}"})
            if disp_rows:
                st.dataframe(pd.DataFrame(disp_rows), width='stretch', hide_index=True)

            st.markdown('<div class="section-header">Sample Games</div>', unsafe_allow_html=True)
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
            st.dataframe(_style_table(_sf_disp), width='stretch', hide_index=True)

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
                format_func=lambda r: f"Round {r - 1}",
                index=max(0, len(available_rounds) - 1),
                key="rbr_round",
            )
        rnd = rr[rr['Round_num'] == selected_round].copy()
        with info_col:
            st.markdown(
                f'<div style="line-height:38px;color:#94a3b8;font-size:14px;">'
                f'Round {selected_round - 1} &nbsp;·&nbsp; {rnd["Match"].nunique()} matches &nbsp;·&nbsp; {len(rnd)} players'
                f'</div>',
                unsafe_allow_html=True,
            )

        def _style_game_table(df):
            max_p3v = df['P(3v) %'].max() if len(df) > 0 and df['P(3v) %'].max() > 0 else 1.0
            def _cell(row):
                i = row.name
                if i == 0: base = 'background-color: rgba(139,111,71,0.22); font-weight:700;'
                elif i == 1: base = 'background-color: rgba(107,124,58,0.15); font-weight:700;'
                elif i == 2: base = 'background-color: rgba(45,80,22,0.12); font-weight:700;'
                elif i % 2 == 0: base = 'background-color: #f0ece4;'
                else: base = 'background-color: #e8f0f8;'
                result = []
                for col in df.columns:
                    if col == 'P(3v) %' and i >= 3:
                        v = row[col]
                        norm = v / max_p3v if max_p3v > 0 else 0.0
                        a = 0.08 + norm * 0.45
                        result.append(f'background-color: rgba(45,80,22,{a:.2f});')
                    else:
                        result.append(base)
                return result
            return df.style.apply(_cell, axis=1)

        GAME_COLOURS = ['#34d399', '#e63946', '#94a3b8', '#6b7c3a', '#4a90d9', '#e07b39', '#6c3483', '#1a6e8c', '#7d6608', '#b03a2e']
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
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{home}</span><span style='color:#94a3b8;font-size:18px'> def. {away}</span>"
                elif away_score > home_score:
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{away}</span><span style='color:#94a3b8;font-size:18px'> def. {home}</span>"
                else:
                    result_html = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{home} drew {away}</span>"
                score_html = f"<span style='color:{colour};font-size:17px;font-weight:600'>&nbsp;&nbsp;{score_str}</span>"
                header_body = f"{result_html}{score_html}"
            except (ValueError, TypeError):
                header_body = f"<span style='color:#34d399;font-size:22px;font-weight:700'>{match}</span>"

            st.markdown(
                f'<div style="border-left:6px solid {colour};padding:16px 22px;background:#ffffff;'
                f'border-radius:0 8px 8px 0;margin:36px 0 8px 0;box-shadow:0 1px 4px rgba(45,80,22,0.08);'
                f'border:1px solid #ddd5c5;border-left:6px solid {colour};">'
                f'<div style="color:{colour};font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px">'
                f'Game {game_idx + 1} &nbsp;·&nbsp; Round {selected_round - 1}</div>'
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
        '<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">2026 Season Projection</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">Actual votes to date + model-projected remaining rounds</p></div>',
        unsafe_allow_html=True,
    )
    proj = load_season_projection()
    if proj is None:
        st.error("No season projection found. Run predict_2026.py first.")
    else:
        rounds_played = int(proj['Games_Played'].max())
        remaining_sp = int(proj['Remaining_Rounds'].iloc[0])
        total_rounds_sp = rounds_played + remaining_sp
        leader_sp = proj.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Rounds Played</div><div class="metric-value">{rounds_played}</div><div class="metric-sub">of {total_rounds_sp} H&A rounds</div></div>', unsafe_allow_html=True)
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
                         visible=True, color='rgba(45,80,22,0.55)', thickness=1.5, width=4),
            hovertemplate='<b>%{x}</b><br>Expected so far: %{y:.1f}<br>'
                          'Floor: ' + top30_sp['Floor_Projection'].round(1).astype(str) + '<br>'
                          'Ceiling: ' + top30_sp['Ceiling_Projection'].round(1).astype(str) + '<extra></extra>',
        ))
        fig_proj.add_trace(go.Bar(
            name='Projected Remaining', x=top30_sp['Player'], y=top30_sp['Projected_Remaining'],
            marker_color='#94a3b8', opacity=0.9,
            hovertemplate='<b>%{x}</b><br>Projected remaining: %{y:.1f}<extra></extra>',
        ))
        fig_proj.update_layout(
            barmode='stack', plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
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
# MODEL INSIGHTS — accuracy section
# ════════════════════════════════════════════════════════════
if _page == 'Model Insights':
    st.markdown(
        '<div style="border-top:2px solid #ddd5c5;margin:36px 0 28px 0;position:relative;">'
        '<span style="position:absolute;top:-11px;left:50%;transform:translateX(-50%);'
        'background:#e8f0f8;padding:0 14px;color:#94a3b8;font-size:11px;font-weight:700;'
        'letter-spacing:2px;text-transform:uppercase;">Model Accuracy</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="section-header">Out-of-Sample Back-Test — {_BT_MIN} to {_BT_MAX}</div>', unsafe_allow_html=True)
    st.caption("Walk-forward: each season trained only on prior years")
    bt = load_backtest()
    if bt is None:
        st.error("No backtest results found. Run backtest.py first.")
    else:
        rows_bt = []
        for season in sorted(bt['Season'].unique()):
            s = bt[bt['Season'] == season]
            actual_winners = s[s['Rank_Actual'] == 1]['Player'].tolist()
            pred_top3 = set(s[s['Rank_Predicted'] <= 3]['Player'])
            pred_top5 = set(s[s['Rank_Predicted'] <= 5]['Player'])
            pred_top10 = set(s[s['Rank_Predicted'] <= 10]['Player'])
            top10_pred = s[s['Rank_Predicted'] <= 10].copy()
            avg_err = (top10_pred['Predicted_Votes'] - top10_pred['Actual_Votes']).abs().mean()
            winner = actual_winners[0] if actual_winners else '?'
            pred_rank = int(s.loc[s['Player'] == winner, 'Rank_Predicted'].values[0]) if winner in s['Player'].values else '?'
            rows_bt.append({
                'Season': int(season), 'Actual Winner': winner, 'Pred. Rank': pred_rank,
                'In Top 3': any(w in pred_top3 for w in actual_winners),
                'In Top 5': any(w in pred_top5 for w in actual_winners),
                'In Top 10': any(w in pred_top10 for w in actual_winners),
                'Avg Error Top 10': round(avg_err, 1),
            })
        acc_df = pd.DataFrame(rows_bt)
        n_seasons = len(acc_df)
        top3_acc = acc_df['In Top 3'].sum()
        top5_acc = acc_df['In Top 5'].sum()
        top10_acc = acc_df['In Top 10'].sum()
        avg_err_total = acc_df['Avg Error Top 10'].mean()

        st.markdown(f'<div class="section-header">Out-of-Sample Accuracy — {_BT_MIN} to {_BT_MAX}</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Top 3 Accuracy</div><div class="metric-value">{top3_acc}/{n_seasons}</div><div class="metric-sub">Winner predicted top 3 · {top3_acc / n_seasons * 100:.0f}%</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Top 5 Accuracy</div><div class="metric-value">{top5_acc}/{n_seasons}</div><div class="metric-sub">Winner predicted top 5 · {top5_acc / n_seasons * 100:.0f}%</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Top 10 Accuracy</div><div class="metric-value">{top10_acc}/{n_seasons}</div><div class="metric-sub">Winner predicted top 10 · {top10_acc / n_seasons * 100:.0f}%</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Vote Error (Top 10)</div><div class="metric-value">{avg_err_total:.1f}</div><div class="metric-sub">votes · across predicted top 10</div></div>', unsafe_allow_html=True)

        with st.expander("What's new in v4.0?", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("""
**Late-season form** (`late_form_ewm`)
EWMA (span=5) of expected votes over prior 5 rounds. More recent rounds weighted higher.
Uses Wheelo ExpVotes where available, otherwise Coaches Votes.
Last 5 rounds of each season receive **2× sample weight** during training.
""")
            with col_b:
                st.markdown("""
**Season momentum** (`momentum_cv`, `momentum_disp`)
Average coaches votes and disposals in last 6 games minus first 6 games.
Positive = improving trajectory, negative = declining.
""")

        st.markdown('<div class="section-header">Season by Season Breakdown</div>', unsafe_allow_html=True)
        display_acc = acc_df.copy()
        display_acc['In Top 3'] = display_acc['In Top 3'].map({True: 'Yes', False: 'No'})
        display_acc['In Top 5'] = display_acc['In Top 5'].map({True: 'Yes', False: 'No'})
        display_acc['In Top 10'] = display_acc['In Top 10'].map({True: 'Yes', False: 'No'})
        _acc_disp = display_acc.rename(columns={'Avg Error Top 10': 'Avg Error (Top 10)'})
        for col in _acc_disp.select_dtypes(include='float').columns:
            _acc_disp[col] = _acc_disp[col].round(1)
        st.dataframe(_style_table(_acc_disp), width='stretch', hide_index=True)

        st.markdown('<div class="section-header">Predicted Rank of Actual Winner by Season</div>', unsafe_allow_html=True)
        fig_rank = go.Figure()
        bar_colors_rank = ['#f0b429' if r <= 3 else ('#34d399' if r <= 5 else ('#4a90c4' if r <= 10 else '#4a5a6a'))
                           for r in acc_df['Pred. Rank']]
        fig_rank.add_trace(go.Bar(
            x=acc_df['Season'].astype(str), y=acc_df['Pred. Rank'], marker_color=bar_colors_rank,
            text=[f"#{r} — {w}" for r, w in zip(acc_df['Pred. Rank'], acc_df['Actual Winner'])],
            textposition='outside', textfont=dict(color='#e8f0f8', size=11),
            hovertemplate='%{text}<extra></extra>',
        ))
        fig_rank.add_hline(y=3, line_dash='dot', line_color='#f0b429', annotation_text='Top 3',
                           annotation_position='right', annotation_font_color='#f0b429')
        fig_rank.add_hline(y=5, line_dash='dot', line_color='#34d399', annotation_text='Top 5',
                           annotation_position='right', annotation_font_color='#34d399')
        fig_rank.add_hline(y=10, line_dash='dot', line_color='#4a90c4', annotation_text='Top 10',
                           annotation_position='right', annotation_font_color='#4a90c4')
        fig_rank = apply_chart_theme(fig_rank)
        fig_rank.update_layout(
            yaxis=dict(title='Predicted Rank of Actual Winner', autorange='reversed',
                       range=[max(acc_df['Pred. Rank']) + 2, 0]),
            xaxis=dict(title='Season'),
            margin=dict(t=40, b=40), showlegend=False,
        )
        st.plotly_chart(fig_rank, width='stretch', key="chart_015")
        st.caption("Gold = Top 3   Green = Top 5   Blue = Top 10   Grey = Outside Top 10")

        st.markdown('<div class="section-header">Predicted vs Actual Votes — Top 10 Predicted Players</div>', unsafe_allow_html=True)
        seasons_avail = sorted(bt['Season'].unique().astype(int).tolist())
        sel_s = st.selectbox("Season", seasons_avail, index=len(seasons_avail) - 1, key='acc_season')
        s_data = bt[(bt['Season'] == sel_s) & (bt['Rank_Predicted'] <= 10)].copy().sort_values('Rank_Predicted')
        fig_scatter = go.Figure()
        marker_colors_sc = ['#f0b429' if row['Rank_Actual'] == 1 else '#4a90c4' for _, row in s_data.iterrows()]
        fig_scatter.add_trace(go.Scatter(
            x=s_data['Actual_Votes'], y=s_data['Predicted_Votes'],
            mode='markers+text', marker=dict(size=12, color=marker_colors_sc),
            text=s_data['Player'], textposition='top center', textfont=dict(size=11, color='#e8f0f8'),
            hovertemplate='<b>%{text}</b><br>Actual: %{x}<br>Predicted: %{y:.1f}<extra></extra>',
        ))
        max_v = max(s_data['Actual_Votes'].max(), s_data['Predicted_Votes'].max()) + 5
        fig_scatter.add_trace(go.Scatter(
            x=[0, max_v], y=[0, max_v], mode='lines',
            line=dict(color='#4a5a6a', dash='dash', width=1), showlegend=False, hoverinfo='skip',
        ))
        fig_scatter = apply_chart_theme(fig_scatter)
        fig_scatter.update_layout(
            xaxis=dict(title='Actual Votes', range=[0, max_v]),
            yaxis=dict(title='Predicted Votes', range=[0, max_v]),
            margin=dict(t=20, b=40), height=420,
        )
        st.plotly_chart(fig_scatter, width='stretch', key="chart_016")
        st.caption("Gold dot = Actual winner   Blue dot = Other top 10 predicted   Dashed line = perfect prediction")

# ════════════════════════════════════════════════════════════
# PLAYER COMPARISON
# ════════════════════════════════════════════════════════════
if _page == 'Player Comparison':
    st.markdown(
        f'<div class="title-bar"><h2 style="color:#e8f0f8;margin:0">Player Comparison — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Head-to-head model comparison and betting analysis</p></div>',
        unsafe_allow_html=True,
    )

    _cmp_players = sorted(predictions['Player_Name'].tolist())
    _cmp_proj = load_season_projection()
    _cmp_odds = load_best_odds()

    _def1 = predictions.iloc[0]['Player_Name'] if len(predictions) > 0 else _cmp_players[0]
    _def2 = predictions.iloc[1]['Player_Name'] if len(predictions) > 1 else _cmp_players[1]

    _sel_col1, _sel_col_vs, _sel_col2 = st.columns([5, 1, 5])
    with _sel_col1:
        _p1 = st.selectbox("Player 1", _cmp_players,
                           index=_cmp_players.index(_def1), key="cmp_p1")
    with _sel_col_vs:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;'
            'padding-top:28px;font-size:28px;font-weight:900;color:#94a3b8;letter-spacing:2px">VS</div>',
            unsafe_allow_html=True,
        )
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

    def _render_cmp_card(d, colour):
        floor_s = f"{d['floor']}" if d['floor'] is not None else "—"
        ceil_s  = f"{d['ceiling']}" if d['ceiling'] is not None else "—"
        odds_s  = f"${d['best_odds']}" if d['best_odds'] is not None else "—"
        mkt_s   = f"{d['market_pct']}%" if d['market_pct'] is not None else "—"
        st.markdown(
            f'<div style="background:#152533;border:1px solid #2a4a5a;border-top:3px solid {colour};'
            f'border-radius:8px;padding:18px 22px;margin:6px 0;">'
            f'<div class="metric-label">{d["team"]}</div>'
            f'<div style="font-size:26px;font-weight:800;color:#e8f0f8;margin:4px 0 14px 0;line-height:1.1">{d["name"]}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px 16px;">'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Exp Votes</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{d["exp_votes"]}</div></div>'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Floor</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{floor_s}</div></div>'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Ceiling</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{ceil_s}</div></div>'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Poll %</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{d["poll_pct"]}%</div></div>'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">3-Vote Games</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{d["three_vote_games"]}</div></div>'
            f'<div><div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Best Odds / Mkt%</div>'
            f'<div style="font-size:20px;font-weight:700;color:{colour}">{odds_s} <span style="font-size:13px;color:#94a3b8">/ {mkt_s}</span></div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    _d1 = _cmp_player_data(_p1)
    _d2 = _cmp_player_data(_p2)

    if _p1 == _p2:
        st.warning("Select two different players to compare.")
    elif _d1 and _d2:
        _tab_so, _tab_h2h = st.tabs(["Season Overview", "Head to Head Betting"])

        # ── Season Overview tab ───────────────────────────────
        with _tab_so:
            _cc1, _cc2 = st.columns(2)
            with _cc1:
                _render_cmp_card(_d1, '#34d399')
            with _cc2:
                _render_cmp_card(_d2, '#94a3b8')

            st.markdown('<div class="section-header">Vote Projection Comparison</div>', unsafe_allow_html=True)
            _proj_cats = ['Floor', 'Expected', 'Ceiling']
            _p1_proj = [_d1['floor'] or 0, _d1['exp_votes'], _d1['ceiling'] or 0]
            _p2_proj = [_d2['floor'] or 0, _d2['exp_votes'], _d2['ceiling'] or 0]
            _fig_proj = go.Figure()
            _fig_proj.add_trace(go.Bar(
                name=_p1, y=_proj_cats, x=_p1_proj, orientation='h',
                marker_color='#34d399', opacity=0.88,
                text=[f'{v:.1f}' for v in _p1_proj], textposition='outside',
                textfont=dict(color='#e8f0f8', size=12),
            ))
            _fig_proj.add_trace(go.Bar(
                name=_p2, y=_proj_cats, x=_p2_proj, orientation='h',
                marker_color='#94a3b8', opacity=0.88,
                text=[f'{v:.1f}' for v in _p2_proj], textposition='outside',
                textfont=dict(color='#e8f0f8', size=12),
            ))
            _fig_proj = apply_chart_theme(_fig_proj)
            _fig_proj.update_layout(
                barmode='group',
                xaxis=dict(title='Votes', zeroline=False),
                yaxis=dict(title='', tickfont=dict(size=12)),
                legend=dict(orientation='h', y=1.12),
                margin=dict(t=20, b=20, l=10, r=60),
                height=240,
            )
            st.plotly_chart(_fig_proj, width='stretch', key="chart_017")

            if game_df is not None:
                st.markdown('<div class="section-header">Round by Round — Predicted Votes</div>', unsafe_allow_html=True)
                _g1 = game_df[game_df['Player_Name'] == _p1].sort_values('Round_num')
                _g2 = game_df[game_df['Player_Name'] == _p2].sort_values('Round_num')
                if not _g1.empty or not _g2.empty:
                    _fig_rbr = go.Figure()
                    if not _g1.empty:
                        _fig_rbr.add_trace(go.Scatter(
                            x=(_g1['Round_num'] - 1), y=_g1['Exp_Votes'].round(1),
                            name=_p1, mode='lines+markers',
                            line=dict(color='#34d399', width=2.5),
                            marker=dict(size=7, color='#34d399'),
                            hovertemplate='<b>' + _p1 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    if not _g2.empty:
                        _fig_rbr.add_trace(go.Scatter(
                            x=(_g2['Round_num'] - 1), y=_g2['Exp_Votes'].round(1),
                            name=_p2, mode='lines+markers',
                            line=dict(color='#94a3b8', width=2.5),
                            marker=dict(size=7, color='#94a3b8'),
                            hovertemplate='<b>' + _p2 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    _fig_rbr = apply_chart_theme(_fig_rbr)
                    _fig_rbr.update_layout(
                        xaxis=dict(title='Round', dtick=1),
                        yaxis=dict(title='Predicted Votes', rangemode='tozero'),
                        legend=dict(orientation='h', y=1.1),
                        margin=dict(t=20, b=40), height=300, hovermode='x unified',
                    )
                    st.plotly_chart(_fig_rbr, width='stretch', key="chart_018")

                st.markdown('<div class="section-header">Stat Comparison</div>', unsafe_allow_html=True)
                _radar_candidates = [
                    ('Disposals',              'Disposals'),
                    ('Contested.Possessions',  'Cont. Poss'),
                    ('Clearances',             'Clearances'),
                    ('Tackles',                'Tackles'),
                    ('Inside.50s',             'Inside 50s'),
                    ('Coaches_Votes',          'Coaches Votes'),
                ]
                _radar_pairs = [(s, l) for s, l in _radar_candidates if s in game_df.columns]
                if _radar_pairs:
                    _r_stats  = [s for s, _ in _radar_pairs]
                    _r_labels = [l for _, l in _radar_pairs]
                    _all_means = game_df.groupby('Player_Name')[_r_stats].mean()
                    _g1_mean   = game_df[game_df['Player_Name'] == _p1][_r_stats].mean()
                    _g2_mean   = game_df[game_df['Player_Name'] == _p2][_r_stats].mean()
                    _p1_norm, _p2_norm = [], []
                    for _rs in _r_stats:
                        _cmin = _all_means[_rs].min()
                        _cmax = _all_means[_rs].max()
                        _rng  = _cmax - _cmin if _cmax > _cmin else 1.0
                        _p1_norm.append(round(float(((_g1_mean.get(_rs, _cmin) - _cmin) / _rng) * 100), 1))
                        _p2_norm.append(round(float(((_g2_mean.get(_rs, _cmin) - _cmin) / _rng) * 100), 1))
                    _fig_radar = go.Figure()
                    _fig_radar.add_trace(go.Scatterpolar(
                        r=_p1_norm + [_p1_norm[0]], theta=_r_labels + [_r_labels[0]],
                        name=_p1, fill='toself', fillcolor='rgba(52,211,153,0.12)',
                        line=dict(color='#34d399', width=2.5),
                    ))
                    _fig_radar.add_trace(go.Scatterpolar(
                        r=_p2_norm + [_p2_norm[0]], theta=_r_labels + [_r_labels[0]],
                        name=_p2, fill='toself', fillcolor='rgba(148,163,184,0.15)',
                        line=dict(color='#94a3b8', width=2.5),
                    ))
                    _fig_radar.update_layout(
                        polar=dict(
                            bgcolor='#152533',
                            radialaxis=dict(visible=True, range=[0, 100], gridcolor='#1e3a4a',
                                            tickfont=dict(size=9), tickvals=[25, 50, 75, 100]),
                            angularaxis=dict(gridcolor='#1e3a4a', tickfont=dict(size=11)),
                        ),
                        paper_bgcolor='#152533', font_color='#94a3b8',
                        legend=dict(orientation='h', y=-0.08, bgcolor='rgba(0,0,0,0)'),
                        margin=dict(t=30, b=60, l=60, r=60), height=420,
                    )
                    _fig_radar = apply_chart_theme(_fig_radar)
                    st.plotly_chart(_fig_radar, width='stretch', key="chart_019")
                    st.caption("Each axis normalised 0–100 relative to all players in the dataset")

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
            for _col, _d, _colour, _mpct in [(_h2h_ca, _d1, '#34d399', _ma), (_h2h_cb, _d2, '#94a3b8', _mb)]:
                with _col:
                    _fs = f"{_d['floor']}" if _d['floor'] is not None else "—"
                    _cs = f"{_d['ceiling']}" if _d['ceiling'] is not None else "—"
                    st.markdown(
                        f'<div style="background:#152533;border:1px solid #2a4a5a;border-top:3px solid {_colour};'
                        f'border-radius:8px;padding:16px 20px;margin:4px 0;">'
                        f'<div style="font-size:10px;color:#4a5a6a;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">{_d["team"]}</div>'
                        f'<div style="font-size:22px;font-weight:800;color:#e8f0f8;margin:3px 0 12px 0">{_d["name"]}</div>'
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
                f'<div style="width:{_mb}%;background:#94a3b8;display:flex;align-items:center;justify-content:center;">'
                f'<span style="color:#fff;font-weight:800;font-size:17px">{_mb}%</span></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;margin-bottom:4px;">'
                f'<span>{_p1}</span><span>{_p2}</span></div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="section-header">Market Implied Probability</div>', unsafe_allow_html=True)
            if _has_mkt:
                st.markdown(
                    f'<div style="margin:12px 0 6px 0;display:flex;border-radius:6px;overflow:hidden;height:44px;">'
                    f'<div style="width:{_mkta}%;background:#4a90c4;display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:#e8f0f8;font-weight:800;font-size:17px">{_mkta}%</span></div>'
                    f'<div style="width:{_mktb}%;background:#1e3a4a;display:flex;align-items:center;justify-content:center;">'
                    f'<span style="color:#94a3b8;font-weight:800;font-size:17px">{_mktb}%</span></div>'
                    f'</div>'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;margin-bottom:4px;">'
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
                    _ebg, _ebord, _elabel = '#152533', '#2a4a5a', 'NEUTRAL'
                    _emsg = (f"Model and market broadly agree — difference is only "
                             f"<strong>{_edge_abs}%</strong>. No clear edge either way.")
                st.markdown(
                    f'<div style="background:{_ebg};border:1px solid {_ebord};'
                    f'border-radius:8px;padding:16px 22px;margin:8px 0;">'
                    f'<div style="font-size:11px;font-weight:800;letter-spacing:2.5px;text-transform:uppercase;'
                    f'color:{_ebord};margin-bottom:6px">{_elabel}</div>'
                    f'<div style="font-size:14px;color:#e8f0f8;line-height:1.8">{_emsg}</div>'
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
                            x=(_hg1['Round_num'] - 1), y=_hg1['Exp_Votes'].round(1),
                            name=_p1, mode='lines+markers',
                            line=dict(color='#34d399', width=2.5), marker=dict(size=7, color='#34d399'),
                            hovertemplate='<b>' + _p1 + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                        ))
                    if not _hg2.empty:
                        _fig_h2h_rbr.add_trace(go.Scatter(
                            x=(_hg2['Round_num'] - 1), y=_hg2['Exp_Votes'].round(1),
                            name=_p2, mode='lines+markers',
                            line=dict(color='#94a3b8', width=2.5), marker=dict(size=7, color='#94a3b8'),
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
            _vc2 = '#34d399' if _ma >= _mb else '#94a3b8'
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
                f'<div style="background:#152533;border:1px solid #2a4a5a;border-top:3px solid {_vc2};'
                f'border-radius:8px;padding:20px 24px;margin:6px 0;">'
                f'<div style="font-size:14px;color:#e8f0f8;line-height:2;">'
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
        f'<div class="title-bar"><h2 style="color:#2c2c2c;margin:0">Head to Head — {selected_season}</h2>'
        f'<p style="color:#94a3b8;margin:4px 0 0 0">Model probability vs market implied probability</p></div>',
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
                'padding-top:28px;font-size:28px;font-weight:900;color:#94a3b8;letter-spacing:2px">VS</div>',
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
                    (_card_b, _db, '#94a3b8', _mb),
                ]:
                    with _col:
                        floor_s = f"{_d['floor']}" if _d['floor'] is not None else "—"
                        ceil_s  = f"{_d['ceiling']}" if _d['ceiling'] is not None else "—"
                        st.markdown(
                            f'<div style="background:#f0ece4;border:1px solid #ddd5c5;border-left:5px solid {_colour};'
                            f'border-radius:8px;padding:16px 20px;margin:4px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
                            f'<div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">{_d["team"]}</div>'
                            f'<div style="font-size:22px;font-weight:800;color:#2c2c2c;margin:3px 0 12px 0;line-height:1.1">{_d["name"]}</div>'
                            f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px 14px;">'
                            f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Exp Votes</div>'
                            f'<div style="font-size:22px;font-weight:800;color:{_colour}">{_d["exp"]}</div></div>'
                            f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Floor</div>'
                            f'<div style="font-size:22px;font-weight:800;color:{_colour}">{floor_s}</div></div>'
                            f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:600;letter-spacing:0.8px">Ceiling</div>'
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
                    f'<div style="width:{_mb}%;background:#94a3b8;display:flex;align-items:center;justify-content:center;">'
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
                        _edge_bord  = '#94a3b8'
                        _edge_label = 'MARKET FAVOURS'
                        _mkt_fav    = _hb if _favoured == _ha else _ha
                        _edge_msg   = (f"Market prices <strong>{_mkt_fav}</strong> "
                                       f"<strong>{_edge_abs}%</strong> higher than the model suggests. "
                                       f"Model: {_ma if _favoured == _ha else _mb}% &nbsp;·&nbsp; "
                                       f"Market: {_mkta if _favoured == _ha else _mktb}%")
                    else:
                        _edge_bg    = '#f0ece4'
                        _edge_bord  = '#b0a090'
                        _edge_label = 'NEUTRAL'
                        _edge_msg   = (f"Model and market broadly agree — difference is only "
                                       f"<strong>{_edge_abs}%</strong>. No clear edge either way.")
                    st.markdown(
                        f'<div style="background:{_edge_bg};border:1px solid #ddd5c5;border-left:6px solid {_edge_bord};'
                        f'border-radius:8px;padding:16px 22px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
                        f'<div style="font-size:11px;font-weight:800;letter-spacing:2.5px;text-transform:uppercase;'
                        f'color:{_edge_bord};margin-bottom:6px">{_edge_label}</div>'
                        f'<div style="font-size:14px;color:#2c2c2c;line-height:1.8">{_edge_msg}</div>'
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
                                x=(_hg1['Round_num'] - 1), y=_hg1['Exp_Votes'].round(1),
                                name=_ha, mode='lines+markers',
                                line=dict(color='#34d399', width=2.5),
                                marker=dict(size=7, color='#34d399'),
                                hovertemplate='<b>' + _ha + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        if not _hg2.empty:
                            _fig_h2h.add_trace(go.Scatter(
                                x=(_hg2['Round_num'] - 1), y=_hg2['Exp_Votes'].round(1),
                                name=_hb, mode='lines+markers',
                                line=dict(color='#94a3b8', width=2.5),
                                marker=dict(size=7, color='#94a3b8'),
                                hovertemplate='<b>' + _hb + '</b><br>Round %{x}<br>%{y:.1f} exp votes<extra></extra>',
                            ))
                        _fig_h2h.update_layout(
                            plot_bgcolor='#e8f0f8', paper_bgcolor='#e8f0f8', font_color='#2c2c2c',
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
                _vc2   = '#34d399' if _ma >= _mb else '#94a3b8'

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
                    f'<div style="background:#f0ece4;border:1px solid #ddd5c5;border-left:5px solid {_vc2};'
                    f'border-radius:8px;padding:20px 24px;margin:6px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
                    f'<div style="font-size:14px;color:#2c2c2c;line-height:2;">'
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

    # ── title bar ────────────────────────────────────────────
    _badge_class = "live-badge" if _lt_live else "live-badge-off"
    _dot_lbl     = "LIVE" if _lt_live else "OFF-SEASON"
    st.markdown(
        f'<div class="title-bar" style="display:flex;align-items:center;justify-content:space-between">'
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<h2 style="color:#2c2c2c;margin:0">Live Tracker</h2>'
        f'<span class="{_badge_class}">{_dot_lbl}</span>'
        f'</div>'
        f'<p style="color:#94a3b8;margin:0;font-size:13px">{_lt_sn}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── controls row ─────────────────────────────────────────
    _ctrl_l, _ctrl_r = st.columns([3, 7])
    with _ctrl_l:
        _lt_auto = st.checkbox("Auto-refresh every 60 s", value=False, key="lt_auto_refresh")
    with _ctrl_r:
        _lt_ts = _time.strftime("%H:%M:%S")
        st.markdown(
            f'<p style="color:#94a3b8;font-size:12px;margin:6px 0 0 0">'
            f'Last fetched: {_lt_ts} &nbsp;·&nbsp; '
            f'<a href="https://www.afl.com.au/brownlow-medal/live-tracker" target="_blank" '
            f'style="color:#34d399">AFL.com.au tracker ↗</a></p>',
            unsafe_allow_html=True,
        )

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
        # ── metrics strip ────────────────────────────────────
        _lt_rlabel = "OR" if _lt_last == 0 else f"Round {_lt_last}"
        _lt_leader = _lt_df.iloc[0]["Player"] if len(_lt_df) else "—"
        _lt_leader_votes = int(_lt_df.iloc[0]["Total_Votes"]) if len(_lt_df) else 0
        _lt_margin = (
            _lt_leader_votes - int(_lt_df.iloc[1]["Total_Votes"])
            if len(_lt_df) > 1 else 0
        )
        _lt_with_votes = int((_lt_df["Total_Votes"] > 0).sum())

        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        with _mc1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Last Round Counted</div>'
                f'<div class="metric-value">{_lt_rlabel}</div>'
                f'<div class="metric-sub">{"Count in progress" if _count_night else "Prediction Mode — Live votes will appear on count night"}</div></div>',
                unsafe_allow_html=True,
            )
        with _mc2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Current Leader</div>'
                f'<div class="metric-value" style="font-size:16px">{_lt_leader}</div>'
                f'<div class="metric-sub"><span class="counter" data-target="{_lt_leader_votes}">{_lt_leader_votes}</span> votes</div></div>',
                unsafe_allow_html=True,
            )
        with _mc3:
            _margin_abs = abs(_lt_margin)
            _margin_sign = "+" if _lt_margin >= 0 else "−"
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Lead Margin</div>'
                f'<div class="metric-value">{_margin_sign}<span class="counter" data-target="{_margin_abs}">{_margin_abs}</span></div>'
                f'<div class="metric-sub">ahead of 2nd place</div></div>',
                unsafe_allow_html=True,
            )
        with _mc4:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Players with Votes</div>'
                f'<div class="metric-value"><span class="counter" data-target="{_lt_with_votes}">{_lt_with_votes}</span></div>'
                f'<div class="metric-sub">of {len(_lt_df)} tracked</div></div>',
                unsafe_allow_html=True,
            )

        # ── leaderboard + feed ────────────────────────────────
        st.markdown('<div class="section-header">Running Leaderboard</div>', unsafe_allow_html=True)
        _lb_col, _feed_col = st.columns([3, 2])

        with _lb_col:
            _lt_show = _lt_df[_lt_df["Total_Votes"] > 0].head(25).copy()
            if _lt_show.empty:
                _lt_show = _lt_df.head(25).copy()

            # Format last-vote round label
            def _fmt_rnd(v):
                if pd.isna(v):
                    return "—"
                return "OR" if int(v) == 0 else f"Rd {int(v)}"

            _lt_disp = pd.DataFrame({
                "#":        _lt_show["Rank"].astype(int),
                "Player":   _lt_show["Player"],
                "Team":     _lt_show["Team"],
                "Votes":    _lt_show["Total_Votes"].astype(int),
                "Last Rd":  _lt_show["Last_Vote_Round"].apply(_fmt_rnd),
            })

            def _lt_row_style(row):
                base = "background-color:{bg};color:{fg};font-weight:{fw};"
                if row["#"] == 1:
                    return [base.format(bg="#34d399", fg="#e8f0f8", fw="700")] * len(row)
                elif row["#"] <= 3:
                    return [base.format(bg="#e8f0dd", fg="#2c2c2c", fw="600")] * len(row)
                return [""] * len(row)

            st.dataframe(
                _lt_disp.style
                    .apply(_lt_row_style, axis=1)
                    .set_table_styles(_TABLE_STYLES)
                    .hide(axis="index"),
                use_container_width=True,
                height=min(600, 36 * len(_lt_disp) + 40),
                key="lt_leaderboard_df",
            )

        with _feed_col:
            st.markdown('<div class="section-header">Latest Votes</div>', unsafe_allow_html=True)
            if _lt_feed:
                for _fi in _lt_feed:
                    st.markdown(
                        f'<div style="background:#f0ece4;border:1px solid #ddd5c5;border-radius:6px;'
                        f'padding:8px 12px;margin-bottom:6px;font-size:13px;color:#2c2c2c">'
                        f'{_fi}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="color:#94a3b8;font-size:13px;padding:12px 0">'
                    'No votes announced yet.</div>',
                    unsafe_allow_html=True,
                )

        # ── top 10 bar chart ──────────────────────────────────
        st.markdown('<div class="section-header">Top 10 — Votes Tally</div>', unsafe_allow_html=True)
        _lt_top10 = _lt_df[_lt_df["Total_Votes"] > 0].head(10)
        if _lt_top10.empty:
            _lt_top10 = _lt_df.head(10)
        _lt_colours = [
            "#34d399" if i == 0 else ("#6b7c3a" if i < 3 else "#94a3b8")
            for i in range(len(_lt_top10))
        ]
        _fig_lt_bar = go.Figure(go.Bar(
            y=_lt_top10["Player"].tolist()[::-1],
            x=_lt_top10["Total_Votes"].tolist()[::-1],
            orientation="h",
            marker_color=_lt_colours[::-1],
            text=[str(int(v)) for v in _lt_top10["Total_Votes"].tolist()[::-1]],
            textposition="outside",
            textfont=dict(color="#2c2c2c", size=12),
            hovertemplate="%{y}: %{x} votes<extra></extra>",
        ))
        _fig_lt_bar.update_layout(
            height=340,
            paper_bgcolor="#e8f0f8", plot_bgcolor="#e8f0f8",
            margin=dict(l=0, r=40, t=10, b=10),
            xaxis=dict(showgrid=True, gridcolor="#ede8df", tickfont=dict(color="#6c6c6c")),
            yaxis=dict(tickfont=dict(color="#2c2c2c", size=12)),
            font=dict(family="sans-serif"),
        )
        _fig_lt_bar = apply_chart_theme(_fig_lt_bar)
        st.plotly_chart(_fig_lt_bar, use_container_width=True, key="lt_bar_chart")

        # ── model vs tracker comparison ───────────────────────
        st.markdown('<div class="section-header">Our Model vs AFL Tracker</div>', unsafe_allow_html=True)
        _lt_proj = load_season_projection()
        if _lt_proj is not None and "Exp_Total_Votes" in _lt_proj.columns:
            _lt_cmp = _lt_df[_lt_df["Total_Votes"] > 0].head(30)[["Player", "Team", "Total_Votes"]].copy()
            _lt_cmp = _lt_cmp.merge(
                _lt_proj[["Player", "Exp_Total_Votes"]].rename(columns={"Exp_Total_Votes": "Model_Votes"}),
                on="Player", how="left",
            )
            _lt_cmp["Model_Votes"] = _lt_cmp["Model_Votes"].round(1)
            _lt_cmp["Delta"] = (_lt_cmp["Total_Votes"] - _lt_cmp["Model_Votes"]).round(1)

            def _lt_delta_fmt(v):
                if pd.isna(v):
                    return "—"
                return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"

            _lt_cmp_disp = pd.DataFrame({
                "Player":       _lt_cmp["Player"],
                "Team":         _lt_cmp["Team"],
                "Tracker Votes": _lt_cmp["Total_Votes"].astype(int),
                "Model Pred":   _lt_cmp["Model_Votes"].apply(
                    lambda v: f"{v:.1f}" if pd.notna(v) else "—"
                ),
                "Delta":        _lt_cmp["Delta"].apply(_lt_delta_fmt),
            })

            def _lt_cmp_style(row):
                try:
                    raw = _lt_cmp.loc[_lt_cmp["Player"] == row["Player"], "Delta"].values
                    d = float(raw[0]) if len(raw) else 0
                except Exception:
                    d = 0
                if d > 2:
                    return ["", "", "", "", "color:#34d399;font-weight:700"] * 1
                elif d < -2:
                    return ["", "", "", "", "color:#8b1a1a;font-weight:700"] * 1
                return [""] * 5

            st.dataframe(
                _lt_cmp_disp.style
                    .apply(_lt_cmp_style, axis=1)
                    .set_table_styles(_TABLE_STYLES)
                    .hide(axis="index"),
                use_container_width=True,
                key="lt_cmp_df",
            )
            st.caption(
                "Tracker Votes = AFL's current data · Model Pred = our XGBoost season projection · "
                "Delta = Tracker minus Model (green = tracker ahead, red = model overestimated)"
            )
        else:
            st.info("Run predict_2026.py to enable model comparison.")

    # ── auto-refresh ─────────────────────────────────────────
    if _lt_auto:
        _time.sleep(60)
        st.rerun()

# ════════════════════════════════════════════════════════════
# MODEL COMPARISON
# ════════════════════════════════════════════════════════════
if _page == 'Model Comparison':
    st.markdown(
        '<div class="title-bar"><h2 style="color:#e8f0f8;margin:0">Model Comparison — 2026</h2>'
        '<p style="color:#94a3b8;margin:4px 0 0 0">'
        'Cha Ching · AFL Predictor · Betfair · Wheelo · ESPN — five models, one view</p></div>',
        unsafe_allow_html=True,
    )

    # ── Load all five data sources ────────────────────────────

    _mc_tab1, _mc_tab2 = st.tabs(['2026 (Live)', 'Historical (2021–2025)'])

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
        _MC_SUBS = {
            'Cha Ching':     'Season XGBoost model',
            'AFL Predictor': 'AFL live API' + (' · pre-count' if not _mc_afl_has_votes else ''),
            'Betfair':       'Betfair vote predictor',
            'Wheelo':        'Wheelo ratings system',
            'ESPN':          'ESPN vote predictor',
        }
        _MC_ERRS = {
            'Betfair': _mc_bf_err,
            'ESPN':    _mc_espn_err,
        }

        # ── Five metric cards ─────────────────────────────────────
        _mc_card_cols = st.columns(5)
        for _cc, (_mlabel, _mdf, _mrc, _mcsv, _mcls) in zip(_mc_card_cols, _MC_MODELS):
            with _cc:
                if not _mdf.empty:
                    _top1 = _mdf.iloc[0]['Player']
                    _color = "#34d399" if _mcls == "metric-card-primary" else "#94a3b8"
                    _chg = _rank_change_html(_mcsv, _top1) if _mcsv else ''
                    _ts = _file_ts(_mcsv) if _mcsv else ''
                else:
                    _err = _MC_ERRS.get(_mlabel, '')
                    _top1 = f"Unavail. — {_err[:40]}" if _err else "Data unavailable"
                    _color, _chg, _ts = "#6c6c6c", '', _file_ts(_mcsv) if _mcsv else ''
                _ts_html = (f'<div style="font-size:10px;color:#aaaaaa;margin-top:4px">'
                            f'Updated {_ts}</div>') if _ts else ''
                st.markdown(
                    f'<div class="{_mcls}">'
                    f'<div class="metric-label">{_mlabel}</div>'
                    f'<div class="metric-value" style="font-size:16px;color:{_color};line-height:1.2">'
                    f'{_top1}{_chg}</div>'
                    f'<div class="metric-sub">{_MC_SUBS[_mlabel]}</div>'
                    f'{_ts_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">Consensus Ranking — Top 25 Players</div>',
                    unsafe_allow_html=True)

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

        _cmp_disp = pd.DataFrame({
            'Consensus': _pc_df['Consensus'].astype(str),
            'Player':    _pc_df['Player'],
            'Cha Ching': _pc_df['_cc'].apply(_rk),
            'AFL':       _pc_df['_afl'].apply(_rk),
            'Betfair':   _pc_df['_bf'].apply(_rk),
            'Wheelo':    _pc_df['_wh'].apply(_rk),
            'ESPN':      _pc_df['_espn'].apply(_rk),
            '_cc_r':     _pc_df['_cc'],
            '_cons_f':   _pc_df['_cons'],
        })

        _green_mask = _cmp_disp.apply(
            lambda row: (
                int(row['Consensus']) <= 10
                and all(row[c] != '—' and int(row[c]) <= 10
                        for c in ['Cha Ching', 'AFL', 'Betfair', 'Wheelo', 'ESPN']
                        if row[c] != '—')
                and sum(1 for c in ['Cha Ching', 'AFL', 'Betfair', 'Wheelo', 'ESPN']
                        if row[c] != '—') == 5
            ), axis=1
        ).values
        _brown_mask = _cmp_disp.apply(
            lambda row: (
                not bool(_green_mask[row.name])
                and _rk_valid(row['_cc_r'])
                and abs(int(row['Consensus']) - int(row['_cc_r'])) >= 5
            ), axis=1
        ).values

        _cmp_show = _cmp_disp[['Consensus', 'Player', 'Cha Ching', 'AFL', 'Betfair', 'Wheelo', 'ESPN']].copy()

        def _mc_cmp_style(row):
            idx = row.name
            if _green_mask[idx]:
                return ['background-color:rgba(52,211,153,0.15);color:#34d399;font-weight:700'] * len(row)
            if _brown_mask[idx]:
                return ['background-color:rgba(240,180,41,0.12);color:#f0b429;font-weight:700'] * len(row)
            return [''] * len(row)

        st.dataframe(
            _cmp_show.style.apply(_mc_cmp_style, axis=1).set_table_styles(_TABLE_STYLES).hide(axis='index'),
            use_container_width=True,
            key='mc_cmp_table',
        )
        st.markdown(
            '<div style="display:flex;gap:20px;margin-top:6px;font-size:12px;color:#94a3b8;">'
            '<span><span style="display:inline-block;width:12px;height:12px;'
            'background:rgba(52,211,153,0.20);border:1px solid #34d399;'
            'border-radius:2px;vertical-align:middle;margin-right:5px"></span>'
            'All 5 models agree — player top 10 in every model</span>'
            '<span><span style="display:inline-block;width:12px;height:12px;'
            'background:rgba(240,180,41,0.18);border:1px solid #f0b429;'
            'border-radius:2px;vertical-align:middle;margin-right:5px"></span>'
            'Cha Ching rank differs 5+ places from consensus</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Summary stats ─────────────────────────────────────────
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">Consensus Summary</div>', unsafe_allow_html=True)

        _avail_models = [(_mdf, _mrc) for _, _mdf, _mrc, _, _ in _MC_MODELS if not _mdf.empty]
        _n_models = len(_avail_models)

        def _in_top10(df, match_key, rc):
            r = _mc_lookup(df, match_key, rc)
            return r is not None and r <= 10

        _all_agree_count = sum(
            1 for _, row in _pc_df[_pc_df['Consensus'] <= 10].iterrows()
            if all(_in_top10(df, row['_mk'], rc) for df, rc in _avail_models)
        )
        _3of_agree_count = sum(
            1 for _, row in _pc_df[_pc_df['Consensus'] <= 10].iterrows()
            if sum(_in_top10(df, row['_mk'], rc) for df, rc in _avail_models) >= max(3, _n_models - 1)
        )
        _cc_outlier_count = int(sum(_brown_mask))

        _ss1, _ss2, _ss3 = st.columns(3)
        with _ss1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">All {_n_models} models agree</div>'
                f'<div class="metric-value">{_all_agree_count} of top 10</div>'
                f'<div class="metric-sub">Players top 10 in every available model</div></div>',
                unsafe_allow_html=True,
            )
        with _ss2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">{max(3,_n_models-1)} of {_n_models} agree</div>'
                f'<div class="metric-value">{_3of_agree_count} of top 10</div>'
                f'<div class="metric-sub">Top 10 in at least {max(3,_n_models-1)} models</div></div>',
                unsafe_allow_html=True,
            )
        with _ss3:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Cha Ching outliers</div>'
                f'<div class="metric-value">{_cc_outlier_count} of top 25</div>'
                f'<div class="metric-sub">CC rank differs 5+ from consensus rank</div></div>',
                unsafe_allow_html=True,
            )

        # ── Rank heatmap with team colour dots ───────────────────
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-header">Rank Heatmap — Top 20 by Cha Ching (team colour dots)</div>',
            unsafe_allow_html=True,
        )

        if not _mc_cc_df.empty and '_match_key' in _mc_cc_df.columns:
            _hmap_top20   = _mc_cc_df.head(20)
            _hmap_players = _hmap_top20['Player'].tolist()       # display labels
            _hmap_mkeys   = _hmap_top20['_match_key'].tolist()   # lookup keys
            _hmap_models  = ['Cha Ching', 'AFL', 'Betfair', 'Wheelo', 'ESPN']

            def _mk_series(df, col):
                """Build a _match_key → rank Series, deduped so .get() always returns a scalar."""
                if df.empty or '_match_key' not in df.columns:
                    return pd.Series(dtype=float)
                s = df.set_index('_match_key')[col]
                # Keep first occurrence when duplicate match keys exist
                return s[~s.index.duplicated(keep='first')]

            def _scalar_rank(series, key, sentinel):
                """Return a plain float rank for key, never a Series."""
                val = series.get(key, sentinel)
                if isinstance(val, pd.Series):
                    val = val.iloc[0] if not val.empty else sentinel
                return float(pd.to_numeric(val, errors='coerce') if not isinstance(val, float) else val or sentinel)

            _hmap_rank_s = [
                _mk_series(_mc_cc_df,   'CC_Rank'),
                _mk_series(_mc_afl_df,  'AFL_Rank'),
                _mk_series(_mc_bf_df,   'BF_Rank'),
                _mk_series(_mc_wh_df,   'WH_Rank'),
                _mk_series(_mc_espn_df, 'ESPN_Rank'),
            ]
            _hmap_z_raw = np.array([
                [_scalar_rank(_s, _mk, _MC_SEN) for _s in _hmap_rank_s]
                for _mk in _hmap_mkeys
            ])
            _hmap_z_inv = float(_MC_SEN + 1) - _hmap_z_raw
            _hmap_text  = [
                [str(int(v)) if v < _MC_SEN else 'N/A' for v in row]
                for row in _hmap_z_raw.tolist()
            ]

            _fig_hmap = go.Figure(data=go.Heatmap(
                z=_hmap_z_inv,
                x=_hmap_models,
                y=_hmap_players,
                colorscale=[[0, '#0f1923'], [0.3, '#1e3a4a'], [0.7, '#1a5c40'], [1, '#34d399']],
                zmin=1, zmax=float(_MC_SEN),
                showscale=False,
                text=_hmap_text,
                texttemplate='%{text}',
                textfont=dict(size=11, color='#e8f0f8'),
                hovertemplate='%{y}<br>%{x}: Rank %{text}<extra></extra>',
            ))

            # Team colour dots to the left of each row (x=-0.6, categorical axis)
            for _p, _pmk in zip(_hmap_players, _hmap_mkeys):
                _tc = _TEAM_COLOURS.get(_mc_cc_team.get(_pmk, ''), '#aaaaaa')
                _fig_hmap.add_annotation(
                    x=-0.6, y=_p,
                    xref='x', yref='y',
                    text='⬤',
                    showarrow=False,
                    font=dict(size=14, color=_tc),
                )

            _fig_hmap = apply_chart_theme(_fig_hmap)
            _fig_hmap.update_layout(
                height=640,
                margin=dict(l=200, r=30, t=50, b=40),
                xaxis=dict(
                    side='top',
                    tickfont=dict(size=12, color='#34d399'),
                    range=[-1, len(_hmap_models) - 0.5],
                ),
                yaxis=dict(autorange='reversed', tickfont=dict(size=11, color='#94a3b8')),
            )
            st.plotly_chart(_fig_hmap, use_container_width=True, key='mc_heatmap')
            st.caption(
                "Darker green = higher ranked. Numbers show rank position. "
                "'N/A' = player not ranked by that model. Coloured dots = team colour."
            )
        else:
            st.info("Heatmap requires Cha Ching predictions/season_2026.csv.")

        # ── Scatter: Cha Ching vs AFL rank ───────────────────────
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-header">Cha Ching vs AFL Predictor — Rank Scatter</div>',
            unsafe_allow_html=True,
        )

        if not _mc_cc_df.empty and not _mc_afl_df.empty and '_match_key' in _mc_cc_df.columns:
            _sc_cc  = _mc_cc_df.head(20).copy()
            _sc_mrg = _sc_cc.merge(
                _mc_afl_df[['_match_key', 'AFL_Rank']], on='_match_key', how='left'
            )
            _sc_mrg['AFL_Rank'] = _sc_mrg['AFL_Rank'].fillna(_MC_SEN)
            _sc_mrg['CC_Votes'] = _sc_mrg['CC_Votes'].round(1)

            _fig_sc = go.Figure()
            _sc_max = 22
            _fig_sc.add_trace(go.Scatter(
                x=list(range(1, _sc_max + 1)),
                y=list(range(1, _sc_max + 1)),
                mode='lines',
                line=dict(color='#4a5a6a', dash='dash', width=1.5),
                name='Perfect agreement',
                hoverinfo='skip',
            ))
            _fig_sc.add_trace(go.Scatter(
                x=_sc_mrg['CC_Rank'].tolist(),
                y=_sc_mrg['AFL_Rank'].tolist(),
                mode='markers+text',
                text=_sc_mrg['Player'].tolist(),
                textposition='top center',
                textfont=dict(size=9, color='#e8f0f8'),
                marker=dict(size=10, color='#34d399', opacity=0.78,
                            line=dict(color='#2a4a5a', width=1.2)),
                name='Players',
                hovertemplate='%{text}<br>CC Rank: %{x}<br>AFL Rank: %{y}<extra></extra>',
            ))
            _fig_sc = apply_chart_theme(_fig_sc)
            _fig_sc.update_layout(
                height=540,
                xaxis=dict(
                    title='Cha Ching Rank',
                    zeroline=False,
                    tickmode='linear', tick0=1, dtick=2,
                    range=[0.5, _sc_max + 0.5],
                ),
                yaxis=dict(
                    title='AFL Predictor Rank',
                    autorange='reversed',
                    zeroline=False,
                    tickmode='linear', tick0=1, dtick=2,
                ),
                legend=dict(orientation='h', y=1.06),
                margin=dict(l=70, r=30, t=60, b=70),
            )
            st.plotly_chart(_fig_sc, use_container_width=True, key='mc_scatter')
            _afl_note_sc = (" Note: AFL predictor has no live votes yet — ranks not meaningful."
                            if not _mc_afl_has_votes else "")
            st.caption(
                "Rank 1 (best) is at top-left. Points above the dashed line: AFL ranks that player "
                "higher than Cha Ching. Points below: Cha Ching ranks them higher." + _afl_note_sc
            )
        else:
            st.info("Scatter plot requires both Cha Ching and AFL Predictor data.")

# ── Global footer ────────────────────────────────────────────
st.markdown(
    '<div style="border-top:1px solid #ddd5c5;margin-top:40px;padding:14px 0;'
    'color:#94a3b8;font-size:10px;letter-spacing:1.2px;text-align:center;'
    'text-transform:uppercase;font-weight:600;">'
    f'Model v4.0 &nbsp;&nbsp;·&nbsp;&nbsp; Data: {_TRAIN_MIN}–{_TRAIN_MAX} &nbsp;&nbsp;·&nbsp;&nbsp; 93 features &nbsp;&nbsp;·&nbsp;&nbsp; MAE 0.0904'
    '</div>',
    unsafe_allow_html=True,
)