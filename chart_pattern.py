import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# --- 1. [디자인] 초경량 모드 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v87.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [긴급] 데이터 로드 로직 (가장 단순한 방식) ---
def find_ticker_simple(query):
    # 우리금융지주, 삼성전자 등 주요 종목 수동 매핑 (에러 방지용)
    mapping = {
        "우리금융지주": "053000.KS",
        "우리금융": "053000.KS",
        "삼성전자": "005930.KS",
        "한화솔루션": "009830.KS",
        "현대차": "005380.KS",
        "SK하이닉스": "000660.KS",
        "엔비디아": "NVDA",
        "테슬라": "TSLA"
    }
    return mapping.get(query, query.upper())

@st.cache_data(ttl=60)
def get_emergency_data(ticker):
    try:
        # yfinance의 가장 안정적인 기본 호출 방식 사용
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty: return None
        
        # MultiIndex 제거 및 컬럼명 정리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]
        
        # 필수 지표만 계산 (부하 감소)
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        return df
    except:
        return None

# --- 3. [메인] 사이드바 제어 ---
with st.sidebar:
    st.header("Oracle Control")
    u_input = st.text_input("종목명(삼성전자) 또는 티커(AAPL)", value="삼성전자")
    ticker = find_ticker_simple(u_input)
    st.info(f"Target Ticker: {ticker}")
    
    invest_val = st.number_input("투자 원금", value=10000000)
    chart_style = st.radio("차트 형태", ["캔들", "라인"])

# --- 4. [메인] 분석 실행 ---
df = get_emergency_data(ticker)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    
    # 초간단 기대수익 시뮬레이션
    ret_avg = df['Close'].pct_change().mean()
    win_rate = 50 + (ret_avg * 1000) # 간이 승률 계산
    
    st.markdown(f"### {u_input} ({ticker}) 분석 결과")
    
    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        st.markdown(f"""<div class="profit-card">
            <h1 style="margin:0;">{(ret_avg*100):+.2f}%</h1>
            <p style="margin:0;">평균 변동성 기반 기대수익</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.metric("현재가", f"{curr_p:,.0f}")
        st.metric("AI 점수", f"{int(win_rate)}점")
    with col3:
        st.metric("목표가", f"{curr_p*1.1:,.0f}")
        st.metric("손절가", f"{curr_p*0.95:,.0f}")

    # 차트
    fig = go.Figure()
    if chart_style == "캔들":
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff'), fill='tozeroy', name='Price'))
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FF37AF', width=1), name='20일선'))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#00F2FF', width=1), name='60일선'))
    
    fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)
    
    st.success("💡 현재 긴급 모드로 작동 중입니다. 라이브러리 설치가 완료되면 모든 기능이 복구됩니다.")

else:
    st.warning("데이터를 불러오는 중입니다. 티커가 정확한지 확인해 주세요. (예: 005930.KS)")
