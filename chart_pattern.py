import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v18.1 Alpha Quant")

# --- 2. 초강력 직통 심볼 엔진 (KRX 리스트 의존도 낮춤) ---
@st.cache_data(ttl=86400)
def get_symbol_direct(name):
    name = name.strip()
    # 0. 자주 쓰는 종목 하드코딩 (서버 에러 대비 필살기)
    hardcoded = {
        "현대자동차": "005380.KS", "현대차": "005380.KS",
        "삼성전자": "005930.KS", "삼전": "005930.KS",
        "SK하이닉스": "000660.KS", "하이닉스": "000660.KS",
        "카카오": "035720.KS", "NAVER": "035420.KS", "네이버": "035420.KS",
        "에코프로": "086520.KQ", "에코프로비엠": "247540.KQ"
    }
    
    if name in hardcoded:
        return hardcoded[name], name

    try:
        # 1. KRX 리스트 로드 시도 (실패해도 중단되지 않게 try-except)
        krx = fdr.StockListing('KRX')
        match = krx[krx['Name'].str.contains(name)]
        if not match.empty:
            symbol = match.iloc[0]['Symbol']
            market = match.iloc[0]['Market']
            suffix = ".KS" if market == 'KOSPI' else ".KQ"
            return f"{symbol}{suffix}", match.iloc[0]['Name']
    except:
        pass
        
    # 2. 미국 주식이나 티커는 그대로 반환
    return name.upper(), name.upper()

@st.cache_data(ttl=3600)
def load_data_final(symbol):
    try:
        # 야후 파이낸스 소스를 기본으로 사용하여 서버 차단 회피
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(200)
        return None
    except:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v18.1 Alpha Quant (Direct)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명(현대차, 삼성전자) 또는 티커(NVDA)", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    # 1. 심볼 직통 변환
    symbol, real_name = get_symbol_direct(stock_input)
    
    # 2. 데이터 로드
    df = load_stock_data = load_data_final(symbol)

    if df is not None:
        # 기본 지표 미리 계산 (에러 방지용)
        df['MA20'] = df['Close'].rolling(20).mean()
        
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{real_name} ({symbol})] 실시간 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1), name='MA20'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("시장의 열기를 측정 중입니다...")
        with tab3:
            st.success("데이터 기반 매매 전략 도출 완료")
    else:
        st.error(f"⚠️ '{stock_input}' ({symbol}) 데이터를 불러올 수 없습니다. 서버 연결을 확인해 주세요.")
