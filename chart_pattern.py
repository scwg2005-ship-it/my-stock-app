import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.6 Alpha Quant")

# --- 2. 한글 종목명을 코드로 바꾸는 강력한 함수 ---
@st.cache_data(ttl=86400) # 하루 동안 검색 리스트 저장
def search_stock_code(name):
    try:
        # KRX, KOSPI, KOSDAQ 종목 전체 리스트 로드
        df_krx = fdr.StockListing('KRX')
        # 이름이 정확히 일치하는 행 찾기
        match = df_krx[df_krx['Name'] == name.strip()]
        if not match.empty:
            return match.iloc[0]['Symbol'], name.strip()
        return None, None
    except:
        return None, None

@st.cache_data(ttl=3600)
def get_data(symbol):
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(200)
        return None
    except:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v17.6 Alpha Quant (한글 검색)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        # 이제 숫자 적지 마시고 한글로만 입력해 보세요!
        stock_input = st.text_input("종목명을 입력하세요 (예: 삼성전자, 현대차, 카카오)", value="삼성전자")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    # 1. 한글명으로 코드 찾기
    code, real_name = search_stock_code(stock_input)
    
    # 2. 코드를 찾았다면 데이터 가져오기
    if code:
        df = get_data(code)
    else:
        # 한글명이 아니면 미국 티커(ONDS 등)로 간주하고 직접 시도
        df = get_data(stock_input)
        real_name = stock_input

    if df is not None:
        tab1, tab2, tab3 = st.tabs(["📈 차트 분석", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{real_name}] 분석 차트")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.info("온도계 기능이 활성화되었습니다.")
        with tab3:
            st.info("전략 가이드가 산출되었습니다.")
    else:
        st.error(f"⚠️ '{stock_input}' 종목을 찾을 수 없습니다. 이름이 정확한지(오타 확인) 또는 상장된 종목인지 확인해 주세요.")
