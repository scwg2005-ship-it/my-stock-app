import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Aegis Terminus v25.1")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 ---
@st.cache_data(ttl=600)
def get_comprehensive_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660"}
    code = codes.get(name.strip())
    if not code: return None
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers=headers)
        df = pd.read_html(res.text, flavor='lxml')[0].dropna()
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 3. 실행 영역 ---
st.markdown('<p class="main-title">Aegis Terminus v25.1</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스"])
    st.write("---")
    st.caption("Interactive Logic Mode")

df = get_comprehensive_data(target_stock)

if df is not None:
    curr_p = df['Close'].iloc[-1]
    
    # [핵심] 체크박스 상태에 따른 점수 계산 로직
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 정밀 진단", "🔍 [3P] 실시간 뉴스"])

    with tab2:
        st.subheader("🤖 AI 정밀 진단 및 사용자 판단 연동")
        
        # 체크박스 배치 및 점수 합산
        user_score_mod = 0
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            c1 = st.checkbox("POC 매물대 지지 확인 (+10)")
            if c1: user_score_mod += 10
        with col_c2:
            c2 = st.checkbox("삼각수렴 상단 돌파 시도 (+15)")
            if c2: user_score_mod += 15
        with col_c3:
            c3 = st.checkbox("거래량 급증 포착 (+10)")
            if c3: user_score_mod += 10

        # 기본 AI 점수 (RSI 기반 모사)
        base_ai_score = 45 
        final_score = base_ai_score + user_score_mod
        
        st.divider()
        
        res_col1, res_col2 = st.columns([1, 1.2])
        with res_col1:
            # 점수에 따라 색상이 변하는 게이지
            gauge_color = "#00e5ff" if final_score < 70 else "#ff0055"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=final_score,
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': gauge_color},
                       'steps': [{'range': [0, 30], 'color': "#111"}, {'range': [70, 100], 'color': "#222"}]},
                title={'text': "최종 퀀트 스코어"}
            ))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
            
        with res_col2:
            # 점수에 따른 동적 전략 문구
            if final_score >= 70:
                st.error("🔥 전략: [적극 매수/보유] 강력한 상승 신호가 포착되었습니다.")
            elif final_score >= 55:
                st.warning("✅ 전략: [분할 진입] 긍정적인 추세 전환 중입니다.")
            else:
                st.info("⚖️ 전략: [관망] 지지선 확인이 더 필요합니다.")
                
            st.write("---")
            st.metric("추천 매수가", f"{curr_p*0.98:,.0f}원")
            st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}원")

    with tab1:
        # 1페이지 차트 (줌 방지 유지)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff'), row=1, col=1)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

else:
    st.error("데이터 로드 실패")
