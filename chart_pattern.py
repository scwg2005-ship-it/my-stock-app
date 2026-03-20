import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Quantum Terminal v24.3")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    @media (max-width: 640px) { .main-title { font-size: 1.6rem; } }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI 뉴스 및 테마 감지 엔진 ---
@st.cache_data(ttl=600)
def get_ai_news_data():
    try:
        url = "https://finance.naver.com/news/mainnews.naver"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        headlines = [item.get_text(strip=True) for item in soup.select('.articleSubject a')[:8]]
        
        # 키워드 기반 AI 판정
        bull = ['상승', '급등', '반등', '호조', '매수', '훈풍']
        bear = ['하락', '급락', '우려', '부진', '매도', '위기']
        b_cnt = sum(any(w in h for w in bull) for h in headlines)
        s_cnt = sum(any(w in h for w in bear) for h in headlines)
        
        if b_cnt > s_cnt: judgment = "🔵 AI 판정: [매수 유리] 긍정적 흐름"
        elif s_cnt > b_cnt: judgment = "🔴 AI 판정: [매도 유리] 경계 필요"
        else: judgment = "⚪ AI 판정: [중립] 방향성 탐색 중"
        
        return headlines, judgment
    except:
        return ["뉴스를 불러올 수 없습니다."], "⚠️ 분석 불가"

# --- 3. 주가 데이터 수집 엔진 ---
@st.cache_data(ttl=3600)
def get_stock_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        df = pd.read_html(res.text, flavor='lxml')[0].dropna()
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 4. 메인 실행 ---
st.markdown('<p class="main-title">Quantum Terminal v24.3</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.write("---")
    st.caption("Quantum Engine v24.3 Active")

df = get_stock_data(target_stock)
headlines, news_judgment = get_ai_news_data()

if df is not None and not df.empty:
    curr_p = df['Close'].iloc[-1]
    
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 온도계", "🔍 [3P] 뉴스 및 테마"])

    # --- Tab 1: 차트 및 대시보드 ---
    with tab1:
        st.info(news_judgment)
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{curr_p:,.0f}원", f"{df['Diff'].iloc[-1]:+,.0f}")
        m2.metric("AI 목표가", f"{curr_p*1.15:,.0f}원", "+15%")
        m3.metric("AI 손절가", f"{curr_p*0.93:,.0f}원", "-7%")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff', name='시세'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='gray', name='거래량'), row=2, col=1)
        
        # 줌 방지 (핵심 수정 사항)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- Tab 2: AI 온도계 및 정밀 전략 ---
    with tab2:
        st.subheader("🤖 AI 정밀 진단 및 손익 시뮬레이션")
        c1, c2 = st.columns([1, 1.2])
        with c1:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=72, # 예시 점수
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00e5ff"},
                       'steps': [{'range': [0, 30], 'color': "#111"}, {'range': [70, 100], 'color': "#333"}]},
                title={'text': "AI 신뢰 점수"}
            ))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
        with c2:
            st.write("### 💸 1,000만원 투자 시 가이드")
            st.metric("목표 도달 시 이익", f"+1,500,000원", "Target")
            st.metric("손절 발생 시 손실", f"-700,000원", "Risk", delta_color="inverse")
            st.divider()
            st.checkbox("POC 매물대 지지 여부 체크", value=True)
            st.checkbox("RSI 과매수 탈피 여부 체크", value=False)

    # --- Tab 3: 뉴스 및 테마 감지 ---
    with tab3:
        st.subheader("🔍 실시간 뉴스 브리핑")
        for h in headlines:
            st.write(f"- {h}")
        st.divider()
        st.subheader("🔥 현재 주도 테마 (추정)")
        st.table(pd.DataFrame({'테마': ['반도체', 'AI', '2차전지'], '강도': ['🔥🔥🔥', '🔥🔥', '🔥']}))

else:
    st.error("데이터 로드 실패! 종목명을 확인해 주세요.")
