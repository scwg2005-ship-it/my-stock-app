import streamlit as st
import matplotlib
matplotlib.use('Agg') # 핵심: 서버 충돌 방지 설정
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import trendln
from sklearn.cluster import KMeans
import feedparser

# --- 전역 설정 ---
st.set_page_config(layout="wide", page_title="v16.1 Alpha Quant")

# --- 종목 코드 변환 ---
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

# --- 뉴스 크롤링 ---
def get_news(keyword):
    is_us = keyword.replace(".","").isupper()
    url = f"https://news.google.com/rss/search?q={keyword}+stock&hl={'en-US' if is_us else 'ko'}&gl={'US' if is_us else 'KR'}&ceid={'US:en' if is_us else 'KR:ko'}"
    feed = feedparser.parse(url)
    return [{'title': e.title, 'link': e.link, 'date': e.published} for e in feed.entries[:3]]

# --- 데이터 분석 ---
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
        
        # 추세선 계산 (오류 방지를 위해 try-except)
        try:
            h_lines = trendln.get_lines(df['High'].values, extmethod=trendln.METHOD_NAIVE)
            l_lines = trendln.get_lines(df['Low'].values, extmethod=trendln.METHOD_NAIVE)
            top, bot = (h_lines[0] if h_lines else None), (l_lines[0] if l_lines else None)
        except:
            top, bot = None, None
            
        return df, top, bot
    except:
        return None

# --- UI 그리기 ---
st.sidebar.title("⚙️ 제어판")
stock = st.sidebar.text_input("종목명/티커", "ONDS")
if st.sidebar.button("새로고침"): st.rerun()

code = get_stock_code(stock)
data = analyze(code)

if data:
    df, top, bot = data
    st.title(f"🏛️ v16.1 Alpha Quant System")
    
    # 지표 요약
    c1, c2, c3 = st.columns(3)
    curr = df['Close'].iloc[-1]
    c1.metric("현재가", f"{curr:,.2f}")
    c2.metric("20일 이평선", f"{df['MA20'].iloc[-1]:,.2f}")
    
    # 뉴스 섹션
    st.markdown("### 📰 실시간 뉴스")
    for n in get_news(stock):
        st.markdown(f"• [{n['title']}]({n['link']})")

    # 차트
    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
    
    if top:
        fig.add_trace(go.Scatter(x=[df.index[top[0][0]], df.index[top[0][-1]]], y=[top[2][0], top[2][-1]], mode='lines', line=dict(color='red', dash='dot'), name='Resistance'))
    if bot:
        fig.add_trace(go.Scatter(x=[df.index[bot[0][0]], df.index[bot[0][-1]]], y=[bot[2][0], bot[2][-1]], mode='lines', line=dict(color='blue', dash='dot'), name='Support'))

    fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("데이터 로드 중 오류가 발생했습니다. 티커를 확인하거나 잠시 후 다시 시도해 주세요.")
