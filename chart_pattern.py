import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 통합 프리미엄 네온 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Master v35.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; box-shadow: 0 0 15px rgba(0,242,255,0.15); }
    .main-title { font-size: 2.5rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 30px; text-shadow: 0 0 12px rgba(255,223,0,0.6); text-transform: uppercase; }
    .stTabs>div { background-color: #0a0a0a; border-radius: 10px; border: 1px solid #222; }
    .stRadio>div { background-color: #111; padding: 10px; border-radius: 10px; border: 1px solid #222; }
    /* 상태 메시지 스타일 */
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 스마트 데이터 엔진 ---
@st.cache_data(ttl=300)
def get_master_data(name, mode="day"):
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

# --- 3. 메인 화면 ---
st.markdown('<p class="main-title">Aegis Master Control v35.0</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("📡 종목 및 주기")
    target_stock = st.selectbox("분석 종목", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    view_mode = st.radio("차트 주기", ["1분봉", "5분봉", "일봉", "월봉"], index=2)
    st.divider()
    st.subheader("🛠️ 분석 도구 레이어")
    opt_wave = st.checkbox("엘리어트 파동 (1-5)", value=True)
    opt_angle = st.checkbox("삼각수렴 빗각 분석", value=True)
    opt_lines = st.checkbox("지지/저항 영역 표시", value=True)
    opt_cross = st.checkbox("골든/데드크로스 신호", value=True)

df, headlines, msg = get_master_data(target_stock, "day" if view_mode == "일봉" else "month" if view_mode == "월봉" else "time")

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1] if '종가' in df.columns else df['종가'].iloc[0]
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 패턴 차트", "🌡️ [2P] AI 자동 온도계", "🔍 [3P] 시장 리포트"])

    # --- 1페이지 (이전과 동일 - 고시인성 네온 차트) ---
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        if view_mode in ["일봉", "월봉"]:
            fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                         increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#00f2ff', width=1.5), name='5선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1, dash='dot'), 
                                     fill='tonexty', fillcolor='rgba(0, 242, 255, 0.05)', name='20선'), row=1, col=1)
            if opt_angle:
                idx = np.arange(len(df)); h_fit = np.polyfit(idx[-15:], df['고가'].iloc[-15:], 1); l_fit = np.polyfit(idx[-15:], df['저가'].iloc[-15:], 1)
                fig.add_trace(go.Scatter(x=df.index[-15:], y=h_fit[0]*idx[-15:]+h_fit[1], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index[-15:], y=l_fit[0]*idx[-15:]+l_fit[1], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)
            if opt_wave:
                wave_idx = [len(df)-20, len(df)-15, len(df)-10, len(df)-5, len(df)-1]
                fig.add_trace(go.Scatter(x=df.index[wave_idx], y=df['종가'].iloc[wave_idx], mode='lines+markers+text', text=['1','2','3','4','5'], 
                                         textfont=dict(color="white", size=14), line=dict(color='#ffdf00', width=3), name='파동'), row=1, col=1)
            if opt_lines:
                res_v = df['고가'].tail(60).max(); sup_v = df['저가'].tail(60).min()
                fig.add_hrect(y0=res_v*0.998, y1=res_v*1.002, fillcolor="red", opacity=0.15, line_width=0, row=1, col=1)
                fig.add_hrect(y0=sup_v*0.998, y1=sup_v*1.002, fillcolor="dodgerblue", opacity=0.15, line_width=0, row=1, col=1)
            if opt_cross:
                for date in df[df.get('GC_Signal', False)].index:
                    fig.add_annotation(x=date, y=df.loc[date,'저가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), row=1, col=1)
                for date in df[df.get('DC_Signal', False)].index:
                    fig.add_annotation(x=date, y=df.loc[date,'고가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00f2ff', width=2), name=view_mode), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=580, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False, paper_bgcolor='black', plot_bgcolor='black')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 2페이지 (AI 온도계 가이드 업데이트) ---
    with tab2:
        st.subheader("🌡️ AI 정밀 진단 시스템")
        # 점수 계산 로직
        is_gc = df['GC_Signal'].tail(5).any() if 'GC_Signal' in df.columns else False
        is_uptrend = curr_p > df['MA20'].iloc[-1] if 'MA20' in df.columns else False
        is_vol = df['거래량'].iloc[-1] > df['거래량'].mean() if '거래량' in df.columns else False
        
        score = 30 + (30 if is_gc else 0) + (20 if is_uptrend else 0) + (10 if is_vol else 0)
        
        # 점수별 상태 및 색상 정의
        if score >= 80: status, color = "🚀 강력 매수 (Strong Buy)", "#00ff41"
        elif score >= 60: status, color = "✅ 매수 권장 (Buy)", "#00f2ff"
        elif score >= 40: status, color = "⚖️ 관망 유지 (Neutral)", "#ffdf00"
        elif score >= 20: status, color = "📉 매도 주의 (Sell)", "#ff9100"
        else: status, color = "💀 강력 매도 (Strong Sell)", "#ff0055"

        c_chk, c_gauge = st.columns([1, 1.5])
        with c_chk:
            st.write("### AI 자동 분석 지표")
            st.checkbox("골든크로스 컨펌", value=is_gc, disabled=True)
            st.checkbox("이평선 정배열 추세", value=is_uptrend, disabled=True)
            st.checkbox("거래량 동반 상승", value=is_vol, disabled=True)
            st.divider()
            # 상태 텍스트 표시
            st.markdown(f'<div class="status-text" style="color:{color}; border: 2px solid {color};">{status}</div>', unsafe_allow_html=True)
            st.write(f"\n현재 지표 점수: **{score}점**")

        with c_gauge:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score,
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': color},
                    'bgcolor': "#111",
                    'steps': [
                        {'range': [0, 20], 'color': "rgba(255,0,85,0.1)"},
                        {'range': [20, 40], 'color': "rgba(255,145,0,0.1)"},
                        {'range': [40, 60], 'color': "rgba(255,223,0,0.1)"},
                        {'range': [60, 80], 'color': "rgba(0,242,255,0.1)"},
                        {'range': [80, 100], 'color': "rgba(0,255,65,0.1)"}
                    ],
                    'threshold': {'line': {'color': color, 'width': 4}, 'thickness': 0.75, 'value': score}
                }
            ))
            fig_g.update_layout(height=380, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=50, b=0))
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    # --- 3페이지 ---
    with tab3:
        st.subheader("🔍 리포트")
        for h in headlines: st.write(f"- {h}")
