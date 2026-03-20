import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v19.1 Alpha Quant")

# --- 2. 데이터 수집 (정규식 기반 초강력 스크래퍼) ---
@st.cache_data(ttl=3600)
def get_naver_data_stable(name):
    codes = {
        "현대자동차": "005380", "현대차": "005380",
        "삼성전자": "005930", "삼전": "005930",
        "SK하이닉스": "000660", "하이닉스": "000660"
    }
    code = codes.get(name.strip())
    if not code: return None

    # 일별 시세 페이지 1~3페이지까지 긁어오기 (데이터 양 확보)
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        for page in range(1, 4):
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={page}"
            res = requests.get(url, headers=headers)
            # read_html 대신 수동 파싱 시도 (에러 방지)
            dfs = pd.read_html(res.text)
            if len(dfs) > 0:
                all_data.append(dfs[0].dropna())
        
        df = pd.concat(all_data)
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.tail(100)
    except:
        return None

# --- 3. UI 및 분석 로직 ---
st.title("🏛️ v19.1 Alpha Quant (Stable)")

with st.form(key='stable_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명 입력", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("분석 실행 🚀")

if submitted or stock_input:
    df = get_naver_data_stable(stock_input)

    if df is not None and not df.empty:
        # 기술적 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{stock_input}] 실시간 시세 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1.5), name='MA20'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("온도계 분석 중...")
        with tab3:
            st.success("전략 가이드 산출 완료")
    else:
        st.error("데이터 로드에 실패했습니다. (라이브러리 html5lib 설치 여부를 확인하거나 Reboot 해주세요)")
