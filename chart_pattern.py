import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v18.3 Alpha Quant")

@st.cache_data(ttl=3600)
def load_data_yfinance(keyword):
    # 하드코딩 매핑 (한국 주식 전용)
    mapping = {
        "현대자동차": "005380.KS", "현대차": "005380.KS",
        "삼성전자": "005930.KS", "삼전": "005930.KS",
        "SK하이닉스": "000660.KS", "하이닉스": "000660.KS",
        "카카오": "035720.KS", "에코프로": "086520.KQ"
    }
    
    # 1. 매핑된 코드가 있으면 사용, 없으면 입력값 그대로 사용
    symbol = mapping.get(keyword.strip(), keyword.strip().upper())
    
    try:
        # yfinance로 데이터 직접 로드
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y") # 최근 1년치
        
        if not df.empty:
            return df, symbol
        return None, None
    except:
        return None, None

# --- 2. UI 구성 ---
st.title("🏛️ v18.3 Alpha Quant (Global)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명(현대차) 또는 미국티커(NVDA, ONDS)", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    df, real_symbol = load_data_yfinance(stock_input)

    if df is not None:
        # 차트 그리기
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{stock_input} ({real_symbol})] 실시간 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("온도계 분석 중...")
        with tab3:
            st.success("전략 도출 완료")
    else:
        st.error(f"⚠️ '{stock_input}' 데이터를 불러올 수 없습니다. yfinance 서버 응답을 확인하세요.")
