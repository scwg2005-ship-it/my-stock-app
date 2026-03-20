import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse

# ==========================================
# 1. UI/UX 전면 개편 & 모바일 최적화
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; padding-top: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px;}
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 검색 엔진 (단어장 매핑 방식)
# ==========================================
TICKER_MAP = {
    "삼성전자": "005930.KS",
    "카카오": "035720.KS",
    "테슬라": "TSLA",
    "애플": "AAPL",
    "엔비디아": "NVDA",
    "ONDS": "ONDS",
    "쓰리빌리언": "394990.KQ"
}

@st.cache_data(ttl=3600, show_spinner=False)
def get_ticker_from_name(query):
    query = query.strip()
    # 단어장에 있는 한글 이름이면 코드로 바로 변환
    if query in TICKER_MAP:
        return TICKER_MAP[query]
    if ".KS" in query.upper() or ".KQ" in query.upper(): 
        return query.upper()
    return query.upper()

# ==========================================
# 3. 사이드바: 설정 및 퀵뷰
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

st.sidebar.subheader("⭐ 관심 종목 퀵뷰")
quick_tickers = ["직접 입력...", "삼성전자", "테슬라", "애플", "엔비디아", "ONDS", "쓰리빌리언"]
selected_quick = st.sidebar.selectbox("빠른 선택", quick_tickers)

default_input = "삼성전자" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명 검색 (예: 테슬라, 카카오)", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 자동 검색된 코드: **{ticker}**")

period = st.sidebar.select_slider("조회 기간", options=["1mo", "3mo", "6mo", "1y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 시뮬레이터")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 데이터 수집 및 퀀트 연산 (오류 방어 완벽 적용)
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def load_and_calc_data(symbol, p):
    try:
        # 1. 차트 주가 데이터 수집 (야후가 잘 허락해 줌)
        df = yf.download(symbol, period=p, interval="1d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 20: return None, None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        df['Stoch_K'] = 100 * ((df['Close'] - df['Low'].rolling(14).min()) / (df['
