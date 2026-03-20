import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import trendln
from sklearn.cluster import KMeans
import feedparser
from bs4 import BeautifulSoup

# --- 1. 전역 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="v16.0 Alpha Quant System")
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 종목 코드 검색 함수 ---
def get_stock_code(name):
    if 'krx_list' not in st.session_state:
        st.session_state['krx_list'] = fdr.StockListing('KRX')
    if 'nasdaq_list' not in st.session_state:
        st.session_state['nasdaq_list'] = fdr.StockListing('NASDAQ')

    df_krx = st.session_state['krx_list']
    df_nasdaq = st.session_state['nasdaq_list']
    
    # 한국 종목명 검색
    target = df_krx[df_krx['Name'] == name]
    if not target.empty: return target.iloc[0]['Code']
    
    # 미국 티커 검색
    target = df_nasdaq[df_nasdaq['Symbol'] == name.upper()]
    if not target.empty: return target.iloc[0]['Symbol']
    
    return name.upper() 

# --- 3. 실시간 뉴스 및 감성 분석 ---
def get_realtime_news(keyword):
    # 미국 종목(영문)과 한국 종목 구분하여 RSS 검색
    if keyword.replace(".","").replace("-","").isupper():
        rss_url = f"https://news.google.com/rss/search?q={keyword}+stock+news&hl=en-US&gl=US&ceid=US:en"
    else:
        rss_url = f"https://news.google.com/rss/search?q={keyword}+주식+뉴스&hl=ko&gl=KR&ceid=KR:ko"
        
    feed = feedparser.parse(rss_url)
    news_data = []
    
    pos_keywords = ['상승', '호재', '계약', '돌파', '실적개선', 'soar', 'buy', 'growth', 'positive']
    neg_keywords = ['하락', '악재', '유상증자', '손실', '급락', 'drop', 'sell', 'loss', 'negative']

    for entry in feed.entries[:5]:
        title = entry.title
        score = sum(1 for w in pos_keywords if w in title.lower()) - sum(1 for w in neg_keywords if w in title.lower())
        sentiment = "🚀 호재" if score > 0 else ("⚠️ 악재" if score < 0 else "😐 중립")
        news_data.append({'title': title, 'link': entry.link, 'sentiment': sentiment, 'date': entry.published})
    return news_data

# --- 4. 핵심 분석 로직 (기술적 지표 + AI 매물대) ---
@st.cache_data(ttl=300)
def analyze_data(symbol, period=250):
    try:
        df = fdr.DataReader(symbol).tail(period)
        if df.empty: return None, None, None, None
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (std * 2)
        df['BB_Lower'] = df['MA20'] - (std * 2)
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/(loss + 1e-9)))

        # 빗각/추세선 (trendln)
        h_lines = trendln.get_lines(df['High'].values, extmethod=trendln.METHOD_NAIVE)
        l_lines = trendln.get_lines(df['Low'].values, extmethod=trendln.METHOD_NAIVE)
        
        # AI 매물대 (K-Means)
        kmeans = KMeans(n_clusters=5, n_init=10).fit(df[['Close']].tail(100))
        poc = kmeans.cluster_centers_.flatten()[np.abs(kmeans.cluster_centers_.flatten() - df['Close'].iloc[-1]).argmin()]

        return df, h_lines[0] if h_lines else None, l_lines[0] if l_lines else None, poc
    except:
        return None, None, None, None

# --- 5. UI 메인 레이아웃 ---
st.sidebar.title("⚙️ Alpha Quant 제어판")
stock_name = st.sidebar.text_input("종목명(한글) 또는 티커", value="ONDS")
period_val = st.sidebar.slider("분석 기간", 100, 500, 250)
refresh_btn = st.sidebar.button("실시간 데이터 갱신 🔄")

code = get_stock_code(stock_name)
df, top_line, bot_line, poc_val = analyze_data(code, period_val)
news_list = get_realtime_news(stock_name)

if df is not None:
    st.title(f"🏛️ v16.0 Alpha Quant System")
    st.subheader(f"📊 {stock_name} ({code}) 실시간 분석 리포트")

    # [섹션 1] 실시간 호가 및 감성 지표
    c1, c2, c3, c4 = st.columns(4)
    curr_price = df['Close'].iloc[-1]
    prev_price = df['Close'].iloc[-2]
    change = curr_price - prev_price
    
    c1.metric("현재가", f"{curr_price:,.0f}", f"{change:+,} ({(change/prev_price)*100:+.2f}%)")
    c2.metric("퀀트 온도 (RSI)", f"{df['RSI'].iloc[-1]:.1f}°C")
    c3.metric("AI 매물대 (POC)", f"{poc_val:,.0f}")
    
    # 뉴스 감성 합산
    pos_count = sum(1 for n in news_list if "🚀" in n['sentiment'])
    neg_count = sum(1 for n in news_list if "⚠️" in n['sentiment'])
    overall_sent = "매수 우위" if pos_count > neg_count else ("매도 우위" if neg_count > pos_count else "중립")
    c4.metric("종합 뉴스 감성", overall_sent)

    st.divider()

    # [섹션 2] 실시간 뉴스 보드 & 매매 전략
    col_news, col_strat = st.columns([2, 1])
    
    with col_news:
        st.markdown("### 📰 실시간 주요 뉴스 (AI 감성 분석)")
        for n in news_list:
            with st.expander(f"[{n['sentiment']}] {n['title'][:50]}..."):
                st.write(f"일시: {n['date']}")
                st.write(n['title'])
                st.markdown(f"[뉴스 원문 보기]({n['link']})")

    with col_strat:
        st.markdown("### 🚨 실시간 대응 가이드")
        if "매수" in overall_sent:
            st.success(f"**🟢 강력 매수 신호**\n뉴스 호재와 기술적 반등이 일치합니다.\n목표가: {curr_price*1.1:,.0f}")
        elif "매도" in overall_sent:
            st.error(f"**🔴 긴급 손절 경고**\n악재 뉴스가 감지되었습니다.\n손절가: {curr_price*0.95:,.0f} 엄수")
        else:
            st.info("**🟡 관망 구간**\n뚜렷한 방향성이 없습니다. 매물대 {poc_val:,.0f} 돌파 확인 필요")

    # [섹션 3] 메인 차트 (빗각 및 추세선)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # 캔들차트
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
    
    # 빗각 추세선 시각화
    if top_line is not None:
        fig.add_trace(go.Scatter(x=[df.index[top_line[0][0]], df.index[top_line[0][-1]]], y=[top_line[2][0], top_line[2][-1]], 
                                 mode='lines', line=dict(color='red', width=2, dash='dot'), name='하락 빗각(저항)'), row=1, col=1)
    if bot_line is not None:
        fig.add_trace(go.Scatter(x=[df.index[bot_line[0][0]], df.index[bot_line[0][-1]]], y=[bot_line[2][0], bot_line[2][-1]], 
                                 mode='lines', line=dict(color='blue', width=2, dash='dot'), name='상승 빗각(지지)'), row=1, col=1)

    # 볼린저 밴드
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(255,255,255,0.2)'), name='BB상단'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(255,255,255,0.2)'), fill='tonexty', name='BB하단'), row=1, col=1)

    # 거래량 및 RSI
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='거래량', marker_color='gray'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='orange')), row=2, col=1)

    fig.update_layout(height=800, template='plotly_dark', xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("종목을 찾을 수 없거나 데이터 로드에 실패했습니다. 종목명을 다시 확인해주세요.")
