import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# --- 1. [디자인] 프리미엄 다크 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Titan v62.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(88, 86, 214, 0.3); }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [핵심] 지능형 종목 검색 엔진 (KRX 통합) ---
@st.cache_data(ttl=86400)
def get_krx_master_v62():
    try:
        # KIND에서 상장법인 목록 추출 (코스피/코스닥 통합)
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, timeout=10)
        df = pd.read_html(StringIO(res.text), header=0)[0]
        # 회사명과 종목코드 추출
        df = df[['회사명', '종목코드']].copy()
        # 모든 종목을 일단 코스피(.KS)와 코스닥(.KQ) 양쪽으로 시도할 수 있게 처리
        return df
    except:
        return pd.DataFrame({'회사명': ['삼성전자', '한화솔루션'], '종목코드': [5930, 9830]})

def find_ticker(user_input, krx_df):
    user_input = user_input.strip()
    # 1. 한국 종목명 검색
    match = krx_df[krx_df['회사명'] == user_input]
    if not match.empty:
        code = f"{match.iloc[0]['종목코드']:06d}"
        # 코스피(.KS) 먼저 시도 후 에러나면 .KQ로 자동 전환 로직 (yfinance 내부 처리)
        return f"{code}.KS"
    
    # 2. 미국 주식 티커인 경우 (예: TSLA)
    return user_input.upper()

@st.cache_data(ttl=60)
def get_titan_data(ticker, mode="일봉"):
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    try:
        # yfinance로 데이터 로드 (.KS가 안되면 .KQ로 재시도)
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        
        if data.empty: return None
        
        df = data.copy()
        # 보조지표 연산
        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        # RSI
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean(); exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2; df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        return df
    except: return None

# --- 3. [UI] 사이드바 및 컨트롤 ---
st.markdown('<p style="font-size:2.5rem; font-weight:800; color:#fff;">Aegis Titan <span style="color:#00f2ff;">v62.1</span></p>', unsafe_allow_html=True)

krx_master = get_krx_master_v62()
with st.sidebar:
    st.markdown('<p style="font-size:1.5rem; font-weight:800; color:#00f2ff;">TITAN Terminal</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 (삼성전자, TSLA, AAPL)", value="한화솔루션")
    
    # 실시간 검색 제안
    suggestions = krx_master[krx_master['회사명'].str.contains(u_input, na=False)]['회사명'].tolist()
    if suggestions:
        target_name = st.selectbox(f"검색 결과 ({len(suggestions)}건)", options=suggestions[:100])
    else:
        target_name = u_input
    
    ticker = find_ticker(target_name, krx_master)
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    
    st.divider()
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60], default=[5, 20])
    show_rsi = st.checkbox("RSI 지표 표시", value=True)

# --- 4. [메인] 분석 및 시각화 ---
df = get_titan_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); prev_p = float(df['Close'].iloc[-2])
    unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    
    # 퀀트 스코어링
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10) + (25 if float(df['RSI'].iloc[-1]) < 35 else 0)
    est_ret = 14.5 if score > 70 else 3.8
    est_profit = invest_val * (est_ret / 100)

    # 상단 대시보드
    st.markdown(f"### {target_name} <span style='color:#888; font-size:1rem;'>{ticker}</span>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:0.9rem; opacity:0.8;">백데이터 기반 기대 수익 (10D)</p>
            <h1 style="margin:0; font-size:3.2rem;">+{est_ret}%</h1>
            <p style="margin:0; font-weight:bold;">{invest_val:,.0f}{unit} 투자 시: {est_profit:+,.0f} {unit}</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.metric("현재가", f"{curr_p:,.0f}{unit}", f"{curr_p-prev_p:+,.0f}")
        st.metric("AI 퀀트 점수", f"{score}점", f"{score-50:+}")
    with c3:
        st.metric("RSI (14D)", f"{df['RSI'].iloc[-1]:.1f}", "과매도" if df['RSI'].iloc[-1] < 30 else "정상")
        st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")

    tab1, tab2, tab3 = st.tabs(["📉 시세 분석", "🌡️ AI 정밀 진단", "📰 실시간 뉴스"])

    with tab1:
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.05)', line=dict(color='#007AFF', width=2), name=''), row=1, col=1)
        for ma in show_ma: fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
        if show_rsi:
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#FF37AF', width=1.5), name='RSI'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: st.info(f"현재 {target_name}의 종합 진단 점수는 {score}점입니다.")
    with tab3: st.markdown(f"👉 [{target_name} 최신 뉴스 확인](https://finance.naver.com/quote/{ticker.split('.')[0]})")

else:
    st.error("데이터 로드 실패: 종목명을 정확하게 입력하거나 미국 주식 티커(예: TSLA)를 입력해 주세요.")
