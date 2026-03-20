import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Quantum Terminal v26.2")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 초경량 데이터 수집 엔진 (차단 방지 강화) ---
@st.cache_data(ttl=600)
def get_clean_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None, [], "종목코드 없음"

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    
    try:
        # 주가 데이터
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=5)
        # read_html 대신 StringIO를 사용하여 경고 방지
        from io import StringIO
        dfs = pd.read_html(StringIO(res.text), flavor='lxml')
        df = dfs[0].dropna()
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')

        # 뉴스 데이터
        n_url = "https://finance.naver.com/news/mainnews.naver"
        n_res = requests.get(n_url, headers=headers, timeout=5)
        soup = BeautifulSoup(n_res.text, 'html.parser')
        headlines = [item.get_text(strip=True) for item in soup.select('.articleSubject a')[:5]]
        
        return df, headlines, "성공"
    except Exception as e:
        return None, [], str(e)

# --- 3. 메인 실행부 ---
st.markdown('<p class="main-title">Quantum Terminal v26.2</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.write("---")
    st.caption("Fixed Static Mode")

df, headlines, msg = get_clean_data(target_stock)

if df is not None and not df.empty:
    curr_p = df['Close'].iloc[-1]
    
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 온도계", "🔍 [3P] 뉴스"])

    with tab1:
        # 1페이지: 패턴 차트 (줌 방지)
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{curr_p:,.0f}원")
        m2.metric("목표가", f"{curr_p*1.15:,.0f}원")
        m3.metric("손절가", f"{curr_p*0.93:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff'), row=1, col=1)
        
        # 엘리어트 파동 및 빗각 (간소화하여 에러 방지)
        idx = np.arange(len(df))
        h_fit = np.polyfit(idx[-15:], df['High'].iloc[-15:], 1)
        l_fit = np.polyfit(idx[-15:], df['Low'].iloc[-15:], 1)
        fig.add_trace(go.Scatter(x=df.index[-15:], y=h_fit[0]*idx[-15:]+h_fit[1], line=dict(color='cyan', dash='dash'), name='저항'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-15:], y=l_fit[0]*idx[-15:]+l_fit[1], line=dict(color='magenta', dash='dash'), name='지지'), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        st.subheader("🌡️ AI 온도계 및 점수 연동")
        bonus = 0
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("매물대 지지 (+10)"): bonus += 10
            if st.checkbox("거래량 급증 (+15)"): bonus += 15
        
        final_score = 45 + bonus
        with c2:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=final_score,
                                           gauge={'axis':{'range':[0,100]}, 'bar':{'color':'#00e5ff'}}))
            fig_g.update_layout(height=300, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    with tab3:
        st.subheader("🔍 실시간 증시 뉴스")
        for h in headlines:
            st.write(f"- {h}")
else:
    st.error(f"데이터를 불러올 수 없습니다. (에러: {msg})")
    st.info("사유: 네이버 금융 서버에서 일시적으로 접속을 제한했을 수 있습니다. 잠시 후 다시 시도해 주세요.")
