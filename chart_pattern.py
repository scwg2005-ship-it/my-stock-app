import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import feedparser
import urllib.parse
import time

# ==========================================
# 1. 전역 설정 및 프리미엄 CSS (UI/UX)
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트 v5.6", page_icon="👑")

@st.cache_data(ttl=86400)
def load_krx_data():
    return fdr.StockListing('KRX')

krx_list = load_krx_data()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 15px; border-bottom: 2px solid #333; padding-bottom: 5px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: 800; color: #999; padding: 12px 25px; transition: all 0.3s; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom: 3px solid #00FF00 !important; }
    .ai-report-container { background: linear-gradient(145deg, #1e1e26, #14141b); padding: 30px; border-radius: 20px; border-left: 8px solid #00FF00; margin-bottom: 30px; box-shadow: 0 15px 35px rgba(0,0,0,0.6); }
    .price-card-v2 { background: #1c1e26; border-radius: 15px; padding: 25px; text-align: center; border: 1px solid #333; transition: all 0.4s; }
    .price-card-v2:hover { border-color: #00FF00; transform: translateY(-5px); }
    div[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 900 !important; color: #00FF00; }
    /* 온도계 여백 확보 */
    .gauge-container { margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 엔진: 데이터 분석 (KeyError 방어)
# ==========================================
def smart_ticker_search(user_query):
    query = user_query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    target = krx_list[krx_list['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not target.empty: return target.iloc[0]['Code']
    manual_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "하이닉스": "000660", "삼성전자": "005930"}
    return manual_map.get(query, query.upper())

@st.cache_data(ttl=60)
def get_advanced_data(symbol, period_choice, interval_choice):
    try:
        # 티커 변환
        if symbol.isdigit():
            market_info = krx_list[krx_list['Code'] == symbol]
            m_type = market_info['Market'].values[0] if not market_info.empty else "KOSPI"
            yf_symbol = f"{symbol}.KS" if m_type == "KOSPI" else f"{symbol}.KQ"
        else: yf_symbol = symbol

        # 데이터 호출
        if "분봉" in interval_choice:
            i_map = {"5분봉": "5m", "15분봉": "15m", "60분봉": "60m"}
            df = yf.download(yf_symbol, period="1mo", interval=i_map.get(interval_choice, "60m"), progress=False)
        else:
            p_map = {"3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
            df = yf.download(yf_symbol, period=p_map.get(period_choice, "6mo"), interval="1d", progress=False)

        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # [필수 컬럼 강제 생성 - KeyError 방어]
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col not in df.columns: return None

        # [기술적 지표 계산]
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_S'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_H'] = df['MACD'] - df['MACD_S']

        # Stochastic
        df['L14'] = df['Low'].rolling(14).min()
        df['H14'] = df['High'].rolling(14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - df['L14']) / (df['H14'] - df['L14']))
        
        # 볼린저 밴드
        df['BB_Mid'] = df['MA20']
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)

        # [⭐ KeyError 방지용 컬럼 생성]
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))

        # [AI 퀀트 스코어링]
        df['AI_Score'] = 50.0
        df.loc[df['Close'] > df['MA20'], 'AI_Score'] += 15
        df.loc[df['MACD_H'] > 0, 'AI_Score'] += 10
        df.loc[df['GC'], 'AI_Score'] += 15
        df.loc[df['RSI'] < 30, 'AI_Score'] += 15
        df.loc[df['DC'], 'AI_Score'] -= 20
        df.loc[df['Close'] < df['MA60'], 'AI_Score'] -= 20
        df['AI_Score'] = df['AI_Score'].clip(0, 100).fillna(50)

        # [백테스팅]
        df['Pos'] = 0
        df.loc[df['AI_Score'] >= 60, 'Pos'] = 1
        df.loc[df['AI_Score'] <= 40, 'Pos'] = 0
        df['Pos'] = df['Pos'].replace(0, np.nan).ffill().fillna(0)
        df['Strat_Ret'] = df['Pos'].shift(1) * df['Close'].pct_change()
        df['Cum_Mkt'] = (1 + df['Close'].pct_change().fillna(0)).cumprod() * 100
        df['Cum_Strat'] = (1 + df['Strat_Ret'].fillna(0)).cumprod() * 100

        # [변곡점]
        pks, _ = find_peaks(df['High'].values, distance=10, prominence=df['High'].std()*0.2)
        vls, _ = find_peaks(-df['Low'].values, distance=10, prominence=df['Low'].std()*0.2)

        return df, pks, vls
    except Exception as e:
        return None

# ==========================================
# 3. 사이드바 제어판
# ==========================================
st.sidebar.title("👑 MASTER v5.6")
u_query = st.sidebar.text_input("종목명/티커", value="SK하이닉스")
t_symbol = smart_ticker_search(u_query)
c_int = st.sidebar.selectbox("주기", ["일봉", "60분봉", "15분봉", "5분봉"])
c_per = st.sidebar.select_slider("기간", options=["3mo", "6mo", "1y", "2y"], value="1y")

# ==========================================
# 4. 대시보드 출력
# ==========================================
pkg = get_advanced_data(t_symbol, c_per, c_int)

if pkg:
    df, pks, vls = pkg
    cur_p = float(df['Close'].iloc[-1])
    ai_s = float(df['AI_Score'].iloc[-1])
    
    # 목표/손절가 예외처리
    tgt_p = df['High'].iloc[pks[-1]] if len(pks) > 0 else cur_p * 1.12
    stp_p = df['Low'].iloc[vls[-1]] if len(vls) > 0 else cur_p * 0.92
    if stp_p >= cur_p: stp_p = cur_p * 0.94
    
    st.title(f"👑 {u_query} 프리미엄 분석")
    m1, m2, m3 = st.columns(3)
    m1.metric("현재가", f"{cur_p:,.0f}", f"{((cur_p/df['Close'].iloc[-2]-1)*100):+.2f}%")
    m2.metric("AI 점수", f"{ai_s:.0f}점")
    m3.metric("RSI 강도", f"{df['RSI'].iloc[-1]:.1f}")

    tabs = st.tabs(["📊 마스터 차트", "🧠 AI 전략 리포트", "📉 백테스팅 성과", "⚡ 실시간 뉴스"])

    with tabs[0]:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        
        # 엘리어트 숫자
        lbls = ['1','2','3','4','5','A','B','C']
        pts = sorted([('p', p, df['High'].iloc[p]) for p in pks] + [('v', v, df['Low'].iloc[v]) for v in vls], key=lambda x: x[1])[-8:]
        for i, pt in enumerate(pts):
            if i < len(lbls):
                clr = "#00FF00" if pt[0] == 'v' else "#FF4B4B"
                fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{lbls[i]}</b>"], 
                                         textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=22, color=clr), showlegend=False), row=1, col=1)
        
        # 골든크로스 표시 (에러 방지용 체크)
        if 'GC' in df.columns:
            gc_idx = df[df['GC']].index
            fig.add_trace(go.Scatter(x=gc_idx, y=df.loc[gc_idx, 'Low']*0.96, mode='markers', marker=dict(symbol='star', size=12, color='yellow'), name="GC"), row=1, col=1)
        
        fig.add_hline(y=tgt_p, line_dash="dash", line_color="#00FF00", annotation_text="목표")
        fig.add_hline(y=stp_p, line_dash="dash", line_color="#FF4B4B", annotation_text="손절")
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if x<0 else 'green' for x in df['MACD_H']]), row=2, col=1)
        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        # 온도계
        fig_g = go.Figure(go.Indicator(
            mode = "gauge+number", value = ai_s, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "AI 퀀트 점수", 'font': {'size': 24, 'color': 'white'}},
            gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#00FF00" if ai_s>=60 else "#FF4B4B"}}
        ))
        fig_g.update_layout(height=400, margin=dict(t=150, b=20), paper_bgcolor="#0E1117", font={'color': 'white'})
        st.plotly_chart(fig_g, use_container_width=True)
        
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='price-card-v2'><h4>🎯 목표가</h4><h2 style='color:#00FF00;'>{tgt_p:,.0f}</h2></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='price-card-v2'><h4>🛡️ 손절가</h4><h2 style='color:#FF4B4B;'>{stp_p:,.0f}</h2></div>", unsafe_allow_html=True)

    with tabs[2]:
        m_r, s_r = df['Cum_Mkt'].iloc[-1]-100, df['Cum_Strat'].iloc[-1]-100
        col_bt1, col_bt2 = st.columns(2)
        col_bt1.metric("존버 수익률", f"{m_r:+.2f}%")
        col_bt2.metric("AI 전략 수익률", f"{s_r:+.2f}%", f"{s_r-m_r:+.2f}%p")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="시장", line=dict(color='gray')))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="AI", line=dict(color='#00FF00', width=3)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="Score", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        fig_bt.update_layout(height=500, template="plotly_dark", yaxis2=dict(overlaying="y", side="right", range=[0, 100]))
        st.plotly_chart(fig_bt, use_container_width=True)

    with tabs[3]:
        kw = urllib.parse.quote(f"{u_query} 특징주")
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
        for e in feed.entries[:8]:
            st.markdown(f"<div style='background:#16181d; padding:15px; border-radius:10px; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:white; text-decoration:none; font-weight:bold;'>{e.title}</a></div>", unsafe_allow_html=True)

else: st.error("데이터 로드 실패")
