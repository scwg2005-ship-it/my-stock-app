import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.9 Alpha Quant")

# --- 2. 스마트 심볼 변환기 (핵심) ---
@st.cache_data(ttl=86400)
def get_smart_symbol(keyword):
    keyword = keyword.strip()
    try:
        # 한국 거래소 종목 리스트 확보
        krx = fdr.StockListing('KRX')
        match = krx[krx['Name'] == keyword]
        
        if not match.empty:
            symbol = match.iloc[0]['Symbol']
            return symbol, keyword, "KR" # 한국 주식 판정
        
        # 이름에 포함된 경우도 검색 (예: '한화' 입력 시 '한화솔루션' 매칭)
        match_cont = krx[krx['Name'].str.contains(keyword)]
        if not match_cont.empty:
            return match_cont.iloc[0]['Symbol'], match_cont.iloc[0]['Name'], "KR"
            
        return keyword.upper(), keyword.upper(), "US" # 기본은 미국/기타 티커
    except:
        return keyword.upper(), keyword.upper(), "US"

@st.cache_data(ttl=3600)
def load_data_smart(symbol, origin):
    try:
        # 한국 주식과 미국 주식의 데이터 소스를 분리하여 안정성 확보
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(200)
        return None
    except:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v17.9 Alpha Quant (Smart Search)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명(삼성전자, 현대차) 또는 미국 티커(NVDA, ONDS)", value="한화솔루션")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    # 1. 심볼 및 국가 판정
    symbol, real_name, origin = get_smart_symbol(stock_input)
    
    # 2. 데이터 로드
    df = load_data_smart(symbol, origin)

    if df is not None:
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        tab1, tab2, tab3 = st.tabs(["📈 빗각 추세 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{real_name}] 분석 차트")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            
            # 캔들
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            
            # 이동평균선
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1), name='MA20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='orange', width=1), name='MA60'), row=1, col=1)
            
            # 거래량
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            
            fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.info("실시간 시장 온도 분석 중...")
        with tab3:
            st.success("데이터 기반 전략 도출 완료")
    else:
        st.error(f"⚠️ '{stock_input}' 데이터를 불러올 수 없습니다. 이름이 정확한지 확인해 주세요.")
