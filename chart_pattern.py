import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
from scipy.stats import norm
import feedparser
import urllib.parse
import os
import time

# ==============================================================================
# [MODULE 1] UI 디자인 및 전문가용 스타일 설정 (1번 요구사항)
# ==============================================================================
st.set_page_config(layout="wide", page_title="QUANT INFINITY PRO v6.1", page_icon="👑")

def apply_neon_styling():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500&family=Pretendard:wght@100;400;700;900&display=swap');
        :root {
            --bg-base: #030305; --bg-widget: #0c0c0e;
            --neon-blue: #00E5FF; --neon-green: #00FF99;
            --neon-purple: #BF00FF; --neon-red: #FF3366;
            --text-silver: #d1d1d1; --border-dim: #1e1e26;
        }
        html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: var(--bg-base); color: var(--text-silver); }
        [data-testid="stSidebar"] { background-color: #08080a; border-right: 1px solid var(--border-dim); }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; background-color: #0a0a0f; padding: 15px 30px; border-radius: 18px; border: 1px solid var(--border-dim); }
        .stTabs [data-baseweb="tab"] { font-size: 1.2rem; font-weight: 900; color: #444; }
        .stTabs [aria-selected="true"] { color: var(--neon-blue) !important; text-shadow: 0 0 15px var(--neon-blue); }
        .master-report-card { background: linear-gradient(165deg, #0f0f15, #050508); border-left: 12px solid var(--neon-green); padding: 40px; border-radius: 25px; margin-bottom: 30px; box-shadow: 0 30px 60px rgba(0,0,0,0.8); }
        .trade-log-box { background: #08080a; border: 1px solid #222; padding: 25px; border-radius: 15px; font-family: 'JetBrains Mono', monospace; height: 400px; overflow-y: auto; line-height: 1.6; }
        .news-node { background: #0b0b0d; padding: 20px; border-radius: 15px; margin-bottom: 12px; border-left: 5px solid var(--neon-purple); transition: 0.3s; }
        div[data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 900 !important; color: var(--neon-green); }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        .live-dot { width: 12px; height: 12px; background: var(--neon-red); border-radius: 50%; display: inline-block; margin-right: 10px; animation: pulse 2s infinite; }
        </style>
    """, unsafe_allow_html=True)

apply_neon_styling()

# ==============================================================================
# [MODULE 2] 데이터 엔진 및 티커 해결사 (5번 요구사항)
# ==============================================================================
@st.cache_data(ttl=86400)
def fetch_krx_master_list():
    """KRX 전체 종목 리스트 로드"""
    return fdr.StockListing('KRX')

def resolve_ticker_v6(query_str):
    q = query_str.strip().replace(" ", "").upper()
    if q.isdigit() and len(q) == 6: return q
    master = fetch_krx_master_list()
    match = master[master['Name'].str.replace(" ", "", regex=False).str.upper() == q]
    if not match.empty: return match.iloc[0]['Code']
    # 글로벌 특수 매핑
    mapping = {"비트코인":"BTC-USD", "이더리움":"ETH-USD", "테슬라":"TSLA", "엔비디아":"NVDA", "온다스":"ONDS"}
    return mapping.get(q, q)

# ==============================================================================
# [MODULE 3] 원시 기술적 분석 엔진 (3, 6, 7, 9, 11번 요구사항)
# ==============================================================================
class RawMathQuantEngineV6:
    def __init__(self, data):
        self.df = data.copy()
        if isinstance(self.df.columns, pd.MultiIndex): self.df.columns = self.df.columns.get_level_values(0)

    def process_all_raw_math(self):
        # 1. 이동평균 (SMA)
        self.df['SMA5'] = self.df['Close'].rolling(5).mean()
        self.df['SMA20'] = self.df['Close'].rolling(20).mean()
        self.df['SMA60'] = self.df['Close'].rolling(60).mean()
        self.df['SMA120'] = self.df['Close'].rolling(120).mean() # 9번 필터용
        
        # 2. RSI 원시 수식
        delta = self.df['Close'].diff()
        u, d = delta.clip(lower=0), -delta.clip(upper=0)
        rs = u.rolling(14).mean() / d.rolling(14).mean()
        self.df['RSI_RAW'] = 100 - (100 / (1 + rs))

        # 3. MACD 원시 수식
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_L'] = ema12 - ema26
        self.df['MACD_S'] = self.df['MACD_L'].ewm(span=9, adjust=False).mean()
        self.df['MACD_H'] = self.df['MACD_L'] - self.df['MACD_S']

        # 4. 일목균형표 상세 (7번)
        h9, l9 = self.df['High'].rolling(9).max(), self.df['Low'].rolling(9).min()
        h26, l26 = self.df['High'].rolling(26).max(), self.df['Low'].rolling(26).min()
        self.df['Tenkan'] = (h9 + l9) / 2
        self.df['Kijun'] = (h26 + l26) / 2
        self.df['SpanA'] = ((self.df['Tenkan'] + self.df['Kijun']) / 2).shift(26)
        self.df['SpanB'] = ((self.df['High'].rolling(52).max() + self.df['Low'].rolling(52).min()) / 2).shift(26)
        self.df['Chikou'] = self.df['Close'].shift(-26)

        # 5. ATR 및 변곡점 (3, 10번)
        tr = pd.concat([self.df['High']-self.df['Low'], abs(self.df['High']-self.df['Close'].shift()), abs(self.df['Low']-self.df['Close'].shift())], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(14).mean()
        self.pks, _ = find_peaks(self.df['High'].values, distance=14, prominence=self.df['High'].std()*0.4)
        self.vls, _ = find_peaks(-self.df['Low'].values, distance=14, prominence=self.df['High'].std()*0.4)
        mx, mn = self.df['High'].max(), self.df['Low'].min()
        self.fib618 = mx - 0.618 * (mx - mn)

        # 6. 매물대 분석 POC (6번)
        price_bins = pd.cut(self.df['Close'], bins=20)
        self.poc_val = self.df.groupby(price_bins, observed=False)['Volume'].sum().idxmax().mid

        # 7. 캔들 패턴 (11번)
        body = abs(self.df['Close'] - self.df['Open'])
        ls = self.df[['Open','Close']].min(axis=1) - self.df['Low']
        us = self.df['High'] - self.df[['Open','Close']].max(axis=1)
        self.df['Hammer'] = (ls > body * 2.2) & (us < body * 0.5)

        # 8. AI 스코어링 (9번)
        s = pd.Series(50.0, index=self.df.index)
        s += np.where(self.df['Close'] > self.df['SMA120'], 12, -8)
        s += np.where(self.df['Close'] > self.df['SMA20'], 10, -10)
        s += np.where(self.df['MACD_H'] > 0, 10, -5)
        s += np.where(self.df['RSI_RAW'] < 32, 18, 0)
        s += np.where(self.df['Hammer'], 15, 0)
        self.df['AI_Score'] = s.clip(0, 100).fillna(50)

        return self.df

# ==============================================================================
# [MODULE 4] 백테스팅 & 시뮬레이션 (4, 8, 10번 요구사항)
# ==============================================================================
def run_trade_simulation_v6(df):
    df['Position'] = 0
    df.loc[df['AI_Score'] >= 62, 'Position'] = 1
    df.loc[df['AI_Score'] <= 42, 'Position'] = 0
    df['Position'] = df['Position'].replace(0, np.nan).ffill().fillna(0)
    
    mkt_ret = df['Close'].pct_change()
    df['Strat_Ret'] = (df['Position'].shift(1) * mkt_ret) - (df['Position'].diff().abs() * 0.00035)
    df['Cum_Mkt'] = (1 + mkt_ret.fillna(0)).cumprod() * 100
    df['Cum_Strat'] = (1 + df['Strat_Ret'].fillna(0)).cumprod() * 100
    
    trade_logs = []
    for i in range(1, len(df)):
        pos, prev_pos = df['Position'].iloc[i], df['Position'].iloc[i-1]
        dt, pr = df.index[i].strftime('%Y-%m-%d %H:%M'), df['Close'].iloc[i]
        if pos == 1 and prev_pos == 0:
            trade_logs.append(f"🟢 <b style='color:#00FF99'>BUY ENTRY</b> | {dt} | PRICE: <b>{pr:,.0f}</b>")
        elif pos == 0 and prev_pos == 1:
            trade_logs.append(f"🔴 <b style='color:#FF3366'>SELL EXIT</b> | {dt} | PRICE: <b>{pr:,.0f}</b>")
    return df, trade_logs[::-1]

def run_heavy_simulation_5000(df, n=5000):
    rets = df['Close'].pct_change().dropna()
    mu, sigma = rets.mean(), rets.std()
    shocks = np.random.normal(mu, sigma, (252, n))
    paths = df['Close'].iloc[-1] * np.exp(np.cumsum(shocks, axis=0))
    # 켈리 공식 (8번)
    win_p = (rets > 0).sum() / len(rets)
    b = rets[rets > 0].mean() / abs(rets[rets < 0].mean())
    kelly = (win_p * b - (1 - win_p)) / b
    return paths, max(0, kelly)

# ==============================================================================
# [MODULE 5] 메인 실행부 (전체 통합)
# ==============================================================================
def start_ultimate_terminal_v6():
    st.sidebar.markdown("# 💎 MASTER CONTROL")
    u_asset = st.sidebar.text_input("종목명/티커 입력", value="SK하이닉스")
    ticker = resolve_ticker_v6(u_asset)
    
    # 한국 주식 시장 처리
    if ticker.isdigit():
        krx_master = fetch_krx_master_list()
        m_type = krx_master[krx_master['Code']==ticker]['Market'].iloc[0]
        yf_ticker = f"{ticker}.KS" if m_type == "KOSPI" else f"{ticker}.KQ"
    else: yf_ticker = ticker

    t_frame = st.sidebar.selectbox("차트 주기 (Timeframe)", ["일봉", "60분봉", "15분봉", "5분봉"])
    p_range = st.sidebar.select_slider("데이터 범위", options=["1mo", "3mo", "6mo", "1y", "2y"], value="1y")

    try:
        int_map = {"일봉":"1d", "60분봉":"60m", "15분봉":"15m", "5분봉":"5m"}
        raw = yf.download(yf_ticker, period="1mo" if "분" in t_frame else p_range, interval=int_map[t_frame], progress=False)
        
        if raw.empty: return st.error("데이터 로드 실패")
        
        # 엔진 가동
        engine = RawMathQuantEngineV6(raw)
        df = engine.process_all_raw_math()
        df, trade_logs = run_trade_simulation_v6(df)
        paths, kelly = run_heavy_simulation_5000(df)
        
        # UI 메인
        cp, score = df['Close'].iloc[-1], df['AI_Score'].iloc[-1]
        st.markdown(f"<h2><span class='live-dot'></span>QUANT TERMINAL v6.1 | {u_asset}</h2>", unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("실시간 가격", f"{cp:,.0f}", f"{((cp/df['Close'].iloc[-2]-1)*100):+.2f}%")
        c2.metric("AI 점수", f"{score:.0f}")
        c3.metric("누적 수익률", f"{df['Cum_Strat'].iloc[-1]-100:+.2f}%")
        c4.metric("매물대 POC", f"{engine.poc_val:,.0f}")

        tab_ch, tab_ai, tab_sim, tab_log, tab_news = st.tabs(["📊 마스터 차트", "🌡️ AI 온도계", "🔮 5,000회 예측", "📜 매매 로그", "⚡ 뉴스"])

        with tab_ch:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanB'], fill='tonexty', fillcolor='rgba(0, 255, 153, 0.05)', name="Kumo"), row=1, col=1)
            # 엘리어트 숫자
            lbls = ['1','2','3','4','5','A','B','C']
            pts = sorted([('p',i,df['High'].iloc[i]) for i in engine.pks]+[('v',i,df['Low'].iloc[i]) for i in engine.vls], key=lambda x:x[1])[-8:]
            for idx, pt in enumerate(pts):
                if idx < len(lbls):
                    clr = "#00FF99" if pt[0]=='v' else "#FF3366"
                    fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{lbls[idx]}</b>"], 
                                             textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=22, color=clr),
                                             marker=dict(size=12, symbol='diamond'), showlegend=False), row=1, col=1)
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab_ai:
            st.subheader("🌡️ AI 매수 매력도 온도계")
            g_clr = "#00FF99" if score >= 60 else "#FFCC00" if score >= 40 else "#FF3366"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': g_clr}},
                title={'text': "AI Master Score", 'font': {'size': 24}}
            ))
            fig_g.update_layout(height=400, margin=dict(t=120, b=0), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_g, use_container_width=True)
            st.write(f"• **익절가(Target)**: {cp + (df['ATR'].iloc[-1]*3):,.0f} | **손절가(Stop)**: {cp - (df['ATR'].iloc[-1]*2):,.0f}")

        with tab_sim:
            st.subheader("🔮 5,000회 확률 예측")
            fig_sim = go.Figure()
            for i in range(25): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.2, showlegend=False))
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=4), name="Mean"))
            st.plotly_chart(fig_sim, use_container_width=True)
            st.success(f"📈 1년 뒤 상승 확률: **{(paths[-1, :] > cp).sum() / 50.0:.1f}%** | **추천 비중: {kelly*100:.1f}%**")

        with tab_log:
            st.subheader("📜 매매 상세 로그")
            log_html = "".join([f"<div style='border-bottom:1px solid #222; padding:10px;'>{log}</div>" for log in trade_logs])
            st.markdown(f"<div class='trade-log-box'>{log_html}</div>", unsafe_allow_html=True)

        with tab_news:
            kw = urllib.parse.quote(f"{u_asset} 특징주 OR {u_asset} 주가")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            for e in feed.entries[:10]:
                st.markdown(f"<div class='news-node'><a href='{e.link}' target='_blank' style='color:white;font-weight:700;'>{e.title}</a></div>", unsafe_allow_html=True)

    except Exception as e: st.error(f"시스템 오류: {e}")

if __name__ == "__main__":
    start_ultimate_terminal_v6()
