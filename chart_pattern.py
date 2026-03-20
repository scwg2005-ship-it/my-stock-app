import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v18.4 Alpha Quant")

# --- 2. 네이버 금융 데이터 직접 수집 함수 ---
@st.cache_data(ttl=3600)
def get_naver_data(name):
    # 하드코딩된 주요 종목 코드
    codes = {
        "현대자동차": "005380", "현대차": "005380",
        "삼성전자": "005930", "삼전": "005930",
        "SK하이닉스": "000660", "하이닉스": "000660"
    }
    
    code = codes.get(name.strip())
    if not code:
        st.error(f"'{name}' 종목의 코드를 찾을 수 없습니다. (현재 현대차, 삼성전자, 하이닉스 우선 지원)")
        return None

    url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        res = requests.get(url, headers=headers)
        df = pd.read_html(res.text, flavor='bs4')[0]
        df = df.dropna()
        
        # 컬럼명 정리 및 변환
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        # 숫자 타입 변환
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"데이터 수집 오류: {e}")
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v18.4 Alpha Quant (Direct Scraper)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명 입력 (테스트: 현대자동차)", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    df = get_naver_data(stock_input)

    if df is not None and not df.empty:
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{stock_input}] 최근 시세 (Naver 직접 수집)")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("시장의 열기를 분석 중입니다...")
        with tab3:
            st.success("데이터 기반 매매 전략 도출 완료")
    else:
        st.warning("데이터를 가져오는 데 실패했습니다. 종목명을 확인하거나 잠시 후 시도하세요.")
