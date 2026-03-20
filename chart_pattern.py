import streamlit as st
import matplotlib
import matplotlib.pyplot as plt

# [중요] 서버 환경에서 GUI 충돌 방지를 위한 설정 (반드시 최상단 배치)
matplotlib.use('Agg')
plt.switch_backend('Agg')

import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import trendln
from sklearn.cluster import KMeans
import feedparser

# --- 1. 전역 설정 ---
st.set_page_config(layout="wide", page_title="v16.2 Alpha Quant")

# --- 2. 보조 함수들 ---
def get_stock_code(name):
    if 'krx_list' not in st.session_state:
        st.session_state['krx_list'] = fdr.StockListing('KRX')
    if 'nasdaq_list' not in st.session_state:
        st.session_state['nasdaq_list'] = fdr.StockListing('NASDAQ')
    
    name_upper = name.upper()
    target_kr = st.session_state['krx_list'][st.session_state['krx_list']['Name'] == name]
    if not target_kr.empty: return target_kr.iloc[0]['Code']
    
    target_us = st.session_state['nasdaq_list'][st.session_state['nasdaq_list']['Symbol'] == name_upper]
    if not target_us.empty: return target_us.iloc[0]['Symbol']
    
    return name_upper

def get_news(keyword):
    is_us = keyword.replace(".","").isupper()
    url = f"https://news.google.com/rss/search?q={keyword}+stock&hl={'en-US' if is_us else 'ko'}&gl={'US' if is_us else 'KR'}&ceid={'US:en' if is_us else 'KR:ko'}"
    feed = feedparser.parse(url)
    return [{'title': e.title, 'link': e.link, 'sentiment': "😐 중립"} for e in feed.entries[:3]]

# --- 3. 핵심 분석 (에러 방어 로직 강화) ---
@st.cache_data(ttl=300)
def analyze(symbol):
    try:
        df = fdr.DataReader(symbol).tail(200)
        if df.empty: return None
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'] = df['MA20'] + (std * 2)
        df['BB_L'] = df['MA20'] - (std * 2)
        
        # trendln 추세선 계산 (오류 발생 시 패스하도록 설계)
        top, bot = None, None
        try:
            h_lines = trendln.get_lines(df['High'].values, extmethod=trendln.METHOD_NAIVE)
            l_lines = trendln.get_lines(df['Low'].values, extmethod=trendln.METHOD_NAIVE)
            if h_lines: top = h_lines[0]
            if l_lines: bot = l_lines[0]
        except Exception as e:
            st.warning(f"추세선 계산 중 경미한 오류 발생 (무시 가능): {e}")
            
        return df, top, bot
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# --- 4. 메인 대시보드 그리기 ---
st.sidebar.title("⚙️ Alpha Quant")
stock = st.sidebar.text_input("종목명/티커", "ONDS")
if st.sidebar.button("새로고침"): st.rerun()

code = get_stock_code(stock)
data = analyze(code)

if data:
    df, top, bot = data
    st.title(f"🏛️ v16.2 Alpha Quant System")
    st.subheader(f"📊 {stock} ({code})")

    # 상단 요약 지표
    c1, c2, c3 = st.columns(3)
    curr = df['Close'].iloc[-1]
    c1.metric("현재가", f"{curr:,.2f}")
    c2.metric("전일비", f"{(curr - df['Close'].iloc[-2]):+.2f}")
    c3.info(f"뉴스 리서치 중... (실시간)")

    # 뉴스 및 차트 레이아웃
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.markdown("### 📰 실시간 주요 뉴스")
        news_items = get_news(stock)
        for n in news_items:
            st.markdown(f"• [{n['title'][:40]}...]({n['link']})")

    with col_right:
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'))
        
        # 추세선 시각화 (존재할 때만)
        if top:
            fig.add_trace(go.Scatter(x=[df.index[top[0][0]], df.index[top[0][-1]]], y=[top[2][0], top[2][-1]], mode='lines', line=dict(color='red', dash='dot'), name='Resistance'))
        if bot:
            fig.add_trace(go.Scatter(x=[df.index[bot[0][0]], df.index[bot[0][-1]]], y=[bot[2][0], bot[2][-1]], mode='lines', line=dict(color='blue', dash='dot'), name='Support'))

        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("데이터를 불러오는 중입니다. 티커가 정확한지 확인해 주세요.")
