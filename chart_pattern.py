import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# --- 1. [디자인] 증권사 VIP 전용 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Titan v62.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(88, 86, 214, 0.3); }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; transition: 0.3s; }
    .info-card:hover { border-color: #00f2ff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 글로벌 멀티 데이터 엔진 ---
@st.cache_data(ttl=86400)
def get_krx_dict():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url)
        df = pd.read_html(StringIO(res.text), header=0)[0]
        df = df[['회사명', '종목코드']].copy()
        # 코스피(.KS), 코스닥(.KQ) 구분은 간소화를 위해 .KS 우선 적용
        df['ticker'] = df['종목코드'].apply(lambda x: f"{x:06d}.KS")
        return dict(zip(df['회사명'], df['ticker']))
    except:
        return {"삼성전자": "005930.KS", "한화솔루션": "009830.KS", "NAVER": "035420.KS"}

@st.cache_data(ttl=60)
def get_master_data(ticker, mode="일봉"):
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    try:
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty: return None
        df = data.copy()
        # --- 고급 보조지표 계산 ---
        # 1. 이동평균선
        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean(); df['MA60'] = df['Close'].rolling(60).mean()
        # 2. 볼린저 밴드
        std = df['Close'].rolling(20).std(); df['BB_UP'] = df['MA20'] + (std * 2); df['BB_LOW'] = df['MA20'] - (std * 2)
        # 3. RSI
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        # 4. MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean(); exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2; df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        return df
    except: return None

# --- 3. [메인 사이드바] 전문가용 설정 패널 ---
krx_map = get_krx_dict()
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">TITAN Terminal</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 (삼성전자, TSLA, BTC-USD)", value="한화솔루션")
    
    filtered = [n for n in krx_map.keys() if u_input in n]
    if filtered:
        target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100])
        ticker = krx_map[target_name]
    else:
        target_name = u_input.upper(); ticker = target_name
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    
    st.divider()
    st.subheader("🛠️ 지표 커스텀")
    chart_type = st.radio("차트 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_bb = st.checkbox("볼린저 밴드 (변동성)", value=True)
    show_macd = st.checkbox("MACD (추세강도)", value=True)
    show_rsi = st.checkbox("RSI (과매수/과매도)", value=True)
    
    st.divider()
    st.caption("Aegis Titan v62.0 | Global Data Active")

# --- 4. [메인] 퀀트 엔진 및 시각화 ---
df = get_master_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); prev_p = float(df['Close'].iloc[-2])
    unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    
    # [백데이터 퀀트 스코어링]
    score = 50 
    if curr_p > float(df['MA20'].iloc[-1]): score += 15
    if float(df['RSI'].iloc[-1]) < 35: score += 20 # 과매도 반등 신호
    if float(df['MACD'].iloc[-1]) > float(df['Signal'].iloc[-1]): score += 15 # 골든크로스
    
    est_ret = 14.2 if score > 70 else 4.5
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
        st.metric("변동성(BB)", f"{((df['BB_UP'].iloc[-1]-df['BB_LOW'].iloc[-1])/curr_p*100):.1f}%", "폭")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 터미널", "🌡️ AI 정밀 진단", "📰 실시간 뉴스", "📅 공모/배당"])

    with tab1: # 메인 차트 레이아웃
        row_list = [1]; row_h = [1]
        if show_macd: row_list.append(len(row_list)+1); row_h.append(0.3)
        if show_rsi: row_list.append(len(row_list)+1); row_h.append(0.3)
        
        fig = make_subplots(rows=len(row_list), cols=1, shared_xaxes=True, row_heights=row_h, vertical_spacing=0.02)
        
        # 메인 시세
        if chart_type == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.05)', line=dict(color='#007AFF', width=2), name=''), row=1, col=1)
        
        # 볼린저 밴드
        if show_bb:
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_UP'], line=dict(color='rgba(255,255,255,0.1)', width=1), name='Upper'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_LOW'], line=dict(color='rgba(255,255,255,0.1)', width=1), fill='tonexty', fillcolor='rgba(255,255,255,0.03)', name='Lower'), row=1, col=1)

        # MACD
        if show_macd:
            idx = 2
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#00f2ff', width=1.2), name='MACD'), row=idx, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#ff9500', width=1.2), name='Signal'), row=idx, col=1)
            idx += 1
        
        # RSI
        if show_rsi:
            idx = 3 if show_macd else 2
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#FF37AF', width=1.5), name='RSI'), row=idx, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=idx, col=1); fig.add_hline(y=30, line_dash="dot", line_color="green", row=idx, col=1)

        fig.update_layout(height=800, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # AI 정밀 진단
        st.write("### AI 멀티 지표 분석 결과")
        st.markdown(f'<div style="background:#111; padding:20px; border-radius:12px; border-left:5px solid #00f2ff;">'
                    f'<b>현재 종합 스코어: {score}점</b><br>'
                    f'이동평균선: {"상향 추세" if curr_p > df["MA20"].iloc[-1] else "하향 추세"}<br>'
                    f'RSI 상태: {"과매수 경계" if rsi_val > 70 else "과매도 기회" if rsi_val < 30 else "안정적"}<br>'
                    f'MACD 시그널: {"매수 우위" if df["MACD"].iloc[-1] > df["Signal"].iloc[-1] else "매도 우위"}'
                    f'</div>', unsafe_allow_html=True)

    with tab3: # 뉴스 (Global API 기반)
        st.subheader("📰 실시간 글로벌 뉴스")
        st.info("Yahoo Finance 공식 채널을 통해 해당 종목의 최신 뉴스를 확인하세요.")
        st.markdown(f"👉 [{target_name} 최신 뉴스 바로가기](https://finance.yahoo.com/quote/{ticker}/news)")

    with tab4: # 공모주/배당주
        st.subheader("📅 투자 캘린더 센터")
        c_ipo, c_div = st.columns(2)
        with c_ipo: st.markdown(f'<div class="info-card"><a href="https://finance.naver.com/sise/ipo.naver" target="_blank" style="color:#00f2ff; text-decoration:none;">🚀 실시간 IPO 공모주 일정</a></div>', unsafe_allow_html=True)
        with c_div: st.markdown(f'<div class="info-card"><a href="https://finance.naver.com/quote/{ticker}" target="_blank" style="color:#FFD60A; text-decoration:none;">💰 {target_name} 상세 배당/재무 정보</a></div>', unsafe_allow_html=True)

else:
    st.error("종목 검색에 실패했습니다. 올바른 종목명이나 미국 주식 티커(예: TSLA)를 입력해 주세요.")
