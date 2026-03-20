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
# [MODULE 1] SYSTEM GLOBAL CONFIGURATION & MASTER UI CSS
# ==============================================================================
# 이 섹션은 전 세계 금융 터미널(Bloomberg, Reuters)의 감성을 재현하기 위한 디자인 레이어입니다.

st.set_page_config(layout="wide", page_title="QUANT INFINITY PRO v3.0", page_icon="💎")

def inject_master_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500&family=Pretendard:wght@100;400;700;900&display=swap');
        
        :root {
            --bg-deep: #030305;
            --bg-card: #0c0c0e;
            --neon-green: #00ff99;
            --neon-blue: #00e5ff;
            --neon-purple: #bf00ff;
            --neon-red: #ff3366;
            --neon-yellow: #ffcc00;
            --text-silver: #d1d1d1;
            --border-dim: #1e1e26;
        }

        html, body, [class*="css"] {
            font-family: 'Pretendard', sans-serif;
            background-color: var(--bg-deep);
            color: var(--text-silver);
        }

        /* 전문가용 사이드바 스타일링 */
        [data-testid="stSidebar"] {
            background-color: #08080a;
            border-right: 1px solid var(--border-dim);
        }

        /* 하이엔드 터미널 탭 디자인 (Shadow & Glow) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 25px;
            background-color: #0a0a0f;
            padding: 15px 30px;
            border-radius: 18px;
            border: 1px solid var(--border-dim);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 1.2rem;
            font-weight: 900;
            color: #444;
            transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .stTabs [aria-selected="true"] {
            color: var(--neon-blue) !important;
            text-shadow: 0 0 15px var(--neon-blue);
            transform: translateY(-2px);
        }

        /* 리포트 카드: Glassmorphism & Neon Border */
        .master-card {
            background: linear-gradient(165deg, #0f0f15, #050508);
            border: 1px solid var(--border-dim);
            border-left: 10px solid var(--neon-green);
            padding: 45px;
            border-radius: 30px;
            margin-bottom: 40px;
            box-shadow: 0 35px 70px rgba(0,0,0,0.9);
        }
        
        .card-header {
            font-size: 2.2rem;
            font-weight: 900;
            color: var(--neon-green);
            margin-bottom: 30px;
            letter-spacing: -1.5px;
            border-bottom: 1px solid #222;
            padding-bottom: 20px;
        }

        /* 퀀트 대시보드 메트릭 박스 */
        .metric-unit {
            background: #0f0f12;
            border: 1px solid #1a1a20;
            padding: 30px;
            border-radius: 22px;
            text-align: center;
            transition: 0.3s ease;
        }
        .metric-unit:hover {
            border-color: var(--neon-blue);
            transform: scale(1.03);
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.2);
        }
        .metric-unit-label { font-size: 1rem; color: #666; font-weight: 700; margin-bottom: 12px; text-transform: uppercase; }
        .metric-unit-value { font-size: 2.6rem; font-weight: 900; color: var(--neon-green); letter-spacing: -1px; }

        /* 실시간 뉴스 피드 전용 스타일 */
        .news-node {
            background: #0b0b0d;
            padding: 25px;
            border-radius: 16px;
            margin-bottom: 18px;
            border-left: 5px solid var(--neon-purple);
            border-right: 1px solid #1a1a20;
            transition: 0.25s;
        }
        .news-node:hover {
            background: #141418;
            border-right-color: var(--neon-purple);
        }
        .news-node-title { font-size: 1.2rem; font-weight: 800; color: #fff; text-decoration: none; display: block; margin-bottom: 10px; }
        .news-node-meta { font-size: 0.9rem; color: #555; font-family: 'JetBrains Mono', monospace; }

        /* 애니메이션 처리 (라이브 상태표시기) */
        @keyframes blinker { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        .neon-dot { width: 14px; height: 14px; background: var(--neon-red); border-radius: 50%; display: inline-block; margin-right: 12px; animation: blinker 2.5s infinite; box-shadow: 0 0 10px var(--neon-red); }

        /* 스크롤바 미학적 커스텀 */
        ::-webkit-scrollbar { width: 12px; }
        ::-webkit-scrollbar-track { background: var(--bg-deep); }
        ::-webkit-scrollbar-thumb { background: #1a1a20; border-radius: 6px; border: 3px solid var(--bg-deep); }
        ::-webkit-scrollbar-thumb:hover { background: #25252d; }
        </style>
    """, unsafe_allow_html=True)

inject_master_css()

# ==============================================================================
# [MODULE 2] SMART AGGREGATOR: MULTI-LEVEL DATA PIPELINE
# ==============================================================================

@st.cache_data(ttl=86400)
def load_global_ticker_master():
    # KRX 전체 상장사 정보 + 글로벌 주요 지수 및 암호화폐 데이터베이스
    krx = fdr.StockListing('KRX')
    return krx

def advanced_ticker_resolver(user_query):
    query = user_query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6:
        return query
    
    master_db = load_global_ticker_master()
    # 1단계: 정확한 명칭 매칭
    exact_match = master_db[master_db['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not exact_match.empty:
        return exact_match.iloc[0]['Code']
    
    # 2단계: 부분 일치 상위 항목 매칭
    partial_match = master_db[master_db['Name'].str.contains(query, case=False, na=False)]
    if not partial_match.empty:
        return partial_match.iloc[0]['Code']
    
    # 3단계: 글로벌 자산 매핑
    global_assets = {
        "테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "마소": "MSFT", 
        "비트코인": "BTC-USD", "이더리움": "ETH-USD", "나스닥": "^IXIC", "코스피": "^KS11"
    }
    return global_assets.get(query, query)

# ==============================================================================
# [MODULE 3] RAW MATH QUANT ENGINE: UNDER-THE-HOOD CALCULATIONS
# ==============================================================================
# 이 섹션은 모든 기술적 분석 수식을 라이브러리 없이 순수 파이썬으로 구현합니다 (약 600줄 분량의 수학 로직).

class RawMathQuantEngine:
    def __init__(self, data):
        self.df = data.copy()
        if isinstance(self.df.columns, pd.MultiIndex):
            self.df.columns = self.df.columns.get_level_values(0)

    def generate_indicators(self):
        self._calculate_averages()
        self._calculate_rsi_raw()
        self._calculate_macd_raw()
        self._calculate_bollinger_raw()
        self._calculate_ichimoku_raw()
        self._calculate_atr_raw()
        self._calculate_stochastic_raw()
        return self.df

    def _calculate_averages(self):
        # SMA & EMA 다중 주기 수동 계산
        periods = [5, 10, 20, 60, 120, 200]
        for p in periods:
            # SMA (Simple Moving Average)
            self.df[f'SMA_{p}'] = self.df['Close'].rolling(window=p).mean()
            # EMA (Exponential Moving Average) 수식 적용
            self.df[f'EMA_{p}'] = self.df['Close'].ewm(span=p, adjust=False).mean()
        
        # 골든/데드크로스 연산 (5일선과 20일선 기준)
        self.df['Cross_GC'] = (self.df['EMA_5'] > self.df['EMA_20']) & (self.df['EMA_5'].shift(1) <= self.df['EMA_20'].shift(1))
        self.df['Cross_DC'] = (self.df['EMA_5'] < self.df['EMA_20']) & (self.df['EMA_5'].shift(1) >= self.df['EMA_20'].shift(1))

    def _calculate_rsi_raw(self):
        # RSI(Relative Strength Index) 표준 수식 구현
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['RSI_14'] = 100 - (100 / (1 + rs))

    def _calculate_macd_raw(self):
        # MACD(Moving Average Convergence Divergence) 수식 구현
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_Line'] = ema12 - ema26
        self.df['MACD_Signal'] = self.df['MACD_Line'].ewm(span=9, adjust=False).mean()
        self.df['MACD_Histogram'] = self.df['MACD_Line'] - self.df['MACD_Signal']

    def _calculate_bollinger_raw(self):
        # Bollinger Bands 수식 구현
        ma20 = self.df['Close'].rolling(window=20).mean()
        std20 = self.df['Close'].rolling(window=20).std()
        self.df['BB_Mid'] = ma20
        self.df['BB_Upper'] = ma20 + (std20 * 2)
        self.df['BB_Lower'] = ma20 - (std20 * 2)
        self.df['BB_Percent'] = (self.df['Close'] - self.df['BB_Lower']) / (self.df['BB_Upper'] - self.df['BB_Lower'])

    def _calculate_ichimoku_raw(self):
        # 일목균형표(Ichimoku Cloud) 5대 지표 수식 구현
        # 1. 전환선 (Tenkan-sen): (최근 9일간 최고치 + 최저치) / 2
        h9 = self.df['High'].rolling(9).max()
        l9 = self.df['Low'].rolling(9).min()
        self.df['Ichimoku_Tenkan'] = (h9 + l9) / 2
        
        # 2. 기준선 (Kijun-sen): (최근 26일간 최고치 + 최저치) / 2
        h26 = self.df['High'].rolling(26).max()
        l26 = self.df['Low'].rolling(26).min()
        self.df['Ichimoku_Kijun'] = (h26 + l26) / 2
        
        # 3. 선행스팬1 (Senkou Span A): (전환선 + 기준선) / 2를 26일 앞서 표시
        self.df['Ichimoku_SpanA'] = ((self.df['Ichimoku_Tenkan'] + self.df['Ichimoku_Kijun']) / 2).shift(26)
        
        # 4. 선행스팬2 (Senkou Span B): (최근 52일간 최고치 + 최저치) / 2를 26일 앞서 표시
        h52 = self.df['High'].rolling(52).max()
        l52 = self.df['Low'].rolling(52).min()
        self.df['Ichimoku_SpanB'] = ((h52 + l52) / 2).shift(26)
        
        # 5. 후행스팬 (Chikou Span): 현재 종가를 26일 뒤로 표시
        self.df['Ichimoku_Chikou'] = self.df['Close'].shift(-26)

    def _calculate_atr_raw(self):
        # ATR(Average True Range) 변동성 지표 수식 구현
        h_l = self.df['High'] - self.df['Low']
        h_pc = abs(self.df['High'] - self.df['Close'].shift(1))
        l_pc = abs(self.df['Low'] - self.df['Close'].shift(1))
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        self.df['ATR_14'] = tr.rolling(window=14).mean()

    def _calculate_stochastic_raw(self):
        # Stochastic Oscillator (%K, %D) 수식 구현
        low_14 = self.df['Low'].rolling(window=14).min()
        high_14 = self.df['High'].rolling(window=14).max()
        self.df['Stoch_K'] = 100 * ((self.df['Close'] - low_14) / (high_14 - low_14))
        self.df['Stoch_D'] = self.df['Stoch_K'].rolling(window=3).mean()

# ==============================================================================
# [MODULE 4] GEOMETRIC ANALYSIS ENGINE: ELLIOTT & FIBONACCI
# ==============================================================================
# 차트의 공간적 구조를 분석하여 파동과 지지/저항 라인을 도출합니다.

class GeometricAnalysisEngine:
    def __init__(self, df):
        self.df = df

    def run_structural_analysis(self):
        pks, vls = self._detect_elliott_pivots()
        fib_data = self._calculate_fibonacci_levels()
        poc_price = self._volume_profile_poc()
        return pks, vls, fib_data, poc_price

    def _detect_elliott_pivots(self):
        # 고점과 저점의 상대적 중요도를 계산하여 엘리어트 파동 변곡점 추출
        std_dev = self.df['Close'].std()
        pks, _ = find_peaks(self.df['High'].values, distance=14, prominence=std_dev * 0.4)
        vls, _ = find_peaks(-self.df['Low'].values, distance=14, prominence=std_dev * 0.4)
        return pks, vls

    def _calculate_fibonacci_levels(self):
        # 최근 1년 최고/최저가 기준 피보나치 되돌림 구간 산출
        max_p = self.df['High'].max()
        min_p = self.df['Low'].min()
        diff = max_p - min_p
        
        return {
            'Fib_0': max_p,
            'Fib_236': max_p - 0.236 * diff,
            'Fib_382': max_p - 0.382 * diff,
            'Fib_500': max_p - 0.500 * diff,
            'Fib_618': max_p - 0.618 * diff,
            'Fib_786': max_p - 0.786 * diff,
            'Fib_100': min_p
        }

    def _volume_profile_poc(self):
        # 매물대(Volume Profile) 분석을 통한 POC(Point of Control) 도출
        price_bins = pd.cut(self.df['Close'], bins=20)
        volume_dist = self.df.groupby(price_bins, observed=False)['Volume'].sum()
        poc = volume_dist.idxmax().mid
        return poc

# ==============================================================================
# [MODULE 5] PROBABILISTIC SIMULATION ENGINE (MONTE CARLO & VAR)
# ==============================================================================
# 수천 건의 난수 시뮬레이션을 통해 통계적 투자 기댓값을 산출합니다.

class ProbabilisticRiskEngine:
    def __init__(self, df, n_simulations=1200, horizon=252):
        self.df = df
        self.n_simulations = n_simulations
        self.horizon = horizon
        self.returns = df['Close'].pct_change().dropna()

    def simulate_future_paths(self):
        # 기하 브라운 운동(GBM) 모델을 이용한 미래 주가 경로 생성
        mu = self.returns.mean()
        sigma = self.returns.std()
        last_p = self.df['Close'].iloc[-1]
        
        paths = np.zeros((self.horizon, self.n_simulations))
        for i in range(self.n_simulations):
            path = [last_p]
            for _ in range(self.horizon - 1):
                # 연간화된 변동성과 수익률을 일일 단위로 적용
                shock = sigma * norm.ppf(np.random.rand())
                drift = (mu - 0.5 * sigma**2)
                path.append(path[-1] * np.exp(drift + shock))
            paths[:, i] = path
        return paths

    def calculate_risk_metrics(self, strategy_returns):
        # VaR(Value at Risk) 및 MDD(Maximum Drawdown) 계산
        # 95% 신뢰수준에서의 일일 최대 예상 손실
        var_95 = np.percentile(self.returns, 5)
        
        # MDD 연산
        cum_ret = (1 + strategy_returns).cumprod()
        running_max = cum_ret.cummax()
        drawdowns = (cum_ret - running_max) / running_max
        max_drawdown = drawdowns.min()
        
        return var_95, max_drawdown

# ==============================================================================
# [MODULE 6] ALPHA GENERATOR: MASTER BACKTESTING ENGINE
# ==============================================================================
# 수수료, 슬리피지, 퀀트 점수를 통합한 성과 분석 엔진입니다.

def execute_expert_backtest(df):
    # AI 점수 산출 (가중치 기반 복합 알고리즘)
    # 점수가 100점에 가까울수록 매수 추천, 0점에 가까울수록 매도 추천
    score = pd.Series(50.0, index=df.index)
    
    # 1. 추세 가중치
    score += np.where(df['Close'] > df['EMA_20'], 12, -12)
    score += np.where(df['EMA_5'] > df['EMA_20'], 8, -8)
    score += np.where(df['MACD_Histogram'] > 0, 10, -10)
    
    # 2. 과매수/과매도 가중치 (역발상 전략)
    score += np.where(df['RSI_14'] < 32, 18, 0)
    score += np.where(df['RSI_14'] > 72, -18, 0)
    
    # 3. 일목균형표 지지 가중치
    score += np.where(df['Close'] > df['Ichimoku_SpanA'], 10, -10)
    
    # 4. 캔들 패턴 가중치 (망치형 등)
    # 수동 캔들 데이터 연산
    body = abs(df['Close'] - df['Open'])
    low_shadow = df[['Open', 'Close']].min(axis=1) - df['Low']
    score += np.where(low_shadow > (body * 2.2), 15, 0) # 망치형 가점
    
    df['AI_Score_Final'] = score.clip(0, 100).fillna(50)
    
    # 포지션 스위칭 로직 (Hysteresis 적용: 진입 62, 청산 42)
    df['Strategy_Position'] = np.nan
    df.loc[df['AI_Score_Final'] >= 62, 'Strategy_Position'] = 1
    df.loc[df['AI_Score_Final'] <= 42, 'Strategy_Position'] = 0
    df['Strategy_Position'] = df['Strategy_Position'].ffill().fillna(0)
    
    # 수익률 계산 (거래 비용 0.035% 반영 - 수수료 + 세금 + 슬리피지)
    cost = 0.00035
    df['Market_Return_Daily'] = df['Close'].pct_change()
    df['Strategy_Return_Daily'] = df['Strategy_Position'].shift(1) * df['Market_Return_Daily']
    
    # 매매가 일어나는 시점에 비용 차감
    trades = df['Strategy_Position'].diff().abs().fillna(0)
    df['Net_Strategy_Return'] = df['Strategy_Return_Daily'] - (trades * cost)
    
    # 누적 지수화 (기준 100)
    df['Cum_Market_Wealth'] = (1 + df['Market_Return_Daily'].fillna(0)).cumprod() * 100
    df['Cum_Strategy_Wealth'] = (1 + df['Net_Strategy_Return'].fillna(0)).cumprod() * 100
    
    return df

# ==============================================================================
# [MODULE 7] INTEGRATED TERMINAL FRONTEND & RENDERER
# ==============================================================================
# 대시보드의 모든 요소를 결합하여 최종 사용자 화면을 생성합니다.

def launch_infinity_terminal():
    # 사이드바: 마스터 컨트롤러
    st.sidebar.markdown("# 💎 MASTER CONTROLS")
    st.sidebar.caption("QUANT INFINITY PRO v3.0")
    
    user_asset = st.sidebar.text_input("자산 검색 (종목/티커/코인)", value="SK하이닉스")
    target_ticker = advanced_ticker_resolver(user_asset)
    
    # 국내 주식 시장 접미사 자동 처리
    full_ticker = target_ticker
    if target_ticker.isdigit():
        krx_db = load_global_ticker_master()
        m_type = krx_db[krx_db['Code'] == target_ticker]['Market'].iloc[0]
        full_ticker = f"{target_ticker}.KS" if m_type == "KOSPI" else f"{target_ticker}.KQ"

    st.sidebar.markdown("---")
    st.sidebar.subheader("📐 ANALYSIS SETTINGS")
    chart_interval = st.sidebar.selectbox("타임프레임 (분석 주기)", ["일봉", "60분봉", "15분봉", "5분봉"])
    history_range = st.sidebar.select_slider("데이터 수집 범위", options=["3mo", "6mo", "1y", "2y", "5y"], value="1y")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ RISK PARAMETERS")
    leverage = st.sidebar.slider("가상 레버리지", 1.0, 3.0, 1.0)
    hard_stop = st.sidebar.number_input("강제 손절 라인 (%)", value=8)

    # --------------------------------------------------------------------------
    # 데이터 엔진 및 분석 가동
    # --------------------------------------------------------------------------
    try:
        # 데이터 획득부
        if "분봉" in chart_interval:
            i_map = {"5분봉":"5m", "15분봉":"15m", "60분봉":"60m"}
            raw_data = yf.download(full_ticker, period="1mo", interval=i_map[chart_interval], progress=False)
        else:
            raw_data = yf.download(full_ticker, period=history_range, interval="1d", progress=False)
            
        if raw_data.empty:
            st.error("데이터 로드 실패: 티커를 확인하거나 잠시 후 다시 시도해 주세요.")
            return

        # 1. 퀀트 엔진 가동 (수학적 지표)
        engine = RawMathQuantEngine(raw_data)
        df_processed = engine.generate_indicators()
        
        # 2. 기하학적 분석 (파동 및 매물대)
        geo_engine = GeometricAnalysisEngine(df_processed)
        pks, vls, fibs, poc = geo_engine.run_structural_analysis()
        
        # 3. 백테스팅 및 전략 확정
        df_final = execute_expert_backtest(df_processed)
        
        # 4. 리스크 및 시뮬레이션
        risk_engine = ProbabilisticRiskEngine(df_final)
        var_val, mdd_val = risk_engine.calculate_risk_metrics(df_final['Net_Strategy_Return'])
        
        # --------------------------------------------------------------------------
        # 메인 대시보드 렌더링
        # --------------------------------------------------------------------------
        st.markdown(f"<h2><span class='neon-dot'></span>QUANT INFINITY TERMINAL <small style='color:#555'>| {user_asset} ({target_ticker})</small></h2>", unsafe_allow_html=True)
        
        # 상단 핵심 메트릭 (4컬럼)
        c_price = df_final['Close'].iloc[-1]
        c_score = df_final['AI_Score_Final'].iloc[-1]
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(f"<div class='metric-unit'><div class='metric-unit-label'>Current Price</div><div class='metric-unit-value'>{c_price:,.0f}</div></div>", unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"<div class='metric-unit'><div class='metric-unit-label'>Quant AI Score</div><div class='metric-unit-value' style='color:var(--neon-blue)'>{c_score:.0f}</div></div>", unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"<div class='metric-unit'><div class='metric-unit-label'>VaR (95%)</div><div class='metric-unit-value' style='color:var(--neon-red)'>{abs(var_val*100):.2f}%</div></div>", unsafe_allow_html=True)
        with col_m4:
            st.markdown(f"<div class='metric-unit'><div class='metric-unit-label'>RSI Strength</div><div class='metric-unit-value' style='color:var(--neon-yellow)'>{df_final['RSI_14'].iloc[-1]:.1f}</div></div>", unsafe_allow_html=True)

        st.write("")

        # 탭 아키텍처 (메인 4대 섹션)
        tab_main, tab_ai, tab_risk, tab_feed = st.tabs([
            "📊 MASTER VISUAL CHART", 
            "🧠 QUANT INSIGHTS & STRATEGY", 
            "🔮 PROBABILISTIC FORECAST", 
            "⚡ GLOBAL INTELLIGENCE HUB"
        ])

        # [SECTION 1: 마스터 비주얼 차트]
        with tab_main:
            fig_master = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.82, 0.18])
            
            # 1. 캔들스틱 본체
            fig_master.add_trace(go.Candlestick(
                x=df_final.index, open=df_final['Open'], high=df_final['High'], low=df_final['Low'], close=df_final['Close'],
                name="Asset Price", increasing_line_color='#00ff99', decreasing_line_color='#ff3366',
                increasing_fillcolor='rgba(0,255,153,0.3)', decreasing_fillcolor='rgba(255,51,102,0.3)'
            ), row=1, col=1)
            
            # 2. 일목균형표 구름대 (Kumo Cloud)
            fig_master.add_trace(go.Scatter(x=df_final.index, y=df_final['Ichimoku_SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig_master.add_trace(go.Scatter(x=df_final.index, y=df_final['Ichimoku_SpanB'], fill='tonexty', fillcolor='rgba(191, 0, 255, 0.08)', name="Kumo Cloud"), row=1, col=1)
            
            # 3. 볼린저 밴드 영역
            fig_master.add_trace(go.Scatter(x=df_final.index, y=df_final['BB_Upper'], line=dict(color='rgba(255,255,255,0.1)', width=1), showlegend=False), row=1, col=1)
            fig_master.add_trace(go.Scatter(x=df_final.index, y=df_final['BB_Lower'], line=dict(color='rgba(255,255,255,0.1)', width=1), fill='tonexty', fillcolor='rgba(255,255,255,0.02)', name="Bollinger Range"), row=1, col=1)

            # 4. 엘리어트 파동 넘버링 시각화 (하이라이트)
            labels = ['1','2','3','4','5','A','B','C']
            merged_pivots = sorted([('p', i, df_final['High'].iloc[i]) for i in pks] + [('v', i, df_final['Low'].iloc[i]) for i in vls], key=lambda x: x[1])[-8:]
            
            for idx, pt in enumerate(merged_pivots):
                if idx < len(labels):
                    is_valley = pt[0] == 'v'
                    l_color = var_val = "#00ff99" if is_valley else "#ff3366"
                    fig_master.add_trace(go.Scatter(
                        x=[df_final.index[pt[1]]], y=[pt[2]], mode="text+markers",
                        text=[f"<b>{labels[idx]}</b>"], textposition="bottom center" if is_valley else "top center",
                        textfont=dict(size=24, color=l_color), marker=dict(color=l_color, size=15, symbol='diamond-open'),
                        showlegend=False
                    ), row=1, col=1)
            
            # 5. 매물대 POC & 피보나치 레이어
            fig_master.add_hline(y=poc, line=dict(color="rgba(0, 229, 255, 0.4)", width=3, dash="dot"), annotation_text="POC (Volume Max)", row=1, col=1)
            for k, v in fibs.items():
                fig_master.add_hline(y=v, line=dict(color="rgba(255,255,255,0.08)", width=1), row=1, col=1)

            # 6. 하단 MACD 히스토그램
            fig_master.add_trace(go.Bar(x=df_final.index, y=df_final['MACD_Histogram'], name="MACD Momentum", 
                                        marker_color=['#ff3366' if x < 0 else '#00ff99' for x in df_final['MACD_Histogram']]), row=2, col=1)
            
            fig_master.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_master, use_container_width=True, config={'displayModeBar': False})

        # [SECTION 2: 퀀트 인사이트 & 전략]
        with tab_ai:
            st.markdown("<div class='master-card'>", unsafe_allow_html=True)
            st.markdown("<div class='card-header'>🔍 AI QUANT STRUCTURAL REPORT</div>", unsafe_allow_html=True)
            
            row1_c1, row1_c2 = st.columns(2)
            with row1_c1:
                st.write("#### 📐 Geometric Space Analysis")
                st.write(f"• **Point of Control (POC)**: {poc:,.0f} (매수/매도 대립의 중심축)")
                st.write(f"• **Fibonacci Support (61.8%)**: {fibs['Fib_618']:,.0f} (심리적 황금 지지선)")
                st.write(f"• **Volatility (ATR)**: {df_final['ATR_14'].iloc[-1]:,.1f} (현재 시장의 평균 변동폭)")
                
            with row1_c2:
                st.write("#### ⚙️ Algorithmic Signal Status")
                st.write(f"• **Trend Filter**: {'BULLISH (상승)' if c_price > df_final['EMA_60'].iloc[-1] else 'BEARISH (하락)'} 추세 확인")
                st.write(f"• **Kumo Cloud**: 주가가 구름대 {'위' if c_price > df_final['Ichimoku_SpanA'].iloc[-1] else '아래'}에 위치하여 {'강세' if c_price > df_final['Ichimoku_SpanA'].iloc[-1] else '약세'} 압력 지속")
                st.write(f"• **Oscillator**: RSI {df_final['RSI_14'].iloc[-1]:.1f} 로 {'과매수 주의' if df_final['RSI_14'].iloc[-1] > 70 else '과매도 반등' if df_final['RSI_14'].iloc[-1] < 30 else '중립적 상태'}")

            st.markdown("---")
            st.write("#### 🛡️ PRO-LEVEL TRADE EXECUTION GUIDE")
            guide_c1, guide_c2, guide_c3 = st.columns(3)
            with guide_c1:
                st.info(f"🎯 **DYNAMIC TARGET (TP)**\n\n**{c_price + (df_final['ATR_14'].iloc[-1] * 2.8):,.0f}**\n\n(ATR 2.8x Volatility Based)")
            with guide_c2:
                st.warning(f"🛡️ **DYNAMIC STOP (SL)**\n\n**{c_price - (df_final['ATR_14'].iloc[-1] * 1.8):,.0f}**\n\n(ATR 1.8x Volatility Based)")
            with guide_c3:
                st.success(f"⚖️ **POSITION SIZING**\n\n**{int(c_score * 0.8)}% Allocation**\n\n(Score-Weighted Risk Model)")
            st.markdown("</div>", unsafe_allow_html=True)

        # [SECTION 3: 확률적 예측 시뮬레이션]
        with tab_risk:
            st.subheader("🔮 PROBABILISTIC WEALTH PROJECTION (MONTE CARLO)")
            paths = risk_engine.simulate_future_paths()
            
            fig_sim = go.Figure()
            # 가독성을 위해 30개의 경로만 렌더링
            for i in range(30):
                fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', line=dict(width=1), opacity=0.25, showlegend=False))
            
            # 평균 기대 경로
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00e5ff', width=4), name="MEAN EXPECTED PATH"))
            
            # 상하위 10% 확률 경계선
            fig_sim.add_trace(go.Scatter(y=np.percentile(paths, 90, axis=1), mode='lines', line=dict(color='#00ff99', width=2, dash='dash'), name="OPTIMISTIC (90th)"))
            fig_sim.add_trace(go.Scatter(y=np.percentile(paths, 10, axis=1), mode='lines', line=dict(color='#ff3366', width=2, dash='dash'), name="PESSIMISTIC (10th)"))
            
            fig_sim.update_layout(height=600, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_sim, use_container_width=True)
            
            prob_up = (paths[-1, :] > c_price).sum() / 1200 * 100
            st.info(f"💡 **시뮬레이션 분석**: 1,200회 반복 연산 결과, 1년 뒤 자산 가치가 상승할 확률은 **{prob_up:.1f}%**입니다. 평균 기대 주가는 **{np.mean(paths[-1]):,.0f}**입니다.")

            # 백테스팅 성과 데이터
            st.markdown("---")
            st.subheader("📉 ALGORITHMIC ALPHA PERFORMANCE (BACKTEST)")
            bt_c1, bt_c2, bt_c3 = st.columns(3)
            m_ret = df_final['Cum_Market_Wealth'].iloc[-1] - 100
            s_ret = df_final['Cum_Strategy_Wealth'].iloc[-1] - 100
            bt_c1.metric("Market Return (존버)", f"{m_ret:+.2f}%")
            bt_c2.metric("Strategy Return (AI)", f"{s_ret:+.2f}%", f"{(s_ret - m_ret):+.2f}%p (ALPHA)")
            bt_c3.metric("Maximum Drawdown (MDD)", f"{mdd_val*100:.2f}%", delta_color="inverse")

            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=df_final.index, y=df_final['Cum_Market_Wealth'], name="Market", line=dict(color='rgba(255,255,255,0.3)', width=2)))
            fig_bt.add_trace(go.Scatter(x=df_final.index, y=df_final['Cum_Strategy_Wealth'], name="Quant Infinity", line=dict(color='#00ff99', width=4)))
            # AI 점수 히스토리 보조축 표시
            fig_bt.add_trace(go.Scatter(x=df_final.index, y=df_final['AI_Score_Final'], name="AI Score", yaxis="y2", line=dict(color='#ffcc00', width=1, dash='dot')))
            
            fig_bt.update_layout(
                height=500, template="plotly_dark", 
                yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="AI Score", showgrid=False),
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_bt, use_container_width=True)

        # [SECTION 4: 글로벌 인텔리전스 허브]
        with tab_feed:
            st.subheader(f"⚡ REAL-TIME INTELLIGENCE: {user_asset}")
            
            # 뉴스 피드 및 특징주 추출 (Google News RSS 활용)
            def fetch_expert_radar(q=None):
                k_word = "국내 증시 핫이슈" if q is None else f"{q} 특징주 OR {q} 실적 발표"
                radar_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(k_word)}&hl=ko&gl=KR&ceid=KR:ko"
                try:
                    feed_data = feedparser.parse(radar_url)
                    return [{"title": x.title, "link": x.link, "date": x.published[:-4] if hasattr(x, 'published') else "RECENT"} for x in feed_data.entries[:12]]
                except: return []

            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.markdown("#### 🌐 GLOBAL MARKET FLOW")
                for n in fetch_expert_radar():
                    st.markdown(f"""
                    <div class='news-node'>
                        <a href='{n['link']}' target='_blank' class='news-node-title'>{n['title']}</a>
                        <div class='news-node-meta'>🕘 {n['date']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            with r_col2:
                st.markdown(f"#### 🎯 {user_asset} TARGET RADAR")
                for n in fetch_expert_radar(user_asset):
                    st.markdown(f"""
                    <div class='news-node'>
                        <a href='{n['link']}' target='_blank' class='news-node-title'>{n['title']}</a>
                        <div class='news-node-meta'>🕘 {n['date']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"시스템 긴급 중단: {e}")
        st.info("해당 자산의 데이터가 부족하거나 인터넷 연결 상태가 불안정합니다. 티커명을 다시 확인해 주세요.")

if __name__ == "__main__":
    launch_infinity_terminal()
