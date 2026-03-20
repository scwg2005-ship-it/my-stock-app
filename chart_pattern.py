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

# ==========================================
# 1. 시스템 설정 및 프리미엄 UI
# ==========================================
st.set_page_config(layout="wide", page_title="QUANT INFINITY v5.0", page_icon="👑")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&family=JetBrains+Mono&display=swap');
    :root { --neon-blue: #00E5FF; --neon-green: #00FF99; --neon-red: #FF3366; --bg-deep: #030305; --bg-card: #0c0c0e; }
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: var(--bg-deep); color: #E0E0E0; }
    .report-box { background: var(--bg-card); border-left: 10px solid var(--neon-blue); padding: 25px; border-radius: 20px; margin-bottom: 20px; }
    .trade-log { background: #111; border-radius: 10px; padding: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; height: 300px; overflow-y: scroll; border: 1px solid #333; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 900 !important; color: var(--neon-green); }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 데이터 엔진 (분봉/일봉 완벽 지원)
# ==========================================
@st.cache_data(ttl=86400)
def load_krx_all(): return fdr.StockListing('KRX')

def get_ticker_v5(query):
    q = query.strip().replace(" ", "").upper()
    if q.isdigit() and len(q) == 6: return q
    master = load_krx_all()
    match = master[master['Name'].str.upper() == q]
    return match.iloc[0]['Code'] if not match.empty else q

# ==========================================
# 3. 퀀트 코어 클래스 (모든 수식 직접 구현)
# ==========================================
class UltimateEngineV5:
    def __init__(self, df):
        self.df = df.copy()
        if isinstance(self.df.columns, pd.MultiIndex): self.df.columns = self.df.columns.get_level_values(0)

    def process(self):
        # [원시 지표]
        self.df['MA20'] = self.df['Close'].rolling(20).mean()
        self.df['MA60'] = self.df['Close'].rolling(60).mean()
        self.df['MA120'] = self.df['Close'].rolling(120).mean()
        
        # RSI
        diff = self.df['Close'].diff()
        u, d = diff.copy(), diff.copy()
        u[u < 0], d[d > 0] = 0, 0
        self.df['RSI'] = 100 - (100 / (1 + (u.rolling(14).mean() / d.abs().rolling(14).mean())))
        
        # MACD
        e12 = self.df['Close'].ewm(span=12).mean()
        e26 = self.df['Close'].ewm(span=26).mean()
        self.df['MACD_L'] = e12 - e26
        self.df['MACD_S'] = self.df['MACD_L'].ewm(span=9).mean()
        self.df['MACD_H'] = self.df['MACD_L'] - self.df['MACD_S']
        
        # 일목균형표
        h9, l9 = self.df['High'].rolling(9).max(), self.df['Low'].rolling(9).min()
        h26, l26 = self.df['High'].rolling(26).max(), self.df['Low'].rolling(26).min()
        self.df['Tenkan'] = (h9 + l9) / 2
        self.df['Kijun'] = (h26 + l26) / 2
        self.df['SpanA'] = ((self.df['Tenkan'] + self.df['Kijun']) / 2).shift(26)
        self.df['SpanB'] = ((self.df['High'].rolling(52).max() + self.df['Low'].rolling(52).min()) / 2).shift(26)
        
        # [패턴 & 매물대]
        body = abs(self.df['Close'] - self.df['Open'])
        low_s = self.df[['Open','Close']].min(axis=1) - self.df['Low']
        self.df['Hammer'] = (low_s > body * 2)
        
        price_bins = pd.cut(self.df['Close'], bins=20)
        self.poc = self.df.groupby(price_bins, observed=False)['Volume'].sum().idxmax().mid
        
        # [AI 스코어링]
        score = pd.Series(50.0, index=self.df.index)
        score += np.where(self.df['Close'] > self.df['MA20'], 10, -10)
        score += np.where(self.df['MACD_H'] > 0, 10, -5)
        score += np.where(self.df['RSI'] < 30, 20, 0)
        self.df['AI_Score'] = score.clip(0, 100).fillna(50)
        
        # [엘리어트/피보나치]
        self.pks, _ = find_peaks(self.df['High'].values, distance=14, prominence=self.df['High'].std()*0.3)
        self.vls, _ = find_peaks(-self.df['Low'].values, distance=14, prominence=self.df['High'].std()*0.3)
        mx, mn = self.df['High'].max(), self.df['Low'].min()
        self.fib618 = mx - 0.618 * (mx - mn)
        
        return self.df

# ==========================================
# 4. 실전 백테스팅 & 매매 로그 생성 (핵심 요구사항)
# ==========================================
def run_backtest_with_logs(df):
    df['Pos'] = 0
    df.loc[df['AI_Score'] >= 60, 'Pos'] = 1
    df.loc[df['AI_Score'] <= 40, 'Pos'] = 0
    df['Pos'] = df['Pos'].replace(0, np.nan).ffill().fillna(0)
    
    df['Ret'] = df['Close'].pct_change()
    df['Strat_Ret'] = (df['Pos'].shift(1) * df['Ret']) - (df['Pos'].diff().abs() * 0.0003)
    df['Cum_Mkt'] = (1 + df['Ret'].fillna(0)).cumprod() * 100
    df['Cum_Strat'] = (1 + df['Strat_Ret'].fillna(0)).cumprod() * 100
    
    # 매매 로그 생성
    logs = []
    pos_state = 0
    for i in range(1, len(df)):
        current_pos = df['Pos'].iloc[i]
        prev_pos = df['Pos'].iloc[i-1]
        date_str = df.index[i].strftime('%Y-%m-%d %H:%M')
        price = df['Close'].iloc[i]
        
        if current_pos == 1 and prev_pos == 0:
            logs.append(f"🟢 [{date_str}] 매수 진입 | 가격: {price:,.0f}")
        elif current_pos == 0 and prev_pos == 1:
            logs.append(f"🔴 [{date_str}] 매도 탈출 | 가격: {price:,.0f}")
            
    return df, logs[::-1] # 최신순 정렬

# ==========================================
# 5. 메인 앱 레이아웃
# ==========================================
st.sidebar.title("👑 MASTER CTRL v5.0")
target = st.sidebar.text_input("종목명/티커", value="SK하이닉스")
symbol = get_ticker_v5(target)

# 분봉/일봉 선택 (사용자 요청)
t_frame = st.sidebar.selectbox("차트 주기 설정", ["일봉", "60분봉", "15분봉", "5분봉"])
p_range = st.sidebar.select_slider("분석 데이터 범위", options=["1mo", "3mo", "6mo", "1y", "2y"], value="1y")

if symbol.isdigit():
    m_info = load_krx_all()[load_krx_all()['Code']==symbol]['Market'].iloc[0]
    ticker = f"{symbol}.KS" if m_info == "KOSPI" else f"{symbol}.KQ"
else: ticker = symbol

try:
    # 주기별 데이터 로드
    int_map = {"일봉":"1d", "60분봉":"60m", "15분봉":"15m", "5분봉":"5m"}
    raw = yf.download(ticker, period="1mo" if "분" in t_frame else p_range, interval=int_map[t_frame], progress=False)
    
    if not raw.empty:
        engine = UltimateEngineV5(raw)
        df = engine.process()
        df, trade_logs = run_backtest_with_logs(df)
        cp, score = df['Close'].iloc[-1], df['AI_Score'].iloc[-1]

        st.markdown(f"## 💎 QUANT TERMINAL v5.0 | {target}")
        
        # 상단 핵심 지표
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("실시간 현재가", f"{cp:,.0f}", f"{((cp/df['Close'].iloc[-2]-1)*100):+.2f}%")
        c2.metric("AI 퀀트 점수", f"{score:.0f}")
        c3.metric("누적 전략 수익률", f"{df['Cum_Strat'].iloc[-1]-100:+.2f}%")
        c4.metric("매물대 POC", f"{engine.poc:,.0f}")

        tabs = st.tabs(["📊 마스터 분석 차트", "🌡️ AI 온도계 & 전략", "🔮 5,000회 확률 예측", "📜 실전 매매 내역", "⚡ 뉴스"])

        with tabs[0]:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
            # 일목구름
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanB'], fill='tonexty', fillcolor='rgba(0, 255, 153, 0.05)', name="구름대"), row=1, col=1)
            # 엘리어트 숫자
            lbls = ['1','2','3','4','5','A','B','C']
            merged = sorted([('p',i,df['High'].iloc[i]) for i in engine.pks]+[('v',i,df['Low'].iloc[i]) for i in engine.vls], key=lambda x:x[1])[-8:]
            for idx, pt in enumerate(merged):
                if idx < len(lbls):
                    clr = "#00FF99" if pt[0]=='v' else "#FF3366"
                    fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{lbls[idx]}</b>"], 
                                             textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=22, color=clr),
                                             marker=dict(color=clr, size=12, symbol='diamond'), showlegend=False), row=1, col=1)
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tabs[1]:
            # [1번 온도계 복구]
            st.subheader("🌡️ AI 매수 매력도 온도계")
            g_clr = "#00FF99" if score >= 60 else "#FFCC00" if score >= 40 else "#FF3366"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': g_clr}},
                title={'text': "AI MASTER SCORE", 'font': {'size': 24}}
            ))
            fig_g.update_layout(height=400, margin=dict(t=100, b=0), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_g, use_container_width=True)
            
            st.markdown("<div class='report-box'>", unsafe_allow_html=True)
            st.write(f"#### 🔍 {target} 실전 가격 전략")
            st.write(f"• **익절 목표가**: {cp + (df['Close'].diff().std() * 3):,.0f} (변동성 3배 적용)")
            st.write(f"• **손절 마지노선**: {cp - (df['Close'].diff().std() * 2):,.0f} (보수적 2배 적용)")
            st.write(f"• **피보나치 61.8%**: {engine.fib618:,.0f} 원")
            st.markdown("</div>", unsafe_allow_html=True)

        with tabs[2]:
            st.subheader("🔮 5,000회 확률적 자산 예측")
            rets = df['Close'].pct_change().dropna()
            mu, sigma = rets.mean(), rets.std()
            shocks = np.random.normal(mu, sigma, (252, 5000))
            paths = cp * np.exp(np.cumsum(shocks, axis=0))
            
            fig_sim = go.Figure()
            for i in range(25): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.2, showlegend=False))
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=4), name="평균 경로"))
            fig_sim.update_layout(height=550, template="plotly_dark")
            st.plotly_chart(fig_sim, use_container_width=True)
            
            prob_up = (paths[-1, :] > cp).sum() / 50.0
            st.success(f"📈 5,000회 시뮬레이션 결과, 1년 뒤 자산 가치 상승 확률은 **{prob_up:.1f}%** 입니다.")

        with tabs[3]:
            # [수익률의 근거: 매매 내역 로그]
            st.subheader("📜 AI 퀀트 매매 실행 내역 (Trade Logs)")
            st.info(f"누적 수익률 {df['Cum_Strat'].iloc[-1]-100:+.2f}% 의 상세 거래 기록입니다.")
            log_html = "".join([f"<div style='margin-bottom:5px;'>{log}</div>" for log in trade_logs])
            st.markdown(f"<div class='trade-log'>{log_html}</div>", unsafe_allow_html=True)

        with tabs[4]:
            st.subheader("⚡ 글로벌 인텔리전스")
            kw = urllib.parse.quote(f"{target} 특징주 OR {target} 주가")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            for e in feed.entries[:10]:
                st.markdown(f"<div style='padding:15px; border-bottom:1px solid #222;'><a href='{e.link}' target='_blank' style='color:white;text-decoration:none;font-weight:700;'>{e.title}</a></div>", unsafe_allow_html=True)

except Exception as e: st.error(f"시스템 오류: {e}")
