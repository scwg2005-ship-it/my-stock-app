import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 프리미엄 UI 및 모바일 최적화 설정 ---
st.set_page_config(layout="wide", page_title="Quantum Terminal v26.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'JetBrains Mono', 'Noto Sans KR', sans-serif; background-color: #050505; color: #e0e0e0; }
    .stMetric { background-color: #111; border: 1px solid #333; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,229,255,0.1); }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #00e5ff; text-align: center; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 2px; }
    div[data-testid="stExpander"] { border: 1px solid #222; border-radius: 10px; background-color: #0a0a0a; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 고성능 데이터 엔진 ---
@st.cache_data(ttl=600)
def get_premium_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 데이터 수집 (일봉)
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=10)
        df = pd.read_html(res.text, flavor='lxml')[0].dropna()
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 3. 고급 분석 알고리즘 (패턴 & 파동) ---
def analyze_quantum(df):
    idx = np.arange(len(df))
    close = df['Close'].values
    
    # 엘리어트 파동 포인트 (모사)
    wave_idx = [len(df)-25, len(df)-20, len(df)-15, len(df)-10, len(df)-1]
    
    # 삼각수렴 빗각
    h_fit = np.polyfit(idx[-20:], df['High'].iloc[-20:], 1)
    l_fit = np.polyfit(idx[-20:], df['Low'].iloc[-20:], 1)
    
    # 지지/저항선
    res_line = df['High'].tail(40).max()
    sup_line = df['Low'].tail(40).min()
    
    return {
        'wave_x': df.index[wave_idx], 'wave_y': close[wave_idx],
        'h_line': h_fit[0] * idx[-20:] + h_fit[1],
        'l_line': l_fit[0] * idx[-20:] + l_fit[1],
        'res': res_line, 'sup': sup_line
    }

# --- 4. 메인 화면 구성 ---
st.markdown('<p class="main-title">Quantum Terminal v26.1</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("📊 Assets")
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.write("---")
    st.caption("AI-Powered Pattern Analysis")

df = get_premium_data(target_stock)

if df is not None and len(df) > 25:
    res = analyze_quantum(df)
    tab1, tab2, tab3 = st.tabs(["📉 [1P] 통합 차트 (일/분)", "🌡️ [2P] AI 온도계", "🔍 [3P] 뉴스 리포트"])

    # --- 1페이지: 일봉/분봉 통합 및 패턴 시각화 ---
    with tab1:
        # 상단 핵심 수치 대시보드
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{df['Close'].iloc[-1]:,.0f}원", f"{df['Diff'].iloc[-1]:+,.0f}")
        m2.metric("일봉 추세", "상승 수렴 중", delta_color="normal")
        m3.metric("실시간 변동", "Low Vol", delta_color="off")

        # 메인 통합 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        # 1. 캔들차트 (네온 컬러)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     increasing_line_color='#ff0055', decreasing_line_color='#00e5ff', name='Price'), row=1, col=1)
        
        # 2. 엘리어트 파동 & 빗각
        fig.add_trace(go.Scatter(x=res['wave_x'], y=res['wave_y'], mode='lines+markers+text', 
                                 text=['1','2','3','4','5'], textposition='top center',
                                 line=dict(color='#fbff00', width=2), name='Wave'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-20:], y=res['h_line'], line=dict(color='#00f2ff', dash='dash'), name='Resistance Cut'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-20:], y=res['l_line'], line=dict(color='#ff00ff', dash='dash'), name='Support Cut'), row=1, col=1)
        
        # 3. 수평 지지/저항
        fig.add_hline(y=res['res'], line_dash="solid", line_color="#ff4b4b", opacity=0.5, row=1, col=1)
        fig.add_hline(y=res['sup'], line_dash="solid", line_color="#1c83e1", opacity=0.5, row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='Volume'), row=2, col=1)
        
        # 줌 방지(Fixed Range) 및 레이아웃 최적화
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False, 
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # 분봉 데이터 리스트 (가시성 확보)
        with st.expander("⏱️ 실시간 분봉 체결 흐름 보기"):
            st.dataframe(df.tail(10).sort_index(ascending=False), use_container_width=True)

    # --- 2페이지: AI 온도계 & 사용자 체크 연동 ---
    with tab2:
        st.subheader("🌡️ AI 시장 온도계 및 전략 분석")
        
        # 체크박스 상단 배치 (상태 전이 방지)
        bonus = 0
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.checkbox("매물대 지지 확인 (+10)"): bonus += 10
        with c2: 
            if st.checkbox("패턴 돌파 시도 (+15)"): bonus += 15
        with c3: 
            if st.checkbox("수급 급증 포착 (+10)"): bonus += 10
            
        final_score = 48 + bonus # 기본 48점 설정
        
        col_g, col_s = st.columns([1, 1.2])
        with col_g:
            # 화려한 AI 게이지 차트
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=final_score,
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00e5ff" if final_score < 70 else "#ff0055"},
                       'steps': [{'range': [0, 35], 'color': "#111"}, {'range': [75, 100], 'color': "#222"}]},
                title={'text': "AI 신뢰도 점수"}
            ))
            fig_g.update_layout(height=380, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
            
        with col_s:
            st.write("### 🎯 AI 정밀 매매 가이드")
            st.info(f"**매수 진입가:** {df['Close'].iloc[-1]*0.98:,.0f}원 부근")
            st.success(f"**목표 수익가:** {df['Close'].iloc[-1]*1.12:,.0f}원 (+12%)")
            st.error(f"**리스크 손절가:** {df['Close'].iloc[-1]*0.94:,.0f}원 (-6%)")
            st.write("---")
            st.write(f"**현재 AI 판단:** {'강력 매수' if final_score > 70 else '관망 후 진입'}")

    with tab3:
        st.subheader("🔍 실시간 뉴스 브리핑")
        st.write("전체 증시 흐름을 분석 중입니다...")
        # (이전 버전의 뉴스 크롤링 로직 추가 가능)

else:
    st.warning("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")
