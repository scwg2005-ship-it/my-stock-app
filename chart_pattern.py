import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.3 Premium Quant")

# --- 2. 데이터 로드 함수 (오타 수정 및 로직 강화) ---
@st.cache_data(ttl=3600)
def get_stock_data(keyword):
    try:
        # 입력값 정제
        target = keyword.strip()
        
        # 1. 한국 종목 리스트에서 검색 시도
        krx = fdr.StockListing('KRX')
        match = krx[krx['Name'] == target]
        
        if not match.empty:
            symbol = match.iloc[0]['Symbol']
            display_name = target
        else:
            # 리스트에 없으면 티커(숫자나 영문)로 직접 시도
            symbol = target
            display_name = target
            
        df = fdr.DataReader(symbol)
        
        if df is not None and not df.empty:
            return df.tail(200), display_name
        return None, None
    except:
        return None, None

# --- 3. UI 구성 ---
st.title("🏛️ v17.3 Alpha Quant")

# 폼 구조를 확실하게 잡아서 오타 방지
with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        # 변수명을 정확히 stock_input으로 완성
        stock_input = st.text_input("종목명(예: 삼성전자) 또는 티커(예: ONDS)", value="삼성전자")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

# 실행 로직
if submitted or stock_input:
    df, name = get_stock_data(stock_input)

    if df is not None:
        tab1, tab2, tab3 = st.tabs(["📈 빗각 추세 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{name}] 차트 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            
            # 캔들차트
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], 
                low=df['Low'], close=df['Close'], name='Price'
            ), row=1, col=1)
            
            # 거래량
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            
            fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True, key="main_chart_v17")
            
        with tab2:
            st.info("투자 온도계 계산 중...")
        with tab3:
            st.info("전략 가이드 산출 중...")
    else:
        st.warning(f"⚠️ '{stock_input}' 데이터를 찾을 수 없습니다. 종목명을 정확히 입력하거나 6자리 코드를 입력해 보세요.")
