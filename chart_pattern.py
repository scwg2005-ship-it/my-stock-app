import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 및 레이아웃 ---
st.set_page_config(layout="wide", page_title="Aegis Intelligent v31.0")
st.markdown("""
    <style>
    .stMetric { background-color: #0d0d0d; border: 1px solid #333; padding: 15px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    .status-box { background-color: #111; padding: 20px; border-radius: 15px; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 스마트 데이터 엔진 (신호 자동 분석) ---
@st.cache_data(ttl=300)
def get_intelligent_data(name, mode="day"):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None, [], "코드 오류"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "time" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=7)
        df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
        
        if mode in ["day", "month"]:
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            df = df.set_index('날짜').sort_index()
            # 기술적 지표 계산
            df['MA5'] = df['종가'].rolling(window=5).mean()
            df['MA20'] = df['종가'].rolling(window=20).mean()
            # 자동 신호 포착
            df['GC_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
            df['DC_Signal'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        else:
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            
        # 뉴스 수집
        n_res = requests.get("https://finance.naver.com/news/mainnews.naver", headers=headers, timeout=5)
        headlines = [item.get_text(strip=True) for item in BeautifulSoup(n_res.text, 'html.parser').select('.articleSubject a')[:5]]
        
        return df, headlines, "성공"
    except Exception as e: return None, [], str(e)

# --- 3. 메인 화면 ---
st.markdown('<p class="main-title">Aegis Intelligent v31.0</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    view_mode = st.radio("주기 선택", ["1분봉", "5분봉", "일봉", "월봉"], index=2)
    st.divider()
    st.caption("AI 자동 진단 시스템 가동 중")

df, headlines, msg = get_intelligent_data(target_stock, "day" if view_mode == "일봉" else "month" if view_mode == "월봉" else "time")

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 차트 및 매매가", "🌡️ [2P] AI 자동 온도계", "🔍 [3P] 시장 리포트"])

    # --- 1페이지: 통합 차트 + 매수/매도/손절가 ---
    with tab1:
        curr_p = df['종가'].iloc[-1] if '종가' in df.columns else df['종가'].iloc[0]
        
        # 핵심 가격 정보 상단 배치
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수가", f"{curr_p * 0.99:,.0f}원", "진입 대기")
        c2.metric("🚀 목표가 (익절)", f"{curr_p * 1.12:,.0f}원", "+12%")
        c3.metric("⚠️ 손절가 (리스크)", f"{curr_p * 0.94:,.0f}원", "-6%")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        if view_mode in ["일봉", "월봉"]:
            fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'], name='시세'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ffdf00', width=1.5), name='5선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1.2, dash='dot'), name='20선'), row=1, col=1)
            
            # 골든/데드 신호 시각화
            for date in df[df.get('GC_Signal', False)].index:
                fig.add_annotation(x=date, y=df.loc[date,'저가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), yshift=-10, row=1, col=1)
            for date in df[df.get('DC_Signal', False)].index:
                fig.add_annotation(x=date, y=df.loc[date,'고가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), yshift=10, row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00e5ff'), name=view_mode), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 2페이지: AI 자동 체크 및 온도계 ---
    with tab2:
        st.subheader("🌡️ AI 실시간 진단 온도계")
        
        # AI 자동 판단 로직
        is_gc = df['GC_Signal'].tail(5).any() if 'GC_Signal' in df.columns else False
        is_uptrend = curr_p > df['MA20'].iloc[-1] if 'MA20' in df.columns else False
        is_vol_up = df['거래량'].iloc[-1] > df['거래량'].mean() if '거래량' in df.columns else False
        
        score = 40
        if is_gc: score += 25
        if is_uptrend: score += 15
        if is_vol_up: score += 10
        
        col_chk, col_gauge = st.columns([1, 1.5])
        
        with col_chk:
            st.write("### AI 자동 체크리스트")
            st.checkbox("골든크로스 발생 (최근 5일)", value=is_gc, disabled=True)
            st.checkbox("20일 이평선 상단 위치", value=is_uptrend, disabled=True)
            st.checkbox("평균 거래량 상회", value=is_vol_up, disabled=True)
            st.info(f"현재 AI 판단 근거에 따라 {score}점이 산출되었습니다.")

        with col_gauge:
            # 부활한 AI 온도계
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score,
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': "#ffdf00"},
                    'steps': [
                        {'range': [0, 40], 'color': "#333"},
                        {'range': [40, 70], 'color': "#555"},
                        {'range': [70, 100], 'color': "#222"}
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 90}
                }
            ))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=0))
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    # --- 3페이지: 뉴스 ---
    with tab3:
        st.subheader("🔍 뉴스 브리핑")
        for h in headlines: st.write(f"- {h}")
        st.divider()
        st.table(pd.DataFrame({'항목': ['시장심리', '외인수급', '기관수급'], '상태': ['안정', '매수우위', '관망']}))

else: st.error("데이터 로드 중 오류가 발생했습니다.")
