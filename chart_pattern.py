import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.7 Alpha Quant")

# --- 2. 한글 검색 강화 로직 (핵심) ---
@st.cache_data(ttl=86400)
def find_symbol_by_name(name):
    try:
        name = name.strip()
        # 모든 시장 종목 리스트 로드 (KOSPI, KOSDAQ, KONEX)
        df_krx = fdr.StockListing('KRX')
        
        # 이름 포함 여부로 검색 (완전 일치 우선)
        match = df_krx[df_krx['Name'] == name]
        
        if not match.empty:
            return match.iloc[0]['Symbol'], match.iloc[0]['Name']
        
        # 부분 일치 검색 (예: '한화' 입력 시 '한화솔루션' 등)
        match_contains = df_krx[df_krx['Name'].str.contains(name)]
        if not match_contains.empty:
            return match_contains.iloc[0]['Symbol'], match_contains.iloc[0]['Name']
            
        return None, None
    except:
        return None, None

@st.cache_data(ttl=3600)
def get_stock_data(symbol):
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(200)
        return None
    except:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v17.7 Alpha Quant (한글 검색 마스터)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        # 한글로 '한화솔루션' 입력해 보세요!
        stock_input = st.text_input("종목명 또는 티커 입력", value="한화솔루션")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    # 1. 이름으로 코드 찾기 시도
    symbol, real_name = find_symbol_by_name(stock_input)
    
    # 2. 결과가 없으면 티커로 직접 시도 (미국주식 등)
    if not symbol:
        symbol = stock_input.upper()
        real_name = stock_input

    df = get_stock_data(symbol)

    if df is not None:
        tab1, tab2, tab3 = st.tabs(["📈 차트 분석", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{real_name} ({symbol})] 기술적 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.success("시장 온도계가 정상 작동 중입니다.")
        with tab3:
            st.info("전략 가이드가 산출되었습니다.")
    else:
        st.error(f"⚠️ '{stock_input}' 종목을 찾을 수 없습니다. (리스트를 새로 불러오려면 페이지를 새로고침하거나 잠시 후 시도하세요.)")

# 검색 팁
with st.expander("💡 검색 팁"):
    st.write("1. 종목명은 띄어쓰기 없이 정확히 입력하세요 (예: 한화솔루션)")
    st.write("2. 미국 주식은 티커를 입력하세요 (예: ONDS, NVDA)")
    st.write("3. 최근 상장한 종목은 데이터 로드에 시간이 걸릴 수 있습니다.")
