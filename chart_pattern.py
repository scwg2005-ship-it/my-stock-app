import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.2 Premium Quant")

# --- 2. 종목 리스트 캐싱 (매번 로드하면 느려지므로 1일 1회 로드) ---
@st.cache_data(ttl=86400)
def get_krx_list():
    return fdr.StockListing('KRX')[['Symbol', 'Name']]

@st.cache_data(ttl=1800)
def get_stock_data(keyword):
    try:
        krx = get_krx_list()
        # 입력값의 앞뒤 공백 제거 및 대문자 변환
        clean_keyword = keyword.strip()
        
        # 1. 이름에서 찾기 (정확히 일치)
        target = krx[krx['Name'] == clean_keyword]
        
        # 2. 이름에서 못 찾으면 코드로 찾기
        if target.empty:
            target = krx[krx['Symbol'] == clean_keyword]
            
        if not target.empty:
            symbol = target.iloc[0]['Symbol']
            real_name = target.iloc[0]['Name']
            df = fdr.DataReader(symbol)
            if df is not None and not df.empty:
                return df.tail(200), real_name
        
        # 3. 미국 주식 등 기타 티커 직접 시도
        df = fdr.DataReader(clean_keyword)
        if df is not None and not df.empty:
            return df.tail(200), clean_keyword
            
        return None, None
    except:
        return None, None

# --- 3. UI 구성 ---
st.title("🏛️ v17.2 Alpha Quant")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        # 도움말 추가
        stock_input = st.text_input("종목명(예: 삼성전자, SK하이닉스) 또는 티커(ONDS, TSLA)", value="삼성전자")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    df, name = get_stock_data(stock_input)

    if df is not None:
        tab1, tab2, tab3 = st.tabs(["📈 빗각 추세 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{name}] 차트 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.write("시장 온도계 준비 중...")
        with tab3:
            st.write("전략 가이드 준비 중...")
    else:
        st.warning(f"⚠️ '{stock_input}'에 대한 데이터를 찾을 수 없습니다. 종목명을 정확히 입력했는지 확인해 주세요. (예: 삼성전자)")
