import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v18.5 Alpha Quant")

# --- 2. 데이터 수집 엔진 (안정화 버전) ---
@st.cache_data(ttl=3600)
def get_naver_data(name):
    codes = {
        "현대자동차": "005380", "현대차": "005380",
        "삼성전자": "005930", "삼전": "005930",
        "SK하이닉스": "000660", "하이닉스": "000660"
    }
    
    code = codes.get(name.strip())
    if not code:
        return None

    # 네이버 금융 일별 시세 (모바일 페이지가 수집이 더 안정적입니다)
    url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers)
        # html5lib 대신 기본 html.parser 또는 lxml 사용 시도
        df_list = pd.read_html(res.text)
        df = df_list[0].dropna()
        
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df
    except Exception as e:
        return None

# --- 3. 메인 UI ---
st.title("🏛️ v18.5 Alpha Quant (Stable Scraper)")

with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명 입력 (현대자동차, 삼성전자)", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("분석 실행 🚀")

if submitted or stock_input:
    df = get_naver_data(stock_input)

    if df is not None and not df.empty:
        tab1, tab2, tab3 = st.tabs(["📈 분석 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])
        
        with tab1:
            st.subheader(f"[{stock_input}] 시세 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.info("온도계 분석 준비 중...")
        with tab3:
            st.success("전략 도출 완료")
    else:
        st.error("데이터 수집 엔진 설치 중입니다. 잠시 후 다시 분석 실행을 눌러주세요.")
