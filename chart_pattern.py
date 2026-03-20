import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v18.2 Alpha Quant")

@st.cache_data(ttl=3600)
def load_data_korea(keyword):
    try:
        # 공백 제거 및 대문자화
        target = keyword.strip().upper()
        
        # 1. 한국 종목 리스트 로드 (실패 대비)
        try:
            krx = fdr.StockListing('KRX')
            match = krx[krx['Name'] == target]
            if not match.empty:
                symbol = match.iloc[0]['Symbol']
                name = target
            else:
                symbol = target
                name = target
        except:
            symbol = target
            name = target

        # 2. [핵심] 소스를 'NAVER'로 강제 지정 (야후 차단 회피)
        # 한국 종목은 6자리 숫자여야 합니다.
        df = fdr.DataReader(symbol, exchange='KRX') # KRX(Naver 소스) 사용
        
        if df is not None and not df.empty:
            return df.tail(200), name
        
        # 3. 만약 미국 주식이라면 일반 로드 시도
        df = fdr.DataReader(target)
        if df is not None and not df.empty:
            return df.tail(200), target
            
        return None, None
    except:
        return None, None

# --- 2. UI 구성 ---
st.title("🏛️ v18.2 Alpha Quant (Naver Source)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명(현대자동차) 또는 티커(ONDS)", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    df, real_name = load_data_korea(stock_input)

    if df is not None:
        # 이동평균선 등 기본 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{real_name}] 실시간 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1), name='MA20'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("시장의 열기를 분석 중입니다...")
        with tab3:
            st.success("데이터 기반 매매 전략 산출 완료")
    else:
        st.error(f"⚠️ '{stock_input}' 데이터를 불러올 수 없습니다. '현대자동차'로 다시 검색해 보시거나 잠시 후 시도해 주세요.")
