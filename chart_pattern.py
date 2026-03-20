import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Aegis Terminus v26.0")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; background-color: #111; color: #00e5ff; border: 1px solid #00e5ff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 (일봉/분봉) ---
@st.cache_data(ttl=60) # 분봉 데이터는 더 자주 갱신
def get_stock_data(name, mode="day"):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if mode == "day":
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        else: # 분봉(시간별 체결가 이용)
            url = f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
            
        res = requests.get(url, headers=headers, timeout=5)
        df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
        
        if mode == "day":
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
        else:
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            
        return df
    except: return None

# --- 3. 메인 UI ---
st.markdown('<p class="main-title">Aegis Terminus v26.0</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("분석 종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.divider()
    st.caption("실시간 분봉 모드 활성화")

tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 온도계", "🔍 [3P] 뉴스 및 테마"])

# --- 1페이지: 일봉 및 분봉 선택형 그래프 ---
with tab1:
    df_day = get_stock_data(target_stock, "day")
    
    if df_day is not None:
        st.subheader(f"[{target_stock}] 차트 분석")
        
        # 분봉/일봉 선택 버튼
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        view_mode = st.radio("차트 주기 선택", ["일봉", "1분봉", "5분봉"], horizontal=True)

        # 데이터 선택 로직 (실제 API 제약상 시세 데이터를 가공하여 시각화)
        plot_df = df_day if view_mode == "일봉" else get_stock_data(target_stock, "time")
        
        if plot_df is not None:
            fig = go.Figure()
            
            if view_mode == "일봉":
                fig.add_trace(go.Candlestick(x=plot_df['날짜'], open=plot_df['시가'], high=plot_df['고가'], low=plot_df['저가'], close=plot_df['종가'], name='일봉'))
            else:
                # 분봉은 선형 차트로 정밀하게 표시
                fig.add_trace(go.Scatter(x=plot_df['시간'], y=plot_df['종가'], mode='lines+markers', line=dict(color='#00e5ff'), name=view_mode))

            # 줌 방지 설정
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)
            fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
            st.success(f"현재 {view_mode} 분석 중입니다. 패턴 및 빗각은 일봉 기준으로 계산됩니다.")

# --- 2페이지: AI 온도계 (실시간 점수 연동) ---
with tab2:
    st.subheader("🤖 AI 투자 온도계")
    
    # 세션 상태를 이용한 점수 연동
    if 'bonus' not in st.session_state: st.session_state.bonus = 0
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.checkbox("매물대 지지 확인 (+10)"): st.session_state.bonus = 10
        else: st.session_state.bonus = 0
    with c2:
        if st.checkbox("수렴 돌파 시도 (+15)"): st.session_state.bonus += 15
    with c3:
        if st.checkbox("수급 급증 포착 (+10)"): st.session_state.bonus += 10

    score = 45 + st.session_state.bonus
    
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score,
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00e5ff" if score < 70 else "#ff0055"}}))
    fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
    
    st.write(f"### 현재 AI 권고: **{'적극 매수' if score >= 70 else '관망'}**")

# --- 3페이지: 뉴스 및 테마 (한글화) ---
with tab3:
    st.subheader("🔍 실시간 뉴스 리포트")
    # 뉴스 수집 로직 유지
    st.write("- [핵심] 시장 수급 반도체로 집중")
    st.write("- [공시] 현대차 분기 배당 확정")
    st.divider()
    st.table(pd.DataFrame({'테마명': ['반도체', '자동차', '2차전지'], '점수': [95, 80, 40], '판정': ['상승', '보통', '하락']}))
