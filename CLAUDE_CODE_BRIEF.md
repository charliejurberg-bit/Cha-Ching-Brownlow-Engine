# Cha Ching — Midnight Turf Design System
# Implementation brief for Claude Code
# File: C:\Users\User\Python\brownlow_engine\dashboard.py

---

## What this does

Full visual redesign of the Cha Ching Brownlow Medal dashboard.
- New colour scheme: Midnight Turf (dark navy + emerald + gold)
- New fonts: Sora (headings) + DM Mono (numbers) via Google Fonts
- Global CSS reskin of all Streamlit widgets
- Animated Home page with staggered reveals

---

## Step 1 — Add colour tokens

Find the existing COLORS dict (search: `"background": "#faf7f2"`) and replace the entire dict with:

```python
COLORS = {
    "bg_base":       "#0f1923",
    "bg_surface":    "#152533",
    "bg_elevated":   "#1e3a4a",
    "bg_subtle":     "#1a2d3d",
    "accent":        "#34d399",
    "accent_dim":    "#1a6b4a",
    "accent_glow":   "rgba(52,211,153,0.12)",
    "gold":          "#f0b429",
    "gold_dim":      "#5c420a",
    "red":           "#e05252",
    "red_dim":       "#5c1f1f",
    "blue":          "#4a90c4",
    "text_primary":  "#e8f0f8",
    "text_secondary":"#94a3b8",
    "text_muted":    "#4a5a6a",
    "border":        "#2a4a5a",
    "border_subtle": "#1e3040",
}
```

---

## Step 2 — Add inject_global_css() function

Add this function near the top of dashboard.py, after imports and the COLORS dict.
Call it once at the very start of your main() function: `inject_global_css()`

```python
def inject_global_css():
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1923 !important;
    color: #e8f0f8;
    font-family: 'Sora', sans-serif;
}
[data-testid="stAppViewContainer"] > .main {
    background-color: #0f1923 !important;
}
[data-testid="block-container"] {
    padding-top: 1.5rem !important;
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
</style>
""", unsafe_allow_html=True)
```

---

## Step 3 — Replace render_page_home()

Find the existing home page render function (around line 1624) and replace it entirely with:

```python
def render_page_home():
    SEASON = 2026
    CURRENT_ROUND = 10  # UPDATE THIS EACH WEEK

    df = load_season(SEASON)
    odds_df = load_best_odds()

    if df is not None and not df.empty:
        top5 = (
            df.groupby("player")["predicted_votes"]
            .sum()
            .reset_index()
            .sort_values("predicted_votes", ascending=False)
            .head(5)
        )
    else:
        top5 = pd.DataFrame(columns=["player", "predicted_votes"])

    leader_name  = top5.iloc[0]["player"] if len(top5) else "—"
    leader_votes = top5.iloc[0]["predicted_votes"] if len(top5) else 0

    leader_odds = "—"
    if not odds_df.empty and "player" in odds_df.columns:
        match = odds_df[odds_df["player"] == leader_name]
        if not match.empty:
            num_cols = odds_df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                leader_odds = f"${float(match.iloc[0][num_cols[0]]):.2f}"

    rounds_remaining = 23 - CURRENT_ROUND
    season_pct = int((CURRENT_ROUND / 23) * 100)

    # Hero
    st.markdown(f"""
<div style="padding:40px 0 32px;animation:fadeSlideUp 500ms cubic-bezier(0.23,1,0.32,1) both;">
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

    # Season progress bar
    st.markdown(f"""
<div style="margin-bottom:32px;animation:fadeSlideUp 500ms 80ms cubic-bezier(0.23,1,0.32,1) both;">
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

    # Stat cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
<div class="mt-card" style="background:#152533;border:1px solid #2a4a5a;
            border-left:3px solid #f0b429;border-radius:10px;padding:16px 18px;">
  <div style="font-size:10px;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;
              color:#94a3b8;margin-bottom:6px;">Predicted winner</div>
  <div style="font-size:20px;font-weight:700;color:#f0b429;
              font-family:'Sora',sans-serif;letter-spacing:-0.02em;">{leader_name}</div>
  <div style="font-size:12px;color:#94a3b8;margin-top:4px;">{leader_votes:.1f} pred. votes</div>
</div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
<div class="mt-card" style="background:#152533;border:1px solid #2a4a5a;
            border-left:3px solid #34d399;border-radius:10px;padding:16px 18px;">
  <div style="font-size:10px;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;
              color:#94a3b8;margin-bottom:6px;">Best odds</div>
  <div style="font-size:20px;font-weight:700;color:#34d399;
              font-family:'Sora',sans-serif;letter-spacing:-0.02em;">{leader_odds}</div>
  <div style="font-size:12px;color:#94a3b8;margin-top:4px;">{leader_name} to win</div>
</div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
<div class="mt-card" style="background:#152533;border:1px solid #2a4a5a;
            border-left:3px solid #4a90c4;border-radius:10px;padding:16px 18px;">
  <div style="font-size:10px;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;
              color:#94a3b8;margin-bottom:6px;">Model accuracy</div>
  <div style="font-size:20px;font-weight:700;color:#e8f0f8;
              font-family:'Sora',sans-serif;letter-spacing:-0.02em;">86%</div>
  <div style="font-size:12px;color:#94a3b8;margin-top:4px;">top-10 · MAE 0.09</div>
</div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
<div class="mt-card" style="background:#152533;border:1px solid #2a4a5a;
            border-left:3px solid #e05252;border-radius:10px;padding:16px 18px;">
  <div style="font-size:10px;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;
              color:#94a3b8;margin-bottom:6px;">Round</div>
  <div style="font-size:20px;font-weight:700;color:#e8f0f8;
              font-family:'Sora',sans-serif;letter-spacing:-0.02em;">
    {CURRENT_ROUND} <span style="font-size:13px;color:#4a5a6a;">/ 23</span>
  </div>
  <div style="font-size:12px;color:#94a3b8;margin-top:4px;">{rounds_remaining} rounds remaining</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # Top 5 leaderboard strip
    st.markdown("""
<div style="font-size:11px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;
            color:#4a5a6a;padding-bottom:10px;border-bottom:1px solid #2a4a5a;margin-bottom:14px;">
  Top 5 predictions · 2026
</div>""", unsafe_allow_html=True)

    medals = ["🥇", "🥈", "🥉", "4", "5"]
    medal_colors = ["#f0b429", "#94a3b8", "#a0632a", "#4a5a6a", "#4a5a6a"]

    if not top5.empty:
        max_votes = top5["predicted_votes"].max()
        for i, (_, row) in enumerate(top5.iterrows()):
            pct = int((row["predicted_votes"] / max_votes) * 100) if max_votes > 0 else 0
            delay = 240 + i * 50
            color = medal_colors[i]
            is_top = i == 0
            st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;
            background:{'#1a3a2a' if is_top else '#152533'};
            border:1px solid {'#34d399' if is_top else '#2a4a5a'};
            border-radius:8px;margin-bottom:6px;
            animation:fadeSlideUp 350ms {delay}ms cubic-bezier(0.23,1,0.32,1) both;">
  <span style="font-size:{'16px' if i < 3 else '12px'};min-width:22px;text-align:center;
               color:{color};font-weight:700;">{medals[i]}</span>
  <span style="flex:1;font-size:13px;font-weight:{'600' if i < 2 else '400'};
               color:{'#e8f0f8' if i < 2 else '#94a3b8'};font-family:'Sora',sans-serif;">
    {row['player']}
  </span>
  <div style="width:140px;height:4px;background:#1e3a4a;border-radius:2px;overflow:hidden;">
    <div style="height:100%;width:{pct}%;background:{color};border-radius:2px;opacity:0.8;"></div>
  </div>
  <span style="font-size:13px;font-weight:600;min-width:36px;text-align:right;
               color:{color};font-family:'DM Mono',monospace;">
    {row['predicted_votes']:.1f}
  </span>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Quick nav cards
    st.markdown("""
<div style="font-size:11px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;
            color:#4a5a6a;padding-bottom:10px;border-bottom:1px solid #2a4a5a;margin-bottom:14px;">
  Quick navigation
</div>""", unsafe_allow_html=True)

    nav_items = [
        ("📊", "Leaderboard",    "Full season rankings",    "#34d399"),
        ("👤", "Player Profile", "Deep dive any player",    "#4a90c4"),
        ("💰", "Value Finder",   "Model vs market odds",    "#f0b429"),
        ("🎯", "Cha Ching Tips", "Curated betting tips",    "#e05252"),
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
```

---

## Step 4 — Wire inject_global_css() into main()

In your main() function, add this as the very first line before any page routing:

```python
inject_global_css()
```

---

## Step 5 — Update Plotly chart themes

Any existing `go.Figure()` or `px.*()` calls need their layout updated to match.
Add a helper at the top of dashboard.py and call it on every figure before st.plotly_chart():

```python
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
        margin=dict(l=16, r=16, t=40, b=16),
    )
    fig.update_traces(marker_line_width=0)
    return fig
```

Usage: `fig = apply_chart_theme(fig)` then `st.plotly_chart(fig, use_container_width=True, key="chart_001")`

---

## Colour reference (use everywhere)

| Token          | Hex       | Use for                              |
|----------------|-----------|--------------------------------------|
| bg_base        | #0f1923   | Page background                      |
| bg_surface     | #152533   | Cards, panels, sidebar items         |
| bg_elevated    | #1e3a4a   | Hover states, table headers          |
| accent         | #34d399   | Primary CTA, positive values, links  |
| gold           | #f0b429   | #1 prediction, medals, top bets      |
| red            | #e05252   | Losses, negative delta, warnings     |
| blue           | #4a90c4   | Secondary info, model stats          |
| text_primary   | #e8f0f8   | Headings, important numbers          |
| text_secondary | #94a3b8   | Labels, body text, subtext           |
| text_muted     | #4a5a6a   | Section headers, disabled, placeholders |
| border         | #2a4a5a   | Card borders, dividers               |
| border_subtle  | #1e3040   | Table row separators                 |

---

## Fonts

- Headings / UI: `Sora` (loaded via Google Fonts in inject_global_css)
- Numbers / code / odds: `DM Mono` (loaded via Google Fonts in inject_global_css)
- No local install needed — loaded at runtime.

---

## CURRENT_ROUND

In render_page_home(), update this constant manually each week:
```python
CURRENT_ROUND = 10  # change to 11 after Round 11, etc.
```

---

## Notes for Claude Code

- Do NOT change any data loading logic, model logic, or CSV paths.
- Do NOT rename any existing functions other than render_page_home().
- inject_global_css() is new — add it, don't replace anything.
- apply_chart_theme() is new — add it and apply to all existing st.plotly_chart() calls.
- The COLORS dict replaces the existing one at the top of the file.
- All st.markdown() calls use unsafe_allow_html=True — this is intentional.
- Keep all existing st.plotly_chart(key=...) unique keys — do not remove or duplicate them.
