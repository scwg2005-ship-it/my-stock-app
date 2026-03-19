import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse
import numpy as np

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="AI 프로 투자 시스템", page_icon="📈")

# --- 2. 사이드바: 설정 및 나의 포트폴리오 ---
st.sidebar.header("🔍 시스템 설정")
ticker = st.sidebar.text_input("종목 코드 입력 (예: ONDS, 005930.KS)", value="005930.KS").upper()
period = st.sidebar.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=1)

st.sidebar.markdown("---")
st.sidebar.header("🧮 나의 포트폴리오")
buy_price = st.sidebar.number_input("평균 매수가 (해당 통화 기준)", value=0.0, step=0.1)
quantity = st.sidebar.number_input("보유 수량", value=0, step=1)

@st.cache_data
def load_data(symbol, p):
    try:
        df = yf.download(symbol, period=p, interval="1d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df.dropna()
    except: return None

df = load_data(ticker, period)

if df is not None and not df.empty:
    # --- 데이터 계산 영역 ---
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # RSI 계산
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # 삼각수렴 빗각 계산 (고점/저점 추세선)
    x_axis = np.arange(len(df))
    upper_trend = np.poly1d(np.polyfit([0, len(df)-1], [df['High'].max(), df['High'].iloc[-1]], 1))(x_axis)
    lower_trend = np.poly1d(np.polyfit([0, len(df)-1], [df['Low'].min(), df['Low'].iloc[-1]], 1))(x_axis)

    # --- 상단 요약 정보 (통화 자동 구분) ---
    is_us = not (ticker.endswith(".KS") or ticker.endswith(".KQ"))
    unit = "$" if is_us else "원"
    fmt = ",.2f" if is_us else ",.0f"

    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change = curr_p - prev_p
    pct = (change / prev_p) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재가", f"{unit}{curr_p:{fmt}}", f"{change:{fmt}} ({pct:.2f}%)")
    c2.metric("RSI 심리도", f"{df['RSI'].iloc[-1]:.1f}", "안정" if 35 < df['RSI'].iloc[-1] < 65 else "주의")
    
    if buy_price > 0 and quantity > 0:
        profit = (curr_p - buy_price) * quantity
        p_rate = ((curr_p - buy_price) / buy_price) * 100
        c3.metric("나의 손익", f"{unit}{profit:{fmt}}", f"{p_rate:.2f}%")
    
    # 추세 탄력 (5일선 이격도)
    momentum = ((curr_p - df['MA5'].iloc[-1]) / df['MA5'].iloc[-1]) * 100
    c4.metric("단기 추세 탄력", f"{momentum:.2f}%", "상승세" if momentum > 0 else "조정")

    st.markdown("---")

    # --- 3. 실시간 알림창 ---
    st.subheader("🔔 현재 알림")
    cols = st.columns(3)
    with cols[0]:
        if df['MA5'].iloc[-1] > df['MA20'].iloc[-1]: st.success("✅ **단기 정배열**: 5일선이 20일선 위에 안착함")
        else: st.error("⚠️ **단기 역배열**: 리스크 관리 필요 구간")
    with cols[1]:
        st.info(f"💎 **심리 지표**: 현재 RSI {df['RSI'].iloc[-1]:.1f}로 그대로 유지 중")
    with cols[2]:
        if curr_p > df['MA5'].iloc[-1]: st.success("📈 **주가 추세**: 5일선 위에서 탄력 받는 중")
        else: st.error("📉 **주가 추세**: 5일선 하회, 단기 조정 주의")

    # --- 4. 메인 차트 및 뉴스 ---
    col_left, col_right = st.columns([7.5, 2.5])

    with col_left:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        
        # 캔들차트 & 이평선
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='yellow', width=1.5), name='5일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='magenta', width=2), name='20일선'), row=1, col=1)
        
        # 삼각수렴 빗각 (추세선)
        fig.add_trace(go.Scatter(x=df.index, y=upper_trend, line=dict(color='red', width=2, dash='dash'), name='저항선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower_trend, line=dict(color='green', width=2, dash='dash'), name='지지선'), row=1, col=1)

        # 거래량
        v_colors = ['red' if o < c else 'blue' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name='거래량'), row=2, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("📰 핵심 뉴스")
        search_term = ticker.split('.')[0]
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(search_term)}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            st.markdown(f"**[{entry.title.rsplit(' - ', 1)[-1] if ' - ' in entry.title else '뉴스'}]**")
            st.markdown(f"[{entry.title.rsplit(' - ', 1)[0]}]({entry.link})")
            st.divider()
else:
    st.error("데이터 로딩 실패. 종목 코드를 확인해 주세요.")