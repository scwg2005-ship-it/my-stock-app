import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse
import numpy as np

# 1. 페이지 설정 및 모바일 스타일링
st.set_page_config(layout="wide", page_title="AI 모바일 투자 비서", page_icon="📱")
st.markdown("""
    <style>
    /* 모바일에서 글자 크기 및 여백 조정 */
    .main { padding: 10px !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stSidebar"] { width: 250px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 사이드바: 설정 ---
st.sidebar.header("⚙️ 설정")
ticker = st.sidebar.text_input("종목 코드", value="005930.KS").upper()
chart_type = st.sidebar.radio("단위", ["일봉", "분봉"])

if chart_type == "일봉":
    period = st.sidebar.selectbox("기간", ["3mo", "6mo", "1y"], index=0)
    interval = "1d"
else:
    period = st.sidebar.selectbox("최근", ["1d", "5d"], index=0)
    interval = st.sidebar.selectbox("분", ["1m", "5m", "15m"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("🧮 계산기")
buy_price = st.sidebar.number_input("내 평단가", value=0.0, step=0.1)
quantity = st.sidebar.number_input("내 수량", value=0, step=1)

@st.cache_data(ttl=60)
def load_data(symbol, p, i):
    try:
        df = yf.download(symbol, period=p, interval=i)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df.dropna()
    except: return None

df = load_data(ticker, period, interval)

if df is not None and not df.empty:
    # 지표 계산
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # 삼각수렴 빗각
    x_axis = np.arange(len(df))
    upper_trend = np.poly1d(np.polyfit([0, len(df)-1], [df['High'].max(), df['High'].iloc[-1]], 1))(x_axis)
    lower_trend = np.poly1d(np.polyfit([0, len(df)-1], [df['Low'].min(), df['Low'].iloc[-1]], 1))(x_axis)

    # --- 3. [모바일형] 상단 요약 카드 ---
    st.title(f"📈 {ticker} 분석")
    
    is_us = not (ticker.endswith(".KS") or ticker.endswith(".KQ"))
    unit = "$" if is_us else "원"
    fmt = ",.2f" if is_us else ",.0f"

    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change = curr_p - prev_p
    pct = (change / prev_p) * 100

    # 모바일은 2열씩 배치
    m1, m2 = st.columns(2)
    m1.metric("현재가", f"{unit}{curr_p:{fmt}}", f"{pct:.2f}%")
    
    if buy_price > 0 and quantity > 0:
        profit = (curr_p - buy_price) * quantity
        p_rate = ((curr_p - buy_price) / buy_price) * 100
        m2.metric("내 수익률", f"{p_rate:.2f}%", f"{unit}{profit:{fmt}}")
    else:
        m2.metric("변동폭", f"{change:{fmt}}", "수익률 계산대기")

    # --- 4. [모바일형] 알림 메시지 ---
    if curr_p > df['MA5'].iloc[-1]:
        st.success(f"✅ **상승세**: 주가가 5일선 위에서 탄력을 받는 중!")
    else:
        st.error(f"📉 **조정 중**: 현재 5일선 아래에 머물러 있습니다.")

    # --- 5. 메인 차트 (큼직하게) ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='yellow', width=1.5), name='5평균'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=upper_trend, line=dict(color='red', width=2, dash='dash'), name='저항'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=lower_trend, line=dict(color='green', width=2, dash='dash'), name='지지'), row=1, col=1)
    
    v_colors = ['red' if o < c else 'blue' for o, c in zip(df['Open'], df['Close'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name='거래량'), row=2, col=1)
    
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=5, b=5))
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. 뉴스 (아래로 길게) ---
    st.markdown("---")
    st.subheader("📰 실시간 뉴스")
    search_term = ticker.split('.')[0]
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(search_term)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    for entry in feed.entries[:8]:
        with st.expander(f"[{entry.title.rsplit(' - ', 1)[-1] if ' - ' in entry.title else '뉴스'}] {entry.title.split(' - ')[0][:25]}..."):
            st.write(entry.title.rsplit(' - ', 1)[0])
            st.link_button("기사 원문 열기", entry.link)
else:
    st.error("데이터 로딩 실패. 종목 코드를 확인해 주세요.")
