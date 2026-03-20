import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Alpha Quant v25.5")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 ---
@st.cache_data(ttl=600)
def get_naver_data(name):
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

# --- 3. 패턴 분석 로직 (1페이지용) ---
def analyze_v25_5(df):
    indices = np.arange(len(df))
    # 엘리어트 파동 모사 (최근 25일 내 5개 변곡점)
    wave_idx = [len(df)-25, len(df)-20, len(df)-15, len(df)-10, len(df)-1]
    # 삼각수렴 빗각 (최근 20일)
    h_fit = np.polyfit(indices[-20:], df['High'].iloc[-20:], 1)
    l_fit = np.polyfit(indices[-20:], df['Low'].iloc[-20:], 1)
    # 지지/저항
    res_l = df['High'].tail(60).max()
    sup_l = df['Low'].tail(60).min()
    return {
        'w_x': df.index[wave_idx], 'w_y': df['Close'].iloc[wave_idx],
        'h_line': h_fit[0] * indices[-20:] + h_fit[1],
        'l_line': l_fit[0] * indices[-20:] + l_fit[1],
        'res': res_l, 'sup': sup_l
    }

# --- 4. 메인 실행 ---
st.markdown('<p class="main-title">Alpha Quant v25.5</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스"])
    st.write("---")
    st.caption("Integrated Analytics Mode")

df = get_naver_data(target_stock)

if df is not None:
    curr_p = df['Close'].iloc[-1]
    res = analyze_v25_5(df)
    
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 패턴 차트", "🌡️ [2P] AI 점수 연동", "🔍 [3P] 실시간 뉴스"])

    # --- 1페이지: 화려한 분석 차트 복구 ---
    with tab1:
        st.subheader(f"[{target_stock}] 엘리어트 파동 & 삼각수렴 분석")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        
        # 엘리어트 파동 (노란선)
        fig.add_trace(go.Scatter(x=res['w_x'], y=res['w_y'], mode='lines+markers+text', 
                                 text=['1','2','3','4','5'], textposition='top center',
                                 line=dict(color='yellow', width=2), name='Wave'), row=1, col=1)
        # 삼각수렴 빗각 (점선)
        fig.add_trace(go.Scatter(x=df.index[-20:], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-20:], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)
        # 수평 지지/저항
        fig.add_hline(y=res['res'], line_dash="solid", line_color="red", row=1, col=1)
        fig.add_hline(y=res['sup'], line_dash="solid", line_color="dodgerblue", row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='gray'), row=2, col=1)
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 2페이지: 체크박스 점수 실시간 연동 ---
    with tab2:
        st.subheader("🤖 AI 점수 및 사용자 판단 피드백")
        bonus = 0
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.checkbox("POC 매물대 지지 (+10)"): bonus += 10
        with c2: 
            if st.checkbox("삼각수렴 돌파 시도 (+15)"): bonus += 15
        with c3: 
            if st.checkbox("거래량 급증 포착 (+10)"): bonus += 10
        
        final_s = 45 + bonus # 기본 45점 + 사용자 보너스
        
        col_g, col_t = st.columns([1, 1.2])
        with col_g:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=final_s,
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00e5ff" if final_s < 70 else "#ff0055"}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
        with col_t:
            if final_s >= 70: st.error("🔥 전략: [적극 매수] 강력 추천")
            elif final_s >= 55: st.warning("✅ 전략: [보유/추가] 긍정적")
            else: st.info("⚖️ 전략: [관망] 신중 필요")
            st.metric("추천 매수가", f"{curr_p*0.98:,.0f}원")
            st.metric("목표가", f"{curr_p*1.12:,.0f}원")
            
    with tab3:
        st.write("실시간 뉴스 리스트 영역입니다.")

else: st.error("데이터 로드 실패")
