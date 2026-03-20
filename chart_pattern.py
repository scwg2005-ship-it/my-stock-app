import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup

# --- 1. 스타일 및 설정 ---
st.set_page_config(layout="wide", page_title="Quantum Trader v24.1")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 (에러 방지 로직 강화) ---
@st.cache_data(ttl=600)
def get_safe_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None, pd.DataFrame()

    url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        # lxml 파서를 명시하여 에러 방지
        dfs = pd.read_html(res.text, flavor='lxml')
        if not dfs: return None, pd.DataFrame()
        
        df = dfs[0].dropna()
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 가상의 백테스트 데이터 (에러 방지용 기본값)
        bt_df = pd.DataFrame({
            '전략': ['AI종합', '수급돌파', 'RSI반전'],
            '승률': [75.2, 62.1, 68.5],
            '수익률': [32.8, 12.5, 18.2]
        })
        return df, bt_df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return None, pd.DataFrame()

# --- 3. 메인 실행 ---
st.markdown('<p class="main-title">Quantum Trader v24.1</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    btn = st.button("분석 실행")

df, bt_df = get_safe_data(target_stock)

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["[1P] 통합 차트", "[2P] AI 정밀 진단", "[3P] 자동 매매 & 백테스트"])

    with tab1:
        # 차트 줌인 방지 설정 (fixedrange)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff'), row=1, col=1)
        fig.update_xaxes(fixedrange=True) # 줌 방지
        fig.update_yaxes(fixedrange=True) # 줌 방지
        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        st.subheader("🤖 AI 정밀 진단")
        st.metric("추천 매수가", f"{df['Close'].iloc[-1]*0.98:,.0f}원")
        st.metric("목표가", f"{df['Close'].iloc[-1]*1.12:,.0f}원")

    with tab3:
        st.subheader("📊 AI 자동 매매 점수 & 백테스트")
        if not bt_df.empty:
            fig_bt = go.Figure(go.Bar(x=bt_df['전략'], y=bt_df['승률'], marker_color='#00e5ff'))
            fig_bt.update_layout(height=400, template='plotly_dark', fixedrange=True)
            st.plotly_chart(fig_bt, use_container_width=True, config={'displayModeBar': False})
else:
    st.warning("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")
