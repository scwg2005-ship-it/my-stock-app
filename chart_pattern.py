import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 프리미엄 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Ultimate v30.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; background-color: #050505; color: #e0e0e0; }
    .stMetric { background-color: #111; border: 1px solid #333; padding: 15px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; text-shadow: 0 0 10px rgba(255,223,0,0.5); }
    .stRadio>div { background-color: #111; padding: 10px; border-radius: 10px; border: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 통합 데이터 및 신호 엔진 ---
@st.cache_data(ttl=300)
def get_ultimate_data(name, mode="day"):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None, [], "코드 없음"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 데이터 수집 (이평선 계산을 위해 넉넉히 가져옴)
        p_count = 5 if mode in ["day", "month"] else 1
        all_dfs = []
        for p in range(1, p_count + 1):
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}" if mode != "time" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
            res = requests.get(url, headers=headers, timeout=7)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            if dfs: all_dfs.append(dfs[0].dropna())
        
        df = pd.concat(all_dfs)
        if mode in ["day", "month"]:
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            df = df.set_index('날짜').sort_index()
            # 이평선 및 크로스 로직
            df['MA5'] = df['종가'].rolling(window=5).mean()
            df['MA20'] = df['종가'].rolling(window=20).mean()
            df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
            df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        else:
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            
        # 뉴스 데이터
        n_url = "https://finance.naver.com/news/mainnews.naver"
        n_res = requests.get(n_url, headers=headers, timeout=5)
        soup = BeautifulSoup(n_res.text, 'html.parser')
        headlines = [item.get_text(strip=True) for item in soup.select('.articleSubject a')[:8]]
        
        return df, headlines, "성공"
    except Exception as e: return None, [], str(e)

# --- 3. 메인 실행부 ---
st.markdown('<p class="main-title">Aegis Omni-Signal v30.0</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("📡 감시 종목")
    target_stock = st.selectbox("리스트", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.divider()
    view_mode = st.radio("차트 주기", ["1분봉", "5분봉", "일봉", "월봉"], index=2)

df, headlines, msg = get_ultimate_data(target_stock, "day" if view_mode == "일봉" else "month" if view_mode == "월봉" else "time")

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 패턴 차트", "🌡️ [2P] AI 점수 연동", "🔍 [3P] 뉴스/테마"])

    # --- 1페이지: 통합 멀티 차트 (신호/패턴/줌방지) ---
    with tab1:
        st.subheader(f"[{target_stock}] {view_mode} 정밀 분석")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        if view_mode in ["일봉", "월봉"]:
            # 캔들 및 이평선
            fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                         increasing_line_color='#ff0055', decreasing_line_color='#00f2ff', name='시세'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ffdf00', width=1.5), name='5선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1.5, dash='dot'), name='20선'), row=1, col=1)
            
            # 패턴 분석 (최근 15일 기준 빗각/파동)
            idx = np.arange(len(df))
            h_fit = np.polyfit(idx[-15:], df['고가'].iloc[-15:], 1)
            l_fit = np.polyfit(idx[-15:], df['저가'].iloc[-15:], 1)
            wave_idx = [len(df)-20, len(df)-15, len(df)-10, len(df)-5, len(df)-1]
            fig.add_trace(go.Scatter(x=df.index[wave_idx], y=df['종가'].iloc[wave_idx], mode='lines+markers+text', 
                                     text=['1','2','3','4','5'], line=dict(color='orange', width=2), name='파동'), row=1, col=1)
            
            # 골든/데드크로스 신호
            for date in df[df['GC']].index:
                fig.add_annotation(x=date, y=df.loc[date,'저가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), yshift=-10, row=1, col=1)
            for date in df[df['DC']].index:
                fig.add_annotation(x=date, y=df.loc[date,'고가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), yshift=10, row=1, col=1)
        else:
            # 분봉 선형 차트
            fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00e5ff'), name=view_mode), row=1, col=1)

        # 거래량 및 레이아웃
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 2페이지: AI 온도계 (실시간 체크 연동) ---
    with tab2:
        st.subheader("🤖 AI 전략 온도계")
        bonus = 0
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.checkbox("골든크로스 신호 확인"): bonus += 20
        with c2: 
            if st.checkbox("엘리어트 3파 진행 중"): bonus += 15
        with c3: 
            if st.checkbox("삼각수렴 상단 돌파"): bonus += 10
            
        score = 45 + bonus
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ffdf00"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
        st.write(f"### 최종 판단: **{'강력 매수' if score >= 70 else '관망'}**")

    # --- 3페이지: 뉴스/테마 ---
    with tab3:
        st.subheader("🔍 실시간 뉴스 및 테마")
        for h in headlines: st.write(f"- {h}")
        st.divider()
        st.table(pd.DataFrame({'테마': ['반도체', 'AI', '자동차'], '상태': ['🔥급등', '✨골든', '⚖️조정']}))

else: st.error("데이터 로드 실패")
