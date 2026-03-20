import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Intelligent v32.0")
st.markdown("""
    <style>
    .stMetric { background-color: #0d0d0d; border: 1px solid #333; padding: 15px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 엔진 ---
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
            df['MA5'] = df['종가'].rolling(window=5).mean()
            df['MA20'] = df['종가'].rolling(window=20).mean()
            df['GC_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
            df['DC_Signal'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        else:
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
        
        n_res = requests.get("https://finance.naver.com/news/mainnews.naver", headers=headers, timeout=5)
        headlines = [item.get_text(strip=True) for item in BeautifulSoup(n_res.text, 'html.parser').select('.articleSubject a')[:5]]
        return df, headlines, "성공"
    except Exception as e: return None, [], str(e)

# --- 3. 메인 화면 및 사이드바 옵션 ---
st.markdown('<p class="main-title">Aegis Intelligent v32.0</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("📡 종목 및 주기")
    target_stock = st.selectbox("분석 종목", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    view_mode = st.radio("차트 주기", ["1분봉", "5분봉", "일봉", "월봉"], index=2)
    
    st.divider()
    st.subheader("🛠️ 분석 도구 설정")
    show_wave = st.checkbox("엘리어트 파동 (1-5)", value=True)
    show_angle = st.checkbox("삼각수렴 빗각", value=True)
    show_lines = st.checkbox("지지/저항 수평선", value=True)
    show_cross = st.checkbox("골든/데드 크로스", value=True)

df, headlines, msg = get_intelligent_data(target_stock, "day" if view_mode == "일봉" else "month" if view_mode == "월봉" else "time")

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 맞춤 패턴 차트", "🌡️ [2P] AI 자동 온도계", "🔍 [3P] 시장 리포트"])

    # --- 1페이지: 커스텀 레이어 차트 ---
    with tab1:
        curr_p = df['종가'].iloc[-1] if '종가' in df.columns else df['종가'].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수가", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표가 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 손절가 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        if view_mode in ["일봉", "월봉"]:
            fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'], name='시세'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ffdf00', width=1.5), name='5선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1.2, dash='dot'), name='20선'), row=1, col=1)
            
            # 패턴 계산
            idx = np.arange(len(df))
            if show_angle:
                h_fit = np.polyfit(idx[-15:], df['고가'].iloc[-15:], 1)
                l_fit = np.polyfit(idx[-15:], df['저가'].iloc[-15:], 1)
                fig.add_trace(go.Scatter(x=df.index[-15:], y=h_fit[0]*idx[-15:]+h_fit[1], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index[-15:], y=l_fit[0]*idx[-15:]+l_fit[1], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)
            
            if show_wave:
                wave_idx = [len(df)-20, len(df)-15, len(df)-10, len(df)-5, len(df)-1]
                fig.add_trace(go.Scatter(x=df.index[wave_idx], y=df['종가'].iloc[wave_idx], mode='lines+markers+text', 
                                         text=['1','2','3','4','5'], line=dict(color='orange', width=2), name='파동'), row=1, col=1)
            
            if show_lines:
                fig.add_hline(y=df['고가'].tail(60).max(), line_dash="solid", line_color="red", opacity=0.3, row=1, col=1)
                fig.add_hline(y=df['저가'].tail(60).min(), line_dash="solid", line_color="dodgerblue", opacity=0.3, row=1, col=1)

            if show_cross:
                for date in df[df.get('GC_Signal', False)].index:
                    fig.add_annotation(x=date, y=df.loc[date,'저가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), yshift=-10, row=1, col=1)
                for date in df[df.get('DC_Signal', False)].index:
                    fig.add_annotation(x=date, y=df.loc[date,'고가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), yshift=10, row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00e5ff'), name=view_mode), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 2페이지: AI 자동 온도계 ---
    with tab2:
        st.subheader("🌡️ AI 실시간 진단 온도계")
        is_gc = df['GC_Signal'].tail(5).any() if 'GC_Signal' in df.columns else False
        is_uptrend = curr_p > df['MA20'].iloc[-1] if 'MA20' in df.columns else False
        score = 40 + (25 if is_gc else 0) + (15 if is_uptrend else 0)
        
        col_chk, col_gauge = st.columns([1, 1.5])
        with col_chk:
            st.write("### AI 분석 리포트")
            st.checkbox("골든크로스 발생", value=is_gc, disabled=True)
            st.checkbox("20일선 위 시세 형성", value=is_uptrend, disabled=True)
            st.metric("종합 분석 점수", f"{score}점")

        with col_gauge:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score,
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ffdf00"},
                       'steps': [{'range': [0, 50], 'color': "#333"}, {'range': [50, 100], 'color': "#111"}]}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    # --- 3페이지: 뉴스 ---
    with tab3:
        for h in headlines: st.write(f"- {h}")
