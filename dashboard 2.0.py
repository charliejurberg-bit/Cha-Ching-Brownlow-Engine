"""
Brownlow Medal Prediction Dashboard
Run: python -m streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Brownlow Medal Engine", page_icon="🏅", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #252940);
        border: 1px solid #3d4566;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .metric-label { color: #8892b0; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .metric-value { color: #ccd6f6; font-size: 26px; font-weight: 700; margin-top: 4px; }
    .metric-sub { color: #64ffda; font-size: 13px; margin-top: 2px; }
    .title-bar {
        background: linear-gradient(135deg, #1a1f35, #0d1b2a);
        border-left: 4px solid #64ffda;
        padding: 20px 24px;
        border-radius: 8px;
        margin-bottom: 24px;
    }
    .section-header {
        color: #64ffda; font-size: 13px; font-weight: 600;
        letter-spacing: 2px; text-transform: uppercase;
        margin: 24px 0 12px 0;
        border-bottom: 1px solid #1e2130; padding-bottom: 8px;
    }
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

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏅 Brownlow Engine")
    st.markdown("---")

    if not AVAILABLE_SEASONS:
        st.error("No predictions found.\nRun brownlow_model.py first.")
        st.stop()

    selected_season = st.selectbox("Season", AVAILABLE_SEASONS, index=0)

    page = st.radio("Navigate", [
        "📊 Leaderboard",
        "👤 Player Profile",
        "🔍 Feature Importance",
        "📈 Poll Probability",
        "🎯 Value Finder",
    ])
    st.markdown("---")
    st.markdown(f"**Season:** {selected_season}")
    st.markdown("**Model:** XGBoost")
    st.markdown("**Training:** 2015–2025")

predictions = load_season(selected_season)
game_df = load_game(selected_season)
importance = load_importance()

if predictions is None:
    st.error(f"No data for {selected_season}. Run brownlow_model.py first.")
    st.stop()

# ── Page: Leaderboard ────────────────────────────────────────
if page == "📊 Leaderboard":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">📊 {selected_season} Brownlow Leaderboard</h2><p style="color:#8892b0;margin:4px 0 0 0">Model predicted votes vs actual results</p></div>', unsafe_allow_html=True)

    top3 = predictions.head(3)
    medals = ['🥇','🥈','🥉']
    cols = st.columns(3)
    for i, (col, (_, row)) in enumerate(zip(cols, top3.iterrows())):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{medals[i]} #{i+1} Predicted</div>
                <div class="metric-value">{row['Player_Name']}</div>
                <div class="metric-sub">{row['Team']} &nbsp;|&nbsp; {row['Exp_Total_Votes']:.1f} exp &nbsp;|&nbsp; {int(row['Actual_Votes'])} actual</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Full Leaderboard</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1:
        search = st.text_input("Search player", "")
    with col2:
        show_n = st.selectbox("Show", [20,50,100,200], index=0)

    display = predictions.copy()
    if search:
        display = display[display['Player_Name'].str.contains(search, case=False)]
    display = display.head(show_n).copy()
    display.insert(0, 'Rank', range(1, len(display)+1))
    display['Poll %'] = (display['Avg_Poll_Prob']*100).round(1)
    display['Exp Votes'] = display['Exp_Total_Votes'].round(1)
    display['Actual'] = display['Actual_Votes'].astype(int)
    display['3-vote games'] = display['Exp_3vote_games'].round(1)
    display['Diff'] = (display['Exp Votes'] - display['Actual']).round(1)

    st.dataframe(
        display[['Rank','Player_Name','Team','Games','Actual','Exp Votes','Diff','Poll %','3-vote games']]\
            .rename(columns={'Player_Name':'Player'}),
        use_container_width=True, hide_index=True
    )

    st.markdown('<div class="section-header">Expected vs Actual — Top 20</div>', unsafe_allow_html=True)
    chart = predictions.head(20).copy()
    fig = go.Figure()
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
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">👤 Player Profile — {selected_season}</h2></div>', unsafe_allow_html=True)

    if game_df is None:
        st.error("No game-level data found.")
        st.stop()

    players = sorted(predictions['Player_Name'].tolist())
    selected_player = st.selectbox("Select player", players)

    if selected_player:
        player_games = game_df[game_df['Player_Name']==selected_player].copy()
        pred_row = predictions[predictions['Player_Name']==selected_player]

        if not pred_row.empty:
            row = pred_row.iloc[0]
            c1,c2,c3,c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Team</div><div class="metric-value" style="font-size:20px">{row["Team"]}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Actual Votes</div><div class="metric-value">{int(row["Actual_Votes"])}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Model Expected</div><div class="metric-value">{row["Exp_Total_Votes"]:.1f}</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Poll Prob</div><div class="metric-value">{row["Avg_Poll_Prob"]*100:.1f}%</div></div>', unsafe_allow_html=True)

        if not player_games.empty:
            player_games = player_games.sort_values('Round_num')
            st.markdown('<div class="section-header">Game-by-Game</div>', unsafe_allow_html=True)

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=player_games['Round_num'], y=player_games['Brownlow.Votes'],
                                  name='Actual Votes', marker_color='#8892b0', opacity=0.7))
            fig2.add_trace(go.Scatter(x=player_games['Round_num'], y=player_games['Poll_Prob'],
                                      name='Poll Prob', mode='lines+markers',
                                      line=dict(color='#64ffda', width=2), yaxis='y2'))
            fig2.update_layout(
                plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                xaxis_title='Round',
                yaxis=dict(title='Votes', range=[0,3.5]),
                yaxis2=dict(title='Poll Probability', overlaying='y', side='right', range=[0,1]),
                legend=dict(orientation='h', y=1.1), margin=dict(t=20)
            )
            st.plotly_chart(fig2, use_container_width=True)

            st.markdown('<div class="section-header">Game Log</div>', unsafe_allow_html=True)
            log_cols = ['Round_num','Disposals','Goals','Contested.Possessions',
                        'Clearances','Coaches_Votes','Brownlow.Votes','Poll_Prob','Exp_Votes','Is_Win']
            available = [c for c in log_cols if c in player_games.columns]
            log = player_games[available].copy()
            if 'Is_Win' in log.columns:
                log['Is_Win'] = log['Is_Win'].map({1:'✅ W', 0:'❌ L'})
            if 'Poll_Prob' in log.columns:
                log['Poll_Prob'] = (log['Poll_Prob']*100).round(1).astype(str)+'%'
            if 'Exp_Votes' in log.columns:
                log['Exp_Votes'] = log['Exp_Votes'].round(2)
            log = log.rename(columns={'Round_num':'Rnd','Contested.Possessions':'ContPoss',
                                      'Coaches_Votes':'CV','Brownlow.Votes':'BV',
                                      'Poll_Prob':'Poll%','Exp_Votes':'ExpV','Is_Win':'Result'})
            st.dataframe(log.sort_values('Rnd'), use_container_width=True, hide_index=True)

# ── Page: Feature Importance ─────────────────────────────────
elif page == "🔍 Feature Importance":
    st.markdown('<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🔍 What Drives Brownlow Votes?</h2></div>', unsafe_allow_html=True)

    if importance is None:
        st.error("Run brownlow_model.py first.")
        st.stop()

    imp = importance.copy()
    imp['Importance %'] = (imp['Importance']*100).round(2)
    imp = imp.sort_values('Importance %', ascending=True)

    fig3 = go.Figure(go.Bar(x=imp['Importance %'], y=imp['Feature'], orientation='h',
                            marker=dict(color=imp['Importance %'], colorscale='Teal', showscale=False)))
    fig3.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#ccd6f6',
                       xaxis_title='Importance (%)', height=700, margin=dict(l=200,t=20))
    st.plotly_chart(fig3, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top signals:**\n- 🥇 Coaches Votes — strongest predictor\n- 🥈 Is_Loss — losing kills chances\n- 🥉 Impact Score — goals + clearances + contested")
    with c2:
        st.markdown("**Key findings:**\n- Outcome matters more than any stat\n- Contested possession > uncontested\n- Kicks weighted higher than handballs\n- Season year captures gameplay evolution")

# ── Page: Poll Probability ───────────────────────────────────
elif page == "📈 Poll Probability":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">📈 Poll Probability — {selected_season}</h2></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([2,1])
    with c1: min_games = st.slider("Min games played", 1, 23, 10)
    with c2: top_n = st.selectbox("Show top N", [20,30,50], index=0)

    filtered = predictions[predictions['Games']>=min_games].head(top_n).copy()
    filtered['P3%'] = (filtered['Exp_3vote_games']/filtered['Games']*100).round(1)
    filtered['P2%'] = (filtered['Exp_2vote_games']/filtered['Games']*100).round(1)
    filtered['P1%'] = (filtered['Exp_1vote_games']/filtered['Games']*100).round(1)

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(name='P(3 votes)', x=filtered['Player_Name'], y=filtered['P3%'], marker_color='#64ffda'))
    fig4.add_trace(go.Bar(name='P(2 votes)', x=filtered['Player_Name'], y=filtered['P2%'], marker_color='#0096c7'))
    fig4.add_trace(go.Bar(name='P(1 vote)', x=filtered['Player_Name'], y=filtered['P1%'], marker_color='#48cae4'))
    fig4.update_layout(barmode='stack', plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                       font_color='#ccd6f6', yaxis_title='Probability (%)',
                       xaxis_tickangle=-35, legend=dict(orientation='h', y=1.05),
                       margin=dict(t=20,b=120))
    st.plotly_chart(fig4, use_container_width=True)

# ── Page: Value Finder ───────────────────────────────────────
elif page == "🎯 Value Finder":
    st.markdown(f'<div class="title-bar"><h2 style="color:#ccd6f6;margin:0">🎯 Value Finder — {selected_season}</h2><p style="color:#8892b0;margin:4px 0 0 0">Enter bookmaker odds to find EV opportunities</p></div>', unsafe_allow_html=True)

    top30 = predictions.head(30).copy()
    top30['Model_Win_Prob'] = (top30['Exp_Total_Votes']/top30['Exp_Total_Votes'].sum()*100).round(1)

    st.markdown('<div class="section-header">Enter Odds</div>', unsafe_allow_html=True)
    odds_data = []
    cols = st.columns(3)
    for i, (_, row) in enumerate(top30.iterrows()):
        with cols[i % 3]:
            default_odds = float(max(2.0, round(100/max(row['Model_Win_Prob'],0.5), 1)))
            odds = st.number_input(
                f"{row['Player_Name']} ({row['Team']})",
                min_value=1.01, max_value=1001.0,
                value=default_odds, step=0.5, key=f"odds_{i}"
            )
            odds_data.append({
                'Player': row['Player_Name'], 'Team': row['Team'],
                'Exp Votes': round(row['Exp_Total_Votes'],1),
                'Model %': row['Model_Win_Prob'],
                'Bookie Odds': odds,
                'Implied %': round(100/odds, 1),
            })

    odds_df = pd.DataFrame(odds_data)
    odds_df['Edge %'] = (odds_df['Model %'] - odds_df['Implied %']).round(1)

    def flag(edge):
        if edge > 5: return '🟢 Strong Value'
        elif edge > 2: return '🟡 Value'
        elif edge > 0: return '👀 Watch'
        else: return '🔴 Lay'

    odds_df['Flag'] = odds_df['Edge %'].apply(flag)
    odds_df = odds_df.sort_values('Edge %', ascending=False)

    st.markdown('<div class="section-header">EV Analysis</div>', unsafe_allow_html=True)
    st.dataframe(odds_df, use_container_width=True, hide_index=True)

    value = odds_df[odds_df['Edge %'] > 2]
    if not value.empty:
        st.markdown('<div class="section-header">Value Plays</div>', unsafe_allow_html=True)
        for _, row in value.iterrows():
            st.success(f"**{row['Player']}** — Model: {row['Model %']}% | Bookie: {row['Implied %']}% | Edge: +{row['Edge %']}%")
