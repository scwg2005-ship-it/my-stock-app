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

# ==============================================================================
# [MODULE 1] PREMIUM TERMINAL UI CONFIGURATION (CSS & LAYOUT)
# ==============================================================================
st.set_page_config(layout="wide", page_title="QUANT INFINITY PRO v2.0", page_icon="💎")

def apply_terminal_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;500&family=Pretendard:wght@100;400;700;900&display=swap');
        
        :root {
            --bg-main: #050507;
            --bg-card: #0c0c0e;
            --neon-green: #00ff66;
            --neon-blue: #00e5ff;
            --neon-purple: #9d00ff;
            --neon-red: #ff3366;
            --border: #1e1e24;
        }

        html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: var(--bg-main); color: #e0e0e0; }

        /* 하이엔드 터미널 탭 스타일 */
        .stTabs [data-baseweb="tab-list"] { gap: 20px; background-color: #0a0a0c; padding: 15px 25px; border-radius: 15px; border: 1px solid var(--border); }
        .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: 800; color: #555; transition: 0.4s; }
        .stTabs [aria-selected="true"] { color: var(--neon-blue) !important; text-shadow: 0 0 12px var(--neon-blue); }

        /* 리포트 섹션: 글래스모피즘 */
        .analysis-card {
            background: linear-gradient(145deg, #0f0f12, #08080a);
            border: 1px solid var(--border);
            border-left: 8px solid var(--neon-green);
            padding: 35px; border-radius: 25px; margin-bottom: 35px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.8);
        }
        
        .report-title { font-size: 2rem; font-weight: 900; color: var(--neon-green); margin-bottom: 20px; }
        .metric-value { font-size: 2.2rem; font-weight: 900; color: var(--neon-green); }

        /* 패턴 태그 */
        .pattern-tag { padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; margin-right: 5px; background: rgba(0,229,255,0.1); color: var(--neon-blue); border: 1px solid var(--neon-blue); }

        /* 애니메이션 */
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        .live-dot { width: 12px; height: 12px; background: var(--neon-red); border-radius: 50%; display: inline-block; margin-right: 8px; animation: pulse 2s infinite; }
        </style>
    """, unsafe_allow_html=True)

apply_terminal_style()

# ==============================================================================
# [MODULE 2] SMART DATA AGGREGATOR & TICKER RESOLVER
# ==============================================================================
@st.cache_data(ttl=86400)
def load_full_krx_listing():
    return fdr.StockListing('KRX')

def resolve_ticker_expert(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    krx = load_full_krx_listing()
    match = krx[krx['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not match.empty: return match.iloc[0]['Code']
    # 글로벌 티커 확장
    global_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "비트코인": "BTC-USD"}
    return global_map.get(query, query)

# ==============================================================================
# [MODULE 3] RAW MATH INDICATOR ENGINE (NO EXTERNAL TA LIBRARIES)
# ==============================================================================
class RawIndicatorEngine:
    @staticmethod
    def calculate_sma(series, n): return series.rolling(window=n).mean()

    @staticmethod
    def calculate_ema(series, n): return series.ewm(span=n, adjust=False).mean()

    @staticmethod
    def calculate_rsi(series, n=14):
        delta = series.diff()
        u, d = delta.copy(), delta.copy()
        u[u < 0], d[d > 0] = 0, 0
        avg_u = u.rolling(window=n).mean()
        avg_d = d.abs().rolling(window=n).mean()
        return 100 - (100 / (1 + (avg_u / avg_d)))

    @staticmethod
    def calculate_macd(series):
        e12, e26 = series.ewm(span=12).mean(), series.ewm(span=26).mean()
        macd = e12 - e26
        sig = macd.ewm(span=9).mean()
        return macd, sig, macd - sig

    @staticmethod
    def calculate_bollinger(series, n=20):
        ma = series.rolling(n).mean()
        std = series.rolling(n).std()
        return ma + (std*2), ma, ma - (std*2)

    @staticmethod
    def calculate_ichimoku(df):
        h9, l9 = df['High'].rolling(9).max(), df['Low'].rolling(9).min()
        df['Tenkan'] = (h9 + l9) / 2
        h26, l26 = df['High'].rolling(26).max(), df['Low'].rolling(26).min()
        df['Kijun'] = (h26 + l26) / 2
        df['SpanA'] = ((df['Tenkan'] + df['Kijun']) / 2).shift(26)
        h52, l52 = df['High'].rolling(52).max(), df['Low'].rolling(52).min()
        df['SpanB'] = ((h52 + l52) / 2).shift(26)
        return df

# ==============================================================================
# [MODULE 4] ADVANCED GEOMETRY: ELLIOTT, FIBONACCI, VOLUME PROFILE
# ==============================================================================
class GeometryEngine:
    def __init__(self, df):
        self.df = df

    def analyze(self):
        # 1. 엘리어트 파동 변곡점 (Peak & Valley)
        pks, _ = find_peaks(self.df['High'].values, distance=12, prominence=self.df['High'].std()*0.3)
        vls, _ = find_peaks(-self.df['Low'].values, distance=12, prominence=self.df['Low'].std()*0.3)
        
        # 2. 피보나치 되돌림 라인
        max_p, min_p = self.df['High'].max(), self.df['Low'].min()
        diff = max_p - min_p
        fib = {
            'L236': max_p - 0.236 * diff,
            'L382': max_p - 0.382 * diff,
            'L500': max_p - 0.5 * diff,
            'L618': max_p - 0.618 * diff
        }
        
        # 3. 매물대 분석 (Volume Profile)
        price_bins = pd.cut(self.df['Close'], bins=15)
        v_profile = self.df.groupby(price_bins, observed=False)['Volume'].sum()
        poc = v_profile.idxmax().mid # 가장 거래 많은 가격대
        
        return pks, vls, fib, poc

# ==============================================================================
# [MODULE 5] PROBABILISTIC RISK & SIMULATION (MONTE CARLO)
# ==============================================================================
class RiskEngine:
    def __init__(self, df):
        self.df = df
        self.returns = df['Close'].pct_change().dropna()

    def run_simulation(self, n=1000, days=252):
        mu, sigma = self.returns.mean(), self.returns.std()
        last = self.df['Close'].iloc[-1]
        paths = np.zeros((days, n))
        for i in range(n):
            p = [last]
            for _ in range(days-1):
                p.append(p[-1] * np.exp((mu - 0.5 * sigma**2) + sigma * norm.ppf(np.random.rand())))
            paths[:, i] = p
        return paths

    def get_var_mdd(self):
        # VaR (95% 신뢰수준)
        var = np.percentile(self.returns, 5)
        # MDD
        cum = (1 + self.returns).cumprod()
        peak = cum.cummax()
        mdd = ((cum - peak) / peak).min()
        return var, mdd

# ==============================================================================
# [MODULE 6] MASTER BACKTESTING ENGINE
# ==============================================================================
def run_master_backtest(df):
    # AI 점수 정밀 산출 (가중치 7종)
    eng = RawIndicatorEngine()
    s = pd.Series(50.0, index=df.index)
    s += np.where(df['Close'] > df['MA20'], 12, -12)
    s += np.where(df['MACD_Hist'] > 0, 10, -10)
    s += np.where(df['RSI'] < 30, 15, 0)
    s += np.where(df['Close'] > df['SpanA'], 13, -13)
    # 캔들 패턴 가중치
    body = abs(df['Close'] - df['Open'])
    low_s = df[['Open','Close']].min(axis=1) - df['Low']
    s += np.where(low_s > body*2, 10, 0) # 망치형 가점
    
    df['AI_Score'] = s.clip(0, 100).fillna(50)
    
    # 백테스트 실행 (수수료 0.03% 반영)
    df['Pos'] = (df['AI_Score'] >= 60).astype(int)
    df['Mkt_Ret'] = df['Close'].pct_change()
    df['Strat_Ret'] = df['Pos'].shift(1) * df['Mkt_Ret']
    trade_cost = df['Pos'].diff().abs() * 0.0003
    df['Net_Ret'] = df['Strat_Ret'] - trade_cost
    
    df['Cum_Mkt'] = (1 + df['Mkt_Ret'].fillna(0)).cumprod() * 100
    df['Cum_Strat'] = (1 + df['Net_Ret'].fillna(0)).cumprod() * 100
    return df

# ==============================================================================
# [MODULE 7] INTEGRATED FRONTEND EXECUTION
# ==============================================================================
def start_quant_infinity():
    st.sidebar.markdown("### 🛠️ INFINITY MASTER CTRL")
    u_name = st.sidebar.text_input("종목명/코드", value="SK하이닉스")
    ticker = resolve_ticker_expert(u_name)
    
    if ticker.isdigit():
        krx = load_full_krx_listing()
        ticker = f"{ticker}.KS" if krx[krx['Code']==ticker]['Market'].iloc[0]=='KOSPI' else f"{ticker}.KQ"

    t_frame = st.sidebar.selectbox("주기", ["일봉", "60분봉", "15분봉", "5분봉"])
    p_range = st.sidebar.select_slider("분석 범위", options=["3mo", "6mo", "1y", "2y"], value="1y")

    try:
        raw = yf.download(ticker, period=p_range if "봉" not in t_frame else "1mo", 
                         interval={"일봉":"1d","60분봉":"60m","15분봉":"15m","5분봉":"5m"}.get(t_frame, "1d"), progress=False)
        
        if raw.empty: return st.error("데이터 로드 실패")
        if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)

        # 1. 지표 및 엔진 구동
        eng = RawIndicatorEngine()
        df = raw.copy()
        df['MA20'] = eng.calculate_sma(df['Close'], 20)
        df['RSI'] = eng.calculate_rsi(df['Close'])
        df['MACD'], _, df['MACD_Hist'] = eng.calculate_macd(df['Close'])
        df = eng.calculate_ichimoku(df)
        
        # 2. 기하학 분석
        geo = GeometryEngine(df)
        pks, vls, fib, poc = geo.analyze()
        
        # 3. 리스크 및 백테스트
        df = run_master_backtest(df)
        risk = RiskEngine(df)
        var, mdd = risk.get_var_mdd()

        # ----------------------------------------------------------------------
        # UI 렌더링
        # ----------------------------------------------------------------------
        st.markdown(f"## <span class='live-dot'></span>QUANT INFINITY TERMINAL v2.0 | {u_name}")
        
        # 상단 메트릭
        cp = df['Close'].iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PRICE", f"{cp:,.0f}", f"{((cp/df['Close'].iloc[-2]-1)*100):+.2f}%")
        c2.metric("AI SCORE", f"{df['AI_Score'].iloc[-1]:.0f} PTS")
        c3.metric("VaR (95%)", f"{abs(var*100):.1f}%", delta_color="inverse")
        c4.metric("MDD", f"{mdd*100:.1f}%", delta_color="inverse")

        tabs = st.tabs(["📊 MASTER CHART", "🧠 QUANT REPORT", "🔮 SIMULATION", "⚡ NEWS"])

        with tabs[0]:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="PRICE"), row=1, col=1)
            
            # 일목 구름대 및 POC
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanB'], fill='tonexty', fillcolor='rgba(0, 255, 102, 0.05)', name="KUMO"), row=1, col=1)
            fig.add_hline(y=poc, line=dict(color="rgba(255,255,255,0.3)", dash="dash"), annotation_text="POC", row=1, col=1)
            
            # 피보나치 라인
            for k, v in fib.items():
                fig.add_hline(y=v, line=dict(color="rgba(0,229,255,0.2)", width=1), row=1, col=1)

            # 엘리어트 파동 레이블
            w_lbl = ['1','2','3','4','5','A','B','C']
            pts = sorted([('p',i,df['High'].iloc[i]) for i in pks]+[('v',i,df['Low'].iloc[i]) for i in vls], key=lambda x:x[1])[-8:]
            for idx, pt in enumerate(pts):
                if idx < len(w_lbl):
                    clr = "#00FF99" if pt[0]=='v' else "#FF3366"
                    fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{w_lbl[idx]}</b>"], 
                                             textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=24, color=clr),
                                             marker=dict(color=clr, size=14, symbol='diamond'), showlegend=False), row=1, col=1)
            
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=['#FF3366' if x<0 else '#00FF99' for x in df['MACD_Hist']]), row=2, col=1)
            fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tabs[1]:
            st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
            st.markdown("<div class='report-title'>🔍 AI 기술적 심층 분석</div>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("#### 📐 지지/저항 공간 분석")
                st.write(f"- **매물대 POC**: {poc:,.0f}원 (가장 강력한 매수/매도 대립 구간)")
                st.write(f"- **피보나치 61.8%**: {fib['L618']:,.0f}원 (황금 분할 지지선)")
                st.write(f"- **일목 기준선**: {df['Kijun'].iloc[-1]:,.0f}원")
            with col_b:
                st.write("#### 🛡️ 가격 대응 전략")
                st.info(f"**목표가 (익절)**: {cp*1.15:,.0f}원 | **손절가 (대피)**: {cp*0.93:,.0f}원")
                st.write(f"현재 AI 점수는 **{df['AI_Score'].iloc[-1]:.0f}점**으로, {'적극 매수' if df['AI_Score'].iloc[-1]>60 else '관망 및 현금화'}를 권장합니다.")
            st.markdown("</div>", unsafe_allow_html=True)

        with tabs[2]:
            st.subheader("🔮 몬테카를로 시뮬레이션 (확률적 예측)")
            paths = risk.run_simulation()
            fig_sim = go.Figure()
            for i in range(20): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.3, showlegend=False))
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=3), name="EXPECTED"))
            fig_sim.update_layout(height=550, template="plotly_dark")
            st.plotly_chart(fig_sim, use_container_width=True)
            
            p_up = (paths[-1, :] > cp).sum() / 10.0
            st.success(f"통계적 시뮬레이션 결과, 1년 후 주가가 현재보다 상승할 확률은 **{p_up:.1f}%**입니다.")

        with tabs[3]:
            st.subheader("⚡ 실시간 특징주 뉴스")
            kw = urllib.parse.quote(f"{u_name} 특징주")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            for e in feed.entries[:10]:
                st.markdown(f"<div style='padding:15px; border-bottom:1px solid #222;'><a href='{e.link}' target='_blank' style='color:white; text-decoration:none;'><b>{e.title}</b></a><br><small>{e.published}</small></div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"ENGINE ERROR: {e}")

if __name__ == "__main__":
    start_quant_infinity()
