import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Quantum Trader v29.0")
st.markdown("""
    <style>
    .stMetric { background-color: #0d0d0d; border: 1px solid #333; padding: 10px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 및 크로스 로직 엔진 ---
@st.cache_data(ttl=300)
def get_cross_data(name, mode="day"):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        p_count = 5 if mode in ["day", "month"] else 1
        all_dfs = []
        for p in range(1, p_count + 1):
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}"
            res = requests.get(url, headers=headers, timeout=5)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            if dfs: all_dfs.append(dfs[0].dropna())
        
        df = pd.concat(all_dfs)
        df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
        df['날짜'] = pd.to_datetime(df['날짜'])
        df = df.set_index('날짜').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 이동평균선 (5일선, 20일선)
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        
        # 골든크로스 & 데드크로스 판정
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        return df
    except: return None

# --- 3. UI 구성 ---
st.markdown('<p class="main-title">Quantum Trader v24.0: Dual Cross</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.divider()
    st.caption("Golden & Dead Cross Mode")

df = get_cross_data(target_stock)

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 점수판", "🔍 [3P] 테마 뉴스"])

    with tab1:
        view_mode = st.radio("주기 선택", ["일봉", "월봉"], horizontal=True)
        
        # 차트 생성 (줌 방지 포함)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff', name='가격'), row=1, col=1)
        
        # 이평선
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ffdf00', width=1.5), name='5일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1.5, dash='dot'), name='20일선'), row=1, col=1)
        
        # 골든크로스(GC) & 데드크로스(DC) 신호
        gc_dates = df[df['GC'] == True].index
        for date in gc_dates:
            fig.add_annotation(x=date, y=df.loc[date, '저가'], text="✨GOLDEN", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), yshift=-10, row=1, col=1)
        
        dc_dates = df[df['DC'] == True].index
        for date in dc_dates:
            fig.add_annotation(x=date, y=df.loc[date, '고가'], text="💀DEAD", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), yshift=10, row=1, col=1)

        # 거래량
        fig.add_trace(go.Bar(x=df.index, y=df['거래량'], marker_color='#333', name='거래량'), row=2, col=1)
        
        # 줌 방지 설정
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        st.subheader("🤖 AI 전략 점수판")
        bonus = 0
        if df['GC'].iloc[-1]: bonus += 20
        if df['DC'].iloc[-1]: bonus -= 20
        
        final_s = 50 + bonus
        st.metric("최종 AI 점수", f"{final_s}점", f"크로스 영향: {bonus:+d}")
        
        st.write("---")
        st.checkbox("골든크로스 발생 확인", value=df['GC'].iloc[-1])
        st.checkbox("데드크로스 회피 확인", value=not df['DC'].iloc[-1])

    with tab3:
        st.subheader("🔍 실시간 테마 소식")
        st.write("현재 증시의 주요 이슈를 분석 중입니다.")
