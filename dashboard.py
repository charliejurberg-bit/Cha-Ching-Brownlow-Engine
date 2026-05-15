"""
Brownlow Medal Prediction Dashboard v3.0
Run: python -m streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import subprocess
import sys

st.set_page_config(page_title="Brownlow Medal Engine", page_icon="🏅", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #252940);
        border: 1px solid #3d4566; border-radius: 12px;
        padding: 16px 20px; margin: 6px 0;
    }
    .metric-label { color: #8892b0; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .metric-value { color: #ccd6f6; font-size: 26px; font-weight: 700; margin-top: 4px; }
    .metric-sub { color: #64ffda; font-size: 13px; margin-top: 2px; }
    .title-bar {
        background: linear-gradient(135deg, #1a1f35, #0d1b2a);
        border-left: 4px solid #64ffda;
        padding: 20px 24px; border-radius: 8px; margin-bottom: 24px;
    }
    .section-header {
        color: #64ffda; font-size: 13px; font-weight: 600;
        letter-spacing: 2px; text-transform: uppercase;
        margin: 24px 0 12px 0;
        border-bottom: 1px solid #1e2130; padding-bottom: 8px;
    }
    .dna-card {
        background: #1a1f35; border: 1px solid #2d3561;
        border-radius: 10px; padding: 14px 18px; margin: 4px 0;
    }
    .dna-label { color: #8892b0; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
    .dna-value { color: #64ffda; font-size: 22px; font-weight: 700; }
    .dna-sub { color: #ccd6f6; font-size: 12px; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────
PRED_DIR = "predictions"
AVAILABLE_SEASONS = []
if os.path.exists(PRED_DIR):
    for f in os.listdir(PRED_DIR):
        if f.startswith("season_") and f.endswith(".csv"):
            try:
                AVAILABLE_SEASONS.append(int(f.replace("season_","").replace(".csv","")))
            except: pass
AVAILABLE_SEASONS = sorted(AVAILABLE_SEASONS, reverse=True)

@st.cache_data
def load_season(season):
    path = f"{PRED_DIR}/season_{season}.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_game(season):
    path = f"{PRED_DIR}/game_level_{season}.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_importance():
    path = f"{PRED_DIR}/feature_importance.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

@st.cache_data
def load_all_historical():
    frames = []
    for season in range(2015, 2026):
        path = f"{PRED_DIR}/game_level_{season}.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['Season'] = season
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else None

@st.cache_data
def compute_player_efficiency(season):
    """Calculate player-specific polling efficiency from game level data"""
    df = load_game(season)
    if df is None:
        return None

    # Overall efficiency
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

    # High disposal (30+) efficiency
    hd = df[df['Disposals'] >= 30].groupby('Player_Name').agg(
        HD_Games=('Round_num', 'count'),
        HD_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
        HD_Avg_Votes=('Brownlow.Votes', 'mean'),
    ).reset_index()

    # Win efficiency
    wins = df[df['Is_Win'] == 1].groupby('Player_Name').agg(
        Win_Games=('Round_num', 'count'),
        Win_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
        Win_Avg_Votes=('Brownlow.Votes', 'mean'),
    ).reset_index()

    # Loss efficiency
    losses = df[df['Is_Loss'] == 1].groupby('Player_Name').agg(
        Loss_Games=('Round_num', 'count'),
        Loss_Poll_Rate=('Brownlow.Votes', lambda x: (x > 0).mean()),
    ).reset_index()

    eff = overall.merge(hd, on='Player_Name', how='left')
    eff = eff.merge(wins, on='Player_Name', how='left')
    eff = eff.merge(losses, on='Player_Name', how='left')
    return eff

def load_odds():
    path = "data_2026/bookmaker_odds.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

def load_best_odds():
    path = "data_2026/best_odds.csv"
    return pd.read_csv(path) if os.path.exists(path) else None

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏅 Brownlow Engine")
    st.markdown("---")

    if not AVAILABLE_SEASONS:
        st.error("No predictions found. Run brownlow_model.py first.")
        st.stop()

    selected_season = st.selectbox("Season", AVAILABLE_SEASONS, index=0)
    is_2026 = (selected_season == 2026)

    page = st.radio("Navigate", [
        "📊 Leaderboard",
        "👤 Player Profile",
        "🧬 Player DNA",
        "🔍 Feature Importance",
        "📈 Poll Probability",
        "🎯 Value Finder",
        "🔬 Stat Filter",
    ])

    st.markdown("---")
    st.markdown("### 🔄 2026 Live Update")
    if st.button("▶ Run Update", use_container_width=True, type="primary"):
        with st.spinner("Fetching stats and odds..."):
            result = subprocess.run([sys.executable, "update.py"],
                                   capture_output=True, text=True, timeout=300)
        st.cache_data.clear()
        if result.returncode == 0:
            st.success("✅ Update complete!")
        else:
            st.warning("⚠ Finished with warnings.")
        if result.stdout:
            with st.expander("Output log"):
                st.code(result.stdout[-2000:])

    odds = load_odds()
    if odds is not None and 'scraped_at' in odds.columns:
        st.caption(f"Odds updated: {odds['scraped_at'].iloc[0]}")

    st.markdown("---")
    st.caption(f"Model v2.0 | Data: 2015–2025 | 62 features")

predictions = load_season(selected_season)
game_df = load_game(selected_season)
importance = load_importance()

if predictions is None:
    st.error(f"No predictions for {selected_season}. Run brownlow_model.py first.")
    st.stop()

# ── Page: Leaderboard ────────────────────────────────────────
if page == "📊 Leaderboard":
    live_tag = " 🔴 LIVE" if is_2026 else ""
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">📊 {selected_season} Brownlow Leaderboard{live_tag}</h2><p style="color:#8892b0;margin:4px 0 0 0">{"Projected votes through current round" if is_2026 else "Model predicted vs actual results"}</p></div>', unsafe_allow_html=True)

    top3 = predictions.head(3)
    medals = ['🥇','🥈','🥉']
    cols = st.columns(3)
    for i, (col, (_, row)) in enumerate(zip(cols, top3.iterrows())):
        actual_str = "TBC" if is_2026 else f"{int(row['Actual_Votes'])} actual"
        with col:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">{medals[i]} #{i+1} Predicted</div>
                <div class="metric-value">{row['Player_Name']}</div>
                <div class="metric-sub">{row['Team']} &nbsp;|&nbsp; {row['Exp_Total_Votes']:.1f} exp &nbsp;|&nbsp; {actual_str}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Full Leaderboard</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3,1])
    with col1: search = st.text_input("Search player", "")
    with col2: show_n = st.selectbox("Show", [20,50,100,200], index=0)

    display = predictions.copy()
    if search:
        display = display[display['Player_Name'].str.contains(search, case=False)]
    display = display.head(show_n).copy()
    display.insert(0, 'Rank', range(1, len(display)+1))
    display['Poll %'] = (display['Avg_Poll_Prob']*100).round(1)
    display['Exp Votes'] = display['Exp_Total_Votes'].round(1)
    display['3-vote games'] = display['Exp_3vote_games'].round(1)

    if is_2026:
        cols_show = ['Rank','Player_Name','Team','Games','Exp Votes','Poll %','3-vote games']
    else:
        display['Actual'] = display['Actual_Votes'].astype(int)
        display['Diff'] = (display['Exp Votes'] - display['Actual']).round(1)
        cols_show = ['Rank','Player_Name','Team','Games','Actual','Exp Votes','Diff','Poll %','3-vote games']

    st.dataframe(display[cols_show].rename(columns={'Player_Name':'Player'}),
                 use_container_width=True, hide_index=True)

    st.markdown(f'<div class="section-header">{"Projected — Top 20" if is_2026 else "Expected vs Actual — Top 20"}</div>', unsafe_allow_html=True)
    chart = predictions.head(20).copy()
    fig = go.Figure()
    if not is_2026:
        fig.add_trace(go.Bar(name='Actual', x=chart['Player_Name'], y=chart['Actual_Votes'],
                             marker_color='#8892b0', opacity=0.7))
    fig.add_trace(go.Bar(name='Model Expected', x=chart['Player_Name'],
                         y=chart['Exp_Total_Votes'].round(1), marker_color='#64ffda', opacity=0.9))
    fig.update_layout(barmode='group', plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                      font_color='#ccd6f6', legend=dict(orientation='h', y=1.1),
                      xaxis_tickangle=-35, margin=dict(t=20,b=120))
    st.plotly_chart(fig, use_container_width=True)

# ── Page: Player Profile ─────────────────────────────────────
elif page == "👤 Player Profile":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">👤 Player Profile — {selected_season}</h2><p style="color:#8892b0;margin:4px 0 0 0">Round by round breakdown with vote probability</p></div>', unsafe_allow_html=True)

    if game_df is None:
        st.error("No game-level data found.")
        st.stop()

    players = sorted(predictions['Player_Name'].tolist())
    selected_player = st.selectbox("Select player", players)

    if selected_player:
        player_games = game_df[game_df['Player_Name']==selected_player].copy().sort_values('Round_num')
        pred_row = predictions[predictions['Player_Name']==selected_player]

        # Summary cards
        if not pred_row.empty:
            row = pred_row.iloc[0]
            c1,c2,c3,c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Team</div><div class="metric-value" style="font-size:18px">{row["Team"]}</div></div>', unsafe_allow_html=True)
            with c2:
                val = int(row["Actual_Votes"]) if not is_2026 else int(row["Games"])
                lbl = "Actual Votes" if not is_2026 else "Games Played"
                st.markdown(f'<div class="metric-card"><div class="metric-label">{lbl}</div><div class="metric-value">{val}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">{"Model Expected" if not is_2026 else "Projected Total"}</div><div class="metric-value">{row["Exp_Total_Votes"]:.1f}</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Poll Prob</div><div class="metric-value">{row["Avg_Poll_Prob"]*100:.1f}%</div></div>', unsafe_allow_html=True)

        if not player_games.empty:
            # ── Round by round chart ─────────────────────────
            st.markdown('<div class="section-header">Round by Round — Votes & Poll Probability</div>', unsafe_allow_html=True)

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Actual votes bars (historical only)
            if not is_2026 and 'Brownlow.Votes' in player_games.columns:
                colors = []
                for v in player_games['Brownlow.Votes']:
                    if v == 3: colors.append('#64ffda')
                    elif v == 2: colors.append('#0096c7')
                    elif v == 1: colors.append('#48cae4')
                    else: colors.append('#2d3561')

                fig.add_trace(go.Bar(
                    x=player_games['Round_num'],
                    y=player_games['Brownlow.Votes'],
                    name='Actual Votes',
                    marker_color=colors,
                    opacity=0.85,
                    text=player_games['Brownlow.Votes'].apply(lambda v: str(int(v)) if v > 0 else ''),
                    textposition='outside',
                ), secondary_y=False)

            # Expected votes line
            fig.add_trace(go.Scatter(
                x=player_games['Round_num'],
                y=player_games['Exp_Votes'].round(2),
                name='Expected Votes',
                mode='lines+markers',
                line=dict(color='#ffd700', width=2, dash='dot'),
                marker=dict(size=6),
            ), secondary_y=False)

            # Poll probability line
            fig.add_trace(go.Scatter(
                x=player_games['Round_num'],
                y=(player_games['Poll_Prob']*100).round(1),
                name='Poll Probability %',
                mode='lines+markers',
                line=dict(color='#ff6b6b', width=2),
                marker=dict(size=7),
                fill='tozeroy',
                fillcolor='rgba(255,107,107,0.08)',
            ), secondary_y=True)

            fig.update_layout(
                plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                xaxis=dict(title='Round', dtick=1, gridcolor='#1e2130'),
                legend=dict(orientation='h', y=1.12, bgcolor='rgba(0,0,0,0)'),
                margin=dict(t=40, b=40),
                hovermode='x unified'
            )
            fig.update_yaxes(title_text="Votes", secondary_y=False,
                           range=[0, 4], gridcolor='#1e2130')
            fig.update_yaxes(title_text="Poll Probability (%)", secondary_y=True,
                           range=[0, 105], gridcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

            # ── Stat context chart ───────────────────────────
            st.markdown('<div class="section-header">Stat Context by Round</div>', unsafe_allow_html=True)

            stat_choice = st.selectbox("Stat to overlay", 
                ['Disposals','Coaches_Votes','Goals','Contested.Possessions','Clearances','Kicks'],
                index=0)

            fig2 = go.Figure()
            # Colour bars by win/loss
            bar_colors = ['#1D9E75' if w else '#D85A30' 
                         for w in player_games['Is_Win'].fillna(0).astype(int)]

            fig2.add_trace(go.Bar(
                x=player_games['Round_num'],
                y=player_games[stat_choice],
                name=stat_choice.replace('.',' ').replace('_',' '),
                marker_color=bar_colors,
                opacity=0.85,
                text=player_games[stat_choice].astype(int),
                textposition='outside',
            ))
            fig2.add_trace(go.Scatter(
                x=player_games['Round_num'],
                y=(player_games['Poll_Prob']*100).round(1),
                name='Poll Probability %',
                mode='lines+markers',
                line=dict(color='#ff6b6b', width=2),
                yaxis='y2'
            ))
            fig2.update_layout(
                plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                xaxis=dict(title='Round', dtick=1, gridcolor='#1e2130'),
                yaxis=dict(title=stat_choice.replace('.',' '), gridcolor='#1e2130'),
                yaxis2=dict(title='Poll %', overlaying='y', side='right',
                           range=[0,105], gridcolor='rgba(0,0,0,0)'),
                legend=dict(orientation='h', y=1.12, bgcolor='rgba(0,0,0,0)'),
                margin=dict(t=40,b=40),
                hovermode='x unified'
            )
            # Legend for colours
            st.caption("🟢 Win &nbsp;&nbsp; 🔴 Loss")
            st.plotly_chart(fig2, use_container_width=True)

            # ── Detailed game log ────────────────────────────
            st.markdown('<div class="section-header">Game Log</div>', unsafe_allow_html=True)

            log = player_games.copy()
            log['Result'] = log['Is_Win'].map({1:'✅ W', 0:'❌ L'})
            log['Poll%'] = (log['Poll_Prob']*100).round(1).astype(str)+'%'
            log['ExpV'] = log['Exp_Votes'].round(2)
            log['P(3)'] = (log['P_3']*100).round(1).astype(str)+'%'
            log['P(2)'] = (log['P_2']*100).round(1).astype(str)+'%'
            log['P(1)'] = (log['P_1']*100).round(1).astype(str)+'%'

            display_cols = ['Round_num','Result','Disposals','Goals',
                           'Contested.Possessions','Clearances','Coaches_Votes']
            if not is_2026 and 'Brownlow.Votes' in log.columns:
                display_cols.append('Brownlow.Votes')
            display_cols += ['ExpV','Poll%','P(3)','P(2)','P(1)']

            available = [c for c in display_cols if c in log.columns]
            log_display = log[available].rename(columns={
                'Round_num':'Rnd','Contested.Possessions':'ContPoss',
                'Coaches_Votes':'CV','Brownlow.Votes':'BV','Margin':'Mgn'
            })
            st.dataframe(log_display.sort_values('Rnd'), use_container_width=True, hide_index=True)

# ── Page: Player DNA ─────────────────────────────────────────
elif page == "🧬 Player DNA":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🧬 Player DNA — {selected_season}</h2><p style="color:#8892b0;margin:4px 0 0 0">Player-specific polling efficiency and tendencies</p></div>', unsafe_allow_html=True)

    efficiency = compute_player_efficiency(selected_season)
    if efficiency is None:
        st.error("No game-level data found.")
        st.stop()

    # ── Individual player DNA ────────────────────────────────
    players = sorted(predictions['Player_Name'].tolist())
    selected_player = st.selectbox("Select player", players)

    if selected_player:
        eff_row = efficiency[efficiency['Player_Name']==selected_player]

        if not eff_row.empty:
            e = eff_row.iloc[0]
            st.markdown('<div class="section-header">Polling DNA</div>', unsafe_allow_html=True)

            c1,c2,c3,c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="dna-card"><div class="dna-label">Overall Poll Rate</div><div class="dna-value">{e["Poll_Rate"]*100:.1f}%</div><div class="dna-sub">Polled in {e["Poll_Rate"]*e["Games"]:.0f} of {e["Games"]:.0f} games</div></div>', unsafe_allow_html=True)
            with c2:
                wr = e.get('Win_Poll_Rate', 0)
                st.markdown(f'<div class="dna-card"><div class="dna-label">Poll Rate in Wins</div><div class="dna-value">{wr*100:.1f}%</div><div class="dna-sub">Avg {e.get("Win_Avg_Votes",0):.2f} votes per win</div></div>', unsafe_allow_html=True)
            with c3:
                lr = e.get('Loss_Poll_Rate', 0)
                st.markdown(f'<div class="dna-card"><div class="dna-label">Poll Rate in Losses</div><div class="dna-value">{lr*100:.1f}%</div><div class="dna-sub">Win/loss gap: {(wr-lr)*100:.1f}pts</div></div>', unsafe_allow_html=True)
            with c4:
                hd = e.get('HD_Poll_Rate', 0)
                hd_g = e.get('HD_Games', 0)
                st.markdown(f'<div class="dna-card"><div class="dna-label">30+ Disposal Poll Rate</div><div class="dna-value">{hd*100:.1f}%</div><div class="dna-sub">{hd_g:.0f} games with 30+ disposals</div></div>', unsafe_allow_html=True)

            # Vote distribution
            if game_df is not None:
                player_games = game_df[game_df['Player_Name']==selected_player].copy()
                if not player_games.empty and 'Brownlow.Votes' in player_games.columns:
                    st.markdown('<div class="section-header">Vote Distribution</div>', unsafe_allow_html=True)
                    vote_counts = player_games['Brownlow.Votes'].value_counts().sort_index()
                    c1, c2 = st.columns([1,2])
                    with c1:
                        st.markdown(f"""
                        | Votes | Games | Rate |
                        |-------|-------|------|
                        | 3 | {int(vote_counts.get(3,0))} | {vote_counts.get(3,0)/len(player_games)*100:.1f}% |
                        | 2 | {int(vote_counts.get(2,0))} | {vote_counts.get(2,0)/len(player_games)*100:.1f}% |
                        | 1 | {int(vote_counts.get(1,0))} | {vote_counts.get(1,0)/len(player_games)*100:.1f}% |
                        | 0 | {int(vote_counts.get(0,0))} | {vote_counts.get(0,0)/len(player_games)*100:.1f}% |
                        """)
                    with c2:
                        fig_pie = go.Figure(go.Pie(
                            labels=['3 votes','2 votes','1 vote','0 votes'],
                            values=[vote_counts.get(3,0), vote_counts.get(2,0),
                                   vote_counts.get(1,0), vote_counts.get(0,0)],
                            marker_colors=['#64ffda','#0096c7','#48cae4','#2d3561'],
                            hole=0.4
                        ))
                        fig_pie.update_layout(
                            plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                            font_color='#ccd6f6', margin=dict(t=10,b=10),
                            showlegend=True, height=250,
                            legend=dict(orientation='h', y=-0.1)
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

                    # Disposal threshold analysis
                    st.markdown('<div class="section-header">Disposal Threshold Analysis</div>', unsafe_allow_html=True)
                    thresholds = [15, 20, 25, 28, 30, 33, 35]
                    thresh_data = []
                    for t in thresholds:
                        subset = player_games[player_games['Disposals'] >= t]
                        if len(subset) >= 2:
                            thresh_data.append({
                                'Min Disposals': t,
                                'Games': len(subset),
                                'Poll Rate': f"{(subset['Brownlow.Votes']>0).mean()*100:.1f}%",
                                'Avg Votes': f"{subset['Brownlow.Votes'].mean():.2f}",
                                '3-vote Rate': f"{(subset['Brownlow.Votes']==3).mean()*100:.1f}%",
                            })
                    if thresh_data:
                        st.dataframe(pd.DataFrame(thresh_data), use_container_width=True, hide_index=True)

    # ── League-wide efficiency leaderboard ───────────────────
    st.markdown('<div class="section-header">League Efficiency Rankings</div>', unsafe_allow_html=True)

    min_g = st.slider("Minimum games", 5, 20, 10)
    sort_by = st.selectbox("Sort by", ['Poll_Rate','Win_Poll_Rate','HD_Poll_Rate','Three_Vote_Rate'], 
                           format_func=lambda x: {
                               'Poll_Rate':'Overall Poll Rate',
                               'Win_Poll_Rate':'Win Poll Rate',
                               'HD_Poll_Rate':'30+ Disposal Poll Rate',
                               'Three_Vote_Rate':'3-Vote Rate'
                           }[x])

    eff_display = efficiency[efficiency['Games'] >= min_g].copy()
    eff_display = eff_display.sort_values(sort_by, ascending=False).head(30)
    eff_display['Poll %'] = (eff_display['Poll_Rate']*100).round(1)
    eff_display['Win Poll %'] = (eff_display['Win_Poll_Rate']*100).round(1)
    eff_display['Loss Poll %'] = (eff_display['Loss_Poll_Rate']*100).round(1)
    eff_display['30+ Poll %'] = (eff_display['HD_Poll_Rate']*100).round(1)
    eff_display['3v Rate %'] = (eff_display['Three_Vote_Rate']*100).round(1)
    eff_display.insert(0, 'Rank', range(1, len(eff_display)+1))

    st.dataframe(
        eff_display[['Rank','Player_Name','Games','Poll %','Win Poll %',
                     'Loss Poll %','30+ Poll %','3v Rate %','Avg_Disposals']]\
            .rename(columns={'Player_Name':'Player','Avg_Disposals':'Avg Disp'}),
        use_container_width=True, hide_index=True
    )

# ── Page: Feature Importance ─────────────────────────────────
elif page == "🔍 Feature Importance":
    st.markdown('<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🔍 What Drives Brownlow Votes?</h2><p style="color:#8892b0;margin:4px 0 0 0">XGBoost v2.0 — 62 features including relative game context</p></div>', unsafe_allow_html=True)

    if importance is None:
        st.error("Run brownlow_model.py first.")
        st.stop()

    imp = importance.copy()
    imp['Importance %'] = (imp['Importance']*100).round(2)

    # Split base vs relative
    tab1, tab2 = st.tabs(["All Features", "Top 20"])

    with tab2:
        top20 = imp.head(20).sort_values('Importance %', ascending=True)
        fig3 = go.Figure(go.Bar(x=top20['Importance %'], y=top20['Feature'], orientation='h',
                                marker=dict(color=top20['Importance %'], colorscale='Teal', showscale=False)))
        fig3.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                           xaxis_title='Importance (%)', height=500, margin=dict(l=220,t=20))
        st.plotly_chart(fig3, use_container_width=True)

    with tab1:
        all_imp = imp.sort_values('Importance %', ascending=True)
        fig4 = go.Figure(go.Bar(x=all_imp['Importance %'], y=all_imp['Feature'], orientation='h',
                                marker=dict(color=all_imp['Importance %'], colorscale='Teal', showscale=False)))
        fig4.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                           xaxis_title='Importance (%)', height=1400, margin=dict(l=250,t=20))
        st.plotly_chart(fig4, use_container_width=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Top signals (v2.0):**\n- 🥇 Coaches Votes (raw + relative z-score)\n- 🥈 Impact Score relative to game\n- 🥉 Top 3 coaches votes flag\n- Is_Loss and Is_Win\n- BOG flags")
    with c2:
        st.markdown("**v2.0 improvement:**\n- MAE improved from 0.0954 → 0.0910\n- Relative features now in top 5\n- Model now understands who was best *in that game*\n- Not just raw stat volume")

# ── Page: Poll Probability ───────────────────────────────────
elif page == "📈 Poll Probability":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">📈 Poll Probability — {selected_season}</h2></div>', unsafe_allow_html=True)

    c1,c2 = st.columns([2,1])
    with c1: min_games = st.slider("Min games played", 1, 25, 10)
    with c2: top_n = st.selectbox("Show top N", [20,30,50], index=0)

    filtered = predictions[predictions['Games']>=min_games].head(top_n).copy()
    filtered['P3%'] = (filtered['Exp_3vote_games']/filtered['Games']*100).round(1)
    filtered['P2%'] = (filtered['Exp_2vote_games']/filtered['Games']*100).round(1)
    filtered['P1%'] = (filtered['Exp_1vote_games']/filtered['Games']*100).round(1)

    fig5 = go.Figure()
    fig5.add_trace(go.Bar(name='P(3 votes)', x=filtered['Player_Name'], y=filtered['P3%'], marker_color='#64ffda'))
    fig5.add_trace(go.Bar(name='P(2 votes)', x=filtered['Player_Name'], y=filtered['P2%'], marker_color='#0096c7'))
    fig5.add_trace(go.Bar(name='P(1 vote)', x=filtered['Player_Name'], y=filtered['P1%'], marker_color='#48cae4'))
    fig5.update_layout(barmode='stack', plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                       font_color='#ccd6f6', yaxis_title='Probability (%)',
                       xaxis_tickangle=-35, legend=dict(orientation='h',y=1.05),
                       margin=dict(t=20,b=120))
    st.plotly_chart(fig5, use_container_width=True)

# ── Page: Value Finder ───────────────────────────────────────
elif page == "🎯 Value Finder":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🎯 Value Finder — {selected_season}</h2><p style="color:#8892b0;margin:4px 0 0 0">EV analysis against bookmaker odds</p></div>', unsafe_allow_html=True)

    top30 = predictions.head(30).copy()
    top30['Model_Win_Prob'] = (top30['Exp_Total_Votes']/top30['Exp_Total_Votes'].sum()*100).round(2)

    scraped_odds = load_best_odds()

    if scraped_odds is not None and len(scraped_odds) > 0:
        st.success(f"✅ {len(scraped_odds)} odds loaded from bookmakers")
        tab1, tab2 = st.tabs(["Auto Odds", "Manual Entry"])
    else:
        st.info("No scraped odds. Enter manually below.")
        tab1, tab2 = None, st.container()

    odds_data = []

    if tab1 is not None:
        with tab1:
            merged = top30.merge(scraped_odds, left_on='Player_Name', right_on='player', how='left')
            merged['Bookie_Odds'] = merged['best_odds'].fillna(999)
            merged['Implied %'] = (100/merged['Bookie_Odds']).round(2)
            merged['Edge %'] = (merged['Model_Win_Prob'] - merged['Implied %']).round(2)
            merged['Flag'] = merged['Edge %'].apply(lambda e: '🟢 Strong Value' if e>5 else ('🟡 Value' if e>2 else ('👀 Watch' if e>0 else '🔴 Lay')))
            merged = merged.sort_values('Edge %', ascending=False)
            st.dataframe(merged[['Player_Name','Team','Model_Win_Prob','Bookie_Odds','Implied %','Edge %','Flag']]\
                .rename(columns={'Player_Name':'Player','Model_Win_Prob':'Model %','Bookie_Odds':'Best Odds'}),
                use_container_width=True, hide_index=True)
            value_plays = merged[merged['Edge %'] > 2]
            if not value_plays.empty:
                st.markdown('<div class="section-header">Value Plays</div>', unsafe_allow_html=True)
                for _, row in value_plays.iterrows():
                    st.success(f"**{row['Player_Name']}** — Model: {row['Model_Win_Prob']}% | Bookie: {row['Implied %']}% | Edge: +{row['Edge %']}% | Odds: ${row['Bookie_Odds']}")

    manual_container = tab2 if tab1 is not None else tab2
    with manual_container:
        st.markdown("Enter decimal odds for each player:")
        cols = st.columns(3)
        for i, (_, row) in enumerate(top30.iterrows()):
            with cols[i % 3]:
                default = float(max(2.0, round(100/max(row['Model_Win_Prob'],0.5),1)))
                odds = st.number_input(
                    f"{row['Player_Name']} ({row['Team']})",
                    min_value=1.01, max_value=1001.0,
                    value=default, step=0.5, key=f"odds_{i}"
                )
                odds_data.append({
                    'Player': row['Player_Name'], 'Team': row['Team'],
                    'Exp Votes': round(row['Exp_Total_Votes'],1),
                    'Model %': row['Model_Win_Prob'],
                    'Odds': odds, 'Implied %': round(100/odds,1),
                })

        if odds_data:
            odf = pd.DataFrame(odds_data)
            odf['Edge %'] = (odf['Model %'] - odf['Implied %']).round(1)
            odf['Flag'] = odf['Edge %'].apply(lambda e: '🟢 Strong Value' if e>5 else ('🟡 Value' if e>2 else ('👀 Watch' if e>0 else '🔴 Lay')))
            odf = odf.sort_values('Edge %', ascending=False)
            st.markdown('<div class="section-header">EV Analysis</div>', unsafe_allow_html=True)
            st.dataframe(odf, use_container_width=True, hide_index=True)
            value = odf[odf['Edge %'] > 2]
            if not value.empty:
                st.markdown('<div class="section-header">Value Plays</div>', unsafe_allow_html=True)
                for _, row in value.iterrows():
                    st.success(f"**{row['Player']}** — Model: {row['Model %']}% | Bookie: {row['Implied %']}% | Edge: +{row['Edge %']}%")

# ── Page: Stat Filter ────────────────────────────────────────
elif page == "🔬 Stat Filter":
    st.markdown('<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🔬 Stat Filter</h2><p style="color:#8892b0;margin:4px 0 0 0">Set thresholds and see historical poll rates — 2015–2025</p></div>', unsafe_allow_html=True)

    hist = load_all_historical()
    if hist is None:
        st.error("No historical game-level data found. Run brownlow_model.py first.")
        st.stop()

    hist = hist[hist['Brownlow.Votes'].notna()].copy()

    # ── Filters ──────────────────────────────────────────────
    st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)

    all_players = sorted(hist['Player_Name'].dropna().unique().tolist())
    selected_players = st.multiselect(
        "Player (leave blank for all players)",
        all_players,
        default=[],
        placeholder="All players",
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        result_filter = st.radio("Game result", ["Either", "Win only", "Loss only"], horizontal=True)
        min_disp = st.slider("Min disposals", 0, 50, 0, 1)
        min_goals = st.slider("Min goals", 0, 10, 0, 1)
        min_kicks = st.slider("Min kicks", 0, 40, 0, 1)

    with col2:
        min_clearances = st.slider("Min clearances", 0, 15, 0, 1)
        min_contested = st.slider("Min contested possessions", 0, 25, 0, 1)
        min_coaches = st.slider("Min coaches votes", 0, 10, 0, 1)
        min_tackles = st.slider("Min tackles", 0, 12, 0, 1)

    with col3:
        min_score_inv = st.slider("Min score involvements", 0, 15, 0, 1)
        has_rating = 'RatingPoints' in hist.columns
        min_rating = st.slider("Min Wheelo rating pts", 0, 100, 0, 1) if has_rating else 0
        season_range = st.slider(
            "Season range",
            int(hist['Season'].min()), int(hist['Season'].max()),
            (int(hist['Season'].min()), int(hist['Season'].max()))
        )

    # ── Apply filters ─────────────────────────────────────────
    mask = (
        (hist['Season'] >= season_range[0]) & (hist['Season'] <= season_range[1]) &
        (hist['Player_Name'].isin(selected_players) if selected_players else pd.Series(True, index=hist.index)) &
        (hist['Disposals'] >= min_disp) &
        (hist['Goals'] >= min_goals) &
        (hist['Kicks'] >= min_kicks) &
        (hist['Clearances'] >= min_clearances) &
        (hist['Contested.Possessions'] >= min_contested) &
        (hist['Coaches_Votes'] >= min_coaches) &
        (hist['Tackles'] >= min_tackles) &
        (hist['Score_Involvements'] >= min_score_inv)
    )
    if has_rating:
        mask &= (hist['RatingPoints'] >= min_rating)
    if result_filter == "Win only":
        mask &= (hist['Is_Win'] == 1)
    elif result_filter == "Loss only":
        mask &= (hist['Is_Loss'] == 1)

    filtered = hist[mask]
    total = len(filtered)

    # ── Summary metrics ───────────────────────────────────────
    st.markdown('<div class="section-header">Results</div>', unsafe_allow_html=True)

    if total == 0:
        st.warning("No games match these filters.")
    else:
        n3 = (filtered['Brownlow.Votes'] == 3).sum()
        n2 = (filtered['Brownlow.Votes'] == 2).sum()
        n1 = (filtered['Brownlow.Votes'] == 1).sum()
        n0 = (filtered['Brownlow.Votes'] == 0).sum()
        poll_rate = (filtered['Brownlow.Votes'] > 0).mean()
        avg_votes = filtered['Brownlow.Votes'].mean()

        c1, c2, c3, c4, c5 = st.columns(5)
        player_sub = f"{len(selected_players)} player{'s' if len(selected_players)!=1 else ''}" if selected_players else "All players"
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Matching Games</div><div class="metric-value">{total:,}</div><div class="metric-sub">{season_range[0]}–{season_range[1]} · {player_sub}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Poll Rate</div><div class="metric-value">{poll_rate*100:.1f}%</div><div class="metric-sub">Any votes</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">3-Vote Rate</div><div class="metric-value">{n3/total*100:.1f}%</div><div class="metric-sub">{n3:,} games</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">2-Vote Rate</div><div class="metric-value">{n2/total*100:.1f}%</div><div class="metric-sub">{n2:,} games</div></div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Votes</div><div class="metric-value">{avg_votes:.3f}</div><div class="metric-sub">per game</div></div>', unsafe_allow_html=True)

        # ── Vote distribution chart ───────────────────────────
        col_chart, col_table = st.columns([2, 1])

        with col_chart:
            fig_bar = go.Figure(go.Bar(
                x=['3 votes', '2 votes', '1 vote', '0 votes'],
                y=[n3/total*100, n2/total*100, n1/total*100, n0/total*100],
                marker_color=['#64ffda', '#0096c7', '#48cae4', '#2d3561'],
                text=[f"{v:.1f}%" for v in [n3/total*100, n2/total*100, n1/total*100, n0/total*100]],
                textposition='outside',
            ))
            fig_bar.update_layout(
                plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                yaxis=dict(title='% of games', gridcolor='#1e2130', range=[0, max(n0/total*100*1.1, 10)]),
                xaxis=dict(gridcolor='#1e2130'),
                margin=dict(t=20, b=20),
                height=300,
                showlegend=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_table:
            st.markdown("**Vote breakdown**")
            st.markdown(f"""
| Votes | Games | Rate |
|-------|------:|-----:|
| 3 | {n3:,} | {n3/total*100:.1f}% |
| 2 | {n2:,} | {n2/total*100:.1f}% |
| 1 | {n1:,} | {n1/total*100:.1f}% |
| 0 | {n0:,} | {n0/total*100:.1f}% |
| **Total** | **{total:,}** | |
""")

        # ── Per-threshold breakdown ───────────────────────────
        st.markdown('<div class="section-header">Threshold Comparison</div>', unsafe_allow_html=True)
        st.caption("Poll rate at each disposal threshold, holding all other filters fixed")

        disp_rows = []
        for t in [0, 15, 20, 25, 28, 30, 33, 35, 38, 40]:
            sub_mask = mask & (hist['Disposals'] >= t)
            sub = hist[sub_mask]
            if len(sub) >= 5:
                disp_rows.append({
                    'Min Disposals': t,
                    'Games': len(sub),
                    'Poll Rate': f"{(sub['Brownlow.Votes']>0).mean()*100:.1f}%",
                    '3-vote Rate': f"{(sub['Brownlow.Votes']==3).mean()*100:.1f}%",
                    'Avg Votes': f"{sub['Brownlow.Votes'].mean():.3f}",
                })
        if disp_rows:
            st.dataframe(pd.DataFrame(disp_rows), use_container_width=True, hide_index=True)

        # ── Matching game sample ──────────────────────────────
        st.markdown('<div class="section-header">Sample Games</div>', unsafe_allow_html=True)
        show_cols = ['Season', 'Round_num', 'Player_Name', 'Playing.for',
                     'Disposals', 'Goals', 'Clearances', 'Contested.Possessions',
                     'Coaches_Votes', 'Is_Win', 'Brownlow.Votes']
        available = [c for c in show_cols if c in filtered.columns]
        sample = filtered[available].copy()
        sample['Is_Win'] = sample['Is_Win'].map({1: 'W', 0: 'L'})
        sample = sample.rename(columns={
            'Round_num': 'Rnd', 'Player_Name': 'Player', 'Playing.for': 'Team',
            'Contested.Possessions': 'ContPoss', 'Coaches_Votes': 'CV',
            'Is_Win': 'Result', 'Brownlow.Votes': 'Votes'
        })
        st.dataframe(
            sample.sort_values(['Season', 'Rnd'], ascending=[False, False]).head(200),
            use_container_width=True, hide_index=True
        )
