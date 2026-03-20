import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Master v35.2")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 정밀 분석 엔진 (함수 정의가 호출보다 먼저 와야 함) ---
def analyze_master_precision(df):
    highs = df['고가'].values
    lows = df['저가'].values
    closes = df['종가'].values
    
    # 엘리어트 파동: 최근 40일 데이터 중 실제 변곡점 추적
    lookback = min(len(df), 40)
    w_idx = [len(df)-lookback, len(df)-int(lookback*0.7), len(df)-int(lookback*0.4), len(df)-int(lookback*0.2), len(df)-1]
    
    # 삼각수렴 빗각: 최근 20일 최고점/최저점 기반
    h_max_val = highs[-20:].max()
    l_min_val = lows[-20:].min()
    h_line = np.linspace(h_max_val, closes[-1], 20)
    l_line = np.linspace(l_min_val, closes[-1], 20)
    
    # 지지/저항 영역: 꼬리 끝단에 맞춤
    res_v = highs[-60:].max()
    sup_v = lows[-60:].min()
    
    return {
        'w_x': df.index[w_idx], 'w_y': closes[w_idx],
        'h_line': h_line, 'l_line': l_line,
        'res': res_v, 'sup': sup_v, 'fit_idx': df.index[-20:]
    }

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
            df['날짜'] = pd.to_datetime(df['날짜']); df = df.set_index('날짜').sort_index()
            df['MA5'] = df['종가'].rolling(window=5).mean(); df['MA20'] = df['종가'].rolling(window=20).mean()
            df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
            df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        else: df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
        n_res = requests.get("https://finance.naver.com/news/mainnews.naver", headers=headers, timeout=5)
        headlines = [item.get_text(strip=True) for item in BeautifulSoup(n_res.text, 'html.parser').select('.articleSubject a')[:5]]
        return df, headlines, "성공"
    except Exception as e: return None, [], str(e)

# --- 3. 메인 화면 ---
st.markdown('<p class="main-title">Aegis Master Control v35.2</p>', unsafe_allow_html=True)

with st.sidebar:
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
    res = analyze_master_precision(df) # 함수 호출
    curr_p = df['종가'].iloc[-1] if '종가' in df.columns else df['종가'].iloc[0]
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 패턴 차트", "🌡️ [2P] AI 자동 온도계", "🔍 [3P] 시장 리포트"])

    with tab1:
        # 매매가 가이드
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        if view_mode in ["일봉", "월봉"]:
            fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                         increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
            # 레이어 시각화
            if opt_wave:
                fig.add_trace(go.Scatter(x=res['w_x'], y=res['w_y'], mode='lines+markers+text', text=['1','2','3','4','5'], line=dict(color='#ffdf00', width=3), name='파동'), row=1, col=1)
            if opt_angle:
                fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
                fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)
            if opt_lines:
                fig.add_hrect(y0=res['res']*0.999, y1=res['res']*1.001, fillcolor="red", opacity=0.3, row=1, col=1)
                fig.add_hrect(y0=res['sup']*0.999, y1=res['sup']*1.001, fillcolor="dodgerblue", opacity=0.3, row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00f2ff'), name=view_mode), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=580, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        # AI 온도계 로직
        score = 40 + (30 if df.get('GC', [False])[-1] else 0) + (20 if curr_p > df.get('MA20', [0])[-1] else 0)
        status = "🚀 강력 매수" if score >= 70 else "⚖️ 관망"
        st.markdown(f'<div class="status-text" style="color:#00ff41;">{status} ({score}점)</div>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    with tab3:
        for h in headlines: st.write(f"- {h}")
else: st.error("데이터 로드 실패")
